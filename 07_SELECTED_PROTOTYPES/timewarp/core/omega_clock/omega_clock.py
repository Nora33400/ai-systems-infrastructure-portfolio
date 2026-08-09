from dataclasses import dataclass

@dataclass
class OmegaMetrics:
    W: float = 0.0
    C: float = 1.0
    P: float = 0.0
    N: float = 0.0
    Q: float = 1.0

def delta_omega(m: OmegaMetrics) -> float:
    return (m.W / (1.0 + m.P)) * m.C * (1.0 - m.N) * m.Q
