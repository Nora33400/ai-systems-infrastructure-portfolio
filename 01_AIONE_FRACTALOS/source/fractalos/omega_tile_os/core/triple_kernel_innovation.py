from __future__ import annotations

from pathlib import Path
from typing import Any

from .autonomy_runtime import submit_workload
from .codex_worker import submit_worker_session
from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import utc_now
from .meta_supervisor import supervisor_plan
from ..tilemindfs.store import TileMindFS


VERTICES = [
    ("matter", "Matter Kernel", "materiel, drivers, interruptions, memoire physique"),
    ("mind", "Mind Kernel", "agents, formules, preuve, planification intelligente"),
    ("mesh", "Mesh Kernel", "services, federation, stockage, mission graph"),
]

DOMAINS = [
    ("boot", "boot path"),
    ("memory", "memory engine"),
    ("interrupts", "interrupt fabric"),
    ("scheduler", "scheduler"),
    ("drivers", "device drivers"),
    ("graphics", "framebuffer and ui"),
    ("storage", "storage and fs"),
    ("network", "network transport"),
    ("security", "capability and proof"),
    ("agent", "agent execution"),
    ("research", "research automation"),
    ("compiler", "toolchain intelligence"),
    ("telemetry", "telemetry bus"),
    ("services", "service isolation"),
    ("shell", "user shell"),
    ("virtualization", "sandbox and vm"),
    ("safety", "thermal and rollback safety"),
    ("proof", "formal verification hints"),
    ("compression", "memory/object compression"),
    ("orchestration", "mission orchestration"),
]

MOTIFS = [
    ("lattice", "introduce a lattice that constrains and accelerates"),
    ("bridge", "build a bridge between"),
    ("fabric", "compose a fabric that fuses"),
    ("gate", "add a gate that validates"),
    ("oracle", "derive an oracle that predicts"),
]

LENSES = [
    ("latency", "for low-latency execution"),
    ("thermal", "under thermal safety constraints"),
    ("reliability", "with rollback and integrity guarantees"),
    ("autonomy", "for semi-autonomous self-expansion"),
]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _catalog() -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    index = 1
    for vertex_id, vertex_label, vertex_scope in VERTICES:
        for domain_id, domain_label in DOMAINS:
            for motif_id, motif_text in MOTIFS:
                for lens_id, lens_text in LENSES:
                    complexity = 0.18 + ((index % 9) * 0.07)
                    risk = 0.04 + ((index % 7) * 0.045)
                    value = 0.58 + ((index % 5) * 0.08)
                    ideas.append(
                        {
                            "id": f"tki-{index:04d}",
                            "vertex": vertex_id,
                            "vertex_label": vertex_label,
                            "domain": domain_id,
                            "domain_label": domain_label,
                            "motif": motif_id,
                            "lens": lens_id,
                            "title": f"{vertex_label} :: {domain_label} :: {motif_id.title()} :: {lens_id.title()}",
                            "description": f"{motif_text} {vertex_scope} around {domain_label} {lens_text}.",
                            "complexity": round(_clamp(complexity), 3),
                            "risk": round(_clamp(risk), 3),
                            "value": round(_clamp(value), 3),
                        }
                    )
                    index += 1
    return ideas


TRIPLE_KERNEL_CATALOG = _catalog()


def triple_kernel_catalog(vertex: str | None = None, limit: int = 1200) -> dict[str, Any]:
    items = [dict(item) for item in TRIPLE_KERNEL_CATALOG]
    if vertex:
        items = [item for item in items if item["vertex"] == vertex]
    return {
        "count": len(items[:limit]),
        "total": len(TRIPLE_KERNEL_CATALOG),
        "vertices": [item[0] for item in VERTICES],
        "items": items[:limit],
    }


def _score(item: dict[str, Any], perf: dict[str, Any], supervisor: dict[str, Any]) -> float:
    stability = float(perf["formulas"].get("stability_index", 0.5))
    risk_level = str(perf["recommendations"].get("risk_level", "unknown"))
    risk_budget = 0.15 if risk_level == "critical" else 0.42 if risk_level == "elevated" else 0.88
    growth = float(supervisor.get("clean_growth_index", 0.4))
    vertex_bonus = 0.08 if item["vertex"] in {"mind", "mesh"} else 0.03
    return round(_clamp(0.34 * float(item["value"]) + 0.22 * (1.0 - float(item["risk"])) + 0.16 * (1.0 - float(item["complexity"])) + 0.14 * stability + 0.1 * risk_budget + 0.04 * growth + vertex_bonus), 4)


def triple_kernel_plan(workspace: Path, limit: int = 24, queue: bool = False) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    supervisor = supervisor_plan(workspace, max_lanes=4)
    items = [dict(item) for item in TRIPLE_KERNEL_CATALOG]
    for item in items:
        item["priority_score"] = _score(item, perf, supervisor)
    selected = sorted(items, key=lambda item: float(item["priority_score"]), reverse=True)[: max(1, limit)]
    report_path = _write_plan_report(workspace, selected, perf, supervisor)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"triple_kernel::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="triple_kernel_innovation",
    )
    queued_workers: list[dict[str, Any]] = []
    queued_workloads: list[dict[str, Any]] = []
    if queue:
        for item in selected[:6]:
            lane = "ecosystem" if item["vertex"] == "mesh" else "research" if item["vertex"] == "mind" else "code"
            mode = "evolver" if lane == "ecosystem" else "researcher" if lane == "research" else "builder"
            queued_workers.append(
                submit_worker_session(
                    workspace,
                    mode,
                    f"TripleKernel :: {item['title']}",
                    str(item["description"]),
                    scope=f"priority={item['priority_score']} vertex={item['vertex']} domain={item['domain']}",
                )
            )
            queued_workloads.append(
                submit_workload(
                    workspace,
                    lane,
                    f"TripleKernel :: {item['title']}",
                    str(item["description"]),
                    context=f"priority={item['priority_score']} motif={item['motif']}",
                )
            )
    append_event(workspace, "triple_kernel_plan_created", {"selected": len(selected), "queued": len(queued_workers)})
    return {
        "generated_at": utc_now(),
        "selected_count": len(selected),
        "selected": selected,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
        "queued_workers": queued_workers,
        "queued_workloads": queued_workloads,
    }


def _write_plan_report(workspace: Path, selected: list[dict[str, Any]], perf: dict[str, Any], supervisor: dict[str, Any]) -> Path:
    root = workspace / "triple_kernel"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"TRIPLE_KERNEL_PLAN_{len(list(root.glob('TRIPLE_KERNEL_PLAN_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Triple Kernel Innovation Plan",
        "",
        f"- Generated at: {utc_now()}",
        f"- Risk level: {perf['recommendations'].get('risk_level')}",
        f"- Stability: {perf['formulas'].get('stability_index')}",
        f"- Clean growth: {supervisor.get('clean_growth_index')}",
        f"- Total invention catalog: {len(TRIPLE_KERNEL_CATALOG)}",
        "",
        "## Selected Innovations",
    ]
    for item in selected:
        lines.append(f"- {item['id']} score={item['priority_score']} :: {item['title']}")
        lines.append(f"  {item['description']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
