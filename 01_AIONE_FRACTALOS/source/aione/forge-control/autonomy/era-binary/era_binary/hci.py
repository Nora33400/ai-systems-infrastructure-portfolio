"""Minimal HCI parser and typed CIR compiler.

HCI/0.1 is deliberately small and line-oriented. It describes intent and
contracts. It never evaluates Python, shell, templates, or model output.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
from typing import Any


IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
MEMORY_ADDRESS = re.compile(
    r"^memory://(?:project|task|context|cause|decision)/[A-Za-z0-9._~/-]{1,240}$"
)
MAX_SOURCE_CHARS = 128_000
MAX_INSTRUCTIONS = 256


class HciError(ValueError):
    """Raised when an HCI program or CIR violates its contract."""


@dataclass(frozen=True)
class HciStatement:
    kind: str
    name: str
    arguments: dict[str, Any]
    line: int


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_identifier(value: str, label: str, line: int) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise HciError(f"line {line}: invalid {label}: {value!r}")
    return value


def _attributes(tokens: list[str], line: int) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            raise HciError(f"line {line}: expected key=value, got {token!r}")
        key, value = token.split("=", 1)
        _require_identifier(key, "attribute", line)
        if not value or len(value) > 2_048:
            raise HciError(f"line {line}: invalid value for {key}")
        if key in result:
            raise HciError(f"line {line}: duplicate attribute {key}")
        result[key] = value
    return result


def _split_list(value: str, line: int) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items or len(items) > 64:
        raise HciError(f"line {line}: invalid bounded list")
    return items


def parse_hci(source: str) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip():
        raise HciError("HCI source is empty")
    if len(source) > MAX_SOURCE_CHARS:
        raise HciError("HCI source exceeds 128000 characters")

    meaningful: list[tuple[int, str]] = []
    for number, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        meaningful.append((number, line))
    if len(meaningful) < 2:
        raise HciError("HCI program requires a header and closing brace")

    header_line, header = meaningful[0]
    match = re.fullmatch(r"program\s+([A-Za-z][A-Za-z0-9_-]{0,63})\s*\{", header)
    if not match:
        raise HciError(f"line {header_line}: expected 'program Name {{'")
    if meaningful[-1][1] != "}":
        raise HciError(f"line {meaningful[-1][0]}: expected closing brace")

    statements: list[HciStatement] = []
    names: set[str] = set()
    for line_number, line in meaningful[1:-1]:
        if "{" in line or "}" in line or ";" in line:
            raise HciError(f"line {line_number}: nested blocks and semicolons are not HCI/0.1")
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError as error:
            raise HciError(f"line {line_number}: {error}") from error
        if not tokens:
            continue
        keyword = tokens[0].lower()
        statement: HciStatement
        if keyword in {"context", "model"}:
            if len(tokens) < 3:
                raise HciError(f"line {line_number}: incomplete {keyword} statement")
            name = _require_identifier(tokens[1], keyword, line_number)
            statement = HciStatement(keyword, name, _attributes(tokens[2:], line_number), line_number)
        elif keyword == "represent":
            if len(tokens) < 4 or tokens[2].lower() != "as":
                raise HciError(f"line {line_number}: expected 'represent source as type'")
            source_name = _require_identifier(tokens[1], "representation source", line_number)
            representation = _require_identifier(tokens[3], "representation type", line_number)
            attrs = _attributes(tokens[4:], line_number)
            name = _require_identifier(attrs.pop("target", f"{source_name}_view"), "representation target", line_number)
            statement = HciStatement(
                "represent", name, {"source": source_name, "representation": representation, **attrs}, line_number
            )
        elif keyword == "hypothesis":
            if len(tokens) < 4 or tokens[2].lower() != "from":
                raise HciError(f"line {line_number}: expected 'hypothesis name from model'")
            name = _require_identifier(tokens[1], "hypothesis", line_number)
            model = _require_identifier(tokens[3], "model reference", line_number)
            statement = HciStatement(
                "hypothesis", name, {"model": model, **_attributes(tokens[4:], line_number)}, line_number
            )
        elif keyword == "verify":
            if len(tokens) < 3:
                raise HciError(f"line {line_number}: incomplete verify statement")
            targets = _split_list(tokens[1], line_number)
            attrs = _attributes(tokens[2:], line_number)
            checks = _split_list(attrs.pop("with", ""), line_number)
            name = _require_identifier(attrs.pop("target", "verification"), "verification target", line_number)
            statement = HciStatement("verify", name, {"targets": targets, "checks": checks, **attrs}, line_number)
        elif keyword == "select":
            if len(tokens) < 3:
                raise HciError(f"line {line_number}: incomplete select statement")
            name = _require_identifier(tokens[1], "selection", line_number)
            attrs = _attributes(tokens[2:], line_number)
            sources = _split_list(attrs.pop("from", ""), line_number)
            statement = HciStatement("select", name, {"sources": sources, **attrs}, line_number)
        elif keyword == "persist":
            if len(tokens) != 3 or not tokens[2].startswith("to="):
                raise HciError(f"line {line_number}: expected 'persist artifact to=memory://...'")
            artifact = _require_identifier(tokens[1], "persisted artifact", line_number)
            address = tokens[2][3:]
            if not MEMORY_ADDRESS.fullmatch(address) or ".." in address:
                raise HciError(f"line {line_number}: invalid or unsafe memory address")
            statement = HciStatement("persist", f"persist_{artifact}", {"artifact": artifact, "address": address}, line_number)
        elif keyword == "simulate":
            if len(tokens) < 3:
                raise HciError(f"line {line_number}: incomplete simulate statement")
            name = _require_identifier(tokens[1], "simulation", line_number)
            statement = HciStatement("simulate", name, _attributes(tokens[2:], line_number), line_number)
        else:
            raise HciError(f"line {line_number}: unknown HCI statement {tokens[0]!r}")

        if statement.name in names:
            raise HciError(f"line {line_number}: duplicate artifact {statement.name}")
        names.add(statement.name)
        statements.append(statement)
        if len(statements) > MAX_INSTRUCTIONS:
            raise HciError("HCI program exceeds 256 instructions")

    return {
        "schema": "aione.hci-program.v1",
        "language": "HCI/0.1",
        "program": match.group(1),
        "statements": [
            {"kind": item.kind, "name": item.name, "arguments": item.arguments, "line": item.line}
            for item in statements
        ],
        "sourceHash": sha256(source.encode("utf-8")).hexdigest(),
    }


_OPCODE_BY_KIND = {
    "context": "CONTEXT_OPEN",
    "represent": "REPRESENT",
    "model": "MODEL_ASSIGN_ROLE",
    "hypothesis": "HYPOTHESIS_CREATE",
    "verify": "VERIFY_EXECUTION",
    "select": "SELECT_ROBUST_PATH",
    "persist": "MEMORY_PROMOTE",
    "simulate": "SIMULATE_IF",
}


def compile_hci(source_or_ast: str | dict[str, Any]) -> dict[str, Any]:
    ast = parse_hci(source_or_ast) if isinstance(source_or_ast, str) else source_or_ast
    if ast.get("schema") != "aione.hci-program.v1":
        raise HciError("unsupported HCI AST schema")
    instructions = []
    previous: str | None = None
    for index, statement in enumerate(ast.get("statements", []), start=1):
        opcode = _OPCODE_BY_KIND.get(statement.get("kind"))
        if not opcode:
            raise HciError(f"unsupported AST statement: {statement.get('kind')}")
        instruction_id = f"i{index:03d}_{statement['name']}"
        dependencies = [previous] if previous else []
        instructions.append(
            {
                "id": instruction_id,
                "opcode": opcode,
                "artifact": statement["name"],
                "arguments": statement.get("arguments", {}),
                "dependencies": dependencies,
                "contract": {
                    "simulationOnly": True,
                    "sideEffects": "NONE",
                    "reversible": True,
                    "timeoutMs": 5_000,
                    "maxOutputBytes": 262_144,
                },
                "sourceLine": statement.get("line"),
            }
        )
        previous = instruction_id
    cir = {
        "schema": "aione.cir.v1",
        "program": ast["program"],
        "sourceHash": ast["sourceHash"],
        "instructions": instructions,
        "resources": {
            "cpuThreadsMax": 4,
            "ramBytesMax": 536_870_912,
            "vramBytesMax": 2_147_483_648,
            "wallClockMsMax": 30_000,
        },
        "security": {
            "network": "DENY",
            "filesystem": "SIMULATION_ONLY",
            "processExecution": "DENY",
            "permissionExpansion": "DENY",
        },
        "metadata": {"compiler": "aione-era-reference/0.1", "astHash": _digest(ast)},
    }
    cir["cirHash"] = _digest(cir)
    validate_cir(cir)
    return cir


def validate_cir(cir: dict[str, Any], instruction_registry_path: Path | None = None) -> dict[str, Any]:
    if cir.get("schema") != "aione.cir.v1":
        raise HciError("unsupported CIR schema")
    instructions = cir.get("instructions")
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= MAX_INSTRUCTIONS:
        raise HciError("CIR requires between 1 and 256 instructions")

    registry_path = instruction_registry_path or Path(__file__).resolve().parents[1] / "hci" / "instructions.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    allowed = {item["opcode"] for item in registry["instructions"]}
    seen: set[str] = set()
    for instruction in instructions:
        instruction_id = instruction.get("id")
        if not isinstance(instruction_id, str) or instruction_id in seen:
            raise HciError("CIR instruction IDs must be unique strings")
        seen.add(instruction_id)
        if instruction.get("opcode") not in allowed:
            raise HciError(f"unknown CIR opcode: {instruction.get('opcode')}")
        contract = instruction.get("contract") or {}
        if contract.get("simulationOnly") is not True or contract.get("sideEffects") != "NONE":
            raise HciError("HCI/0.1 only accepts side-effect-free simulation contracts")
        for dependency in instruction.get("dependencies", []):
            if dependency not in seen:
                raise HciError(f"dependency must precede instruction: {dependency}")
        if instruction.get("opcode") == "MEMORY_PROMOTE":
            address = instruction.get("arguments", {}).get("address", "")
            if not MEMORY_ADDRESS.fullmatch(address) or ".." in address:
                raise HciError("unsafe CIR memory address")

    security = cir.get("security") or {}
    expected = {
        "network": "DENY",
        "filesystem": "SIMULATION_ONLY",
        "processExecution": "DENY",
        "permissionExpansion": "DENY",
    }
    if any(security.get(key) != value for key, value in expected.items()):
        raise HciError("CIR root security policy cannot be weakened")
    return {"ok": True, "instructionCount": len(instructions), "opcodes": sorted({i["opcode"] for i in instructions})}

