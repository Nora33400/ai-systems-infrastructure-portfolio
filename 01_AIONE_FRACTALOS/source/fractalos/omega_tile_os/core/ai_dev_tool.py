from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .autonomy_runtime import submit_workload
from .events import append_event
from .formula_programs import formula_runtime_advice
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import utc_now
from ..tilemindfs.store import TileMindFS


CATEGORIES = [
    ("code-intel", "Comprendre le code", "code"),
    ("spec", "Transformer les idees en specifications", "research"),
    ("architecture", "Architecture et modularite", "code"),
    ("testing", "Tests et verification", "code"),
    ("debug", "Debug et observation", "automation"),
    ("refactor", "Refactorisation sure", "code"),
    ("performance", "Performance stable", "ecosystem"),
    ("security", "Securite et garde-fous", "automation"),
    ("automation", "Automatisation locale", "automation"),
    ("docs", "Documentation vivante", "research"),
    ("review", "Review et qualite", "code"),
    ("release", "Packaging et livraison", "automation"),
    ("research", "Recherche assistee", "research"),
    ("memory", "Memoire projet", "ecosystem"),
    ("ui", "Interfaces dev", "code"),
    ("data", "Donnees et schemas", "code"),
    ("ops", "Operations locales", "automation"),
    ("agent", "Workers IA", "automation"),
    ("learning", "Apprentissage continu", "research"),
    ("governance", "Decision et priorisation", "ecosystem"),
]

IMPROVEMENT_THEMES = [
    ("Map", "cartographier automatiquement les modules, dependances et zones de risque"),
    ("Explain", "expliquer chaque composant avec objectifs, entrees, sorties et invariants"),
    ("Plan", "generer un plan d'implementation reversible et testable"),
    ("Patch", "proposer des patchs atomiques avec justification et impact attendu"),
    ("Test", "creer des tests unitaires et d'integration adaptes au changement"),
    ("Probe", "lancer des diagnostics locaux non destructifs avant execution"),
    ("Trace", "ajouter des traces utiles sans bruit excessif"),
    ("Score", "scorer priorite, risque, complexite et valeur utilisateur"),
    ("Compress", "resumer gros contextes en capsules reutilisables"),
    ("Guard", "bloquer les actions destructives ou thermiquement dangereuses"),
]

CATEGORY_WEIGHTS = {
    "code-intel": 0.74,
    "spec": 0.66,
    "architecture": 0.78,
    "testing": 0.88,
    "debug": 0.84,
    "refactor": 0.76,
    "performance": 0.82,
    "security": 0.9,
    "automation": 0.78,
    "docs": 0.58,
    "review": 0.86,
    "release": 0.62,
    "research": 0.64,
    "memory": 0.72,
    "ui": 0.56,
    "data": 0.7,
    "ops": 0.74,
    "agent": 0.8,
    "learning": 0.62,
    "governance": 0.82,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _build_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    index = 1
    for category_id, category_label, lane in CATEGORIES:
        for theme_name, theme_text in IMPROVEMENT_THEMES[:5]:
            local_value = CATEGORY_WEIGHTS.get(category_id, 0.65)
            complexity = 0.24 + (index % 7) * 0.07
            risk = 0.05 + (index % 5) * 0.035
            catalog.append(
                {
                    "id": f"aid-{index:03d}",
                    "category": category_id,
                    "category_label": category_label,
                    "lane": lane,
                    "title": f"{theme_name} :: {category_label}",
                    "description": f"Utiliser l'IA locale pour {theme_text}.",
                    "local_only": True,
                    "safe_default": True,
                    "complexity": round(_clamp(complexity), 3),
                    "risk": round(_clamp(risk), 3),
                    "value": round(local_value, 3),
                    "outputs": ["markdown-plan", "json-score", "autonomy-workload"],
                }
            )
            index += 1
    return catalog[:100]


AI_DEV_CATALOG = _build_catalog()


def _context_signals(workspace: Path) -> dict[str, Any]:
    from .doctor import run_doctor

    doctor = run_doctor(workspace)
    perf = PerformanceGovernor(workspace).report()
    advice = formula_runtime_advice(workspace, perf_report=perf, router_signals={})
    return {
        "doctor_status": doctor["status"],
        "doctor_counts": doctor["counts"],
        "risk_level": perf["recommendations"].get("risk_level", "unknown"),
        "stability_index": float(perf["formulas"].get("stability_index", 0.0)),
        "formula_biases": advice.get("action_biases", {}),
        "protective_program_count": advice.get("protective_program_count", 0),
    }


def score_improvement(item: dict[str, Any], signals: dict[str, Any]) -> float:
    severity = _clamp(0.2 + 0.18 * int(signals.get("doctor_counts", {}).get("warn", 0)) + 0.35 * int(signals.get("doctor_counts", {}).get("fail", 0)))
    stability = _clamp(float(signals.get("stability_index", 0.5)))
    value = float(item.get("value", 0.5))
    risk = float(item.get("risk", 0.2))
    complexity = float(item.get("complexity", 0.4))
    risk_level = str(signals.get("risk_level", "unknown"))
    protective_boost = 0.12 if risk_level in {"elevated", "critical"} and item.get("category") in {"debug", "performance", "security", "testing"} else 0.0
    score = (
        0.34 * value
        + 0.24 * (1.0 - risk)
        + 0.16 * (1.0 - complexity)
        + 0.14 * severity
        + 0.12 * stability
        + protective_boost
    )
    return round(_clamp(score), 4)


def ai_dev_catalog(category: str | None = None, limit: int = 100) -> dict[str, Any]:
    items = [dict(item) for item in AI_DEV_CATALOG]
    if category:
        items = [item for item in items if item["category"] == category]
    return {
        "count": len(items[:limit]),
        "total_catalog": len(AI_DEV_CATALOG),
        "categories": [item[0] for item in CATEGORIES],
        "items": items[:limit],
    }


def ai_dev_report(workspace: Path) -> dict[str, Any]:
    root = workspace / "ai_dev_tool"
    reports = sorted(root.glob("AI_DEV_PLAN_*.md")) if root.exists() else []
    latest = reports[-1] if reports else None
    category_counts: dict[str, int] = {}
    for item in AI_DEV_CATALOG:
        category = str(item["category"])
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "catalog_total": len(AI_DEV_CATALOG),
        "category_count": len(category_counts),
        "category_counts": category_counts,
        "report_count": len(reports),
        "latest_report": str(latest) if latest else None,
        "local_only": all(bool(item.get("local_only")) for item in AI_DEV_CATALOG),
        "safe_default": all(bool(item.get("safe_default")) for item in AI_DEV_CATALOG),
        "top_categories": sorted(category_counts)[:8],
    }


