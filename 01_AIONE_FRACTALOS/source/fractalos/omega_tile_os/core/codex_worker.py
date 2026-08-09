from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

from .autonomy_runtime import WORKLOAD_DOMAINS, submit_workload
from .chrono_mesh import checkpoint_mission
from .events import append_event, read_events
from .mesh_federation import mesh_route_mission_dynamic
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import load_state, load_worker_state, save_worker_state, utc_now
from ..tilemindfs.store import TileMindFS


WORKER_MODES = ("builder", "researcher", "automator", "evolver")


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts[:12]) or "session"


def _worker_root(workspace: Path) -> Path:
    root = workspace / "worker"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_root(workspace: Path, session: dict) -> Path:
    root = _worker_root(workspace) / f"{session['id']}_{_slugify(str(session['title']))}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_domain_for_mode(mode: str) -> str:
    return {
        "builder": "code",
        "researcher": "research",
        "automator": "automation",
        "evolver": "ecosystem",
    }.get(mode, "code")


def submit_worker_session(workspace: Path, mode: str, title: str, objective: str, scope: str = "") -> dict[str, object]:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in WORKER_MODES:
        raise ValueError(f"Unsupported mode: {mode}")

    worker_state = load_worker_state(workspace)
    session = {
        "id": uuid4().hex[:12],
        "mode": normalized_mode,
        "title": title.strip() or f"{normalized_mode.title()} session",
        "objective": objective.strip(),
        "scope": scope.strip(),
        "status": "queued",
        "submitted_at": utc_now(),
        "domain_hint": _default_domain_for_mode(normalized_mode),
    }
    worker_state["sessions"].append(session)
    worker_state["metrics"]["submitted"] = int(worker_state["metrics"].get("submitted", 0)) + 1
    save_worker_state(workspace, worker_state)
    append_event(workspace, "worker_session_submitted", {"id": session["id"], "mode": normalized_mode, "title": session["title"]})
    return session


def _role_cards(session: dict, perf_result: dict) -> list[dict[str, object]]:
    recommendations = perf_result["recommendations"]
    base_risk = str(recommendations["risk_level"])
    return [
        {
            "role": "planner",
            "focus": "decompose objective into bounded milestones",
            "questions": [
                "What is the smallest safe first move?",
                "What evidence is required before implementation?",
                "Which parts can be delegated to the rest of FractalOS?",
            ],
            "risk_bias": base_risk,
        },
        {
            "role": "executor",
            "focus": "produce concrete artifacts and action graphs",
            "questions": [
                "Which files or domains are directly impacted?",
                "Which actions can run now with current telemetry?",
                "What should be archived for replay?",
            ],
            "risk_bias": base_risk,
        },
        {
            "role": "reviewer",
            "focus": "find regressions, gaps, and missing validation",
            "questions": [
                "What can silently fail?",
                "What test or probe is missing?",
                "Which assumptions remain unchecked?",
            ],
            "risk_bias": "conservative",
        },
        {
            "role": "reflector",
            "focus": "learn from the run and propose the next step",
            "questions": [
                "What did this session unlock?",
                "What should FractalOS queue next on its own?",
                "How should memory and mesh be updated?",
            ],
            "risk_bias": "adaptive",
        },
    ]


def _mission_graph(session: dict) -> list[dict[str, object]]:
    slug = _slugify(str(session["title"]))
    if session["mode"] == "researcher":
        return [
            {"stage": "scan", "job_id": f"{slug}-scan", "depends_on": []},
            {"stage": "evidence", "job_id": f"{slug}-evidence", "depends_on": [f"{slug}-scan"]},
            {"stage": "synthesis", "job_id": f"{slug}-synthesis", "depends_on": [f"{slug}-evidence"]},
            {"stage": "reflection", "job_id": f"{slug}-reflection", "depends_on": [f"{slug}-synthesis"]},
        ]
    if session["mode"] == "automator":
        return [
            {"stage": "trigger-map", "job_id": f"{slug}-trigger-map", "depends_on": []},
            {"stage": "workflow-design", "job_id": f"{slug}-workflow-design", "depends_on": [f"{slug}-trigger-map"]},
            {"stage": "safeguards", "job_id": f"{slug}-safeguards", "depends_on": [f"{slug}-workflow-design"]},
            {"stage": "reflection", "job_id": f"{slug}-reflection", "depends_on": [f"{slug}-safeguards"]},
        ]
    if session["mode"] == "evolver":
        return [
            {"stage": "observe", "job_id": f"{slug}-observe", "depends_on": []},
            {"stage": "design", "job_id": f"{slug}-design", "depends_on": [f"{slug}-observe"]},
            {"stage": "integration", "job_id": f"{slug}-integration", "depends_on": [f"{slug}-design"]},
            {"stage": "reflection", "job_id": f"{slug}-reflection", "depends_on": [f"{slug}-integration"]},
        ]
    return [
        {"stage": "frame", "job_id": f"{slug}-frame", "depends_on": []},
        {"stage": "implement", "job_id": f"{slug}-implement", "depends_on": [f"{slug}-frame"]},
        {"stage": "verify", "job_id": f"{slug}-verify", "depends_on": [f"{slug}-implement"]},
        {"stage": "reflection", "job_id": f"{slug}-reflection", "depends_on": [f"{slug}-verify"]},
    ]


