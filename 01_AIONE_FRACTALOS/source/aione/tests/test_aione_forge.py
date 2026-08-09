from __future__ import annotations

import json
from pathlib import Path

from aione_forge.cli import main as cli_main
from aione_forge.forge import AioneForge


def test_forge_cycle_generates_core_artifacts(tmp_path: Path) -> None:
    forge = AioneForge(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path / "target"))
    result = forge.run(cycles=1)

    assert result.cycle == 1
    assert result.status == "cycle_artifacts_generated"
    assert (result.runtime_dir / "state" / "forge_state.json").exists()
    assert (result.runtime_dir / "logs" / "events.jsonl").exists()
    assert (result.runtime_dir / "reports" / "PLAN.md").exists()
    assert (result.runtime_dir / "reports" / "CHECKLIST.md").exists()
    assert (result.runtime_dir / "reports" / "CONTRACTS_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "KERNEL_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "LAYER_RUNTIME_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "STORE_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "MEMORY_QUERY_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "CONTRACT_GATE_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "AGENT_ORCHESTRATOR_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "AUTONOMOUS_MISSION_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "STOP_FORGE_GUIDE.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_STATUS.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_DOCUMENT_BENCHMARK.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_CACHE_REUSE_BENCHMARK.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_DIVERGENCE_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_DIFFCACHE_BENCHMARK.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_POTENTIALSTATE_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_INTRASTATE_DELTA_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_MICRODELTA_DEPENDENCY_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_PREDICTIVE_SPARSE_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_BOUNDED_PREDICTIVE_RUNTIME.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_DUAL_COST_VALIDATION.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_AUTOTUNING_POLICY.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_LONG_HORIZON_STABILITY.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_EXTERNAL_WORKLOAD_ADAPTER.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_ANSWER_QUALITY_VERIFICATION.md").exists()
    assert (result.runtime_dir / "reports" / "MMR_REAL_USER_TASK_BENCHMARK.md").exists()
    assert (result.runtime_dir / "queue" / "tasks.json").exists()
    assert (result.runtime_dir / "kernel" / "cycle_kernel.json").exists()
    assert (result.runtime_dir / "kernel" / "mission.json").exists()
    assert (result.runtime_dir / "kernel" / "route_decision.json").exists()
    assert (result.runtime_dir / "kernel" / "layer_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "layer_packet.json").exists()
    assert (result.runtime_dir / "kernel" / "layer_execution_result.json").exists()
    assert (result.runtime_dir / "kernel" / "proof_capsule.json").exists()
    assert (result.runtime_dir / "kernel" / "knowledge_tile.json").exists()
    assert (result.runtime_dir / "kernel" / "patch_ledger.json").exists()
    assert (result.runtime_dir / "kernel" / "agent_specs.json").exists()
    assert (result.runtime_dir / "kernel" / "agent_decision.json").exists()
    assert (result.runtime_dir / "kernel" / "autonomous_mission.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_bundle.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_potential_state.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_constraint_set.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_materialization_request.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_materialization_plan.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_materialized_slice.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_cost_trace.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_proof.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_document_benchmark.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_cache_reuse_benchmark.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_divergence_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_diffcache_benchmark.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_potentialstate_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_intrastate_delta_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_microdelta_dependency_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_predictive_sparse_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_bounded_predictive_runtime.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_dual_cost_validation.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_autotuning_policy.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_long_horizon_stability.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_external_workload_adapter.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_answer_quality_verification.json").exists()
    assert (result.runtime_dir / "kernel" / "mmr_real_user_task_benchmark.json").exists()
    assert (result.runtime_dir / "kernel" / "relation_graph.json").exists()
    assert (result.runtime_dir / "kernel" / "weighted_relation_graph.json").exists()
    assert (result.runtime_dir / "kernel" / "context_summary.json").exists()
    assert (result.runtime_dir / "kernel" / "runtime_contract_validation.json").exists()
    assert (result.runtime_dir / "kernel" / "contract_gate.json").exists()
    assert (result.runtime_dir / "stores" / "knowledge_tiles.jsonl").exists()
    assert (result.runtime_dir / "stores" / "proof_capsules.jsonl").exists()
    assert (result.runtime_dir / "stores" / "patch_ledgers.jsonl").exists()
    assert (result.runtime_dir / "stores" / "store_index.json").exists()
    assert (result.runtime_dir / "stores" / "mmr_index.sqlite").exists()
    assert (result.runtime_dir / "prompts" / "PLANNER.md").exists()
    assert (result.runtime_dir / "config" / "nvidia_model_roles.json").exists()
    assert (result.runtime_dir / "config" / "operator_specs.json").exists()
    assert (result.runtime_dir / "config" / "agent_specs.json").exists()
    assert (result.runtime_dir / "config" / "contract_schema_index.json").exists()

    contracts_report = (result.runtime_dir / "reports" / "CONTRACTS_STATUS.md").read_text(encoding="utf-8")
    assert "ForgeTask validation" in contracts_report
    assert "ModelRole validation" in contracts_report
    assert "Runtime contract validation" in contracts_report
    assert "AgentDecision" in contracts_report
    assert "AgentSpec" in contracts_report
    assert "AutonomousMissionSpec" in contracts_report
    assert "PotentialState" in contracts_report
    assert "MMRProof" in contracts_report
    assert "OperatorSpec" in contracts_report
    assert "PASS" in contracts_report

    contract_gate_report = (result.runtime_dir / "reports" / "CONTRACT_GATE_STATUS.md").read_text(encoding="utf-8")
    assert "Status: passed" in contract_gate_report
    assert "Can continue: True" in contract_gate_report

    agent_report = (result.runtime_dir / "reports" / "AGENT_ORCHESTRATOR_STATUS.md").read_text(encoding="utf-8")
    assert "Agent Orchestrator Status" in agent_report
    assert "Mutation allowed: False" in agent_report

    autonomous_report = (result.runtime_dir / "reports" / "AUTONOMOUS_MISSION_STATUS.md").read_text(encoding="utf-8")
    assert "Autonomous Mission Status" in autonomous_report
    assert "Mutation allowed: False" in autonomous_report

    stop_guide = (result.runtime_dir / "reports" / "STOP_FORGE_GUIDE.md").read_text(encoding="utf-8")
    assert "STOP_FORGE Guide" in stop_guide
    assert "No new cycle starts while the file exists." in stop_guide

    mmr_report = (result.runtime_dir / "reports" / "MMR_STATUS.md").read_text(encoding="utf-8")
    assert "MMR Status" in mmr_report
    assert "Potential state:" in mmr_report
    assert "SQLite Index" in mmr_report

    benchmark_report = (result.runtime_dir / "reports" / "MMR_DOCUMENT_BENCHMARK.md").read_text(encoding="utf-8")
    assert "MMR Document Benchmark" in benchmark_report
    assert "Avoided documents:" in benchmark_report

    cache_report = (result.runtime_dir / "reports" / "MMR_CACHE_REUSE_BENCHMARK.md").read_text(encoding="utf-8")
    assert "MMR Cache Reuse Benchmark" in cache_report
    assert "MMR with valid cache" in cache_report
    assert "Cache invalidations:" in cache_report

    divergence_report = (result.runtime_dir / "reports" / "MMR_DIVERGENCE_RUNTIME.md").read_text(encoding="utf-8")
    assert "MMR Divergence Runtime" in divergence_report
    assert "Low divergence" in divergence_report
    assert "High divergence" in divergence_report

    diffcache_report = (result.runtime_dir / "reports" / "MMR_DIFFCACHE_BENCHMARK.md").read_text(encoding="utf-8")
    assert "MMR DiffCache Benchmark" in diffcache_report
    assert "MMR cache exact" in diffcache_report
    assert "MMR cache approximate" in diffcache_report

    potentialstate_report = (result.runtime_dir / "reports" / "MMR_POTENTIALSTATE_RUNTIME.md").read_text(
        encoding="utf-8"
    )
    assert "MMR PotentialState Runtime" in potentialstate_report
    assert "Second resolution same state" in potentialstate_report
    assert "After memory invalidator" in potentialstate_report

    intrastate_report = (result.runtime_dir / "reports" / "MMR_INTRASTATE_DELTA_RUNTIME.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Intra-State Delta Runtime" in intrastate_report
    assert "Weak segment mutation" in intrastate_report
    assert "Global memory invalidation" in intrastate_report

    microdelta_report = (result.runtime_dir / "reports" / "MMR_MICRODELTA_DEPENDENCY_RUNTIME.md").read_text(
        encoding="utf-8"
    )
    assert "MMR MicroDelta Dependency Runtime" in microdelta_report
    assert "Weak micro mutation" in microdelta_report
    assert "SliceDependencyGraph" in microdelta_report

    predictive_report = (result.runtime_dir / "reports" / "MMR_PREDICTIVE_SPARSE_RUNTIME.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Predictive Sparse Runtime" in predictive_report
    assert "Predictive sparse runtime" in predictive_report
    assert "SparseActivationMap" in predictive_report

    bounded_report = (result.runtime_dir / "reports" / "MMR_BOUNDED_PREDICTIVE_RUNTIME.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Bounded Predictive Runtime" in bounded_report
    assert "ActivationBudget" in bounded_report
    assert "PredictionPenalty" in bounded_report

    dual_cost_report = (result.runtime_dir / "reports" / "MMR_DUAL_COST_VALIDATION.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Dual Cost Validation" in dual_cost_report
    assert "Scaling Sanity Check" in dual_cost_report
    assert "Adversarial Benchmark" in dual_cost_report

    autotuning_report = (result.runtime_dir / "reports" / "MMR_AUTOTUNING_POLICY.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Auto-Tuning Runtime Policy" in autotuning_report
    assert "RuntimePolicy" in autotuning_report
    assert "PolicyDecision" in autotuning_report

    long_horizon_report = (result.runtime_dir / "reports" / "MMR_LONG_HORIZON_STABILITY.md").read_text(
        encoding="utf-8"
    )
    assert "MMR Long-Horizon Runtime Stability" in long_horizon_report
    assert "StabilityTrace" in long_horizon_report
    assert "RuntimeEpisodes" in long_horizon_report

    external_workload_report = (
        result.runtime_dir / "reports" / "MMR_EXTERNAL_WORKLOAD_ADAPTER.md"
    ).read_text(encoding="utf-8")
    assert "MMR External Workload Adapter" in external_workload_report
    assert "WorkloadSource" in external_workload_report
    assert "Runtime Evaluation" in external_workload_report

    answer_quality_report = (
        result.runtime_dir / "reports" / "MMR_ANSWER_QUALITY_VERIFICATION.md"
    ).read_text(encoding="utf-8")
    assert "MMR Answer Quality Verification" in answer_quality_report
    assert "VerifiedAnswer" in answer_quality_report
    assert "CompletenessCheck" in answer_quality_report

    real_user_task_report = (
        result.runtime_dir / "reports" / "MMR_REAL_USER_TASK_BENCHMARK.md"
    ).read_text(encoding="utf-8")
    assert "MMR Real User Task Benchmark" in real_user_task_report
    assert "Task Set" in real_user_task_report
    assert "Task Benchmark" in real_user_task_report

    kernel_report = (result.runtime_dir / "reports" / "KERNEL_STATUS.md").read_text(encoding="utf-8")
    assert "Selected role" in kernel_report
    assert "Layer Runtime" in kernel_report
    assert "Proof capsule" in kernel_report

    layer_report = (result.runtime_dir / "reports" / "LAYER_RUNTIME_STATUS.md").read_text(encoding="utf-8")
    assert "Layer Runtime Status" in layer_report

    store_report = (result.runtime_dir / "reports" / "STORE_STATUS.md").read_text(encoding="utf-8")
    assert "Knowledge tiles" in store_report

    memory_query_report = (result.runtime_dir / "reports" / "MEMORY_QUERY_STATUS.md").read_text(encoding="utf-8")
    assert "Memory Query Status" in memory_query_report
    assert "Memory states" in memory_query_report
    assert "TruthGate" in memory_query_report


def test_stop_forge_file_stops_before_new_cycle(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "STOP_FORGE").write_text("stop", encoding="utf-8")

    forge = AioneForge(runtime_dir=str(runtime_dir), target_workspace=str(tmp_path / "target"))
    result = forge.run(cycles=1)

    assert result.status == "stopped"
    assert result.cycle == 0
    assert result.artifacts == []
    assert not (runtime_dir / "reports" / "PLAN.md").exists()

    state = (runtime_dir / "state" / "forge_state.json").read_text(encoding="utf-8")
    assert '"status": "stopped"' in state
    assert '"stop_reason": "STOP_FORGE present"' in state

    events = (runtime_dir / "logs" / "events.jsonl").read_text(encoding="utf-8")
    assert '"type": "stopped"' in events
    assert "STOP_FORGE present" in events


def test_cli_workload_command_writes_report_and_artifact(tmp_path: Path) -> None:
    workload = tmp_path / "workload"
    runtime = tmp_path / "runtime"
    workload.mkdir()
    (workload / "README.md").write_text(
        "Architecture runtime TODO tests dependencies.\n",
        encoding="utf-8",
    )
    (workload / "main.py").write_text(
        "def main():\n    assert True\n",
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "workload",
            "--runtime-dir",
            str(runtime),
            "--path",
            str(workload),
            "--queries",
            "architecture",
            "tests",
            "TODO",
            "--verify-answer",
            "--real-tasks",
        ]
    )

    assert exit_code == 0
    assert (runtime / "reports" / "MMR_EXTERNAL_WORKLOAD_ADAPTER.md").exists()
    assert (runtime / "reports" / "MMR_ANSWER_QUALITY_VERIFICATION.md").exists()
    assert (runtime / "reports" / "MMR_REAL_USER_TASK_BENCHMARK.md").exists()
    artifact = json.loads(
        (runtime / "kernel" / "mmr_external_workload_adapter.json").read_text(encoding="utf-8")
    )
    assert artifact["workload_source"]["file_count"] == 2
    assert artifact["metrics"]["total_chunks"] >= 2
    answer_artifact = json.loads(
        (runtime / "kernel" / "mmr_answer_quality_verification.json").read_text(encoding="utf-8")
    )
    assert answer_artifact["metrics"]["minimum_evidence_score"] > 0
    assert answer_artifact["metrics"]["unsupported_claim_count"] == 0
    real_tasks_artifact = json.loads(
        (runtime / "kernel" / "mmr_real_user_task_benchmark.json").read_text(encoding="utf-8")
    )
    assert real_tasks_artifact["metrics"]["task_count"] == 7
    assert real_tasks_artifact["metrics"]["average_task_success_score"] > 0


def test_forge_runs_multiple_bounded_cycles(tmp_path: Path) -> None:
    forge = AioneForge(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path / "target"))
    result = forge.run(cycles=2)

    assert result.status == "cycle_artifacts_generated"
    assert result.cycle == 2
    assert (result.runtime_dir / "reports" / "STOP_FORGE_GUIDE.md").exists()

    state = (result.runtime_dir / "state" / "forge_state.json").read_text(encoding="utf-8")
    assert '"cycle": 2' in state
    assert '"status": "cycle_artifacts_generated"' in state

    events = (result.runtime_dir / "logs" / "events.jsonl").read_text(encoding="utf-8")
    assert events.count('"type": "cycle_started"') == 2
    assert events.count('"type": "cycle_completed"') == 2

    potentialstate_runtime = json.loads(
        (result.runtime_dir / "kernel" / "mmr_potentialstate_runtime.json").read_text(encoding="utf-8")
    )
    assert potentialstate_runtime["multi_cycle"]["previous_cycle_reuse"] is True

    intrastate_runtime = json.loads(
        (result.runtime_dir / "kernel" / "mmr_intrastate_delta_runtime.json").read_text(encoding="utf-8")
    )
    assert intrastate_runtime["scenarios"]["stable_state"]["metrics"]["reused_segments"] > 0

    microdelta_runtime = json.loads(
        (result.runtime_dir / "kernel" / "mmr_microdelta_dependency_runtime.json").read_text(encoding="utf-8")
    )
    assert microdelta_runtime["scenarios"]["stable"]["metrics"]["reused_fragments"] > 0
    assert microdelta_runtime["scenarios"]["weak_micro_mutation"]["metrics"]["rebuilt_fragments"] == 1

    predictive_runtime = json.loads(
        (result.runtime_dir / "kernel" / "mmr_predictive_sparse_runtime.json").read_text(encoding="utf-8")
    )
    assert predictive_runtime["scenarios"]["predictive_sparse_runtime"]["metrics"]["predictive_hit_rate"] > 0
    assert (
        predictive_runtime["scenarios"]["predictive_sparse_runtime"]["metrics"]["relative_resolution_cost"]
        < predictive_runtime["scenarios"]["cold_runtime"]["metrics"]["relative_resolution_cost"]
    )

    bounded_runtime = json.loads(
        (result.runtime_dir / "kernel" / "mmr_bounded_predictive_runtime.json").read_text(encoding="utf-8")
    )
    bounded_x25 = bounded_runtime["scenarios"]["x25"]["modes"]["bounded_predictive"]
    assert bounded_x25["budget_status"]["prewarmed_fragments_ok"] is True
    assert bounded_x25["budget_status"]["materialized_tokens_ok"] is True
    assert bounded_x25["metrics"]["relative_resolution_cost"] < bounded_runtime["scenarios"]["x25"]["modes"][
        "cold"
    ]["metrics"]["relative_resolution_cost"]

    dual_cost = json.loads(
        (result.runtime_dir / "kernel" / "mmr_dual_cost_validation.json").read_text(encoding="utf-8")
    )
    assert dual_cost["scaling"]["x25"]["metrics"]["relative_resolution_cost"] < dual_cost["scaling"]["x1"][
        "metrics"
    ]["relative_resolution_cost"]
    assert dual_cost["adversarial"]["bad_predictions"]["metrics"]["prediction_false_positive_rate"] == 1.0

    autotuning_policy = json.loads(
        (result.runtime_dir / "kernel" / "mmr_autotuning_policy.json").read_text(encoding="utf-8")
    )
    assert autotuning_policy["policy_decision"]["selected_mode"] != "predictive_sparse"
    assert autotuning_policy["metrics"]["avoided_bad_prediction"] is True
    assert autotuning_policy["auto_tuned"]["metrics"]["warning_count"] == 0

    long_horizon = json.loads(
        (result.runtime_dir / "kernel" / "mmr_long_horizon_stability.json").read_text(encoding="utf-8")
    )
    assert len(long_horizon["scenarios"]["50_cycles"]["episodes"]) == 50
    assert long_horizon["metrics"]["recovery_after_bad_prediction"] is True
    assert long_horizon["metrics"]["long_horizon_stability_score"] > 0

    external_workload = json.loads(
        (result.runtime_dir / "kernel" / "mmr_external_workload_adapter.json").read_text(encoding="utf-8")
    )
    assert external_workload["metrics"]["total_files"] > 0
    assert external_workload["metrics"]["total_chunks"] > 0
    assert external_workload["runtime_evaluation"]["architecture"]["modes"]["mmr_minimal"]["metrics"][
        "relative_resolution_cost"
    ] < external_workload["runtime_evaluation"]["architecture"]["modes"]["naive_full_scan"]["metrics"][
        "relative_resolution_cost"
    ]

    answer_quality = json.loads(
        (result.runtime_dir / "kernel" / "mmr_answer_quality_verification.json").read_text(encoding="utf-8")
    )
    assert answer_quality["metrics"]["minimum_evidence_score"] > 0
    assert answer_quality["metrics"]["minimum_completeness_score"] > 0
    assert answer_quality["metrics"]["unsupported_claim_count"] == 0

    real_user_tasks = json.loads(
        (result.runtime_dir / "kernel" / "mmr_real_user_task_benchmark.json").read_text(encoding="utf-8")
    )
    assert real_user_tasks["metrics"]["task_count"] == 7
    assert real_user_tasks["metrics"]["average_task_success_score"] > 0
    assert real_user_tasks["metrics"]["average_source_coverage_score"] > 0
