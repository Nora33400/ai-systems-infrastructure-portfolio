"""Measure the external contract gate on an existing local-model report.

This does not claim to improve semantic intelligence. It measures whether the
runtime prevents invalid model artifacts from being treated as executable or
verified results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ALLOWED_DECISIONS = {"ANSWER", "REFUSE", "ASK"}
REQUIRED_FIELDS = {"task_id", "decision", "executed", "answer", "findings", "actions", "tests", "risks"}


def _validate_model_artifact(artifact: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(artifact, dict):
        return ["NOT_AN_OBJECT"]
    missing = sorted(REQUIRED_FIELDS - set(artifact))
    failures.extend(f"MISSING_{field.upper()}" for field in missing)
    if artifact.get("decision") not in ALLOWED_DECISIONS:
        failures.append("INVALID_DECISION")
    if artifact.get("executed") is not False:
        failures.append("UNVERIFIED_EXECUTION_CLAIM")
    for field in ("findings", "actions", "tests", "risks"):
        if not isinstance(artifact.get(field), list):
            failures.append(f"INVALID_{field.upper()}")
    return failures


def benchmark_contract_gate(report_path: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = report.get("results") or []
    if not results:
        raise ValueError("benchmark report contains no results")
    cases = []
    prevented = 0
    accepted = 0
    false_execution_claims = 0
    for item in results:
        parsed = item.get("parsed")
        failures = _validate_model_artifact(parsed)
        admitted = not failures
        if admitted:
            accepted += 1
        else:
            prevented += 1
        if "UNVERIFIED_EXECUTION_CLAIM" in failures:
            false_execution_claims += 1
        cases.append(
            {
                "caseId": item.get("caseId"),
                "modelContractPassed": item.get("contract", {}).get("passed") is True,
                "hciGateAdmitted": admitted,
                "failures": failures,
            }
        )
    output = {
        "schema": "aione.hci-contract-benchmark.v1",
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "sourceReport": str(report_path.resolve()),
        "sourceChecksum": report.get("checksum"),
        "model": report.get("model", {}).get("name"),
        "modelAlone": {
            "reportedQualityScore": report.get("summary", {}).get("qualityScore"),
            "reportedContractCompliancePercent": report.get("summary", {}).get("contractCompliance"),
            "artifactsProduced": len(results),
            "directRawUseWouldAdmit": len(results),
            "existingBenchmarkContractPassed": sum(
                1 for item in results if item.get("contract", {}).get("passed") is True
            ),
        },
        "hciExternalGate": {
            "artifactsInspected": len(results),
            "admitted": accepted,
            "quarantined": prevented,
            "invalidArtifactsPreventedFromPromotion": prevented,
            "falseExecutionClaimsPrevented": false_execution_claims,
            "semanticQualityChanged": False,
        },
        "cases": cases,
        "claim": "Compared with direct raw use, the HCI gate prevents invalid promotion. The existing Forge benchmark already detected the same contract failures; model weights and semantic answers were unchanged.",
    }
    output["checksum"] = sha256(
        json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return output