def ai_dev_plan(workspace: Path, focus: str = "all", limit: int = 12, queue: bool = False) -> dict[str, Any]:
    signals = _context_signals(workspace)
    items = [dict(item) for item in AI_DEV_CATALOG]
    if focus != "all":
        items = [item for item in items if item["category"] == focus or item["lane"] == focus]
    for item in items:
        item["priority_score"] = score_improvement(item, signals)
        item["priority_formula"] = "0.34*value + 0.24*(1-risk) + 0.16*(1-complexity) + 0.14*doctor_severity + 0.12*stability + protective_boost"
    selected = sorted(items, key=lambda item: float(item["priority_score"]), reverse=True)[: max(1, limit)]
    report_path = _write_ai_dev_report(workspace, selected, signals, focus)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"ai_dev_tool::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="ai_dev_tool",
    )
    queued: list[dict[str, Any]] = []
    if queue:
        for item in selected[: min(5, len(selected))]:
            queued.append(
                submit_workload(
                    workspace,
                    str(item["lane"]),
                    f"AI Dev Upgrade :: {item['title']}",
                    str(item["description"]),
                    context=f"priority_score={item['priority_score']} category={item['category']} formula={item['priority_formula']}",
                )
            )
    append_event(workspace, "ai_dev_plan_created", {"focus": focus, "selected": len(selected), "queued": len(queued)})
    return {
        "generated_at": utc_now(),
        "focus": focus,
        "signals": signals,
        "selected_count": len(selected),
        "selected": selected,
        "queued": queued,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }


def _write_ai_dev_report(workspace: Path, selected: list[dict[str, Any]], signals: dict[str, Any], focus: str) -> Path:
    root = workspace / "ai_dev_tool"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"AI_DEV_PLAN_{len(list(root.glob('AI_DEV_PLAN_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS AI Dev Tool",
        "",
        f"- Generated at: {utc_now()}",
        f"- Focus: {focus}",
        f"- Doctor status: {signals.get('doctor_status')}",
        f"- Risk level: {signals.get('risk_level')}",
        f"- Stability: {signals.get('stability_index')}",
        "",
        "## Top Improvements",
    ]
    for item in selected:
        lines.append(
            f"- {item['id']} score={item['priority_score']} lane={item['lane']} category={item['category']} :: {item['title']}"
        )
        lines.append(f"  {item['description']}")
    lines.extend(
        [
            "",
            "## Formula",
            "priority = 0.34*value + 0.24*(1-risk) + 0.16*(1-complexity) + 0.14*doctor_severity + 0.12*stability + protective_boost",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
