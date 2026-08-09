from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from .hetero_scheduler import assign_jobs
from .perf_governor import PerformanceGovernor


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _lane_capacity(device: dict[str, Any], recommendations: dict[str, Any]) -> int:
    if device["kind"] == "cpu":
        return max(1, min(int(device.get("recommended_concurrency", 1)), int(recommendations["recommended_concurrency"])))
    return max(1, int(round(1 + 2 * float(device["capacity"]))))


def _predicted_job_impact(job: dict[str, Any], device: dict[str, Any], formulas: dict[str, Any]) -> dict[str, float]:
    resource = float(job.get("resource_estimate", 1.0))
    complexity = float(job.get("complexity", 0.5))
    risk = float(job.get("risk", 0.2))
    scheduler_score = float(job.get("scheduler_score", 0.0))

    base_pressure = 0.05 + 0.08 * resource + 0.04 * complexity + 0.06 * risk
    capacity_relief = 0.05 + 0.08 * float(device["capacity"]) + 0.03 * max(scheduler_score, 0.0)

    if device["kind"] == "gpu":
        cpu_delta = base_pressure * 0.18
        gpu_delta = max(0.01, base_pressure - capacity_relief * 0.35)
    else:
        cpu_delta = max(0.01, base_pressure - capacity_relief * 0.25)
        gpu_delta = base_pressure * 0.05

    stability_drop = 0.06 * resource + 0.05 * risk + 0.03 * complexity - 0.04 * float(device["capacity"])
    throughput_gain = 0.08 + 0.06 * float(device["capacity"]) + 0.04 * max(scheduler_score, 0.0)

    return {
        "cpu_pressure_delta": round(_clamp(cpu_delta, 0.0, 0.95), 4),
        "gpu_pressure_delta": round(_clamp(gpu_delta, 0.0, 0.95), 4),
        "stability_drop": round(_clamp(stability_drop, 0.0, 0.85), 4),
        "throughput_gain": round(_clamp(throughput_gain, 0.0, 0.95), 4),
        "baseline_stability": round(float(formulas["stability_index"]), 4),
    }


def _dependencies_satisfied(job: dict[str, Any], completed: set[str]) -> bool:
    deps = [str(dep) for dep in job.get("depends_on", [])]
    return all(dep in completed for dep in deps)


