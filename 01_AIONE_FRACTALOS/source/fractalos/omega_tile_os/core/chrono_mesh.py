from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .future_fabric import execute_future_plan, orchestrate_jobs
from .perf_governor import PerformanceGovernor
from .state import load_mission_journal, save_mission_journal


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _job_id(job: dict[str, Any], index: int) -> str:
    return str(job.get("job_id") or f"job-{index:03d}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mission_id(jobs: list[dict[str, Any]]) -> str:
    payload = "|".join(sorted(str(job.get("job_id") or index) for index, job in enumerate(jobs, start=1)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compile_mission_graph(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    orchestration = orchestrate_jobs(workspace, jobs)
    report = PerformanceGovernor(workspace).report()
    recommendations = report["recommendations"]
    formulas = report["formulas"]
    learned = report.get("learned_profile") or {}

    nodes = []
    edges = []
    placements = {item["job_id"]: item for item in orchestration["placements"]}
    wave_lookup = {}
    for wave in orchestration["waves"]:
        for item in wave["jobs"]:
            wave_lookup[item["job_id"]] = wave["wave_id"]

    for index, raw_job in enumerate(jobs, start=1):
        job = dict(raw_job)
        job_name = _job_id(job, index)
        placement = placements.get(job_name, {})
        deps = [str(dep) for dep in job.get("depends_on", [])]
        criticality = _clamp(
            0.45 * float(job.get("risk", 0.2))
            + 0.30 * float(job.get("complexity", 0.4))
            + 0.25 * float(job.get("resource_estimate", 1.0)) / max(float(recommendations["recommended_resource_limit"]), 1.0),
            0.0,
            1.0,
        )
        resilience = _clamp(
            0.55 * float(formulas["stability_index"])
            + 0.25 * (1.0 - criticality)
            + 0.20 * float(formulas["memory_guard"]),
            0.0,
            1.0,
        )
        retry_budget = max(0, min(4, int(round(1 + resilience * 3 - criticality * 2))))
        recovery_mode = "checkpoint-resume"
        if placement.get("target_kind") == "cpu":
            recovery_mode = "instant-replay"
        if criticality > 0.75:
            recovery_mode = "quarantine-and-review"

        nodes.append(
            {
                "job_id": job_name,
                "title": str(job.get("title", job_name)),
                "wave_id": wave_lookup.get(job_name),
                "target_device": placement.get("target_device"),
                "target_kind": placement.get("target_kind"),
                "criticality": round(criticality, 4),
                "resilience_score": round(resilience, 4),
                "retry_budget": retry_budget,
                "recovery_mode": recovery_mode,
                "depends_on": deps,
            }
        )
        for dep in deps:
            edges.append({"from": dep, "to": job_name, "kind": "dependency"})

    mission = {
        "mode": report["mode"],
        "learned_profile": learned,
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
        "orchestration": orchestration,
        "causal_projection": {
            "completed_projection": orchestration.get("completed_projection", []),
            "wave_count": len(orchestration.get("waves", [])),
        },
        "mission_envelope": {
            "recommended_concurrency": recommendations["recommended_concurrency"],
            "recommended_resource_limit": recommendations["recommended_resource_limit"],
            "stability_index": round(float(formulas["stability_index"]), 4),
            "risk_level": recommendations["risk_level"],
        },
    }
    return mission


def simulate_mission_recovery(workspace: Path, jobs: list[dict[str, Any]], failed_jobs: list[str] | None = None) -> dict[str, Any]:
    mission = compile_mission_graph(workspace, jobs)
    execution = execute_future_plan(workspace, jobs)
    failed = set(failed_jobs or [])

    recovery_actions = []
    for node in mission["graph"]["nodes"]:
        if node["job_id"] not in failed:
            continue
        blocked = [edge["to"] for edge in mission["graph"]["edges"] if edge["from"] == node["job_id"]]
        recovery_actions.append(
            {
                "job_id": node["job_id"],
                "recovery_mode": node["recovery_mode"],
                "retry_budget": node["retry_budget"],
                "blocked_descendants": blocked,
                "recommended_action": (
                    "resume-now"
                    if node["recovery_mode"] == "instant-replay"
                    else "checkpoint-and-reroute"
                    if node["recovery_mode"] == "checkpoint-resume"
                    else "manual-review"
                ),
            }
        )

    return {
        "mission": mission,
        "execution": execution,
        "failed_jobs": sorted(failed),
        "recovery_actions": recovery_actions,
    }


def checkpoint_mission(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    mission = compile_mission_graph(workspace, jobs)
    execution = execute_future_plan(workspace, jobs)
    mission_state = load_mission_journal(workspace)
    mission_id = _mission_id(jobs)
    completed_jobs = execution.get("mission_snapshots", [])[-1]["completed_jobs"] if execution.get("mission_snapshots") else []

    snapshot = {
        "mission_id": mission_id,
        "ts": _utc_now(),
        "completed_jobs": completed_jobs,
        "stop_reason": execution["stop_reason"],
        "wave_count": len(execution.get("executed_waves", [])),
        "job_ids": [node["job_id"] for node in mission["graph"]["nodes"]],
    }
    mission_state["missions"][mission_id] = {
        "last_snapshot": snapshot,
        "mission": mission,
        "execution": execution,
    }
    mission_state["events"] = (mission_state.get("events", []) + [{"kind": "mission_checkpointed", **snapshot}])[-100:]
    latest = load_mission_journal(workspace)
    latest["missions"].update(mission_state.get("missions", {}))
    latest["events"] = (latest.get("events", []) + [mission_state["events"][-1]])[-100:]
    save_mission_journal(workspace, latest)
    return {
        "mission_id": mission_id,
        "snapshot": snapshot,
    }


def replay_mission(workspace: Path, jobs: list[dict[str, Any]], from_job: str | None = None) -> dict[str, Any]:
    mission_id = _mission_id(jobs)
    mission_state = load_mission_journal(workspace)
    stored = mission_state.get("missions", {}).get(mission_id)
    mission = compile_mission_graph(workspace, jobs)

    completed = set()
    if stored:
        completed.update(stored.get("last_snapshot", {}).get("completed_jobs", []))
    if from_job:
        nodes = [node["job_id"] for node in mission["graph"]["nodes"]]
        if from_job in nodes:
            cutoff = nodes.index(from_job)
            completed = set(nodes[:cutoff])

    replayable_jobs = [job for job in jobs if str(job.get("job_id")) not in completed]
    execution = execute_future_plan(workspace, replayable_jobs)
    replay_record = {
        "mission_id": mission_id,
        "ts": _utc_now(),
        "from_job": from_job,
        "already_completed": sorted(completed),
        "replayed_jobs": [str(job.get("job_id")) for job in replayable_jobs],
        "stop_reason": execution["stop_reason"],
    }
    latest = load_mission_journal(workspace)
    latest["missions"].update(mission_state.get("missions", {}))
    latest["events"] = (latest.get("events", []) + [{"kind": "mission_replayed", **replay_record}])[-100:]
    save_mission_journal(workspace, latest)
    return {
        "mission_id": mission_id,
        "replay": replay_record,
        "execution": execution,
    }


def mission_journal_report(workspace: Path) -> dict[str, Any]:
    mission_state = load_mission_journal(workspace)
    return {
        "mission_count": len(mission_state.get("missions", {})),
        "missions": list(mission_state.get("missions", {}).keys())[-10:],
        "recent_events": mission_state.get("events", [])[-10:],
    }
