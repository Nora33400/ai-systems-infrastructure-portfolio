from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Issue:
    code: str
    severity: str
    reason: str


def detect(sigma: Dict[str, float], test_pass_rate: float, consecutive_fails: int) -> List[Issue]:
    out: List[Issue] = []
    if test_pass_rate < 0.75:
        out.append(Issue("T1", "high", "low_test_pass_rate"))
    if sigma.get("epsilon", 0.0) > 0.55:
        out.append(Issue("Q1", "high", "quality_drift"))
    if sigma.get("lambda", 0.0) > 0.70:
        out.append(Issue("C1", "medium", "compute_overuse"))
    if consecutive_fails >= 2:
        out.append(Issue("R1", "high", "persistent_failure"))
    return out


def autorepair_plan(issues: List[Issue]) -> List[Dict[str, str]]:
    plan: List[Dict[str, str]] = []
    for i in issues:
        if i.code == "T1":
            plan.append({"step": "increase_tests", "detail": "run smoke + regression + deterministic checks"})
        elif i.code == "Q1":
            plan.append({"step": "reduce_scope", "detail": "limit patches to one module, enable rollback"})
        elif i.code == "C1":
            plan.append({"step": "budget_cap", "detail": "decrease workers and top_k"})
        elif i.code == "R1":
            plan.append({"step": "safe_rebuild", "detail": "rebuild from last green checkpoint"})
    if issues:
        plan.append({"step": "revalidate", "detail": "run full pipeline and compare before/after metrics"})
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Derived XConcept auto-repair planner")
    parser.add_argument("--sigma", default='{"mu":0.4,"kappa":0.5,"rho":0.3,"epsilon":0.2,"delta":0.2,"lambda":0.3}')
    parser.add_argument("--test-pass-rate", type=float, default=1.0)
    parser.add_argument("--consecutive-fails", type=int, default=0)
    args = parser.parse_args()

    sigma = json.loads(args.sigma)
    issues = detect(sigma, args.test_pass_rate, args.consecutive_fails)
    result = {
        "issues": [i.__dict__ for i in issues],
        "plan": autorepair_plan(issues),
        "auto_repair": bool(issues),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
