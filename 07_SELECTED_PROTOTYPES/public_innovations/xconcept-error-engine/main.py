from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ErrorItem:
    code: str
    severity: str
    reason: str


def detect_errors(sigma: Dict[str, float], has_tests: bool, contradictions: int) -> List[ErrorItem]:
    errors: List[ErrorItem] = []
    if sigma.get("epsilon", 0.0) > 0.55 and not has_tests:
        errors.append(ErrorItem("C1", "high", "unsupported_claim_without_tests"))
    if sigma.get("lambda", 0.0) > 0.65:
        errors.append(ErrorItem("B1", "medium", "overcompute_risk"))
    if contradictions > 0:
        errors.append(ErrorItem("C2", "high", "critical_contradiction"))
    if sigma.get("delta", 0.0) > 0.6:
        errors.append(ErrorItem("B3", "medium", "oscillation_detected"))
    return errors


def mitigations(errors: List[ErrorItem]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for e in errors:
        if e.code == "C1":
            out.append({"action": "add_test", "detail": "require_min_test=1"})
        elif e.code == "B1":
            out.append({"action": "reduce_budget", "detail": "max_options=3,k_retrieve=3"})
        elif e.code == "C2":
            out.append({"action": "rollback", "detail": "return_to_last_stable_checkpoint"})
        elif e.code == "B3":
            out.append({"action": "lock_mode", "detail": "switch=focus"})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="XConcept Error Engine")
    parser.add_argument("--sigma", default='{"mu":0.4,"kappa":0.5,"rho":0.3,"epsilon":0.2,"delta":0.2,"lambda":0.3}')
    parser.add_argument("--has-tests", action="store_true")
    parser.add_argument("--contradictions", type=int, default=0)
    args = parser.parse_args()

    sigma = json.loads(args.sigma)
    found = detect_errors(sigma, args.has_tests, args.contradictions)
    result = {
        "errors": [e.__dict__ for e in found],
        "mitigations": mitigations(found),
        "rollback_needed": any(e.code == "C2" for e in found),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
