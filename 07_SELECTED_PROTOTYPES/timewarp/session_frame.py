from dataclasses import dataclass, field
from typing import List

@dataclass
class SessionFrame:
    objective: str
    done: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    next_step: str = ""
