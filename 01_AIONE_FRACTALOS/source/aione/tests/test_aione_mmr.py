from __future__ import annotations

import sqlite3
from pathlib import Path

from aione_forge.mmr import (
    build_mmr_bundle,
    persist_mmr_index,
    render_answer_quality_verification_status,
    render_autotuning_policy_status,
    render_bounded_predictive_runtime_status,
    render_cache_reuse_benchmark_status,
    render_diffcache_benchmark_status,
    render_divergence_runtime_status,
    render_document_benchmark_status,
    render_dual_cost_validation_status,
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
    run_diffcache_benchmark,
    run_divergence_runtime,
    run_document_benchmark,
    run_dual_cost_validation,
    run_external_workload_adapter,
    run_intrastate_delta_runtime,
    run_long_horizon_stability,
    run_microdelta_dependency_runtime,
    run_potentialstate_runtime,
    run_predictive_sparse_runtime,
    run_real_user_task_benchmark,
)


def test_mmr_bundle_materializes_bounded_context() -> None:
    bundle = build_mmr_bundle(
        mission={
            "id": "MISSION-0001",
            "objective": "Test MMR",
            "constraints": ["contract_gate_required"],
            "risk_level": "low",
        },
        context_summary={
            "result_count": 5,
            "items": [
                {"id": "KT-1", "title": "A"},
                {"id": "KT-2", "title": "B"},
                {"id": "KT-3", "title": "C"},
                {"id": "KT-4", "title": "D"},
                {"id": "KT-5", "title": "E"},
            ],
        },
        cycle=1,
    )

    assert bundle.potential_state["status"] == "potential"
    assert bundle.materialization_plan["strategy"] == "summary"
    assert bundle.materialized_slice["approximation"]["used"] is True
    assert bundle.cost_trace["result"] == "better"
    assert bundle.cost_trace["metrics"]["materialized_units"] == 3
    assert bundle.cost_trace["metrics"]["avoided_units"] == 2
    assert bundle.mmr_proof["status"] == "passed"


def test_mmr_index_persists_bundle(tmp_path: Path) -> None:
    bundle = build_mmr_bundle(
        mission={
            "id": "MISSION-0002",
            "objective": "Persist MMR",
            "constraints": [],
            "risk_level": "low",
        },
        context_summary={"result_count": 1, "items": [{"id": "KT-1", "title": "A"}]},
        cycle=2,
    )
    index_path = tmp_path / "mmr_index.sqlite"

    status = persist_mmr_index(index_path, bundle)

    assert status["records_written"] == 7
    assert status["records_total"] == 7
    with sqlite3.connect(index_path) as connection:
        kinds = {row[0] for row in connection.execute("SELECT kind FROM mmr_artifacts")}
    assert "potential_state" in kinds
    assert "mmr_proof" in kinds


def test_render_mmr_status_mentions_cost_trace(tmp_path: Path) -> None:
    bundle = build_mmr_bundle(
        mission={
            "id": "MISSION-0003",
            "objective": "Render MMR",
            "constraints": [],
            "risk_level": "low",
        },
        context_summary={"result_count": 1, "items": [{"id": "KT-1", "title": "A"}]},
        cycle=3,
    )
    status = persist_mmr_index(tmp_path / "mmr_index.sqlite", bundle)

    report = render_mmr_status(bundle, status)

    assert "MMR Status" in report
    assert "Cost Trace" in report
    assert "Saved tokens:" in report
    assert "SQLite Index" in report


def test_document_benchmark_materializes_subset(tmp_path: Path) -> None:
    benchmark = run_document_benchmark(
        tmp_path / "mmr_index.sqlite",
        query="minimum materialization memory context",
        limit=2,
    )

    assert benchmark["result"] == "better"
    assert benchmark["naive"]["materialized_documents"] > benchmark["mmr"]["materialized_documents"]
    assert benchmark["saved_work_estimate"]["avoided_documents"] > 0
    assert benchmark["saved_work_estimate"]["tokens"] > 0
    assert benchmark["selected_documents"]

    report = render_document_benchmark_status(benchmark)
    assert "MMR Document Benchmark" in report
    assert "Avoided documents:" in report
    assert "Selected Documents" in report


