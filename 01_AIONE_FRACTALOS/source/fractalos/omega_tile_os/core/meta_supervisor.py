from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .autonomy_runtime import WORKLOAD_DOMAINS, autonomy_report, submit_workload
from .codex_worker import WORKER_MODES, submit_worker_session, worker_report
from .events import append_event
from .formula_programs import formula_runtime_advice
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import utc_now
from ..tilemindfs.store import TileMindFS


LANE_TO_MODE = {
    "code": "builder",
    "research": "researcher",
    "automation": "automator",
    "ecosystem": "evolver",
}

LANE_OBJECTIVES = {
    "code": "Implementer une amelioration modulaire avec tests, rollback et trace de decision.",
    "research": "Explorer une hypothese utile, produire evidence locale et prochaine experience.",
    "automation": "Transformer une action repetitive en pipeline observable, idempotent et protege.",
    "ecosystem": "Relier les sorties des agents, reduire la dette et amplifier les boucles stables.",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _risk_weight(risk: str) -> float:
    return {
        "low": 1.0,
        "nominal": 0.86,
        "elevated": 0.46,
        "critical": 0.12,
    }.get(risk, 0.3)


def _lane_balance_scores(domain_counts: dict[str, int]) -> dict[str, float]:
    if not domain_counts:
        return {domain: 1.0 for domain in WORKLOAD_DOMAINS}
    peak = max(max(domain_counts.values()), 1)
    return {domain: round(1.0 - (domain_counts.get(domain, 0) / (peak + 1)), 4) for domain in WORKLOAD_DOMAINS}


def _agent_plan(lane: str, score: float, reason: str) -> dict[str, Any]:
    return {
        "lane": lane,
        "mode": LANE_TO_MODE.get(lane, "builder"),
        "title": f"MetaSupervisor Expansion :: {lane.title()}",
        "objective": LANE_OBJECTIVES.get(lane, LANE_OBJECTIVES["code"]),
        "reason": reason,
        "score": round(score, 4),
        "checks": ["doctor", "router-simulate", "targeted-tests", "memory-report"],
    }


def supervisor_plan(workspace: Path, max_lanes: int = 4) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    risk = str(perf["recommendations"].get("risk_level", "unknown"))
    stability = float(perf["formulas"].get("stability_index", 0.0))
    queued_autonomy = int(autonomy["status_counts"].get("queued", 0))
    queued_workers = int(worker["status_counts"].get("queued", 0))
    domain_counts = {domain: int(autonomy.get("domain_counts", {}).get(domain, 0)) for domain in WORKLOAD_DOMAINS}
    balance = _lane_balance_scores(domain_counts)
    advice = formula_runtime_advice(
        workspace,
        perf_report=perf,
        router_signals={"queued_autonomy": queued_autonomy, "queued_workers": queued_workers},
    )
    formula_push = _clamp(float(advice.get("action_biases", {}).get("autonomy-run", 0.0)) + float(advice.get("action_biases", {}).get("worker-run", 0.0)))
    queue_pressure = _clamp((queued_autonomy + queued_workers) / 24.0)
    risk_budget = _risk_weight(risk)
    clean_growth_index = round(_clamp(0.38 * stability + 0.32 * risk_budget + 0.2 * (1.0 - queue_pressure) + 0.1 * formula_push), 4)
    max_new_agents = 0
    if clean_growth_index >= 0.62:
        max_new_agents = min(max_lanes, 3)
    elif clean_growth_index >= 0.42:
        max_new_agents = 1

    candidates: list[dict[str, Any]] = []
    for lane in WORKLOAD_DOMAINS:
        lane_score = (
            0.42 * balance[lane]
            + 0.22 * risk_budget
            + 0.2 * stability
            + 0.16 * (1.0 - queue_pressure)
        )
        reason = (
            f"balance={balance[lane]:.3f}, risk_budget={risk_budget:.3f}, "
            f"stability={stability:.3f}, queue_pressure={queue_pressure:.3f}"
        )
        candidates.append(_agent_plan(lane, lane_score, reason))
    candidates.sort(key=lambda item: float(item["score"]), reverse=True)
    selected = candidates[:max_new_agents]
    mode = "expand" if selected else "stabilize"
    if risk == "critical":
        mode = "protect"
        selected = []

    codex_delta = {
        "strategy": "multi-agent supervisor with clean-growth budgeting",
        "advantages": [
            "separe les roles planner/builder/automator/evolver au lieu d'un seul flux lineaire",
            "bloque l'expansion quand la queue ou le risque monte trop",
            "archive chaque decision dans TileMindFS et OmegaRAM",
            "utilise les formules runtime comme biais de stabilite",
        ],
        "limits": [
            "n'execute pas de patch destructif automatiquement",
            "reste depend du runtime local et des tests disponibles",
        ],
    }

    return {
        "generated_at": utc_now(),
        "mode": mode,
        "clean_growth_index": clean_growth_index,
        "risk_level": risk,
        "stability_index": stability,
        "queue_pressure": round(queue_pressure, 4),
        "domain_counts": domain_counts,
        "lane_balance": balance,
        "max_new_agents": max_new_agents,
        "selected_agents": selected,
        "candidate_agents": candidates,
        "formula_advice": {
            "program_count": advice.get("program_count", 0),
            "action_biases": advice.get("action_biases", {}),
            "protective_program_count": advice.get("protective_program_count", 0),
        },
        "codex_delta": codex_delta,
    }


def supervisor_run(workspace: Path, max_lanes: int = 4, queue: bool = True) -> dict[str, Any]:
    plan = supervisor_plan(workspace, max_lanes=max_lanes)
    report_path = _write_supervisor_report(workspace, plan)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"meta_supervisor::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="meta_supervisor",
    )
    queued_workers: list[dict[str, Any]] = []
    queued_workloads: list[dict[str, Any]] = []
    if queue and plan["mode"] == "expand":
        for item in plan.get("selected_agents", []):
            mode = str(item.get("mode", "builder"))
            if mode not in WORKER_MODES:
                mode = "builder"
            queued_workers.append(
                submit_worker_session(
                    workspace,
                    mode,
                    str(item["title"]),
                    str(item["objective"]),
                    scope=f"MetaSupervisor score={item['score']} checks={', '.join(item.get('checks', []))}",
                )
            )
            queued_workloads.append(
                submit_workload(
                    workspace,
                    str(item["lane"]),
                    str(item["title"]),
                    str(item["objective"]),
                    context=f"MetaSupervisor clean_growth_index={plan['clean_growth_index']} reason={item['reason']}",
                )
            )
    append_event(
        workspace,
        "meta_supervisor_run",
        {
            "mode": plan["mode"],
            "clean_growth_index": plan["clean_growth_index"],
            "queued_workers": len(queued_workers),
            "queued_workloads": len(queued_workloads),
            "report_path": str(report_path),
        },
    )
    return {
        "plan": plan,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
        "queued_workers": queued_workers,
        "queued_workloads": queued_workloads,
    }


