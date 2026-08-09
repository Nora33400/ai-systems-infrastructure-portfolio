from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .agents import architect_output, builder_output, planner_output, slugify
from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import load_state, save_state
from ..tilemindfs.store import TileMindFS


def submit_intent(workspace: Path, title: str, intent: str) -> dict:
    state = load_state(workspace)
    item = {
        "id": uuid4().hex[:12],
        "title": title.strip() or "Untitled intent",
        "intent": intent.strip(),
        "status": "queued",
    }
    state["intents"].append(item)
    state["memory"]["recent_focus"] = item["intent"]
    state["memory"]["last_intent_title"] = item["title"]
    save_state(workspace, state)
    append_event(workspace, "intent_submitted", {"id": item["id"], "title": item["title"]})
    return item


def _write_artifacts(workspace: Path, title: str, intent: str) -> list[str]:
    root = workspace / "artifacts" / slugify(title)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "PLAN.md": planner_output(title, intent),
        "ARCHITECTURE.md": architect_output(title, intent),
        "TASKS.md": builder_output(title, intent),
    }
    created: list[str] = []
    for name, content in outputs.items():
        target = root / name
        target.write_text(content, encoding="utf-8")
        created.append(str(target))
    return created


def tick(workspace: Path) -> dict:
    state = load_state(workspace)
    perf_result = PerformanceGovernor(workspace).apply()
    state["metrics"]["ticks"] += 1
    queued = next((item for item in state["intents"] if item["status"] == "queued"), None)
    if queued is None:
        state["node"]["status"] = "idle"
        for agent in state["agents"]:
            agent["status"] = "idle"
            agent["last_output"] = ""
        save_state(workspace, state)
        append_event(
            workspace,
            "tick_idle",
            {
                "ticks": state["metrics"]["ticks"],
                "recommended_concurrency": perf_result["recommendations"]["recommended_concurrency"],
                "risk_level": perf_result["recommendations"]["risk_level"],
            },
        )
        return {
            "status": "idle",
            "message": "No queued intents.",
            "performance": perf_result,
        }

    state["node"]["status"] = "processing"
    queued["status"] = "processing"
    for agent in state["agents"]:
        agent["status"] = "running"
        agent["last_output"] = f"Working on {queued['title']}"
    save_state(workspace, state)
    append_event(workspace, "intent_processing", {"id": queued["id"], "title": queued["title"]})

    created_files = _write_artifacts(workspace, queued["title"], queued["intent"])

    tilefs = TileMindFS(workspace)
    archived = []
    omega_ram = OmegaRAM(workspace)
    for file_path in created_files:
        archived.append(tilefs.store_file(Path(file_path)))
        omega_ram.put_file(
            key=f"artifact::{queued['id']}::{Path(file_path).name}",
            path=Path(file_path),
            source=f"intent:{queued['title']}",
        )

    state = load_state(workspace)
    final_item = next(item for item in state["intents"] if item["id"] == queued["id"])
    final_item["status"] = "done"
    state["node"]["status"] = "idle"
    state["metrics"]["processed_intents"] += 1
    state["artifacts"].append(
        {
            "intent_id": final_item["id"],
            "title": final_item["title"],
            "files": created_files,
            "tile_archives": archived,
        }
    )
    agent_outputs = [
        "Plan generated.",
        "Architecture generated.",
        "Build tasks generated.",
        "Artifacts archived in TileMindFS.",
    ]
    for agent, output in zip(state["agents"], agent_outputs):
        agent["status"] = "idle"
        agent["last_output"] = output
    save_state(workspace, state)
    append_event(workspace, "intent_completed", {"id": final_item["id"], "files": created_files})
    return {
        "status": "done",
        "intent_id": final_item["id"],
        "files": created_files,
        "tile_archives": archived,
        "performance": perf_result,
    }
