from dataclasses import dataclass

@dataclass
class InstantFrame:
    mode: str
    goal: str
    active_file: str
    recent_action: str
    issue: str = ""
    next_hint: str = ""