def _mission_jobs_from_session(session: dict) -> list[dict[str, object]]:
    jobs = []
    for item in session.get("mission_graph", _mission_graph(session)):
        stage = str(item.get("stage", "stage"))
        resource_estimate = 0.8
        complexity = 0.35
        risk = 0.08
        if stage in {"implement", "integration", "workflow-design", "evidence"}:
            resource_estimate = 1.8
            complexity = 0.7
            risk = 0.18
        elif stage in {"verify", "reflection", "safeguards", "synthesis"}:
            resource_estimate = 0.95
            complexity = 0.42
            risk = 0.11
        jobs.append(
            {
                "job_id": str(item.get("job_id")),
                "title": f"{session['title']}::{stage}",
                "depends_on": list(item.get("depends_on", [])),
                "resource_estimate": resource_estimate,
                "complexity": complexity,
                "risk": risk,
                "latency_sensitive": stage in {"verify", "reflection"},
                "vectorizable": stage in {"implement", "integration", "evidence"},
            }
        )
    return jobs


def _build_session_outputs(workspace: Path, session: dict, perf_result: dict, worker_state: dict) -> dict[str, str]:
    state = load_state(workspace)
    recent_events = read_events(workspace, limit=12)
    event_counts = Counter(str(item.get("kind", "")) for item in recent_events)
    role_cards = _role_cards(session, perf_result)
    mission_graph = _mission_graph(session)
    recommendations = perf_result["recommendations"]
    scope = str(session.get("scope", "")).strip()

    header = (
        f"# {session['title']}\n\n"
        f"- Worker mode: {session['mode']}\n"
        f"- Session id: {session['id']}\n"
        f"- Submitted at: {session['submitted_at']}\n"
        f"- Recommended concurrency: {recommendations['recommended_concurrency']}\n"
        f"- Recommended resource limit: {recommendations['recommended_resource_limit']}\n"
        f"- Risk level: {recommendations['risk_level']}\n\n"
        f"## Objective\n{session['objective']}\n\n"
    )
    if scope:
        header += f"## Scope\n{scope}\n\n"

    brief = (
        header
        + "## Mission Framing\n"
        + f"- Node status: {state['node']['status']}\n"
        + f"- Processed intents: {state['metrics']['processed_intents']}\n"
        + f"- Worker sessions before this run: {worker_state.get('metrics', {}).get('processed', 0)}\n"
    )

    plan_lines = [header + "## Role Loop\n"]
    for role in role_cards:
        plan_lines.append(f"### {role['role'].title()}\n")
        plan_lines.append(f"- Focus: {role['focus']}\n")
        plan_lines.extend(f"- Question: {question}\n" for question in role["questions"])
        plan_lines.append(f"- Risk bias: {role['risk_bias']}\n\n")
    plan_lines.append("## Mission Graph\n")
    plan_lines.extend(
        f"- {item['stage']} -> {item['job_id']} deps={','.join(item['depends_on']) or 'none'}\n" for item in mission_graph
    )

    action_graph = {
        "session_id": session["id"],
        "mode": session["mode"],
        "domain_hint": session["domain_hint"],
        "graph": mission_graph,
        "role_cards": role_cards,
        "resource_guidance": recommendations,
    }

    review = (
        header
        + "## Review Findings\n"
        + "- Strength: bounded mission graph with explicit reflection stage.\n"
        + "- Risk: no external execution backend is invoked yet; this worker stays in safe planning mode.\n"
        + "- Gap: next iterations should bind outputs to real code-edit or research execution loops.\n\n"
        + "## Recent Event Signals\n"
        + ("\n".join(f"- {kind}: {count}" for kind, count in event_counts.items()) or "- No recent event signals.")
        + "\n"
    )

    domain_hint = session["domain_hint"]
    next_step_title = f"{domain_hint.title()} lane from worker {session['id']}"
    next_step_goal = f"Continue the objective '{session['title']}' through the {domain_hint} autonomy lane."
    reflection = (
        header
        + "## Reflection\n"
        + "This worker is modeled after a Codex-like flow: it separates framing, execution intent, review, and reflection.\n\n"
        + "## Suggested Follow-up\n"
        + f"- Domain: {domain_hint}\n"
        + f"- Title: {next_step_title}\n"
        + f"- Goal: {next_step_goal}\n"
    )

    return {
        "BRIEF.md": brief,
        "PLAN.md": "".join(plan_lines),
        "ACTION_GRAPH.json": json.dumps(action_graph, indent=2, ensure_ascii=True),
        "REVIEW.md": review,
        "REFLECTION.md": reflection,
    }


