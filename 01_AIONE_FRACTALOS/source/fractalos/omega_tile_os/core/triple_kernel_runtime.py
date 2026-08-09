from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from .triple_kernel_innovation import TRIPLE_KERNEL_CATALOG, triple_kernel_plan
from ..tilemindfs.store import TileMindFS


VERTEX_LABELS = {
    "matter": "Matter Kernel",
    "mind": "Mind Kernel",
    "mesh": "Mesh Kernel",
}


def _runtime_state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "triple_kernel_runtime.json"


def _default_state() -> dict[str, Any]:
    return {
        "builds": [],
        "metrics": {
            "syntheses": 0,
            "queued_followups": 0,
        },
        "last_build": None,
    }


def _load_runtime_state(workspace: Path) -> dict[str, Any]:
    path = _runtime_state_path(workspace)
    if not path.exists():
        state = _default_state()
        path.write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")
        return state
    return json.loads(path.read_text(encoding="utf-8"))


def _save_runtime_state(workspace: Path, state: dict[str, Any]) -> None:
    _runtime_state_path(workspace).write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def _bridge_matrix(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vertex_counts = {
        "matter": len([item for item in selected if item["vertex"] == "matter"]),
        "mind": len([item for item in selected if item["vertex"] == "mind"]),
        "mesh": len([item for item in selected if item["vertex"] == "mesh"]),
    }
    pairs = [("matter", "mind"), ("mind", "mesh"), ("mesh", "matter")]
    bridges: list[dict[str, Any]] = []
    for left, right in pairs:
        strength = min(1.0, 0.22 + 0.11 * vertex_counts[left] + 0.11 * vertex_counts[right])
        bridges.append(
            {
                "id": f"{left}-{right}",
                "from": left,
                "to": right,
                "strength": round(strength, 4),
                "purpose": f"Synchronize {VERTEX_LABELS[left]} with {VERTEX_LABELS[right]}.",
            }
        )
    return bridges


def _implemented_primitives(selected: list[dict[str, Any]], perf: dict[str, Any]) -> list[dict[str, Any]]:
    stability = float(perf["formulas"].get("stability_index", 0.5))
    primitives: list[dict[str, Any]] = []
    for item in selected[:12]:
        primitive_kind = "guard" if item["domain"] in {"safety", "security", "proof"} else "engine" if item["vertex"] == "matter" else "agent" if item["vertex"] == "mind" else "fabric"
        deployment = "kernel" if item["vertex"] == "matter" else "control-plane"
        readiness = min(1.0, 0.45 + 0.35 * float(item["priority_score"]) + 0.15 * stability)
        primitives.append(
            {
                "id": f"primitive::{item['id']}",
                "source_id": item["id"],
                "title": item["title"],
                "kind": primitive_kind,
                "deployment": deployment,
                "readiness": round(readiness, 4),
                "summary": f"{primitive_kind} derived from {item['domain_label']} on the {item['vertex_label']}.",
            }
        )
    return primitives


def _vertex_profiles(selected: list[dict[str, Any]], perf: dict[str, Any]) -> list[dict[str, Any]]:
    stability = float(perf["formulas"].get("stability_index", 0.5))
    profiles: list[dict[str, Any]] = []
    for vertex in ("matter", "mind", "mesh"):
        bucket = [item for item in selected if item["vertex"] == vertex]
        mean_priority = sum(float(item["priority_score"]) for item in bucket) / max(1, len(bucket))
        profiles.append(
            {
                "id": vertex,
                "label": VERTEX_LABELS[vertex],
                "selected": len(bucket),
                "mean_priority": round(mean_priority, 4),
                "stability_bias": round(min(1.0, 0.4 * stability + 0.6 * mean_priority), 4),
                "top_domains": sorted({item["domain"] for item in bucket})[:5],
            }
        )
    return profiles


def triple_kernel_status(workspace: Path) -> dict[str, Any]:
    state = _load_runtime_state(workspace)
    catalog_total = len(TRIPLE_KERNEL_CATALOG)
    return {
        "generated_at": utc_now(),
        "catalog_total": catalog_total,
        "runtime": {
            "version": "0.3.0",
            "triangle_mode": "matter-mind-mesh",
            "last_build": state.get("last_build"),
        },
        "metrics": state.get("metrics", {}),
        "build_count": len(state.get("builds", [])),
        "recent_builds": state.get("builds", [])[-3:],
    }


def triple_kernel_synthesize(workspace: Path, limit: int = 18, queue: bool = False) -> dict[str, Any]:
    ensure_workspace(workspace)
    perf = PerformanceGovernor(workspace).report()
    plan = triple_kernel_plan(workspace, limit=limit, queue=queue)
    selected = [dict(item) for item in plan["selected"]]
    profiles = _vertex_profiles(selected, perf)
    bridges = _bridge_matrix(selected)
    primitives = _implemented_primitives(selected, perf)
    report_path = _write_synthesis_report(workspace, selected, profiles, bridges, primitives)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"triple_kernel_runtime::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="triple_kernel_runtime",
    )

    state = _load_runtime_state(workspace)
    build_id = f"tk-build-{len(state['builds']) + 1:04d}"
    build = {
        "id": build_id,
        "ts": utc_now(),
        "selected_count": len(selected),
        "primitive_count": len(primitives),
        "bridge_count": len(bridges),
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }
    state.setdefault("builds", []).append(build)
    state["builds"] = state["builds"][-24:]
    state.setdefault("metrics", {})["syntheses"] = int(state.setdefault("metrics", {}).get("syntheses", 0)) + 1
    state["metrics"]["queued_followups"] = int(state["metrics"].get("queued_followups", 0)) + len(plan.get("queued_workers", []))
    state["last_build"] = build
    _save_runtime_state(workspace, state)
    append_event(workspace, "triple_kernel_synthesized", {"build_id": build_id, "selected": len(selected), "primitives": len(primitives)})
    return {
        "generated_at": utc_now(),
        "build": build,
        "profiles": profiles,
        "bridges": bridges,
        "primitives": primitives,
        "plan_report_path": plan["report_path"],
        "report_path": str(report_path),
        "queued_workers": plan.get("queued_workers", []),
        "queued_workloads": plan.get("queued_workloads", []),
    }


def _write_synthesis_report(
    workspace: Path,
    selected: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    bridges: list[dict[str, Any]],
    primitives: list[dict[str, Any]],
) -> Path:
    root = workspace / "triple_kernel"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"TRIPLE_KERNEL_SYNTHESIS_{len(list(root.glob('TRIPLE_KERNEL_SYNTHESIS_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Triple Kernel Synthesis",
        "",
        f"- Generated at: {utc_now()}",
        f"- Selected innovations: {len(selected)}",
        f"- Primitive count: {len(primitives)}",
        "",
        "## Vertex Profiles",
    ]
    for profile in profiles:
        lines.append(
            f"- {profile['label']} selected={profile['selected']} mean_priority={profile['mean_priority']} stability_bias={profile['stability_bias']}"
        )
    lines.extend(["", "## Bridge Matrix"])
    for bridge in bridges:
        lines.append(f"- {bridge['id']} strength={bridge['strength']} :: {bridge['purpose']}")
    lines.extend(["", "## Implemented Primitives"])
    for primitive in primitives:
        lines.append(
            f"- {primitive['id']} readiness={primitive['readiness']} deployment={primitive['deployment']} :: {primitive['summary']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
