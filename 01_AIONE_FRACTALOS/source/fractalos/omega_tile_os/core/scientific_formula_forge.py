from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .autonomy_runtime import submit_workload
from .corpus_deep_index import corpus_deep_index_report
from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


FORMULA_TARGETS = [
    {
        "id": "storage-density",
        "sector": "storage",
        "subsystem": "TileMindFS",
        "principle": "entropy-tiered tile packing",
        "equation": "D_eff = (1 + H_dup + H_delta) * C_codec * A_heat",
        "guard": "never rewrite originals; store reversible manifests and verify reconstruction hashes",
        "effect": "higher effective capacity through dedupe, deltas and heat-aware compression",
    },
    {
        "id": "ram-morphology",
        "sector": "memory",
        "subsystem": "OmegaRAM",
        "principle": "hot/warm/cold semantic retention",
        "equation": "R_keep = sigmoid(2H_access + C_context - P_pressure)",
        "guard": "demote before evicting and cap hot memory below governor budget",
        "effect": "more useful cache residency under pressure",
    },
    {
        "id": "thermal-throughput",
        "sector": "cpu",
        "subsystem": "PerformanceGovernor",
        "principle": "thermal envelope shaped concurrency",
        "equation": "Q_safe = cores * S_stability * sqrt(T_headroom)",
        "guard": "reduce concurrency when stability or thermal headroom falls",
        "effect": "sustained speed without heat spikes",
    },
    {
        "id": "latency-field",
        "sector": "scheduler",
        "subsystem": "RegimeScheduler",
        "principle": "intent weighted latency field",
        "equation": "L_score = I_user / (1 + Q_queue + C_contention)",
        "guard": "interactive lanes cannot starve proof, IO or safety checks",
        "effect": "more responsive desktop and agents",
    },
    {
        "id": "proof-promotion",
        "sector": "security",
        "subsystem": "ProofState",
        "principle": "evidence gated state promotion",
        "equation": "P_promote = min(T_tests, D_doctor, R_rollback) * C_confidence",
        "guard": "unproven states remain speculative and reversible",
        "effect": "safer auto-evolution and live upgrades",
    },
    {
        "id": "gpu-mesh",
        "sector": "gpu",
        "subsystem": "GpuRuntime",
        "principle": "batch locality and native runtime guard",
        "equation": "G_use = B_batch * M_locality * N_native * T_headroom",
        "guard": "fall back to CPU when native GPU telemetry is absent",
        "effect": "GPU acceleration only when it is actually available and safe",
    },
    {
        "id": "network-resilience",
        "sector": "network",
        "subsystem": "MeshFederation",
        "principle": "redundant route confidence",
        "equation": "R_mesh = C_peer * (1 - F_fail) * S_cache",
        "guard": "prefer offline-first local execution when peers are stale",
        "effect": "more reliable multi-machine expansion",
    },
    {
        "id": "agent-foundry",
        "sector": "ai-dev",
        "subsystem": "Foundry",
        "principle": "bounded multi-agent production line",
        "equation": "A_gain = min(W_workers, B_budget) * P_proof * (1 - R_risk)",
        "guard": "queue only bounded workloads and stop on elevated risk",
        "effect": "more useful autonomous development",
    },
    {
        "id": "desktop-attention",
        "sector": "ui",
        "subsystem": "FractalDesktop",
        "principle": "persistent overlay attention routing",
        "equation": "U_focus = I_goal * P_overlay / (1 + N_noise)",
        "guard": "overlay stays inspectable and never hides critical system warnings",
        "effect": "desktop becomes a control plane instead of window clutter",
    },
    {
        "id": "future-branching",
        "sector": "simulation",
        "subsystem": "FutureFabric",
        "principle": "speculate, score, promote",
        "equation": "F_best = argmax(score(branch) * proof(branch) - cost(branch))",
        "guard": "speculative branches cannot mutate stable state until promoted",
        "effect": "safer exploration of code, configs and workflows",
    },
]