def test_cache_reuse_benchmark_hits_and_invalidates(tmp_path: Path) -> None:
    benchmark = run_cache_reuse_benchmark(
        tmp_path / "mmr_index.sqlite",
        query="minimum materialization memory context",
        limit=2,
    )

    scenarios = benchmark["scenarios"]
    assert scenarios["naive_full_materialization"]["materialized_documents"] == 6
    assert scenarios["mmr_without_cache"]["cache_miss"] is True
    assert scenarios["mmr_with_valid_cache"]["cache_hit"] is True
    assert scenarios["mmr_with_valid_cache"]["materialized_documents"] == 0
    assert scenarios["mmr_with_invalidated_cache"]["invalidated"] is True
    assert "corpus_fingerprint_changed" in scenarios["mmr_with_invalidated_cache"]["invalidators"]
    assert benchmark["metrics"]["cache_hits"] == 1
    assert benchmark["metrics"]["cache_invalidations"] == 1
    assert benchmark["metrics"]["avoided_materialization"] > 0
    assert benchmark["metrics"]["saved_tokens"] > 0
    assert benchmark["metrics"]["latency_gain_ms"] > 0

    report = render_cache_reuse_benchmark_status(benchmark)
    assert "MMR Cache Reuse Benchmark" in report
    assert "MMR with valid cache" in report
    assert "MMR with invalidated cache" in report


def test_divergence_runtime_reuses_coherent_slices(tmp_path: Path) -> None:
    benchmark = run_divergence_runtime(
        tmp_path / "mmr_index.sqlite",
        query="minimum materialization memory context",
        limit=2,
    )

    scenarios = benchmark["scenarios"]
    stable = scenarios["stable_corpus"]["metrics"]
    low = scenarios["low_divergence"]["metrics"]
    high = scenarios["high_divergence"]["metrics"]

    assert stable["divergence_ratio"] == 0
    assert stable["rebuilt_slices"] == 0
    assert stable["reused_slices"] > 0
    assert low["divergence_ratio"] > 0
    assert low["reused_slices"] > 0
    assert low["rebuilt_slices"] == 0
    assert low["avoided_tokens"] > 0
    assert high["divergence_ratio"] > low["divergence_ratio"]
    assert high["rebuilt_slices"] > low["rebuilt_slices"]
    assert high["relative_resolution_cost"] > low["relative_resolution_cost"]
    assert "selected_slice_hash_changed" in scenarios["high_divergence"]["invalidators"]

    report = render_divergence_runtime_status(benchmark)
    assert "MMR Divergence Runtime" in report
    assert "Low divergence" in report
    assert "High divergence" in report
    assert "Relative resolution cost" in report


def test_diffcache_benchmark_uses_exact_approximate_and_divergence_cache(tmp_path: Path) -> None:
    benchmark = run_diffcache_benchmark(
        tmp_path / "mmr_index.sqlite",
        query="minimum materialization runtime memory context",
        approximate_query="minimum materialization memory context",
        limit=2,
    )

    state = benchmark["resolution_state"]
    assert state["query"] == "minimum materialization runtime memory context"
    assert state["selected_docs"]
    assert state["materialized_slice"]["documents"] == state["selected_docs"]
    assert state["corpus_fingerprint"]
    assert state["scoring_strategy"] == "lexical-v1"
    assert state["answer_fingerprint"]
    assert state["coherence_score"] >= 0.5
    assert state["created_at"]

    scenarios = benchmark["scenarios"]
    exact = scenarios["mmr_cache_exact"]["metrics"]
    approximate = scenarios["mmr_cache_approximate"]["metrics"]
    divergence = scenarios["mmr_divergence_only_after_partial_change"]["metrics"]
    no_cache = scenarios["mmr_without_cache"]["metrics"]

    assert scenarios["naive_full_materialization"]["metrics"]["materialized_tokens"] == exact[
        "total_available_tokens"
    ]
    assert no_cache["materialized_tokens"] > exact["materialized_tokens"]
    assert exact["cache_hit"] is True
    assert exact["materialized_tokens"] == 0
    assert approximate["approximate_cache_hit"] is True
    assert scenarios["mmr_cache_approximate"]["query_similarity"] >= benchmark["similarity_threshold"]
    assert divergence["divergence_ratio"] > 0
    assert divergence["reused_slices"] > 0
    assert divergence["rebuilt_slices"] > 0
    assert divergence["invalidations"] > 0
    assert divergence["coherence_score"] >= benchmark["coherence_threshold"]
    assert benchmark["divergence_map"]["changed_docs"]

    report = render_diffcache_benchmark_status(benchmark)
    assert "MMR DiffCache Benchmark" in report
    assert "MMR cache approximate" in report
    assert "Divergence Map" in report