def supervisor_report(workspace: Path) -> dict[str, Any]:
    root = workspace / "meta_supervisor"
    reports = sorted(root.glob("SUPERVISOR_*.md")) if root.exists() else []
    latest = reports[-1] if reports else None
    plan = supervisor_plan(workspace, max_lanes=4)
    return {
        "report_count": len(reports),
        "latest_report": str(latest) if latest else None,
        "current_mode": plan["mode"],
        "clean_growth_index": plan["clean_growth_index"],
        "risk_level": plan["risk_level"],
        "selected_count": len(plan["selected_agents"]),
    }


def _write_supervisor_report(workspace: Path, plan: dict[str, Any]) -> Path:
    root = workspace / "meta_supervisor"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"SUPERVISOR_{len(list(root.glob('SUPERVISOR_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS MetaSupervisor",
        "",
        f"- Generated at: {plan['generated_at']}",
        f"- Mode: {plan['mode']}",
        f"- Clean growth index: {plan['clean_growth_index']}",
        f"- Risk level: {plan['risk_level']}",
        f"- Stability: {plan['stability_index']}",
        f"- Queue pressure: {plan['queue_pressure']}",
        "",
        "## Selected Agents",
    ]
    if not plan.get("selected_agents"):
        lines.append("- none")
    for item in plan.get("selected_agents", []):
        lines.append(f"- {item['lane']}::{item['mode']} score={item['score']} :: {item['title']}")
        lines.append(f"  Objective: {item['objective']}")
        lines.append(f"  Reason: {item['reason']}")
    lines.extend(["", "## Candidate Agents"])
    for item in plan.get("candidate_agents", []):
        lines.append(f"- {item['lane']} score={item['score']} :: {item['reason']}")
    lines.extend(["", "## Codex Delta"])
    for item in plan.get("codex_delta", {}).get("advantages", []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
