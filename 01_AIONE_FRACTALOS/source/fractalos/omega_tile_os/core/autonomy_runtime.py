from __future__ import annotations

from collections import Counter
from pathlib import Path
from uuid import uuid4

from .events import append_event, read_events
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import load_autonomy_state, load_state, save_autonomy_state, utc_now
from ..tilemindfs.store import TileMindFS


WORKLOAD_DOMAINS = ("code", "research", "automation", "ecosystem")


def _slugify(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in normalized.split("-") if part]
    return "-".join(parts[:10]) or "workload"


def _autonomy_root(workspace: Path) -> Path:
    root = workspace / "autonomy"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _workload_root(workspace: Path, workload: dict) -> Path:
    root = _autonomy_root(workspace) / str(workload["domain"]) / f"{workload['id']}_{_slugify(str(workload['title']))}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _domain_jobs(domain: str, title: str) -> list[dict]:
    base = _slugify(title)
    if domain == "code":
        return [
            {"job_id": f"{base}-spec", "resource_estimate": 0.8, "complexity": 0.35, "risk": 0.08},
            {"job_id": f"{base}-impl", "depends_on": [f"{base}-spec"], "resource_estimate": 1.9, "complexity": 0.74, "risk": 0.22, "vectorizable": True},
            {"job_id": f"{base}-verify", "depends_on": [f"{base}-impl"], "resource_estimate": 0.9, "complexity": 0.45, "risk": 0.12, "latency_sensitive": True},
        ]
    if domain == "research":
        return [
            {"job_id": f"{base}-question-map", "resource_estimate": 0.7, "complexity": 0.32, "risk": 0.06},
            {"job_id": f"{base}-evidence", "depends_on": [f"{base}-question-map"], "resource_estimate": 1.4, "complexity": 0.61, "risk": 0.11},
            {"job_id": f"{base}-synthesis", "depends_on": [f"{base}-evidence"], "resource_estimate": 1.0, "complexity": 0.52, "risk": 0.1},
        ]
    if domain == "automation":
        return [
            {"job_id": f"{base}-trigger-design", "resource_estimate": 0.6, "complexity": 0.3, "risk": 0.07},
            {"job_id": f"{base}-flow-map", "depends_on": [f"{base}-trigger-design"], "resource_estimate": 1.1, "complexity": 0.58, "risk": 0.14},
            {"job_id": f"{base}-safeguards", "depends_on": [f"{base}-flow-map"], "resource_estimate": 0.8, "complexity": 0.4, "risk": 0.1},
        ]
    return [
        {"job_id": f"{base}-observe", "resource_estimate": 0.6, "complexity": 0.28, "risk": 0.05},
        {"job_id": f"{base}-integrate", "depends_on": [f"{base}-observe"], "resource_estimate": 1.6, "complexity": 0.67, "risk": 0.16},
        {"job_id": f"{base}-amplify", "depends_on": [f"{base}-integrate"], "resource_estimate": 1.0, "complexity": 0.49, "risk": 0.1},
    ]


