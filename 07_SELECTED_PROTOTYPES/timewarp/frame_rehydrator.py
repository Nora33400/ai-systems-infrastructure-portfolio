from typing import List
from .instant_frame import InstantFrame
from .project_frame import ProjectFrame
from .session_frame import SessionFrame

def rehydrate_context(project: ProjectFrame, session: SessionFrame, instant: InstantFrame) -> List[str]:
    return [
        f"priority:{project.current_priority}",
        f"objective:{session.objective}",
        f"next:{session.next_step}",
        f"active:{instant.active_file}",
        f"action:{instant.recent_action}",
    ]
