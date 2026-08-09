from __future__ import annotations

import base64
import json
import re
import zlib
from collections import Counter
from pathlib import Path

from .autonomy_runtime import submit_workload
from .events import append_event
from .ram_memory import OmegaRAM
from .state import load_research_state, save_research_state, utc_now
from ..tilemindfs.store import TileMindFS


DOMAIN_TO_OS_AXIS = {
    "energy_perf": "performance governor, safe benchmark calibration, thermal-aware scheduling",
    "context_routing": "action router, worker mode selection, cockpit next-action prediction",
    "scheduler_control": "heterogeneous scheduler and future-fabric wave planning",
    "risk_security": "guardrails, ISO validation gates, non-destructive execution policy",
    "proof_validation": "review loops, confidence scoring, reproducible evidence trails",
    "coherence_invariants": "state consistency, mesh compaction, memory integrity checks",
    "cube_compression_gpu": "TileMindFS packing, GPU-friendly compression, cache capsules",
    "tableau_state_indexing": "OmegaRAM indexing, timeline cards, search surfaces",
    "agent_orchestration": "Codex worker graph, autonomy lanes, mission bridges",
    "fractal_complexity": "meta-prioritization and ecosystem growth balancing",
    "seed_state_dynamics": "safe-mode transitions and bounded self-evolution",
    "dynamic_static_reconciliation": "bridge between generated plans and executable runtime actions",
}


def _decode_pdf_literal(value: bytes) -> str:
    out = bytearray()
    index = 0
    while index < len(value):
        char = value[index]
        if char == 92 and index + 1 < len(value):
            nxt = value[index + 1]
            if 48 <= nxt <= 55:
                octal = bytes([nxt])
                cursor = index + 2
                while cursor < len(value) and len(octal) < 3 and 48 <= value[cursor] <= 55:
                    octal += bytes([value[cursor]])
                    cursor += 1
                out.append(int(octal, 8))
                index = cursor
                continue
            escapes = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
            out.append(escapes.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return out.decode("latin-1", errors="replace")


def extract_pdf_text(path: Path, max_chars: int = 12000) -> str:
    data = path.read_bytes()
    chunks: list[str] = []
    cursor = 0
    while True:
        start = data.find(b"stream\n", cursor)
        if start < 0:
            break
        end = data.find(b"endstream", start)
        if end < 0:
            break
        raw_stream = data[start + len(b"stream\n") : end].strip()
        cursor = end + len(b"endstream")
        try:
            decoded = zlib.decompress(base64.a85decode(b"<~" + raw_stream, adobe=True))
        except (ValueError, zlib.error):
            continue
        for literal in re.findall(rb"\((?:\\.|[^\\)])*\)\s*Tj", decoded):
            chunks.append(_decode_pdf_literal(literal[1 : literal.rfind(b")")]))
        for array in re.findall(rb"\[(.*?)\]\s*TJ", decoded, re.S):
            for literal in re.findall(rb"\((?:\\.|[^\\)])*\)", array):
                chunks.append(_decode_pdf_literal(literal[1:-1]))
        if sum(len(item) for item in chunks) >= max_chars:
            break
    return " ".join(part.strip() for part in chunks if part.strip())[:max_chars]


def _formula_files(corpus_root: Path, limit: int) -> list[Path]:
    files: list[Path] = []
    if not corpus_root.exists():
        return files
    for path in sorted(corpus_root.rglob("formula_*.txt")):
        files.append(path)
        if len(files) >= limit:
            break
    return files


def _parse_formula_file(path: Path, max_formulas_per_file: int = 16) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n## FORMULA ", text)
    records: list[dict[str, object]] = []
    for block in blocks[1 : max_formulas_per_file + 1]:
        module = re.search(r"\[module\]\s*(.+)", block)
        domain = re.search(r"\[domain\]\s*(.+)", block)
        note = re.search(r"\[note\]\s*(.+)", block)
        f1 = re.search(r"F1:\s*(.+)", block)
        params = re.search(r"params\[(.+?)\]", block)
        records.append(
            {
                "file": str(path),
                "module": module.group(1).strip() if module else "unknown",
                "domain": domain.group(1).strip() if domain else "unknown",
                "note": note.group(1).strip() if note else "",
                "f1": f1.group(1).strip() if f1 else "",
                "params": params.group(1).strip() if params else "",
            }
        )
    return records


def scan_formula_corpus(corpus_root: Path, max_files: int = 12) -> dict[str, object]:
    records: list[dict[str, object]] = []
    sampled_files = _formula_files(corpus_root, max_files)
    for path in sampled_files:
        records.extend(_parse_formula_file(path))
    domain_counts = Counter(str(item["domain"]) for item in records)
    module_counts = Counter(str(item["module"]) for item in records)
    return {
        "corpus_root": str(corpus_root),
        "sampled_files": [str(path) for path in sampled_files],
        "formula_count": len(records),
        "domain_counts": dict(domain_counts),
        "module_counts": dict(module_counts.most_common(12)),
        "records": records[:80],
    }


def ingest_pdf_notes(paths: list[Path]) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(path.resolve())
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        text = extract_pdf_text(path)
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{3,}", text)
        keywords = Counter(token.lower() for token in tokens)
        docs.append(
            {
                "path": resolved,
                "name": path.name,
                "chars": len(text),
                "preview": text[:900],
                "keywords": [item for item, _ in keywords.most_common(16)],
            }
        )
    return docs


def _innovation_cards(corpus: dict[str, object], docs: list[dict[str, object]]) -> list[dict[str, object]]:
    domain_counts = dict(corpus.get("domain_counts", {}))
    cards: list[dict[str, object]] = []
    for domain, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True):
        axis = DOMAIN_TO_OS_AXIS.get(domain, "general research lane")
        cards.append(
            {
                "domain": domain,
                "formula_count": count,
                "os_axis": axis,
                "implementation": f"Convert {domain} formulas into a bounded FractalOS heuristic for {axis}.",
                "safety": "Require simulation, reversible state writes, and performance governor approval before execution.",
            }
        )
    if docs:
        cards.insert(
            0,
            {
                "domain": "pdf_research_notes",
                "formula_count": len(docs),
                "os_axis": "research desk, autonomy-lab, proof/evidence memory",
                "implementation": "Fuse PDF research programs into autonomy workloads with explicit conjecture/proof/test separation.",
                "safety": "Treat advanced math notes as hypotheses until independently verified.",
            },
        )
    return cards[:12]


