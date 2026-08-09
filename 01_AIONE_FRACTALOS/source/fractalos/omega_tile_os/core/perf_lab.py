from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .perf_governor import PerformanceGovernor
from .state import load_perf_state, save_perf_state


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _risk_score(label: str) -> int:
    return {"low": 0, "elevated": 1, "critical": 2}.get(label, 1)


@dataclass
class BenchmarkPolicy:
    workers: int
    batch_size: int
    pause_ms: int
    should_stop: bool
    reason: str


def build_benchmark_policy(report: dict[str, Any], previous: dict[str, Any] | None = None) -> BenchmarkPolicy:
    recommendations = report["recommendations"]
    formulas = report["formulas"]
    stability = float(formulas["stability_index"])
    throughput = float(formulas["throughput_index"])
    risk = str(recommendations["risk_level"])
    prev_risk = str((previous or {}).get("risk_level", "low"))

    workers = max(1, int(recommendations["recommended_concurrency"]))
    batch_size = max(128, int(2048 * (0.25 + throughput)))
    pause_ms = int(30 + (1.0 - stability) * 170)
    should_stop = False
    reason = "running"

    if risk == "critical" and _risk_score(prev_risk) >= 1:
        should_stop = True
        reason = "critical risk persisted"
    elif stability < 0.18:
        should_stop = True
        reason = "stability floor breached"
    elif formulas["thermal_envelope"] < 0.22:
        should_stop = True
        reason = "thermal envelope collapsed"

    return BenchmarkPolicy(
        workers=workers,
        batch_size=batch_size,
        pause_ms=pause_ms,
        should_stop=should_stop,
        reason=reason,
    )


def summarize_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "stability_mean": 0.0,
            "stability_min": 0.0,
            "throughput_mean": 0.0,
            "pressure_wave": 0.0,
            "risk_peak": "low",
        }

    stabilities = [float(item["formulas"]["stability_index"]) for item in history]
    throughputs = [float(item["formulas"]["throughput_index"]) for item in history]
    cpu_pressures = [float(item["formulas"]["cpu_pressure"]) for item in history]
    risk_peak = max((str(item["recommendations"]["risk_level"]) for item in history), key=_risk_score)

    pressure_wave = 0.0
    if len(cpu_pressures) > 1:
        deltas = [abs(b - a) for a, b in zip(cpu_pressures, cpu_pressures[1:])]
        pressure_wave = statistics.fmean(deltas)

    return {
        "stability_mean": round(statistics.fmean(stabilities), 4),
        "stability_min": round(min(stabilities), 4),
        "throughput_mean": round(statistics.fmean(throughputs), 4),
        "pressure_wave": round(pressure_wave, 4),
        "risk_peak": risk_peak,
    }


def derive_learned_profile(campaigns: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not campaigns:
        return None

    summaries = [campaign["summary"] for campaign in campaigns if campaign.get("summary")]
    if not summaries:
        return None

    stability_mean = statistics.fmean(float(item["stability_mean"]) for item in summaries)
    throughput_mean = statistics.fmean(float(item["throughput_mean"]) for item in summaries)
    pressure_wave = statistics.fmean(float(item["pressure_wave"]) for item in summaries)
    risk_peak = max((str(item["risk_peak"]) for item in summaries), key=_risk_score)

    mode = "safe-adaptive"
    if stability_mean >= 0.52 and pressure_wave <= 0.08 and risk_peak == "low":
        mode = "calibrated-balanced"
    elif stability_mean >= 0.42 and pressure_wave <= 0.12 and _risk_score(risk_peak) <= 1:
        mode = "calibrated-safe"

    thermal_penalty = 0.82
    if mode == "calibrated-balanced":
        thermal_penalty = 0.88
    elif mode == "calibrated-safe":
        thermal_penalty = 0.85

    resource_boost = _clamp(0.90 + throughput_mean * 0.22, 0.90, 1.12)
    hot_boost = _clamp(1.00 + stability_mean * 0.18, 1.00, 1.10)
    warm_boost = _clamp(1.00 + throughput_mean * 0.24, 1.00, 1.16)
    baseline_limit = round(10.0 * resource_boost, 2)
    baseline_top_k = max(3, min(10, int(round(3 + throughput_mean * 6))))

    return {
        "mode": mode,
        "evidence": {
            "campaigns": len(campaigns),
            "stability_mean": round(stability_mean, 4),
            "throughput_mean": round(throughput_mean, 4),
            "pressure_wave_mean": round(pressure_wave, 4),
            "risk_peak": risk_peak,
        },
        "performance_governor": {
            "mode": mode,
            "thermal_unknown_penalty": thermal_penalty,
        },
        "planner": {
            "baseline_resource_limit": baseline_limit,
            "baseline_top_k": baseline_top_k,
        },
        "omega_ram": {
            "baseline_hot_budget_bytes": int(262144 * hot_boost),
            "baseline_warm_budget_bytes": int(1048576 * warm_boost),
        },
    }


def _cpu_burst(workers: int, batch_size: int) -> int:
    total = 0
    for worker_id in range(workers):
        seed = f"fractalos:{worker_id}:{batch_size}".encode("utf-8")
        payload = seed
        rounds = max(64, batch_size)
        for _ in range(rounds):
            payload = hashlib.sha256(payload).digest()
            total ^= payload[0]
    return total


def run_safe_benchmark(workspace: Path, duration_s: float = 6.0) -> dict[str, Any]:
    governor = PerformanceGovernor(workspace)
    started_at = time.perf_counter()
    samples: list[dict[str, Any]] = []
    loops = 0
    work_checksum = 0
    previous_recommendations: dict[str, Any] | None = None
    stop_reason = "duration reached"

    while time.perf_counter() - started_at < max(duration_s, 1.0):
        report = governor.report()
        samples.append(report)
        policy = build_benchmark_policy(report, previous_recommendations)
        previous_recommendations = report["recommendations"]

        if policy.should_stop:
            stop_reason = policy.reason
            break

        work_checksum ^= _cpu_burst(policy.workers, policy.batch_size)
        loops += 1
        time.sleep(policy.pause_ms / 1000.0)

    ended_at = time.perf_counter()
    summary = summarize_history(samples)
    final_report = samples[-1] if samples else governor.report()
    result = {
        "duration_s": round(ended_at - started_at, 3),
        "iterations": loops,
        "stop_reason": stop_reason,
        "checksum": work_checksum,
        "summary": summary,
        "final_report": final_report,
    }
    perf_state = load_perf_state(workspace)
    campaigns = perf_state.get("campaigns", []) + [result]
    perf_state["campaigns"] = campaigns[-16:]
    perf_state["learned_profile"] = derive_learned_profile(perf_state["campaigns"])
    save_perf_state(workspace, perf_state)
    result["learned_profile"] = perf_state["learned_profile"]
    return result


def calibration_report(workspace: Path) -> dict[str, Any]:
    perf_state = load_perf_state(workspace)
    campaigns = perf_state.get("campaigns", [])
    learned = perf_state.get("learned_profile") or derive_learned_profile(campaigns)
    return {
        "campaign_count": len(campaigns),
        "recent_campaigns": campaigns[-3:],
        "learned_profile": learned,
    }
