from typing import Dict, Any, List

def priority(task: Dict[str, Any]) -> float:
    return (
        float(task.get("alignment", 0.0)) *
        float(task.get("goal_weight", 0.0)) *
        float(task.get("maturity", 0.0))
        - (float(task.get("estimate_cost", 0.0)) * float(task.get("risk", 0.0)))
    )

def order(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(tasks, key=priority, reverse=True)

def omega_budget(task: Dict[str, Any], base: float = 160.0) -> float:
    p = max(0.0, priority(task))
    cost = float(task.get("estimate_cost", 0.25))
    risk = float(task.get("risk", 0.25))
    return max(25.0, base * (0.65 + p) * (0.85 + cost) * (1.0 - 0.45 * risk))
