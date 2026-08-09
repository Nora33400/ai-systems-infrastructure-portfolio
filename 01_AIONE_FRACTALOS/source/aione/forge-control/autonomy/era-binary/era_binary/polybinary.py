"""PolyBinary manifest validation and bounded morphology selection."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .scheduler import ComplexityVector, plan_execution


class PolyBinaryError(ValueError):
    pass


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_polybinary(cir: dict[str, Any]) -> dict[str, Any]:
    manifest = {
        "schema": "aione.polybinary.v1",
        "program": cir["program"],
        "intent": "execute-bounded-cognitive-program",
        "cirHash": cir["cirHash"],
        "morphologies": [
            {"id": "CPU_ONLY", "requiresGpuCount": 0, "maxTemperatureCelsius": None},
            {"id": "CPU_GPU", "requiresGpuCount": 1, "maxTemperatureCelsius": 81},
            {"id": "MULTI_GPU", "requiresGpuCount": 2, "maxTemperatureCelsius": 81},
        ],
        "securityPolicy": cir["security"],
        "fallbackTree": ["MULTI_GPU", "CPU_GPU", "CPU_ONLY", "STOP_WITH_EVIDENCE"],
        "verification": ["cir-validation", "resource-budget", "evidence-chain"],
    }
    manifest["manifestHash"] = _hash(manifest)
    return manifest


def select_morphology(
    manifest: dict[str, Any], topology: dict[str, Any], complexity: ComplexityVector | None = None
) -> dict[str, Any]:
    if manifest.get("schema") != "aione.polybinary.v1":
        raise PolyBinaryError("unsupported PolyBinary schema")
    expected = manifest.get("manifestHash")
    candidate = {key: value for key, value in manifest.items() if key != "manifestHash"}
    if not expected or _hash(candidate) != expected:
        raise PolyBinaryError("PolyBinary manifest integrity failure")
    plan = plan_execution(topology, complexity)
    allowed = {item["id"] for item in manifest.get("morphologies", [])}
    if plan["morphology"] not in allowed:
        raise PolyBinaryError("scheduled morphology is absent from manifest")
    return {"ok": True, "manifestHash": expected, "plan": plan}