FORMULA_VARIANTS = [
    ("alpha", "low-risk baseline", 0.74, 0.92),
    ("beta", "balanced adaptive", 0.68, 0.86),
    ("gamma", "high-throughput guarded", 0.78, 0.76),
    ("delta", "low-latency interactive", 0.72, 0.82),
    ("epsilon", "long-run stability", 0.64, 0.95),
    ("zeta", "speculative branch", 0.83, 0.70),
    ("eta", "proof-heavy promotion", 0.61, 0.98),
    ("theta", "fractal multi-scale", 0.75, 0.80),
    ("iota", "energy-aware", 0.66, 0.93),
    ("kappa", "capacity-oriented", 0.80, 0.78),
    ("lambda", "agent-cooperative", 0.74, 0.84),
    ("mu", "semantic-indexed", 0.70, 0.88),
]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _formula_id(target: dict[str, str], variant: str) -> str:
    return f"{target['id']}-{variant}"


def scientific_formula_catalog(target: str | None = None, limit: int = 120) -> list[dict[str, Any]]:
    formulas: list[dict[str, Any]] = []
    for target_spec in FORMULA_TARGETS:
        if target and target not in {target_spec["id"], target_spec["sector"], target_spec["subsystem"]}:
            continue
        for variant, mode, potential, safety in FORMULA_VARIANTS:
            formulas.append(
                {
                    "id": _formula_id(target_spec, variant),
                    "name": f"{target_spec['principle']} :: {variant}",
                    "sector": target_spec["sector"],
                    "target": target_spec["subsystem"],
                    "mode": mode,
                    "equation": target_spec["equation"],
                    "safety_guard": target_spec["guard"],
                    "expected_effect": target_spec["effect"],
                    "potential": potential,
                    "safety": safety,
                    "safe_default": safety >= 0.80,
                    "local_only": True,
                }
            )
    return formulas[: max(0, limit)]


def _runtime_signals(workspace: Path) -> dict[str, float]:
    perf = PerformanceGovernor(workspace).report()
    tile = TileMindFS(workspace).report()
    ram = OmegaRAM(workspace).report()
    corpus = corpus_deep_index_report(workspace)
    last_index = corpus.get("last_index") or {}
    formulas = perf.get("formulas", {})
    tile_ratio = float(tile.get("compression_ratio", 1.0) or 1.0)
    warm_entries = float(ram.get("metrics", {}).get("warm_entries", 0) or 0)
    hot_entries = float(ram.get("metrics", {}).get("hot_entries", 0) or 0)
    storage_gain = _clamp(1.0 - tile_ratio, 0.0, 0.92)
    memory_heat = _clamp((hot_entries + 0.5 * warm_entries) / 128.0)
    formula_count = float(last_index.get("formula_count", 0) or 0)
    corpus_scale = _clamp(math.log10(max(formula_count, 1.0)) / 7.0)
    return {
        "stability": float(formulas.get("stability_index", 0.5) or 0.5),
        "throughput": float(formulas.get("throughput_index", 0.5) or 0.5),
        "memory_guard": float(formulas.get("memory_guard", 0.5) or 0.5),
        "thermal": float(formulas.get("thermal_envelope", 0.5) or 0.5),
        "storage_gain": storage_gain,
        "memory_heat": memory_heat,
        "corpus_coverage": float(last_index.get("coverage_ratio", 0.0) or 0.0),
        "corpus_scale": corpus_scale,
    }


def score_scientific_formula(formula: dict[str, Any], signals: dict[str, float]) -> dict[str, Any]:
    sector = str(formula["sector"])
    potential = float(formula["potential"])
    safety = float(formula["safety"])
    stability = signals["stability"]
    thermal = signals["thermal"]
    throughput = signals["throughput"]
    memory_guard = signals["memory_guard"]
    storage_gain = signals["storage_gain"]
    memory_heat = signals["memory_heat"]
    corpus_boost = 0.08 * signals.get("corpus_coverage", 0.0) * signals.get("corpus_scale", 0.0)
    sector_fit = {
        "storage": 0.45 + 0.55 * storage_gain + corpus_boost,
        "memory": 0.35 + 0.35 * memory_guard + 0.30 * memory_heat + corpus_boost,
        "cpu": 0.30 + 0.35 * throughput + 0.35 * thermal + corpus_boost,
        "scheduler": 0.30 + 0.40 * stability + 0.30 * throughput + corpus_boost,
        "security": 0.35 + 0.65 * stability + corpus_boost,
        "gpu": 0.25 + 0.35 * thermal + 0.40 * throughput,
        "network": 0.55 + 0.45 * stability + corpus_boost,
        "ai-dev": 0.30 + 0.45 * stability + 0.25 * throughput + corpus_boost,
        "ui": 0.45 + 0.55 * stability + corpus_boost,
        "simulation": 0.25 + 0.50 * stability + 0.25 * memory_guard + corpus_boost,
    }.get(sector, 0.5)
    sector_fit = _clamp(sector_fit)
    risk_penalty = 1.0 - max(0.0, 0.55 - stability) * 0.8
    activation = _clamp(potential * sector_fit * safety * risk_penalty)
    return {
        **formula,
        "activation_score": round(activation, 4),
        "recommended": activation >= 0.48 and safety >= 0.76,
        "runtime_notes": {
            "sector_fit": round(sector_fit, 4),
            "risk_penalty": round(risk_penalty, 4),
            "storage_effective_capacity_hint": round(1.0 + 3.0 * storage_gain * safety, 4)
            if sector == "storage"
            else None,
            "safe_concurrency_hint": max(1, math.floor(1 + 15 * stability * thermal)) if sector in {"cpu", "scheduler", "ai-dev"} else None,
        },
    }


