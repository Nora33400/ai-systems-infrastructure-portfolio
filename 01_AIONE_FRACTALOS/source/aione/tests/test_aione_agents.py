from __future__ import annotations

from aione_forge.agents import AgentOrchestrator, render_agent_orchestrator_status


def _agent(role: str) -> dict:
    return {
        "id": f"AGENT-{role.upper()}-0001",
        "name": f"{role.title()}Agent",
        "role": role,
        "locality": "verification" if role == "verifier" else "mission",
        "objective": "Test agent.",
        "inputs": ["Mission"],
        "outputs": ["decision"],
        "allowed_buses": ["mission_bus"],
        "required_gates": ["ContractGateOperator"],
        "permissions": ["read_mission"],
        "budget": {"cost_class": "low"},
        "compatible_model_roles": ["fast_router_or_summarizer"],
        "compatible_tools": ["test_tool"],
        "memory_policy": {"read": True},
        "rollback_policy": {"required": True, "strategy": "no_mutation"},
        "tests": ["tests/test_aione_agents.py"],
        "metrics": ["decision_count"],
        "activation_conditions": ["contract_gate_passed"],
        "stop_conditions": ["contract_gate_blocked"],
        "version": "0.1.0",
        "status": "experimental",
    }


def test_agent_orchestrator_selects_verifier_for_verification_mission() -> None:
    orchestrator = AgentOrchestrator([_agent("planner"), _agent("verifier")])

    decision = orchestrator.decide(
        mission={
            "id": "MISSION-0001",
            "objective": "Verify runtime contracts and tests.",
            "expected_outputs": ["tests"],
        },
        contract_gate={"status": "passed", "can_continue": True, "issue_count": 0},
        context_summary={"result_count": 0, "items": []},
    )

    assert decision["selected_agent_role"] == "verifier"
    assert decision["status"] == "proposed"
    assert decision["proposed_action"]["mutation_allowed"] is False
    assert "Status: proposed" in render_agent_orchestrator_status(decision)


def test_agent_orchestrator_blocks_when_contract_gate_blocks() -> None:
    orchestrator = AgentOrchestrator([_agent("planner")])

    decision = orchestrator.decide(
        mission={
            "id": "MISSION-0002",
            "objective": "Plan next tasks.",
            "expected_outputs": ["plan"],
        },
        contract_gate={"status": "blocked", "can_continue": False, "issue_count": 1},
        context_summary={"result_count": 0, "items": []},
    )

    assert decision["selected_agent_role"] == "planner"
    assert decision["status"] == "blocked"
    assert decision["proposed_action"]["gate_passed"] is False