def _domain_outputs(workspace: Path, workload: dict, perf_result: dict, autonomy_state: dict) -> dict[str, str]:
    title = str(workload["title"])
    goal = str(workload["goal"])
    context = str(workload.get("context", "")).strip()
    domain = str(workload["domain"])
    recommendations = perf_result["recommendations"]
    metrics = autonomy_state.get("metrics", {})
    recent_processed = metrics.get("processed", 0)

    common_header = (
        f"# {title}\n\n"
        f"- Domain: {domain}\n"
        f"- Created at: {workload['submitted_at']}\n"
        f"- Risk level: {recommendations['risk_level']}\n"
        f"- Recommended concurrency: {recommendations['recommended_concurrency']}\n"
        f"- Recommended resource limit: {recommendations['recommended_resource_limit']}\n\n"
        f"## Goal\n{goal}\n\n"
    )
    if context:
        common_header += f"## Context\n{context}\n\n"

    outputs: dict[str, str] = {}
    if domain == "code":
        outputs["SPEC.md"] = (
            common_header
            + "## Engineering Intent\n"
            + "Build a change set that is testable, reversible, and aligned with FractalOS orchestration.\n\n"
            + "## Work Breakdown\n"
            + "1. Clarify interfaces and impacted modules.\n"
            + "2. Plan edits, tests, and verification steps.\n"
            + "3. Preserve performance and mesh safety.\n"
        )
        outputs["IMPLEMENTATION_PLAN.md"] = (
            common_header
            + "## Implementation Map\n"
            + "1. Read target modules and existing invariants.\n"
            + "2. Apply bounded changes.\n"
            + "3. Run tests or simulations.\n"
            + "4. Archive results in TileMindFS and OmegaRAM.\n\n"
            + f"Processed workloads before this run: {recent_processed}\n"
        )
        outputs["TEST_STRATEGY.md"] = (
            common_header
            + "## Verification\n"
            + "- Unit tests for new logic.\n"
            + "- Integration checks for CLI/daemon surfaces.\n"
            + "- Safety checks for performance governor and mesh state.\n"
        )
    elif domain == "research":
        outputs["RESEARCH_MAP.md"] = (
            common_header
            + "## Research Questions\n"
            + "1. What is already known in the workspace?\n"
            + "2. What evidence is missing?\n"
            + "3. What should be tested or implemented next?\n"
        )
        outputs["HYPOTHESES.md"] = (
            common_header
            + "## Working Hypotheses\n"
            + "- Hypothesis A: the system can converge faster with structured evidence loops.\n"
            + "- Hypothesis B: memory capsules and TileMindFS can support iterative research snapshots.\n"
        )
        outputs["SOURCES_TO_CHECK.md"] = (
            common_header
            + "## Source Lenses\n"
            + "- Local code and docs already in the workspace.\n"
            + "- Mission journals and mesh events.\n"
            + "- Performance telemetry for prioritizing experiments.\n"
        )
    elif domain == "automation":
        outputs["PIPELINE.md"] = (
            common_header
            + "## Automation Flow\n"
            + "1. Trigger discovery.\n"
            + "2. Input validation.\n"
            + "3. Safe action graph.\n"
            + "4. Observable outputs and rollback path.\n"
        )
        outputs["TRIGGERS.md"] = (
            common_header
            + "## Trigger Classes\n"
            + "- Manual CLI invocation.\n"
            + "- Mesh-adopted mission.\n"
            + "- Periodic self-evolution cycle.\n"
        )
        outputs["SAFETY_RULES.md"] = (
            common_header
            + "## Safeguards\n"
            + "- Keep actions idempotent where possible.\n"
            + "- Prefer append-only event trails.\n"
            + "- Avoid destructive file operations.\n"
        )
    else:
        outputs["EVOLUTION_MAP.md"] = (
            common_header
            + "## Ecosystem Growth Axes\n"
            + "- Runtime quality\n"
            + "- Automation depth\n"
            + "- Research memory\n"
            + "- Mesh-scale execution\n"
        )
        outputs["INTEGRATION_TARGETS.md"] = (
            common_header
            + "## Integration Targets\n"
            + "- Code workload orchestration\n"
            + "- Research artifact memory\n"
            + "- Automation loops\n"
            + "- Self-reflection telemetry\n"
        )
        outputs["GROWTH_TASKS.md"] = (
            common_header
            + "## Growth Tasks\n"
            + "1. Detect the most active domain.\n"
            + "2. Strengthen the weakest domain.\n"
            + "3. Archive the decision and queue the next cycle.\n"
        )
    return outputs


def submit_workload(workspace: Path, domain: str, title: str, goal: str, context: str = "") -> dict[str, object]:
    normalized_domain = domain.strip().lower()
    if normalized_domain not in WORKLOAD_DOMAINS:
        raise ValueError(f"Unsupported domain: {domain}")

    autonomy_state = load_autonomy_state(workspace)
    workload = {
        "id": uuid4().hex[:12],
        "domain": normalized_domain,
        "title": title.strip() or f"{normalized_domain.title()} workload",
        "goal": goal.strip(),
        "context": context.strip(),
        "status": "queued",
        "submitted_at": utc_now(),
    }
    autonomy_state["workloads"].append(workload)
    autonomy_state["metrics"]["submitted"] = int(autonomy_state["metrics"].get("submitted", 0)) + 1
    save_autonomy_state(workspace, autonomy_state)
    append_event(workspace, "autonomy_workload_submitted", {"id": workload["id"], "domain": normalized_domain, "title": workload["title"]})
    return workload


