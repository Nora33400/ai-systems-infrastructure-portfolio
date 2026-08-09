from dataclasses import dataclass
from typing import Dict, Any, Tuple

@dataclass
class GuardThresholds:
    C_min: float = 0.72
    P_max: float = 0.85
    N_max: float = 0.30

def decide(metrics: Dict[str, float], th: GuardThresholds) -> Tuple[str, Dict[str, Any]]:
    C=float(metrics.get("C",1.0)); P=float(metrics.get("P",0.0)); N=float(metrics.get("N",0.0))
    if C < th.C_min:
        return "stabilize_mode", {"reason":"C_below_min","C":C,"C_min":th.C_min}
    if P > th.P_max:
        return "throttle_mode", {"reason":"P_above_max","P":P,"P_max":th.P_max}
    if N > th.N_max:
        return "quarantine_branch", {"reason":"N_above_max","N":N,"N_max":th.N_max}
    return "normal", {"reason":"ok","C":C,"P":P,"N":N}