def test_potentialstate_runtime_reuses_live_memory_between_runs(tmp_path: Path) -> None:
    index_path = tmp_path / "mmr_index.sqlite"

    first = run_potentialstate_runtime(index_path, query="kernel proof memory", limit=2)
    second = run_potentialstate_runtime(index_path, query="kernel proof memory", limit=2)

    state = first["potential_state"]
    assert state["id"].startswith("PSTATE-LIVE-")
    assert state["type"] == "memory"
    assert state["latent_payload"]["record_count"] > 0
    assert state["state_fingerprint"]
    assert state["memory_version"]
    assert state["created_at"]
    assert state["updated_at"]
    assert isinstance(state["invalidators"], list)

    materialized_slice = first["materialized_slice"]
    assert materialized_slice["potential_state_id"] == state["id"]
    assert materialized_slice["query"] == "kernel proof memory"
    assert materialized_slice["slice_payload"]["items"]
    assert materialized_slice["slice_fingerprint"]
    assert materialized_slice["coherence_score"] >= first["coherence_threshold"]
    assert materialized_slice["source_refs"]
    assert materialized_slice["created_at"]

    scenarios = first["scenarios"]
    assert scenarios["initial_resolution"]["metrics"]["rebuilt_slices"] > 0
    assert scenarios["second_resolution_same_state"]["metrics"]["reused_potential_states"] == 1
    assert scenarios["second_resolution_same_state"]["metrics"]["reused_slices"] > 0
    assert scenarios["after_low_mutation"]["metrics"]["reused_slices"] > 0
    assert scenarios["after_strong_mutation"]["metrics"]["rebuilt_slices"] > 0
    assert "source_refs_changed" in scenarios["after_strong_mutation"]["invalidators"]
    assert scenarios["after_memory_invalidator"]["metrics"]["memory_invalidation_count"] > 0
    assert scenarios["after_memory_invalidator"]["metrics"]["rebuilt_slices"] > 0
    assert first["multi_cycle"]["previous_cycle_reuse"] is False
    assert second["multi_cycle"]["previous_cycle_reuse"] is True

    report = render_potentialstate_runtime_status(second)
    assert "MMR PotentialState Runtime" in report
    assert "Previous cycle reuse: True" in report
    assert "After memory invalidator" in report


def test_intrastate_delta_runtime_rebuilds_only_changed_segments(tmp_path: Path) -> None:
    benchmark = run_intrastate_delta_runtime(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        limit=2,
    )

    segments = benchmark["base_segments"]
    base_slice = benchmark["base_materialized_slice"]
    assert segments
    assert segments[0]["id"].startswith("SEG-")
    assert segments[0]["potential_state_id"] == benchmark["potential_state"]["id"]
    assert segments[0]["segment_key"]
    assert segments[0]["segment_payload"]
    assert segments[0]["segment_fingerprint"]
    assert segments[0]["semantic_tags"]
    assert segments[0]["updated_at"]
    assert base_slice["state_segment_ids"]
    assert set(base_slice["state_segment_ids"]).issubset({segment["id"] for segment in segments})

    scenarios = benchmark["scenarios"]
    stable = scenarios["stable_state"]["metrics"]
    weak = scenarios["weak_segment_mutation"]["metrics"]
    medium = scenarios["medium_segment_mutation"]["metrics"]
    strong = scenarios["strong_segment_mutation"]["metrics"]
    global_invalidated = scenarios["global_memory_invalidation"]["metrics"]

    assert stable["changed_segments"] == 0
    assert stable["reused_segments"] > 0
    assert stable["rebuilt_segments"] == 0
    assert weak["changed_segments"] > 0
    assert weak["reused_segments"] > 0
    assert weak["rebuilt_segments"] > 0
    assert weak["avoided_rebuild_ratio"] > 0
    assert medium["delta_ratio"] > 0
    assert strong["changed_segments"] >= medium["changed_segments"]
    assert global_invalidated["rebuilt_segments"] > 0
    assert "memory_store_changed" in scenarios["global_memory_invalidation"]["invalidators"]
    assert "segment_fingerprint_changed" in scenarios["medium_segment_mutation"]["invalidators"]
    assert "source_ref_changed" in scenarios["strong_segment_mutation"]["invalidators"]

    report = render_intrastate_delta_runtime_status(benchmark)
    assert "MMR Intra-State Delta Runtime" in report
    assert "Weak segment mutation" in report
    assert "DeltaMap" in report


