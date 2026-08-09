from __future__ import annotations

from aione_forge.layers import (
    DynamicLayerRuntime,
    ExecLayer,
    IntentLayer,
    validate_layer_execution_result,
    validate_layer_packet,
)


def test_intent_layer_blocks_firmware_mutation() -> None:
    packet = IntentLayer().ask("modifie le BIOS", mission_id="MISSION-0001")

    assert packet["action"] == "WRITE_BIOS"
    assert packet["risk"] == "critical"
    assert packet["approved"] is False
    assert packet["mode"] == "blocked"
    assert validate_layer_packet(packet) == []


def test_exec_layer_returns_blocked_for_denied_packet() -> None:
    packet = IntentLayer().ask("modifie le BIOS", mission_id="MISSION-0001")
    result = ExecLayer().run(packet)

    assert result["status"] == "blocked"
    assert result["backend"] == "policy"
    assert result["risk_triggered"] is True
    assert validate_layer_execution_result(result) == []


def test_dynamic_layer_runtime_runs_safe_simulation() -> None:
    runtime_result = DynamicLayerRuntime().ask("lis l'etat CPU", mission_id="MISSION-0001")

    assert runtime_result["packet"]["action"] == "READ_CPU"
    assert runtime_result["packet"]["approved"] is True
    assert runtime_result["result"]["status"] == "done"
    assert runtime_result["result"]["backend"] == "simulation"


def test_dynamic_layer_runtime_allows_safe_python_backend() -> None:
    runtime_result = DynamicLayerRuntime().ask("python safe time", mission_id="MISSION-0001")

    assert runtime_result["packet"]["action"] == "RUN_PYTHON_SAFE"
    assert runtime_result["packet"]["mode"] == "safe"
    assert runtime_result["result"]["backend"] == "python_safe"
    assert runtime_result["result"]["status"] == "done"
