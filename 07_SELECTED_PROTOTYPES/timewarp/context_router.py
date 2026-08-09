from typing import List
from .instant_frame import InstantFrame
from .project_frame import ProjectFrame
from .session_frame import SessionFrame

def route_context(task: str, project: ProjectFrame, session: SessionFrame, instant: InstantFrame) -> List[str]:
    task = task.lower()
    selected = [f"task:{task}"]
    if "runtime" in task:
        selected.append(f"runtime:{project.runtime}")
    if "hud" in task:
        selected.append(f"hud:{project.hud}")
    selected.append(f"objective:{session.objective}")
    selected.append(f"active_file:{instant.active_file}")
    return selected