def _store_outputs(workspace: Path, session: dict, outputs: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    root = _session_root(workspace, session)
    tilefs = TileMindFS(workspace)
    ram = OmegaRAM(workspace)
    created_files: list[str] = []
    manifests: list[str] = []
    ram_keys: list[str] = []

    for name, content in outputs.items():
        target = root / name
        target.write_text(content, encoding="utf-8")
        created_files.append(str(target))
        manifests.append(str(tilefs.store_file(target).get("manifest_id", "")))
        ram_key = f"worker::{session['mode']}::{session['id']}::{name}"
        ram.put_text(key=ram_key, text=content, source=f"worker:{session['mode']}")
        ram_keys.append(ram_key)
    return created_files, manifests, ram_keys


def run_worker_sessions(workspace: Path, max_items: int = 1, auto_queue_autonomy: bool = True) -> dict[str, object]:
    worker_state = load_worker_state(workspace)
    perf_result = PerformanceGovernor(workspace).apply()
    queued = [item for item in worker_state.get("sessions", []) if item.get("status") == "queued"]
    processed: list[dict[str, object]] = []
    spawned_autonomy: list[dict[str, object]] = []

    for session in queued[: max(1, max_items)]:
        session["status"] = "running"
        session["started_at"] = utc_now()
        outputs = _build_session_outputs(workspace, session, perf_result, worker_state)
        created_files, manifests, ram_keys = _store_outputs(workspace, session, outputs)
        session["status"] = "done"
        session["completed_at"] = utc_now()
        session["files"] = created_files
        session["tile_archives"] = manifests
        session["ram_keys"] = ram_keys
        session["mission_graph"] = _mission_graph(session)
        session["reflection_score"] = round(0.55 + min(0.35, len(created_files) * 0.05), 3)

        if auto_queue_autonomy:
            followup = submit_workload(
                workspace,
                session["domain_hint"],
                f"{session['domain_hint'].title()} lane from worker {session['id']}",
                f"Continue the objective '{session['title']}' through the {session['domain_hint']} autonomy lane.",
                context=f"Spawned by worker session {session['id']}.",
            )
            session["spawned_autonomy_id"] = followup["id"]
            spawned_autonomy.append(followup)

        processed.append(
            {
                "id": session["id"],
                "mode": session["mode"],
                "title": session["title"],
                "spawned_autonomy_id": session.get("spawned_autonomy_id"),
                "files": created_files,
            }
        )
        append_event(workspace, "worker_session_completed", {"id": session["id"], "mode": session["mode"], "file_count": len(created_files)})

    worker_state["metrics"]["processed"] = int(worker_state["metrics"].get("processed", 0)) + len(processed)
    worker_state["metrics"]["reflections"] = int(worker_state["metrics"].get("reflections", 0)) + len(processed)
    save_worker_state(workspace, worker_state)
    return {
        "processed": processed,
        "spawned_autonomy": spawned_autonomy,
        "queued_remaining": len([item for item in worker_state.get("sessions", []) if item.get("status") == "queued"]),
        "performance": perf_result,
    }


def worker_report(workspace: Path) -> dict[str, object]:
    worker_state = load_worker_state(workspace)
    sessions = list(worker_state.get("sessions", []))
    status_counts = Counter(str(item.get("status", "unknown")) for item in sessions)
    mode_counts = Counter(str(item.get("mode", "unknown")) for item in sessions)
    return {
        "metrics": worker_state.get("metrics", {}),
        "status_counts": dict(status_counts),
        "mode_counts": dict(mode_counts),
        "queued": [item for item in sessions if item.get("status") == "queued"][-10:],
        "recent_done": [item for item in sessions if item.get("status") == "done"][-5:],
    }


def worker_to_mission(workspace: Path, session_id: str, route: str = "dynamic") -> dict[str, object]:
    worker_state = load_worker_state(workspace)
    session = next((item for item in worker_state.get("sessions", []) if str(item.get("id")) == session_id), None)
    if not session:
        return {"session_id": session_id, "bridged": False, "reason": "session_not_found"}
    if str(session.get("status")) != "done":
        return {"session_id": session_id, "bridged": False, "reason": "session_not_ready"}

    jobs = _mission_jobs_from_session(session)
    checkpoint = checkpoint_mission(workspace, jobs)
    if route == "dynamic":
        execution = mesh_route_mission_dynamic(workspace, jobs)
    else:
        execution = {"mode": "checkpoint-only", "checkpointed": True}
    session["mission_bridge"] = {
        "checkpoint_mission_id": checkpoint["mission_id"],
        "route": route,
        "bridged_at": utc_now(),
        "job_count": len(jobs),
    }
    save_worker_state(workspace, worker_state)
    append_event(workspace, "worker_session_bridged", {"id": session_id, "checkpoint_mission_id": checkpoint["mission_id"], "route": route})
    return {
        "session_id": session_id,
        "bridged": True,
        "jobs": jobs,
        "checkpoint": checkpoint,
        "execution": execution,
    }