def test_microdelta_dependency_runtime_rebuilds_only_dependent_fragments(tmp_path: Path) -> None:
    benchmark = run_microdelta_dependency_runtime(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        limit=2,
        fragment_limit=6,
    )

    fragments = benchmark["base_microfragments"]
    base_slice = benchmark["base_materialized_slice"]
    dependency_graph = benchmark["base_dependency_graph"]
    assert fragments
    assert fragments[0]["id"].startswith("MICRO-")
    assert fragments[0]["state_segment_id"].startswith("SEG-")
    assert fragments[0]["fragment_key"]
    assert fragments[0]["fragment_payload"]
    assert fragments[0]["fragment_fingerprint"]
    assert fragments[0]["semantic_tags"]
    assert isinstance(fragments[0]["source_refs"], list)
    assert base_slice["microfragment_ids"]
    assert set(base_slice["microfragment_ids"]).issubset({fragment["id"] for fragment in fragments})
    assert dependency_graph
    assert dependency_graph[0]["slice_id"].startswith("MSLICE-DEPENDENCY-")
    assert dependency_graph[0]["depends_on_microfragment_ids"]
    assert dependency_graph[0]["invalidation_reason"] is None

    scenarios = benchmark["scenarios"]
    stable = scenarios["stable"]["metrics"]
    weak_micro = scenarios["weak_micro_mutation"]["metrics"]
    weak_segment = scenarios["weak_segment_mutation"]["metrics"]
    medium = scenarios["medium_mutation"]["metrics"]
    strong = scenarios["strong_mutation"]["metrics"]
    global_invalidated = scenarios["global_invalidation"]["metrics"]

    assert stable["changed_fragments"] == 0
    assert stable["reused_fragments"] > 0
    assert stable["rebuilt_fragments"] == 0
    assert weak_micro["changed_fragments"] == 1
    assert weak_micro["reused_fragments"] > weak_micro["rebuilt_fragments"]
    assert weak_micro["affected_slices"] == weak_micro["rebuilt_fragments"]
    assert weak_micro["avoided_rebuild_ratio"] > weak_segment["avoided_rebuild_ratio"] - 0.001
    assert weak_segment["changed_fragments"] >= weak_micro["changed_fragments"]
    assert weak_segment["reused_fragments"] > 0
    assert medium["changed_fragments"] > weak_segment["changed_fragments"]
    assert medium["relative_resolution_cost"] > weak_micro["relative_resolution_cost"]
    assert strong["changed_fragments"] >= medium["changed_fragments"]
    assert global_invalidated["rebuilt_fragments"] > 0
    assert "memory_store_changed" in scenarios["global_invalidation"]["invalidators"]
    assert "fragment_fingerprint_changed" in scenarios["weak_micro_mutation"]["invalidators"]
    assert "source_ref_changed" in scenarios["strong_mutation"]["invalidators"]

    report = render_microdelta_dependency_runtime_status(benchmark)
    assert "MMR MicroDelta Dependency Runtime" in report
    assert "Weak micro mutation" in report
    assert "SliceDependencyGraph" in report


def test_predictive_sparse_runtime_prewarms_probable_fragments(tmp_path: Path) -> None:
    benchmark = run_predictive_sparse_runtime(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        fragment_limit=6,
        prewarm_limit=4,
    )

    patterns = benchmark["predictive_patterns"]
    materialization = benchmark["predictive_materialization"]
    assert patterns
    assert patterns[0]["id"].startswith("PPAT-")
    assert patterns[0]["query_signature"]
    assert patterns[0]["mutation_signature"]
    assert patterns[0]["frequently_used_fragments"]
    assert patterns[0]["prediction_weight"] > 0
    assert patterns[0]["last_hit_at"]
    assert patterns[0]["hit_count"] > 0
    assert materialization["id"].startswith("PMAT-")
    assert materialization["prewarmed_fragments"]
    assert len(materialization["prewarmed_fragments"]) <= 4

    scenarios = benchmark["scenarios"]
    cold = scenarios["cold_runtime"]["metrics"]
    warm = scenarios["warm_runtime"]["metrics"]
    predictive = scenarios["predictive_sparse_runtime"]["metrics"]
    heavy = scenarios["heavy_divergence_runtime"]["metrics"]
    global_invalidated = scenarios["global_invalidation"]["metrics"]

    assert cold["predictive_hit_rate"] == 0
    assert cold["relative_resolution_cost"] > predictive["relative_resolution_cost"]
    assert warm["predictive_hit_rate"] == 1
    assert predictive["predictive_hit_rate"] > 0
    assert predictive["predictive_hit_rate"] < warm["predictive_hit_rate"]
    assert predictive["prewarm_accuracy"] > 0
    assert predictive["avoided_materialization_ratio"] > 0
    assert predictive["active_fragment_ratio"] > 0
    assert heavy["predictive_hit_rate"] < predictive["predictive_hit_rate"]
    assert heavy["relative_resolution_cost"] > predictive["relative_resolution_cost"]
    assert global_invalidated["predictive_hit_rate"] == 0
    assert "memory_store_changed" in scenarios["global_invalidation"]["invalidators"]

    activation_map = scenarios["predictive_sparse_runtime"]["sparse_activation_map"]
    assert activation_map["active_fragments"]
    assert activation_map["dormant_fragments"]
    assert activation_map["predictive_fragments"]
    assert activation_map["prewarmed_fragments"]

    report = render_predictive_sparse_runtime_status(benchmark)
    assert "MMR Predictive Sparse Runtime" in report
    assert "Predictive sparse runtime" in report
    assert "SparseActivationMap" in report


