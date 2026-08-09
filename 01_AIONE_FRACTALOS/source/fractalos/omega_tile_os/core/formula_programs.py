from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .autonomy_runtime import submit_workload
from .events import append_event
from .ram_memory import OmegaRAM
from .research_fusion import DOMAIN_TO_OS_AXIS, scan_formula_corpus
from .state import load_formula_program_state, save_formula_program_state, utc_now
from ..tilemindfs.store import TileMindFS


DOMAIN_KERNELS = {
    "scheduler_control": "adaptive_priority_gate",
    "context_routing": "route_confidence_amplifier",
    "energy_perf": "thermal_efficiency_budget",
    "risk_security": "guarded_execution_score",
    "proof_validation": "evidence_confidence_gate",
    "coherence_invariants": "state_coherence_balancer",
    "cube_compression_gpu": "tile_packing_efficiency",
    "tableau_state_indexing": "memory_index_heatmap",
    "agent_orchestration": "worker_lane_allocator",
    "fractal_complexity": "ecosystem_growth_balance",
    "seed_state_dynamics": "safe_mode_transition",
    "dynamic_static_reconciliation": "plan_runtime_bridge",
}


DOMAIN_WEIGHTS = {
    "scheduler_control": {"performance": 0.34, "energy": 0.14, "complexity": 0.18, "risk": 0.14, "coherence": 0.20},
    "context_routing": {"performance": 0.22, "energy": 0.10, "complexity": 0.16, "risk": 0.20, "coherence": 0.32},
    "energy_perf": {"performance": 0.30, "energy": 0.34, "complexity": 0.10, "risk": 0.16, "coherence": 0.10},
    "risk_security": {"performance": 0.10, "energy": 0.10, "complexity": 0.10, "risk": 0.46, "coherence": 0.24},
    "proof_validation": {"performance": 0.10, "energy": 0.08, "complexity": 0.16, "risk": 0.22, "coherence": 0.44},
    "coherence_invariants": {"performance": 0.12, "energy": 0.08, "complexity": 0.18, "risk": 0.18, "coherence": 0.44},
    "cube_compression_gpu": {"performance": 0.28, "energy": 0.20, "complexity": 0.18, "risk": 0.12, "coherence": 0.22},
    "tableau_state_indexing": {"performance": 0.20, "energy": 0.12, "complexity": 0.18, "risk": 0.14, "coherence": 0.36},
    "agent_orchestration": {"performance": 0.22, "energy": 0.10, "complexity": 0.20, "risk": 0.18, "coherence": 0.30},
    "fractal_complexity": {"performance": 0.16, "energy": 0.12, "complexity": 0.34, "risk": 0.16, "coherence": 0.22},
    "seed_state_dynamics": {"performance": 0.12, "energy": 0.12, "complexity": 0.18, "risk": 0.28, "coherence": 0.30},
    "dynamic_static_reconciliation": {"performance": 0.18, "energy": 0.10, "complexity": 0.18, "risk": 0.22, "coherence": 0.32},
}


DEFAULT_WEIGHTS = {"performance": 0.18, "energy": 0.14, "complexity": 0.18, "risk": 0.22, "coherence": 0.28}

DOMAIN_TO_AUTONOMY_LANE = {
    "scheduler_control": "code",
    "context_routing": "automation",
    "energy_perf": "ecosystem",
    "risk_security": "automation",
    "proof_validation": "research",
    "coherence_invariants": "ecosystem",
    "cube_compression_gpu": "code",
    "tableau_state_indexing": "code",
    "agent_orchestration": "automation",
    "fractal_complexity": "ecosystem",
    "seed_state_dynamics": "ecosystem",
    "dynamic_static_reconciliation": "code",
}

DOMAIN_ACTION_BIASES = {
    "scheduler_control": {"worker-run": 0.04, "autonomy-run": 0.03},
    "context_routing": {"autonomy-run": 0.05, "worker-run": 0.03, "mesh-consensus": 0.02},
    "energy_perf": {"perf-tune": 0.07, "mesh-compact": 0.03},
    "risk_security": {"perf-tune": 0.05, "mesh-compact": 0.04},
    "proof_validation": {"worker-run": 0.03, "autonomy-run": 0.02},
    "coherence_invariants": {"mesh-compact": 0.05, "mesh-consensus": 0.03},
    "cube_compression_gpu": {"perf-tune": 0.02, "autonomy-run": 0.02},
    "tableau_state_indexing": {"autonomy-run": 0.03, "worker-run": 0.02},
    "agent_orchestration": {"worker-run": 0.05, "autonomy-run": 0.03},
    "fractal_complexity": {"autonomy-evolve": 0.05},
    "seed_state_dynamics": {"perf-tune": 0.04, "autonomy-evolve": 0.02},
    "dynamic_static_reconciliation": {"worker-run": 0.04, "autonomy-run": 0.04},
}

