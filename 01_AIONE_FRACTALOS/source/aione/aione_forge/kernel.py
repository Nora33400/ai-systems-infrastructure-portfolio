from __future__ import annotations

from pathlib import Path
from typing import Any

from .bus import MessageBus, make_message
from .layers import DynamicLayerRuntime, render_layer_runtime_status
from .mission import MissionParser
from .operators import MemoryOperator, PatchLedgerOperator, RoutingOperator, TruthGateOperator


class AioneKernel:
    def __init__(
        self,
        exchange_log_path: str | None = None,
        memory_records: list[dict[str, Any]] | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> None:
        self.parser = MissionParser()
        self.bus = MessageBus()
        self.router = RoutingOperator()
        self.truth_gate = TruthGateOperator()
        self.memory = MemoryOperator()
        self.patch_ledger = PatchLedgerOperator()
        self.memory_records = memory_records or []
        self.memory_context = memory_context or {"query": "", "result_count": 0, "items": []}
        self.layer_runtime = DynamicLayerRuntime(exchange_log_path=None if exchange_log_path is None else Path(exchange_log_path))

    def run_intent(self, intent_raw: str, cycle: int) -> dict[str, Any]:
        mission = self.parser.parse(intent_raw, mission_id=f"MISSION-{cycle:04d}")
        message = make_message(
            message_id=f"MSG-{cycle:04d}-001",
            mission_id=mission["id"],
            source="mission_parser",
            destination="routing_operator",
            bus="mission_bus",
            message_type="task",
            payload={
                "objective": mission["objective"],
                "expected_outputs": mission["expected_outputs"],
                "memory_context": self.memory_context,
            },
            priority="high" if mission["risk_level"] in {"high", "critical"} else "normal",
            confidence=0.82,
            verification_status="pending",
            trace=[mission["id"]],
        )
        self.bus.publish(message)

        route_decision = self.router.route(mission, message)
        layer_runtime = self.layer_runtime.ask(
            "lis l'etat CPU",
            mission_id=mission["id"],
        )
        proof_claims = [
            "mission parsed into a structured contract",
            "message routed through a controlled bus",
            "model role selected before concrete model usage",
            "intent layer packet passed through controlled execution layer",
        ]
        proof_capsule = self.truth_gate.create_proof_capsule(
            target_artifact="kernel/cycle_kernel.json",
            claims=proof_claims,
            sources=[
                "cahier_des_charges/AIONE_CDC_v0.md",
                "schemas/aione_contracts.schema.json",
                "aione_forge/layers.py",
            ],
            tests=[
                "tests/test_aione_kernel.py",
                "tests/test_aione_forge.py",
                "tests/test_aione_layers.py",
            ],
            risks=[
                "heuristic parsing is not semantic understanding",
                "model availability still requires live verification",
                "execution layer is simulation-first and not hardware control",
            ],
            memory_records=self.memory_records,
        )
        knowledge_tile = self.memory.create_tile(
            title="AIONE executable kernel cycle",
            summary="First executable cycle connecting MissionParser, MessageBus, RoutingOperator, TruthGateOperator and MemoryOperator.",
            source_refs=[
                "aione_forge/kernel.py",
                "cahier_des_charges/AIONE_CDC_v0.md",
            ],
            tags=[
                "kernel",
                "mission",
                "message_bus",
                "layer_runtime",
                "routing",
                "proof",
                "memory",
            ],
            claims=[
                *proof_claims,
                "AIONE can produce a structured mission, message, layer packet, execution result, route decision, proof capsule and memory tile in one cycle.",
            ],
            relations=[
                mission["id"],
                message["id"],
                layer_runtime["packet"]["id"],
                proof_capsule["id"],
            ],
        )
        patch_ledger = self.patch_ledger.create_patch_ledger(
            mission_id=mission["id"],
            change_summary="Run first executable AIONE kernel cycle.",
            files_touched=[
                "aione_forge/kernel.py",
                "aione_forge/layers.py",
                "aione_forge/operators.py",
            ],
            reason="Persist mission, layer runtime, routing, proof and memory artifacts for each Forge cycle.",
            verification=[
                "tests/test_aione_kernel.py",
                "tests/test_aione_layers.py",
                "tests/test_aione_forge.py",
            ],
            rollback_plan="Disable kernel persistence wiring and keep generated JSON artifacts only.",
            before_state="contracts and kernel artifacts only",
            after_state="kernel artifacts plus persistent store records",
        )

        return {
            "mission": mission,
            "messages": self.bus.drain(),
            "layer_runtime": layer_runtime,
            "route_decision": route_decision,
            "proof_capsule": proof_capsule,
            "knowledge_tile": knowledge_tile,
            "patch_ledger": patch_ledger,
            "memory_context": self.memory_context,
        }


def render_kernel_status(kernel_result: dict[str, Any]) -> str:
    mission = kernel_result["mission"]
    route = kernel_result["route_decision"]
    layer = kernel_result["layer_runtime"]
    proof = kernel_result["proof_capsule"]
    tile = kernel_result["knowledge_tile"]
    patch = kernel_result["patch_ledger"]
    context = kernel_result.get("memory_context", {"result_count": 0})
    return "\n".join(
        [
            "# Kernel Status",
            "",
            f"Mission: {mission['id']} - {mission['title']}",
            f"Depth: {mission['depth']}",
            f"Risk: {mission['risk_level']}",
            f"Autonomy: {mission['autonomy_level']}",
            f"Memory context items: {context.get('result_count', 0)}",
            "",
            "## Route",
            "",
            f"Selected role: {route['selected_role']}",
            f"Cost class: {route['cost_class']}",
            f"Fallback role: {route['fallback_role']}",
            "",
            "## Layer Runtime",
            "",
            f"Action: {layer['packet']['action']}",
            f"Mode: {layer['packet']['mode']}",
            f"Execution status: {layer['result']['status']}",
            f"Backend: {layer['result']['backend']}",
            "",
            "## Proof",
            "",
            f"Proof capsule: {proof['id']}",
            f"Status: {proof['status']}",
            f"Confidence: {proof['confidence']}",
            "",
            "## Memory",
            "",
            f"Knowledge tile: {tile['id']}",
            f"Verification: {tile['verification_status']}",
            "",
            "## Patch Ledger",
            "",
            f"Patch ledger: {patch['id']}",
            f"Status: {patch['status']}",
        ]
    )


def render_layer_status(kernel_result: dict[str, Any]) -> str:
    return render_layer_runtime_status(kernel_result["layer_runtime"])