def _queue_recommendations(autonomy_state: dict, recommendations: list[dict[str, str]]) -> list[dict[str, object]]:
    existing = {(str(item.get("domain")), str(item.get("title"))) for item in autonomy_state.get("workloads", [])}
    queued = []
    for item in recommendations:
        key = (item["domain"], item["title"])
        if key in existing:
            continue
        workload = {
            "id": uuid4().hex[:12],
            "domain": item["domain"],
            "title": item["title"],
            "goal": item["goal"],
            "context": item.get("context", ""),
            "status": "queued",
            "submitted_at": utc_now(),
            "origin": "autonomy-evolve",
        }
        autonomy_state["workloads"].append(workload)
        autonomy_state["metrics"]["submitted"] = int(autonomy_state["metrics"].get("submitted", 0)) + 1
        queued.append(workload)
        existing.add(key)
    return queued


def _store_outputs(workspace: Path, workload: dict, outputs: dict[str, str]) -> tuple[list[str], list[dict], list[str]]:
    root = _workload_root(workspace, workload)
    created_files: list[str] = []
    tilefs = TileMindFS(workspace)
    omega_ram = OmegaRAM(workspace)
    archives: list[dict] = []
    ram_keys: list[str] = []

    for name, content in outputs.items():
        target = root / name
        target.write_text(content, encoding="utf-8")
        created_files.append(str(target))
        archives.append(tilefs.store_file(target))
        ram_key = f"autonomy::{workload['domain']}::{workload['id']}::{name}"
        omega_ram.put_text(key=ram_key, text=content, source=f"autonomy:{workload['domain']}")
        ram_keys.append(ram_key)
    return created_files, archives, ram_keys


def run_workloads(workspace: Path, max_items: int = 1) -> dict[str, object]:
    autonomy_state = load_autonomy_state(workspace)
    perf_result = PerformanceGovernor(workspace).apply()
    queued = [item for item in autonomy_state.get("workloads", []) if item.get("status") == "queued"]
    processed: list[dict[str, object]] = []

    for workload in queued[: max(1, max_items)]:
        workload["status"] = "running"
        workload["started_at"] = utc_now()
        outputs = _domain_outputs(workspace, workload, perf_result, autonomy_state)
        created_files, archives, ram_keys = _store_outputs(workspace, workload, outputs)
        workload["status"] = "done"
        workload["completed_at"] = utc_now()
        workload["files"] = created_files
        workload["tile_archives"] = [item.get("manifest_id", "") for item in archives]
        workload["ram_keys"] = ram_keys
        workload["job_blueprint"] = _domain_jobs(str(workload["domain"]), str(workload["title"]))
        processed.append(
            {
                "id": workload["id"],
                "domain": workload["domain"],
                "title": workload["title"],
                "files": created_files,
                "job_blueprint": workload["job_blueprint"],
            }
        )
        append_event(workspace, "autonomy_workload_completed", {"id": workload["id"], "domain": workload["domain"], "file_count": len(created_files)})

    autonomy_state["metrics"]["processed"] = int(autonomy_state["metrics"].get("processed", 0)) + len(processed)
    autonomy_state["cycles"] = (
        autonomy_state.get("cycles", [])
        + [
            {
                "kind": "workload-run",
                "ts": utc_now(),
                "processed_ids": [item["id"] for item in processed],
                "recommended_concurrency": perf_result["recommendations"]["recommended_concurrency"],
                "risk_level": perf_result["recommendations"]["risk_level"],
            }
        ]
    )[-100:]
    save_autonomy_state(workspace, autonomy_state)
    return {
        "processed": processed,
        "queued_remaining": len([item for item in autonomy_state.get("workloads", []) if item.get("status") == "queued"]),
        "performance": perf_result,
    }


