from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOCALITIES = {
    "globalite",
    "mission",
    "recherche",
    "memoire",
    "verification",
    "execution",
    "ressources",
    "securite",
    "dashboard",
}

OPERATORS = {
    "RoutingOperator",
    "PlanningOperator",
    "MemoryOperator",
    "MemoryContextOperator",
    "ContractGateOperator",
    "TruthGateOperator",
    "CompressionOperator",
    "AbstractionOperator",
    "ReflexiveOperator",
    "SchedulerOperator",
    "CodeOperator",
}

MODEL_ROLES = {
    "planner_deep",
    "fast_router_or_summarizer",
    "safety",
    "retrieval_rerank",
    "ocr_document",
    "code",
    "embedding",
}

CONTRACT_DEFINITIONS = {
    "AgentDecision",
    "AgentSpec",
    "AutonomousMissionSpec",
    "ConstraintSet",
    "CostTrace",
    "Mission",
    "Message",
    "MaterializationPlan",
    "MaterializationRequest",
    "MaterializedSlice",
    "MMRProof",
    "OperatorSpec",
    "KnowledgeTile",
    "ProofCapsule",
    "PatchLedger",
    "PotentialState",
    "ModelRole",
    "ForgeTask",
    "LayerPacket",
    "LayerExecutionResult",
}


