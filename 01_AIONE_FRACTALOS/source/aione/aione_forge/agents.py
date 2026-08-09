from __future__ import annotations

from hashlib import sha256
from typing import Any

from .io import utc_ts


class AgentOrchestrator:
    def __init__(self, agent_specs: list[dict[str, Any]]):
        self.agent_specs = agent_specs

    def decide(
        self,
        *,
        mission: dict[str, Any],
        contract_gate: dict[str, Any],
        context_summary: dict[str, Any],
    ) -> dict[str, Any]:
        selected = self.select_agent(mission, context_summary)
        if selected is None:
            return self._skipped_decision(mission, contract_gate)

        gate_passed = bool(contract_gate.get("can_continue"))
        status = "proposed" if gate_passed else "blocked"
        reason = (
            f"{selected['name']} selected for locality={selected['locality']} role={selected['role']}."
            if gate_passed
            else "Contract gate blocked; no agent action can continue."
        )
        action = self._proposed_action(selected, mission, context_summary, gate_passed)
        raw = f"{mission['id']}|{selected['id']}|{status}|{action['type']}"
        return {
            "id": f"ADEC-{sha256(raw.encode('utf-8')).hexdigest()[:8].upper()}",
            "mission_id": mission["id"],
            "selected_agent_id": selected["id"],
            "selected_agent_name": selected["name"],
            "selected_agent_role": selected["role"],
            "status": status,
            "reason": reason,
            "required_gates": selected.get("required_gates", []),
            "gate_status": {
                "ContractGateOperator": contract_gate.get("status", "unknown"),
                "issue_count": contract_gate.get("issue_count", 0),
            },
            "proposed_action": action,
            "permissions": selected.get("permissions", []),
            "tests": selected.get("tests", []),
            "rollback_policy": selected.get("rollback_policy", {}),
            "created_at": utc_ts(),
        }

    def select_agent(self, mission: dict[str, Any], context_summary: dict[str, Any]) -> dict[str, Any] | None:
        if not self.agent_specs:
            return None
        objective = str(mission.get("objective", "")).lower()
        expected_outputs = " ".join(mission.get("expected_outputs", [])).lower()
        context_text = " ".join(str(item.get("title", "")) for item in context_summary.get("items", [])).lower()
        selection_text = " ".join([objective, expected_outputs, context_text])
        preferred_role = self._preferred_role(selection_text)

        for agent in self.agent_specs:
            if agent.get("role") == preferred_role:
                return agent
        return self.agent_specs[0]

    def _preferred_role(self, text: str) -> str:
        if any(word in text for word in ["contract", "proof", "verify", "verification", "test"]):
            return "verifier"
        if any(word in text for word in ["memory", "memoire", "knowledge", "context"]):
            return "memory_curator"
        return "planner"

    def _proposed_action(
        self,
        selected: dict[str, Any],
        mission: dict[str, Any],
        context_summary: dict[str, Any],
        gate_passed: bool,
    ) -> dict[str, Any]:
        role_actions = {
            "planner": "plan_tasks",
            "verifier": "verify_artifacts",
            "memory_curator": "curate_memory_context",
        }
        return {
            "type": role_actions.get(selected.get("role", ""), "observe"),
            "mode": "proposal_only",
            "mutation_allowed": False,
            "target_mission": mission["id"],
            "context_items": context_summary.get("result_count", 0),
            "requires_gate_passed": True,
            "gate_passed": gate_passed,
        }

    def _skipped_decision(self, mission: dict[str, Any], contract_gate: dict[str, Any]) -> dict[str, Any]:
        raw = f"{mission['id']}|no-agent|skipped"
        return {
            "id": f"ADEC-{sha256(raw.encode('utf-8')).hexdigest()[:8].upper()}",
            "mission_id": mission["id"],
            "selected_agent_id": "none",
            "selected_agent_name": "none",
            "selected_agent_role": "orchestrator",
            "status": "skipped",
            "reason": "No agent specs available.",
            "required_gates": ["ContractGateOperator"],
            "gate_status": {
                "ContractGateOperator": contract_gate.get("status", "unknown"),
                "issue_count": contract_gate.get("issue_count", 0),
            },
            "proposed_action": {
                "type": "no_agent_available",
                "mode": "proposal_only",
                "mutation_allowed": False,
            },
            "permissions": [],
            "tests": [],
            "rollback_policy": {"required": False, "strategy": "no_mutation"},
            "created_at": utc_ts(),
        }


def render_agent_orchestrator_status(decision: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestrator Status",
        "",
        f"Decision: {decision['id']}",
        f"Mission: {decision['mission_id']}",
        f"Selected agent: {decision['selected_agent_name']} ({decision['selected_agent_id']})",
        f"Role: {decision['selected_agent_role']}",
        f"Status: {decision['status']}",
        f"Reason: {decision['reason']}",
        "",
        "## Proposed action",
        "",
        f"Type: {decision['proposed_action'].get('type')}",
        f"Mode: {decision['proposed_action'].get('mode')}",
        f"Mutation allowed: {decision['proposed_action'].get('mutation_allowed')}",
        "",
        "## Gates",
        "",
    ]
    for name, status in decision.get("gate_status", {}).items():
        lines.append(f"- {name}: {status}")
    lines.extend(["", "## Tests", ""])
    if decision.get("tests"):
        lines.extend(f"- {test}" for test in decision["tests"])
    else:
        lines.append("No test selected.")
    return "\n".join(lines)