def test_bounded_predictive_runtime_respects_budget_and_scales(tmp_path: Path) -> None:
    benchmark = run_bounded_predictive_runtime(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        fragment_limit=6,
    )

    budget = benchmark["activation_budget"]
    assert budget["max_active_fragments"] >= 6
    assert budget["max_prewarmed_fragments"] > 0
    assert budget["max_materialized_tokens"] > 0
    assert budget["max_latency_ms"] > 0
    assert budget["budget_policy"] == "score_then_token_cap_with_fallback"

    assert set(benchmark["scaling_factors"]) == {"x1", "x5", "x10", "x25"}
    x1 = benchmark["scenarios"]["x1"]
    x25 = benchmark["scenarios"]["x25"]
    assert x25["record_count"] > x1["record_count"]
    assert x25["fragment_count"] > x1["fragment_count"]

    for scale_case in benchmark["scenarios"].values():
        bounded = scale_case["modes"]["bounded_predictive"]
        status = bounded["budget_status"]
        assert status["active_fragments_ok"] is True
        assert status["prewarmed_fragments_ok"] is True
        assert status["materialized_tokens_ok"] is True
        assert status["latency_ok"] is True
        assert bounded["metrics"]["budget_utilization"] <= 1

        predictive = scale_case["modes"]["predictive_sparse"]
        cold = scale_case["modes"]["cold"]
        assert bounded["metrics"]["relative_resolution_cost"] < cold["metrics"]["relative_resolution_cost"]
        assert bounded["metrics"]["wasted_prewarm_ratio"] <= predictive["metrics"]["wasted_prewarm_ratio"]
        assert bounded["prediction_penalty"]["penalty_score"] <= predictive["prediction_penalty"]["penalty_score"]

    assert (
        x25["modes"]["bounded_predictive"]["metrics"]["active_fragment_ratio"]
        < x1["modes"]["bounded_predictive"]["metrics"]["active_fragment_ratio"]
    )
    assert (
        x25["modes"]["bounded_predictive"]["metrics"]["total_available_tokens"]
        > x1["modes"]["bounded_predictive"]["metrics"]["total_available_tokens"]
    )
    assert benchmark["metrics"]["bounded_wasted_prewarm_ratio"] < benchmark["metrics"][
        "predictive_wasted_prewarm_ratio"
    ]

    report = render_bounded_predictive_runtime_status(benchmark)
    assert "MMR Bounded Predictive Runtime" in report
    assert "ActivationBudget" in report
    assert "PredictionPenalty" in report
    assert "x25" in report


def test_dual_cost_validation_tracks_relative_and_absolute_costs(tmp_path: Path) -> None:
    benchmark = run_dual_cost_validation(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        fragment_limit=6,
    )

    assert benchmark["id"] == "MMR-DUAL-COST-VALIDATION-0001"
    assert benchmark["result"] == "warn"
    assert set(benchmark["scaling"]) == {"x1", "x5", "x10", "x25"}
    assert set(benchmark["adversarial"]) == {
        "compressible_corpus",
        "low_compressible_corpus",
        "random_mutations",
        "out_of_distribution_query",
        "bad_predictions",
    }

    x1 = benchmark["scaling"]["x1"]
    x25 = benchmark["scaling"]["x25"]
    trace = x1["absolute_cost_trace"]
    assert trace["materialized_tokens"] > 0
    assert trace["rebuilt_fragments"] > 0
    assert trace["reused_fragments"] >= 0
    assert trace["sqlite_read_count"] > 0
    assert trace["sqlite_write_count"] > 0
    assert trace["wall_latency_ms"] >= 0
    assert trace["process_cpu_ms"] >= 0
    assert trace["peak_memory_mb"] >= 0

    report = x1["dual_cost_report"]
    assert report["relative_resolution_cost"] == x1["metrics"]["relative_resolution_cost"]
    assert report["absolute_materialization_cost"] > 0
    assert report["normalized_efficiency"] > 0
    assert "cost_discrepancy_warning" in report

    assert x25["metrics"]["relative_resolution_cost"] < x1["metrics"]["relative_resolution_cost"]
    assert x25["metrics"]["absolute_materialized_tokens"] <= x1["metrics"]["absolute_materialized_tokens"] * 2
    assert x25["dual_cost_report"]["scaling_efficiency"] > x1["dual_cost_report"]["scaling_efficiency"]

    ood = benchmark["adversarial"]["out_of_distribution_query"]["metrics"]
    bad = benchmark["adversarial"]["bad_predictions"]["metrics"]
    assert ood["out_of_distribution_fallback_rate"] == 1.0
    assert bad["prediction_false_positive_rate"] == 1.0
    assert bad["wasted_prewarm_ratio"] == 1.0
    assert benchmark["metrics"]["warning_count"] > 0

    rendered = render_dual_cost_validation_status(benchmark)
    assert "MMR Dual Cost Validation" in rendered
    assert "Scaling Sanity Check" in rendered
    assert "Adversarial Benchmark" in rendered
    assert "DualCostReport" in rendered


