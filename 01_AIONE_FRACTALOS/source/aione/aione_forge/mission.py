from __future__ import annotations

import re
from typing import Any

from .io import utc_ts


def _contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _title_from_intent(intent_raw: str) -> str:
    cleaned = " ".join(intent_raw.strip().split())
    if not cleaned:
        return "Mission sans titre"
    first = re.split(r"[.!?\n]", cleaned, maxsplit=1)[0].strip()
    if len(first) <= 80:
        return first or "Mission sans titre"
    return first[:77].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


class MissionParser:
    def parse(self, intent_raw: str, mission_id: str = "MISSION-0001") -> dict[str, Any]:
        cleaned = " ".join(intent_raw.strip().split())
        if not cleaned:
            raise ValueError("intent_raw cannot be empty")

        risk_level = self._risk_level(cleaned)
        depth = self._depth(cleaned)
        autonomy_level = self._autonomy_level(cleaned, risk_level)
        now = utc_ts()

        return {
            "id": mission_id,
            "title": _title_from_intent(cleaned),
            "intent_raw": cleaned,
            "objective": cleaned,
            "constraints": self._constraints(cleaned),
            "expected_outputs": self._expected_outputs(cleaned),
            "risk_level": risk_level,
            "autonomy_level": autonomy_level,
            "depth": depth,
            "resource_budget": {
                "tokens": None,
                "cpu": "normal",
                "gpu": None,
                "vram": None,
                "time_seconds": None,
            },
            "verification_required": True,
            "status": "planned",
            "created_at": now,
            "updated_at": now,
        }

    def _constraints(self, text: str) -> list[str]:
        constraints = ["local-first", "verification-required", "rollback-for-critical-mutations"]
        if _contains_any(text, ["energie", "consommation", "sobriete", "performance"]):
            constraints.append("optimize-capacity-per-resource")
        if _contains_any(text, ["nvidia", "build.nvidia.com", "model"]):
            constraints.append("verify-model-availability-before-use")
        if _contains_any(text, ["autonome", "auto", "daemon", "forge"]):
            constraints.append("controlled-autonomy")
        return sorted(set(constraints))

    def _expected_outputs(self, text: str) -> list[str]:
        outputs = ["plan", "verification_checklist", "operation_pack"]
        if _contains_any(text, ["schema", "contrat", "json"]):
            outputs.append("schemas")
        if _contains_any(text, ["code", "coder", "forge", "implement"]):
            outputs.append("code_tasks")
        if _contains_any(text, ["test", "verif", "preuve"]):
            outputs.append("tests")
        if _contains_any(text, ["memoire", "knowledge", "source"]):
            outputs.append("knowledge_tiles")
        return sorted(set(outputs))

    def _risk_level(self, text: str) -> str:
        if _contains_any(text, ["delete", "supprimer", "format", "credential", "secret", "systeme", "reseau"]):
            return "high"
        if _contains_any(text, ["code", "execution", "autonome", "daemon", "forge", "fichier"]):
            return "medium"
        return "low"

    def _depth(self, text: str) -> str:
        if _contains_any(text, ["architecture", "science", "recherche", "aione", "forge", "autonome"]):
            return "deep"
        if _contains_any(text, ["simple", "rapide", "status"]):
            return "quick"
        return "standard"

    def _autonomy_level(self, text: str, risk_level: str) -> str:
        if risk_level in {"high", "critical"}:
            return "suggestion"
        if _contains_any(text, ["autonome", "daemon", "forge", "auto"]):
            return "verified_execution"
        return "suggestion"
