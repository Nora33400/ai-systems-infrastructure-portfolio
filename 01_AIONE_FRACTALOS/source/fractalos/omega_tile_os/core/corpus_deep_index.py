from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .events import append_event
from .ram_memory import OmegaRAM
from .research_fusion import DOMAIN_TO_OS_AXIS
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


DOMAIN_TO_SECTOR = {
    "energy_perf": "thermal-energy",
    "context_routing": "routing-intent",
    "scheduler_control": "cpu-scheduler",
    "risk_security": "security-proof",
    "proof_validation": "security-proof",
    "coherence_invariants": "state-coherence",
    "cube_compression_gpu": "storage-density",
    "tableau_state_indexing": "memory-indexing",
    "agent_orchestration": "agent-foundry",
    "fractal_complexity": "system-evolution",
    "seed_state_dynamics": "system-evolution",
    "dynamic_static_reconciliation": "runtime-bridge",
}


def _state_path(workspace: Path) -> Path:
    return workspace / "state" / "corpus_deep_index.json"


def _load_state(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    path = _state_path(workspace)
    if not path.exists():
        return {"metrics": {"indexes": 0}, "last_index": None}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    _state_path(workspace).write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def _formula_files(corpus_root: Path) -> list[Path]:
    if not corpus_root.exists():
        return []
    return sorted(corpus_root.rglob("formula_*.txt"))


def _extension_counts(corpus_root: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if not corpus_root.exists():
        return {}
    for path in corpus_root.rglob("*"):
        if path.is_file():
            counts[path.suffix.lower() or "<none>"] += 1
    return dict(counts.most_common())


def _value_after_marker(line: str, marker: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith(marker):
        return None
    return stripped[len(marker) :].strip()


def _scan_formula_file(path: Path) -> dict[str, Any]:
    domain_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()
    equation_tokens: Counter[str] = Counter()
    formulas = 0
    equations = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("## FORMULA "):
                    formulas += 1
                    continue
                domain = _value_after_marker(stripped, "[domain]")
                if domain:
                    domain_counts[domain] += 1
                    continue
                module = _value_after_marker(stripped, "[module]")
                if module:
                    module_counts[module] += 1
                    continue
                if stripped.startswith("F1:"):
                    equations += 1
                    equation = stripped[3:].strip()
                    token = equation.split("=", 1)[0].strip()[:48] if equation else "unknown"
                    equation_tokens[token or "unknown"] += 1
    except OSError:
        return {
            "readable": False,
            "formulas": 0,
            "equations": 0,
            "domain_counts": {},
            "module_counts": {},
            "equation_tokens": {},
        }
    return {
        "readable": True,
        "formulas": formulas,
        "equations": equations,
        "domain_counts": dict(domain_counts),
        "module_counts": dict(module_counts),
        "equation_tokens": dict(equation_tokens),
    }


def build_corpus_deep_index(
    workspace: Path,
    corpus_root: Path,
    max_files: int | None = None,
) -> dict[str, Any]:
    ensure_workspace(workspace)
    files = _formula_files(corpus_root)
    total_files = len(files)
    selected_files = files[: max_files if max_files is not None else total_files]
    domain_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()
    equation_tokens: Counter[str] = Counter()
    sector_counts: Counter[str] = Counter()
    unreadable = 0
    formula_count = 0
    equation_count = 0
    byte_count = 0
    samples: list[str] = []

    for path in selected_files:
        try:
            byte_count += path.stat().st_size
        except OSError:
            pass
        result = _scan_formula_file(path)
        if not result["readable"]:
            unreadable += 1
            continue
        formula_count += int(result["formulas"])
        equation_count += int(result["equations"])
        domain_counts.update(result["domain_counts"])
        module_counts.update(result["module_counts"])
        equation_tokens.update(result["equation_tokens"])
        if len(samples) < 12:
            samples.append(str(path))

    for domain, count in domain_counts.items():
        sector_counts[DOMAIN_TO_SECTOR.get(domain, "unmapped")] += count

    ext_counts = _extension_counts(corpus_root)
    top_domains = dict(domain_counts.most_common(20))
    top_modules = dict(module_counts.most_common(20))
    top_equations = dict(equation_tokens.most_common(20))
    integration_axes = [
        {
            "domain": domain,
            "sector": DOMAIN_TO_SECTOR.get(domain, "unmapped"),
            "count": count,
            "os_axis": DOMAIN_TO_OS_AXIS.get(domain, "general FractalOS research lane"),
            "integration": _integration_hint(domain),
        }
        for domain, count in domain_counts.most_common(14)
    ]

    coverage = 0.0 if total_files == 0 else len(selected_files) / total_files
    index = {
        "generated_at": utc_now(),
        "corpus_root": str(corpus_root),
        "total_formula_files": total_files,
        "indexed_formula_files": len(selected_files),
        "coverage_ratio": round(coverage, 6),
        "indexed_bytes": byte_count,
        "formula_count": formula_count,
        "equation_count": equation_count,
        "unreadable_files": unreadable,
        "extension_counts": ext_counts,
        "top_domains": top_domains,
        "top_modules": top_modules,
        "top_equation_tokens": top_equations,
        "sector_counts": dict(sector_counts.most_common()),
        "integration_axes": integration_axes,
        "sampled_files": samples,
    }
    report_path = _write_report(workspace, index)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"corpus_deep_index::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="corpus_deep_index",
    )

    state = _load_state(workspace)
    state["last_index"] = {
        "ts": utc_now(),
        "corpus_root": str(corpus_root),
        "total_formula_files": total_files,
        "indexed_formula_files": len(selected_files),
        "coverage_ratio": round(coverage, 6),
        "formula_count": formula_count,
        "equation_count": equation_count,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }
    state.setdefault("metrics", {})["indexes"] = int(state.setdefault("metrics", {}).get("indexes", 0)) + 1
    _save_state(workspace, state)
    append_event(
        workspace,
        "corpus_deep_index_completed",
        {
            "indexed_formula_files": len(selected_files),
            "total_formula_files": total_files,
            "formula_count": formula_count,
        },
    )
    return {**index, "report_path": str(report_path), "tile_manifest": tile.get("manifest_id", "")}


def corpus_deep_index_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    return {
        "metrics": state.get("metrics", {}),
        "last_index": state.get("last_index"),
    }


def _integration_hint(domain: str) -> str:
    hints = {
        "cube_compression_gpu": "feed TileMindFS packing, storage-density formulas and GPU-safe compression lanes",
        "energy_perf": "feed thermal throughput formulas and safe concurrency recommendations",
        "scheduler_control": "feed regime scheduling, latency fields and worker routing",
        "proof_validation": "feed ProofState promotion, doctor gates and rollback contracts",
        "risk_security": "feed sandbox policy, attack simulation and zero-trust modules",
        "tableau_state_indexing": "feed OmegaRAM heat maps and semantic memory classes",
        "agent_orchestration": "feed Foundry worker lanes and autonomous dev pipelines",
        "coherence_invariants": "feed clean-growth scoring and mesh compaction",
    }
    return hints.get(domain, "feed research queues and formula program synthesis")


def _write_report(workspace: Path, index: dict[str, Any]) -> Path:
    root = workspace / "corpus_index"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"CORPUS_INDEX_{len(list(root.glob('CORPUS_INDEX_*.md'))) + 1:04d}.md"
    lines = [
        "# Fractal Formula Corpus Deep Index",
        "",
        f"- Generated at: {index['generated_at']}",
        f"- Corpus: {index['corpus_root']}",
        f"- Formula files: {index['indexed_formula_files']} / {index['total_formula_files']}",
        f"- Coverage: {index['coverage_ratio']}",
        f"- Indexed bytes: {index['indexed_bytes']}",
        f"- Formula blocks: {index['formula_count']}",
        f"- F1 equations: {index['equation_count']}",
        "",
        "## Extension Counts",
    ]
    for ext, count in index["extension_counts"].items():
        lines.append(f"- {ext}: {count}")
    lines.extend(["", "## Top Domains"])
    for domain, count in index["top_domains"].items():
        lines.append(f"- {domain}: {count}")
    lines.extend(["", "## Sector Map"])
    for sector, count in index["sector_counts"].items():
        lines.append(f"- {sector}: {count}")
    lines.extend(["", "## Integration Axes"])
    for axis in index["integration_axes"]:
        lines.append(f"- {axis['domain']} -> {axis['sector']} :: {axis['integration']}")
    lines.extend(["", "## Top Modules"])
    for module, count in index["top_modules"].items():
        lines.append(f"- {module}: {count}")
    lines.extend(["", "## Top Equation Tokens"])
    for token, count in index["top_equation_tokens"].items():
        lines.append(f"- `{token}`: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
