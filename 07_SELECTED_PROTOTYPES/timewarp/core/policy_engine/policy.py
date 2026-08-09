import json, os
from typing import Dict, Any, Optional, Tuple

DEFAULT_POLICY = {
  "roles": {
    "user": {"allow": ["dashboard.view", "fs.read"]},
    "agent.planner": {"allow": ["fs.read", "ledger.append"]},
    "agent.coder": {"allow": ["fs.read", "fs.write", "ledger.append"]},
    "agent.debugger": {"allow": ["fs.read", "fs.write", "proc.run", "ledger.append"]},
    "agent.tester": {"allow": ["fs.read", "proc.run", "ledger.append"]},
    "agent.applier": {"allow": ["fs.read", "fs.write", "ledger.append"]},
    "agent.doc": {"allow": ["fs.read", "fs.write", "ledger.append"]},
    "agent.forge": {"allow": ["fs.read", "fs.write", "ledger.append"]}
  },
  "modes": {
    "safe": {"deny": ["net.http", "proc.run:unbounded", "fs.write:system_paths"]}
  }
}

def load_policy(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return DEFAULT_POLICY
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def is_allowed(policy: Dict[str, Any], role: str, perm: str) -> Tuple[bool, Optional[str]]:
    allow = set(policy.get("roles", {}).get(role, {}).get("allow", []))
    if perm in allow:
        return True, None
    return False, f"Permission '{perm}' denied for role '{role}'."

def tool_permission(tool_name: str) -> str:
    if tool_name.startswith("tool.fs.read"): return "fs.read"
    if tool_name.startswith("tool.fs.write"): return "fs.write"
    if tool_name.startswith("tool.proc.run"): return "proc.run"
    if tool_name.startswith("tool.ledger.append"): return "ledger.append"
    if tool_name.startswith("tool.net.http"): return "net.http"
    return "unknown"