PROTECTIVE_DOMAINS = {"energy_perf", "risk_security", "coherence_invariants", "seed_state_dynamics"}
PROTECTIVE_ACTION_BIASES = {
    "energy_perf": {"perf-tune": 0.08, "mesh-compact": 0.03},
    "risk_security": {"perf-tune": 0.06, "mesh-compact": 0.05},
    "coherence_invariants": {"mesh-compact": 0.08, "mesh-consensus": 0.04},
    "seed_state_dynamics": {"perf-tune": 0.05, "mesh-compact": 0.03},
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_float(signals: dict[str, object], key: str, default: float) -> float:
    try:
        return _clamp(float(signals.get(key, default)))
    except (TypeError, ValueError):
        return default


def _program_id(domain: str, records: list[dict[str, object]]) -> str:
    seed = "|".join([domain] + [str(item.get("f1", ""))[:80] for item in records[:5]])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"{domain.replace('_', '-')}-{digest}"


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(value)) for value in weights.values()) or 1.0
    return {key: round(max(0.0, float(value)) / total, 4) for key, value in weights.items()}


def _domain_records(records: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("domain") or "unknown")].append(record)
    return dict(grouped)


def _build_program(domain: str, records: list[dict[str, object]]) -> dict[str, object]:
    modules = Counter(str(item.get("module") or "unknown") for item in records)
    weights = _normalize_weights(DOMAIN_WEIGHTS.get(domain, DEFAULT_WEIGHTS))
    program_id = _program_id(domain, records)
    source_examples = []
    for item in records[:3]:
        source_examples.append(
            {
                "module": item.get("module", "unknown"),
                "note": item.get("note", ""),
                "formula": item.get("f1", ""),
                "file": item.get("file", ""),
            }
        )
    return {
        "schema": "fractal_os.formula_program.v1",
        "id": program_id,
        "domain": domain,
        "kernel": DOMAIN_KERNELS.get(domain, "bounded_formula_policy"),
        "created_at": utc_now(),
        "source_formula_count": len(records),
        "module_targets": [{"module": module, "count": count} for module, count in modules.most_common(5)],
        "weights": weights,
        "activation": {
            "safe_min": 0.0,
            "safe_max": 1.0,
            "install_mode": "reversible-data-policy",
            "requires_simulation": True,
        },
        "integration": {
            "target": DOMAIN_TO_OS_AXIS.get(domain, "general FractalOS autonomy lane"),
            "runtime": "omega_tile_os.core.formula_programs.evaluate_formula_program",
            "commands": ["formula-simulate", "formula-programs"],
        },
        "source_examples": source_examples,
    }


def _render_program_readme(program: dict[str, object]) -> str:
    lines = [
        f"# Formula Program :: {program['id']}",
        "",
        f"- Domain: {program['domain']}",
        f"- Kernel: {program['kernel']}",
        f"- Target: {program['integration']['target']}",
        f"- Source formulas: {program['source_formula_count']}",
        "",
        "## Safe Execution Contract",
        "- The corpus formula text is never executed as code.",
        "- The installed program is a bounded JSON policy evaluated by FractalOS.",
        "- Outputs remain in safe numeric ranges and can be simulated before use.",
        "",
        "## Weights",
    ]
    for key, value in dict(program["weights"]).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Source Examples"])
    for item in program.get("source_examples", []):
        lines.append(f"- {item.get('module', 'unknown')} :: {item.get('note') or item.get('formula') or 'no note'}")
    return "\n".join(lines) + "\n"