def scientific_formula_plan(workspace: Path, target: str | None = None, limit: int = 18, queue: bool = False) -> dict[str, Any]:
    ensure_workspace(workspace)
    signals = _runtime_signals(workspace)
    catalog = scientific_formula_catalog(target=target, limit=240)
    scored = [score_scientific_formula(item, signals) for item in catalog]
    selected = sorted(scored, key=lambda item: item["activation_score"], reverse=True)[: max(1, limit)]
    report_path = _write_formula_report(workspace, selected, signals)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"scientific_formula::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="scientific_formula_forge",
    )
    queued: list[dict[str, Any]] = []
    if queue:
        for item in selected[: min(6, len(selected))]:
            queued.append(
                submit_workload(
                    workspace,
                    "research" if item["sector"] in {"storage", "security", "simulation"} else "code",
                    f"Apply formula {item['id']}",
                    f"Prototype the formula {item['equation']} for {item['target']} with guard: {item['safety_guard']}",
                    context=f"activation={item['activation_score']} sector={item['sector']}",
                )
            )
    state = _load_state(workspace)
    state["last_plan"] = {
        "ts": utc_now(),
        "target": target or "all",
        "selected_count": len(selected),
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }
    state["metrics"]["plans"] = int(state["metrics"].get("plans", 0)) + 1
    state["metrics"]["queued"] = int(state["metrics"].get("queued", 0)) + len(queued)
    _save_state(workspace, state)
    append_event(workspace, "scientific_formula_plan", {"selected_count": len(selected), "target": target or "all"})
    return {
        "generated_at": utc_now(),
        "signals": signals,
        "selected": selected,
        "queued": queued,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }


def scientific_formula_report(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    state = _load_state(workspace)
    corpus = corpus_deep_index_report(workspace)
    return {
        "catalog_total": len(scientific_formula_catalog(limit=10000)),
        "target_count": len(FORMULA_TARGETS),
        "variant_count": len(FORMULA_VARIANTS),
        "safe_default": True,
        "local_only": True,
        "corpus_index": corpus.get("last_index"),
        "metrics": state.get("metrics", {}),
        "last_plan": state.get("last_plan"),
    }


def _state_path(workspace: Path) -> Path:
    return workspace / "state" / "scientific_formula_forge.json"


def _load_state(workspace: Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        return {"metrics": {"plans": 0, "queued": 0}, "last_plan": None}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    _state_path(workspace).write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def _write_formula_report(workspace: Path, selected: list[dict[str, Any]], signals: dict[str, float]) -> Path:
    root = workspace / "scientific_formulas"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"SCIENTIFIC_FORMULAS_{len(list(root.glob('SCIENTIFIC_FORMULAS_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Scientific Formula Forge",
        "",
        f"- Generated at: {utc_now()}",
        f"- Stability: {signals['stability']:.4f}",
        f"- Thermal envelope: {signals['thermal']:.4f}",
        f"- Storage gain signal: {signals['storage_gain']:.4f}",
        "",
        "## Rule",
        "Every formula is reversible, bounded and must pass doctor/tests before promotion.",
        "",
        "## Selected Formulas",
    ]
    for item in selected:
        lines.extend(
            [
                f"### {item['id']}",
                f"- Target: {item['target']}",
                f"- Sector: {item['sector']}",
                f"- Equation: `{item['equation']}`",
                f"- Activation: {item['activation_score']}",
                f"- Guard: {item['safety_guard']}",
                f"- Effect: {item['expected_effect']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
