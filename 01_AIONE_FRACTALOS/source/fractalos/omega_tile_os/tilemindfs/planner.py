from __future__ import annotations

import json
import math
from pathlib import Path

from ..core.hetero_scheduler import assign_jobs
from ..core.perf_governor import PerformanceGovernor
from ..core.state import load_config


def bounded_coherence(p_world: list[float], p_model: list[float]) -> float:
    epsilon = 1e-9
    total = 0.0
    for pw, pm in zip(p_world, p_model):
        a = max(float(pw), epsilon)
        b = max(float(pm), epsilon)
        total += a * math.log(a / b)
    coherence = math.exp(-total)
    return max(min(coherence, 1.0), epsilon)


def score_job(job: dict, config: dict) -> dict:
    weights = config["weights"]
    omega = bounded_coherence(job.get("p_world", [1.0]), job.get("p_model", [1.0]))
    score = (
        float(job.get("delta_p", 0.0))
        - weights["lambda"] * float(job.get("delta_e", 0.0))
        - weights["mu"] * float(job.get("complexity", 0.0))
        - weights["rho"] * float(job.get("risk", 0.0))
        + weights["eta"] * omega
    )
    enriched = dict(job)
    enriched["omega"] = omega
    enriched["score"] = score
    return enriched


def plan_jobs(workspace: Path, jobs: list[dict], resource_limit: float | None = None, top_k: int | None = None) -> dict:
    config = load_config(workspace)
    planner_cfg = config["planner"]
    governor = PerformanceGovernor(workspace)
    perf_report = governor.report()
    recommended = perf_report["recommendations"]
    limit = float(
        resource_limit
        if resource_limit is not None
        else recommended.get("recommended_resource_limit", planner_cfg["default_resource_limit"])
    )
    chosen_k = int(
        top_k if top_k is not None else recommended.get("recommended_planner_top_k", planner_cfg["default_top_k"])
    )

    ranked = sorted((score_job(job, config) for job in jobs), key=lambda item: item["score"], reverse=True)

    selected = []
    total_resource = 0.0
    for item in ranked:
        need = float(item.get("resource_estimate", 0.0))
        if len(selected) >= chosen_k:
            break
        if total_resource + need > limit:
            continue
        selected.append(item)
        total_resource += need

    return {
        "resource_limit": limit,
        "top_k": chosen_k,
        "selected": selected,
        "rejected": [item for item in ranked if item not in selected],
        "total_resource": total_resource,
        "performance_governor": {
            "mode": perf_report["mode"],
            "recommendations": recommended,
            "formulas": perf_report["formulas"],
        },
        "scheduler": assign_jobs(workspace, selected),
    }


def load_jobs_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("jobs", []))
