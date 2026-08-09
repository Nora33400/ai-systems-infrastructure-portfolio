from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from unicodedata import normalize

from .io import append_jsonl, utc_ts


ACTIONS = {"READ_CPU", "OPTIMIZE_MEMORY", "RUN_PYTHON_SAFE", "WRITE_BIOS", "UNKNOWN"}


@dataclass(frozen=True)
class PolicyDecision:
    approved: bool
    mode: str
    permissions: list[str]
    reason: str


class PolicyRules:
    def __init__(self) -> None:
        self.rules = {
            "READ_CPU": PolicyDecision(True, "simulation", ["read_system_state"], "Read-only system observation."),
            "OPTIMIZE_MEMORY": PolicyDecision(True, "simulation", ["simulate_memory_optimization"], "Optimization must start in simulation."),
            "RUN_PYTHON_SAFE": PolicyDecision(True, "safe", ["run_safe_python"], "Only allow whitelisted pure Python commands."),
            "WRITE_BIOS": PolicyDecision(False, "blocked", [], "Firmware mutation is forbidden in MVP runtime."),
            "UNKNOWN": PolicyDecision(False, "blocked", [], "Unknown actions are blocked by default."),
        }

    def decide(self, action: str) -> PolicyDecision:
        return self.rules.get(action, self.rules["UNKNOWN"])


