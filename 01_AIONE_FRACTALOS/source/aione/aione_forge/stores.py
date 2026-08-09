from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from .io import append_jsonl, utc_ts, write_json
from .operators import MemoryContextOperator


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append(
                {
                    "_corrupt": True,
                    "raw": line,
                }
            )
    return records


class JsonlStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: dict[str, Any]) -> None:
        append_jsonl(
            self.path,
            {
                "stored_at": utc_ts(),
                "record": record,
            },
        )

    def append_unique(self, record: dict[str, Any]) -> bool:
        identity = record_identity(record)
        if identity in self.identities():
            return False
        self.append(record)
        return True

    def all(self) -> list[dict[str, Any]]:
        return read_jsonl(self.path)

    def identities(self) -> set[str]:
        return {record_identity(record) for record in self.records()}

    def search(self, query: str) -> list[dict[str, Any]]:
        lowered = query.lower()
        results = []
        for record in self.unique_records():
            text = json.dumps(record, ensure_ascii=False).lower()
            if lowered in text:
                results.append({"record": record})
        return results

    def records(self) -> list[dict[str, Any]]:
        return [item.get("record", item) for item in self.all()]

    def unique_records(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for record in self.records():
            identity = record_identity(record)
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(record)
        return unique


class KnowledgeStore(JsonlStore):
    def query(
        self,
        *,
        text: str | None = None,
        tags: list[str] | None = None,
        verification_status: str | None = None,
        relation: str | None = None,
        source_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for record in self.unique_records():
            if text and text.lower() not in json.dumps(record, ensure_ascii=False).lower():
                continue
            if tags and not set(tags).issubset(set(record.get("tags", []))):
                continue
            if verification_status and record.get("verification_status") != verification_status:
                continue
            if relation and relation not in record.get("relations", []):
                continue
            if source_ref and source_ref not in record.get("source_refs", []):
                continue
            results.append({"record": record, "score": relevance_score(record, text or " ".join(tags or []))})
        return results


class ProofStore(JsonlStore):
    def query(
        self,
        *,
        target_artifact: str | None = None,
        status: str | None = None,
        source: str | None = None,
        claim_text: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for record in self.unique_records():
            if target_artifact and record.get("target_artifact") != target_artifact:
                continue
            if status and record.get("status") != status:
                continue
            if source and source not in record.get("sources", []):
                continue
            if claim_text and claim_text.lower() not in " ".join(record.get("claims", [])).lower():
                continue
            results.append({"record": record, "score": relevance_score(record, claim_text or target_artifact or "")})
        return results


class PatchLedgerStore(JsonlStore):
    def query(
        self,
        *,
        mission_id: str | None = None,
        status: str | None = None,
        file_touched: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for record in self.unique_records():
            if mission_id and record.get("mission_id") != mission_id:
                continue
            if status and record.get("status") != status:
                continue
            if file_touched and file_touched not in record.get("files_touched", []):
                continue
            results.append({"record": record, "score": relevance_score(record, file_touched or mission_id or "")})
        return results


class StoreBundle:
    def __init__(self, root: Path):
        self.root = root
        self.knowledge = KnowledgeStore(root / "knowledge_tiles.jsonl")
        self.proofs = ProofStore(root / "proof_capsules.jsonl")
        self.patches = PatchLedgerStore(root / "patch_ledgers.jsonl")

    def persist_kernel_result(self, kernel_result: dict[str, Any]) -> dict[str, Any]:
        inserted = {
            "knowledge_tile": self.knowledge.append_unique(kernel_result["knowledge_tile"]),
            "proof_capsule": self.proofs.append_unique(kernel_result["proof_capsule"]),
            "patch_ledger": self.patches.append_unique(kernel_result["patch_ledger"]),
        }
        status = self.status()
        status["inserted"] = inserted
        write_json(self.root / "store_index.json", status)
        return status

    def status(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "knowledge_tiles": len(self.knowledge.unique_records()),
            "proof_capsules": len(self.proofs.unique_records()),
            "patch_ledgers": len(self.patches.unique_records()),
            "raw_knowledge_tiles": len(self.knowledge.all()),
            "raw_proof_capsules": len(self.proofs.all()),
            "raw_patch_ledgers": len(self.patches.all()),
            "updated_at": utc_ts(),
        }

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        return self.knowledge.search(query)

    def query_knowledge(
        self,
        *,
        text: str | None = None,
        tags: list[str] | None = None,
        verification_status: str | None = None,
        relation: str | None = None,
        source_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.knowledge.query(
            text=text,
            tags=tags,
            verification_status=verification_status,
            relation=relation,
            source_ref=source_ref,
        )

    def query_proofs(
        self,
        *,
        target_artifact: str | None = None,
        status: str | None = None,
        source: str | None = None,
        claim_text: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.proofs.query(
            target_artifact=target_artifact,
            status=status,
            source=source,
            claim_text=claim_text,
        )

    def query_patches(
        self,
        *,
        mission_id: str | None = None,
        status: str | None = None,
        file_touched: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.patches.query(
            mission_id=mission_id,
            status=status,
            file_touched=file_touched,
        )

    def relation_graph(self) -> dict[str, list[str]]:
        return MemoryContextOperator().build_relation_graph(self.knowledge.unique_records())

    def weighted_relation_graph(self) -> dict[str, list[dict[str, Any]]]:
        return MemoryContextOperator().build_weighted_relation_graph(self.knowledge.unique_records())

    def memory_state_counts(self) -> dict[str, int]:
        return MemoryContextOperator().state_counts(self.knowledge.unique_records())

    def fusion_candidates(self) -> list[dict[str, Any]]:
        return MemoryContextOperator().fusion_candidates(self.knowledge.unique_records())

    def synthesize_context(self, query: str, limit: int = 5) -> dict[str, Any]:
        return MemoryContextOperator().synthesize_context(self.knowledge.unique_records(), query, limit)


def render_store_status(status: dict[str, Any], search_results: list[dict[str, Any]]) -> str:
    lines = [
        "# Store Status",
        "",
        f"Root: {status['root']}",
        f"Knowledge tiles: {status['knowledge_tiles']}",
        f"Proof capsules: {status['proof_capsules']}",
        f"Patch ledgers: {status['patch_ledgers']}",
        f"Raw knowledge tiles: {status['raw_knowledge_tiles']}",
        f"Raw proof capsules: {status['raw_proof_capsules']}",
        f"Raw patch ledgers: {status['raw_patch_ledgers']}",
        f"Updated at: {status['updated_at']}",
        "",
        "## Search sample",
        "",
        f"Results for `kernel`: {len(search_results)}",
    ]
    for item in search_results[:5]:
        record = item.get("record", {})
        score = item.get("score")
        suffix = f" score={score}" if score is not None else ""
        lines.append(f"- {record.get('id', 'unknown')} - {record.get('title', record.get('change_summary', 'record'))}{suffix}")
    return "\n".join(lines)


def render_memory_query_status(query_report: dict[str, Any]) -> str:
    lines = [
        "# Memory Query Status",
        "",
        "## Knowledge",
        "",
        f"Kernel-tagged tiles: {query_report['knowledge_by_tag']}",
        f"Partial tiles: {query_report['knowledge_partial']}",
        "",
        "## Proofs",
        "",
        f"Kernel artifact proofs: {query_report['proofs_for_kernel']}",
        f"Passed proofs: {query_report['proofs_passed']}",
        "",
        "## Patches",
        "",
        f"Applied patches: {query_report['patches_applied']}",
        f"Kernel file patches: {query_report['patches_for_kernel_file']}",
        f"Relation nodes: {query_report['relation_nodes']}",
        f"Weighted relation nodes: {query_report['weighted_relation_nodes']}",
        f"Context items: {query_report['context_items']}",
        f"Fusion candidates: {query_report['fusion_candidates']}",
        "",
        "## Memory states",
        "",
        f"Active: {query_report['memory_states'].get('active', 0)}",
        f"Stale: {query_report['memory_states'].get('stale', 0)}",
        f"Low value: {query_report['memory_states'].get('low_value', 0)}",
        f"Obsolete: {query_report['memory_states'].get('obsolete', 0)}",
        "",
        "## TruthGate",
        "",
        f"Confirmations: {query_report['truth_gate']['confirmations']}",
        f"Contradictions: {query_report['truth_gate']['contradictions']}",
        f"Status: {query_report['truth_gate']['status']}",
    ]
    return "\n".join(lines)


def record_identity(record: dict[str, Any]) -> str:
    if "change_summary" in record and "files_touched" in record:
        raw_patch = json.dumps(
            {
                "change_summary": record.get("change_summary"),
                "files_touched": record.get("files_touched"),
                "reason": record.get("reason"),
                "rollback_plan": record.get("rollback_plan"),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return sha256(raw_patch.encode("utf-8")).hexdigest()
    for key in ["hash", "id"]:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def relevance_score(record: dict[str, Any], query: str) -> float:
    return MemoryContextOperator().relevance_score(record, query)
