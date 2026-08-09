"""Side-effect-free reference CIR interpreter with hash-chained evidence."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import time
from typing import Any, Callable

from .hci import HciError, validate_cir


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class InterpreterPolicy:
    max_steps: int = 256
    wall_clock_ms: int = 30_000
    max_artifact_bytes: int = 262_144
    allow_network: bool = False
    allow_process_execution: bool = False
    allow_filesystem_write: bool = False


class EvidenceChain:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "index": len(self.events),
            "type": event_type,
            "previousHash": self.events[-1]["eventHash"] if self.events else None,
            "payload": payload,
        }
        event["eventHash"] = sha256(_canonical(event).encode("utf-8")).hexdigest()
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous = None
        for index, current in enumerate(self.events):
            candidate = {key: value for key, value in current.items() if key != "eventHash"}
            if current.get("index") != index or current.get("previousHash") != previous:
                return False
            if sha256(_canonical(candidate).encode("utf-8")).hexdigest() != current.get("eventHash"):
                return False
            previous = current["eventHash"]
        return True


ModelProvider = Callable[[str, dict[str, Any]], dict[str, Any]]
Verifier = Callable[[dict[str, Any], list[str]], dict[str, Any]]


def _default_model_provider(role: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate": f"simulated:{role}",
        "contextArtifacts": sorted(context),
        "executed": False,
        "confidence": 0.5,
        "source": "REFERENCE_SIMULATOR",
    }


def _default_verifier(candidate: dict[str, Any], checks: list[str]) -> dict[str, Any]:
    safe_shape = isinstance(candidate, dict) and candidate.get("executed") is not True
    has_external_evidence = safe_shape and candidate.get("externalEvidenceVerified") is True
    return {
        "passed": has_external_evidence and bool(checks),
        "score": 1.0 if has_external_evidence and checks else 0.0,
        "checks": [{"id": check, "passed": has_external_evidence} for check in checks],
        "evidence": "MISSING_EXTERNAL_VERIFIER_EVIDENCE" if not has_external_evidence else "external-verifier-evidence",
        "candidateShapeSafe": safe_shape,
    }


def interpret_cir(
    cir: dict[str, Any],
    *,
    inputs: dict[str, Any] | None = None,
    policy: InterpreterPolicy | None = None,
    model_provider: ModelProvider | None = None,
    verifier: Verifier | None = None,
) -> dict[str, Any]:
    validation = validate_cir(cir)
    policy = policy or InterpreterPolicy()
    if policy.allow_network or policy.allow_process_execution or policy.allow_filesystem_write:
        raise HciError("the HCI/0.1 reference interpreter cannot receive expanded authorities")
    if len(cir["instructions"]) > policy.max_steps:
        raise HciError("CIR exceeds interpreter step budget")
    model_provider = model_provider or _default_model_provider
    verifier = verifier or _default_verifier
    started = time.monotonic()
    artifacts: dict[str, Any] = {"input": inputs or {}}
    evidence = EvidenceChain()
    evidence.append("RUN_STARTED", {"program": cir["program"], "cirHash": cir["cirHash"]})

    for instruction in cir["instructions"]:
        elapsed_ms = (time.monotonic() - started) * 1_000
        if elapsed_ms > min(policy.wall_clock_ms, cir["resources"]["wallClockMsMax"]):
            evidence.append("BUDGET_EXCEEDED", {"elapsedMs": round(elapsed_ms, 3)})
            raise HciError("CIR wall-clock budget exceeded")
        opcode = instruction["opcode"]
        name = instruction["artifact"]
        args = instruction["arguments"]
        if opcode == "CONTEXT_OPEN":
            result = {"scope": args.get("scope", "TASK"), "source": args.get("source"), "input": artifacts["input"]}
        elif opcode == "REPRESENT":
            result = {
                "representation": args["representation"],
                "source": args["source"],
                "constraints": [],
                "unknowns": [],
                "provenance": cir["sourceHash"],
            }
        elif opcode == "MODEL_ASSIGN_ROLE":
            result = {
                "role": args.get("role", name),
                "preferredDevice": args.get("device", "CPU"),
                "fallback": args.get("fallback", "CPU"),
                "modelBound": False,
            }
        elif opcode == "HYPOTHESIS_CREATE":
            model_name = args["model"]
            role = artifacts.get(model_name, {}).get("role", model_name)
            result = model_provider(role, artifacts.copy())
            if not isinstance(result, dict) or result.get("executed") is True:
                raise HciError("model provider returned an unsafe or invalid artifact")
        elif opcode == "VERIFY_EXECUTION":
            checks = args["checks"]
            result = {
                target: verifier(artifacts.get(target, {}), checks)
                for target in args["targets"]
            }
        elif opcode == "SELECT_ROBUST_PATH":
            verification = artifacts.get("verification", {})
            ranked = []
            for source in args["sources"]:
                verdict = verification.get(source, {})
                ranked.append((float(verdict.get("score", 0)), source, verdict.get("passed") is True))
            eligible = [item for item in ranked if item[2]]
            selected = max(eligible, default=(0.0, None, False), key=lambda item: (item[0], item[1] or ""))
            result = {
                "selected": selected[1],
                "score": selected[0],
                "strategy": args.get("strategy", "maximum_verified_score"),
                "artifact": artifacts.get(selected[1]) if selected[1] else None,
            }
        elif opcode == "MEMORY_PROMOTE":
            result = {
                "address": args["address"],
                "artifact": artifacts.get(args["artifact"]),
                "persisted": False,
                "reason": "REFERENCE_INTERPRETER_SIMULATION_ONLY",
            }
        elif opcode == "SIMULATE_IF":
            result = {"simulated": True, "condition": args.get("if"), "mutated": False}
        else:
            raise HciError(f"opcode is registered but not implemented by reference interpreter: {opcode}")
        if len(_canonical(result).encode("utf-8")) > policy.max_artifact_bytes:
            raise HciError(f"artifact exceeds byte budget: {name}")
        artifacts[name] = result
        evidence.append("INSTRUCTION_COMPLETED", {"id": instruction["id"], "opcode": opcode, "artifact": name})

    evidence.append("RUN_COMPLETED", {"steps": len(cir["instructions"]), "evidenceValid": True})
    return {
        "schema": "aione.hci-run-result.v1",
        "ok": True,
        "program": cir["program"],
        "validation": validation,
        "artifacts": artifacts,
        "evidence": evidence.events,
        "evidenceValid": evidence.verify(),
        "sideEffects": [],
        "elapsedMs": round((time.monotonic() - started) * 1_000, 3),
    }