def evaluate_formula_program(program: dict[str, object], signals: dict[str, object] | None = None) -> dict[str, object]:
    signals = signals or {}
    weights = dict(program.get("weights", DEFAULT_WEIGHTS))
    perf = _safe_float(signals, "performance_pressure", 0.52)
    energy = 1.0 - _safe_float(signals, "energy_pressure", 0.32)
    complexity = 1.0 - _safe_float(signals, "complexity_pressure", 0.36)
    risk = 1.0 - _safe_float(signals, "risk_pressure", 0.24)
    coherence = _safe_float(signals, "coherence", 0.72)
    score = _clamp(
        perf * float(weights.get("performance", 0.0))
        + energy * float(weights.get("energy", 0.0))
        + complexity * float(weights.get("complexity", 0.0))
        + risk * float(weights.get("risk", 0.0))
        + coherence * float(weights.get("coherence", 0.0))
    )
    domain = str(program.get("domain", "unknown"))
    recommendation: dict[str, object] = {
        "confidence": round(score, 4),
        "mode": "observe" if score < 0.50 else "assist" if score < 0.72 else "accelerate",
        "safe_to_apply": score >= 0.55,
    }
    if domain == "scheduler_control":
        recommendation["priority_multiplier"] = round(0.70 + score * 0.70, 4)
    elif domain == "energy_perf":
        recommendation["thermal_budget_fraction"] = round(0.45 + score * 0.35, 4)
    elif domain == "risk_security":
        recommendation["guard_threshold"] = round(0.50 + (1.0 - score) * 0.30, 4)
        recommendation["safe_to_apply"] = score >= 0.62
    elif domain == "context_routing":
        recommendation["route_bonus"] = round(score * 0.22, 4)
    elif domain == "cube_compression_gpu":
        recommendation["packing_aggressiveness"] = round(0.25 + score * 0.55, 4)
    elif domain == "tableau_state_indexing":
        recommendation["index_heat_boost"] = round(score * 0.40, 4)
    elif domain == "agent_orchestration":
        recommendation["worker_parallelism_hint"] = max(1, min(4, int(1 + score * 4)))
    else:
        recommendation["balance_factor"] = round(score, 4)
    return {
        "program_id": program.get("id", "unknown"),
        "domain": domain,
        "kernel": program.get("kernel", "bounded_formula_policy"),
        "score": round(score, 4),
        "recommendation": recommendation,
    }


def discover_formula_programs(
    workspace: Path,
    corpus_root: Path,
    max_formula_files: int = 8,
    max_programs: int = 6,
    install: bool = True,
) -> dict[str, object]:
    corpus = scan_formula_corpus(corpus_root, max_files=max_formula_files)
    records = list(corpus.get("records", []))
    grouped = _domain_records(records)
    selected = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:max_programs]
    programs = [_build_program(domain, domain_records) for domain, domain_records in selected if domain != "unknown"]

    state = load_formula_program_state(workspace)
    installed: list[dict[str, object]] = []
    root = workspace / "formula_programs"
    root.mkdir(parents=True, exist_ok=True)
    existing = {item.get("id"): item for item in state.get("programs", [])}

    if install:
        for program in programs:
            program_dir = root / str(program["id"])
            program_dir.mkdir(parents=True, exist_ok=True)
            program_path = program_dir / "PROGRAM.json"
            readme_path = program_dir / "README.md"
            program_path.write_text(json.dumps(program, indent=2, ensure_ascii=True), encoding="utf-8")
            readme_path.write_text(_render_program_readme(program), encoding="utf-8")
            tile_archive = TileMindFS(workspace).store_file(program_path)
            OmegaRAM(workspace).put_text(
                key=f"formula_program::{program['id']}",
                text=_render_program_readme(program),
                source="formula_programs",
            )
            entry = {
                "id": program["id"],
                "domain": program["domain"],
                "kernel": program["kernel"],
                "program_path": str(program_path),
                "readme_path": str(readme_path),
                "tile_manifest": tile_archive.get("manifest_id", ""),
                "source_formula_count": program["source_formula_count"],
                "installed_at": utc_now(),
            }
            existing[program["id"]] = entry
            installed.append(entry)

    state["programs"] = list(existing.values())[-80:]
    metrics = state.setdefault("metrics", {})
    metrics["discoveries"] = int(metrics.get("discoveries", 0)) + 1
    metrics["installed"] = int(metrics.get("installed", 0)) + len(installed)
    state["last_discovery"] = {
        "ts": utc_now(),
        "corpus_root": str(corpus_root),
        "formula_files_sampled": len(corpus.get("sampled_files", [])),
        "formula_count": corpus.get("formula_count", 0),
        "program_count": len(programs),
        "installed_count": len(installed),
        "domains": [program["domain"] for program in programs],
    }
    save_formula_program_state(workspace, state)
    append_event(
        workspace,
        "formula_programs_discovered",
        {"program_count": len(programs), "installed_count": len(installed), "domains": state["last_discovery"]["domains"]},
    )
    return {
        "last_discovery": state["last_discovery"],
        "programs": programs,
        "installed": installed,
        "corpus": {key: value for key, value in corpus.items() if key != "records"},
    }


