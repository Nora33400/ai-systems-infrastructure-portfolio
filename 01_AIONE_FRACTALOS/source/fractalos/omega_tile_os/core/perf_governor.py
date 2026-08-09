from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import copy

import psutil

from .state import load_config, load_perf_state, load_state, save_config, save_perf_state, save_state


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class GovernorInputs:
    cpu_utilization: float
    memory_utilization: float
    cpu_temp_c: float | None
    cpu_frequency_ratio: float
    gpu_utilization: float
    gpu_temp_c: float | None
    gpu_memory_utilization: float
    logical_cores: int
    total_memory_bytes: int
    available_memory_bytes: int


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_ratio(value: float) -> float:
    return clamp(value / 100.0 if value > 1.0 else value, 0.0, 1.0)


def _cpu_temperature() -> float | None:
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    if not sensors:
        return None

    candidates: list[float] = []
    for entries in sensors.values():
        for entry in entries:
            label = (getattr(entry, "label", "") or "").lower()
            current = getattr(entry, "current", None)
            if current is None:
                continue
            if label in {"package id 0", "package", "tctl", "tdie", "cpu", "core"}:
                candidates.append(float(current))
            else:
                candidates.append(float(current))
    return max(candidates) if candidates else None


def _query_nvidia_smi() -> list[dict[str, Any]]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return []

    command = [
        nvidia_smi,
        "--query-gpu=name,temperature.gpu,utilization.gpu,utilization.memory,power.draw,power.limit,clocks.current.graphics,clocks.current.memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
    except (subprocess.SubprocessError, OSError):
        return []

    gpus: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 8:
            continue
        gpus.append(
            {
                "name": parts[0],
                "temperature_c": _safe_float(parts[1], default=float("nan")),
                "utilization": _normalize_ratio(_safe_float(parts[2])),
                "memory_utilization": _normalize_ratio(_safe_float(parts[3])),
                "power_draw_w": None if parts[4] in {"[N/A]", "N/A"} else _safe_float(parts[4], default=0.0),
                "power_limit_w": None if parts[5] in {"[N/A]", "N/A"} else _safe_float(parts[5], default=0.0),
                "graphics_clock_mhz": _safe_float(parts[6]),
                "memory_clock_mhz": _safe_float(parts[7]),
            }
        )
    return gpus


def collect_telemetry() -> dict[str, Any]:
    cpu_util = _normalize_ratio(psutil.cpu_percent(interval=0.25))
    per_core = [_normalize_ratio(value) for value in psutil.cpu_percent(interval=None, percpu=True)]
    vm = psutil.virtual_memory()
    freq = psutil.cpu_freq()
    max_freq = _safe_float(getattr(freq, "max", 0.0), default=0.0)
    current_freq = _safe_float(getattr(freq, "current", 0.0), default=0.0)
    cpu_ratio = clamp(current_freq / max(max_freq, current_freq, 1.0), 0.0, 1.0)
    gpus = _query_nvidia_smi()

    return {
        "cpu": {
            "utilization": cpu_util,
            "per_core_utilization": per_core,
            "temperature_c": _cpu_temperature(),
            "current_frequency_mhz": current_freq,
            "max_frequency_mhz": max_freq if max_freq > 0 else current_freq,
            "frequency_ratio": cpu_ratio,
            "logical_cores": psutil.cpu_count(logical=True) or 1,
            "physical_cores": psutil.cpu_count(logical=False) or 1,
        },
        "memory": {
            "utilization": _normalize_ratio(vm.percent),
            "available_bytes": int(vm.available),
            "used_bytes": int(vm.used),
            "total_bytes": int(vm.total),
        },
        "gpus": gpus,
    }


def performance_formulas(inputs: GovernorInputs, config: dict[str, Any]) -> dict[str, float]:
    cfg = config["performance_governor"]

    def thermal_headroom(temp_c: float | None, idle_c: float, safe_c: float) -> float:
        if temp_c is None:
            return float(cfg["thermal_unknown_penalty"])
        return clamp((safe_c - temp_c) / max(safe_c - idle_c, 1.0), 0.0, 1.0)

    cpu_h = thermal_headroom(inputs.cpu_temp_c, float(cfg["cpu_idle_reference_c"]), float(cfg["cpu_safe_temp_c"]))
    gpu_h = thermal_headroom(inputs.gpu_temp_c, float(cfg["gpu_idle_reference_c"]), float(cfg["gpu_safe_temp_c"]))

    pressure_cpu = clamp(
        0.55 * inputs.cpu_utilization
        + 0.20 * inputs.memory_utilization
        + 0.15 * inputs.cpu_frequency_ratio
        + 0.10 * inputs.gpu_utilization,
        0.0,
        1.0,
    )
    pressure_gpu = clamp(0.70 * inputs.gpu_utilization + 0.30 * inputs.gpu_memory_utilization, 0.0, 1.0)
    memory_guard = clamp(
        (float(cfg["memory_target_utilization"]) - inputs.memory_utilization)
        / max(float(cfg["memory_target_utilization"]), 0.01),
        0.0,
        1.0,
    )

    thermal_envelope = math.sqrt(max(cpu_h, 0.0) * max(gpu_h, 0.0))
    stability_index = clamp(
        (thermal_envelope ** 0.9)
        * ((1.0 - pressure_cpu) ** 0.8)
        * ((1.0 - 0.5 * pressure_gpu) ** 0.6)
        * (0.35 + 0.65 * memory_guard),
        0.0,
        1.0,
    )
    throughput_index = clamp(
        (0.45 + 0.55 * stability_index)
        * (0.60 + 0.40 * cpu_h)
        * (0.70 + 0.30 * gpu_h),
        0.0,
        1.0,
    )

    return {
        "cpu_headroom": cpu_h,
        "gpu_headroom": gpu_h,
        "cpu_pressure": pressure_cpu,
        "gpu_pressure": pressure_gpu,
        "memory_guard": memory_guard,
        "thermal_envelope": thermal_envelope,
        "stability_index": stability_index,
        "throughput_index": throughput_index,
    }


class PerformanceGovernor:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.config = load_config(workspace)

    def _refresh_config(self) -> dict[str, Any]:
        self.config = load_config(self.workspace)
        return self.config

    def _effective_config(self) -> dict[str, Any]:
        effective = copy.deepcopy(self.config)
        perf_state = load_perf_state(self.workspace)
        learned = perf_state.get("learned_profile") or {}
        governor_overrides = learned.get("performance_governor", {})
        planner_overrides = learned.get("planner", {})
        omega_ram_overrides = learned.get("omega_ram", {})
        effective["performance_governor"].update(governor_overrides)
        effective["planner"].update(planner_overrides)
        effective["omega_ram"].update(omega_ram_overrides)
        return effective

    def _inputs_from_telemetry(self, telemetry: dict[str, Any]) -> GovernorInputs:
        cpu = telemetry["cpu"]
        memory = telemetry["memory"]
        gpus = telemetry.get("gpus", [])
        dominant_gpu = max(gpus, key=lambda item: item.get("utilization", 0.0), default={})
        gpu_utilization = _safe_float(dominant_gpu.get("utilization", 0.0))
        gpu_temp_c = dominant_gpu.get("temperature_c")
        if isinstance(gpu_temp_c, float) and math.isnan(gpu_temp_c):
            gpu_temp_c = None
        return GovernorInputs(
            cpu_utilization=_safe_float(cpu.get("utilization", 0.0)),
            memory_utilization=_safe_float(memory.get("utilization", 0.0)),
            cpu_temp_c=cpu.get("temperature_c"),
            cpu_frequency_ratio=_safe_float(cpu.get("frequency_ratio", 0.0)),
            gpu_utilization=gpu_utilization,
            gpu_temp_c=gpu_temp_c,
            gpu_memory_utilization=_safe_float(dominant_gpu.get("memory_utilization", 0.0)),
            logical_cores=int(cpu.get("logical_cores", 1)),
            total_memory_bytes=int(memory.get("total_bytes", 0)),
            available_memory_bytes=int(memory.get("available_bytes", 0)),
        )

    def _recommendations(self, inputs: GovernorInputs, formulas: dict[str, float]) -> dict[str, Any]:
        cfg = self.config["performance_governor"]
        omega_ram_cfg = self.config["omega_ram"]
        planner_cfg = self.config["planner"]

        logical_cores = max(inputs.logical_cores, 1)
        min_concurrency = int(cfg["minimum_concurrency"])
        concurrency_scale = 0.25 + 0.75 * formulas["stability_index"]
        recommended_concurrency = max(min_concurrency, min(logical_cores, math.floor(logical_cores * concurrency_scale)))

        total_mem = max(inputs.total_memory_bytes, 1)
        available_ratio = clamp(inputs.available_memory_bytes / total_mem, 0.0, 1.0)
        ram_scale = 0.50 + 1.50 * min(formulas["memory_guard"], available_ratio)
        hot_base = int(omega_ram_cfg.get("baseline_hot_budget_bytes", omega_ram_cfg["hot_budget_bytes"]))
        warm_base = int(omega_ram_cfg.get("baseline_warm_budget_bytes", omega_ram_cfg["warm_budget_bytes"]))
        hot_budget = int(clamp(hot_base * ram_scale, hot_base, int(cfg["hot_budget_cap_bytes"])))
        warm_budget = int(clamp(warm_base * ram_scale * 1.4, warm_base, int(cfg["warm_budget_cap_bytes"])))

        baseline_limit = float(planner_cfg.get("baseline_resource_limit", planner_cfg["default_resource_limit"]))
        resource_limit = max(
            2.0,
            round(baseline_limit * (0.55 + 0.90 * formulas["throughput_index"]), 2),
        )
        baseline_top_k = int(planner_cfg.get("baseline_top_k", planner_cfg["default_top_k"]))
        top_k = max(1, min(recommended_concurrency, max(8, baseline_top_k)))

        risk_level = "low"
        if formulas["stability_index"] < 0.45 or formulas["thermal_envelope"] < 0.45:
            risk_level = "elevated"
        if formulas["stability_index"] < 0.25 or formulas["thermal_envelope"] < 0.25:
            risk_level = "critical"

        return {
            "recommended_concurrency": recommended_concurrency,
            "recommended_planner_top_k": top_k,
            "recommended_resource_limit": resource_limit,
            "recommended_hot_budget_bytes": hot_budget,
            "recommended_warm_budget_bytes": warm_budget,
            "risk_level": risk_level,
        }

    def _smooth_recommendations(
        self,
        current: dict[str, Any],
        previous: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not previous:
            return current

        def ramp_up(prev: int, new: int, step: int = 1) -> int:
            if new <= prev:
                return new
            return min(new, prev + step)

        def soften(prev: float, new: float, growth_limit: float = 1.10) -> float:
            if new <= prev:
                return new
            return min(new, prev * growth_limit)

        smoothed = dict(current)
        smoothed["recommended_concurrency"] = ramp_up(
            int(previous["recommended_concurrency"]),
            int(current["recommended_concurrency"]),
        )
        smoothed["recommended_planner_top_k"] = ramp_up(
            int(previous["recommended_planner_top_k"]),
            int(current["recommended_planner_top_k"]),
        )
        smoothed["recommended_resource_limit"] = round(
            soften(
                float(previous["recommended_resource_limit"]),
                float(current["recommended_resource_limit"]),
                growth_limit=1.08,
            ),
            2,
        )
        smoothed["recommended_hot_budget_bytes"] = int(
            soften(
                float(previous["recommended_hot_budget_bytes"]),
                float(current["recommended_hot_budget_bytes"]),
                growth_limit=1.10,
            )
        )
        smoothed["recommended_warm_budget_bytes"] = int(
            soften(
                float(previous["recommended_warm_budget_bytes"]),
                float(current["recommended_warm_budget_bytes"]),
                growth_limit=1.10,
            )
        )

        severity = {"low": 0, "elevated": 1, "critical": 2}
        prev_risk = str(previous.get("risk_level", "low"))
        new_risk = str(current.get("risk_level", "low"))
        smoothed["risk_level"] = new_risk if severity.get(new_risk, 0) >= severity.get(prev_risk, 0) else prev_risk
        return smoothed

    def sample(self) -> dict[str, Any]:
        self._refresh_config()
        self.config = self._effective_config()
        telemetry = collect_telemetry()
        inputs = self._inputs_from_telemetry(telemetry)
        formulas = performance_formulas(inputs, self.config)
        recommendations = self._recommendations(inputs, formulas)

        sample = {
            "telemetry": telemetry,
            "formulas": formulas,
            "recommendations": recommendations,
        }

        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"] = sample
        perf_state["history"] = (perf_state.get("history", []) + [sample])[-20:]
        save_perf_state(self.workspace, perf_state)
        return sample

    def apply(self) -> dict[str, Any]:
        sample = self.sample()
        raw_recommendations = sample["recommendations"]
        perf_state = load_perf_state(self.workspace)
        last_tuning = perf_state.get("last_tuning") or {}
        previous_tuning = last_tuning.get("recommendations")
        recommendations = self._smooth_recommendations(raw_recommendations, previous_tuning)

        config = self._refresh_config()
        effective = self._effective_config()
        config["planner"]["default_top_k"] = int(recommendations["recommended_planner_top_k"])
        config["planner"]["default_resource_limit"] = float(recommendations["recommended_resource_limit"])
        config["omega_ram"]["hot_budget_bytes"] = int(recommendations["recommended_hot_budget_bytes"])
        config["omega_ram"]["warm_budget_bytes"] = int(recommendations["recommended_warm_budget_bytes"])
        save_config(self.workspace, config)

        perf_state["last_tuning"] = {
            "raw_recommendations": raw_recommendations,
            "recommendations": recommendations,
            "formulas": sample["formulas"],
        }
        save_perf_state(self.workspace, perf_state)

        state = load_state(self.workspace)
        state["node"]["performance_profile"] = config["performance_governor"]["mode"]
        state["node"]["status"] = state["node"].get("status", "idle")
        save_state(self.workspace, state)

        return {
            "applied": True,
            "mode": effective["performance_governor"]["mode"],
            "telemetry": sample["telemetry"],
            "formulas": sample["formulas"],
            "recommendations": recommendations,
            "raw_recommendations": raw_recommendations,
            "learned_profile": perf_state.get("learned_profile"),
        }

    def report(self) -> dict[str, Any]:
        self._refresh_config()
        self.config = self._effective_config()
        perf_state = load_perf_state(self.workspace)
        latest = perf_state.get("last_sample")
        if latest is None:
            latest = self.sample()
            perf_state = load_perf_state(self.workspace)
        return {
            "mode": self.config["performance_governor"]["mode"],
            "telemetry": latest["telemetry"],
            "formulas": latest["formulas"],
            "recommendations": latest["recommendations"],
            "last_tuning": perf_state.get("last_tuning"),
            "learned_profile": perf_state.get("learned_profile"),
            "campaign_count": len(perf_state.get("campaigns", [])),
            "history_size": len(perf_state.get("history", [])),
            "scientific_model": {
                "thermal_headroom": "H = clamp((T_safe - T)/(T_safe - T_idle), 0, 1)",
                "pressure_cpu": "P_cpu = 0.55U_cpu + 0.20U_mem + 0.15F_cpu + 0.10U_gpu",
                "stability_index": "S = (H_cpu*H_gpu)^0.45 * (1-P_cpu)^0.8 * (1-0.5P_gpu)^0.6 * (0.35+0.65M)",
                "throughput_index": "Phi = (0.45+0.55S) * (0.60+0.40H_cpu) * (0.70+0.30H_gpu)",
            },
        }
