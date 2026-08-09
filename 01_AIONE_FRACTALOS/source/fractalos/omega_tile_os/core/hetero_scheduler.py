from __future__ import annotations

from pathlib import Path
from typing import Any

from .perf_governor import PerformanceGovernor


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _gpu_capacity(gpu: dict[str, Any]) -> float:
    temp = float(gpu.get("temperature_c") or 55.0)
    util = float(gpu.get("utilization", 0.0))
    mem = float(gpu.get("memory_utilization", 0.0))
    power_draw = gpu.get("power_draw_w")
    power_limit = gpu.get("power_limit_w")
    power_ratio = 0.45
    if power_draw is not None and power_limit:
        power_ratio = _clamp(float(power_draw) / max(float(power_limit), 1.0), 0.0, 1.0)

    thermal = _clamp((78.0 - temp) / 44.0, 0.0, 1.0)
    compute = 1.0 - _clamp(util, 0.0, 1.0)
    memory = 1.0 - _clamp(mem, 0.0, 1.0)
    power = 1.0 - power_ratio
    return round((0.40 * thermal) + (0.30 * compute) + (0.20 * memory) + (0.10 * power), 4)


def _cpu_capacity(report: dict[str, Any]) -> float:
    formulas = report["formulas"]
    telemetry = report["telemetry"]
    cpu_util = float(telemetry["cpu"]["utilization"])
    headroom = float(formulas["cpu_headroom"])
    memory_guard = float(formulas["memory_guard"])
    capacity = (0.45 * headroom) + (0.35 * (1.0 - cpu_util)) + (0.20 * memory_guard)
    return round(_clamp(capacity, 0.0, 1.0), 4)


def _job_affinity(job: dict[str, Any]) -> str:
    hint = str(job.get("accelerator_hint", "")).lower()
    if hint in {"gpu", "cpu"}:
        return hint
    if bool(job.get("vectorizable")) or bool(job.get("matrix_heavy")):
        return "gpu"
    if bool(job.get("latency_sensitive")) or bool(job.get("serial")):
        return "cpu"
    return "hybrid"


def _device_score(job: dict[str, Any], device: dict[str, Any]) -> float:
    affinity = _job_affinity(job)
    base = float(device["capacity"])
    complexity = float(job.get("complexity", 0.5))
    risk = float(job.get("risk", 0.3))
    resource = float(job.get("resource_estimate", 1.0))
    data_parallel = 1.0 if bool(job.get("vectorizable")) or bool(job.get("matrix_heavy")) else 0.0
    latency_sensitive = 1.0 if bool(job.get("latency_sensitive")) else 0.0

    affinity_bonus = 0.0
    if affinity == device["kind"]:
        affinity_bonus = 0.18
    elif affinity == "hybrid":
        affinity_bonus = 0.10

    if device["kind"] == "gpu":
        score = base + affinity_bonus + 0.22 * data_parallel - 0.10 * latency_sensitive - 0.08 * risk - 0.04 * resource
    else:
        score = base + affinity_bonus + 0.16 * latency_sensitive + 0.04 * (1.0 - complexity) - 0.05 * risk
    return round(score, 4)


def available_devices(workspace: Path) -> dict[str, Any]:
    report = PerformanceGovernor(workspace).report()
    telemetry = report["telemetry"]
    learned = report.get("learned_profile") or {}

    devices: list[dict[str, Any]] = [
        {
            "id": "cpu.local",
            "kind": "cpu",
            "label": "Ryzen CPU Pool",
            "capacity": _cpu_capacity(report),
            "recommended_concurrency": int(report["recommendations"]["recommended_concurrency"]),
        }
    ]

    gpu_bias = 0.0
    mode = str((learned.get("mode") or report["mode"])).lower()
    if mode == "calibrated-balanced":
        gpu_bias = 0.05
    for index, gpu in enumerate(telemetry.get("gpus", []), start=1):
        capacity = _clamp(_gpu_capacity(gpu) + gpu_bias, 0.0, 1.0)
        devices.append(
            {
                "id": f"gpu.{index}",
                "kind": "gpu",
                "label": str(gpu.get("name", f"GPU {index}")),
                "capacity": round(capacity, 4),
                "temperature_c": gpu.get("temperature_c"),
                "utilization": gpu.get("utilization"),
                "memory_utilization": gpu.get("memory_utilization"),
            }
        )

    return {
        "mode": report["mode"],
        "learned_profile": learned,
        "recommendations": report["recommendations"],
        "devices": devices,
        "formulas": report["formulas"],
    }


def assign_jobs(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = available_devices(workspace)
    devices = snapshot["devices"]
    placements = []

    for job in jobs:
        ranked = sorted(
            (
                {
                    "device_id": device["id"],
                    "label": device["label"],
                    "kind": device["kind"],
                    "score": _device_score(job, device),
                }
                for device in devices
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        best = ranked[0]
        placements.append(
            {
                **job,
                "target_device": best["device_id"],
                "target_kind": best["kind"],
                "scheduler_score": best["score"],
                "scheduler_reason": {
                    "job_affinity": _job_affinity(job),
                    "best_label": best["label"],
                    "alternatives": ranked[1:3],
                },
            }
        )

    return {
        "scheduler": snapshot,
        "placements": placements,
    }
