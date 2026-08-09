from dataclasses import dataclass

@dataclass
class ProjectFrame:
    runtime: str = "unknown"
    memory: str = "unknown"
    scheduler: str = "unknown"
    hud: str = "unknown"
    builder: str = "unknown"
    current_priority: str = ""