def autonomy_report(workspace: Path) -> dict[str, object]:
    autonomy_state = load_autonomy_state(workspace)
    workloads = list(autonomy_state.get("workloads", []))
    status_counts = Counter(str(item.get("status", "unknown")) for item in workloads)
    domain_counts = Counter(str(item.get("domain", "unknown")) for item in workloads)
    recent_done = [item for item in workloads if item.get("status") == "done"][-5:]
    return {
        "metrics": autonomy_state.get("metrics", {}),
        "status_counts": dict(status_counts),
        "domain_counts": dict(domain_counts),
        "queued": [item for item in workloads if item.get("status") == "queued"][-10:],
        "recent_done": recent_done,
        "cycle_count": len(autonomy_state.get("cycles", [])),
    }


def evolve_ecosystem(workspace: Path, queue_followups: bool = True) -> dict[str, object]:
    autonomy_state = load_autonomy_state(workspace)
    system_state = load_state(workspace)
    recent_events = read_events(workspace, limit=40)
    domain_counts = Counter(str(item.get("domain", "unknown")) for item in autonomy_state.get("workloads", []))
    missing_domains = [domain for domain in WORKLOAD_DOMAINS if domain_counts.get(domain, 0) == 0]
    queued_domains = {str(item.get("domain")) for item in autonomy_state.get("workloads", []) if item.get("status") == "queued"}

    recommendations: list[dict[str, str]] = []
    for domain in WORKLOAD_DOMAINS:
        if domain in queued_domains:
            continue
        if domain in missing_domains:
            recommendations.append(
                {
                    "domain": domain,
                    "title": f"{domain.title()} bootstrap",
                    "goal": f"Initialize a strong {domain} lane inside FractalOS.",
                    "context": "Generated by the ecosystem evolution cycle.",
                }
            )
            continue
        if domain_counts.get(domain, 0) <= max(domain_counts.values() or [0]) - 2:
            recommendations.append(
                {
                    "domain": domain,
                    "title": f"{domain.title()} reinforcement",
                    "goal": f"Strengthen the {domain} lane so the ecosystem stays balanced.",
                    "context": "Generated by domain imbalance detection.",
                }
            )

    root = _autonomy_root(workspace) / "ecosystem"
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / f"EVOLUTION_CYCLE_{len(autonomy_state.get('cycles', [])) + 1:03d}.md"
    processed_intents = int(system_state.get("metrics", {}).get("processed_intents", 0))
    event_kinds = Counter(str(item.get("kind", "")) for item in recent_events)
    report_text = (
        "# FractalOS Ecosystem Evolution\n\n"
        f"- Generated at: {utc_now()}\n"
        f"- Processed intents: {processed_intents}\n"
        f"- Autonomy submitted: {autonomy_state.get('metrics', {}).get('submitted', 0)}\n"
        f"- Autonomy processed: {autonomy_state.get('metrics', {}).get('processed', 0)}\n\n"
        "## Domain Balance\n"
        + "\n".join(f"- {domain}: {domain_counts.get(domain, 0)}" for domain in WORKLOAD_DOMAINS)
        + "\n\n## Recent Signals\n"
        + ("\n".join(f"- {kind}: {count}" for kind, count in event_kinds.items()) or "- No recent events.")
        + "\n\n## Recommended Follow-ups\n"
        + ("\n".join(f"- [{item['domain']}] {item['title']}: {item['goal']}" for item in recommendations) or "- No new follow-ups.")
        + "\n"
    )
    report_path.write_text(report_text, encoding="utf-8")
    TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"autonomy::ecosystem::evolution::{report_path.stem}",
        text=report_text,
        source="autonomy:evolution",
    )

    queued = _queue_recommendations(autonomy_state, recommendations) if queue_followups else []
    autonomy_state["metrics"]["evolution_cycles"] = int(autonomy_state["metrics"].get("evolution_cycles", 0)) + 1
    autonomy_state["cycles"] = (
        autonomy_state.get("cycles", [])
        + [
            {
                "kind": "ecosystem-evolve",
                "ts": utc_now(),
                "report_path": str(report_path),
                "queued_ids": [item["id"] for item in queued],
            }
        ]
    )[-100:]
    save_autonomy_state(workspace, autonomy_state)
    append_event(workspace, "autonomy_ecosystem_evolved", {"report_path": str(report_path), "queued": len(queued)})
    return {
        "report_path": str(report_path),
        "recommendations": recommendations,
        "queued": queued,
    }
