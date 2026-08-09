from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import AgentOrchestrator, render_agent_orchestrator_status
from .contracts import (
    flatten_contract_results,
    load_contract_schema,
    render_contract_gate_status,
    render_contract_status,
    render_issues,
    schema_definitions,
    validate_forge_tasks,
    validate_model_roles,
    validate_runtime_contracts,
)
from .io import append_jsonl, read_json, resolve_runtime_dir, utc_ts, write_json, write_text
from .kernel import AioneKernel, render_kernel_status, render_layer_status
from .mmr import (
    build_mmr_bundle,
    persist_mmr_index,
    render_answer_quality_verification_status,
    render_autotuning_policy_status,
    render_bounded_predictive_runtime_status,
    render_document_benchmark_status,
    render_dual_cost_validation_status,
    render_cache_reuse_benchmark_status,
    render_diffcache_benchmark_status,
    render_divergence_runtime_status,
    render_external_workload_adapter_status,
    render_intrastate_delta_runtime_status,
    render_long_horizon_stability_status,
    render_microdelta_dependency_runtime_status,
    render_mmr_status,
    render_potentialstate_runtime_status,
    render_predictive_sparse_runtime_status,
    render_real_user_task_benchmark_status,
    run_answer_quality_verification,
    run_autotuning_policy,
    run_bounded_predictive_runtime,
    run_cache_reuse_benchmark,
    run_dual_cost_validation,
    run_diffcache_benchmark,
    run_divergence_runtime,
    run_document_benchmark,
    run_external_workload_adapter,
    run_intrastate_delta_runtime,
    run_long_horizon_stability,
    run_microdelta_dependency_runtime,
    run_potentialstate_runtime,
    run_predictive_sparse_runtime,
    run_real_user_task_benchmark,
)
from .operators import ContractGateOperator
from .prompts import CODER_PROMPT, NVIDIA_ROUTER_PROMPT, PLANNER_PROMPT, VERIFIER_PROMPT
from .research_catalog import EXTERNAL_SOURCES, GITHUB_CANDIDATES, NVIDIA_MODEL_ROLES
from .stores import StoreBundle, render_memory_query_status, render_store_status


MISSION = (
    "Construire AIONE comme plateforme post-LLM autonome, locale d'abord, "
    "capable de recherche, planification, verification, structuration, codage, "
    "memoire et optimisation cout/energie."
)


MVP_LOCALITIES = [
    "globalite",
    "mission",
    "recherche",
    "memoire",
    "verification",
    "execution",
    "ressources",
    "securite",
    "dashboard",
]


MVP_OPERATORS = [
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
]


@dataclass
class ForgeResult:
    runtime_dir: Path
    used_fallback: bool
    cycle: int
    artifacts: list[str]
    status: str


