from __future__ import annotations

from collections import defaultdict
from typing import Any

from .io import utc_ts


MESSAGE_TYPES = {"observation", "task", "claim", "artifact", "decision", "alert", "command"}
PRIORITIES = {"low", "normal", "high", "critical"}
VERIFICATION_STATUSES = {"unverified", "pending", "verified", "rejected"}


def make_message(
    *,
    message_id: str,
    mission_id: str,
    source: str,
    destination: str,
    bus: str,
    message_type: str,
    payload: dict[str, Any],
    priority: str = "normal",
    confidence: float = 0.5,
    verification_status: str = "pending",
    trace: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": message_id,
        "mission_id": mission_id,
        "source": source,
        "destination": destination,
        "bus": bus,
        "type": message_type,
        "payload": payload,
        "priority": priority,
        "confidence": confidence,
        "cost_estimate": {"class": "low"},
        "verification_status": verification_status,
        "trace": trace or [mission_id],
        "created_at": utc_ts(),
    }


def validate_message_shape(message: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required_strings = ["id", "mission_id", "source", "destination", "bus", "type", "priority", "verification_status", "created_at"]
    for field in required_strings:
        if not isinstance(message.get(field), str) or not message.get(field):
            issues.append(f"{field} must be a non-empty string")

    if message.get("type") not in MESSAGE_TYPES:
        issues.append(f"type is invalid: {message.get('type')}")
    if message.get("priority") not in PRIORITIES:
        issues.append(f"priority is invalid: {message.get('priority')}")
    if message.get("verification_status") not in VERIFICATION_STATUSES:
        issues.append(f"verification_status is invalid: {message.get('verification_status')}")

    confidence = message.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        issues.append("confidence must be between 0 and 1")
    if not isinstance(message.get("payload"), dict):
        issues.append("payload must be an object")
    if not isinstance(message.get("cost_estimate"), dict):
        issues.append("cost_estimate must be an object")
    if not isinstance(message.get("trace"), list):
        issues.append("trace must be a list")
    return issues


class MessageBus:
    def __init__(self, accepted_types: dict[str, set[str]] | None = None):
        self.accepted_types = accepted_types or {
            "mission_bus": {"task", "observation", "decision"},
            "research_bus": {"task", "claim", "artifact", "observation"},
            "memory_bus": {"artifact", "claim", "observation"},
            "verification_bus": {"claim", "artifact", "alert"},
            "resource_bus": {"task", "observation", "decision"},
            "safety_bus": {"command", "alert", "decision"},
            "reflection_bus": {"observation", "decision", "claim"},
        }
        self._messages: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def publish(self, message: dict[str, Any]) -> None:
        issues = validate_message_shape(message)
        if issues:
            raise ValueError("; ".join(issues))

        bus = message["bus"]
        if bus not in self.accepted_types:
            raise ValueError(f"unknown bus: {bus}")
        if message["type"] not in self.accepted_types[bus]:
            raise ValueError(f"message type {message['type']} not accepted by {bus}")

        self._messages[bus].append(message)

    def drain(self, bus: str | None = None) -> list[dict[str, Any]]:
        if bus is None:
            drained: list[dict[str, Any]] = []
            for key in list(self._messages):
                drained.extend(self.drain(key))
            return drained

        drained = list(self._messages.get(bus, []))
        self._messages[bus] = []
        return drained

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {bus: list(messages) for bus, messages in self._messages.items()}