def _render_report(corpus: dict[str, object], docs: list[dict[str, object]], cards: list[dict[str, object]]) -> str:
    lines = [
        "# FractalOS Research Fusion",
        "",
        f"- Generated at: {utc_now()}",
        f"- PDF documents ingested: {len(docs)}",
        f"- Formula files sampled: {len(corpus.get('sampled_files', []))}",
        f"- Formula records parsed: {corpus.get('formula_count', 0)}",
        "",
        "## PDF Signals",
    ]
    if not docs:
        lines.append("- none")
    for doc in docs:
        lines.append(f"- {doc['name']} :: chars={doc['chars']} :: keywords={', '.join(doc['keywords'][:8])}")
    lines.extend(["", "## Formula Domain Balance"])
    for domain, count in sorted(dict(corpus.get("domain_counts", {})).items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {domain}: {count}")
    lines.extend(["", "## Innovation Cards"])
    for card in cards:
        lines.append(f"- [{card['domain']}] axis={card['os_axis']}")
        lines.append(f"  implementation={card['implementation']}")
        lines.append(f"  safety={card['safety']}")
    lines.extend(["", "## Selected Formula Records"])
    for record in corpus.get("records", [])[:16]:
        lines.append(f"- {record['domain']} / {record['module']} :: {record['note'] or record['f1']}")
    return "\n".join(lines) + "\n"


def run_research_fusion(
    workspace: Path,
    corpus_root: Path,
    pdf_paths: list[Path],
    max_formula_files: int = 12,
    queue_followups: bool = False,
) -> dict[str, object]:
    corpus = scan_formula_corpus(corpus_root, max_files=max_formula_files)
    docs = ingest_pdf_notes(pdf_paths)
    cards = _innovation_cards(corpus, docs)
    report_text = _render_report(corpus, docs, cards)

    root = workspace / "research_fusion"
    root.mkdir(parents=True, exist_ok=True)
    research_state = load_research_state(workspace)
    run_id = f"fusion_{int(research_state.get('metrics', {}).get('runs', 0)) + 1:04d}"
    report_path = root / f"{run_id}.md"
    report_path.write_text(report_text, encoding="utf-8")

    tile_archive = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"research_fusion::{run_id}",
        text=report_text,
        source="research_fusion",
    )

    queued: list[dict[str, object]] = []
    if queue_followups:
        for card in cards[:4]:
            queued.append(
                submit_workload(
                    workspace,
                    "research",
                    f"Research Fusion :: {card['domain']}",
                    str(card["implementation"]),
                    context=str(card["safety"]),
                )
            )

    run = {
        "id": run_id,
        "ts": utc_now(),
        "report_path": str(report_path),
        "tile_manifest": tile_archive.get("manifest_id", ""),
        "pdfs_ingested": len(docs),
        "formula_files_sampled": len(corpus.get("sampled_files", [])),
        "formula_count": corpus.get("formula_count", 0),
        "top_domains": dict(list(dict(corpus.get("domain_counts", {})).items())[:8]),
        "queued_followups": [item["id"] for item in queued],
    }
    research_state.setdefault("runs", []).append(run)
    research_state["runs"] = research_state["runs"][-50:]
    metrics = research_state.setdefault("metrics", {})
    metrics["runs"] = int(metrics.get("runs", 0)) + 1
    metrics["pdfs_ingested"] = int(metrics.get("pdfs_ingested", 0)) + len(docs)
    metrics["formula_files_sampled"] = int(metrics.get("formula_files_sampled", 0)) + len(corpus.get("sampled_files", []))
    metrics["followups_queued"] = int(metrics.get("followups_queued", 0)) + len(queued)
    research_state["last_run"] = run
    save_research_state(workspace, research_state)
    append_event(workspace, "research_fusion_completed", {"run_id": run_id, "pdfs": len(docs), "formula_count": corpus.get("formula_count", 0)})
    return {
        "run": run,
        "report_path": str(report_path),
        "cards": cards,
        "docs": docs,
        "corpus": {key: value for key, value in corpus.items() if key != "records"},
        "queued": queued,
    }


def research_fusion_report(workspace: Path) -> dict[str, object]:
    state = load_research_state(workspace)
    return {
        "metrics": state.get("metrics", {}),
        "last_run": state.get("last_run"),
        "recent_runs": state.get("runs", [])[-8:],
    }