@dataclass(frozen=True)
class ContractIssue:
    path: str
    message: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_contract_schema(target_workspace: Path) -> Path:
    candidates = [
        target_workspace / "schemas" / "aione_contracts.schema.json",
        repo_root() / "schemas" / "aione_contracts.schema.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_contract_schema(target_workspace: Path) -> tuple[Path, dict[str, Any]]:
    schema_path = find_contract_schema(target_workspace)
    return schema_path, json.loads(schema_path.read_text(encoding="utf-8"))


def schema_definitions(schema: dict[str, Any]) -> list[str]:
    return sorted(schema.get("$defs", {}).keys())


def _required_string(item: dict[str, Any], path: str, field: str, issues: list[ContractIssue]) -> None:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(ContractIssue(f"{path}.{field}", "required non-empty string"))


def _required_bool(item: dict[str, Any], path: str, field: str, issues: list[ContractIssue]) -> None:
    if not isinstance(item.get(field), bool):
        issues.append(ContractIssue(f"{path}.{field}", "required boolean"))


def _required_list(item: dict[str, Any], path: str, field: str, issues: list[ContractIssue]) -> None:
    value = item.get(field)
    if not isinstance(value, list):
        issues.append(ContractIssue(f"{path}.{field}", "required list"))


def _required_nullable_string(item: dict[str, Any], path: str, field: str, issues: list[ContractIssue]) -> None:
    value = item.get(field)
    if value is not None and not isinstance(value, str):
        issues.append(ContractIssue(f"{path}.{field}", "required string or null"))


def validate_forge_tasks(tasks: list[dict[str, Any]]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    for index, task in enumerate(tasks):
        path = f"tasks[{index}]"
        for field in ["id", "title", "locality", "operator", "verification", "status"]:
            _required_string(task, path, field, issues)
        for field in ["source_refs", "artifact_targets"]:
            _required_list(task, path, field, issues)

        if task.get("locality") not in LOCALITIES:
            issues.append(ContractIssue(f"{path}.locality", f"unknown locality: {task.get('locality')}"))
        if task.get("operator") not in OPERATORS:
            issues.append(ContractIssue(f"{path}.operator", f"unknown operator: {task.get('operator')}"))
        if task.get("status") not in {"pending", "running", "blocked", "done", "failed"}:
            issues.append(ContractIssue(f"{path}.status", f"invalid status: {task.get('status')}"))
    return issues


def validate_model_roles(roles: list[dict[str, Any]]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    for index, role in enumerate(roles):
        path = f"model_roles[{index}]"
        for field in ["role", "selection_reason", "cost_class", "notes"]:
            _required_string(role, path, field, issues)
        _required_list(role, path, "candidate_models", issues)
        _required_nullable_string(role, path, "availability_checked_at", issues)
        _required_nullable_string(role, path, "fallback_role", issues)
        _required_bool(role, path, "local_available", issues)
        _required_bool(role, path, "remote_available", issues)

        if role.get("role") not in MODEL_ROLES:
            issues.append(ContractIssue(f"{path}.role", f"unknown model role: {role.get('role')}"))
        if role.get("cost_class") not in {"low", "medium", "high", "unknown"}:
            issues.append(ContractIssue(f"{path}.cost_class", f"invalid cost class: {role.get('cost_class')}"))
        candidate_models = role.get("candidate_models")
        if isinstance(candidate_models, list) and not candidate_models:
            issues.append(ContractIssue(f"{path}.candidate_models", "must contain at least one candidate"))
    return issues


def validate_contract(schema: dict[str, Any], definition_name: str, value: Any, path: str | None = None) -> list[ContractIssue]:
    if definition_name not in schema.get("$defs", {}):
        return [ContractIssue(path or definition_name, f"unknown schema definition: {definition_name}")]
    return _validate_schema_node(schema, schema["$defs"][definition_name], value, path or definition_name)


def validate_runtime_contracts(
    schema: dict[str, Any],
    *,
    tasks: list[dict[str, Any]],
    model_roles: list[dict[str, Any]],
    operator_specs: list[dict[str, Any]],
    agent_specs: list[dict[str, Any]],
    agent_decision: dict[str, Any] | None = None,
    autonomous_mission: dict[str, Any] | None = None,
    mmr_bundle: dict[str, dict[str, Any]] | None = None,
    kernel_result: dict[str, Any],
) -> dict[str, list[ContractIssue]]:
    results: dict[str, list[ContractIssue]] = {
        "AgentDecision": [],
        "AgentSpec": [],
        "AutonomousMissionSpec": [],
        "ConstraintSet": [],
        "CostTrace": [],
        "ForgeTask": [],
        "ModelRole": [],
        "MaterializationPlan": [],
        "MaterializationRequest": [],
        "MaterializedSlice": [],
        "MMRProof": [],
        "OperatorSpec": [],
        "PotentialState": [],
        "Mission": [],
        "Message": [],
        "LayerPacket": [],
        "LayerExecutionResult": [],
        "KnowledgeTile": [],
        "ProofCapsule": [],
        "PatchLedger": [],
    }
    for index, task in enumerate(tasks):
        results["ForgeTask"].extend(validate_contract(schema, "ForgeTask", task, f"ForgeTask[{index}]"))
    for index, role in enumerate(model_roles):
        results["ModelRole"].extend(validate_contract(schema, "ModelRole", role, f"ModelRole[{index}]"))
    for index, operator_spec in enumerate(operator_specs):
        results["OperatorSpec"].extend(validate_contract(schema, "OperatorSpec", operator_spec, f"OperatorSpec[{index}]"))
    for index, agent_spec in enumerate(agent_specs):
        results["AgentSpec"].extend(validate_contract(schema, "AgentSpec", agent_spec, f"AgentSpec[{index}]"))
    if agent_decision is not None:
        results["AgentDecision"].extend(validate_contract(schema, "AgentDecision", agent_decision, "AgentDecision"))
    if autonomous_mission is not None:
        results["AutonomousMissionSpec"].extend(
            validate_contract(schema, "AutonomousMissionSpec", autonomous_mission, "AutonomousMissionSpec")
        )
    if mmr_bundle is not None:
        mmr_contracts = {
            "PotentialState": "potential_state",
            "ConstraintSet": "constraint_set",
            "MaterializationRequest": "materialization_request",
            "MaterializationPlan": "materialization_plan",
            "MaterializedSlice": "materialized_slice",
            "CostTrace": "cost_trace",
            "MMRProof": "mmr_proof",
        }
        for definition_name, bundle_key in mmr_contracts.items():
            if bundle_key in mmr_bundle:
                results[definition_name].extend(
                    validate_contract(schema, definition_name, mmr_bundle[bundle_key], definition_name)
                )

    results["Mission"].extend(validate_contract(schema, "Mission", kernel_result["mission"], "Mission"))
    for index, message in enumerate(kernel_result["messages"]):
        results["Message"].extend(validate_contract(schema, "Message", message, f"Message[{index}]"))
    results["LayerPacket"].extend(
        validate_contract(schema, "LayerPacket", kernel_result["layer_runtime"]["packet"], "LayerPacket")
    )
    results["LayerExecutionResult"].extend(
        validate_contract(schema, "LayerExecutionResult", kernel_result["layer_runtime"]["result"], "LayerExecutionResult")
    )
    results["KnowledgeTile"].extend(
        validate_contract(schema, "KnowledgeTile", kernel_result["knowledge_tile"], "KnowledgeTile")
    )
    results["ProofCapsule"].extend(
        validate_contract(schema, "ProofCapsule", kernel_result["proof_capsule"], "ProofCapsule")
    )
    results["PatchLedger"].extend(
        validate_contract(schema, "PatchLedger", kernel_result["patch_ledger"], "PatchLedger")
    )
    return results


def flatten_contract_results(results: dict[str, list[ContractIssue]]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    for definition_name in sorted(results):
        issues.extend(results[definition_name])
    return issues


def render_contract_results(results: dict[str, list[ContractIssue]]) -> str:
    lines = []
    for definition_name in sorted(results):
        issues = results[definition_name]
        status = "PASS" if not issues else "FAIL"
        lines.extend([f"### {definition_name}", "", status if not issues else render_issues(issues), ""])
    return "\n".join(lines).rstrip()


def render_contract_gate_status(gate: dict[str, Any]) -> str:
    lines = [
        "# Contract Gate Status",
        "",
        f"Gate: {gate['id']}",
        f"Status: {gate['status']}",
        f"Can continue: {gate['can_continue']}",
        f"Issue count: {gate['issue_count']}",
        "",
        "## Blocking definitions",
        "",
    ]
    if gate["blocking_definitions"]:
        lines.extend(f"- {definition}" for definition in gate["blocking_definitions"])
    else:
        lines.append("PASS")
    lines.extend(["", "## Correction prompts", ""])
    if gate["correction_prompts"]:
        lines.extend(f"- {prompt}" for prompt in gate["correction_prompts"])
    else:
        lines.append("No correction required.")
    return "\n".join(lines)


def render_issues(issues: list[ContractIssue]) -> str:
    if not issues:
        return "PASS"
    return "\n".join(f"- {issue.path}: {issue.message}" for issue in issues)


def render_contract_status(
    schema_path: Path,
    schema: dict[str, Any],
    task_issues: list[ContractIssue],
    model_role_issues: list[ContractIssue],
    runtime_results: dict[str, list[ContractIssue]] | None = None,
) -> str:
    lines = [
        "# Contract Status",
        "",
        f"Schema: {schema_path}",
        "",
        "## Definitions",
        "",
    ]
    lines.extend(f"- {name}" for name in schema_definitions(schema))
    lines.extend(
        [
            "",
            "## ForgeTask validation",
            "",
            render_issues(task_issues),
            "",
            "## ModelRole validation",
            "",
            render_issues(model_role_issues),
        ]
    )
    if runtime_results is not None:
        lines.extend(
            [
                "",
                "## Runtime contract validation",
                "",
                render_contract_results(runtime_results),
            ]
        )
    return "\n".join(lines)


def _validate_schema_node(schema_root: dict[str, Any], schema_node: dict[str, Any], value: Any, path: str) -> list[ContractIssue]:
    if "$ref" in schema_node:
        ref_name = schema_node["$ref"].split("/")[-1]
        ref_node = schema_root.get("$defs", {}).get(ref_name)
        if ref_node is None:
            return [ContractIssue(path, f"unresolved ref: {schema_node['$ref']}")]
        return _validate_schema_node(schema_root, ref_node, value, path)

    issues: list[ContractIssue] = []
    if "enum" in schema_node and value not in schema_node["enum"]:
        issues.append(ContractIssue(path, f"expected one of {schema_node['enum']}, got {value!r}"))
        return issues

    expected_type = schema_node.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_matches(value, item) for item in expected_types):
            issues.append(ContractIssue(path, f"expected type {expected_types}, got {type(value).__name__}"))
            return issues

    if isinstance(value, dict):
        required = schema_node.get("required", [])
        for field in required:
            if field not in value:
                issues.append(ContractIssue(f"{path}.{field}", "required field missing"))

        properties = schema_node.get("properties", {})
        if schema_node.get("additionalProperties") is False:
            for field in value:
                if field not in properties:
                    issues.append(ContractIssue(f"{path}.{field}", "additional property not allowed"))

        for field, child_schema in properties.items():
            if field in value:
                issues.extend(_validate_schema_node(schema_root, child_schema, value[field], f"{path}.{field}"))

    if isinstance(value, list) and "items" in schema_node:
        for index, item in enumerate(value):
            issues.extend(_validate_schema_node(schema_root, schema_node["items"], item, f"{path}[{index}]"))
        min_items = schema_node.get("minItems")
        if min_items is not None and len(value) < min_items:
            issues.append(ContractIssue(path, f"expected at least {min_items} items"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema_node.get("minimum")
        maximum = schema_node.get("maximum")
        if minimum is not None and value < minimum:
            issues.append(ContractIssue(path, f"expected >= {minimum}"))
        if maximum is not None and value > maximum:
            issues.append(ContractIssue(path, f"expected <= {maximum}"))

    if isinstance(value, str) and "pattern" in schema_node:
        if re.match(schema_node["pattern"], value) is None:
            issues.append(ContractIssue(path, f"does not match pattern {schema_node['pattern']}"))

    return issues


def _type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "null":
        return value is None
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False
