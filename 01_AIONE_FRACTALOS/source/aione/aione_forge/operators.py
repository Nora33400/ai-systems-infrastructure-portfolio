from __future__ import annotations

from hashlib import sha256
from typing import Any
from unicodedata import normalize

from .io import utc_ts
from .research_catalog import NVIDIA_MODEL_ROLES


def _role_map() -> dict[str, dict[str, Any]]:
    return {role["role"]: role for role in NVIDIA_MODEL_ROLES}


class RoutingOperator:
    def route(self, mission: dict[str, Any], message: dict[str, Any] | None = None) -> dict[str, Any]:
        role = self._select_role(mission, message)
        role_spec = _role_map()[role]
        return {
            "operator": "RoutingOperator",
            "selected_role": role,
            "candidate_models": role_spec["candidate_models"],
            "selection_reason": self._reason(mission, role),
            "cost_class": role_spec["cost_class"],
            "fallback_role": role_spec["fallback_role"],
            "requires_availability_check": True,
            "requires_verification": True,
            "created_at": utc_ts(),
        }

    def _select_role(self, mission: dict[str, Any], message: dict[str, Any] | None) -> str:
        text = " ".join(
            [
                str(mission.get("intent_raw", "")),
                str(mission.get("objective", "")),
                str((message or {}).get("payload", "")),
            ]
        ).lower()
        if mission.get("risk_level") in {"high", "critical"}:
            return "safety"
        if any(word in text for word in ["ocr", "pdf image", "scan"]):
            return "ocr_document"
        if any(word in text for word in ["source", "retrieval", "rag", "evidence"]):
            return "retrieval_rerank"
        if any(word in text for word in ["code", "implement", "coder"]):
            return "code"
        if mission.get("depth") in {"deep", "abyssal"}:
            return "planner_deep"
        return "fast_router_or_summarizer"

    def _reason(self, mission: dict[str, Any], role: str) -> str:
        return (
            f"role={role} selected for depth={mission.get('depth')} "
            f"risk={mission.get('risk_level')} autonomy={mission.get('autonomy_level')}"
        )