def test_autotuning_policy_selects_safe_runtime_mode(tmp_path: Path) -> None:
    benchmark = run_autotuning_policy(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        fragment_limit=6,
    )

    assert benchmark["id"] == "MMR-AUTOTUNING-POLICY-0001"
    assert benchmark["result"] == "adapted"
    assert set(benchmark["runtime_policies"]) == {
        "cold",
        "warm",
        "predictive_sparse",
        "bounded_predictive",
        "divergence_only",
    }
    assert set(benchmark["fixed_modes"]) == {
        "fixed_cold",
        "fixed_warm",
        "fixed_predictive",
        "fixed_bounded",
    }

    predictive = benchmark["fixed_modes"]["fixed_predictive"]
    auto_tuned = benchmark["auto_tuned"]
    decision = benchmark["policy_decision"]

    assert predictive["metrics"]["wasted_prewarm_ratio"] > 0
    assert predictive["metrics"]["warning_count"] > 0
    assert decision["selected_mode"] != "predictive_sparse"
    assert decision["fallback_used"] is True
    assert decision["avoided_bad_prediction"] is True
    assert decision["warning_reduction"] > 0
    assert auto_tuned["metrics"]["warning_count"] == 0
    assert auto_tuned["metrics"]["policy_score"] < predictive["metrics"]["policy_score"]
    assert benchmark["metrics"]["relative_cost_reduction"] > 0
    assert benchmark["metrics"]["policy_stability_score"] > 0

    selected_policy = auto_tuned["policy"]
    assert selected_policy["mode"] == decision["selected_mode"]
    assert selected_policy["max_relative_cost"] > 0
    assert selected_policy["max_absolute_latency_ms"] > 0
    assert selected_policy["max_wasted_prewarm_ratio"] >= 0
    assert selected_policy["max_warning_count"] == 0

    rendered = render_autotuning_policy_status(benchmark)
    assert "MMR Auto-Tuning Runtime Policy" in rendered
    assert "RuntimePolicy" in rendered
    assert "PolicyDecision" in rendered
    assert "Auto tuned" in rendered


def test_long_horizon_stability_tracks_runtime_episodes(tmp_path: Path) -> None:
    benchmark = run_long_horizon_stability(
        tmp_path / "mmr_index.sqlite",
        query="kernel proof memory",
        fragment_limit=6,
    )

    assert benchmark["id"] == "MMR-LONG-HORIZON-STABILITY-0001"
    assert benchmark["result"] == "stable"
    assert set(benchmark["scenarios"]) == {"10_cycles", "25_cycles", "50_cycles"}

    scenario_50 = benchmark["scenarios"]["50_cycles"]
    assert len(scenario_50["episodes"]) == 50
    first_episode = scenario_50["episodes"][0]
    for key in [
        "cycle_id",
        "selected_policy",
        "relative_cost",
        "absolute_latency_ms",
        "warning_count",
        "reused_fragments",
        "rebuilt_fragments",
        "mutation_type",
        "coherence_score",
    ]:
        assert key in first_episode

    mutation_types = {episode["mutation_type"] for episode in scenario_50["episodes"]}
    assert {"weak_repeated", "strong_rare", "bad_prediction", "out_of_distribution"}.issubset(
        mutation_types
    )

    trace = scenario_50["stability_trace"]
    assert trace["policy_switch_count"] > 0
    assert trace["average_relative_cost"] > 0
    assert trace["average_absolute_latency_ms"] > 0
    assert trace["warning_rate"] > 0
    assert trace["coherence_drift"] >= 0
    assert trace["cache_decay_rate"] >= 0
    assert trace["reuse_rate"] > 0
    assert trace["policy_stability_score"] > 0
    assert trace["long_horizon_stability_score"] > 0

    assert benchmark["metrics"]["long_horizon_stability_score"] > 0
    assert benchmark["metrics"]["policy_stability_score"] > 0
    assert benchmark["metrics"]["total_warnings"] > 0
    assert benchmark["metrics"]["recovery_after_bad_prediction"] is True

    rendered = render_long_horizon_stability_status(benchmark)
    assert "MMR Long-Horizon Runtime Stability" in rendered
    assert "StabilityTrace" in rendered
    assert "RuntimeEpisodes" in rendered
    assert "Recovery after bad prediction" in rendered