def _load_installed_programs(state: dict) -> list[dict[str, object]]:
    programs: list[dict[str, object]] = []
    for item in state.get("programs", []):
        path = Path(str(item.get("program_path", "")))
        if not path.exists():
            continue
        try:
            programs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return programs


def simulate_formula_programs(workspace: Path, signals: dict[str, object] | None = None) -> dict[str, object]:
    state = load_formula_program_state(workspace)
    programs = _load_installed_programs(state)
    evaluations = [evaluate_formula_program(program, signals=signals) for program in programs]
    metrics = state.setdefault("metrics", {})
    metrics["evaluations"] = int(metrics.get("evaluations", 0)) + len(evaluations)
    save_formula_program_state(workspace, state)
    append_event(workspace, "formula_programs_simulated", {"evaluations": len(evaluations)})
    return {
        "signals": signals or {},
        "evaluation_count": len(evaluations),
        "evaluations": evaluations,
    }


def formula_runtime_advice(
    workspace: Path,
    perf_report: dict[str, object] | None = None,
    router_signals: dict[str, object] | None = None,
) -> dict[str, object]:
    state = load_formula_program_state(workspace)
    programs = _load_installed_programs(state)
    perf_report = perf_report or {}
    formulas = dict(perf_report.get("formulas", {})) if isinstance(perf_report.get("formulas", {}), dict) else {}
    recommendations = (
        dict(perf_report.get("recommendations", {})) if isinstance(perf_report.get("recommendations", {}), dict) else {}
    )
    risk_level = str(recommendations.get("risk_level", "low"))
    risk_pressure = {"low": 0.12, "nominal": 0.20, "elevated": 0.42, "critical": 0.82}.get(risk_level, 0.35)
    signals = {
        "performance_pressure": formulas.get("cpu_pressure", 0.52),
        "energy_pressure": 1.0 - float(formulas.get("throughput_index", 0.68)),
        "complexity_pressure": min(1.0, (int((router_signals or {}).get("queued_autonomy", 0)) + int((router_signals or {}).get("queued_workers", 0))) / 12.0),
        "risk_pressure": risk_pressure,
        "coherence": formulas.get("stability_index", 0.72),
    }
    evaluations = [evaluate_formula_program(program, signals=signals) for program in programs]
    safe_evaluations = [
        item for item in evaluations if dict(item.get("recommendation", {})).get("safe_to_apply") and float(item.get("score", 0.0)) >= 0.55
    ]
    protective_evaluations = [
        item
        for item in evaluations
        if str(item.get("domain", "unknown")) in PROTECTIVE_DOMAINS and float(item.get("score", 0.0)) >= 0.40
    ]
    action_biases: dict[str, float] = {}
    for item in safe_evaluations:
        domain = str(item.get("domain", "unknown"))
        score = float(item.get("score", 0.0))
        for action_id, base_bias in DOMAIN_ACTION_BIASES.get(domain, {}).items():
            action_biases[action_id] = action_biases.get(action_id, 0.0) + base_bias * score
    protective_biases: dict[str, float] = {}
    if risk_level in {"elevated", "critical"}:
        for item in protective_evaluations:
            domain = str(item.get("domain", "unknown"))
            score = float(item.get("score", 0.0))
            for action_id, base_bias in PROTECTIVE_ACTION_BIASES.get(domain, {}).items():
                protective_biases[action_id] = protective_biases.get(action_id, 0.0) + base_bias * score
    action_biases = {key: round(min(0.08, value), 4) for key, value in action_biases.items() if value > 0}
    protective_biases = {key: round(min(0.10, value), 4) for key, value in protective_biases.items() if value > 0}
    for action_id, value in protective_biases.items():
        action_biases[action_id] = round(min(0.10, action_biases.get(action_id, 0.0) + value), 4)
    top = sorted(safe_evaluations, key=lambda item: float(item.get("score", 0.0)), reverse=True)[:5]
    top_protective = sorted(protective_evaluations, key=lambda item: float(item.get("score", 0.0)), reverse=True)[:5]
    return {
        "signals": signals,
        "program_count": len(programs),
        "safe_program_count": len(safe_evaluations),
        "protective_program_count": len(protective_evaluations),
        "action_biases": action_biases,
        "protective_biases": protective_biases,
        "top_evaluations": top,
        "top_protective_evaluations": top_protective,
    }


