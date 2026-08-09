from typing import Dict, Any, Callable
from core.policy_engine.policy import tool_permission, is_allowed

class ToolRouter:
    def __init__(self, tools: Dict[str, Callable[..., Dict[str, Any]]]):
        self.tools = tools

    def call(self, ctx, role: str, tool_name: str, **kwargs) -> Dict[str, Any]:
        perm = tool_permission(tool_name)
        ok, reason = is_allowed(ctx.policy, role, perm)
        if not ok:
            return {"ok": False, "error": reason, "tool": tool_name}
        fn = self.tools.get(tool_name)
        if not fn:
            return {"ok": False, "error": "Unknown tool", "tool": tool_name}
        return fn(**kwargs)