class TruthGateOperator:
    def create_proof_capsule(
        self,
        *,
        target_artifact: str,
        claims: list[str],
        sources: list[str],
        tests: list[str],
        risks: list[str] | None = None,
        memory_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        memory_check = self.evaluate_against_memory(claims, memory_records or [])
        confidence = self._confidence(claims, sources, tests)
        status = "passed" if confidence >= 0.75 else "warn"
        if not sources:
            status = "warn"
        if not claims:
            status = "failed"
        if memory_check["contradictions"]:
            status = "failed"
            confidence = min(confidence, 0.35)
        elif memory_check["confirmations"]:
            confidence = min(confidence + 0.05, 1.0)

        return {
            "id": self._id("PROOF", target_artifact, claims),
            "target_artifact": target_artifact,
            "claims": claims,
            "sources": sources,
            "invariants": [
                "claims must stay separated from verified facts",
                "critical mutations require rollback",
            ],
            "tests": tests,
            "risks": risks or [],
            "confidence": confidence,
            "status": status,
            "review_notes": self._review_notes(memory_check),
            "memory_check": memory_check,
            "created_at": utc_ts(),
        }

    def evaluate_against_memory(self, claims: list[str], memory_records: list[dict[str, Any]]) -> dict[str, Any]:
        confirmations: list[dict[str, str]] = []
        contradictions: list[dict[str, str]] = []
        for claim in claims:
            for record in memory_records:
                for known_claim in record.get("claims", []):
                    relation = _claim_relation(claim, known_claim)
                    if relation == "confirm":
                        confirmations.append(
                            {
                                "claim": claim,
                                "known_claim": known_claim,
                                "record_id": record.get("id", "unknown"),
                            }
                        )
                    elif relation == "contradict":
                        contradictions.append(
                            {
                                "claim": claim,
                                "known_claim": known_claim,
                                "record_id": record.get("id", "unknown"),
                            }
                        )
        status = "failed" if contradictions else "passed"
        if not contradictions and not confirmations:
            status = "unverified"
        return {
            "status": status,
            "confirmations": confirmations,
            "contradictions": contradictions,
        }

    def _confidence(self, claims: list[str], sources: list[str], tests: list[str]) -> float:
        if not claims:
            return 0.0
        score = 0.35
        if sources:
            score += 0.25
        if tests:
            score += 0.25
        if len(sources) >= len(claims):
            score += 0.15
        return min(score, 1.0)

    def _id(self, prefix: str, target: str, claims: list[str]) -> str:
        digest = sha256((target + "|".join(claims)).encode("utf-8")).hexdigest()[:8].upper()
        return f"{prefix}-{digest}"

    def _review_notes(self, memory_check: dict[str, Any]) -> str:
        if memory_check["contradictions"]:
            return "Local memory contradiction detected; human review required."
        if memory_check["confirmations"]:
            return "Local memory contains confirming claims; human review still required."
        return "Initial automated proof capsule; human review still required."


class MemoryOperator:
    def create_tile(
        self,
        *,
        title: str,
        summary: str,
        source_refs: list[str],
        tags: list[str],
        claims: list[str],
        relations: list[str] | None = None,
        compression_level: str = "summary",
    ) -> dict[str, Any]:
        now = utc_ts()
        raw = f"{title}|{summary}|{'|'.join(source_refs)}"
        return {
            "id": f"KT-{sha256(raw.encode('utf-8')).hexdigest()[:8].upper()}",
            "title": title,
            "summary": summary,
            "source_refs": source_refs,
            "tags": tags,
            "claims": claims,
            "relations": relations or [],
            "verification_status": "partial" if source_refs else "unverified",
            "usefulness_score": 0.75 if source_refs else 0.45,
            "recency_score": 1.0,
            "compression_level": compression_level,
            "hash": sha256(raw.encode("utf-8")).hexdigest(),
            "created_at": now,
            "updated_at": now,
        }


class MemoryContextOperator:
    def memory_state(self, record: dict[str, Any]) -> str:
        if record.get("obsolete") is True or record.get("verification_status") == "rejected":
            return "obsolete"
        if float(record.get("recency_score", 1.0) or 0.0) < 0.25:
            return "stale"
        if float(record.get("usefulness_score", 0.5) or 0.0) < 0.2:
            return "low_value"
        return "active"

    def build_relation_graph(self, knowledge_records: list[dict[str, Any]]) -> dict[str, list[str]]:
        graph: dict[str, set[str]] = {}
        for tile in knowledge_records:
            node = tile.get("id", "unknown")
            graph.setdefault(node, set())
            for relation in tile.get("relations", []):
                graph[node].add(relation)
                graph.setdefault(relation, set()).add(node)
        return {node: sorted(edges) for node, edges in sorted(graph.items())}

    def build_weighted_relation_graph(self, knowledge_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        graph: dict[str, dict[str, dict[str, Any]]] = {}
        for tile in knowledge_records:
            source = tile.get("id", "unknown")
            graph.setdefault(source, {})
            edge_weight = self._record_weight(tile)
            for relation in tile.get("relations", []):
                graph[source][relation] = {
                    "target": relation,
                    "weight": edge_weight,
                    "state": self.memory_state(tile),
                    "source_tile": source,
                }
                graph.setdefault(relation, {})
                graph[relation][source] = {
                    "target": source,
                    "weight": edge_weight,
                    "state": self.memory_state(tile),
                    "source_tile": source,
                }
        return {
            node: sorted(edges.values(), key=lambda edge: (-float(edge["weight"]), str(edge["target"])))
            for node, edges in sorted(graph.items())
        }

    def fusion_candidates(self, knowledge_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in knowledge_records:
            signature = self._fusion_signature(record)
            groups.setdefault(signature, []).append(record)

        candidates = []
        for signature, records in sorted(groups.items()):
            if len(records) < 2:
                continue
            candidates.append(
                {
                    "signature": signature,
                    "count": len(records),
                    "ids": [record.get("id", "unknown") for record in records],
                    "titles": sorted({str(record.get("title", "")) for record in records if record.get("title")}),
                }
            )
        return candidates

    def state_counts(self, knowledge_records: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"active": 0, "stale": 0, "low_value": 0, "obsolete": 0}
        for record in knowledge_records:
            state = self.memory_state(record)
            counts[state] = counts.get(state, 0) + 1
        return counts

    def synthesize_context(
        self,
        knowledge_records: list[dict[str, Any]],
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        scored = []
        for record in knowledge_records:
            score = self.context_score(record, query)
            if score <= 0:
                continue
            scored.append({"record": record, "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        selected = scored[:limit]
        return {
            "operator": "MemoryContextOperator",
            "query": query,
            "result_count": len(selected),
            "items": [
                {
                    "id": item["record"].get("id"),
                    "title": item["record"].get("title"),
                    "summary": item["record"].get("summary"),
                    "score": item["score"],
                    "state": self.memory_state(item["record"]),
                    "tags": item["record"].get("tags", []),
                }
                for item in selected
            ],
            "state_counts": self.state_counts(knowledge_records),
            "fusion_candidates": self.fusion_candidates(knowledge_records),
        }

    def context_score(self, record: dict[str, Any], query: str) -> float:
        lexical = self.relevance_score(record, query)
        if lexical <= 0:
            return 0.0
        verification_weight = {
            "verified": 1.0,
            "partial": 0.75,
            "unverified": 0.45,
            "rejected": 0.0,
        }.get(record.get("verification_status"), 0.35)
        usefulness = float(record.get("usefulness_score", 0.5) or 0.0)
        recency = float(record.get("recency_score", 0.5) or 0.0)
        source_weight = 1.0 if record.get("source_refs") else 0.65
        state_penalty = {
            "active": 1.0,
            "stale": 0.55,
            "low_value": 0.35,
            "obsolete": 0.0,
        }[self.memory_state(record)]
        score = lexical * 0.5 + verification_weight * 0.2 + usefulness * 0.15 + recency * 0.1 + source_weight * 0.05
        return round(min(score * state_penalty, 1.0), 3)

    def relevance_score(self, record: dict[str, Any], query: str) -> float:
        if not query:
            return 0.0
        query_terms = {term for term in query.lower().replace("_", " ").split() if term}
        if not query_terms:
            return 0.0
        fields = [
            record.get("title", ""),
            record.get("summary", ""),
            " ".join(record.get("tags", [])),
            " ".join(record.get("claims", [])),
            " ".join(record.get("relations", [])),
            " ".join(record.get("source_refs", [])),
        ]
        text = " ".join(str(field).lower() for field in fields)
        matches = sum(1 for term in query_terms if term in text)
        base = matches / len(query_terms)
        if record.get("verification_status") in {"verified", "partial"}:
            base += 0.1
        return round(min(base, 1.0), 3)

    def _record_weight(self, record: dict[str, Any]) -> float:
        usefulness = float(record.get("usefulness_score", 0.5) or 0.0)
        recency = float(record.get("recency_score", 0.5) or 0.0)
        verification = {
            "verified": 1.0,
            "partial": 0.75,
            "unverified": 0.45,
            "rejected": 0.0,
        }.get(record.get("verification_status"), 0.35)
        state_penalty = 0.0 if self.memory_state(record) == "obsolete" else 1.0
        return round((usefulness * 0.4 + recency * 0.25 + verification * 0.35) * state_penalty, 3)

    def _fusion_signature(self, record: dict[str, Any]) -> str:
        tags = sorted(str(tag).lower() for tag in record.get("tags", []))
        claims = sorted(_claim_signature(str(claim))[1] for claim in record.get("claims", []))
        title_words = sorted(set(_ascii_words(str(record.get("title", "")))) - {"aione", "the", "and"})
        raw = "|".join([" ".join(title_words[:6]), ",".join(tags), ",".join(claims[:4])])
        return sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


class ContractGateOperator:
    def evaluate(self, contract_results: dict[str, list[Any]]) -> dict[str, Any]:
        issues = []
        for definition_name, definition_issues in sorted(contract_results.items()):
            for issue in definition_issues:
                issues.append(
                    {
                        "definition": definition_name,
                        "path": self._issue_path(issue),
                        "message": self._issue_message(issue),
                    }
                )

        issue_count = len(issues)
        status = "passed" if issue_count == 0 else "blocked"
        raw = "|".join(f"{issue['definition']}:{issue['path']}:{issue['message']}" for issue in issues) or "pass"
        return {
            "id": f"CG-{sha256(raw.encode('utf-8')).hexdigest()[:8].upper()}",
            "operator": "ContractGateOperator",
            "status": status,
            "can_continue": status == "passed",
            "issue_count": issue_count,
            "blocking_definitions": sorted({issue["definition"] for issue in issues}),
            "issues": issues,
            "correction_prompts": [self._correction_prompt(issue) for issue in issues],
            "created_at": utc_ts(),
        }

    def _issue_path(self, issue: Any) -> str:
        if isinstance(issue, dict):
            return str(issue.get("path", "unknown"))
        return str(getattr(issue, "path", "unknown"))

    def _issue_message(self, issue: Any) -> str:
        if isinstance(issue, dict):
            return str(issue.get("message", "unknown contract issue"))
        return str(getattr(issue, "message", "unknown contract issue"))

    def _correction_prompt(self, issue: dict[str, str]) -> str:
        return (
            f"Fix contract {issue['definition']} at {issue['path']}: {issue['message']}. "
            "Regenerate the artifact, rerun runtime contract validation, then update the patch ledger."
        )


class PatchLedgerOperator:
    def create_patch_ledger(
        self,
        *,
        mission_id: str,
        change_summary: str,
        files_touched: list[str],
        reason: str,
        verification: list[str],
        rollback_plan: str,
        before_state: str | None = None,
        after_state: str | None = None,
        status: str = "applied",
    ) -> dict[str, Any]:
        raw = f"{mission_id}|{change_summary}|{'|'.join(files_touched)}"
        return {
            "id": f"PATCH-{sha256(raw.encode('utf-8')).hexdigest()[:8].upper()}",
            "mission_id": mission_id,
            "change_summary": change_summary,
            "files_touched": files_touched,
            "reason": reason,
            "before_state": before_state,
            "after_state": after_state,
            "verification": verification,
            "rollback_plan": rollback_plan,
            "status": status,
            "created_at": utc_ts(),
        }


def _ascii_words(text: str) -> list[str]:
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    normalized = normalized.replace("cannot", "can not").replace("can't", "can not")
    return ["".join(ch for ch in word if ch.isalnum()) for word in normalized.split()]


def _claim_signature(text: str) -> tuple[bool, str]:
    words = [word for word in _ascii_words(text) if word]
    negative_words = {"not", "no", "never", "pas", "non", "blocked", "forbidden", "interdit"}
    has_negative = any(word in negative_words for word in words)
    filtered = [word for word in words if word not in negative_words]
    return has_negative, " ".join(filtered)


def _claim_relation(left: str, right: str) -> str:
    left_negative, left_body = _claim_signature(left)
    right_negative, right_body = _claim_signature(right)
    if left_body == right_body and left_negative == right_negative:
        return "confirm"
    if left_body == right_body and left_negative != right_negative:
        return "contradict"

    left_words = set(left_body.split())
    right_words = set(right_body.split())
    overlap = len(left_words & right_words)
    if overlap >= 4 and left_negative != right_negative:
        return "contradict"
    return "none"