def test_external_workload_adapter_indexes_fixture_and_mutations(tmp_path: Path) -> None:
    workload = tmp_path / "workload"
    workload.mkdir()
    (workload / "README.md").write_text(
        "# Architecture\nAIONE runtime architecture uses operators and MMR layers.\nTODO: add tests.\n",
        encoding="utf-8",
    )
    (workload / "module.py").write_text(
        "import json\n\n"
        "def build_runtime():\n"
        "    assert True\n"
        "    return {'tests': 'ok'}\n",
        encoding="utf-8",
    )
    (workload / "config.yaml").write_text("dependencies:\n  - sqlite\n", encoding="utf-8")
    for ignored_directory in ("forge_runtime", "__pycache__", ".pytest_cache", ".venv", "bin", "obj"):
        directory = workload / ignored_directory
        directory.mkdir()
        (directory / "ignored.py").write_text("raise RuntimeError('must not be indexed')\n", encoding="utf-8")

    benchmark = run_external_workload_adapter(
        tmp_path / "mmr_index.sqlite",
        source_path=workload,
        queries=["architecture", "tests", "TODO"],
        chunk_line_count=2,
        materialization_limit=3,
    )

    assert benchmark["id"] == "MMR-EXTERNAL-WORKLOAD-ADAPTER-0001"
    assert benchmark["result"] == "measured"
    source = benchmark["workload_source"]
    assert source["file_count"] == 3
    assert source["total_bytes"] > 0
    assert set(source["file_types"]) == {".md", ".py", ".yaml"}
    assert source["source_fingerprint"]

    assert set(benchmark["workload_query_set"]["selected_queries"]) == {"architecture", "tests", "todo"}
    architecture = benchmark["runtime_evaluation"]["architecture"]
    assert set(architecture["modes"]) == {
        "naive_full_scan",
        "mmr_minimal",
        "diffcache",
        "microdelta",
        "bounded_predictive",
        "auto_tuned",
    }
    naive = architecture["modes"]["naive_full_scan"]["metrics"]
    minimal = architecture["modes"]["mmr_minimal"]["metrics"]
    auto_tuned = architecture["modes"]["auto_tuned"]["metrics"]
    assert minimal["materialized_chunks"] < naive["materialized_chunks"]
    assert minimal["relative_resolution_cost"] < naive["relative_resolution_cost"]
    assert auto_tuned["relative_resolution_cost"] <= minimal["relative_resolution_cost"]

    assert set(benchmark["mutation_scenarios"]) == {
        "modify_file",
        "modify_small_chunk",
        "add_file",
        "delete_file",
    }
    assert benchmark["mutation_scenarios"]["modify_small_chunk"]["metrics"]["rebuilt_chunks"] >= 1
    assert benchmark["mutation_scenarios"]["add_file"]["workload_source"]["file_count"] == 4
    assert benchmark["mutation_scenarios"]["delete_file"]["workload_source"]["file_count"] == 2
    assert benchmark["metrics"]["total_files"] == 3
    assert benchmark["metrics"]["total_chunks"] >= 3
    assert benchmark["metrics"]["max_reused_chunks"] > 0

    rendered = render_external_workload_adapter_status(benchmark)
    assert "MMR External Workload Adapter" in rendered
    assert "WorkloadSource" in rendered
    assert "Runtime Evaluation" in rendered
    assert "Mutations" in rendered


