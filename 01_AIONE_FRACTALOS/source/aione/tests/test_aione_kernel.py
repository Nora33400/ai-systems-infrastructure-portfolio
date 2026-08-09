from __future__ import annotations

from aione_forge.bus import MessageBus, make_message, validate_message_shape
from aione_forge.kernel import AioneKernel
from aione_forge.mission import MissionParser
from aione_forge.operators import MemoryOperator, RoutingOperator, TruthGateOperator


def test_mission_parser_creates_structured_mission() -> None:
    mission = MissionParser().parse("Construire AIONE avec une forge autonome verifiee.")

    assert mission["id"] == "MISSION-0001"
    assert mission["risk_level"] == "medium"
    assert mission["depth"] == "deep"
    assert mission["verification_required"] is True
    assert "controlled-autonomy" in mission["constraints"]


def test_message_bus_accepts_valid_mission_task() -> None:
    message = make_message(
        message_id="MSG-0001",
        mission_id="MISSION-0001",
        source="mission_parser",
        destination="routing_operator",
        bus="mission_bus",
        message_type="task",
        payload={"objective": "test"},
    )
    bus = MessageBus()
    bus.publish(message)

    assert validate_message_shape(message) == []
    assert bus.drain("mission_bus") == [message]


def test_routing_operator_selects_planner_for_deep_mission() -> None:
    mission = MissionParser().parse("Concevoir une architecture AIONE autonome.")
    route = RoutingOperator().route(mission)

    assert route["selected_role"] == "planner_deep"
    assert route["candidate_models"]
    assert route["requires_availability_check"] is True


def test_truth_gate_and_memory_operator_create_artifacts() -> None:
    proof = TruthGateOperator().create_proof_capsule(
        target_artifact="artifact.json",
        claims=["artifact exists"],
        sources=["source.md"],
        tests=["test.py"],
    )
    tile = MemoryOperator().create_tile(
        title="Kernel tile",
        summary="A structured memory tile.",
        source_refs=["source.md"],
        tags=["kernel"],
        claims=["artifact exists"],
    )

    assert proof["status"] == "passed"
    assert proof["confidence"] >= 0.75
    assert tile["verification_status"] == "partial"
    assert tile["hash"]


def test_kernel_runs_first_executable_cycle() -> None:
    result = AioneKernel(memory_context={"query": "kernel", "result_count": 1, "items": []}).run_intent(
        "Construire AIONE avec une forge autonome verifiee.",
        cycle=1,
    )

    assert result["mission"]["id"] == "MISSION-0001"
    assert result["messages"][0]["bus"] == "mission_bus"
    assert result["messages"][0]["payload"]["memory_context"]["result_count"] == 1
    assert result["memory_context"]["result_count"] == 1
    assert result["layer_runtime"]["packet"]["action"] == "READ_CPU"
    assert result["layer_runtime"]["result"]["status"] == "done"
    assert result["route_decision"]["selected_role"] in {"planner_deep", "code"}
    assert result["proof_capsule"]["status"] in {"passed", "warn"}
    assert result["proof_capsule"]["memory_check"]["status"] in {"passed", "unverified"}
    assert result["knowledge_tile"]["compression_level"] == "summary"
    assert result["patch_ledger"]["id"].startswith("PATCH-")
    assert result["patch_ledger"]["status"] == "applied"


def test_truth_gate_detects_local_memory_contradiction() -> None:
    proof = TruthGateOperator().create_proof_capsule(
        target_artifact="artifact.json",
        claims=["AIONE can produce a structured mission"],
        sources=["source.md"],
        tests=["test.py"],
        memory_records=[
            {
                "id": "KT-CONTRA",
                "claims": ["AIONE cannot produce a structured mission"],
            }
        ],
    )

    assert proof["status"] == "failed"
    assert proof["memory_check"]["contradictions"]