def validate_layer_packet(packet: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in ["id", "mission_id", "source_layer", "target_layer", "action", "risk", "mode", "reason", "created_at"]:
        if not isinstance(packet.get(field), str) or not packet.get(field):
            issues.append(f"{field} must be a non-empty string")
    if packet.get("action") not in ACTIONS:
        issues.append(f"invalid action: {packet.get('action')}")
    if packet.get("risk") not in {"low", "medium", "high", "critical", "unknown"}:
        issues.append(f"invalid risk: {packet.get('risk')}")
    if packet.get("mode") not in {"safe", "simulation", "blocked"}:
        issues.append(f"invalid mode: {packet.get('mode')}")
    if not isinstance(packet.get("priority"), int) or not 0 <= packet.get("priority", -1) <= 10:
        issues.append("priority must be an integer from 0 to 10")
    if not isinstance(packet.get("payload"), dict):
        issues.append("payload must be an object")
    if not isinstance(packet.get("permissions"), list):
        issues.append("permissions must be a list")
    if not isinstance(packet.get("approved"), bool):
        issues.append("approved must be a boolean")
    return issues


def validate_layer_execution_result(result: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in ["packet_id", "status", "backend", "created_at"]:
        if not isinstance(result.get(field), str) or not result.get(field):
            issues.append(f"{field} must be a non-empty string")
    if result.get("status") not in {"done", "blocked", "error"}:
        issues.append(f"invalid status: {result.get('status')}")
    if not isinstance(result.get("metrics"), dict):
        issues.append("metrics must be an object")
    if not isinstance(result.get("output"), dict):
        issues.append("output must be an object")
    if not isinstance(result.get("risk_triggered"), bool):
        issues.append("risk_triggered must be a boolean")
    return issues


class IntentLayer:
    def __init__(self, policies: PolicyRules | None = None):
        self.policies = policies or PolicyRules()

    def ask(self, command: str, mission_id: str = "MISSION-0001") -> dict[str, Any]:
        cleaned = " ".join(command.strip().split())
        if not cleaned:
            raise ValueError("command cannot be empty")

        action = self._translate_action(cleaned)
        risk = self._risk_for_action(action)
        decision = self.policies.decide(action)
        packet = {
            "id": self._packet_id(mission_id, cleaned),
            "mission_id": mission_id,
            "source_layer": "IntentLayer",
            "target_layer": "ExecLayer",
            "action": action,
            "risk": risk,
            "mode": decision.mode,
            "priority": self._priority(risk),
            "payload": {
                "command": cleaned,
            },
            "permissions": decision.permissions,
            "approved": decision.approved,
            "reason": decision.reason,
            "created_at": utc_ts(),
        }
        issues = validate_layer_packet(packet)
        if issues:
            raise ValueError("; ".join(issues))
        return packet

    def _translate_action(self, command: str) -> str:
        lowered = _ascii_lower(command)
        if "bios" in lowered or "uefi" in lowered or "firmware" in lowered:
            return "WRITE_BIOS"
        if "cpu" in lowered or "processeur" in lowered:
            return "READ_CPU"
        if "memoire" in lowered or "ram" in lowered:
            return "OPTIMIZE_MEMORY"
        if "python" in lowered and ("safe" in lowered or "sur" in lowered):
            return "RUN_PYTHON_SAFE"
        return "UNKNOWN"

    def _risk_for_action(self, action: str) -> str:
        return {
            "READ_CPU": "low",
            "OPTIMIZE_MEMORY": "medium",
            "RUN_PYTHON_SAFE": "medium",
            "WRITE_BIOS": "critical",
            "UNKNOWN": "unknown",
        }[action]

    def _priority(self, risk: str) -> int:
        return {
            "low": 3,
            "medium": 6,
            "high": 8,
            "critical": 10,
            "unknown": 0,
        }[risk]

    def _packet_id(self, mission_id: str, command: str) -> str:
        digest = sha256(f"{mission_id}|{command}".encode("utf-8")).hexdigest()[:8].upper()
        return f"LP-{digest}"


class Backend(Protocol):
    name: str

    def run(self, packet: dict[str, Any]) -> dict[str, Any]:
        ...


class SimulationBackend:
    name = "simulation"

    def run(self, packet: dict[str, Any]) -> dict[str, Any]:
        action = packet["action"]
        if action == "READ_CPU":
            output = {"cpu_usage": "simulation: 34%", "temperature_c": "simulation: 58"}
        elif action == "OPTIMIZE_MEMORY":
            output = {"result": "simulation: cache cleanup planned", "ram_saved_mb": 128}
        elif action == "RUN_PYTHON_SAFE":
            output = {"result": "simulation: safe python command accepted"}
        else:
            output = {"result": "simulation: no action executed"}
        return self._result(packet, "done", output)

    def _result(self, packet: dict[str, Any], status: str, output: dict[str, Any]) -> dict[str, Any]:
        return {
            "packet_id": packet["id"],
            "status": status,
            "backend": self.name,
            "metrics": {
                "latency_ms": 0,
                "cost_class": "low",
            },
            "output": output,
            "risk_triggered": False,
            "created_at": utc_ts(),
        }


class PythonBackend:
    name = "python_safe"

    def run(self, packet: dict[str, Any]) -> dict[str, Any]:
        command = packet.get("payload", {}).get("command", "").lower()
        if packet["action"] != "RUN_PYTHON_SAFE":
            return self._result(packet, "error", {"error": "PythonBackend only handles RUN_PYTHON_SAFE"}, True)
        if "time" in command:
            output = {"result": utc_ts()}
        else:
            output = {"result": "safe python noop"}
        return self._result(packet, "done", output, False)

    def _result(self, packet: dict[str, Any], status: str, output: dict[str, Any], risk_triggered: bool) -> dict[str, Any]:
        return {
            "packet_id": packet["id"],
            "status": status,
            "backend": self.name,
            "metrics": {
                "latency_ms": 0,
                "cost_class": "low",
            },
            "output": output,
            "risk_triggered": risk_triggered,
            "created_at": utc_ts(),
        }


class ExecLayer:
    def __init__(self, exchange_log_path: Path | None = None):
        self.exchange_log_path = exchange_log_path
        self.simulation = SimulationBackend()
        self.python = PythonBackend()

    def run(self, packet: dict[str, Any]) -> dict[str, Any]:
        packet_issues = validate_layer_packet(packet)
        if packet_issues:
            raise ValueError("; ".join(packet_issues))

        if not packet["approved"]:
            result = {
                "packet_id": packet["id"],
                "status": "blocked",
                "backend": "policy",
                "metrics": {
                    "latency_ms": 0,
                    "cost_class": "none",
                },
                "output": {
                    "reason": packet["reason"],
                },
                "risk_triggered": packet["risk"] in {"high", "critical", "unknown"},
                "created_at": utc_ts(),
            }
        elif packet["mode"] == "safe" and packet["action"] == "RUN_PYTHON_SAFE":
            result = self.python.run(packet)
        else:
            result = self.simulation.run(packet)

        result_issues = validate_layer_execution_result(result)
        if result_issues:
            raise ValueError("; ".join(result_issues))
        self._log_exchange(packet, result)
        return result

    def _log_exchange(self, packet: dict[str, Any], result: dict[str, Any]) -> None:
        if not self.exchange_log_path:
            return
        append_jsonl(
            self.exchange_log_path,
            {
                "ts": utc_ts(),
                "type": "layer_exchange",
                "packet": packet,
                "result": result,
            },
        )


class DynamicLayerRuntime:
    def __init__(self, exchange_log_path: Path | None = None):
        self.intent = IntentLayer()
        self.exec = ExecLayer(exchange_log_path=exchange_log_path)

    def ask(self, command: str, mission_id: str = "MISSION-0001") -> dict[str, Any]:
        packet = self.intent.ask(command, mission_id=mission_id)
        result = self.exec.run(packet)
        return {
            "packet": packet,
            "result": result,
        }


def render_layer_runtime_status(runtime_result: dict[str, Any]) -> str:
    packet = runtime_result["packet"]
    result = runtime_result["result"]
    return "\n".join(
        [
            "# Layer Runtime Status",
            "",
            f"Packet: {packet['id']}",
            f"Action: {packet['action']}",
            f"Risk: {packet['risk']}",
            f"Mode: {packet['mode']}",
            f"Approved: {packet['approved']}",
            f"Reason: {packet['reason']}",
            "",
            "## Execution",
            "",
            f"Status: {result['status']}",
            f"Backend: {result['backend']}",
            f"Risk triggered: {result['risk_triggered']}",
        ]
    )


def _ascii_lower(text: str) -> str:
    return normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