def test_answer_quality_verification_scores_sourced_answers(tmp_path: Path) -> None:
    workload = tmp_path / "workload"
    workload.mkdir()
    (workload / "README.md").write_text(
        "# Architecture\nAIONE runtime architecture uses operators and MMR layers.\nTODO: add tests.\n",
        encoding="utf-8",
    )
    (workload / "module.py").write_text(
        "import json\n\n"
        "def build_runtime():\n"
        "    assert True\n"
        "    return {'tests': 'ok'}\n",
        encoding="utf-8",
    )

    benchmark = run_answer_quality_verification(
        tmp_path / "mmr_index.sqlite",
        source_path=workload,
        queries=["architecture", "tests", "TODO"],
        chunk_line_count=2,
        materialization_limit=3,
    )

    assert benchmark["id"] == "MMR-ANSWER-QUALITY-VERIFICATION-0001"
    assert benchmark["result"] == "verified"
    assert set(benchmark["answer_quality_evaluation"]) == {"architecture", "tests", "todo"}

    architecture = benchmark["answer_quality_evaluation"]["architecture"]
    assert architecture["reference_key_points"]
    assert set(architecture["answers"]) == {
        "naive_full_scan_answer",
        "mmr_minimal_answer",
        "diffcache_answer",
        "bounded_predictive_answer",
        "auto_tuned_answer",
    }
    minimal = architecture["answers"]["mmr_minimal_answer"]
    verified = minimal["verified_answer"]
    assert verified["query"] == "architecture"
    assert verified["answer"]
    assert verified["cited_chunks"]
    assert verified["source_file_paths"]
    assert verified["evidence_score"] > 0
    assert verified["completeness_score"] > 0
    assert verified["unsupported_claim_count"] == 0
    assert verified["contradiction_count"] == 0

    metrics = minimal["metrics"]
    assert metrics["relative_resolution_cost"] < 1.0
    assert metrics["evidence_score"] == verified["evidence_score"]
    assert metrics["completeness_score"] == verified["completeness_score"]
    assert metrics["unsupported_claim_count"] == 0
    assert metrics["contradiction_count"] == 0
    assert metrics["answer_quality_score"] > 0

    naive = architecture["answers"]["naive_full_scan_answer"]["metrics"]
    auto_tuned = architecture["answers"]["auto_tuned_answer"]["metrics"]
    assert auto_tuned["answer_quality_score"] >= metrics["answer_quality_score"]
    assert naive["completeness_score"] == 1.0
    assert benchmark["metrics"]["unsupported_claim_count"] == 0
    assert benchmark["metrics"]["contradiction_count"] == 0

    rendered = render_answer_quality_verification_status(benchmark)
    assert "MMR Answer Quality Verification" in rendered
    assert "VerifiedAnswer" in rendered
    assert "SourceVerifier" in rendered
    assert "CompletenessCheck" in rendered


def test_real_user_task_benchmark_scores_agent_tasks(tmp_path: Path) -> None:
    workload = tmp_path / "workload"
    workload.mkdir()
    (workload / "README.md").write_text(
        "# AIONE architecture\n"
        "AIONE runtime architecture uses forge, operator, kernel and MMR layers.\n"
        "Feature add work should touch the CLI workload command and MMR runtime helpers.\n"
        "Risks include warning handling, safety gates, limites, unsupported claims and contradiction checks.\n"
        "Next prochaine step: extract adapter reports with source evidence quality and workload coverage.\n",
        encoding="utf-8",
    )
    (workload / "CHANGELOG.md").write_text(
        "v28 workload adapter, v29 answer quality verification and backlog resultat benchmark updates.\n",
        encoding="utf-8",
    )
    (workload / "module.py").write_text(
        "def run_runtime():\n"
        "    return {'report': 'source evidence quality', 'adapter': 'mmr'}\n",
        encoding="utf-8",
    )
    tests_dir = workload / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mmr.py").write_text(
        "import pytest\n\n"
        "def test_mmr_runtime():\n"
        "    assert 'runtime'\n",
        encoding="utf-8",
    )

    benchmark = run_real_user_task_benchmark(
        tmp_path / "mmr_index.sqlite",
        source_path=workload,
        chunk_line_count=2,
        materialization_limit=3,
    )

    assert benchmark["id"] == "MMR-REAL-USER-TASK-BENCHMARK-0001"
    assert benchmark["result"] == "measured"
    assert benchmark["metrics"]["task_count"] == 7
    assert len(benchmark["task_results"]) == 7

    expected_modes = {
        "naive_full_scan",
        "mmr_minimal",
        "diffcache",
        "microdelta",
        "bounded_predictive",
        "auto_tuned",
    }
    architecture = benchmark["task_results"]["explain_project_architecture"]
    assert set(architecture["modes"]) == expected_modes
    naive = architecture["modes"]["naive_full_scan"]["metrics"]
    minimal = architecture["modes"]["mmr_minimal"]["metrics"]
    assert minimal["relative_resolution_cost"] < naive["relative_resolution_cost"]
    assert minimal["absolute_latency_ms"] >= 0
    assert minimal["evidence_score"] > 0
    assert minimal["completeness_score"] > 0
    assert minimal["unsupported_claim_count"] == 0
    assert minimal["contradiction_count"] == 0
    assert minimal["task_success_score"] > 0
    assert minimal["source_coverage_score"] > 0

    assert benchmark["metrics"]["average_task_success_score"] > 0
    assert benchmark["metrics"]["average_source_coverage_score"] > 0
    assert benchmark["metrics"]["unsupported_claim_count"] == 0
    assert benchmark["metrics"]["contradiction_count"] == 0

    rendered = render_real_user_task_benchmark_status(benchmark)
    assert "MMR Real User Task Benchmark" in rendered
    assert "Task Set" in rendered
    assert "Task Benchmark" in rendered
    assert "VerifiedAnswer" in rendered
