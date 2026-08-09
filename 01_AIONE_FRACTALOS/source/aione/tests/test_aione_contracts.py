from __future__ import annotations

import json
from pathlib import Path

from aione_forge.contracts import (
    ContractIssue,
    flatten_contract_results,
    load_contract_schema,
    render_contract_gate_status,
    schema_definitions,
    validate_contract,
    validate_forge_tasks,
    validate_model_roles,
    validate_runtime_contracts,
)
from aione_forge.kernel import AioneKernel
from aione_forge.mmr import build_mmr_bundle
from aione_forge.operators import ContractGateOperator
from aione_forge.research_catalog import NVIDIA_MODEL_ROLES


def test_contract_schema_is_loadable() -> None:
    schema_path, schema = load_contract_schema(Path.cwd())

    assert schema_path.name == "aione_contracts.schema.json"
    definitions = schema_definitions(schema)
    assert "Mission" in definitions
    assert "Message" in definitions
    assert "OperatorSpec" in definitions
    assert "AgentDecision" in definitions
    assert "AgentSpec" in definitions
    assert "AutonomousMissionSpec" in definitions
    assert "PotentialState" in definitions
    assert "ConstraintSet" in definitions
    assert "MaterializationRequest" in definitions
    assert "MaterializationPlan" in definitions
    assert "MaterializedSlice" in definitions
    assert "CostTrace" in definitions
    assert "MMRProof" in definitions
    assert "ProofCapsule" in definitions
    assert "PatchLedger" in definitions
    assert "ForgeTask" in definitions
    assert "LayerPacket" in definitions
    assert "LayerExecutionResult" in definitions


def test_schema_examples_are_valid_json() -> None:
    for path in (Path.cwd() / "schemas" / "examples").glob("*.json"):
        assert json.loads(path.read_text(encoding="utf-8"))


def test_generated_model_roles_match_contract_subset() -> None:
    assert validate_model_roles(NVIDIA_MODEL_ROLES) == []


def test_generic_contract_validator_accepts_mission_example() -> None:
    _, schema = load_contract_schema(Path.cwd())
    mission = json.loads((Path.cwd() / "schemas" / "examples" / "mission.example.json").read_text(encoding="utf-8"))

    assert validate_contract(schema, "Mission", mission) == []


def test_generic_contract_validator_rejects_bad_field_type() -> None:
    _, schema = load_contract_schema(Path.cwd())
    mission = json.loads((Path.cwd() / "schemas" / "examples" / "mission.example.json").read_text(encoding="utf-8"))
    mission["verification_required"] = "yes"

    issues = validate_contract(schema, "Mission", mission)

    assert any(issue.path == "Mission.verification_required" for issue in issues)


def test_generic_contract_validator_accepts_agent_example() -> None:
    _, schema = load_contract_schema(Path.cwd())
    agent = json.loads((Path.cwd() / "schemas" / "examples" / "agent_spec.example.json").read_text(encoding="utf-8"))

    assert validate_contract(schema, "AgentSpec", agent) == []


def test_generic_contract_validator_accepts_agent_decision_example() -> None:
    _, schema = load_contract_schema(Path.cwd())
    decision = json.loads((Path.cwd() / "schemas" / "examples" / "agent_decision.example.json").read_text(encoding="utf-8"))

    assert validate_contract(schema, "AgentDecision", decision) == []


def test_generic_contract_validator_accepts_autonomous_mission_example() -> None:
    _, schema = load_contract_schema(Path.cwd())
    mission = json.loads((Path.cwd() / "schemas" / "examples" / "autonomous_mission.example.json").read_text(encoding="utf-8"))

    assert validate_contract(schema, "AutonomousMissionSpec", mission) == []


def test_generic_contract_validator_accepts_mmr_examples() -> None:
    _, schema = load_contract_schema(Path.cwd())
    examples = {
        "PotentialState": "potential_state.example.json",
        "ConstraintSet": "constraint_set.example.json",
        "MaterializationRequest": "materialization_request.example.json",
        "MaterializationPlan": "materialization_plan.example.json",
        "MaterializedSlice": "materialized_slice.example.json",
        "CostTrace": "cost_trace.example.json",
        "MMRProof": "mmr_proof.example.json",
    }

    for definition_name, filename in examples.items():
        payload = json.loads((Path.cwd() / "schemas" / "examples" / filename).read_text(encoding="utf-8"))
        assert validate_contract(schema, definition_name, payload) == []


def test_runtime_contracts_accept_kernel_cycle() -> None:
    _, schema = load_contract_schema(Path.cwd())
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    tasks = [
        {
            "id": "TASK-0001-001",
            "title": "Valider les contrats runtime",
            "locality": "verification",
            "operator": "TruthGateOperator",
            "verification": "runtime contracts pass",
            "status": "pending",
            "source_refs": ["schemas/aione_contracts.schema.json"],
            "artifact_targets": ["kernel/runtime_contract_validation.json"],
        }
    ]
    operator_specs = [
        json.loads((Path.cwd() / "schemas" / "examples" / "operator_spec.example.json").read_text(encoding="utf-8"))
    ]
    agent_specs = [
        json.loads((Path.cwd() / "schemas" / "examples" / "agent_spec.example.json").read_text(encoding="utf-8"))
    ]
    agent_decision = json.loads((Path.cwd() / "schemas" / "examples" / "agent_decision.example.json").read_text(encoding="utf-8"))
    autonomous_mission = json.loads(
        (Path.cwd() / "schemas" / "examples" / "autonomous_mission.example.json").read_text(encoding="utf-8")
    )
    mmr_bundle = build_mmr_bundle(
        mission=kernel_result["mission"],
        context_summary={"result_count": 1, "items": [{"id": "KT-0001", "title": "Kernel memory"}]},
        cycle=1,
    )

    results = validate_runtime_contracts(
        schema,
        tasks=tasks,
        model_roles=NVIDIA_MODEL_ROLES,
        operator_specs=operator_specs,
        agent_specs=agent_specs,
        agent_decision=agent_decision,
        autonomous_mission=autonomous_mission,
        mmr_bundle=mmr_bundle.as_dict(),
        kernel_result=kernel_result,
    )

    assert flatten_contract_results(results) == []


def test_contract_gate_operator_passes_clean_results() -> None:
    gate = ContractGateOperator().evaluate({"Mission": [], "Message": []})

    assert gate["status"] == "passed"
    assert gate["can_continue"] is True
    assert gate["issue_count"] == 0
    assert "Status: passed" in render_contract_gate_status(gate)


def test_contract_gate_operator_blocks_issues_with_prompts() -> None:
    gate = ContractGateOperator().evaluate(
        {
            "Mission": [ContractIssue("Mission.id", "required field missing")],
            "Message": [],
        }
    )

    assert gate["status"] == "blocked"
    assert gate["can_continue"] is False
    assert gate["blocking_definitions"] == ["Mission"]
    assert "Mission.id" in gate["correction_prompts"][0]


def test_forge_task_validator_rejects_missing_fields() -> None:
    issues = validate_forge_tasks([{"id": "TASK-0001-001"}])

    assert issues
    assert any(issue.path.endswith(".title") for issue in issues)