class AioneForge:
    def __init__(self, runtime_dir: str | None = None, target_workspace: str | None = None):
        self.runtime_dir, self.used_fallback = resolve_runtime_dir(runtime_dir)
        self.target_workspace = Path(target_workspace or ".").resolve()
        self.state_path = self.runtime_dir / "state" / "forge_state.json"
        self.log_path = self.runtime_dir / "logs" / "events.jsonl"
        self.contract_schema_path, self.contract_schema = load_contract_schema(self.target_workspace)

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        append_jsonl(
            self.log_path,
            {
                "ts": utc_ts(),
                "type": event_type,
                "payload": payload,
            },
        )

    def load_state(self) -> dict[str, Any]:
        return read_json(
            self.state_path,
            {
                "mission": MISSION,
                "cycle": 0,
                "status": "initialized",
                "completed_tasks": [],
                "failed_futures": [],
                "decisions": [],
                "runtime_dir": str(self.runtime_dir),
                "target_workspace": str(self.target_workspace),
            },
        )

    def save_state(self, state: dict[str, Any]) -> None:
        state["runtime_dir"] = str(self.runtime_dir)
        state["target_workspace"] = str(self.target_workspace)
        state["updated_at"] = utc_ts()
        write_json(self.state_path, state)

    def build_tasks(self, cycle: int) -> list[dict[str, Any]]:
        return [
            {
                "id": f"TASK-{cycle:04d}-001",
                "title": "Stabiliser les contrats Mission et Message",
                "locality": "mission",
                "operator": "PlanningOperator",
                "verification": "schemas exist, examples exist, checklist passes",
                "status": "pending",
                "source_refs": [
                    "cahier_des_charges/AIONE_CDC_v0.md",
                    "schemas/aione_contracts.schema.json",
                ],
                "artifact_targets": [
                    "schemas/aione_contracts.schema.json",
                    "schemas/examples/mission.example.json",
                    "schemas/examples/message.example.json",
                ],
            },
            {
                "id": f"TASK-{cycle:04d}-002",
                "title": "Definir Bus, Locality, Node, Layer, SuperLayer, Operator",
                "locality": "globalite",
                "operator": "AbstractionOperator",
                "verification": "contracts map to current research docs",
                "status": "pending",
                "source_refs": [
                    "recherche/03_modele_bus_noeuds_couches.md",
                    "cahier_des_charges/AIONE_CDC_v0.md",
                ],
                "artifact_targets": [
                    "schemas/aione_contracts.schema.json#BusSpec",
                    "schemas/aione_contracts.schema.json#LocalitySpec",
                    "schemas/aione_contracts.schema.json#NodeSpec",
                    "schemas/aione_contracts.schema.json#LayerSpec",
                    "schemas/aione_contracts.schema.json#SuperLayerSpec",
                ],
            },
            {
                "id": f"TASK-{cycle:04d}-003",
                "title": "Creer ProofCapsule et PatchLedger",
                "locality": "verification",
                "operator": "TruthGateOperator",
                "verification": "every generated artifact can cite source, invariant, rollback",
                "status": "pending",
                "source_refs": [
                    "cahier_des_charges/AIONE_CDC_v0.md",
                    "recherche/import_cahier_des_charges/synthese_cahier_des_charges.md",
                ],
                "artifact_targets": [
                    "schemas/aione_contracts.schema.json#ProofCapsule",
                    "schemas/aione_contracts.schema.json#PatchLedger",
                ],
            },
            {
                "id": f"TASK-{cycle:04d}-004",
                "title": "Creer le registre KnowledgeTile",
                "locality": "memoire",
                "operator": "MemoryOperator",
                "verification": "tile contains summary, tags, source, use, hash placeholder",
                "status": "pending",
                "source_refs": [
                    "cahier_des_charges/AIONE_CDC_v0.md",
                    "recherche/01_plan_action.md",
                ],
                "artifact_targets": [
                    "schemas/aione_contracts.schema.json#KnowledgeTile",
                ],
            },
            {
                "id": f"TASK-{cycle:04d}-005",
                "title": "Specifier le ModelRoutingOperator NVIDIA",
                "locality": "ressources",
                "operator": "RoutingOperator",
                "verification": "roles are selected before model ids; availability is checked",
                "status": "pending",
                "source_refs": [
                    "recherche/externe_pre_cahier_des_charges.md",
                    "https://build.nvidia.com/models",
                ],
                "artifact_targets": [
                    "schemas/aione_contracts.schema.json#ModelRole",
                    "config/nvidia_model_roles.json",
                ],
            },
            {
                "id": f"TASK-{cycle:04d}-006",
                "title": "Generer cahier des charges v0 depuis les sources locales et externes",
                "locality": "recherche",
                "operator": "CompressionOperator",
                "verification": "requirements are grouped by module and testable",
                "status": "pending",
                "source_refs": [
                    "recherche/import_cahier_des_charges/synthese_cahier_des_charges.md",
                    "recherche/externe_pre_cahier_des_charges.md",
                ],
                "artifact_targets": [
                    "cahier_des_charges/AIONE_CDC_v0.md",
                ],
            },
        ]

    def render_plan(self, state: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
        lines = [
            "# AIONE Forge Plan",
            "",
            f"Cycle: {state['cycle']}",
            f"Mission: {state['mission']}",
            "",
            "## Localites MVP",
            "",
        ]
        lines.extend(f"- {item}" for item in MVP_LOCALITIES)
        lines.extend(["", "## Operateurs MVP", ""])
        lines.extend(f"- {item}" for item in MVP_OPERATORS)
        lines.extend(["", "## Taches du cycle", ""])
        for task in tasks:
            lines.extend(
                [
                    f"### {task['id']} - {task['title']}",
                    "",
                    f"- localite: {task['locality']}",
                    f"- operateur: {task['operator']}",
                    f"- verification: {task['verification']}",
                    f"- statut: {task['status']}",
                    "",
                ]
            )
        return "\n".join(lines)

    def render_checklist(self, tasks: list[dict[str, Any]]) -> str:
        lines = [
            "# AIONE Forge Verification Checklist",
            "",
            "## Gates globaux",
            "",
            "- [ ] Chaque tache a un objectif testable.",
            "- [ ] Chaque sortie a une source ou une justification.",
            "- [ ] Chaque mutation importante a rollback ou patch proposal.",
            "- [ ] Les modeles NVIDIA sont routes par role et verifies avant usage.",
            "- [ ] Aucun processus infini n'est lance sans fichier STOP_FORGE et logs.",
            "- [ ] Les claims scientifiques restent hypotheses tant qu'ils ne sont pas testes.",
            "",
            "## Taches",
            "",
        ]
        lines.extend(f"- [ ] {task['id']} - {task['title']}" for task in tasks)
        return "\n".join(lines)

    def render_stop_forge_guide(self) -> str:
        stop_path = self.runtime_dir / "STOP_FORGE"
        lines = [
            "# STOP_FORGE Guide",
            "",
            f"Runtime directory: {self.runtime_dir}",
            f"Stop file: {stop_path}",
            "",
            "## Rule",
            "",
            "The Forge must stop before starting a new cycle when `STOP_FORGE` exists.",
            "",
            "## Safe stop",
            "",
            "Create the file in the runtime directory:",
            "",
            "```powershell",
            f"New-Item -ItemType File -Path \"{stop_path}\" -Force",
            "```",
            "",
            "## Resume",
            "",
            "Remove the file only after checking the last state and logs:",
            "",
            "```powershell",
            f"Remove-Item -LiteralPath \"{stop_path}\"",
            "```",
            "",
            "## Invariants",
            "",
            "- No new cycle starts while the file exists.",
            "- The stop event is logged in `logs/events.jsonl`.",
            "- Critical mutations remain disabled until sandbox and rollback exist.",
            "- Continuous mode is supervised, not a background daemon.",
        ]
        return "\n".join(lines)

    def render_next_code_tasks(self, tasks: list[dict[str, Any]]) -> str:
        lines = [
            "# Next Code Tasks",
            "",
            "Ces taches sont les prochains increments de code proposes par la Forge.",
            "",
        ]
        for task in tasks:
            lines.extend(
                [
                    f"## {task['id']}",
                    "",
                    f"Objectif: {task['title']}",
                    f"Module cible: {task['locality']}",
                    f"Operateur responsable: {task['operator']}",
                    f"Definition of done: {task['verification']}",
                    "",
                ]
            )
        return "\n".join(lines)

    def render_source_digest(self) -> str:
        lines = ["# Source Digest", ""]
        lines.append("## External research")
        lines.extend(f"- {item['id']}: {item['title']} - {item['use']} ({item['url']})" for item in EXTERNAL_SOURCES)
        lines.extend(["", "## GitHub candidates"])
        lines.extend(
            f"- {item['id']}: {item['name']} - {item['candidate_for']} ({item['url']})"
            for item in GITHUB_CANDIDATES
        )
        lines.extend(["", "## NVIDIA model roles"])
        for role in NVIDIA_MODEL_ROLES:
            lines.append(f"- {role['role']}: {', '.join(role['candidate_models'])}")
        return "\n".join(lines)

    def build_operator_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "OP-ROUTING-0001",
                "name": "RoutingOperator",
                "type": "routing",
                "locality": "ressources",
                "objective": "Choose model role, tool or strategy from mission depth, risk and cost.",
                "inputs": ["Mission", "Message", "resource_state"],
                "outputs": ["ModelRole", "routing_decision"],
                "allowed_buses": ["mission_bus", "resource_bus", "verification_bus"],
                "required_layers": ["cost", "energy", "verification"],
                "observer_superlayers": ["sobriety", "coherence"],
                "strategies": [{"id": "small_first", "description": "Prefer the cheapest compatible role."}],
                "degrees": {
                    "depth": ["quick", "standard", "deep"],
                    "precision": ["standard", "verified"],
                    "cost": ["minimal", "balanced", "high"],
                    "autonomy": ["suggestion", "verified_execution"],
                },
                "budget": {"default_cost_class": "low"},
                "permissions": ["read_mission", "write_routing_decision"],
                "compatible_model_roles": ["fast_router_or_summarizer", "planner_deep", "safety"],
                "compatible_tools": ["local_state_reader"],
                "metrics": ["latency", "cost_class", "fallback_count"],
                "activation_conditions": ["mission_received", "model_needed"],
                "stop_conditions": ["no_valid_route", "safety_gate_failed"],
                "version": "0.1.0",
                "status": "experimental",
            },
            {
                "id": "OP-MEMORY-CONTEXT-0001",
                "name": "MemoryContextOperator",
                "type": "memory",
                "locality": "memoire",
                "objective": "Select useful memory context and expose relation graphs for the kernel.",
                "inputs": ["KnowledgeTile", "query"],
                "outputs": ["context_summary", "weighted_relation_graph", "fusion_candidates"],
                "allowed_buses": ["memory_bus", "reflection_bus", "verification_bus"],
                "required_layers": ["recency", "verification", "compression"],
                "observer_superlayers": ["coherence", "evolution_structurelle"],
                "strategies": [{"id": "weighted_context", "description": "Rank by lexical fit, usefulness, recency and verification."}],
                "degrees": {
                    "depth": ["quick", "standard", "deep"],
                    "precision": ["approximate", "standard", "verified"],
                    "cost": ["minimal"],
                    "autonomy": ["suggestion", "verified_execution"],
                },
                "budget": {"default_cost_class": "low"},
                "permissions": ["read_memory", "write_context_summary"],
                "compatible_model_roles": ["embedding", "retrieval_rerank", "fast_router_or_summarizer"],
                "compatible_tools": ["jsonl_store", "relation_graph_builder"],
                "metrics": ["context_score", "fusion_candidate_count", "obsolete_count"],
                "activation_conditions": ["kernel_cycle_started", "memory_context_needed"],
                "stop_conditions": ["no_memory_records"],
                "version": "0.1.0",
                "status": "experimental",
            },
            {
                "id": "OP-CONTRACT-GATE-0001",
                "name": "ContractGateOperator",
                "type": "truth",
                "locality": "verification",
                "objective": "Block invalid runtime artifacts before the Forge continues.",
                "inputs": ["runtime_contract_validation"],
                "outputs": ["contract_gate", "correction_prompts"],
                "allowed_buses": ["verification_bus", "safety_bus", "reflection_bus"],
                "required_layers": ["verification", "safety", "rollback"],
                "observer_superlayers": ["coherence", "securite"],
                "strategies": [
                    {
                        "id": "block_on_contract_error",
                        "description": "Continue only when every runtime contract definition passes.",
                    }
                ],
                "degrees": {
                    "depth": ["quick", "standard"],
                    "precision": ["verified"],
                    "cost": ["minimal"],
                    "autonomy": ["verified_execution"],
                },
                "budget": {"default_cost_class": "low"},
                "permissions": ["read_contract_results", "write_gate_decision"],
                "compatible_model_roles": ["safety", "fast_router_or_summarizer"],
                "compatible_tools": ["runtime_contract_validator"],
                "metrics": ["issue_count", "blocking_definition_count"],
                "activation_conditions": ["runtime_contract_validation_complete"],
                "stop_conditions": ["contract_issue_count_zero", "blocking_issue_detected"],
                "version": "0.1.0",
                "status": "experimental",
            },
        ]

    def build_agent_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "AGENT-PLANNER-0001",
                "name": "PlannerAgent",
                "role": "planner",
                "locality": "mission",
                "objective": "Transform a validated mission into scoped, testable Forge tasks.",
                "inputs": ["Mission", "context_summary", "contract_gate"],
                "outputs": ["ForgeTask", "planning_notes"],
                "allowed_buses": ["mission_bus", "verification_bus", "reflection_bus"],
                "required_gates": ["ContractGateOperator", "TruthGateOperator"],
                "permissions": ["read_mission", "write_task_plan"],
                "budget": {"cost_class": "low", "max_cycles": 1},
                "compatible_model_roles": ["fast_router_or_summarizer", "planner_deep"],
                "compatible_tools": ["json_schema_validator", "task_queue_writer"],
                "memory_policy": {"read": True, "write": False, "context_limit": 5},
                "rollback_policy": {"required": True, "strategy": "discard_generated_tasks"},
                "tests": ["tests/test_aione_forge.py", "tests/test_aione_contracts.py"],
                "metrics": ["task_count", "contract_pass_rate"],
                "activation_conditions": ["contract_gate_passed", "mission_planned"],
                "stop_conditions": ["contract_gate_blocked", "no_valid_task"],
                "version": "0.1.0",
                "status": "experimental",
            },
            {
                "id": "AGENT-VERIFIER-0001",
                "name": "VerifierAgent",
                "role": "verifier",
                "locality": "verification",
                "objective": "Validate generated artifacts and route failures to correction prompts.",
                "inputs": ["runtime_contract_validation", "contract_gate", "ProofCapsule"],
                "outputs": ["verification_report", "correction_prompts"],
                "allowed_buses": ["verification_bus", "safety_bus", "reflection_bus"],
                "required_gates": ["ContractGateOperator"],
                "permissions": ["read_artifacts", "write_verification_report"],
                "budget": {"cost_class": "low", "max_cycles": 1},
                "compatible_model_roles": ["safety", "fast_router_or_summarizer"],
                "compatible_tools": ["runtime_contract_validator", "pytest_runner"],
                "memory_policy": {"read": True, "write": True, "context_limit": 3},
                "rollback_policy": {"required": True, "strategy": "block_cycle_until_fixed"},
                "tests": ["tests/test_aione_contracts.py", "tests/test_aione_forge.py"],
                "metrics": ["issue_count", "blocked_cycle_count"],
                "activation_conditions": ["runtime_contract_validation_complete"],
                "stop_conditions": ["contract_gate_passed", "contract_gate_blocked"],
                "version": "0.1.0",
                "status": "experimental",
            },
            {
                "id": "AGENT-MEMORY-CURATOR-0001",
                "name": "MemoryCuratorAgent",
                "role": "memory_curator",
                "locality": "memoire",
                "objective": "Maintain active memory context, fusion candidates and obsolete markers.",
                "inputs": ["KnowledgeTile", "context_summary", "weighted_relation_graph"],
                "outputs": ["memory_state_report", "fusion_candidates"],
                "allowed_buses": ["memory_bus", "reflection_bus", "verification_bus"],
                "required_gates": ["ContractGateOperator", "TruthGateOperator"],
                "permissions": ["read_memory", "write_memory_report"],
                "budget": {"cost_class": "low", "max_cycles": 1},
                "compatible_model_roles": ["embedding", "retrieval_rerank", "fast_router_or_summarizer"],
                "compatible_tools": ["jsonl_store", "relation_graph_builder"],
                "memory_policy": {"read": True, "write": True, "context_limit": 10},
                "rollback_policy": {"required": True, "strategy": "append_only_no_destructive_delete"},
                "tests": ["tests/test_aione_stores.py"],
                "metrics": ["active_tile_count", "fusion_candidate_count", "obsolete_count"],
                "activation_conditions": ["kernel_cycle_completed", "memory_context_needed"],
                "stop_conditions": ["contract_gate_blocked"],
                "version": "0.1.0",
                "status": "experimental",
            },
        ]

    def build_autonomous_mission(
        self,
        *,
        mission: dict[str, Any],
        agent_specs: list[dict[str, Any]],
        contract_gate: dict[str, Any],
        cycle: int,
    ) -> dict[str, Any]:
        now = utc_ts()
        return {
            "id": f"AMISSION-{cycle:04d}",
            "parent_mission_id": mission["id"],
            "title": f"Autonomous envelope for {mission['id']}",
            "objective": mission["objective"],
            "constraints": [
                *mission.get("constraints", []),
                "contract_gate_required",
                "proposal_only_until_sandbox_exists",
                "append_only_memory",
            ],
            "candidate_agents": [agent["id"] for agent in agent_specs],
            "required_gates": ["ContractGateOperator", "TruthGateOperator"],
            "budget": {
                "max_cycles": 3,
                "cost_class": "low",
                "mutation_allowed": False,
                "tokens": mission.get("resource_budget", {}).get("tokens"),
                "time_seconds": mission.get("resource_budget", {}).get("time_seconds"),
            },
            "status": "ready" if contract_gate.get("can_continue") else "blocked",
            "stop_conditions": [
                "contract_gate_blocked",
                "stop_file_present",
                "budget_exceeded",
                "critical_risk_without_permission",
            ],
            "resume_conditions": [
                "contract_gate_passed",
                "human_supervisor_allows_resume",
                "budget_available",
            ],
            "expected_proof": {
                "required_artifacts": ["ProofCapsule", "PatchLedger", "AgentDecision"],
                "minimum_confidence": 0.75,
                "required_tests": ["tests/test_aione_forge.py", "tests/test_aione_contracts.py"],
            },
            "max_cycles": 3,
            "current_cycle": 0,
            "created_at": now,
            "updated_at": now,
        }

    def render_autonomous_mission_status(self, autonomous_mission: dict[str, Any]) -> str:
        lines = [
            "# Autonomous Mission Status",
            "",
            f"Mission: {autonomous_mission['id']}",
            f"Parent: {autonomous_mission['parent_mission_id']}",
            f"Status: {autonomous_mission['status']}",
            f"Max cycles: {autonomous_mission['max_cycles']}",
            f"Current cycle: {autonomous_mission['current_cycle']}",
            f"Mutation allowed: {autonomous_mission['budget'].get('mutation_allowed')}",
            "",
            "## Candidate agents",
            "",
        ]
        lines.extend(f"- {agent_id}" for agent_id in autonomous_mission["candidate_agents"])
        lines.extend(["", "## Required gates", ""])
        lines.extend(f"- {gate}" for gate in autonomous_mission["required_gates"])
        lines.extend(["", "## Stop conditions", ""])
        lines.extend(f"- {condition}" for condition in autonomous_mission["stop_conditions"])
        lines.extend(["", "## Expected proof", ""])
        for artifact in autonomous_mission["expected_proof"].get("required_artifacts", []):
            lines.append(f"- {artifact}")
        return "\n".join(lines)

    def write_prompts(self) -> list[str]:
        prompt_dir = self.runtime_dir / "prompts"
        artifacts = []
        for name, content in {
            "PLANNER.md": PLANNER_PROMPT,
            "VERIFIER.md": VERIFIER_PROMPT,
            "CODER.md": CODER_PROMPT,
            "NVIDIA_MODEL_ROUTER.md": NVIDIA_ROUTER_PROMPT,
        }.items():
            path = prompt_dir / name
            write_text(path, content)
            artifacts.append(str(path))
        return artifacts

    def write_config(self) -> list[str]:
        config_dir = self.runtime_dir / "config"
        artifacts = []
        path = config_dir / "nvidia_model_roles.json"
        write_json(path, NVIDIA_MODEL_ROLES)
        artifacts.append(str(path))
        operator_specs_path = config_dir / "operator_specs.json"
        write_json(operator_specs_path, self.build_operator_specs())
        artifacts.append(str(operator_specs_path))
        agent_specs_path = config_dir / "agent_specs.json"
        write_json(agent_specs_path, self.build_agent_specs())
        artifacts.append(str(agent_specs_path))
        schema_index_path = config_dir / "contract_schema_index.json"
        write_json(
            schema_index_path,
            {
                "schema_path": str(self.contract_schema_path),
                "definitions": schema_definitions(self.contract_schema),
            },
        )
        artifacts.append(str(schema_index_path))
        return artifacts

    def cycle_once(self) -> ForgeResult:
        state = self.load_state()
        state["cycle"] = int(state.get("cycle", 0)) + 1
        state["status"] = "running"

        self.log(
            "cycle_started",
            {
                "cycle": state["cycle"],
                "fallback_runtime": self.used_fallback,
                "runtime_dir": str(self.runtime_dir),
            },
        )

        tasks = self.build_tasks(state["cycle"])
        operator_specs = self.build_operator_specs()
        agent_specs = self.build_agent_specs()
        task_issues = validate_forge_tasks(tasks)
        model_role_issues = validate_model_roles(NVIDIA_MODEL_ROLES)
        stores = StoreBundle(self.runtime_dir / "stores")
        prior_knowledge = stores.knowledge.records()
        prior_context_summary = stores.synthesize_context("kernel proof memory", limit=5)
        kernel_result = AioneKernel(
            exchange_log_path=str(self.runtime_dir / "logs" / "layer_exchange.jsonl"),
            memory_records=prior_knowledge,
            memory_context=prior_context_summary,
        ).run_intent(
            MISSION,
            state["cycle"],
        )
        store_status = stores.persist_kernel_result(kernel_result)
        store_search_results = stores.search_knowledge("kernel")
        relation_graph = stores.relation_graph()
        weighted_relation_graph = stores.weighted_relation_graph()
        context_summary = stores.synthesize_context("kernel proof memory", limit=5)
        mmr_bundle = build_mmr_bundle(
            mission=kernel_result["mission"],
            context_summary=context_summary,
            cycle=state["cycle"],
        )
        mmr_index_status = persist_mmr_index(self.runtime_dir / "stores" / "mmr_index.sqlite", mmr_bundle)
        mmr_document_benchmark = run_document_benchmark(self.runtime_dir / "stores" / "mmr_index.sqlite")
        mmr_cache_reuse_benchmark = run_cache_reuse_benchmark(self.runtime_dir / "stores" / "mmr_index.sqlite")
        mmr_divergence_runtime = run_divergence_runtime(self.runtime_dir / "stores" / "mmr_index.sqlite")
        mmr_diffcache_benchmark = run_diffcache_benchmark(self.runtime_dir / "stores" / "mmr_index.sqlite")
        mmr_potentialstate_runtime = run_potentialstate_runtime(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_intrastate_delta_runtime = run_intrastate_delta_runtime(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_microdelta_dependency_runtime = run_microdelta_dependency_runtime(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_predictive_sparse_runtime = run_predictive_sparse_runtime(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_bounded_predictive_runtime = run_bounded_predictive_runtime(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_dual_cost_validation = run_dual_cost_validation(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_autotuning_policy = run_autotuning_policy(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        mmr_long_horizon_stability = run_long_horizon_stability(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            memory_records=stores.knowledge.unique_records(),
        )
        workload_source_path = self.target_workspace if self.target_workspace.exists() else Path.cwd()
        mmr_external_workload_adapter = run_external_workload_adapter(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            source_path=workload_source_path,
            queries=["architecture", "tests", "todo"],
        )
        mmr_answer_quality_verification = run_answer_quality_verification(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            source_path=workload_source_path,
            queries=["architecture", "tests", "todo"],
        )
        mmr_real_user_task_benchmark = run_real_user_task_benchmark(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            source_path=workload_source_path,
        )
        memory_query_report = {
            "knowledge_by_tag": len(stores.query_knowledge(tags=["kernel"])),
            "knowledge_partial": len(stores.query_knowledge(verification_status="partial")),
            "proofs_for_kernel": len(stores.query_proofs(target_artifact="kernel/cycle_kernel.json")),
            "proofs_passed": len(stores.query_proofs(status="passed")),
            "patches_applied": len(stores.query_patches(status="applied")),
            "patches_for_kernel_file": len(stores.query_patches(file_touched="aione_forge/kernel.py")),
            "relation_nodes": len(relation_graph),
            "weighted_relation_nodes": len(weighted_relation_graph),
            "context_items": context_summary["result_count"],
            "fusion_candidates": len(stores.fusion_candidates()),
            "memory_states": stores.memory_state_counts(),
            "truth_gate": {
                "status": kernel_result["proof_capsule"]["memory_check"]["status"],
                "confirmations": len(kernel_result["proof_capsule"]["memory_check"]["confirmations"]),
                "contradictions": len(kernel_result["proof_capsule"]["memory_check"]["contradictions"]),
            },
        }
        runtime_contract_results = validate_runtime_contracts(
            self.contract_schema,
            tasks=tasks,
            model_roles=NVIDIA_MODEL_ROLES,
            operator_specs=operator_specs,
            agent_specs=agent_specs,
            mmr_bundle=mmr_bundle.as_dict(),
            kernel_result=kernel_result,
        )
        runtime_contract_issues = flatten_contract_results(runtime_contract_results)
        contract_gate = ContractGateOperator().evaluate(runtime_contract_results)
        autonomous_mission = self.build_autonomous_mission(
            mission=kernel_result["mission"],
            agent_specs=agent_specs,
            contract_gate=contract_gate,
            cycle=state["cycle"],
        )
        agent_decision = AgentOrchestrator(agent_specs).decide(
            mission=kernel_result["mission"],
            contract_gate=contract_gate,
            context_summary=context_summary,
        )
        runtime_contract_results["AgentDecision"] = validate_runtime_contracts(
            self.contract_schema,
            tasks=[],
            model_roles=[],
            operator_specs=[],
            agent_specs=[],
            agent_decision=agent_decision,
            autonomous_mission=autonomous_mission,
            kernel_result=kernel_result,
        )["AgentDecision"]
        runtime_contract_results["AutonomousMissionSpec"] = validate_runtime_contracts(
            self.contract_schema,
            tasks=[],
            model_roles=[],
            operator_specs=[],
            agent_specs=[],
            autonomous_mission=autonomous_mission,
            kernel_result=kernel_result,
        )["AutonomousMissionSpec"]
        runtime_contract_issues = flatten_contract_results(runtime_contract_results)
        contract_gate = ContractGateOperator().evaluate(runtime_contract_results)

        state["last_tasks"] = tasks
        state["operator_specs"] = operator_specs
        state["agent_specs"] = agent_specs
        state["agent_decision"] = agent_decision
        state["autonomous_mission"] = autonomous_mission
        state["mmr"] = {
            "potential_state_id": mmr_bundle.potential_state["id"],
            "materialized_slice_id": mmr_bundle.materialized_slice["id"],
            "cost_trace_id": mmr_bundle.cost_trace["id"],
            "result": mmr_bundle.cost_trace["result"],
            "index": mmr_index_status,
            "document_benchmark": {
                "id": mmr_document_benchmark["id"],
                "result": mmr_document_benchmark["result"],
                "selected_documents": len(mmr_document_benchmark["selected_documents"]),
                "saved_tokens": mmr_document_benchmark["saved_work_estimate"]["tokens"],
            },
            "cache_reuse_benchmark": {
                "id": mmr_cache_reuse_benchmark["id"],
                "result": mmr_cache_reuse_benchmark["result"],
                "cache_hits": mmr_cache_reuse_benchmark["metrics"]["cache_hits"],
                "cache_invalidations": mmr_cache_reuse_benchmark["metrics"]["cache_invalidations"],
                "saved_tokens": mmr_cache_reuse_benchmark["metrics"]["saved_tokens"],
                "latency_gain_ms": mmr_cache_reuse_benchmark["metrics"]["latency_gain_ms"],
            },
            "divergence_runtime": {
                "id": mmr_divergence_runtime["id"],
                "result": mmr_divergence_runtime["result"],
                "low_divergence_reused_slices": mmr_divergence_runtime["metrics"][
                    "low_divergence_reused_slices"
                ],
                "high_divergence_rebuilt_slices": mmr_divergence_runtime["metrics"][
                    "high_divergence_rebuilt_slices"
                ],
                "low_divergence_relative_resolution_cost": mmr_divergence_runtime["metrics"][
                    "low_divergence_relative_resolution_cost"
                ],
                "high_divergence_relative_resolution_cost": mmr_divergence_runtime["metrics"][
                    "high_divergence_relative_resolution_cost"
                ],
            },
            "diffcache_benchmark": {
                "id": mmr_diffcache_benchmark["id"],
                "result": mmr_diffcache_benchmark["result"],
                "exact_cache_hit": mmr_diffcache_benchmark["metrics"]["exact_cache_hit"],
                "approximate_cache_hit": mmr_diffcache_benchmark["metrics"]["approximate_cache_hit"],
                "divergence_reused_slices": mmr_diffcache_benchmark["metrics"]["divergence_reused_slices"],
                "divergence_rebuilt_slices": mmr_diffcache_benchmark["metrics"]["divergence_rebuilt_slices"],
                "best_relative_resolution_cost": mmr_diffcache_benchmark["metrics"][
                    "best_relative_resolution_cost"
                ],
            },
            "potentialstate_runtime": {
                "id": mmr_potentialstate_runtime["id"],
                "result": mmr_potentialstate_runtime["result"],
                "previous_cycle_reuse": mmr_potentialstate_runtime["metrics"]["previous_cycle_reuse"],
                "reused_potential_states": mmr_potentialstate_runtime["metrics"]["reused_potential_states"],
                "rebuilt_potential_states": mmr_potentialstate_runtime["metrics"]["rebuilt_potential_states"],
                "reused_slices": mmr_potentialstate_runtime["metrics"]["reused_slices"],
                "rebuilt_slices": mmr_potentialstate_runtime["metrics"]["rebuilt_slices"],
                "best_relative_resolution_cost": mmr_potentialstate_runtime["metrics"][
                    "best_relative_resolution_cost"
                ],
            },
            "intrastate_delta_runtime": {
                "id": mmr_intrastate_delta_runtime["id"],
                "result": mmr_intrastate_delta_runtime["result"],
                "best_relative_resolution_cost": mmr_intrastate_delta_runtime["metrics"][
                    "best_relative_resolution_cost"
                ],
                "max_avoided_rebuild_ratio": mmr_intrastate_delta_runtime["metrics"][
                    "max_avoided_rebuild_ratio"
                ],
                "max_delta_ratio": mmr_intrastate_delta_runtime["metrics"]["max_delta_ratio"],
            },
            "microdelta_dependency_runtime": {
                "id": mmr_microdelta_dependency_runtime["id"],
                "result": mmr_microdelta_dependency_runtime["result"],
                "best_relative_resolution_cost": mmr_microdelta_dependency_runtime["metrics"][
                    "best_relative_resolution_cost"
                ],
                "max_avoided_rebuild_ratio": mmr_microdelta_dependency_runtime["metrics"][
                    "max_avoided_rebuild_ratio"
                ],
                "max_micro_delta_ratio": mmr_microdelta_dependency_runtime["metrics"]["max_micro_delta_ratio"],
            },
            "predictive_sparse_runtime": {
                "id": mmr_predictive_sparse_runtime["id"],
                "result": mmr_predictive_sparse_runtime["result"],
                "best_relative_resolution_cost": mmr_predictive_sparse_runtime["metrics"][
                    "best_relative_resolution_cost"
                ],
                "best_predictive_hit_rate": mmr_predictive_sparse_runtime["metrics"][
                    "best_predictive_hit_rate"
                ],
                "max_avoided_materialization_ratio": mmr_predictive_sparse_runtime["metrics"][
                    "max_avoided_materialization_ratio"
                ],
            },
            "bounded_predictive_runtime": {
                "id": mmr_bounded_predictive_runtime["id"],
                "result": mmr_bounded_predictive_runtime["result"],
                "best_relative_resolution_cost": mmr_bounded_predictive_runtime["metrics"][
                    "best_relative_resolution_cost"
                ],
                "max_scaling_efficiency": mmr_bounded_predictive_runtime["metrics"]["max_scaling_efficiency"],
                "bounded_wasted_prewarm_ratio": mmr_bounded_predictive_runtime["metrics"][
                    "bounded_wasted_prewarm_ratio"
                ],
            },
            "dual_cost_validation": {
                "id": mmr_dual_cost_validation["id"],
                "result": mmr_dual_cost_validation["result"],
                "warning_count": mmr_dual_cost_validation["metrics"]["warning_count"],
                "max_absolute_materialized_tokens": mmr_dual_cost_validation["metrics"][
                    "max_absolute_materialized_tokens"
                ],
                "max_absolute_latency_ms": mmr_dual_cost_validation["metrics"]["max_absolute_latency_ms"],
            },
            "autotuning_policy": {
                "id": mmr_autotuning_policy["id"],
                "result": mmr_autotuning_policy["result"],
                "selected_mode": mmr_autotuning_policy["metrics"]["selected_mode"],
                "avoided_bad_prediction": mmr_autotuning_policy["metrics"]["avoided_bad_prediction"],
                "policy_stability_score": mmr_autotuning_policy["metrics"]["policy_stability_score"],
            },
            "long_horizon_stability": {
                "id": mmr_long_horizon_stability["id"],
                "result": mmr_long_horizon_stability["result"],
                "long_horizon_stability_score": mmr_long_horizon_stability["metrics"][
                    "long_horizon_stability_score"
                ],
                "policy_stability_score": mmr_long_horizon_stability["metrics"]["policy_stability_score"],
                "total_warnings": mmr_long_horizon_stability["metrics"]["total_warnings"],
            },
            "external_workload_adapter": {
                "id": mmr_external_workload_adapter["id"],
                "result": mmr_external_workload_adapter["result"],
                "total_files": mmr_external_workload_adapter["metrics"]["total_files"],
                "total_chunks": mmr_external_workload_adapter["metrics"]["total_chunks"],
                "best_relative_resolution_cost": mmr_external_workload_adapter["metrics"][
                    "best_relative_resolution_cost"
                ],
            },
            "answer_quality_verification": {
                "id": mmr_answer_quality_verification["id"],
                "result": mmr_answer_quality_verification["result"],
                "best_answer_quality_score": mmr_answer_quality_verification["metrics"][
                    "best_answer_quality_score"
                ],
                "minimum_evidence_score": mmr_answer_quality_verification["metrics"][
                    "minimum_evidence_score"
                ],
                "minimum_completeness_score": mmr_answer_quality_verification["metrics"][
                    "minimum_completeness_score"
                ],
            },
            "real_user_task_benchmark": {
                "id": mmr_real_user_task_benchmark["id"],
                "result": mmr_real_user_task_benchmark["result"],
                "task_count": mmr_real_user_task_benchmark["metrics"]["task_count"],
                "average_task_success_score": mmr_real_user_task_benchmark["metrics"][
                    "average_task_success_score"
                ],
                "average_source_coverage_score": mmr_real_user_task_benchmark["metrics"][
                    "average_source_coverage_score"
                ],
                "best_relative_resolution_cost": mmr_real_user_task_benchmark["metrics"][
                    "best_relative_resolution_cost"
                ],
            },
        }
        state["last_kernel"] = {
            "mission_id": kernel_result["mission"]["id"],
            "layer_action": kernel_result["layer_runtime"]["packet"]["action"],
            "layer_status": kernel_result["layer_runtime"]["result"]["status"],
            "selected_role": kernel_result["route_decision"]["selected_role"],
            "proof_status": kernel_result["proof_capsule"]["status"],
            "knowledge_tile_id": kernel_result["knowledge_tile"]["id"],
            "patch_ledger_id": kernel_result["patch_ledger"]["id"],
        }
        state["store_status"] = store_status
        state["memory_query"] = memory_query_report
        state["context_summary"] = context_summary
        state["contract_validation"] = {
            "forge_tasks": render_issues(task_issues),
            "model_roles": render_issues(model_role_issues),
            "runtime": render_issues(runtime_contract_issues),
            "gate": contract_gate["status"],
            "schema_path": str(self.contract_schema_path),
        }
        state["contract_gate"] = contract_gate
        state["status"] = "contract_gate_blocked" if not contract_gate["can_continue"] else "cycle_artifacts_generated"

        artifacts: list[str] = []
        reports_dir = self.runtime_dir / "reports"
        queue_dir = self.runtime_dir / "queue"
        kernel_dir = self.runtime_dir / "kernel"

        report_payloads = {
            "PLAN.md": self.render_plan(state, tasks),
            "CHECKLIST.md": self.render_checklist(tasks),
            "NEXT_CODE_TASKS.md": self.render_next_code_tasks(tasks),
            "SOURCE_DIGEST.md": self.render_source_digest(),
            "KERNEL_STATUS.md": render_kernel_status(kernel_result),
            "LAYER_RUNTIME_STATUS.md": render_layer_status(kernel_result),
            "STORE_STATUS.md": render_store_status(store_status, store_search_results),
            "MEMORY_QUERY_STATUS.md": render_memory_query_status(memory_query_report),
            "CONTRACT_GATE_STATUS.md": render_contract_gate_status(contract_gate),
            "AGENT_ORCHESTRATOR_STATUS.md": render_agent_orchestrator_status(agent_decision),
            "AUTONOMOUS_MISSION_STATUS.md": self.render_autonomous_mission_status(autonomous_mission),
            "STOP_FORGE_GUIDE.md": self.render_stop_forge_guide(),
            "MMR_STATUS.md": render_mmr_status(mmr_bundle, mmr_index_status),
            "MMR_DOCUMENT_BENCHMARK.md": render_document_benchmark_status(mmr_document_benchmark),
            "MMR_CACHE_REUSE_BENCHMARK.md": render_cache_reuse_benchmark_status(mmr_cache_reuse_benchmark),
            "MMR_DIVERGENCE_RUNTIME.md": render_divergence_runtime_status(mmr_divergence_runtime),
            "MMR_DIFFCACHE_BENCHMARK.md": render_diffcache_benchmark_status(mmr_diffcache_benchmark),
            "MMR_POTENTIALSTATE_RUNTIME.md": render_potentialstate_runtime_status(mmr_potentialstate_runtime),
            "MMR_INTRASTATE_DELTA_RUNTIME.md": render_intrastate_delta_runtime_status(
                mmr_intrastate_delta_runtime
            ),
            "MMR_MICRODELTA_DEPENDENCY_RUNTIME.md": render_microdelta_dependency_runtime_status(
                mmr_microdelta_dependency_runtime
            ),
            "MMR_PREDICTIVE_SPARSE_RUNTIME.md": render_predictive_sparse_runtime_status(
                mmr_predictive_sparse_runtime
            ),
            "MMR_BOUNDED_PREDICTIVE_RUNTIME.md": render_bounded_predictive_runtime_status(
                mmr_bounded_predictive_runtime
            ),
            "MMR_DUAL_COST_VALIDATION.md": render_dual_cost_validation_status(mmr_dual_cost_validation),
            "MMR_AUTOTUNING_POLICY.md": render_autotuning_policy_status(mmr_autotuning_policy),
            "MMR_LONG_HORIZON_STABILITY.md": render_long_horizon_stability_status(
                mmr_long_horizon_stability
            ),
            "MMR_EXTERNAL_WORKLOAD_ADAPTER.md": render_external_workload_adapter_status(
                mmr_external_workload_adapter
            ),
            "MMR_ANSWER_QUALITY_VERIFICATION.md": render_answer_quality_verification_status(
                mmr_answer_quality_verification
            ),
            "MMR_REAL_USER_TASK_BENCHMARK.md": render_real_user_task_benchmark_status(
                mmr_real_user_task_benchmark
            ),
            "CONTRACTS_STATUS.md": render_contract_status(
                self.contract_schema_path,
                self.contract_schema,
                task_issues,
                model_role_issues,
                runtime_contract_results,
            ),
        }
        for name, content in report_payloads.items():
            path = reports_dir / name
            write_text(path, content)
            artifacts.append(str(path))

        write_json(queue_dir / "tasks.json", tasks)
        artifacts.append(str(queue_dir / "tasks.json"))
        for name, payload in {
            "cycle_kernel.json": kernel_result,
            "mission.json": kernel_result["mission"],
            "messages.json": kernel_result["messages"],
            "layer_runtime.json": kernel_result["layer_runtime"],
            "layer_packet.json": kernel_result["layer_runtime"]["packet"],
            "layer_execution_result.json": kernel_result["layer_runtime"]["result"],
            "route_decision.json": kernel_result["route_decision"],
            "proof_capsule.json": kernel_result["proof_capsule"],
            "knowledge_tile.json": kernel_result["knowledge_tile"],
            "patch_ledger.json": kernel_result["patch_ledger"],
            "agent_specs.json": agent_specs,
            "agent_decision.json": agent_decision,
            "autonomous_mission.json": autonomous_mission,
            "mmr_bundle.json": mmr_bundle.as_dict(),
            "mmr_potential_state.json": mmr_bundle.potential_state,
            "mmr_constraint_set.json": mmr_bundle.constraint_set,
            "mmr_materialization_request.json": mmr_bundle.materialization_request,
            "mmr_materialization_plan.json": mmr_bundle.materialization_plan,
            "mmr_materialized_slice.json": mmr_bundle.materialized_slice,
            "mmr_cost_trace.json": mmr_bundle.cost_trace,
            "mmr_proof.json": mmr_bundle.mmr_proof,
            "mmr_document_benchmark.json": mmr_document_benchmark,
            "mmr_cache_reuse_benchmark.json": mmr_cache_reuse_benchmark,
            "mmr_divergence_runtime.json": mmr_divergence_runtime,
            "mmr_diffcache_benchmark.json": mmr_diffcache_benchmark,
            "mmr_potentialstate_runtime.json": mmr_potentialstate_runtime,
            "mmr_intrastate_delta_runtime.json": mmr_intrastate_delta_runtime,
            "mmr_microdelta_dependency_runtime.json": mmr_microdelta_dependency_runtime,
            "mmr_predictive_sparse_runtime.json": mmr_predictive_sparse_runtime,
            "mmr_bounded_predictive_runtime.json": mmr_bounded_predictive_runtime,
            "mmr_dual_cost_validation.json": mmr_dual_cost_validation,
            "mmr_autotuning_policy.json": mmr_autotuning_policy,
            "mmr_long_horizon_stability.json": mmr_long_horizon_stability,
            "mmr_external_workload_adapter.json": mmr_external_workload_adapter,
            "mmr_answer_quality_verification.json": mmr_answer_quality_verification,
            "mmr_real_user_task_benchmark.json": mmr_real_user_task_benchmark,
            "relation_graph.json": relation_graph,
            "weighted_relation_graph.json": weighted_relation_graph,
            "context_summary.json": context_summary,
            "runtime_contract_validation.json": {
                key: [issue.__dict__ for issue in issues] for key, issues in runtime_contract_results.items()
            },
            "contract_gate.json": contract_gate,
        }.items():
            path = kernel_dir / name
            write_json(path, payload)
            artifacts.append(str(path))
        for path in [
            self.runtime_dir / "stores" / "knowledge_tiles.jsonl",
            self.runtime_dir / "stores" / "proof_capsules.jsonl",
            self.runtime_dir / "stores" / "patch_ledgers.jsonl",
            self.runtime_dir / "stores" / "store_index.json",
            self.runtime_dir / "stores" / "mmr_index.sqlite",
        ]:
            artifacts.append(str(path))
        artifacts.extend(self.write_prompts())
        artifacts.extend(self.write_config())

        self.save_state(state)
        self.log(
            "contract_validation",
            {
                "cycle": state["cycle"],
                "forge_tasks": render_issues(task_issues),
                "model_roles": render_issues(model_role_issues),
                "gate": contract_gate["status"],
            },
        )
        self.log("kernel_cycle", state["last_kernel"])
        self.log("store_status", store_status)
        self.log("cycle_completed", {"cycle": state["cycle"], "artifacts": artifacts})

        return ForgeResult(
            runtime_dir=self.runtime_dir,
            used_fallback=self.used_fallback,
            cycle=state["cycle"],
            artifacts=artifacts,
            status=state["status"],
        )

    def run(self, cycles: int = 1, continuous: bool = False, sleep_seconds: float = 30.0) -> ForgeResult:
        result: ForgeResult | None = None
        completed = 0
        while True:
            if (self.runtime_dir / "STOP_FORGE").exists():
                state = self.load_state()
                state["status"] = "stopped"
                state["stop_reason"] = "STOP_FORGE present"
                state["stopped_at"] = utc_ts()
                self.save_state(state)
                self.log("stopped", {"reason": "STOP_FORGE present", "cycle": int(state.get("cycle", 0))})
                result = ForgeResult(
                    runtime_dir=self.runtime_dir,
                    used_fallback=self.used_fallback,
                    cycle=int(state.get("cycle", 0)),
                    artifacts=[] if result is None else result.artifacts,
                    status="stopped",
                )
                break

            result = self.cycle_once()
            completed += 1

            if not continuous and completed >= cycles:
                break

            if continuous:
                time.sleep(max(0.1, sleep_seconds))

        if result is None:
            state = self.load_state()
            result = ForgeResult(
                runtime_dir=self.runtime_dir,
                used_fallback=self.used_fallback,
                cycle=int(state.get("cycle", 0)),
                artifacts=[],
                status="stopped",
            )
        return result