def orchestrate_jobs(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    placement = assign_jobs(workspace, jobs)
    scheduler = placement["scheduler"]
    formulas = scheduler["formulas"]
    recommendations = scheduler.get("recommendations") or PerformanceGovernor(workspace).report()["recommendations"]
    device_map = {device["id"]: device for device in scheduler["devices"]}

    lanes = {
        device["id"]: {
            "device": device,
            "capacity": _lane_capacity(device, recommendations),
            "queue": [],
        }
        for device in scheduler["devices"]
    }

    for item in placement["placements"]:
        lanes[item["target_device"]]["queue"].append(item)

    waves: list[dict[str, Any]] = []
    pending = {lane_id: list(data["queue"]) for lane_id, data in lanes.items()}
    completed_jobs: set[str] = set()
    deferred_dependency_cycles = 0
    wave_index = 0
    while any(pending.values()):
        wave_jobs = []
        predicted_cpu_pressure = float(formulas["cpu_pressure"])
        predicted_gpu_pressure = float(formulas["gpu_pressure"])
        predicted_stability = float(formulas["stability_index"])
        deferred: list[tuple[str, dict[str, Any]]] = []
        dependency_blocked: list[tuple[str, dict[str, Any]]] = []

        for lane_id, lane in lanes.items():
            capacity = lane["capacity"]
            device = lane["device"]
            for _ in range(capacity):
                if not pending[lane_id]:
                    break
                item = pending[lane_id].pop(0)
                if not _dependencies_satisfied(item, completed_jobs):
                    dependency_blocked.append((lane_id, item))
                    continue
                impact = _predicted_job_impact(item, device, formulas)
                next_cpu_pressure = _clamp(predicted_cpu_pressure + impact["cpu_pressure_delta"], 0.0, 1.0)
                next_gpu_pressure = _clamp(predicted_gpu_pressure + impact["gpu_pressure_delta"], 0.0, 1.0)
                next_stability = _clamp(predicted_stability - impact["stability_drop"], 0.0, 1.0)
                if wave_jobs and (
                    next_stability < 0.18
                    or next_cpu_pressure > 0.78
                    or next_gpu_pressure > 0.74
                ):
                    deferred.append((lane_id, item))
                    continue
                predicted_cpu_pressure = next_cpu_pressure
                predicted_gpu_pressure = next_gpu_pressure
                predicted_stability = next_stability
                wave_jobs.append(
                    {
                        **item,
                        "impact": impact,
                    }
                )

        wave_index += 1
        for lane_id, item in reversed(dependency_blocked):
            pending[lane_id].insert(0, item)
        for lane_id, item in reversed(deferred):
            pending[lane_id].insert(0, item)
        if not wave_jobs:
            deferred_dependency_cycles += 1
            if deferred_dependency_cycles > len(jobs) + 2:
                break
            continue
        deferred_dependency_cycles = 0
        completed_jobs.update(str(item.get("job_id", "")) for item in wave_jobs)

        waves.append(
            {
                "wave_id": f"wave-{wave_index:03d}",
                "jobs": wave_jobs,
                "predicted_state": {
                    "cpu_pressure": round(predicted_cpu_pressure, 4),
                    "gpu_pressure": round(predicted_gpu_pressure, 4),
                    "stability_index": round(predicted_stability, 4),
                },
            }
        )

    return {
        "scheduler": scheduler,
        "placements": placement["placements"],
        "waves": waves,
        "completed_projection": sorted(completed_jobs),
    }


def _execute_cpu_job(job: dict[str, Any]) -> dict[str, Any]:
    rounds = max(200, int(1600 * float(job.get("resource_estimate", 1.0)) + 900 * float(job.get("complexity", 0.4))))
    payload = job.get("job_id", "job").encode("utf-8")
    started = time.perf_counter()
    for _ in range(rounds):
        payload = hashlib.sha256(payload).digest()
    elapsed = time.perf_counter() - started
    return {
        "job_id": job.get("job_id", "job"),
        "target_device": job["target_device"],
        "mode": "cpu-executed",
        "checksum": payload.hex()[:16],
        "elapsed_ms": round(elapsed * 1000.0, 3),
    }


def _execute_gpu_job(job: dict[str, Any]) -> dict[str, Any]:
    # Current runtime validates placement and reserves the lane, but does not
    # claim native CUDA execution inside this Python-only control plane.
    synthetic_batches = max(1, int(round(3 * float(job.get("resource_estimate", 1.0)))))
    latency_ms = round(10.0 + synthetic_batches * 4.5 + 8.0 * float(job.get("risk", 0.1)), 3)
    return {
        "job_id": job.get("job_id", "job"),
        "target_device": job["target_device"],
        "mode": "gpu-routed-staged",
        "batches": synthetic_batches,
        "elapsed_ms": latency_ms,
    }


def execute_wave_jobs(wave_jobs: list[dict[str, Any]], completed_jobs: set[str]) -> dict[str, Any]:
    results = []
    stop_reason = "completed"
    updated_completed = set(completed_jobs)

    for job in wave_jobs:
        if not _dependencies_satisfied(job, updated_completed):
            stop_reason = f"stopped because dependencies were not satisfied for {job['job_id']}"
            break
        if job["target_kind"] == "cpu":
            results.append(_execute_cpu_job(job))
        else:
            results.append(_execute_gpu_job(job))
        updated_completed.add(str(job.get("job_id", "")))

    return {
        "results": results,
        "completed_jobs": updated_completed,
        "stop_reason": stop_reason,
    }


def execute_future_plan(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    orchestration = orchestrate_jobs(workspace, jobs)
    governor = PerformanceGovernor(workspace)
    report = governor.report()
    executed_waves = []
    stop_reason = "completed"
    completed_jobs: set[str] = set()
    mission_snapshots = []

    for wave in orchestration["waves"]:
        predicted = wave["predicted_state"]
        if predicted["stability_index"] < 0.16:
            stop_reason = f"stopped before {wave['wave_id']} due to low predicted stability"
            break

        wave_execution = execute_wave_jobs(wave["jobs"], completed_jobs)
        results = wave_execution["results"]
        completed_jobs = wave_execution["completed_jobs"]
        if wave_execution["stop_reason"] != "completed":
            stop_reason = f"stopped in {wave['wave_id']}: {wave_execution['stop_reason']}"
            break

        executed_waves.append(
            {
                "wave_id": wave["wave_id"],
                "predicted_state": predicted,
                "results": results,
            }
        )
        mission_snapshots.append(
            {
                "wave_id": wave["wave_id"],
                "completed_jobs": sorted(completed_jobs),
                "predicted_state": predicted,
            }
        )

    return {
        "mode": report["mode"],
        "learned_profile": report.get("learned_profile"),
        "executed_waves": executed_waves,
        "mission_snapshots": mission_snapshots,
        "stop_reason": stop_reason,
        "orchestration": orchestration,
    }