def _render_evolution_report(evolution: dict[str, object], evaluations: list[dict[str, object]], queued: list[dict[str, object]]) -> str:
    lines = [
        "# Formula Program Evolution",
        "",
        f"- Generated at: {evolution['ts']}",
        f"- Evaluations: {len(evaluations)}",
        f"- Queued followups: {len(queued)}",
        "",
        "## Safe Evaluations",
    ]
    for item in evaluations:
        rec = dict(item.get("recommendation", {}))
        lines.append(
            f"- {item.get('domain')} :: score={item.get('score')} :: mode={rec.get('mode')} :: safe={rec.get('safe_to_apply')}"
        )
    lines.extend(["", "## Queued Workloads"])
    if not queued:
        lines.append("- none")
    for item in queued:
        lines.append(f"- {item.get('domain')} :: {item.get('title')} :: {item.get('id')}")
    return "\n".join(lines) + "\n"


def evolve_formula_programs(
    workspace: Path,
    corpus_root: Path | None = None,
    refresh: bool = False,
    max_formula_files: int = 8,
    max_programs: int = 6,
    queue_limit: int = 4,
    signals: dict[str, object] | None = None,
) -> dict[str, object]:
    if refresh and corpus_root is not None:
        discover_formula_programs(
            workspace,
            corpus_root,
            max_formula_files=max_formula_files,
            max_programs=max_programs,
            install=True,
        )

    simulation = simulate_formula_programs(workspace, signals=signals)
    evaluations = sorted(
        list(simulation.get("evaluations", [])),
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    queued: list[dict[str, object]] = []
    for item in evaluations:
        if len(queued) >= max(0, int(queue_limit)):
            break
        recommendation = dict(item.get("recommendation", {}))
        if not recommendation.get("safe_to_apply"):
            continue
        domain = str(item.get("domain", "unknown"))
        lane = DOMAIN_TO_AUTONOMY_LANE.get(domain, "research")
        title = f"Formula Program :: {domain}"
        goal = (
            f"Integrer le programme-formule {item.get('program_id')} dans l'axe {DOMAIN_TO_OS_AXIS.get(domain, 'FractalOS')} "
            "avec tests bornes, rollback et mesure de stabilite."
        )
        context = (
            f"kernel={item.get('kernel')} score={item.get('score')} mode={recommendation.get('mode')} "
            f"recommendation={json.dumps(recommendation, sort_keys=True, ensure_ascii=True)}"
        )
        queued.append(submit_workload(workspace, lane, title, goal, context=context))

    state = load_formula_program_state(workspace)
    metrics = state.setdefault("metrics", {})
    metrics["evolutions"] = int(metrics.get("evolutions", 0)) + 1
    metrics["queued_followups"] = int(metrics.get("queued_followups", 0)) + len(queued)

    evolution_id = f"formula_evolution_{int(metrics.get('evolutions', 0)):04d}"
    evolution = {
        "id": evolution_id,
        "ts": utc_now(),
        "evaluation_count": len(evaluations),
        "queued_count": len(queued),
        "queued_ids": [item["id"] for item in queued],
        "top_domains": [item.get("domain") for item in evaluations[:queue_limit]],
    }
    root = workspace / "formula_programs" / "evolutions"
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / f"{evolution_id}.md"
    report_text = _render_evolution_report(evolution, evaluations, queued)
    report_path.write_text(report_text, encoding="utf-8")
    tile_archive = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"formula_evolution::{evolution_id}",
        text=report_text,
        source="formula_programs",
    )
    evolution["report_path"] = str(report_path)
    evolution["tile_manifest"] = tile_archive.get("manifest_id", "")
    state["last_evolution"] = evolution
    save_formula_program_state(workspace, state)
    append_event(
        workspace,
        "formula_programs_evolved",
        {"evolution_id": evolution_id, "queued_count": len(queued), "top_domains": evolution["top_domains"]},
    )
    return {
        "evolution": evolution,
        "queued": queued,
        "simulation": simulation,
        "report_path": str(report_path),
    }


def formula_program_report(workspace: Path) -> dict[str, object]:
    state = load_formula_program_state(workspace)
    return {
        "metrics": state.get("metrics", {}),
        "last_discovery": state.get("last_discovery"),
        "last_evolution": state.get("last_evolution"),
        "program_count": len(state.get("programs", [])),
        "recent_programs": state.get("programs", [])[-10:],
    }
