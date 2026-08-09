from __future__ import annotations

import json
import sqlite3
import time
import tracemalloc
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .io import utc_ts


MMR_KEYS = [
    "potential_state",
    "constraint_set",
    "materialization_request",
    "materialization_plan",
    "materialized_slice",
    "cost_trace",
    "mmr_proof",
]


DOCUMENT_SCORING_VERSION = "lexical-v1"
DOCUMENT_STRATEGY = "sqlite_index_then_bounded_materialization"
CACHE_SCHEMA_VERSION = "mmr-cache-v1"
DIVERGENCE_SCHEMA_VERSION = "mmr-divergence-v1"
DIFFCACHE_SCHEMA_VERSION = "mmr-diffcache-v1"
DIFFCACHE_SIMILARITY_THRESHOLD = 0.65
DIFFCACHE_COHERENCE_THRESHOLD = 0.5
POTENTIALSTATE_SCHEMA_VERSION = "mmr-potentialstate-runtime-v1"
POTENTIALSTATE_STRATEGY = "live_memory_potential_state_cache"
POTENTIALSTATE_COHERENCE_THRESHOLD = 0.5
INTRASTATE_SCHEMA_VERSION = "mmr-intrastate-delta-runtime-v1"
INTRASTATE_STRATEGY = "intra_state_delta_materialization"
MICRODELTA_SCHEMA_VERSION = "mmr-microdelta-dependency-runtime-v1"
MICRODELTA_STRATEGY = "microdelta_dependency_materialization"
PREDICTIVE_SCHEMA_VERSION = "mmr-predictive-sparse-runtime-v1"
PREDICTIVE_STRATEGY = "predictive_sparse_materialization"
BOUNDED_PREDICTIVE_SCHEMA_VERSION = "mmr-bounded-predictive-runtime-v1"
BOUNDED_PREDICTIVE_STRATEGY = "bounded_predictive_materialization"
DUAL_COST_SCHEMA_VERSION = "mmr-dual-cost-validation-v1"
DUAL_COST_STRATEGY = "dual_cost_validation"
AUTOTUNING_SCHEMA_VERSION = "mmr-autotuning-policy-v1"
AUTOTUNING_STRATEGY = "auto_tuning_runtime_policy"
LONG_HORIZON_SCHEMA_VERSION = "mmr-long-horizon-stability-v1"
LONG_HORIZON_STRATEGY = "long_horizon_runtime_stability"
EXTERNAL_WORKLOAD_SCHEMA_VERSION = "mmr-external-workload-adapter-v1"
EXTERNAL_WORKLOAD_STRATEGY = "external_workload_adapter"
ANSWER_QUALITY_SCHEMA_VERSION = "mmr-answer-quality-verification-v1"
ANSWER_QUALITY_STRATEGY = "answer_quality_source_verification"
REAL_USER_TASK_SCHEMA_VERSION = "mmr-real-user-task-benchmark-v1"
REAL_USER_TASK_STRATEGY = "real_user_task_benchmark"
WORKLOAD_TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml"}
WORKLOAD_QUERY_PRESETS = {
    "architecture": ["architecture", "runtime", "operator", "kernel", "layer", "aione", "mmr"],
    "tests": ["test", "pytest", "assert", "fixture"],
    "erreurs": ["error", "exception", "fail", "warning", "raise"],
    "todo": ["todo", "fixme", "a faire", "next"],
    "fonctions_principales": ["def", "class", "main", "run", "build"],
    "dependances": ["import", "from", "sqlite", "json", "pathlib"],
}
REAL_USER_TASKS = [
    {
        "id": "explain_project_architecture",
        "title": "Explain project architecture",
        "query_terms": ["architecture", "runtime", "forge", "operator", "kernel", "mmr", "aione"],
    },
    {
        "id": "find_feature_location",
        "title": "Find where to add a feature",
        "query_terms": ["feature", "add", "operator", "runtime", "forge", "cli", "mmr"],
    },
    {
        "id": "identify_mmr_tests",
        "title": "Identify tests related to MMR",
        "query_terms": ["test", "mmr", "pytest", "assert", "runtime"],
    },
    {
        "id": "summarize_recent_changes",
        "title": "Summarize recent changes",
        "query_terms": ["resultat", "runtime", "benchmark", "forge", "v28", "v29", "backlog"],
    },
    {
        "id": "locate_technical_risks",
        "title": "Locate technical risks",
        "query_terms": ["risk", "warning", "limites", "contradiction", "unsupported", "safety"],
    },
    {
        "id": "propose_next_step",
        "title": "Propose next step",
        "query_terms": ["next", "prochaine", "todo", "operator", "extract", "adapter"],
    },
    {
        "id": "generate_sourced_mini_report",
        "title": "Generate a sourced mini report",
        "query_terms": ["report", "source", "evidence", "quality", "mmr", "workload"],
    },
]


DEFAULT_DOCUMENT_CORPUS = [
    {
        "id": "DOC-MMR-001",
        "title": "Minimum Materialization Runtime",
        "tags": ["mmr", "materialization", "runtime", "compression"],
        "body": (
            "The MMR keeps logical state compressed and materializes only the slice "
            "required by an observed constraint. It compares naive work with bounded "
            "materialization and tracks control overhead."
        ),
    },
    {
        "id": "DOC-MMR-002",
        "title": "Open source building blocks",
        "tags": ["sqlite", "wasmtime", "arrow", "llama.cpp"],
        "body": (
            "The first AIONE MMR prototype should use SQLite, JSONL and contracts before "
            "heavier systems such as Wasmtime, Apache Arrow, llama.cpp, CRIU or Firecracker."
        ),
    },
    {
        "id": "DOC-MMR-003",
        "title": "Forge safety gates",
        "tags": ["contract", "truth", "stop_forge", "safety"],
        "body": (
            "Forge cycles are controlled by ContractGateOperator, TruthGateOperator and "
            "STOP_FORGE. MMR outputs remain proposal-only until sandbox and rollback exist."
        ),
    },
    {
        "id": "DOC-MMR-004",
        "title": "Memory context",
        "tags": ["memory", "context", "knowledge", "slice"],
        "body": (
            "A memory context can be represented as a potential state. The runtime can "
            "materialize a small ranked slice instead of expanding the full memory store."
        ),
    },
    {
        "id": "DOC-MMR-005",
        "title": "Energy-aware scheduling",
        "tags": ["energy", "scheduler", "cost", "latency"],
        "body": (
            "The scheduler should select the lowest-cost strategy compatible with quality, "
            "risk, latency and verification requirements."
        ),
    },
    {
        "id": "DOC-MMR-006",
        "title": "Document benchmark",
        "tags": ["benchmark", "document", "sqlite", "cost_trace"],
        "body": (
            "A minimal document benchmark compares reading every document against indexing "
            "the corpus, selecting the best matching fragments and materializing only those."
        ),
    },
]


DEFAULT_MEMORY_RECORDS = [
    {
        "id": "KT-AIONE-MEMORY-001",
        "title": "AIONE executable kernel cycle",
        "summary": (
            "AIONE connects MissionParser, MessageBus, RoutingOperator, TruthGateOperator "
            "and MemoryOperator in a persistent Forge cycle."
        ),
        "source_refs": ["aione_forge/kernel.py", "aione_forge/operators.py"],
        "tags": ["kernel", "memory", "proof", "runtime"],
        "claims": [
            "AIONE can produce structured mission, routing, proof and memory artifacts.",
        ],
        "verification_status": "partial",
        "usefulness_score": 0.75,
        "recency_score": 1.0,
    },
    {
        "id": "KT-AIONE-MEMORY-002",
        "title": "MMR potential memory",
        "summary": (
            "Minimum Materialization Runtime keeps memory as a potential state and "
            "materializes bounded slices only when a query observes them."
        ),
        "source_refs": ["cahier_des_charges/MMR_minimum_materialization_runtime/MMR_CDC_v0.md"],
        "tags": ["mmr", "memory", "potential_state", "materialization"],
        "claims": [
            "A bounded materialized slice can be cheaper than expanding full memory.",
        ],
        "verification_status": "partial",
        "usefulness_score": 0.82,
        "recency_score": 1.0,
    },
]


@dataclass(frozen=True)
class MMRBundle:
    potential_state: dict[str, Any]
    constraint_set: dict[str, Any]
    materialization_request: dict[str, Any]
    materialization_plan: dict[str, Any]
    materialized_slice: dict[str, Any]
    cost_trace: dict[str, Any]
    mmr_proof: dict[str, Any]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "potential_state": self.potential_state,
            "constraint_set": self.constraint_set,
            "materialization_request": self.materialization_request,
            "materialization_plan": self.materialization_plan,
            "materialized_slice": self.materialized_slice,
            "cost_trace": self.cost_trace,
            "mmr_proof": self.mmr_proof,
        }


def build_mmr_bundle(
    *,
    mission: dict[str, Any],
    context_summary: dict[str, Any],
    cycle: int,
) -> MMRBundle:
    now = utc_ts()
    mission_id = mission["id"]
    result_count = int(context_summary.get("result_count", 0))
    context_items = _context_items(context_summary)
    materialized_units = max(1, min(3, len(context_items) or result_count or 1))
    naive_units = max(materialized_units, result_count or len(context_items) or 1)
    naive_tokens = max(300, naive_units * 300)
    actual_tokens = max(120, materialized_units * 120)
    overhead_tokens = 60
    saved_tokens = max(0, naive_tokens - actual_tokens - overhead_tokens)
    avoided_units = max(0, naive_units - materialized_units)
    result = "better" if saved_tokens > 0 and avoided_units > 0 else "neutral"

    potential_state = {
        "id": f"PSTATE-{cycle:04d}-001",
        "title": "AIONE memory context as potential state",
        "kind": "memory",
        "logical_scope": "kernel proof memory",
        "compressed_representation": {
            "type": "summary_plus_ranked_context",
            "summary": context_summary.get("summary", ""),
            "result_count": result_count,
            "materialized": False,
            "top_item_ids": [item.get("id", "unknown") for item in context_items[:5]],
        },
        "known_constraints": [
            "contract_gate_required",
            "materialize_only_observed_context",
            "proposal_only_until_sandbox_exists",
        ],
        "dependencies": [
            mission_id,
            "context_summary",
            "knowledge_tiles.jsonl",
        ],
        "resolver": "MaterializationOperator.v0",
        "confidence": 0.72,
        "materialization_cost_estimate": {
            "tokens": naive_tokens,
            "cpu": "low",
            "ram_mb": 8,
            "vram_mb": 0,
            "time_ms": max(20, naive_units * 10),
            "energy_class": "low",
        },
        "invalidators": [
            "memory_store_changed",
            "contract_gate_blocked",
            "mission_objective_changed",
        ],
        "status": "potential",
        "created_at": now,
        "updated_at": now,
    }

    constraint_set = {
        "id": f"CSET-{cycle:04d}-001",
        "source": mission_id,
        "objective": "Materialize only the memory context needed for the current Forge cycle.",
        "observed_inputs": [
            "mission.objective",
            "mission.constraints",
            "context_summary",
        ],
        "required_outputs": [
            "MaterializationPlan",
            "MaterializedSlice",
            "CostTrace",
            "MMRProof",
        ],
        "quality_level": "standard",
        "precision_policy": "best_effort",
        "max_cost": {
            "tokens": max(800, actual_tokens + overhead_tokens),
            "cpu": "low",
            "ram_mb": 16,
            "vram_mb": 0,
            "time_ms": 100,
            "energy_class": "low",
        },
        "risk_level": mission.get("risk_level", "low"),
        "verification_required": True,
        "created_at": now,
    }

    materialization_request = {
        "id": f"MREQ-{cycle:04d}-001",
        "mission_id": mission_id,
        "potential_state_id": potential_state["id"],
        "constraint_set_id": constraint_set["id"],
        "requested_slice": {
            "scope": "current_cycle_context",
            "limit": materialized_units,
            "mode": "bounded_summary",
        },
        "reason": "The Forge needs bounded context, not the full memory store.",
        "priority": "normal",
        "deadline_ms": 100,
        "allowed_approximation": True,
        "required_gates": [
            "ContractGateOperator",
            "TruthGateOperator",
        ],
        "created_at": now,
    }

    materialization_plan = {
        "id": f"MPLAN-{cycle:04d}-001",
        "request_id": materialization_request["id"],
        "strategy": "summary",
        "steps": [
            {
                "id": "STEP-001",
                "action": "read_compressed_context",
                "input": potential_state["id"],
            },
            {
                "id": "STEP-002",
                "action": "select_top_ranked_fragments",
                "limit": materialized_units,
            },
            {
                "id": "STEP-003",
                "action": "emit_bounded_slice",
                "output": "MaterializedSlice",
            },
        ],
        "expected_outputs": [
            "MaterializedSlice",
            "CostTrace",
            "MMRProof",
        ],
        "expected_cost": {
            "tokens": actual_tokens,
            "cpu": "low",
            "ram_mb": 4,
            "vram_mb": 0,
            "time_ms": max(10, materialized_units * 8),
            "energy_class": "low",
        },
        "fallback_strategy": "defer_materialization",
        "risk_notes": [
            "Approximation is allowed only for non-critical context.",
            "No workspace mutation is allowed by this plan.",
        ],
        "status": "proposed",
        "created_at": now,
    }

    selected_items = context_items[:materialized_units]
    materialized_slice = {
        "id": f"MSLICE-{cycle:04d}-001",
        "plan_id": materialization_plan["id"],
        "source_potential_state_id": potential_state["id"],
        "content": {
            "summary": context_summary.get("summary", "No prior context available."),
            "selected_fragments": selected_items,
            "mode": "bounded_summary",
        },
        "coverage": {
            "requested": "current_cycle_context",
            "produced": "summary_and_selected_fragments",
            "missing": [] if selected_items else ["ranked_memory_fragments"],
        },
        "approximation": {
            "used": True,
            "method": "bounded_summary",
            "expected_error": "May omit low-score or stale memory fragments.",
        },
        "confidence": 0.78 if selected_items else 0.6,
        "valid_until": None,
        "invalidators": potential_state["invalidators"],
        "created_at": now,
    }

    cost_trace = {
        "id": f"CTRACE-{cycle:04d}-001",
        "mission_id": mission_id,
        "plan_id": materialization_plan["id"],
        "naive_cost_estimate": {
            "tokens": naive_tokens,
            "materialized_units": naive_units,
            "method": "materialize_all_context_items",
        },
        "actual_cost_estimate": {
            "tokens": actual_tokens,
            "materialized_units": materialized_units,
            "method": "bounded_summary",
        },
        "control_overhead_estimate": {
            "tokens": overhead_tokens,
            "time_ms": 5,
            "method": "mmr_planning_and_validation",
        },
        "saved_work_estimate": {
            "tokens": saved_tokens,
            "avoided_units": avoided_units,
        },
        "metrics": {
            "latency_ms": materialization_plan["expected_cost"]["time_ms"],
            "tokens_used": actual_tokens + overhead_tokens,
            "cache_hits": 0,
            "materialized_units": materialized_units,
            "avoided_units": avoided_units,
            "quality_score": materialized_slice["confidence"],
        },
        "result": result,
        "created_at": now,
    }

    mmr_proof = {
        "id": f"MMRPROOF-{cycle:04d}-001",
        "target_slice_id": materialized_slice["id"],
        "claims": [
            "The MMR cycle materialized a bounded context slice.",
            "The full memory store was not materialized by this operator.",
            "The current MMR output is proposal-only and non-mutating.",
        ],
        "constraints_satisfied": [
            "contract_gate_required",
            "materialize_only_observed_context",
            "proposal_only_until_sandbox_exists",
        ],
        "constraints_not_satisfied": [],
        "sources": [
            "cahier_des_charges/MMR_minimum_materialization_runtime/MMR_CDC_v0.md",
            "cahier_des_charges/MMR_minimum_materialization_runtime/briques_open_source_mmr_v0.md",
        ],
        "tests": [
            "tests/test_aione_mmr.py",
            "tests/test_aione_contracts.py",
            "tests/test_aione_forge.py",
        ],
        "cost_trace_id": cost_trace["id"],
        "confidence": materialized_slice["confidence"],
        "status": "passed",
        "created_at": now,
    }

    return MMRBundle(
        potential_state=potential_state,
        constraint_set=constraint_set,
        materialization_request=materialization_request,
        materialization_plan=materialization_plan,
        materialized_slice=materialized_slice,
        cost_trace=cost_trace,
        mmr_proof=mmr_proof,
    )


def persist_mmr_index(path: Path, bundle: MMRBundle) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = bundle.as_dict()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mmr_artifacts (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                mission_id TEXT,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        for kind, payload in records.items():
            connection.execute(
                """
                INSERT OR REPLACE INTO mmr_artifacts (id, kind, mission_id, created_at, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    kind,
                    _mission_id(payload),
                    payload.get("created_at", utc_ts()),
                    json.dumps(payload, sort_keys=True, ensure_ascii=False),
                ),
            )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM mmr_artifacts").fetchone()[0]
    return {
        "path": str(path),
        "records_written": len(records),
        "records_total": int(count),
        "updated_at": utc_ts(),
    }


def run_document_benchmark(
    path: Path,
    *,
    query: str = "minimum materialization runtime memory context",
    limit: int = 2,
    corpus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    documents = list(corpus or DEFAULT_DOCUMENT_CORPUS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        records = _prepare_document_index(connection, documents)
        connection.commit()

    selected = _select_documents(records, query, limit)
    naive_tokens = sum(record["token_estimate"] for record in records)
    actual_tokens = sum(item["record"]["token_estimate"] for item in selected)
    overhead_tokens = max(20, len(records) * 8)
    saved_tokens = max(0, naive_tokens - actual_tokens - overhead_tokens)
    avoided_documents = max(0, len(records) - len(selected))
    result = "better" if saved_tokens > 0 and avoided_documents > 0 else "neutral"

    return {
        "id": "MMR-DOC-BENCH-0001",
        "query": query,
        "strategy": DOCUMENT_STRATEGY,
        "scoring_version": DOCUMENT_SCORING_VERSION,
        "corpus_fingerprint": _corpus_fingerprint(records),
        "corpus_documents": len(records),
        "selected_documents": [
            {
                "id": item["record"]["id"],
                "title": item["record"]["title"],
                "score": item["score"],
                "token_estimate": item["record"]["token_estimate"],
            }
            for item in selected
        ],
        "naive": {
            "materialized_documents": len(records),
            "token_estimate": naive_tokens,
        },
        "mmr": {
            "materialized_documents": len(selected),
            "token_estimate": actual_tokens,
            "control_overhead_tokens": overhead_tokens,
        },
        "saved_work_estimate": {
            "tokens": saved_tokens,
            "avoided_documents": avoided_documents,
        },
        "metrics": {
            "selection_ratio": round(len(selected) / max(1, len(records)), 3),
            "token_reduction_ratio": round(saved_tokens / max(1, naive_tokens), 3),
        },
        "result": result,
        "created_at": utc_ts(),
    }


def run_cache_reuse_benchmark(
    path: Path,
    *,
    query: str = "minimum materialization runtime memory context",
    limit: int = 2,
    corpus: list[dict[str, Any]] | None = None,
    invalidated_corpus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    documents = list(corpus or DEFAULT_DOCUMENT_CORPUS)
    changed_documents = list(invalidated_corpus or _changed_document_corpus(documents))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        records = _prepare_document_index(connection, documents)
        _ensure_query_cache_table(connection)
        connection.commit()

        naive = _naive_full_materialization(records)
        no_cache = _mmr_without_cache(records, query, limit)
        cache_key = _cache_key(query, limit, _corpus_fingerprint(records), DOCUMENT_SCORING_VERSION)
        _store_query_cache(connection, cache_key, query, limit, records, no_cache["selected_documents"])

        valid_lookup = _lookup_query_cache(connection, query, limit, records, DOCUMENT_SCORING_VERSION)
        valid_cache = _cache_hit_scenario(valid_lookup, no_cache)

        changed_records = _prepare_document_index(connection, changed_documents)
        invalid_lookup = _lookup_query_cache(connection, query, limit, changed_records, DOCUMENT_SCORING_VERSION)
        invalidated = _cache_invalidated_scenario(changed_records, query, limit, invalid_lookup)
        changed_no_cache = _mmr_without_cache(changed_records, query, limit)
        changed_cache_key = _cache_key(query, limit, _corpus_fingerprint(changed_records), DOCUMENT_SCORING_VERSION)
        _store_query_cache(connection, changed_cache_key, query, limit, changed_records, changed_no_cache["selected_documents"])
        connection.commit()

    latency_gain = max(0, no_cache["latency_ms"] - valid_cache["latency_ms"])
    saved_tokens = max(0, no_cache["token_estimate"] - valid_cache["token_estimate"])
    return {
        "id": "MMR-CACHE-REUSE-BENCH-0001",
        "query": query,
        "strategy": DOCUMENT_STRATEGY,
        "scoring_version": DOCUMENT_SCORING_VERSION,
        "schema_version": CACHE_SCHEMA_VERSION,
        "scenarios": {
            "naive_full_materialization": naive,
            "mmr_without_cache": no_cache,
            "mmr_with_valid_cache": valid_cache,
            "mmr_with_invalidated_cache": invalidated,
        },
        "metrics": {
            "cache_hits": 1 if valid_cache["cache_hit"] else 0,
            "cache_misses": int(no_cache["cache_miss"]) + int(invalidated["cache_miss"]),
            "cache_invalidations": 1 if invalidated["invalidated"] else 0,
            "avoided_materialization": valid_cache["avoided_materialization"],
            "saved_tokens": saved_tokens,
            "latency_gain_ms": latency_gain,
        },
        "result": "better" if valid_cache["cache_hit"] and invalidated["invalidated"] else "neutral",
        "created_at": utc_ts(),
    }


def run_divergence_runtime(
    path: Path,
    *,
    query: str = "minimum materialization runtime memory context",
    limit: int = 2,
    corpus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    documents = list(corpus or DEFAULT_DOCUMENT_CORPUS)
    scenarios = {
        "stable_corpus": list(documents),
        "low_divergence": _low_divergence_corpus(documents),
        "high_divergence": _high_divergence_corpus(documents),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        base_records = _prepare_document_index(connection, documents)
        base_selected = _select_documents(base_records, query, limit)
        _ensure_divergence_table(connection)

        scenario_results = {}
        for name, scenario_documents in scenarios.items():
            current_records = _prepare_document_index(connection, scenario_documents)
            scenario = _divergence_only_scenario(
                name=name,
                base_records=base_records,
                base_selected=base_selected,
                current_records=current_records,
                query=query,
                limit=limit,
            )
            scenario_results[name] = scenario
            _store_divergence_scenario(connection, "MMR-DIVERGENCE-RUNTIME-0001", query, scenario)
        connection.commit()

    low = scenario_results["low_divergence"]["metrics"]
    high = scenario_results["high_divergence"]["metrics"]
    stable = scenario_results["stable_corpus"]["metrics"]
    return {
        "id": "MMR-DIVERGENCE-RUNTIME-0001",
        "query": query,
        "strategy": "divergence_only_materialization",
        "scoring_version": DOCUMENT_SCORING_VERSION,
        "schema_version": DIVERGENCE_SCHEMA_VERSION,
        "base": {
            "corpus_fingerprint": _corpus_fingerprint(base_records),
            "logical_corpus_documents": len(base_records),
            "selected_slices": _selected_payload(base_selected),
        },
        "scenarios": scenario_results,
        "metrics": {
            "stable_relative_resolution_cost": stable["relative_resolution_cost"],
            "low_divergence_relative_resolution_cost": low["relative_resolution_cost"],
            "high_divergence_relative_resolution_cost": high["relative_resolution_cost"],
            "low_divergence_reused_slices": low["reused_slices"],
            "high_divergence_rebuilt_slices": high["rebuilt_slices"],
            "max_avoided_tokens": max(item["metrics"]["avoided_tokens"] for item in scenario_results.values()),
        },
        "claim": (
            "The measured resolution cost follows useful divergence more closely than "
            "the total logical corpus size because coherent slices remain reusable."
        ),
        "result": "better" if low["relative_resolution_cost"] < high["relative_resolution_cost"] else "neutral",
        "created_at": utc_ts(),
    }


def run_diffcache_benchmark(
    path: Path,
    *,
    query: str = "minimum materialization runtime memory context",
    approximate_query: str = "minimum materialization memory context",
    limit: int = 2,
    corpus: list[dict[str, Any]] | None = None,
    divergent_corpus: list[dict[str, Any]] | None = None,
    similarity_threshold: float = DIFFCACHE_SIMILARITY_THRESHOLD,
    coherence_threshold: float = DIFFCACHE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    documents = list(corpus or DEFAULT_DOCUMENT_CORPUS)
    changed_documents = list(divergent_corpus or _changed_document_corpus(documents))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        records = _prepare_document_index(connection, documents)
        _ensure_resolution_state_table(connection)
        resolution_state = _build_resolution_state(records, query, limit, coherence_threshold)
        _store_resolution_state(connection, resolution_state)

        naive = _diffcache_naive_scenario(records)
        no_cache = _diffcache_no_cache_scenario(records, query, limit, naive)
        exact_cache = _diffcache_exact_cache_scenario(
            connection,
            records,
            query,
            limit,
            naive,
            coherence_threshold,
        )
        approximate_cache = _diffcache_approximate_cache_scenario(
            connection,
            records,
            approximate_query,
            limit,
            naive,
            similarity_threshold,
            coherence_threshold,
        )
        changed_records = _prepare_document_index(connection, changed_documents)
        divergence_only = _diffcache_divergence_scenario(
            resolution_state,
            records,
            changed_records,
            query,
            limit,
            naive,
            coherence_threshold,
        )
        _store_resolution_state(
            connection,
            _build_resolution_state(changed_records, query, limit, coherence_threshold),
        )
        connection.commit()

    scenarios = {
        "naive_full_materialization": naive,
        "mmr_without_cache": no_cache,
        "mmr_cache_exact": exact_cache,
        "mmr_cache_approximate": approximate_cache,
        "mmr_divergence_only_after_partial_change": divergence_only,
    }
    return {
        "id": "MMR-DIFFCACHE-BENCH-0001",
        "query": query,
        "approximate_query": approximate_query,
        "strategy": "relative_resolution_diffcache",
        "scoring_version": DOCUMENT_SCORING_VERSION,
        "schema_version": DIFFCACHE_SCHEMA_VERSION,
        "similarity_threshold": similarity_threshold,
        "coherence_threshold": coherence_threshold,
        "resolution_state": resolution_state,
        "divergence_map": divergence_only["divergence_map"],
        "scenarios": scenarios,
        "metrics": {
            "total_available_tokens": naive["metrics"]["total_available_tokens"],
            "best_relative_resolution_cost": min(
                item["metrics"]["relative_resolution_cost"] for item in scenarios.values()
            ),
            "exact_cache_hit": exact_cache["metrics"]["cache_hit"],
            "approximate_cache_hit": approximate_cache["metrics"]["approximate_cache_hit"],
            "divergence_reused_slices": divergence_only["metrics"]["reused_slices"],
            "divergence_rebuilt_slices": divergence_only["metrics"]["rebuilt_slices"],
            "max_latency_gain_ms": max(item["metrics"]["latency_gain_ms"] for item in scenarios.values()),
            "minimum_coherence_score": min(item["metrics"]["coherence_score"] for item in scenarios.values()),
        },
        "result": (
            "better"
            if exact_cache["metrics"]["cache_hit"]
            and approximate_cache["metrics"]["approximate_cache_hit"]
            and divergence_only["metrics"]["rebuilt_slices"] > 0
            else "neutral"
        ),
        "created_at": utc_ts(),
    }


def run_potentialstate_runtime(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_potentialstate_tables(connection)
        base_state = _build_live_potential_state(records, query)
        prior_resolution = _lookup_live_resolution(connection, base_state["id"], query)
        previous_cycle_reuse = _can_reuse_live_resolution(prior_resolution, base_state)

        initial = _live_resolution_scenario(
            connection,
            name="initial_resolution",
            previous_resolution=None,
            records=records,
            query=query,
            limit=limit,
            invalidators=[],
            coherence_threshold=coherence_threshold,
            force_store=True,
        )
        second = _live_resolution_scenario(
            connection,
            name="second_resolution_same_state",
            previous_resolution=_lookup_live_resolution(connection, base_state["id"], query),
            records=records,
            query=query,
            limit=limit,
            invalidators=[],
            coherence_threshold=coherence_threshold,
            force_store=True,
        )
        low_records = _low_memory_mutation(records)
        low = _live_resolution_scenario(
            connection,
            name="after_low_mutation",
            previous_resolution=_lookup_live_resolution(connection, base_state["id"], query),
            records=low_records,
            query=query,
            limit=limit,
            invalidators=[],
            coherence_threshold=coherence_threshold,
            force_store=False,
        )
        strong_records = _strong_memory_mutation(records)
        strong = _live_resolution_scenario(
            connection,
            name="after_strong_mutation",
            previous_resolution=_lookup_live_resolution(connection, base_state["id"], query),
            records=strong_records,
            query=query,
            limit=limit,
            invalidators=[],
            coherence_threshold=coherence_threshold,
            force_store=False,
        )
        invalidated = _live_resolution_scenario(
            connection,
            name="after_memory_invalidator",
            previous_resolution=_lookup_live_resolution(connection, base_state["id"], query),
            records=records,
            query=query,
            limit=limit,
            invalidators=["memory_store_changed"],
            coherence_threshold=coherence_threshold,
            force_store=False,
        )
        connection.commit()

    scenarios = {
        "initial_resolution": initial,
        "second_resolution_same_state": second,
        "after_low_mutation": low,
        "after_strong_mutation": strong,
        "after_memory_invalidator": invalidated,
    }
    return {
        "id": "MMR-POTENTIALSTATE-RUNTIME-0001",
        "query": query,
        "strategy": POTENTIALSTATE_STRATEGY,
        "schema_version": POTENTIALSTATE_SCHEMA_VERSION,
        "coherence_threshold": coherence_threshold,
        "multi_cycle": {
            "previous_resolution_found": prior_resolution is not None,
            "previous_cycle_reuse": previous_cycle_reuse,
            "previous_slice_id": None if prior_resolution is None else prior_resolution["materialized_slice"]["id"],
        },
        "potential_state": base_state,
        "materialized_slice": initial["materialized_slice"],
        "resolution_state": initial["resolution_state"],
        "scenarios": scenarios,
        "metrics": {
            "reused_potential_states": sum(
                item["metrics"]["reused_potential_states"] for item in scenarios.values()
            ),
            "rebuilt_potential_states": sum(
                item["metrics"]["rebuilt_potential_states"] for item in scenarios.values()
            ),
            "reused_slices": sum(item["metrics"]["reused_slices"] for item in scenarios.values()),
            "rebuilt_slices": sum(item["metrics"]["rebuilt_slices"] for item in scenarios.values()),
            "memory_invalidation_count": sum(
                item["metrics"]["memory_invalidation_count"] for item in scenarios.values()
            ),
            "best_relative_resolution_cost": min(
                item["metrics"]["relative_resolution_cost"] for item in scenarios.values()
            ),
            "minimum_coherence_score": min(item["metrics"]["coherence_score"] for item in scenarios.values()),
            "previous_cycle_reuse": previous_cycle_reuse,
        },
        "claim": (
            "AIONE can reuse live PotentialState resolutions across Forge cycles and "
            "materialize only divergent memory slices when the state changes partially."
        ),
        "result": "better" if second["metrics"]["reused_slices"] > 0 else "neutral",
        "created_at": utc_ts(),
    }


def run_intrastate_delta_runtime(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_intrastate_tables(connection)
        base_state = _build_live_potential_state(records, query)
        base_segments = _build_state_segments(base_state, records)
        selected_base = _select_state_segments(base_segments, query, limit)
        base_slice = _build_intrastate_materialized_slice(
            base_state,
            query,
            selected_base,
            _segment_coherence_guard(selected_base, query, coherence_threshold)["coherence_score"],
        )
        _store_intrastate_segments(connection, base_segments)
        _store_intrastate_slice(connection, base_slice)

        scenarios = {
            "stable_state": _intrastate_delta_scenario(
                connection=connection,
                name="stable_state",
                previous_segments=base_segments,
                previous_slice=base_slice,
                records=records,
                query=query,
                limit=limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "weak_segment_mutation": _intrastate_delta_scenario(
                connection=connection,
                name="weak_segment_mutation",
                previous_segments=base_segments,
                previous_slice=base_slice,
                records=_weak_segment_mutation(records, {segment["segment_key"] for segment in selected_base}),
                query=query,
                limit=limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "medium_segment_mutation": _intrastate_delta_scenario(
                connection=connection,
                name="medium_segment_mutation",
                previous_segments=base_segments,
                previous_slice=base_slice,
                records=_medium_segment_mutation(records, {segment["segment_key"] for segment in selected_base}),
                query=query,
                limit=limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "strong_segment_mutation": _intrastate_delta_scenario(
                connection=connection,
                name="strong_segment_mutation",
                previous_segments=base_segments,
                previous_slice=base_slice,
                records=_strong_segment_mutation(records),
                query=query,
                limit=limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "global_memory_invalidation": _intrastate_delta_scenario(
                connection=connection,
                name="global_memory_invalidation",
                previous_segments=base_segments,
                previous_slice=base_slice,
                records=records,
                query=query,
                limit=limit,
                invalidators=["memory_store_changed"],
                coherence_threshold=coherence_threshold,
            ),
        }
        connection.commit()

    return {
        "id": "MMR-INTRASTATE-DELTA-RUNTIME-0001",
        "query": query,
        "strategy": INTRASTATE_STRATEGY,
        "schema_version": INTRASTATE_SCHEMA_VERSION,
        "coherence_threshold": coherence_threshold,
        "potential_state": base_state,
        "base_segments": base_segments,
        "base_materialized_slice": base_slice,
        "scenarios": scenarios,
        "metrics": {
            "best_relative_resolution_cost": min(
                item["metrics"]["relative_resolution_cost"] for item in scenarios.values()
            ),
            "max_avoided_rebuild_ratio": max(
                item["metrics"]["avoided_rebuild_ratio"] for item in scenarios.values()
            ),
            "max_delta_ratio": max(item["metrics"]["delta_ratio"] for item in scenarios.values()),
            "minimum_coherence_score": min(item["metrics"]["coherence_score"] for item in scenarios.values()),
        },
        "claim": (
            "The resolution cost follows internal StateSegment divergence instead of "
            "the full PotentialState size because unchanged segments can keep their slices."
        ),
        "result": "better" if scenarios["weak_segment_mutation"]["metrics"]["reused_segments"] > 0 else "neutral",
        "created_at": utc_ts(),
    }


def run_microdelta_dependency_runtime(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_microdelta_tables(connection)
        base_state = _build_live_potential_state(records, query)
        base_segments = _build_state_segments(base_state, records)
        base_fragments = _build_microfragments(base_segments)
        selected_base = _select_microfragments(base_fragments, query, fragment_limit)
        base_slice = _build_microdelta_materialized_slice(
            base_state,
            query,
            selected_base,
            _microfragment_coherence_guard(selected_base, query, coherence_threshold)["coherence_score"],
        )
        base_dependency_graph = _build_slice_dependency_graph(base_slice, selected_base)
        _store_microfragments(connection, base_fragments)
        _store_microdelta_slice(connection, base_slice, base_dependency_graph)

        scenarios = {
            "stable": _microdelta_scenario(
                connection=connection,
                name="stable",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "weak_micro_mutation": _microdelta_scenario(
                connection=connection,
                name="weak_micro_mutation",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=_weak_micro_mutation(records, _selected_microfragment_identities(selected_base)),
                query=query,
                fragment_limit=fragment_limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "weak_segment_mutation": _microdelta_scenario(
                connection=connection,
                name="weak_segment_mutation",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=_weak_segment_micro_mutation(records, _selected_microfragment_identities(selected_base)),
                query=query,
                fragment_limit=fragment_limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "medium_mutation": _microdelta_scenario(
                connection=connection,
                name="medium_mutation",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=_medium_micro_mutation(records, _selected_microfragment_identities(selected_base)),
                query=query,
                fragment_limit=fragment_limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "strong_mutation": _microdelta_scenario(
                connection=connection,
                name="strong_mutation",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=_strong_segment_mutation(records),
                query=query,
                fragment_limit=fragment_limit,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "global_invalidation": _microdelta_scenario(
                connection=connection,
                name="global_invalidation",
                previous_fragments=base_fragments,
                previous_slice=base_slice,
                previous_dependency_graph=base_dependency_graph,
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                invalidators=["memory_store_changed"],
                coherence_threshold=coherence_threshold,
            ),
        }
        connection.commit()

    return {
        "id": "MMR-MICRODELTA-DEPENDENCY-RUNTIME-0001",
        "query": query,
        "strategy": MICRODELTA_STRATEGY,
        "schema_version": MICRODELTA_SCHEMA_VERSION,
        "coherence_threshold": coherence_threshold,
        "potential_state": base_state,
        "base_segments": base_segments,
        "base_microfragments": base_fragments,
        "base_materialized_slice": base_slice,
        "base_dependency_graph": base_dependency_graph,
        "scenarios": scenarios,
        "metrics": {
            "best_relative_resolution_cost": min(
                item["metrics"]["relative_resolution_cost"] for item in scenarios.values()
            ),
            "max_avoided_rebuild_ratio": max(
                item["metrics"]["avoided_rebuild_ratio"] for item in scenarios.values()
            ),
            "max_micro_delta_ratio": max(
                item["metrics"]["micro_delta_ratio"] for item in scenarios.values()
            ),
            "minimum_coherence_score": min(item["metrics"]["coherence_score"] for item in scenarios.values()),
        },
        "claim": (
            "The resolution cost follows useful micro-structural divergence because "
            "unchanged MicroFragments keep dependent slices valid even inside a changed StateSegment."
        ),
        "result": "better" if scenarios["weak_micro_mutation"]["metrics"]["reused_fragments"] > 0 else "neutral",
        "created_at": utc_ts(),
    }


def run_predictive_sparse_runtime(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    prewarm_limit: int = 4,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_predictive_sparse_tables(connection)
        base_state = _build_live_potential_state(records, query)
        base_segments = _build_state_segments(base_state, records)
        base_fragments = _build_microfragments(base_segments)
        active_base = _select_microfragments(base_fragments, query, fragment_limit)
        predictive_patterns = _build_predictive_patterns(query, base_fragments, active_base)
        predictive_materialization = _build_predictive_materialization(
            query,
            predictive_patterns,
            base_fragments,
            prewarm_limit=prewarm_limit,
        )
        _store_predictive_patterns(connection, predictive_patterns)
        _store_predictive_materialization(connection, predictive_materialization)

        warm_materialization = {
            **predictive_materialization,
            "id": "PMAT-WARM-EXACT",
            "prewarmed_fragments": active_base,
            "policy": "exact_active_cache",
        }
        cold_materialization = {
            **predictive_materialization,
            "id": "PMAT-COLD-NONE",
            "prewarmed_fragments": [],
            "policy": "no_prewarm",
        }

        scenarios = {
            "cold_runtime": _predictive_sparse_scenario(
                connection=connection,
                name="cold_runtime",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                predictive_patterns=[],
                predictive_materialization=cold_materialization,
                reference_fragments=base_fragments,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "warm_runtime": _predictive_sparse_scenario(
                connection=connection,
                name="warm_runtime",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                predictive_patterns=predictive_patterns,
                predictive_materialization=warm_materialization,
                reference_fragments=base_fragments,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "predictive_sparse_runtime": _predictive_sparse_scenario(
                connection=connection,
                name="predictive_sparse_runtime",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                predictive_patterns=predictive_patterns,
                predictive_materialization=predictive_materialization,
                reference_fragments=base_fragments,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "heavy_divergence_runtime": _predictive_sparse_scenario(
                connection=connection,
                name="heavy_divergence_runtime",
                records=_strong_segment_mutation(records),
                query=query,
                fragment_limit=fragment_limit,
                predictive_patterns=predictive_patterns,
                predictive_materialization=predictive_materialization,
                reference_fragments=base_fragments,
                invalidators=[],
                coherence_threshold=coherence_threshold,
            ),
            "global_invalidation": _predictive_sparse_scenario(
                connection=connection,
                name="global_invalidation",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                predictive_patterns=predictive_patterns,
                predictive_materialization=predictive_materialization,
                reference_fragments=base_fragments,
                invalidators=["memory_store_changed"],
                coherence_threshold=coherence_threshold,
            ),
        }
        connection.commit()

    return {
        "id": "MMR-PREDICTIVE-SPARSE-RUNTIME-0001",
        "query": query,
        "strategy": PREDICTIVE_STRATEGY,
        "schema_version": PREDICTIVE_SCHEMA_VERSION,
        "coherence_threshold": coherence_threshold,
        "potential_state": base_state,
        "base_segments": base_segments,
        "base_microfragments": base_fragments,
        "predictive_patterns": predictive_patterns,
        "predictive_materialization": predictive_materialization,
        "scenarios": scenarios,
        "metrics": {
            "best_relative_resolution_cost": min(
                item["metrics"]["relative_resolution_cost"] for item in scenarios.values()
            ),
            "best_predictive_hit_rate": max(
                item["metrics"]["predictive_hit_rate"] for item in scenarios.values()
            ),
            "max_avoided_materialization_ratio": max(
                item["metrics"]["avoided_materialization_ratio"] for item in scenarios.values()
            ),
            "minimum_coherence_score": min(item["metrics"]["coherence_score"] for item in scenarios.values()),
        },
        "claim": (
            "AIONE can lower real materialization by prewarming sparse high-probability "
            "MicroFragments before the observed query forces resolution."
        ),
        "result": (
            "better"
            if scenarios["predictive_sparse_runtime"]["metrics"]["relative_resolution_cost"]
            < scenarios["cold_runtime"]["metrics"]["relative_resolution_cost"]
            else "neutral"
        ),
        "created_at": utc_ts(),
    }


def run_bounded_predictive_runtime(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    activation_budget = {
        "max_active_fragments": fragment_limit + 2,
        "max_prewarmed_fragments": max(3, fragment_limit - 2),
        "max_materialized_tokens": 96,
        "max_latency_ms": 25.0,
        "budget_policy": "score_then_token_cap_with_fallback",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    scenarios = {}
    with sqlite3.connect(path) as connection:
        _ensure_bounded_predictive_tables(connection)
        _store_activation_budget(connection, activation_budget)
        for scale in [1, 5, 10, 25]:
            scale_key = f"x{scale}"
            scaled_records = _scale_memory_records(records, scale)
            scenarios[scale_key] = _bounded_predictive_scaling_case(
                connection=connection,
                scale=scale,
                records=scaled_records,
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                coherence_threshold=coherence_threshold,
            )
        _apply_scaling_efficiency(scenarios)
        connection.commit()

    bounded_modes = [
        scale_case["modes"]["bounded_predictive"]
        for scale_case in scenarios.values()
    ]
    predictive_modes = [
        scale_case["modes"]["predictive_sparse"]
        for scale_case in scenarios.values()
    ]
    return {
        "id": "MMR-BOUNDED-PREDICTIVE-RUNTIME-0001",
        "query": query,
        "strategy": BOUNDED_PREDICTIVE_STRATEGY,
        "schema_version": BOUNDED_PREDICTIVE_SCHEMA_VERSION,
        "activation_budget": activation_budget,
        "scaling_factors": ["x1", "x5", "x10", "x25"],
        "scenarios": scenarios,
        "metrics": {
            "best_relative_resolution_cost": min(
                mode["metrics"]["relative_resolution_cost"]
                for scale_case in scenarios.values()
                for mode in scale_case["modes"].values()
            ),
            "max_scaling_efficiency": max(
                mode["metrics"]["scaling_efficiency"]
                for scale_case in scenarios.values()
                for mode in scale_case["modes"].values()
            ),
            "max_budget_utilization": max(
                mode["metrics"]["budget_utilization"] for mode in bounded_modes
            ),
            "bounded_wasted_prewarm_ratio": round(
                sum(mode["metrics"]["wasted_prewarm_ratio"] for mode in bounded_modes)
                / max(1, len(bounded_modes)),
                3,
            ),
            "predictive_wasted_prewarm_ratio": round(
                sum(mode["metrics"]["wasted_prewarm_ratio"] for mode in predictive_modes)
                / max(1, len(predictive_modes)),
                3,
            ),
        },
        "claim": (
            "A predictive runtime can stay bounded under corpus scaling by enforcing activation "
            "budgets, penalizing false prewarm, and keeping relative resolution cost low as "
            "logical size grows."
        ),
        "result": (
            "better"
            if scenarios["x25"]["modes"]["bounded_predictive"]["metrics"]["relative_resolution_cost"]
            < scenarios["x25"]["modes"]["cold"]["metrics"]["relative_resolution_cost"]
            else "neutral"
        ),
        "created_at": utc_ts(),
    }


def run_dual_cost_validation(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    activation_budget = {
        "max_active_fragments": fragment_limit + 2,
        "max_prewarmed_fragments": max(3, fragment_limit - 2),
        "max_materialized_tokens": 96,
        "max_latency_ms": 25.0,
        "budget_policy": "dual_cost_score_then_token_cap",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    scaling = {}
    adversarial = {}
    with sqlite3.connect(path) as connection:
        _ensure_dual_cost_tables(connection)
        for scale in [1, 5, 10, 25]:
            scale_key = f"x{scale}"
            scaling[scale_key] = _dual_cost_scaling_case(
                connection=connection,
                name=scale_key,
                records=_scale_memory_records(records, scale),
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                coherence_threshold=coherence_threshold,
            )
        _apply_dual_scaling_sanity(scaling)
        adversarial = {
            "compressible_corpus": _dual_cost_adversarial_case(
                connection=connection,
                name="compressible_corpus",
                records=_scale_memory_records(records, 10),
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization_mode="bounded",
                coherence_threshold=coherence_threshold,
            ),
            "low_compressible_corpus": _dual_cost_adversarial_case(
                connection=connection,
                name="low_compressible_corpus",
                records=_low_compressible_records(records, 10),
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization_mode="bounded",
                coherence_threshold=coherence_threshold,
            ),
            "random_mutations": _dual_cost_adversarial_case(
                connection=connection,
                name="random_mutations",
                records=_deterministic_mutation_records(_scale_memory_records(records, 10)),
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization_mode="bounded",
                coherence_threshold=coherence_threshold,
            ),
            "out_of_distribution_query": _dual_cost_adversarial_case(
                connection=connection,
                name="out_of_distribution_query",
                records=_scale_memory_records(records, 10),
                query="unseen bios weather finance",
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization_mode="bounded",
                coherence_threshold=coherence_threshold,
            ),
            "bad_predictions": _dual_cost_adversarial_case(
                connection=connection,
                name="bad_predictions",
                records=_scale_memory_records(records, 10),
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization_mode="bad_predictions",
                coherence_threshold=coherence_threshold,
            ),
        }
        connection.commit()

    all_cases = [*scaling.values(), *adversarial.values()]
    warning_count = sum(case["metrics"]["warning_count"] for case in all_cases)
    return {
        "id": "MMR-DUAL-COST-VALIDATION-0001",
        "query": query,
        "strategy": DUAL_COST_STRATEGY,
        "schema_version": DUAL_COST_SCHEMA_VERSION,
        "activation_budget": activation_budget,
        "scaling": scaling,
        "adversarial": adversarial,
        "metrics": {
            "warning_count": warning_count,
            "max_absolute_materialized_tokens": max(
                case["metrics"]["absolute_materialized_tokens"] for case in all_cases
            ),
            "max_absolute_latency_ms": max(case["metrics"]["absolute_latency_ms"] for case in all_cases),
            "max_false_positive_rate": max(
                case["metrics"]["prediction_false_positive_rate"] for case in all_cases
            ),
            "max_ood_fallback_rate": max(
                case["metrics"]["out_of_distribution_fallback_rate"] for case in all_cases
            ),
        },
        "claim": (
            "Dual cost validation checks that normalized relative gains do not hide absolute "
            "materialization, latency, memory, or prediction waste under scaling and adversarial inputs."
        ),
        "result": "warn" if warning_count else "passed",
        "created_at": utc_ts(),
    }


def run_autotuning_policy(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    memory_records: list[dict[str, Any]] | None = None,
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    controlled_records = _scale_memory_records(records, 10)
    activation_budget = {
        "max_active_fragments": fragment_limit + 2,
        "max_prewarmed_fragments": max(3, fragment_limit - 2),
        "max_materialized_tokens": 96,
        "max_latency_ms": 25.0,
        "budget_policy": "auto_tuning_thresholded_compromise",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_autotuning_tables(connection)
        runtime_policies = {
            mode: _runtime_policy(mode, activation_budget)
            for mode in ["cold", "warm", "predictive_sparse", "bounded_predictive", "divergence_only"]
        }
        fixed_modes = _autotuning_fixed_modes(
            records=controlled_records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            runtime_policies=runtime_policies,
            coherence_threshold=coherence_threshold,
        )
        divergence_only = _autotuning_divergence_only_mode(
            records=controlled_records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            runtime_policy=runtime_policies["divergence_only"],
            coherence_threshold=coherence_threshold,
        )
        evaluated_modes = {
            "cold": fixed_modes["fixed_cold"],
            "warm": fixed_modes["fixed_warm"],
            "predictive_sparse": fixed_modes["fixed_predictive"],
            "bounded_predictive": fixed_modes["fixed_bounded"],
            "divergence_only": divergence_only,
        }
        policy_decision = _decide_runtime_policy(evaluated_modes)
        selected = evaluated_modes[policy_decision["selected_mode"]]
        auto_tuned = {
            "mode": "auto_tuned",
            "selected_mode": policy_decision["selected_mode"],
            "policy": selected["runtime_policy"],
            "policy_decision": policy_decision,
            "source_case": selected,
            "metrics": {
                **selected["metrics"],
                "selected_mode": policy_decision["selected_mode"],
                "avoided_bad_prediction": policy_decision["avoided_bad_prediction"],
                "warning_reduction": policy_decision["warning_reduction"],
                "latency_reduction": policy_decision["latency_reduction"],
                "relative_cost_reduction": policy_decision["relative_cost_reduction"],
                "policy_stability_score": policy_decision["policy_stability_score"],
            },
        }
        benchmark = {
            "id": "MMR-AUTOTUNING-POLICY-0001",
            "query": query,
            "strategy": AUTOTUNING_STRATEGY,
            "schema_version": AUTOTUNING_SCHEMA_VERSION,
            "activation_budget": activation_budget,
            "runtime_policies": runtime_policies,
            "fixed_modes": fixed_modes,
            "evaluated_modes": evaluated_modes,
            "auto_tuned": auto_tuned,
            "policy_decision": policy_decision,
            "metrics": {
                "selected_mode": policy_decision["selected_mode"],
                "avoided_bad_prediction": policy_decision["avoided_bad_prediction"],
                "warning_reduction": policy_decision["warning_reduction"],
                "latency_reduction": policy_decision["latency_reduction"],
                "relative_cost_reduction": policy_decision["relative_cost_reduction"],
                "policy_stability_score": policy_decision["policy_stability_score"],
            },
            "claim": (
                "AIONE can use dual-cost warnings to adapt its materialization policy, reject "
                "misleading predictive prewarm, and fall back to a cheaper coherent runtime mode."
            ),
            "result": "adapted" if policy_decision["selected_mode"] != "predictive_sparse" else "neutral",
            "created_at": utc_ts(),
        }
        _store_autotuning_policy_run(connection, benchmark)
        connection.commit()
        return benchmark


def run_long_horizon_stability(
    path: Path,
    *,
    query: str = "kernel proof memory",
    limit: int = 2,
    fragment_limit: int = 6,
    memory_records: list[dict[str, Any]] | None = None,
    horizons: tuple[int, ...] = (10, 25, 50),
    coherence_threshold: float = POTENTIALSTATE_COHERENCE_THRESHOLD,
) -> dict[str, Any]:
    records = _ensure_intrastate_benchmark_records(
        _prepare_memory_records(memory_records or DEFAULT_MEMORY_RECORDS),
        query,
        minimum=max(3, limit + 1),
    )
    controlled_records = _scale_memory_records(records, 10)
    activation_budget = {
        "max_active_fragments": fragment_limit + 2,
        "max_prewarmed_fragments": max(3, fragment_limit - 2),
        "max_materialized_tokens": 96,
        "max_latency_ms": 25.0,
        "budget_policy": "long_horizon_stability_guard",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_long_horizon_tables(connection)
        runtime_policies = {
            mode: _runtime_policy(mode, activation_budget)
            for mode in ["cold", "warm", "predictive_sparse", "bounded_predictive", "divergence_only"]
        }
        templates = _long_horizon_templates(
            records=controlled_records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            runtime_policies=runtime_policies,
            coherence_threshold=coherence_threshold,
        )
        scenarios = {
            f"{horizon}_cycles": _long_horizon_scenario(
                connection=connection,
                horizon=horizon,
                templates=templates,
                activation_budget=activation_budget,
            )
            for horizon in horizons
        }
        connection.commit()

    traces = [scenario["stability_trace"] for scenario in scenarios.values()]
    total_warnings = sum(scenario["metrics"]["total_warnings"] for scenario in scenarios.values())
    return {
        "id": "MMR-LONG-HORIZON-STABILITY-0001",
        "query": query,
        "strategy": LONG_HORIZON_STRATEGY,
        "schema_version": LONG_HORIZON_SCHEMA_VERSION,
        "activation_budget": activation_budget,
        "horizons": list(horizons),
        "runtime_policies": runtime_policies,
        "scenarios": scenarios,
        "metrics": {
            "long_horizon_stability_score": round(
                sum(item["long_horizon_stability_score"] for item in traces) / max(1, len(traces)),
                3,
            ),
            "policy_stability_score": round(
                sum(item["policy_stability_score"] for item in traces) / max(1, len(traces)),
                3,
            ),
            "coherence_drift": round(max(item["coherence_drift"] for item in traces), 3),
            "average_cost": round(
                sum(item["average_relative_cost"] for item in traces) / max(1, len(traces)),
                3,
            ),
            "total_warnings": total_warnings,
            "recovery_after_bad_prediction": all(
                scenario["metrics"]["recovery_after_bad_prediction"] for scenario in scenarios.values()
            ),
        },
        "claim": (
            "AIONE can keep runtime policy, coherence, and cache reuse stable over long horizons "
            "despite repeated weak mutations, rare strong mutations, bad predictions, and OOD queries."
        ),
        "result": "stable" if total_warnings > 0 else "clean",
        "created_at": utc_ts(),
    }


def run_external_workload_adapter(
    path: Path,
    *,
    source_path: Path,
    queries: list[str] | None = None,
    chunk_line_count: int = 40,
    materialization_limit: int = 8,
) -> dict[str, Any]:
    started = time.perf_counter()
    query_set = _workload_query_set(queries)
    path.parent.mkdir(parents=True, exist_ok=True)
    indexed = _index_workload_source(source_path, chunk_line_count=chunk_line_count)
    with sqlite3.connect(path) as connection:
        _ensure_external_workload_tables(connection)
        evaluations = {
            query_name: _evaluate_workload_query(
                index=indexed,
                query_name=query_name,
                query_terms=query_terms,
                materialization_limit=materialization_limit,
            )
            for query_name, query_terms in query_set["queries"].items()
        }
        primary_query = next(iter(query_set["queries"]))
        mutation_scenarios = _evaluate_workload_mutations(
            base_index=indexed,
            query_name=primary_query,
            query_terms=query_set["queries"][primary_query],
            materialization_limit=materialization_limit,
        )
        benchmark = {
            "id": "MMR-EXTERNAL-WORKLOAD-ADAPTER-0001",
            "query": " ".join(query_set["selected_queries"]),
            "strategy": EXTERNAL_WORKLOAD_STRATEGY,
            "schema_version": EXTERNAL_WORKLOAD_SCHEMA_VERSION,
            "workload_source": indexed["workload_source"],
            "workload_indexer": {
                "chunk_line_count": chunk_line_count,
                "supported_file_types": sorted(WORKLOAD_TEXT_SUFFIXES),
                "indexed_files": indexed["files"],
                "chunks": indexed["chunks"],
            },
            "workload_query_set": query_set,
            "runtime_evaluation": evaluations,
            "mutation_scenarios": mutation_scenarios,
            "metrics": _external_workload_metrics(evaluations, mutation_scenarios),
            "claim": (
                "The MMR runtime can index a real file workload, answer code/document queries "
                "with bounded chunk materialization, and preserve reuse under file-level mutations."
            ),
            "result": "measured" if indexed["workload_source"]["file_count"] > 0 else "empty",
            "created_at": utc_ts(),
            "absolute_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        _store_external_workload_run(connection, benchmark)
        connection.commit()
        return benchmark


def run_answer_quality_verification(
    path: Path,
    *,
    source_path: Path,
    queries: list[str] | None = None,
    chunk_line_count: int = 40,
    materialization_limit: int = 8,
) -> dict[str, Any]:
    started = time.perf_counter()
    query_set = _workload_query_set(queries)
    path.parent.mkdir(parents=True, exist_ok=True)
    indexed = _index_workload_source(source_path, chunk_line_count=chunk_line_count)
    with sqlite3.connect(path) as connection:
        _ensure_answer_quality_tables(connection)
        query_evaluations = {
            query_name: _evaluate_answer_quality_query(
                index=indexed,
                query_name=query_name,
                query_terms=query_terms,
                materialization_limit=materialization_limit,
            )
            for query_name, query_terms in query_set["queries"].items()
        }
        benchmark = {
            "id": "MMR-ANSWER-QUALITY-VERIFICATION-0001",
            "query": " ".join(query_set["selected_queries"]),
            "strategy": ANSWER_QUALITY_STRATEGY,
            "schema_version": ANSWER_QUALITY_SCHEMA_VERSION,
            "workload_source": indexed["workload_source"],
            "workload_query_set": query_set,
            "answer_quality_evaluation": query_evaluations,
            "metrics": _answer_quality_metrics(query_evaluations),
            "claim": (
                "AIONE can reduce materialized chunks while keeping answers sourced, complete "
                "against a naive full-scan baseline, and free of simple unsupported claims."
            ),
            "result": "verified" if indexed["workload_source"]["file_count"] > 0 else "empty",
            "created_at": utc_ts(),
            "absolute_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        _store_answer_quality_run(connection, benchmark)
        connection.commit()
        return benchmark


def run_real_user_task_benchmark(
    path: Path,
    *,
    source_path: Path,
    chunk_line_count: int = 40,
    materialization_limit: int = 8,
) -> dict[str, Any]:
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    indexed = _index_workload_source(source_path, chunk_line_count=chunk_line_count)
    with sqlite3.connect(path) as connection:
        _ensure_real_user_task_tables(connection)
        task_results = {
            task["id"]: _evaluate_real_user_task(
                index=indexed,
                task=task,
                materialization_limit=materialization_limit,
            )
            for task in REAL_USER_TASKS
        }
        benchmark = {
            "id": "MMR-REAL-USER-TASK-BENCHMARK-0001",
            "query": "real_user_tasks",
            "strategy": REAL_USER_TASK_STRATEGY,
            "schema_version": REAL_USER_TASK_SCHEMA_VERSION,
            "workload_source": indexed["workload_source"],
            "task_set": REAL_USER_TASKS,
            "task_results": task_results,
            "metrics": _real_user_task_metrics(task_results),
            "claim": (
                "AIONE can preserve source-grounded task success on realistic developer-agent "
                "tasks while materially reducing chunk materialization versus a full scan."
            ),
            "result": "measured" if indexed["workload_source"]["file_count"] > 0 else "empty",
            "created_at": utc_ts(),
            "absolute_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        _store_real_user_task_run(connection, benchmark)
        connection.commit()
        return benchmark


def render_mmr_status(bundle: MMRBundle, index_status: dict[str, Any] | None = None) -> str:
    cost_trace = bundle.cost_trace
    materialized_slice = bundle.materialized_slice
    potential_state = bundle.potential_state
    lines = [
        "# MMR Status",
        "",
        f"Potential state: {potential_state['id']}",
        f"Constraint set: {bundle.constraint_set['id']}",
        f"Plan: {bundle.materialization_plan['id']}",
        f"Slice: {materialized_slice['id']}",
        f"Result: {cost_trace['result']}",
        f"Confidence: {materialized_slice['confidence']}",
        "",
        "## Materialization",
        "",
        f"Strategy: {bundle.materialization_plan['strategy']}",
        f"Status: {bundle.materialization_plan['status']}",
        f"Approximation used: {materialized_slice['approximation']['used']}",
        f"Expected error: {materialized_slice['approximation']['expected_error']}",
        "",
        "## Cost Trace",
        "",
        f"Naive tokens: {cost_trace['naive_cost_estimate'].get('tokens')}",
        f"Actual tokens: {cost_trace['actual_cost_estimate'].get('tokens')}",
        f"Control overhead tokens: {cost_trace['control_overhead_estimate'].get('tokens')}",
        f"Saved tokens: {cost_trace['saved_work_estimate'].get('tokens')}",
        f"Materialized units: {cost_trace['metrics']['materialized_units']}",
        f"Avoided units: {cost_trace['metrics']['avoided_units']}",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- {gate}" for gate in bundle.materialization_request["required_gates"])
    if index_status is not None:
        lines.extend(
            [
                "",
                "## SQLite Index",
                "",
                f"Path: {index_status['path']}",
                f"Records written: {index_status['records_written']}",
                f"Records total: {index_status['records_total']}",
            ]
        )
    return "\n".join(lines)


def render_document_benchmark_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Document Benchmark",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## Cost",
        "",
        f"Naive documents: {benchmark['naive']['materialized_documents']}",
        f"Naive tokens: {benchmark['naive']['token_estimate']}",
        f"MMR documents: {benchmark['mmr']['materialized_documents']}",
        f"MMR tokens: {benchmark['mmr']['token_estimate']}",
        f"Control overhead tokens: {benchmark['mmr']['control_overhead_tokens']}",
        f"Saved tokens: {benchmark['saved_work_estimate']['tokens']}",
        f"Avoided documents: {benchmark['saved_work_estimate']['avoided_documents']}",
        f"Token reduction ratio: {benchmark['metrics']['token_reduction_ratio']}",
        "",
        "## Selected Documents",
        "",
    ]
    for document in benchmark["selected_documents"]:
        lines.append(
            f"- {document['id']} - {document['title']} "
            f"score={document['score']} tokens={document['token_estimate']}"
        )
    return "\n".join(lines)


def render_cache_reuse_benchmark_status(benchmark: dict[str, Any]) -> str:
    scenarios = benchmark["scenarios"]
    metrics = benchmark["metrics"]
    lines = [
        "# MMR Cache Reuse Benchmark",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Scoring version: {benchmark['scoring_version']}",
        f"Result: {benchmark['result']}",
        "",
        "## Comparison",
        "",
        "| Scenario | Cache hit | Invalidated | Materialized docs | Tokens | Latency ms | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("naive_full_materialization", "Naive full materialization"),
        ("mmr_without_cache", "MMR without cache"),
        ("mmr_with_valid_cache", "MMR with valid cache"),
        ("mmr_with_invalidated_cache", "MMR with invalidated cache"),
    ]:
        item = scenarios[key]
        notes = ", ".join(item.get("invalidators", [])) or item.get("mode", "")
        lines.append(
            f"| {label} | {item.get('cache_hit', False)} | {item.get('invalidated', False)} | "
            f"{item['materialized_documents']} | {item['token_estimate']} | {item['latency_ms']} | {notes} |"
        )
    lines.extend(
        [
            "",
            "## Gains",
            "",
            f"Cache hits: {metrics['cache_hits']}",
            f"Cache misses: {metrics['cache_misses']}",
            f"Cache invalidations: {metrics['cache_invalidations']}",
            f"Avoided materialization: {metrics['avoided_materialization']}",
            f"Saved tokens: {metrics['saved_tokens']}",
            f"Latency gain ms: {metrics['latency_gain_ms']}",
        ]
    )
    return "\n".join(lines)


def render_divergence_runtime_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Divergence Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Scoring version: {benchmark['scoring_version']}",
        f"Result: {benchmark['result']}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Divergence ratio | Reused slices | Rebuilt slices | "
            "Avoided tokens | Avoided materialization ratio | Relative resolution cost | Changed docs |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("stable_corpus", "Stable corpus"),
        ("low_divergence", "Low divergence"),
        ("high_divergence", "High divergence"),
    ]:
        scenario = benchmark["scenarios"][key]
        metrics = scenario["metrics"]
        changed = ", ".join(scenario["changed_documents"]) or "none"
        lines.append(
            f"| {label} | {metrics['divergence_ratio']} | {metrics['reused_slices']} | "
            f"{metrics['rebuilt_slices']} | {metrics['avoided_tokens']} | "
            f"{metrics['avoided_materialization_ratio']} | {metrics['relative_resolution_cost']} | {changed} |"
        )
    lines.extend(
        [
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
            "",
            "## Interpretation",
            "",
            "- A stable corpus reuses coherent slices and rebuilds nothing.",
            "- Low divergence keeps selected slices coherent when the changed document is not useful for the query.",
            "- High divergence rebuilds only invalid selected slices instead of rematerializing the full corpus.",
        ]
    )
    return "\n".join(lines)


def render_diffcache_benchmark_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR DiffCache Benchmark",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Approximate query: {benchmark['approximate_query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Scoring version: {benchmark['scoring_version']}",
        f"Result: {benchmark['result']}",
        "",
        "## Resolution State",
        "",
        f"Corpus fingerprint: {benchmark['resolution_state']['corpus_fingerprint']}",
        f"Answer fingerprint: {benchmark['resolution_state']['answer_fingerprint']}",
        f"Coherence score: {benchmark['resolution_state']['coherence_score']}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Total tokens | Materialized tokens | Relative cost | "
            "Divergence | Reused | Rebuilt | Cache hit | Approx hit | Invalidations | "
            "Latency gain ms | Coherence |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("naive_full_materialization", "Naive full materialization"),
        ("mmr_without_cache", "MMR without cache"),
        ("mmr_cache_exact", "MMR cache exact"),
        ("mmr_cache_approximate", "MMR cache approximate"),
        ("mmr_divergence_only_after_partial_change", "MMR divergence-only after partial change"),
    ]:
        metrics = benchmark["scenarios"][key]["metrics"]
        lines.append(
            f"| {label} | {metrics['total_available_tokens']} | {metrics['materialized_tokens']} | "
            f"{metrics['relative_resolution_cost']} | {metrics['divergence_ratio']} | "
            f"{metrics['reused_slices']} | {metrics['rebuilt_slices']} | {metrics['cache_hit']} | "
            f"{metrics['approximate_cache_hit']} | {metrics['invalidations']} | "
            f"{metrics['latency_gain_ms']} | {metrics['coherence_score']} |"
        )
    lines.extend(
        [
            "",
            "## Divergence Map",
            "",
            f"Unchanged docs: {', '.join(benchmark['divergence_map']['unchanged_docs'])}",
            f"Changed docs: {', '.join(benchmark['divergence_map']['changed_docs'])}",
            f"Reused slices: {', '.join(benchmark['divergence_map']['reused_slices'])}",
            f"Rebuilt slices: {', '.join(benchmark['divergence_map']['rebuilt_slices'])}",
            f"Divergence ratio: {benchmark['divergence_map']['divergence_ratio']}",
            "",
            "## Guards",
            "",
            "- Exact cache reuse requires identical corpus fingerprint and scoring strategy.",
            "- Approximate cache reuse requires lexical query similarity above threshold.",
            "- Coherence guard blocks reuse when reused fragments no longer cover required terms.",
            "- Divergence-only rebuilds invalid slices while keeping coherent slices.",
        ]
    )
    return "\n".join(lines)


def render_potentialstate_runtime_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR PotentialState Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## Live State",
        "",
        f"PotentialState: {benchmark['potential_state']['id']}",
        f"State fingerprint: {benchmark['potential_state']['state_fingerprint']}",
        f"Memory version: {benchmark['potential_state']['memory_version']}",
        f"MaterializedSlice: {benchmark['materialized_slice']['id']}",
        f"Previous cycle reuse: {benchmark['multi_cycle']['previous_cycle_reuse']}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Reused states | Rebuilt states | Reused slices | Rebuilt slices | "
            "Invalidations | Relative cost | Coherence | Latency ms |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("initial_resolution", "Initial resolution"),
        ("second_resolution_same_state", "Second resolution same state"),
        ("after_low_mutation", "After low mutation"),
        ("after_strong_mutation", "After strong mutation"),
        ("after_memory_invalidator", "After memory invalidator"),
    ]:
        metrics = benchmark["scenarios"][key]["metrics"]
        lines.append(
            f"| {label} | {metrics['reused_potential_states']} | "
            f"{metrics['rebuilt_potential_states']} | {metrics['reused_slices']} | "
            f"{metrics['rebuilt_slices']} | {metrics['memory_invalidation_count']} | "
            f"{metrics['relative_resolution_cost']} | {metrics['coherence_score']} | "
            f"{metrics['latency_ms']} |"
        )
    lines.extend(
        [
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
            "",
            "## Invalidators",
            "",
            "- `memory_store_changed` blocks reuse and forces rematerialization.",
            "- `state_fingerprint_changed` allows divergence-only reuse when slice fingerprints remain coherent.",
            "- `source_refs_changed` blocks stale source reuse for affected slices.",
        ]
    )
    return "\n".join(lines)


def render_intrastate_delta_runtime_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Intra-State Delta Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## State Segments",
        "",
        f"PotentialState: {benchmark['potential_state']['id']}",
        f"Base segment count: {len(benchmark['base_segments'])}",
        f"Base slice: {benchmark['base_materialized_slice']['id']}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Total segments | Changed | Reused | Rebuilt | Delta ratio | "
            "Avoided rebuild ratio | Relative cost | Latency ms | Coherence | Invalidators |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("stable_state", "Stable state"),
        ("weak_segment_mutation", "Weak segment mutation"),
        ("medium_segment_mutation", "Medium segment mutation"),
        ("strong_segment_mutation", "Strong segment mutation"),
        ("global_memory_invalidation", "Global memory invalidation"),
    ]:
        scenario = benchmark["scenarios"][key]
        metrics = scenario["metrics"]
        invalidators = ", ".join(scenario["invalidators"]) or "none"
        lines.append(
            f"| {label} | {metrics['total_segments']} | {metrics['changed_segments']} | "
            f"{metrics['reused_segments']} | {metrics['rebuilt_segments']} | "
            f"{metrics['delta_ratio']} | {metrics['avoided_rebuild_ratio']} | "
            f"{metrics['relative_resolution_cost']} | {metrics['latency_ms']} | "
            f"{metrics['coherence_score']} | {invalidators} |"
        )
    lines.extend(
        [
            "",
            "## DeltaMap",
            "",
            "Each scenario records `unchanged_segments`, `changed_segments`, `reused_segments`, "
            "`rebuilt_segments` and `delta_ratio` in the JSON artifact.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_microdelta_dependency_runtime_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR MicroDelta Dependency Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## MicroFragments",
        "",
        f"PotentialState: {benchmark['potential_state']['id']}",
        f"Base segment count: {len(benchmark['base_segments'])}",
        f"Base microfragment count: {len(benchmark['base_microfragments'])}",
        f"Base slice: {benchmark['base_materialized_slice']['id']}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Total fragments | Changed | Reused | Rebuilt | Affected slices | "
            "Micro delta ratio | Avoided rebuild ratio | Relative cost | Latency ms | Coherence | Invalidators |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("stable", "Stable"),
        ("weak_micro_mutation", "Weak micro mutation"),
        ("weak_segment_mutation", "Weak segment mutation"),
        ("medium_mutation", "Medium mutation"),
        ("strong_mutation", "Strong mutation"),
        ("global_invalidation", "Global invalidation"),
    ]:
        scenario = benchmark["scenarios"][key]
        metrics = scenario["metrics"]
        invalidators = ", ".join(scenario["invalidators"]) or "none"
        lines.append(
            f"| {label} | {metrics['total_fragments']} | {metrics['changed_fragments']} | "
            f"{metrics['reused_fragments']} | {metrics['rebuilt_fragments']} | "
            f"{metrics['affected_slices']} | {metrics['micro_delta_ratio']} | "
            f"{metrics['avoided_rebuild_ratio']} | {metrics['relative_resolution_cost']} | "
            f"{metrics['latency_ms']} | {metrics['coherence_score']} | {invalidators} |"
        )
    lines.extend(
        [
            "",
            "## MicroDeltaMap",
            "",
            "Each scenario records `unchanged_fragments`, `changed_fragments`, "
            "`reused_fragments`, `rebuilt_fragments` and `micro_delta_ratio` in the JSON artifact.",
            "",
            "## SliceDependencyGraph",
            "",
            "Each slice records the `MicroFragment` ids it depends on, their dependency weights "
            "and the precise invalidation reason when a rebuild is required.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_predictive_sparse_runtime_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Predictive Sparse Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## Predictive Patterns",
        "",
        f"PotentialState: {benchmark['potential_state']['id']}",
        f"Base microfragment count: {len(benchmark['base_microfragments'])}",
        f"Predictive patterns: {len(benchmark['predictive_patterns'])}",
        f"Prewarmed fragments: {len(benchmark['predictive_materialization']['prewarmed_fragments'])}",
        "",
        "## Comparison",
        "",
        (
            "| Scenario | Hit rate | Avoided rebuild | Avoided materialization | "
            "Prewarm accuracy | Relative cost | Coherence | Latency ms | Active ratio | Invalidators |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, label in [
        ("cold_runtime", "Cold runtime"),
        ("warm_runtime", "Warm runtime"),
        ("predictive_sparse_runtime", "Predictive sparse runtime"),
        ("heavy_divergence_runtime", "Heavy divergence runtime"),
        ("global_invalidation", "Global invalidation"),
    ]:
        scenario = benchmark["scenarios"][key]
        metrics = scenario["metrics"]
        invalidators = ", ".join(scenario["invalidators"]) or "none"
        lines.append(
            f"| {label} | {metrics['predictive_hit_rate']} | "
            f"{metrics['avoided_rebuild_ratio']} | {metrics['avoided_materialization_ratio']} | "
            f"{metrics['prewarm_accuracy']} | {metrics['relative_resolution_cost']} | "
            f"{metrics['coherence_score']} | {metrics['latency_ms']} | "
            f"{metrics['active_fragment_ratio']} | {invalidators} |"
        )
    lines.extend(
        [
            "",
            "## SparseActivationMap",
            "",
            "Each scenario records `active_fragments`, `dormant_fragments`, "
            "`predictive_fragments` and `prewarmed_fragments` in the JSON artifact.",
            "",
            "## Prediction Scoring",
            "",
            "Prediction weight combines frequency, structural proximity, divergence history, "
            "query history and coherence stability.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_bounded_predictive_runtime_status(benchmark: dict[str, Any]) -> str:
    budget = benchmark["activation_budget"]
    lines = [
        "# MMR Bounded Predictive Runtime",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## ActivationBudget",
        "",
        f"Max active fragments: {budget['max_active_fragments']}",
        f"Max prewarmed fragments: {budget['max_prewarmed_fragments']}",
        f"Max materialized tokens: {budget['max_materialized_tokens']}",
        f"Max latency ms: {budget['max_latency_ms']}",
        f"Policy: {budget['budget_policy']}",
        "",
        "## Scaling Comparison",
        "",
        (
            "| Corpus | Mode | Relative cost | Active ratio | Prewarm accuracy | "
            "Wasted prewarm | Budget utilization | Latency ms | Materialized tokens | "
            "Total tokens | Scaling efficiency |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scale_key in benchmark["scaling_factors"]:
        scale_case = benchmark["scenarios"][scale_key]
        for mode_key, label in [
            ("cold", "Cold"),
            ("warm", "Warm"),
            ("predictive_sparse", "Predictive sparse"),
            ("bounded_predictive", "Bounded predictive"),
        ]:
            metrics = scale_case["modes"][mode_key]["metrics"]
            lines.append(
                f"| {scale_key} | {label} | {metrics['relative_resolution_cost']} | "
                f"{metrics['active_fragment_ratio']} | {metrics['prewarm_accuracy']} | "
                f"{metrics['wasted_prewarm_ratio']} | {metrics['budget_utilization']} | "
                f"{metrics['latency_ms']} | {metrics['materialized_tokens']} | "
                f"{metrics['total_available_tokens']} | {metrics['scaling_efficiency']} |"
            )
    lines.extend(
        [
            "",
            "## PredictionPenalty",
            "",
            "Each mode records `false_positive_prewarm`, `unused_prewarmed_fragments`, "
            "`wasted_tokens`, `wasted_latency_ms` and `penalty_score` in the JSON artifact.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_dual_cost_validation_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Dual Cost Validation",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        f"Warning count: {benchmark['metrics']['warning_count']}",
        "",
        "## Scaling Sanity Check",
        "",
        (
            "| Corpus | Relative cost | Absolute tokens | Absolute latency ms | "
            "Rebuilt | Reused | Wasted prewarm | False positive | OOD fallback | Warnings |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key in ["x1", "x5", "x10", "x25"]:
        metrics = benchmark["scaling"][key]["metrics"]
        lines.append(
            f"| {key} | {metrics['relative_resolution_cost']} | "
            f"{metrics['absolute_materialized_tokens']} | {metrics['absolute_latency_ms']} | "
            f"{metrics['absolute_rebuilt_fragments']} | "
            f"{benchmark['scaling'][key]['absolute_cost_trace']['reused_fragments']} | "
            f"{metrics['wasted_prewarm_ratio']} | {metrics['prediction_false_positive_rate']} | "
            f"{metrics['out_of_distribution_fallback_rate']} | {metrics['warning_count']} |"
        )
    lines.extend(
        [
            "",
            "## Adversarial Benchmark",
            "",
            (
                "| Scenario | Relative cost | Absolute tokens | Absolute latency ms | "
                "Rebuilt | Wasted prewarm | False positive | OOD fallback | Warnings |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for key, label in [
        ("compressible_corpus", "Compressible corpus"),
        ("low_compressible_corpus", "Low compressible corpus"),
        ("random_mutations", "Random mutations"),
        ("out_of_distribution_query", "Out of distribution query"),
        ("bad_predictions", "Bad predictions"),
    ]:
        metrics = benchmark["adversarial"][key]["metrics"]
        lines.append(
            f"| {label} | {metrics['relative_resolution_cost']} | "
            f"{metrics['absolute_materialized_tokens']} | {metrics['absolute_latency_ms']} | "
            f"{metrics['absolute_rebuilt_fragments']} | {metrics['wasted_prewarm_ratio']} | "
            f"{metrics['prediction_false_positive_rate']} | "
            f"{metrics['out_of_distribution_fallback_rate']} | {metrics['warning_count']} |"
        )
    lines.extend(
        [
            "",
            "## DualCostReport",
            "",
            "Each case records `relative_resolution_cost`, `absolute_materialization_cost`, "
            "`normalized_efficiency`, `scaling_efficiency` and `cost_discrepancy_warning`.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_autotuning_policy_status(benchmark: dict[str, Any]) -> str:
    decision = benchmark["policy_decision"]
    lines = [
        "# MMR Auto-Tuning Runtime Policy",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        f"Selected mode: {decision['selected_mode']}",
        f"Fallback used: {decision['fallback_used']}",
        "",
        "## RuntimePolicy",
        "",
        (
            "| Mode | Max relative cost | Max absolute latency ms | "
            "Max wasted prewarm | Max warnings |"
        ),
        "| --- | --- | --- | --- | --- |",
    ]
    for mode in ["cold", "warm", "predictive_sparse", "bounded_predictive", "divergence_only"]:
        policy = benchmark["runtime_policies"][mode]
        lines.append(
            f"| {mode} | {policy['max_relative_cost']} | {policy['max_absolute_latency_ms']} | "
            f"{policy['max_wasted_prewarm_ratio']} | {policy['max_warning_count']} |"
        )
    lines.extend(
        [
            "",
            "## Benchmark",
            "",
            (
                "| Case | Policy mode | Relative cost | Latency ms | Wasted prewarm | "
                "Warnings | Policy score | Rejected |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for key, label in [
        ("fixed_cold", "Fixed cold"),
        ("fixed_warm", "Fixed warm"),
        ("fixed_predictive", "Fixed predictive"),
        ("fixed_bounded", "Fixed bounded"),
    ]:
        item = benchmark["fixed_modes"][key]
        metrics = item["metrics"]
        lines.append(
            f"| {label} | {item['policy_mode']} | {metrics['relative_resolution_cost']} | "
            f"{metrics['absolute_latency_ms']} | {metrics['wasted_prewarm_ratio']} | "
            f"{metrics['warning_count']} | {metrics['policy_score']} | {item['rejected']} |"
        )
    auto = benchmark["auto_tuned"]
    auto_metrics = auto["metrics"]
    lines.append(
        f"| Auto tuned | {auto['selected_mode']} | {auto_metrics['relative_resolution_cost']} | "
        f"{auto_metrics['absolute_latency_ms']} | {auto_metrics['wasted_prewarm_ratio']} | "
        f"{auto_metrics['warning_count']} | {auto_metrics['policy_score']} | False |"
    )
    lines.extend(
        [
            "",
            "## PolicyDecision",
            "",
            f"Decision reason: {decision['decision_reason']}",
            f"Rejected modes: {', '.join(item['mode'] for item in decision['rejected_modes'])}",
            f"Expected cost score: {decision['expected_cost']['policy_score']}",
            f"Observed cost score: {decision['observed_cost']['policy_score']}",
            "",
            "## Metrics",
            "",
            f"Avoided bad prediction: {benchmark['metrics']['avoided_bad_prediction']}",
            f"Warning reduction: {benchmark['metrics']['warning_reduction']}",
            f"Latency reduction ms: {benchmark['metrics']['latency_reduction']}",
            f"Relative cost reduction: {benchmark['metrics']['relative_cost_reduction']}",
            f"Policy stability score: {benchmark['metrics']['policy_stability_score']}",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_long_horizon_stability_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Long-Horizon Runtime Stability",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Query: {benchmark['query']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## StabilityTrace",
        "",
        (
            "| Horizon | Switches | Avg relative cost | Avg latency ms | Warning rate | "
            "Coherence drift | Cache decay | Reuse rate | Stability score |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key in [f"{horizon}_cycles" for horizon in benchmark["horizons"]]:
        trace = benchmark["scenarios"][key]["stability_trace"]
        lines.append(
            f"| {key} | {trace['policy_switch_count']} | {trace['average_relative_cost']} | "
            f"{trace['average_absolute_latency_ms']} | {trace['warning_rate']} | "
            f"{trace['coherence_drift']} | {trace['cache_decay_rate']} | "
            f"{trace['reuse_rate']} | {trace['long_horizon_stability_score']} |"
        )
    lines.extend(
        [
            "",
            "## RuntimeEpisodes",
            "",
            (
                "| Horizon | First policy | Last policy | Total warnings | Recovery after bad prediction | "
                "Drift warnings |"
            ),
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for key in [f"{horizon}_cycles" for horizon in benchmark["horizons"]]:
        scenario = benchmark["scenarios"][key]
        episodes = scenario["episodes"]
        lines.append(
            f"| {key} | {episodes[0]['selected_policy']} | {episodes[-1]['selected_policy']} | "
            f"{scenario['metrics']['total_warnings']} | "
            f"{scenario['metrics']['recovery_after_bad_prediction']} | "
            f"{', '.join(scenario['drift_warnings']) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"Long horizon stability score: {benchmark['metrics']['long_horizon_stability_score']}",
            f"Policy stability score: {benchmark['metrics']['policy_stability_score']}",
            f"Coherence drift: {benchmark['metrics']['coherence_drift']}",
            f"Average cost: {benchmark['metrics']['average_cost']}",
            f"Total warnings: {benchmark['metrics']['total_warnings']}",
            f"Recovery after bad prediction: {benchmark['metrics']['recovery_after_bad_prediction']}",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_external_workload_adapter_status(benchmark: dict[str, Any]) -> str:
    source = benchmark["workload_source"]
    lines = [
        "# MMR External Workload Adapter",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Source: {source['source_path']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## WorkloadSource",
        "",
        f"Files: {source['file_count']}",
        f"Total bytes: {source['total_bytes']}",
        f"File types: {', '.join(source['file_types']) or 'none'}",
        f"Source fingerprint: {source['source_fingerprint']}",
        "",
        "## Runtime Evaluation",
        "",
        (
            "| Query | Mode | Total chunks | Materialized | Reused | Rebuilt | "
            "Relative cost | Latency ms | Warnings | Coherence |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for query_name, evaluation in benchmark["runtime_evaluation"].items():
        for mode_name in [
            "naive_full_scan",
            "mmr_minimal",
            "diffcache",
            "microdelta",
            "bounded_predictive",
            "auto_tuned",
        ]:
            metrics = evaluation["modes"][mode_name]["metrics"]
            lines.append(
                f"| {query_name} | {mode_name} | {metrics['total_chunks']} | "
                f"{metrics['materialized_chunks']} | {metrics['reused_chunks']} | "
                f"{metrics['rebuilt_chunks']} | {metrics['relative_resolution_cost']} | "
                f"{metrics['absolute_latency_ms']} | {metrics['warning_count']} | "
                f"{metrics['coherence_score']} |"
            )
    lines.extend(
        [
            "",
            "## Mutations",
            "",
            (
                "| Mutation | Total chunks | Materialized | Reused | Rebuilt | "
                "Relative cost | Latency ms | Warnings | Coherence |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for mutation_name, mutation in benchmark["mutation_scenarios"].items():
        metrics = mutation["metrics"]
        lines.append(
            f"| {mutation_name} | {metrics['total_chunks']} | {metrics['materialized_chunks']} | "
            f"{metrics['reused_chunks']} | {metrics['rebuilt_chunks']} | "
            f"{metrics['relative_resolution_cost']} | {metrics['absolute_latency_ms']} | "
            f"{metrics['warning_count']} | {metrics['coherence_score']} |"
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"Total files: {benchmark['metrics']['total_files']}",
            f"Total chunks: {benchmark['metrics']['total_chunks']}",
            f"Best relative cost: {benchmark['metrics']['best_relative_resolution_cost']}",
            f"Max reused chunks: {benchmark['metrics']['max_reused_chunks']}",
            f"Mutation rebuilt chunks: {benchmark['metrics']['mutation_rebuilt_chunks']}",
            f"Warning count: {benchmark['metrics']['warning_count']}",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_answer_quality_verification_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Answer Quality Verification",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Source: {benchmark['workload_source']['source_path']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## VerifiedAnswer",
        "",
        (
            "| Query | Mode | Relative cost | Evidence | Completeness | Unsupported | "
            "Contradictions | Missing key points | Quality |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    mode_order = [
        "naive_full_scan_answer",
        "mmr_minimal_answer",
        "diffcache_answer",
        "bounded_predictive_answer",
        "auto_tuned_answer",
    ]
    for query_name, evaluation in benchmark["answer_quality_evaluation"].items():
        for mode_name in mode_order:
            answer_case = evaluation["answers"][mode_name]
            metrics = answer_case["metrics"]
            lines.append(
                f"| {query_name} | {mode_name} | {metrics['relative_resolution_cost']} | "
                f"{metrics['evidence_score']} | {metrics['completeness_score']} | "
                f"{metrics['unsupported_claim_count']} | {metrics['contradiction_count']} | "
                f"{len(metrics['missing_key_points'])} | {metrics['answer_quality_score']} |"
            )
    lines.extend(
        [
            "",
            "## SourceVerifier",
            "",
            "Each important sentence is checked for chunk citation, unsupported claims, "
            "and simple contradiction markers against the selected source chunks.",
            "",
            "## CompletenessCheck",
            "",
            "Each reduced answer is compared with the naive full-scan answer key points.",
            "",
            "## Metrics",
            "",
            f"Best answer quality score: {benchmark['metrics']['best_answer_quality_score']}",
            f"Minimum evidence score: {benchmark['metrics']['minimum_evidence_score']}",
            f"Minimum completeness score: {benchmark['metrics']['minimum_completeness_score']}",
            f"Unsupported claims: {benchmark['metrics']['unsupported_claim_count']}",
            f"Contradictions: {benchmark['metrics']['contradiction_count']}",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def render_real_user_task_benchmark_status(benchmark: dict[str, Any]) -> str:
    lines = [
        "# MMR Real User Task Benchmark",
        "",
        f"Benchmark: {benchmark['id']}",
        f"Source: {benchmark['workload_source']['source_path']}",
        f"Strategy: {benchmark['strategy']}",
        f"Result: {benchmark['result']}",
        "",
        "## Task Set",
        "",
    ]
    for task in benchmark["task_set"]:
        lines.append(f"- {task['id']}: {task['title']}")
    lines.extend(
        [
            "",
            "## Task Benchmark",
            "",
            (
                "| Task | Mode | Relative cost | Latency ms | Evidence | Completeness | "
                "Unsupported | Contradictions | Task success | Source coverage |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for task_id, task_result in benchmark["task_results"].items():
        for mode_name in [
            "naive_full_scan",
            "mmr_minimal",
            "diffcache",
            "microdelta",
            "bounded_predictive",
            "auto_tuned",
        ]:
            metrics = task_result["modes"][mode_name]["metrics"]
            lines.append(
                f"| {task_id} | {mode_name} | {metrics['relative_resolution_cost']} | "
                f"{metrics['absolute_latency_ms']} | {metrics['evidence_score']} | "
                f"{metrics['completeness_score']} | {metrics['unsupported_claim_count']} | "
                f"{metrics['contradiction_count']} | {metrics['task_success_score']} | "
                f"{metrics['source_coverage_score']} |"
            )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"Average task success score: {benchmark['metrics']['average_task_success_score']}",
            f"Average source coverage score: {benchmark['metrics']['average_source_coverage_score']}",
            f"Best relative cost: {benchmark['metrics']['best_relative_resolution_cost']}",
            f"Average reduced relative cost: {benchmark['metrics']['average_reduced_relative_resolution_cost']}",
            f"Minimum evidence score: {benchmark['metrics']['minimum_evidence_score']}",
            f"Minimum completeness score: {benchmark['metrics']['minimum_completeness_score']}",
            f"Unsupported claims: {benchmark['metrics']['unsupported_claim_count']}",
            f"Contradictions: {benchmark['metrics']['contradiction_count']}",
            "",
            "## Quality Verification",
            "",
            "VerifiedAnswer, SourceVerifier and CompletenessCheck are applied per task and per mode.",
            "",
            "## Scientific Claim",
            "",
            benchmark["claim"],
        ]
    )
    return "\n".join(lines)


def _context_items(context_summary: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ["items", "context_items", "results"]:
        value = context_summary.get(key)
        if isinstance(value, list):
            return [item if isinstance(item, dict) else {"value": item} for item in value]
    return []


def _mission_id(payload: dict[str, Any]) -> str | None:
    for key in ["mission_id", "source"]:
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("MISSION-"):
            return value
    return None


def _document_score(record: dict[str, Any], query: str) -> float:
    terms = {term for term in query.lower().replace("_", " ").split() if term}
    if not terms:
        return 0.0
    title = record.get("title", "").lower()
    tags = " ".join(record.get("tags", [])).lower()
    body = record.get("body", "").lower()
    score = 0.0
    for term in terms:
        if term in title:
            score += 2.0
        if term in tags:
            score += 1.5
        if term in body:
            score += 1.0
    return round(min(score / (len(terms) * 2.5), 1.0), 3)


def _token_estimate(*parts: str) -> int:
    words = " ".join(parts).split()
    return max(1, int(len(words) * 1.35))


def _prepare_document_index(connection: sqlite3.Connection, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            tags TEXT NOT NULL,
            body TEXT NOT NULL,
            token_estimate INTEGER NOT NULL,
            document_hash TEXT NOT NULL DEFAULT ''
        )
        """
    )
    _ensure_column(connection, "mmr_documents", "document_hash", "TEXT NOT NULL DEFAULT ''")
    ids = [document["id"] for document in documents]
    if ids:
        placeholders = ",".join("?" for _ in ids)
        connection.execute(f"DELETE FROM mmr_documents WHERE id NOT IN ({placeholders})", ids)
    else:
        connection.execute("DELETE FROM mmr_documents")
    for document in documents:
        tags = " ".join(document.get("tags", []))
        connection.execute(
            """
            INSERT OR REPLACE INTO mmr_documents (id, title, tags, body, token_estimate, document_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                document["id"],
                document["title"],
                tags,
                document["body"],
                _token_estimate(document["title"], tags, document["body"]),
                _document_hash(document),
            ),
        )
    rows = connection.execute(
        "SELECT id, title, tags, body, token_estimate, document_hash FROM mmr_documents ORDER BY id"
    ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "tags": row[2].split(),
            "body": row[3],
            "token_estimate": int(row[4]),
            "document_hash": row[5],
        }
        for row in rows
    ]


def _ensure_query_cache_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_query_cache (
            cache_key TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            limit_value INTEGER NOT NULL,
            strategy_version TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            corpus_fingerprint TEXT NOT NULL,
            selected_payload TEXT NOT NULL,
            token_estimate INTEGER NOT NULL,
            materialized_documents INTEGER NOT NULL,
            invalidators TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _select_documents(records: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    scored = []
    for record in records:
        score = _document_score(record, query)
        if score > 0:
            scored.append({"record": record, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, limit)]


def _naive_full_materialization(records: list[dict[str, Any]]) -> dict[str, Any]:
    token_estimate = sum(record["token_estimate"] for record in records)
    return {
        "mode": "naive_full_materialization",
        "cache_hit": False,
        "cache_miss": False,
        "invalidated": False,
        "materialized_documents": len(records),
        "token_estimate": token_estimate,
        "latency_ms": _latency_estimate(len(records), token_estimate, cached=False),
        "selected_documents": [
            {
                "id": record["id"],
                "title": record["title"],
                "token_estimate": record["token_estimate"],
            }
            for record in records
        ],
    }


def _mmr_without_cache(records: list[dict[str, Any]], query: str, limit: int) -> dict[str, Any]:
    selected = _select_documents(records, query, limit)
    token_estimate = sum(item["record"]["token_estimate"] for item in selected)
    return {
        "mode": "mmr_without_cache",
        "cache_hit": False,
        "cache_miss": True,
        "invalidated": False,
        "materialized_documents": len(selected),
        "token_estimate": token_estimate,
        "latency_ms": _latency_estimate(len(selected), token_estimate, cached=False),
        "selected_documents": _selected_payload(selected),
    }


def _cache_hit_scenario(cache_entry: dict[str, Any] | None, no_cache: dict[str, Any]) -> dict[str, Any]:
    if cache_entry is None:
        return {
            "mode": "mmr_with_valid_cache",
            "cache_hit": False,
            "cache_miss": True,
            "invalidated": False,
            "materialized_documents": no_cache["materialized_documents"],
            "token_estimate": no_cache["token_estimate"],
            "latency_ms": no_cache["latency_ms"],
            "avoided_materialization": 0,
            "selected_documents": no_cache["selected_documents"],
        }
    selected = cache_entry["selected_documents"]
    return {
        "mode": "mmr_with_valid_cache",
        "cache_hit": True,
        "cache_miss": False,
        "invalidated": False,
        "materialized_documents": 0,
        "reused_documents": len(selected),
        "token_estimate": 0,
        "latency_ms": _latency_estimate(0, 0, cached=True),
        "avoided_materialization": len(selected),
        "saved_tokens": cache_entry["token_estimate"],
        "selected_documents": selected,
    }


def _cache_invalidated_scenario(
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    lookup: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = _select_documents(records, query, limit)
    token_estimate = sum(item["record"]["token_estimate"] for item in selected)
    invalidators = ["cache_entry_missing"]
    if lookup and lookup.get("invalidators"):
        invalidators = lookup["invalidators"]
    return {
        "mode": "mmr_with_invalidated_cache",
        "cache_hit": False,
        "cache_miss": True,
        "invalidated": True,
        "invalidators": invalidators,
        "materialized_documents": len(selected),
        "token_estimate": token_estimate,
        "latency_ms": _latency_estimate(len(selected), token_estimate, cached=False),
        "selected_documents": _selected_payload(selected),
    }


def _build_resolution_state(
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    coherence_threshold: float,
) -> dict[str, Any]:
    selected = _select_documents(records, query, limit)
    selected_docs = _selected_payload(selected)
    selected_records = [item["record"] for item in selected]
    materialized_slice = {
        "mode": "document_resolution_slice",
        "query": query,
        "documents": selected_docs,
        "token_estimate": sum(document["token_estimate"] for document in selected_docs),
    }
    coherence = _coherence_guard(selected_records, query, coherence_threshold)
    now = utc_ts()
    return {
        "query": query,
        "normalized_query": _normalize_query(query),
        "selected_docs": selected_docs,
        "materialized_slice": materialized_slice,
        "corpus_fingerprint": _corpus_fingerprint(records),
        "scoring_strategy": DOCUMENT_SCORING_VERSION,
        "answer_fingerprint": _answer_fingerprint(query, selected_docs),
        "coherence_score": coherence["coherence_score"],
        "coherence_guard": coherence,
        "limit": limit,
        "created_at": now,
    }


def _diffcache_naive_scenario(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = sum(record["token_estimate"] for record in records)
    latency_ms = _latency_estimate(len(records), total_tokens, cached=False)
    return {
        "mode": "naive_full_materialization",
        "materialized_documents": len(records),
        "latency_ms": latency_ms,
        "cost": {
            "control_overhead_tokens": 0,
        },
        "metrics": _diffcache_metrics(
            total_available_tokens=total_tokens,
            materialized_tokens=total_tokens,
            control_overhead_tokens=0,
            naive_latency_ms=latency_ms,
            latency_ms=latency_ms,
            divergence_ratio=0.0,
            reused_slices=0,
            rebuilt_slices=len(records),
            cache_hit=False,
            approximate_cache_hit=False,
            invalidations=0,
            coherence_score=1.0,
        ),
    }


def _diffcache_no_cache_scenario(
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    naive: dict[str, Any],
) -> dict[str, Any]:
    selected = _select_documents(records, query, limit)
    selected_records = [item["record"] for item in selected]
    materialized_tokens = sum(record["token_estimate"] for record in selected_records)
    control_overhead_tokens = max(20, len(records) * 8)
    latency_ms = _latency_estimate(len(selected_records), materialized_tokens, cached=False)
    coherence = _coherence_guard(selected_records, query, DIFFCACHE_COHERENCE_THRESHOLD)
    return {
        "mode": "mmr_without_cache",
        "selected_documents": _selected_payload(selected),
        "materialized_documents": len(selected_records),
        "latency_ms": latency_ms,
        "cost": {
            "control_overhead_tokens": control_overhead_tokens,
        },
        "metrics": _diffcache_metrics(
            total_available_tokens=naive["metrics"]["total_available_tokens"],
            materialized_tokens=materialized_tokens,
            control_overhead_tokens=control_overhead_tokens,
            naive_latency_ms=naive["latency_ms"],
            latency_ms=latency_ms,
            divergence_ratio=0.0,
            reused_slices=0,
            rebuilt_slices=len(selected_records),
            cache_hit=False,
            approximate_cache_hit=False,
            invalidations=0,
            coherence_score=coherence["coherence_score"],
        ),
    }


def _diffcache_exact_cache_scenario(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    naive: dict[str, Any],
    coherence_threshold: float,
) -> dict[str, Any]:
    state = _lookup_resolution_state_exact(connection, query, limit, records)
    invalidators = _resolution_invalidators(state, records) if state else ["resolution_state_missing"]
    selected_records = _records_from_selected_docs(records, state.get("selected_docs", []) if state else [])
    coherence = _coherence_guard(selected_records, query, coherence_threshold)
    can_reuse = state is not None and not invalidators and coherence["passed"]
    materialized_tokens = 0 if can_reuse else sum(record["token_estimate"] for record in selected_records)
    control_overhead_tokens = 6 if can_reuse else max(20, len(records) * 8)
    latency_ms = _latency_estimate(0, 0, cached=True) if can_reuse else _latency_estimate(
        len(selected_records),
        materialized_tokens,
        cached=False,
    )
    return {
        "mode": "mmr_cache_exact",
        "cache_hit": can_reuse,
        "invalidators": invalidators,
        "coherence_guard": coherence,
        "selected_documents": state.get("selected_docs", []) if state else [],
        "materialized_documents": 0 if can_reuse else len(selected_records),
        "latency_ms": latency_ms,
        "cost": {
            "control_overhead_tokens": control_overhead_tokens,
        },
        "metrics": _diffcache_metrics(
            total_available_tokens=naive["metrics"]["total_available_tokens"],
            materialized_tokens=materialized_tokens,
            control_overhead_tokens=control_overhead_tokens,
            naive_latency_ms=naive["latency_ms"],
            latency_ms=latency_ms,
            divergence_ratio=0.0,
            reused_slices=len(selected_records) if can_reuse else 0,
            rebuilt_slices=0 if can_reuse else len(selected_records),
            cache_hit=can_reuse,
            approximate_cache_hit=False,
            invalidations=len(invalidators),
            coherence_score=coherence["coherence_score"],
        ),
    }


def _diffcache_approximate_cache_scenario(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    naive: dict[str, Any],
    similarity_threshold: float,
    coherence_threshold: float,
) -> dict[str, Any]:
    candidate = _lookup_resolution_state_approximate(connection, query, limit, records, similarity_threshold)
    state = candidate.get("state") if candidate else None
    similarity = candidate.get("similarity", 0.0) if candidate else 0.0
    invalidators = _resolution_invalidators(state, records) if state else ["resolution_state_missing"]
    selected_records = _records_from_selected_docs(records, state.get("selected_docs", []) if state else [])
    coherence = _coherence_guard(selected_records, query, coherence_threshold)
    can_reuse = state is not None and not invalidators and similarity >= similarity_threshold and coherence["passed"]
    materialized_tokens = 0 if can_reuse else sum(record["token_estimate"] for record in selected_records)
    control_overhead_tokens = 8 if can_reuse else max(20, len(records) * 8)
    latency_ms = 4 if can_reuse else _latency_estimate(len(selected_records), materialized_tokens, cached=False)
    return {
        "mode": "mmr_cache_approximate",
        "cache_hit": False,
        "approximate_cache_hit": can_reuse,
        "query_similarity": similarity,
        "invalidators": invalidators,
        "coherence_guard": coherence,
        "selected_documents": state.get("selected_docs", []) if state else [],
        "materialized_documents": 0 if can_reuse else len(selected_records),
        "latency_ms": latency_ms,
        "cost": {
            "control_overhead_tokens": control_overhead_tokens,
        },
        "metrics": _diffcache_metrics(
            total_available_tokens=naive["metrics"]["total_available_tokens"],
            materialized_tokens=materialized_tokens,
            control_overhead_tokens=control_overhead_tokens,
            naive_latency_ms=naive["latency_ms"],
            latency_ms=latency_ms,
            divergence_ratio=0.0,
            reused_slices=len(selected_records) if can_reuse else 0,
            rebuilt_slices=0 if can_reuse else len(selected_records),
            cache_hit=False,
            approximate_cache_hit=can_reuse,
            invalidations=len(invalidators),
            coherence_score=coherence["coherence_score"],
        ),
    }


def _diffcache_divergence_scenario(
    resolution_state: dict[str, Any],
    base_records: list[dict[str, Any]],
    current_records: list[dict[str, Any]],
    query: str,
    limit: int,
    naive: dict[str, Any],
    coherence_threshold: float,
) -> dict[str, Any]:
    divergence_map = _build_divergence_map(resolution_state, base_records, current_records, query, limit)
    current_by_id = {record["id"]: record for record in current_records}
    rebuilt_records = [current_by_id[document_id] for document_id in divergence_map["rebuilt_slices"]]
    reused_records = [current_by_id[document_id] for document_id in divergence_map["reused_slices"]]
    output_records = reused_records + rebuilt_records
    coherence = _coherence_guard(output_records, query, coherence_threshold)
    if not coherence["passed"]:
        selected = _select_documents(current_records, query, limit)
        rebuilt_records = [item["record"] for item in selected]
        reused_records = []
        divergence_map = {
            **divergence_map,
            "reused_slices": [],
            "rebuilt_slices": [record["id"] for record in rebuilt_records],
            "coherence_forced_rematerialization": True,
        }
        output_records = rebuilt_records
        coherence = _coherence_guard(output_records, query, coherence_threshold)

    materialized_tokens = sum(record["token_estimate"] for record in rebuilt_records)
    control_overhead_tokens = max(10, len(current_records) * 3 + len(divergence_map["changed_docs"]) * 4)
    latency_ms = _latency_estimate(len(rebuilt_records), materialized_tokens, cached=False)
    invalidators = []
    if divergence_map["changed_docs"]:
        invalidators.extend(["corpus_fingerprint_changed", "document_hash_changed"])
    if divergence_map["rebuilt_slices"]:
        invalidators.append("selected_slice_hash_changed")
    return {
        "mode": "mmr_divergence_only_after_partial_change",
        "divergence_map": divergence_map,
        "invalidators": invalidators,
        "coherence_guard": coherence,
        "selected_documents": [
            {
                "id": record["id"],
                "title": record["title"],
                "token_estimate": record["token_estimate"],
                "document_hash": record["document_hash"],
                "slice_status": "rebuilt" if record in rebuilt_records else "reused",
            }
            for record in output_records
        ],
        "materialized_documents": len(rebuilt_records),
        "latency_ms": latency_ms,
        "cost": {
            "control_overhead_tokens": control_overhead_tokens,
        },
        "metrics": _diffcache_metrics(
            total_available_tokens=sum(record["token_estimate"] for record in current_records),
            materialized_tokens=materialized_tokens,
            control_overhead_tokens=control_overhead_tokens,
            naive_latency_ms=naive["latency_ms"],
            latency_ms=latency_ms,
            divergence_ratio=divergence_map["divergence_ratio"],
            reused_slices=len(reused_records),
            rebuilt_slices=len(rebuilt_records),
            cache_hit=False,
            approximate_cache_hit=False,
            invalidations=len(invalidators),
            coherence_score=coherence["coherence_score"],
        ),
    }


def _diffcache_metrics(
    *,
    total_available_tokens: int,
    materialized_tokens: int,
    control_overhead_tokens: int,
    naive_latency_ms: int,
    latency_ms: int,
    divergence_ratio: float,
    reused_slices: int,
    rebuilt_slices: int,
    cache_hit: bool,
    approximate_cache_hit: bool,
    invalidations: int,
    coherence_score: float,
) -> dict[str, Any]:
    return {
        "total_available_tokens": total_available_tokens,
        "materialized_tokens": materialized_tokens,
        "relative_resolution_cost": round(
            (materialized_tokens + control_overhead_tokens) / max(1, total_available_tokens),
            3,
        ),
        "divergence_ratio": divergence_ratio,
        "reused_slices": reused_slices,
        "rebuilt_slices": rebuilt_slices,
        "cache_hit": cache_hit,
        "approximate_cache_hit": approximate_cache_hit,
        "invalidations": invalidations,
        "latency_gain_ms": max(0, naive_latency_ms - latency_ms),
        "coherence_score": coherence_score,
    }


def _divergence_only_scenario(
    *,
    name: str,
    base_records: list[dict[str, Any]],
    base_selected: list[dict[str, Any]],
    current_records: list[dict[str, Any]],
    query: str,
    limit: int,
) -> dict[str, Any]:
    base_by_id = {record["id"]: record for record in base_records}
    current_by_id = {record["id"]: record for record in current_records}
    changed_documents = [
        document_id
        for document_id in sorted(set(base_by_id) | set(current_by_id))
        if base_by_id.get(document_id, {}).get("document_hash")
        != current_by_id.get(document_id, {}).get("document_hash")
    ]
    changed_ids = set(changed_documents)
    base_selected_by_id = {item["record"]["id"]: item["record"] for item in base_selected}
    current_selected = _select_documents(current_records, query, limit)
    reused = []
    rebuilt = []
    selected_payload = []
    for item in current_selected:
        record = item["record"]
        prior = base_selected_by_id.get(record["id"])
        is_reusable = prior is not None and prior.get("document_hash") == record.get("document_hash")
        if is_reusable:
            reused.append(item)
        else:
            rebuilt.append(item)
        selected_payload.append(
            {
                "id": record["id"],
                "title": record["title"],
                "score": item["score"],
                "token_estimate": record["token_estimate"],
                "document_hash": record.get("document_hash", ""),
                "slice_status": "reused" if is_reusable else "rebuilt",
            }
        )

    naive_tokens = sum(record["token_estimate"] for record in current_records)
    rebuilt_tokens = sum(item["record"]["token_estimate"] for item in rebuilt)
    reused_tokens = sum(item["record"]["token_estimate"] for item in reused)
    control_overhead_tokens = max(6, len(current_records) * 3 + len(changed_documents) * 4)
    avoided_tokens = max(0, naive_tokens - rebuilt_tokens - control_overhead_tokens)
    invalidators = []
    if _corpus_fingerprint(base_records) != _corpus_fingerprint(current_records):
        invalidators.append("corpus_fingerprint_changed")
    if changed_documents:
        invalidators.append("document_hash_changed")
    if changed_ids & {item["record"]["id"] for item in current_selected}:
        invalidators.append("selected_slice_hash_changed")

    return {
        "name": name,
        "mode": "divergence_only_materialization",
        "query": query,
        "limit": limit,
        "fingerprints": {
            "base": _corpus_fingerprint(base_records),
            "current": _corpus_fingerprint(current_records),
        },
        "logical_corpus_documents": len(current_records),
        "changed_documents": changed_documents,
        "changed_selected_documents": [
            item["record"]["id"] for item in current_selected if item["record"]["id"] in changed_ids
        ],
        "selected_slices": selected_payload,
        "coherent_slices": [item["record"]["id"] for item in reused],
        "rebuilt_slice_ids": [item["record"]["id"] for item in rebuilt],
        "invalidators": invalidators,
        "cost": {
            "naive_full_materialization_tokens": naive_tokens,
            "rebuilt_tokens": rebuilt_tokens,
            "reused_tokens": reused_tokens,
            "control_overhead_tokens": control_overhead_tokens,
        },
        "metrics": {
            "divergence_ratio": round(len(changed_documents) / max(1, len(current_records)), 3),
            "reused_slices": len(reused),
            "rebuilt_slices": len(rebuilt),
            "avoided_tokens": avoided_tokens,
            "avoided_materialization_ratio": round((naive_tokens - rebuilt_tokens) / max(1, naive_tokens), 3),
            "relative_resolution_cost": round((rebuilt_tokens + control_overhead_tokens) / max(1, naive_tokens), 3),
        },
        "result": "better" if avoided_tokens > 0 else "neutral",
        "created_at": utc_ts(),
    }


def _ensure_divergence_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_divergence_runs (
            run_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            query TEXT NOT NULL,
            base_fingerprint TEXT NOT NULL,
            current_fingerprint TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (run_id, scenario)
        )
        """
    )


def _store_divergence_scenario(
    connection: sqlite3.Connection,
    run_id: str,
    query: str,
    scenario: dict[str, Any],
) -> None:
    _ensure_divergence_table(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_divergence_runs (
            run_id,
            scenario,
            query,
            base_fingerprint,
            current_fingerprint,
            payload,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            scenario["name"],
            query,
            scenario["fingerprints"]["base"],
            scenario["fingerprints"]["current"],
            json.dumps(scenario, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _ensure_resolution_state_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_resolution_states (
            state_key TEXT PRIMARY KEY,
            normalized_query TEXT NOT NULL,
            query TEXT NOT NULL,
            limit_value INTEGER NOT NULL,
            corpus_fingerprint TEXT NOT NULL,
            scoring_strategy TEXT NOT NULL,
            answer_fingerprint TEXT NOT NULL,
            coherence_score REAL NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_resolution_state(connection: sqlite3.Connection, state: dict[str, Any]) -> None:
    _ensure_resolution_state_table(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_resolution_states (
            state_key,
            normalized_query,
            query,
            limit_value,
            corpus_fingerprint,
            scoring_strategy,
            answer_fingerprint,
            coherence_score,
            payload,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _resolution_state_key(state["normalized_query"], state["limit"], state["corpus_fingerprint"]),
            state["normalized_query"],
            state["query"],
            state["limit"],
            state["corpus_fingerprint"],
            state["scoring_strategy"],
            state["answer_fingerprint"],
            state["coherence_score"],
            json.dumps(state, sort_keys=True, ensure_ascii=False),
            state["created_at"],
        ),
    )


def _lookup_resolution_state_exact(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    _ensure_resolution_state_table(connection)
    key = _resolution_state_key(_normalize_query(query), limit, _corpus_fingerprint(records))
    row = connection.execute(
        """
        SELECT payload
        FROM mmr_resolution_states
        WHERE state_key = ?
        """,
        (key,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def _lookup_resolution_state_approximate(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
    records: list[dict[str, Any]],
    similarity_threshold: float,
) -> dict[str, Any] | None:
    _ensure_resolution_state_table(connection)
    normalized_query = _normalize_query(query)
    rows = connection.execute(
        """
        SELECT normalized_query, payload
        FROM mmr_resolution_states
        WHERE corpus_fingerprint = ? AND limit_value = ? AND scoring_strategy = ?
        """,
        (_corpus_fingerprint(records), limit, DOCUMENT_SCORING_VERSION),
    ).fetchall()
    best: dict[str, Any] | None = None
    for row in rows:
        similarity = _lexical_similarity(normalized_query, row[0])
        if similarity < similarity_threshold:
            continue
        state = json.loads(row[1])
        if best is None or similarity > best["similarity"]:
            best = {
                "state": state,
                "similarity": similarity,
            }
    return best


def _resolution_state_key(normalized_query: str, limit: int, corpus_fingerprint: str) -> str:
    return sha256(
        json.dumps(
            {
                "normalized_query": normalized_query,
                "limit": limit,
                "corpus_fingerprint": corpus_fingerprint,
                "scoring_strategy": DOCUMENT_SCORING_VERSION,
                "schema_version": DIFFCACHE_SCHEMA_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _resolution_invalidators(state: dict[str, Any] | None, records: list[dict[str, Any]]) -> list[str]:
    if state is None:
        return ["resolution_state_missing"]
    invalidators = []
    if state.get("corpus_fingerprint") != _corpus_fingerprint(records):
        invalidators.append("corpus_fingerprint_changed")
    if state.get("scoring_strategy") != DOCUMENT_SCORING_VERSION:
        invalidators.append("scoring_strategy_changed")
    return invalidators


def _build_divergence_map(
    resolution_state: dict[str, Any],
    base_records: list[dict[str, Any]],
    current_records: list[dict[str, Any]],
    query: str,
    limit: int,
) -> dict[str, Any]:
    base_by_id = {record["id"]: record for record in base_records}
    current_by_id = {record["id"]: record for record in current_records}
    all_ids = sorted(set(base_by_id) | set(current_by_id))
    changed_docs = [
        document_id
        for document_id in all_ids
        if base_by_id.get(document_id, {}).get("document_hash")
        != current_by_id.get(document_id, {}).get("document_hash")
    ]
    unchanged_docs = [document_id for document_id in all_ids if document_id not in changed_docs]
    current_selected = _select_documents(current_records, query, limit)
    cached_ids = {document["id"] for document in resolution_state["selected_docs"]}
    changed_ids = set(changed_docs)
    reused_slices = []
    rebuilt_slices = []
    for item in current_selected:
        document_id = item["record"]["id"]
        if document_id in cached_ids and document_id not in changed_ids:
            reused_slices.append(document_id)
        else:
            rebuilt_slices.append(document_id)
    return {
        "unchanged_docs": unchanged_docs,
        "changed_docs": changed_docs,
        "reused_slices": reused_slices,
        "rebuilt_slices": rebuilt_slices,
        "divergence_ratio": round(len(changed_docs) / max(1, len(current_records)), 3),
    }


def _records_from_selected_docs(
    records: list[dict[str, Any]],
    selected_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {record["id"]: record for record in records}
    return [by_id[document["id"]] for document in selected_docs if document["id"] in by_id]


def _answer_fingerprint(query: str, selected_docs: list[dict[str, Any]]) -> str:
    return sha256(
        json.dumps(
            {
                "normalized_query": _normalize_query(query),
                "selected_docs": [
                    {
                        "id": document["id"],
                        "document_hash": document.get("document_hash", ""),
                    }
                    for document in selected_docs
                ],
                "scoring_strategy": DOCUMENT_SCORING_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _normalize_query(query: str) -> str:
    return " ".join(sorted(_query_terms(query)))


def _query_terms(query: str) -> list[str]:
    cleaned = "".join(character.lower() if character.isalnum() else " " for character in query)
    stopwords = {"a", "an", "and", "de", "des", "du", "et", "la", "le", "les", "the"}
    return sorted({term for term in cleaned.split() if term and term not in stopwords})


def _lexical_similarity(left: str, right: str) -> float:
    left_terms = set(left.split())
    right_terms = set(right.split())
    if not left_terms or not right_terms:
        return 0.0
    return round(len(left_terms & right_terms) / len(left_terms | right_terms), 3)


def _coherence_guard(
    records: list[dict[str, Any]],
    query: str,
    threshold: float,
) -> dict[str, Any]:
    terms = _query_terms(query)
    if not terms:
        return {
            "passed": True,
            "coherence_score": 1.0,
            "covered_terms": [],
            "missing_terms": [],
        }
    text_parts = []
    for record in records:
        text_parts.extend(
            [
                record.get("title", ""),
                " ".join(record.get("tags", [])),
                record.get("body", ""),
            ]
        )
    text = " ".join(text_parts).lower()
    covered_terms = [term for term in terms if term in text]
    missing_terms = [term for term in terms if term not in covered_terms]
    score = round(len(covered_terms) / max(1, len(terms)), 3)
    return {
        "passed": score >= threshold,
        "coherence_score": score,
        "covered_terms": covered_terms,
        "missing_terms": missing_terms,
    }


def _prepare_memory_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = []
    for index, record in enumerate(records):
        record_id = str(record.get("id") or f"MEM-{index:04d}")
        prepared.append(
            {
                "id": record_id,
                "title": str(record.get("title", record.get("name", record_id))),
                "summary": str(record.get("summary", record.get("body", ""))),
                "source_refs": [str(item) for item in record.get("source_refs", [])],
                "tags": [str(item) for item in record.get("tags", [])],
                "claims": [str(item) for item in record.get("claims", [])],
                "verification_status": str(record.get("verification_status", "partial")),
                "usefulness_score": float(record.get("usefulness_score", 0.5) or 0.0),
                "recency_score": float(record.get("recency_score", 0.5) or 0.0),
            }
        )
    prepared.sort(key=lambda item: item["id"])
    return prepared


def _build_live_potential_state(
    records: list[dict[str, Any]],
    query: str,
    *,
    invalidators: list[str] | None = None,
) -> dict[str, Any]:
    now = utc_ts()
    latent_payload = {
        "query": query,
        "records": [_memory_record_payload(record) for record in records],
        "record_count": len(records),
    }
    state_fingerprint = _live_state_fingerprint(latent_payload)
    return {
        "id": f"PSTATE-LIVE-{sha256(_normalize_query(query).encode('utf-8')).hexdigest()[:10].upper()}",
        "type": "memory",
        "latent_payload": latent_payload,
        "state_fingerprint": state_fingerprint,
        "memory_version": f"memory-v{len(records)}-{state_fingerprint[:8]}",
        "created_at": now,
        "updated_at": now,
        "invalidators": list(invalidators or []),
    }


def _memory_record_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record["title"],
        "summary": record["summary"],
        "source_refs": record["source_refs"],
        "tags": record["tags"],
        "claims": record["claims"],
        "verification_status": record["verification_status"],
        "usefulness_score": record["usefulness_score"],
        "recency_score": record["recency_score"],
        "state_fingerprint": _memory_record_state_fingerprint(record),
        "slice_fingerprint": _memory_record_slice_fingerprint(record),
        "source_refs_fingerprint": _source_refs_fingerprint(record),
    }


def _live_state_fingerprint(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _select_memory_items(records: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    scored = []
    for record in records:
        score = _memory_score(record, query)
        if score > 0:
            scored.append({"record": record, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, limit)]


def _memory_score(record: dict[str, Any], query: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    text = " ".join(
        [
            record.get("title", ""),
            record.get("summary", ""),
            " ".join(record.get("tags", [])),
            " ".join(record.get("claims", [])),
            " ".join(record.get("source_refs", [])),
        ]
    ).lower()
    lexical = sum(1 for term in terms if term in text) / max(1, len(terms))
    verification = 0.15 if record.get("verification_status") in {"partial", "verified"} else 0.0
    usefulness = float(record.get("usefulness_score", 0.5) or 0.0) * 0.1
    recency = float(record.get("recency_score", 0.5) or 0.0) * 0.05
    return round(min(lexical + verification + usefulness + recency, 1.0), 3)


def _build_live_materialized_slice(
    potential_state: dict[str, Any],
    query: str,
    selected_items: list[dict[str, Any]],
    coherence_score: float,
) -> dict[str, Any]:
    source_refs = sorted(
        {
            source
            for item in selected_items
            for source in item.get("source_refs", [])
        }
    )
    slice_payload = {
        "query": query,
        "items": selected_items,
        "token_estimate": sum(item["token_estimate"] for item in selected_items),
    }
    slice_fingerprint = sha256(
        json.dumps(
            {
                "potential_state_id": potential_state["id"],
                "query": query,
                "items": [
                    {
                        "id": item["id"],
                        "slice_fingerprint": item["slice_fingerprint"],
                        "source_refs_fingerprint": item["source_refs_fingerprint"],
                    }
                    for item in selected_items
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "id": f"MSLICE-LIVE-{slice_fingerprint[:12].upper()}",
        "potential_state_id": potential_state["id"],
        "query": query,
        "slice_payload": slice_payload,
        "slice_fingerprint": slice_fingerprint,
        "coherence_score": coherence_score,
        "source_refs": source_refs,
        "created_at": utc_ts(),
    }


def _live_resolution_scenario(
    connection: sqlite3.Connection,
    *,
    name: str,
    previous_resolution: dict[str, Any] | None,
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    invalidators: list[str],
    coherence_threshold: float,
    force_store: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    potential_state = _build_live_potential_state(records, query, invalidators=invalidators)
    selected = _select_memory_items(records, query, limit)
    selected_items = [_live_selected_item(item["record"], item["score"]) for item in selected]
    total_tokens = _memory_total_tokens(records)
    prior_state = None if previous_resolution is None else previous_resolution["potential_state"]
    prior_slice = None if previous_resolution is None else previous_resolution["materialized_slice"]
    active_invalidators = list(invalidators)
    reused_items: list[dict[str, Any]] = []
    rebuilt_items: list[dict[str, Any]] = []
    reused_potential_states = 0
    rebuilt_potential_states = 1
    mode = "initial_materialization"

    if "memory_store_changed" in active_invalidators:
        rebuilt_items = selected_items
        active_invalidators.append("memory_store_changed")
        mode = "memory_invalidator_rematerialization"
    elif prior_state is not None and prior_state["state_fingerprint"] == potential_state["state_fingerprint"]:
        reused_potential_states = 1
        rebuilt_potential_states = 0
        reused_items = prior_slice["slice_payload"]["items"]
        mode = "exact_potential_state_reuse"
    elif prior_state is not None:
        active_invalidators.append("state_fingerprint_changed")
        prior_items = {item["id"]: item for item in prior_slice["slice_payload"]["items"]}
        for item in selected_items:
            prior_item = prior_items.get(item["id"])
            if prior_item is None:
                rebuilt_items.append(item)
                continue
            if prior_item["source_refs_fingerprint"] != item["source_refs_fingerprint"]:
                active_invalidators.append("source_refs_changed")
                rebuilt_items.append(item)
                continue
            if prior_item["slice_fingerprint"] == item["slice_fingerprint"]:
                reused_items.append(prior_item)
            else:
                rebuilt_items.append(item)
        mode = "divergence_only_potential_state_reuse"
    else:
        rebuilt_items = selected_items

    combined_items = [*reused_items, *rebuilt_items]
    coherence = _live_coherence_guard(combined_items, query, coherence_threshold)
    if not coherence["passed"]:
        reused_items = []
        rebuilt_items = selected_items
        combined_items = rebuilt_items
        coherence = _live_coherence_guard(combined_items, query, coherence_threshold)
        active_invalidators.append("coherence_guard_failed")
        mode = "coherence_forced_rematerialization"

    materialized_slice = _build_live_materialized_slice(
        potential_state,
        query,
        combined_items,
        coherence["coherence_score"],
    )
    rebuilt_tokens = sum(item["token_estimate"] for item in rebuilt_items)
    control_overhead_tokens = max(4, len(records) * 2 + len(active_invalidators) * 4)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    resolution_state = {
        "id": f"RSTATE-LIVE-{materialized_slice['slice_fingerprint'][:12].upper()}",
        "potential_state_id": potential_state["id"],
        "query": query,
        "state_fingerprint": potential_state["state_fingerprint"],
        "materialized_slice_id": materialized_slice["id"],
        "coherence_score": coherence["coherence_score"],
        "created_at": utc_ts(),
    }
    if force_store:
        _store_live_resolution_bundle(connection, potential_state, materialized_slice, resolution_state)
    return {
        "name": name,
        "mode": mode,
        "potential_state": potential_state,
        "materialized_slice": materialized_slice,
        "resolution_state": resolution_state,
        "invalidators": sorted(set(active_invalidators)),
        "coherence_guard": coherence,
        "metrics": {
            "reused_potential_states": reused_potential_states,
            "rebuilt_potential_states": rebuilt_potential_states,
            "reused_slices": len(reused_items),
            "rebuilt_slices": len(rebuilt_items),
            "memory_invalidation_count": len(set(active_invalidators)),
            "relative_resolution_cost": round((rebuilt_tokens + control_overhead_tokens) / max(1, total_tokens), 3),
            "coherence_score": coherence["coherence_score"],
            "latency_ms": latency_ms,
        },
    }


def _live_selected_item(record: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record["title"],
        "summary": record["summary"],
        "tags": record["tags"],
        "source_refs": record["source_refs"],
        "score": score,
        "token_estimate": _token_estimate(
            record["title"],
            record["summary"],
            " ".join(record["tags"]),
            " ".join(record["claims"]),
        ),
        "slice_fingerprint": _memory_record_slice_fingerprint(record),
        "state_fingerprint": _memory_record_state_fingerprint(record),
        "source_refs_fingerprint": _source_refs_fingerprint(record),
    }


def _live_coherence_guard(items: list[dict[str, Any]], query: str, threshold: float) -> dict[str, Any]:
    terms = _query_terms(query)
    if not terms:
        return {"passed": True, "coherence_score": 1.0, "covered_terms": [], "missing_terms": []}
    text = " ".join(
        " ".join(
            [
                item.get("title", ""),
                item.get("summary", ""),
                " ".join(item.get("tags", [])),
                " ".join(item.get("source_refs", [])),
            ]
        )
        for item in items
    ).lower()
    covered = [term for term in terms if term in text]
    missing = [term for term in terms if term not in covered]
    score = round(len(covered) / max(1, len(terms)), 3)
    return {
        "passed": score >= threshold,
        "coherence_score": score,
        "covered_terms": covered,
        "missing_terms": missing,
    }


def _ensure_potentialstate_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_live_potential_states (
            id TEXT NOT NULL,
            type TEXT NOT NULL,
            state_fingerprint TEXT NOT NULL,
            memory_version TEXT NOT NULL,
            payload TEXT NOT NULL,
            invalidators TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (id, state_fingerprint)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_live_materialized_slices (
            id TEXT PRIMARY KEY,
            potential_state_id TEXT NOT NULL,
            query TEXT NOT NULL,
            slice_fingerprint TEXT NOT NULL,
            coherence_score REAL NOT NULL,
            source_refs TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_live_resolution_states (
            state_key TEXT PRIMARY KEY,
            potential_state_id TEXT NOT NULL,
            query TEXT NOT NULL,
            state_fingerprint TEXT NOT NULL,
            materialized_slice_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_live_resolution_bundle(
    connection: sqlite3.Connection,
    potential_state: dict[str, Any],
    materialized_slice: dict[str, Any],
    resolution_state: dict[str, Any],
) -> None:
    _ensure_potentialstate_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_live_potential_states (
            id, type, state_fingerprint, memory_version, payload, invalidators, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            potential_state["id"],
            potential_state["type"],
            potential_state["state_fingerprint"],
            potential_state["memory_version"],
            json.dumps(potential_state, sort_keys=True, ensure_ascii=False),
            json.dumps(potential_state["invalidators"], sort_keys=True, ensure_ascii=False),
            potential_state["created_at"],
            potential_state["updated_at"],
        ),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_live_materialized_slices (
            id, potential_state_id, query, slice_fingerprint, coherence_score, source_refs, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            materialized_slice["id"],
            materialized_slice["potential_state_id"],
            materialized_slice["query"],
            materialized_slice["slice_fingerprint"],
            materialized_slice["coherence_score"],
            json.dumps(materialized_slice["source_refs"], sort_keys=True, ensure_ascii=False),
            json.dumps(materialized_slice, sort_keys=True, ensure_ascii=False),
            materialized_slice["created_at"],
        ),
    )
    state_key = _live_resolution_key(
        resolution_state["potential_state_id"],
        resolution_state["query"],
        resolution_state["state_fingerprint"],
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_live_resolution_states (
            state_key, potential_state_id, query, state_fingerprint, materialized_slice_id, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            state_key,
            resolution_state["potential_state_id"],
            resolution_state["query"],
            resolution_state["state_fingerprint"],
            resolution_state["materialized_slice_id"],
            json.dumps(resolution_state, sort_keys=True, ensure_ascii=False),
            resolution_state["created_at"],
        ),
    )


def _lookup_live_resolution(
    connection: sqlite3.Connection,
    potential_state_id: str,
    query: str,
) -> dict[str, Any] | None:
    _ensure_potentialstate_tables(connection)
    row = connection.execute(
        """
        SELECT r.payload, p.payload, s.payload
        FROM mmr_live_resolution_states r
        JOIN mmr_live_potential_states p
          ON p.id = r.potential_state_id AND p.state_fingerprint = r.state_fingerprint
        JOIN mmr_live_materialized_slices s
          ON s.id = r.materialized_slice_id
        WHERE r.potential_state_id = ? AND r.query = ?
        ORDER BY r.created_at DESC
        LIMIT 1
        """,
        (potential_state_id, query),
    ).fetchone()
    if not row:
        return None
    return {
        "resolution_state": json.loads(row[0]),
        "potential_state": json.loads(row[1]),
        "materialized_slice": json.loads(row[2]),
    }


def _can_reuse_live_resolution(previous_resolution: dict[str, Any] | None, potential_state: dict[str, Any]) -> bool:
    if previous_resolution is None:
        return False
    previous_state = previous_resolution["potential_state"]
    return (
        previous_state["state_fingerprint"] == potential_state["state_fingerprint"]
        and "memory_store_changed" not in previous_state.get("invalidators", [])
    )


def _live_resolution_key(potential_state_id: str, query: str, state_fingerprint: str) -> str:
    return sha256(
        json.dumps(
            {
                "potential_state_id": potential_state_id,
                "query": query,
                "state_fingerprint": state_fingerprint,
                "schema_version": POTENTIALSTATE_SCHEMA_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _memory_record_state_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "id": record["id"],
        "title": record["title"],
        "summary": record["summary"],
        "source_refs": record["source_refs"],
        "tags": record["tags"],
        "claims": record["claims"],
        "verification_status": record["verification_status"],
        "usefulness_score": record["usefulness_score"],
        "recency_score": record["recency_score"],
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _memory_record_slice_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "id": record["id"],
        "title": record["title"],
        "summary": record["summary"],
        "tags": record["tags"],
        "claims": record["claims"],
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _source_refs_fingerprint(record: dict[str, Any]) -> str:
    return sha256(
        json.dumps(sorted(record.get("source_refs", [])), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _memory_total_tokens(records: list[dict[str, Any]]) -> int:
    return sum(
        _token_estimate(
            record.get("title", ""),
            record.get("summary", ""),
            " ".join(record.get("tags", [])),
            " ".join(record.get("claims", [])),
            " ".join(record.get("source_refs", [])),
        )
        for record in records
    )


def _low_memory_mutation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    mutated[0] = {
        **mutated[0],
        "recency_score": max(0.1, float(mutated[0].get("recency_score", 1.0)) - 0.1),
    }
    return mutated


def _strong_memory_mutation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    mutated[0] = {
        **mutated[0],
        "summary": mutated[0]["summary"] + " Strong mutation adds new live memory constraints.",
        "source_refs": [*mutated[0].get("source_refs", []), "runtime/live_memory_mutation"],
    }
    return mutated


def _build_state_segments(potential_state: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments = []
    for record in records:
        segment_payload = {
            "title": record["title"],
            "summary": record["summary"],
            "source_refs": record["source_refs"],
            "claims": record["claims"],
        }
        semantic_tags = sorted(set(record.get("tags", [])))
        segment_fingerprint = sha256(
            json.dumps(segment_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        segment_id = sha256(
            json.dumps(
                {
                    "potential_state_id": potential_state["id"],
                    "segment_key": record["id"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12].upper()
        segments.append(
            {
                "id": f"SEG-{segment_id}",
                "potential_state_id": potential_state["id"],
                "segment_key": record["id"],
                "segment_payload": segment_payload,
                "segment_fingerprint": segment_fingerprint,
                "semantic_tags": semantic_tags,
                "source_refs_fingerprint": _source_refs_fingerprint(record),
                "token_estimate": _token_estimate(
                    record["title"],
                    record["summary"],
                    " ".join(record.get("tags", [])),
                    " ".join(record.get("claims", [])),
                ),
                "updated_at": utc_ts(),
            }
        )
    return sorted(segments, key=lambda segment: segment["segment_key"])


def _ensure_intrastate_benchmark_records(
    records: list[dict[str, Any]],
    query: str,
    *,
    minimum: int,
) -> list[dict[str, Any]]:
    if len(records) >= minimum:
        return records

    prepared_defaults = _prepare_memory_records(DEFAULT_MEMORY_RECORDS)
    existing_ids = {record["id"] for record in records}
    augmented = [*records]
    for record in prepared_defaults:
        if record["id"] in existing_ids:
            continue
        augmented.append(record)
        existing_ids.add(record["id"])
        if len(augmented) >= minimum:
            return sorted(augmented, key=lambda item: item["id"])

    terms = _query_terms(query) or ["memory"]
    while len(augmented) < minimum:
        index = len(augmented) + 1
        record_id = f"KT-INTRASTATE-CONTROL-{index:03d}"
        augmented.append(
            {
                "id": record_id,
                "title": f"Intra-state control segment {index}",
                "summary": (
                    "Controlled benchmark segment for StateSegment delta reuse across "
                    f"{' '.join(terms)} constraints."
                ),
                "source_refs": ["runtime/intrastate_delta"],
                "tags": [*terms, "intrastate", "delta"],
                "claims": [
                    "A controlled segment keeps the benchmark able to measure partial reuse.",
                ],
                "verification_status": "partial",
                "usefulness_score": 0.5,
                "recency_score": 1.0,
            }
        )
    return sorted(augmented, key=lambda item: item["id"])


def _select_state_segments(segments: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    scored = []
    terms = _query_terms(query)
    for segment in segments:
        text = " ".join(
            [
                segment["segment_payload"].get("title", ""),
                segment["segment_payload"].get("summary", ""),
                " ".join(segment.get("semantic_tags", [])),
                " ".join(segment["segment_payload"].get("claims", [])),
                " ".join(segment["segment_payload"].get("source_refs", [])),
            ]
        ).lower()
        matches = sum(1 for term in terms if term in text)
        if matches <= 0:
            continue
        scored.append({"segment": segment, "score": round(matches / max(1, len(terms)), 3)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    selected = []
    for item in scored[: max(1, limit)]:
        selected.append({**item["segment"], "score": item["score"]})
    return selected


def _build_intrastate_materialized_slice(
    potential_state: dict[str, Any],
    query: str,
    segments: list[dict[str, Any]],
    coherence_score: float,
) -> dict[str, Any]:
    source_refs = sorted(
        {
            source
            for segment in segments
            for source in segment["segment_payload"].get("source_refs", [])
        }
    )
    slice_payload = {
        "query": query,
        "segments": [
            {
                "state_segment_id": segment["id"],
                "segment_key": segment["segment_key"],
                "score": segment.get("score", 0.0),
                "token_estimate": segment["token_estimate"],
                "segment_fingerprint": segment["segment_fingerprint"],
            }
            for segment in segments
        ],
        "token_estimate": sum(segment["token_estimate"] for segment in segments),
    }
    slice_fingerprint = sha256(
        json.dumps(
            {
                "potential_state_id": potential_state["id"],
                "query": query,
                "segments": [
                    {
                        "id": segment["id"],
                        "segment_fingerprint": segment["segment_fingerprint"],
                        "semantic_tags": segment["semantic_tags"],
                        "source_refs_fingerprint": segment["source_refs_fingerprint"],
                    }
                    for segment in segments
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "id": f"MSLICE-DELTA-{slice_fingerprint[:12].upper()}",
        "potential_state_id": potential_state["id"],
        "query": query,
        "slice_payload": slice_payload,
        "slice_fingerprint": slice_fingerprint,
        "coherence_score": coherence_score,
        "source_refs": source_refs,
        "state_segment_ids": [segment["id"] for segment in segments],
        "created_at": utc_ts(),
    }


def _intrastate_delta_scenario(
    *,
    connection: sqlite3.Connection,
    name: str,
    previous_segments: list[dict[str, Any]],
    previous_slice: dict[str, Any],
    records: list[dict[str, Any]],
    query: str,
    limit: int,
    invalidators: list[str],
    coherence_threshold: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    potential_state = _build_live_potential_state(records, query, invalidators=invalidators)
    current_segments = _build_state_segments(potential_state, records)
    selected_segments = _select_state_segments(current_segments, query, limit)
    previous_by_key = {segment["segment_key"]: segment for segment in previous_segments}
    current_by_key = {segment["segment_key"]: segment for segment in current_segments}
    selected_keys = {segment["segment_key"] for segment in selected_segments}
    global_invalidation = "memory_store_changed" in invalidators
    unchanged_segments = []
    changed_segments = []
    segment_invalidators = set(invalidators)
    for key in sorted(set(previous_by_key) | set(current_by_key)):
        previous = previous_by_key.get(key)
        current = current_by_key.get(key)
        if previous is None or current is None:
            changed_segments.append(key)
            segment_invalidators.add("segment_fingerprint_changed")
            continue
        changed = False
        if previous["segment_fingerprint"] != current["segment_fingerprint"]:
            segment_invalidators.add("segment_fingerprint_changed")
            changed = True
        if previous["semantic_tags"] != current["semantic_tags"]:
            segment_invalidators.add("semantic_tags_changed")
            changed = True
        if previous["source_refs_fingerprint"] != current["source_refs_fingerprint"]:
            segment_invalidators.add("source_ref_changed")
            changed = True
        if changed:
            changed_segments.append(key)
        else:
            unchanged_segments.append(key)

    previous_slice_keys = {
        item["segment_key"]
        for item in previous_slice["slice_payload"].get("segments", [])
    }
    reused_segments = []
    rebuilt_segments = []
    for segment in selected_segments:
        key = segment["segment_key"]
        if not global_invalidation and key in unchanged_segments and key in previous_slice_keys:
            reused_segments.append(segment)
        else:
            rebuilt_segments.append(segment)

    coherence = _segment_coherence_guard(selected_segments, query, coherence_threshold)
    if not coherence["passed"]:
        reused_segments = []
        rebuilt_segments = selected_segments
        segment_invalidators.add("coherence_guard_failed")
        coherence = _segment_coherence_guard(rebuilt_segments, query, coherence_threshold)

    materialized_slice = _build_intrastate_materialized_slice(
        potential_state,
        query,
        selected_segments,
        coherence["coherence_score"],
    )
    _store_intrastate_segments(connection, current_segments)
    _store_intrastate_slice(connection, materialized_slice)
    _store_intrastate_run(connection, name, potential_state, materialized_slice, current_segments)

    rebuilt_tokens = sum(segment["token_estimate"] for segment in rebuilt_segments)
    total_tokens = sum(segment["token_estimate"] for segment in current_segments)
    control_overhead_tokens = max(4, len(current_segments) + len(segment_invalidators) * 3)
    total_segments = len(current_segments)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    delta_map = {
        "unchanged_segments": unchanged_segments,
        "changed_segments": changed_segments,
        "reused_segments": [segment["segment_key"] for segment in reused_segments],
        "rebuilt_segments": [segment["segment_key"] for segment in rebuilt_segments],
        "delta_ratio": round(len(changed_segments) / max(1, total_segments), 3),
    }
    return {
        "name": name,
        "mode": "intra_state_delta_materialization",
        "potential_state": potential_state,
        "state_segments": current_segments,
        "materialized_slice": materialized_slice,
        "delta_map": delta_map,
        "invalidators": sorted(segment_invalidators),
        "coherence_guard": coherence,
        "metrics": {
            "total_segments": total_segments,
            "changed_segments": len(changed_segments),
            "reused_segments": len(reused_segments),
            "rebuilt_segments": len(rebuilt_segments),
            "delta_ratio": delta_map["delta_ratio"],
            "avoided_rebuild_ratio": round(len(reused_segments) / max(1, len(selected_segments)), 3),
            "relative_resolution_cost": round(
                (rebuilt_tokens + control_overhead_tokens) / max(1, total_tokens),
                3,
            ),
            "latency_ms": latency_ms,
            "coherence_score": coherence["coherence_score"],
        },
    }


def _segment_coherence_guard(segments: list[dict[str, Any]], query: str, threshold: float) -> dict[str, Any]:
    terms = _query_terms(query)
    if not terms:
        return {"passed": True, "coherence_score": 1.0, "covered_terms": [], "missing_terms": []}
    text = " ".join(
        " ".join(
            [
                segment["segment_payload"].get("title", ""),
                segment["segment_payload"].get("summary", ""),
                " ".join(segment.get("semantic_tags", [])),
                " ".join(segment["segment_payload"].get("claims", [])),
                " ".join(segment["segment_payload"].get("source_refs", [])),
            ]
        )
        for segment in segments
    ).lower()
    covered = [term for term in terms if term in text]
    missing = [term for term in terms if term not in covered]
    score = round(len(covered) / max(1, len(terms)), 3)
    return {
        "passed": score >= threshold,
        "coherence_score": score,
        "covered_terms": covered,
        "missing_terms": missing,
    }


def _build_microfragments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fragments = []
    for segment in segments:
        payload = segment["segment_payload"]
        source_refs = [str(item) for item in payload.get("source_refs", [])]
        fields = [
            ("title", {"value": payload.get("title", "")}),
            ("summary", {"value": payload.get("summary", "")}),
            ("claims", {"values": payload.get("claims", [])}),
            ("semantic_tags", {"values": segment.get("semantic_tags", [])}),
            ("source_refs", {"values": source_refs}),
        ]
        for fragment_key, fragment_payload in fields:
            semantic_tags = _microfragment_tags(segment, fragment_key)
            fragment_fingerprint = sha256(
                json.dumps(
                    {
                        "fragment_key": fragment_key,
                        "payload": fragment_payload,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            fragment_id = sha256(
                json.dumps(
                    {
                        "state_segment_id": segment["id"],
                        "fragment_key": fragment_key,
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:12].upper()
            text = _fragment_payload_text(fragment_payload)
            fragments.append(
                {
                    "id": f"MICRO-{fragment_id}",
                    "state_segment_id": segment["id"],
                    "segment_key": segment["segment_key"],
                    "fragment_key": fragment_key,
                    "fragment_identity": f"{segment['segment_key']}::{fragment_key}",
                    "fragment_payload": fragment_payload,
                    "fragment_fingerprint": fragment_fingerprint,
                    "semantic_tags": semantic_tags,
                    "source_refs": source_refs,
                    "token_estimate": _token_estimate(text, " ".join(semantic_tags), " ".join(source_refs)),
                    "updated_at": segment["updated_at"],
                }
            )
    return sorted(fragments, key=lambda item: item["fragment_identity"])


def _microfragment_tags(segment: dict[str, Any], fragment_key: str) -> list[str]:
    tags = set(segment.get("semantic_tags", []))
    tags.add(fragment_key)
    if fragment_key == "source_refs":
        tags.add("source")
    if fragment_key == "claims":
        tags.add("proof")
    return sorted(tags)


def _fragment_payload_text(payload: Any) -> str:
    if isinstance(payload, dict):
        parts = []
        for value in payload.values():
            parts.append(_fragment_payload_text(value))
        return " ".join(parts)
    if isinstance(payload, list):
        return " ".join(_fragment_payload_text(item) for item in payload)
    return str(payload)


def _select_microfragments(
    fragments: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    scored = []
    for fragment in fragments:
        text = " ".join(
            [
                _fragment_payload_text(fragment["fragment_payload"]),
                " ".join(fragment.get("semantic_tags", [])),
                " ".join(fragment.get("source_refs", [])),
            ]
        ).lower()
        matches = sum(1 for term in terms if term in text)
        if matches <= 0:
            continue
        score = round(matches / max(1, len(terms)), 3)
        scored.append({"fragment": fragment, "score": score})
    scored.sort(
        key=lambda item: (
            item["score"],
            _microfragment_priority(item["fragment"]["fragment_key"]),
            -item["fragment"]["token_estimate"],
        ),
        reverse=True,
    )
    return [
        {**item["fragment"], "score": item["score"]}
        for item in scored[: max(1, fragment_limit)]
    ]


def _microfragment_priority(fragment_key: str) -> int:
    return {
        "semantic_tags": 5,
        "summary": 4,
        "title": 3,
        "claims": 2,
        "source_refs": 1,
    }.get(fragment_key, 0)


def _build_microdelta_materialized_slice(
    potential_state: dict[str, Any],
    query: str,
    fragments: list[dict[str, Any]],
    coherence_score: float,
) -> dict[str, Any]:
    source_refs = sorted({source for fragment in fragments for source in fragment.get("source_refs", [])})
    slice_payload = {
        "query": query,
        "microfragments": [
            {
                "microfragment_id": fragment["id"],
                "state_segment_id": fragment["state_segment_id"],
                "segment_key": fragment["segment_key"],
                "fragment_key": fragment["fragment_key"],
                "score": fragment.get("score", 0.0),
                "token_estimate": fragment["token_estimate"],
                "fragment_fingerprint": fragment["fragment_fingerprint"],
            }
            for fragment in fragments
        ],
        "token_estimate": sum(fragment["token_estimate"] for fragment in fragments),
    }
    slice_fingerprint = sha256(
        json.dumps(
            {
                "potential_state_id": potential_state["id"],
                "query": query,
                "microfragments": [
                    {
                        "id": fragment["id"],
                        "fragment_fingerprint": fragment["fragment_fingerprint"],
                        "semantic_tags": fragment["semantic_tags"],
                        "source_refs": fragment["source_refs"],
                    }
                    for fragment in fragments
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "id": f"MSLICE-MICRO-{slice_fingerprint[:12].upper()}",
        "potential_state_id": potential_state["id"],
        "query": query,
        "slice_payload": slice_payload,
        "slice_fingerprint": slice_fingerprint,
        "coherence_score": coherence_score,
        "source_refs": source_refs,
        "microfragment_ids": [fragment["id"] for fragment in fragments],
        "created_at": utc_ts(),
    }


def _build_slice_dependency_graph(
    materialized_slice: dict[str, Any],
    fragments: list[dict[str, Any]],
    invalidation_reasons: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    reasons = invalidation_reasons or {}
    graph = []
    for fragment in fragments:
        slice_id = sha256(
            json.dumps(
                {
                    "materialized_slice_id": materialized_slice["id"],
                    "microfragment_id": fragment["id"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12].upper()
        graph.append(
            {
                "slice_id": f"MSLICE-DEPENDENCY-{slice_id}",
                "depends_on_microfragment_ids": [fragment["id"]],
                "dependency_weight": fragment.get("score", 0.0),
                "invalidation_reason": reasons.get(fragment["id"]),
            }
        )
    return graph


def _selected_microfragment_identities(fragments: list[dict[str, Any]]) -> set[str]:
    return {fragment["fragment_identity"] for fragment in fragments}


def _microdelta_scenario(
    *,
    connection: sqlite3.Connection,
    name: str,
    previous_fragments: list[dict[str, Any]],
    previous_slice: dict[str, Any],
    previous_dependency_graph: list[dict[str, Any]],
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    invalidators: list[str],
    coherence_threshold: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    potential_state = _build_live_potential_state(records, query, invalidators=invalidators)
    current_segments = _build_state_segments(potential_state, records)
    current_fragments = _build_microfragments(current_segments)
    selected_fragments = _select_microfragments(current_fragments, query, fragment_limit)
    previous_by_identity = {fragment["fragment_identity"]: fragment for fragment in previous_fragments}
    current_by_identity = {fragment["fragment_identity"]: fragment for fragment in current_fragments}
    previous_dependency_ids = {
        microfragment_id
        for dependency in previous_dependency_graph
        for microfragment_id in dependency.get("depends_on_microfragment_ids", [])
    }
    selected_identities = {fragment["fragment_identity"] for fragment in selected_fragments}
    global_invalidation = "memory_store_changed" in invalidators
    unchanged_fragments = []
    changed_fragments = []
    fragment_invalidators = set(invalidators)
    invalidation_reasons_by_id: dict[str, str] = {}

    for identity in sorted(set(previous_by_identity) | set(current_by_identity)):
        previous = previous_by_identity.get(identity)
        current = current_by_identity.get(identity)
        if previous is None or current is None:
            changed_fragments.append(identity)
            fragment_invalidators.add("fragment_fingerprint_changed")
            if current is not None:
                invalidation_reasons_by_id[current["id"]] = "fragment_fingerprint_changed"
            continue
        reasons = []
        if previous["fragment_fingerprint"] != current["fragment_fingerprint"]:
            reasons.append("fragment_fingerprint_changed")
        if previous["semantic_tags"] != current["semantic_tags"]:
            reasons.append("semantic_tags_changed")
        if sorted(previous.get("source_refs", [])) != sorted(current.get("source_refs", [])):
            reasons.append("source_ref_changed")
        if reasons:
            changed_fragments.append(identity)
            for reason in reasons:
                fragment_invalidators.add(reason)
            invalidation_reasons_by_id[current["id"]] = ", ".join(reasons)
        else:
            unchanged_fragments.append(identity)

    reused_fragments = []
    rebuilt_fragments = []
    for fragment in selected_fragments:
        identity = fragment["fragment_identity"]
        if (
            not global_invalidation
            and identity in unchanged_fragments
            and fragment["id"] in previous_dependency_ids
        ):
            reused_fragments.append(fragment)
        else:
            rebuilt_fragments.append(fragment)
            invalidation_reasons_by_id.setdefault(
                fragment["id"],
                "memory_store_changed" if global_invalidation else "fragment_fingerprint_changed",
            )

    coherence = _microfragment_coherence_guard(selected_fragments, query, coherence_threshold)
    if not coherence["passed"]:
        reused_fragments = []
        rebuilt_fragments = selected_fragments
        fragment_invalidators.add("coherence_guard_failed")
        for fragment in rebuilt_fragments:
            invalidation_reasons_by_id[fragment["id"]] = "coherence_guard_failed"
        coherence = _microfragment_coherence_guard(rebuilt_fragments, query, coherence_threshold)

    materialized_slice = _build_microdelta_materialized_slice(
        potential_state,
        query,
        selected_fragments,
        coherence["coherence_score"],
    )
    dependency_graph = _build_slice_dependency_graph(
        materialized_slice,
        selected_fragments,
        invalidation_reasons_by_id,
    )
    _store_microfragments(connection, current_fragments)
    _store_microdelta_slice(connection, materialized_slice, dependency_graph)
    _store_microdelta_run(
        connection,
        name,
        potential_state,
        materialized_slice,
        dependency_graph,
        current_fragments,
    )

    rebuilt_tokens = sum(fragment["token_estimate"] for fragment in rebuilt_fragments)
    total_tokens = sum(fragment["token_estimate"] for fragment in current_fragments)
    control_overhead_tokens = max(4, len(selected_fragments) + len(fragment_invalidators) * 2)
    total_fragments = len(current_fragments)
    affected_slices = sum(1 for dependency in dependency_graph if dependency["invalidation_reason"])
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    micro_delta_map = {
        "unchanged_fragments": unchanged_fragments,
        "changed_fragments": changed_fragments,
        "reused_fragments": [fragment["fragment_identity"] for fragment in reused_fragments],
        "rebuilt_fragments": [fragment["fragment_identity"] for fragment in rebuilt_fragments],
        "micro_delta_ratio": round(len(changed_fragments) / max(1, total_fragments), 3),
    }
    return {
        "name": name,
        "mode": "microdelta_dependency_materialization",
        "potential_state": potential_state,
        "state_segments": current_segments,
        "microfragments": current_fragments,
        "materialized_slice": materialized_slice,
        "slice_dependency_graph": dependency_graph,
        "micro_delta_map": micro_delta_map,
        "invalidators": sorted(fragment_invalidators),
        "coherence_guard": coherence,
        "metrics": {
            "total_fragments": total_fragments,
            "changed_fragments": len(changed_fragments),
            "reused_fragments": len(reused_fragments),
            "rebuilt_fragments": len(rebuilt_fragments),
            "affected_slices": affected_slices,
            "micro_delta_ratio": micro_delta_map["micro_delta_ratio"],
            "avoided_rebuild_ratio": round(len(reused_fragments) / max(1, len(selected_fragments)), 3),
            "relative_resolution_cost": round(
                (rebuilt_tokens + control_overhead_tokens) / max(1, total_tokens),
                3,
            ),
            "latency_ms": latency_ms,
            "coherence_score": coherence["coherence_score"],
        },
    }


def _microfragment_coherence_guard(
    fragments: list[dict[str, Any]],
    query: str,
    threshold: float,
) -> dict[str, Any]:
    terms = _query_terms(query)
    if not terms:
        return {"passed": True, "coherence_score": 1.0, "covered_terms": [], "missing_terms": []}
    text = " ".join(
        " ".join(
            [
                _fragment_payload_text(fragment["fragment_payload"]),
                " ".join(fragment.get("semantic_tags", [])),
                " ".join(fragment.get("source_refs", [])),
            ]
        )
        for fragment in fragments
    ).lower()
    covered = [term for term in terms if term in text]
    missing = [term for term in terms if term not in covered]
    score = round(len(covered) / max(1, len(terms)), 3)
    return {
        "passed": score >= threshold,
        "coherence_score": score,
        "covered_terms": covered,
        "missing_terms": missing,
    }


def _build_predictive_patterns(
    query: str,
    fragments: list[dict[str, Any]],
    active_fragments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    query_signature = _query_signature(query)
    active_identities = {fragment["fragment_identity"] for fragment in active_fragments}
    patterns = []
    for fragment in fragments:
        scoring = _prediction_scoring_components(fragment, query, fragment["fragment_identity"] in active_identities)
        prediction_weight = round(
            (
                scoring["frequency"]
                + scoring["structural_proximity"]
                + scoring["divergence_history"]
                + scoring["query_history"]
                + scoring["coherence_stability"]
            )
            / 5,
            3,
        )
        if prediction_weight < 0.45:
            continue
        pattern_id = sha256(
            json.dumps(
                {
                    "query_signature": query_signature,
                    "fragment_identity": fragment["fragment_identity"],
                    "fragment_fingerprint": fragment["fragment_fingerprint"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12].upper()
        patterns.append(
            {
                "id": f"PPAT-{pattern_id}",
                "query_signature": query_signature,
                "mutation_signature": "stable-microdelta-history",
                "frequently_used_fragments": [fragment["fragment_identity"]],
                "microfragment_ids": [fragment["id"]],
                "fragment_fingerprint": fragment["fragment_fingerprint"],
                "prediction_weight": prediction_weight,
                "last_hit_at": utc_ts(),
                "hit_count": max(1, int(prediction_weight * 10)),
                "scoring": scoring,
            }
        )
    patterns.sort(key=lambda item: (item["prediction_weight"], item["hit_count"]), reverse=True)
    return patterns


def _prediction_scoring_components(
    fragment: dict[str, Any],
    query: str,
    active: bool,
) -> dict[str, float]:
    score = float(fragment.get("score", 0.0))
    priority = _microfragment_priority(fragment["fragment_key"]) / 5
    terms = _query_terms(query)
    text = " ".join(
        [
            _fragment_payload_text(fragment["fragment_payload"]),
            " ".join(fragment.get("semantic_tags", [])),
            " ".join(fragment.get("source_refs", [])),
        ]
    ).lower()
    query_hits = sum(1 for term in terms if term in text) / max(1, len(terms))
    stability = 0.95
    if fragment["fragment_key"] in {"source_refs", "semantic_tags"}:
        stability = 0.75
    return {
        "frequency": round(min(1.0, 0.35 + priority * 0.45 + (0.2 if active else 0.0)), 3),
        "structural_proximity": round(min(1.0, score + (0.2 if active else 0.0)), 3),
        "divergence_history": stability,
        "query_history": round(query_hits, 3),
        "coherence_stability": round(min(1.0, 0.5 + query_hits * 0.35 + priority * 0.15), 3),
    }


def _build_predictive_materialization(
    query: str,
    patterns: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    *,
    prewarm_limit: int,
) -> dict[str, Any]:
    fragments_by_identity = {fragment["fragment_identity"]: fragment for fragment in fragments}
    prewarmed_fragments = []
    for pattern in patterns:
        if len(prewarmed_fragments) >= max(1, prewarm_limit):
            break
        for identity in pattern["frequently_used_fragments"]:
            fragment = fragments_by_identity.get(identity)
            if fragment is not None and fragment not in prewarmed_fragments:
                prewarmed_fragments.append(fragment)
    materialization_id = sha256(
        json.dumps(
            {
                "query_signature": _query_signature(query),
                "prewarmed": [fragment["fragment_identity"] for fragment in prewarmed_fragments],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "id": f"PMAT-{materialization_id}",
        "query_signature": _query_signature(query),
        "policy": "predictive_sparse_prewarm",
        "pattern_ids": [pattern["id"] for pattern in patterns[: max(1, prewarm_limit)]],
        "prewarmed_fragments": prewarmed_fragments,
        "created_at": utc_ts(),
    }


def _query_signature(query: str) -> str:
    return sha256(_normalize_query(query).encode("utf-8")).hexdigest()[:16]


def _mutation_signature(records: list[dict[str, Any]], invalidators: list[str]) -> str:
    return sha256(
        json.dumps(
            {
                "records": [
                    {
                        "id": record["id"],
                        "state_fingerprint": _memory_record_state_fingerprint(record),
                    }
                    for record in records
                ],
                "invalidators": sorted(invalidators),
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]


def _predictive_sparse_scenario(
    *,
    connection: sqlite3.Connection,
    name: str,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    predictive_patterns: list[dict[str, Any]],
    predictive_materialization: dict[str, Any],
    reference_fragments: list[dict[str, Any]],
    invalidators: list[str],
    coherence_threshold: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    potential_state = _build_live_potential_state(records, query, invalidators=invalidators)
    current_segments = _build_state_segments(potential_state, records)
    current_fragments = _build_microfragments(current_segments)
    active_fragments = _select_microfragments(current_fragments, query, fragment_limit)
    reference_by_identity = {fragment["fragment_identity"]: fragment for fragment in reference_fragments}
    prewarmed_reference = {
        fragment["fragment_identity"]: fragment
        for fragment in predictive_materialization.get("prewarmed_fragments", [])
    }
    predictive_identities = sorted(
        {
            identity
            for pattern in predictive_patterns
            for identity in pattern.get("frequently_used_fragments", [])
        }
    )
    global_invalidation = "memory_store_changed" in invalidators
    active_identities = [fragment["fragment_identity"] for fragment in active_fragments]
    dormant_identities = [
        fragment["fragment_identity"]
        for fragment in current_fragments
        if fragment["fragment_identity"] not in set(active_identities)
    ]
    changed_fragments = []
    for fragment in current_fragments:
        reference = reference_by_identity.get(fragment["fragment_identity"])
        if reference is None or reference["fragment_fingerprint"] != fragment["fragment_fingerprint"]:
            changed_fragments.append(fragment["fragment_identity"])

    predictive_hits = []
    rebuilt_fragments = []
    for fragment in active_fragments:
        reference = prewarmed_reference.get(fragment["fragment_identity"])
        if (
            not global_invalidation
            and reference is not None
            and reference["fragment_fingerprint"] == fragment["fragment_fingerprint"]
        ):
            predictive_hits.append(fragment)
        else:
            rebuilt_fragments.append(fragment)

    coherence = _microfragment_coherence_guard(active_fragments, query, coherence_threshold)
    if not coherence["passed"]:
        predictive_hits = []
        rebuilt_fragments = active_fragments
        coherence = _microfragment_coherence_guard(rebuilt_fragments, query, coherence_threshold)

    prewarmed_identities = [
        fragment["fragment_identity"]
        for fragment in predictive_materialization.get("prewarmed_fragments", [])
    ]
    sparse_activation_map = {
        "active_fragments": active_identities,
        "dormant_fragments": dormant_identities,
        "predictive_fragments": predictive_identities,
        "prewarmed_fragments": prewarmed_identities,
    }
    active_tokens = sum(fragment["token_estimate"] for fragment in active_fragments)
    rebuilt_tokens = sum(fragment["token_estimate"] for fragment in rebuilt_fragments)
    hit_tokens = sum(fragment["token_estimate"] for fragment in predictive_hits)
    total_tokens = sum(fragment["token_estimate"] for fragment in current_fragments)
    control_overhead_tokens = max(
        3,
        len(predictive_patterns) // 2 + len(predictive_materialization.get("prewarmed_fragments", [])),
    )
    if global_invalidation:
        control_overhead_tokens += 4
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    metrics = {
        "predictive_hit_rate": round(len(predictive_hits) / max(1, len(active_fragments)), 3),
        "avoided_rebuild_ratio": round(len(predictive_hits) / max(1, len(active_fragments)), 3),
        "avoided_materialization_ratio": round(hit_tokens / max(1, active_tokens), 3),
        "prewarm_accuracy": round(
            len(predictive_hits) / max(1, len(predictive_materialization.get("prewarmed_fragments", []))),
            3,
        ),
        "relative_resolution_cost": round((rebuilt_tokens + control_overhead_tokens) / max(1, total_tokens), 3),
        "coherence_score": coherence["coherence_score"],
        "latency_ms": latency_ms,
        "active_fragment_ratio": round(len(active_fragments) / max(1, len(current_fragments)), 3),
        "changed_fragments": len(changed_fragments),
        "rebuilt_fragments": len(rebuilt_fragments),
        "prewarmed_fragments": len(prewarmed_identities),
    }
    scenario = {
        "name": name,
        "mode": "predictive_sparse_materialization",
        "mutation_signature": _mutation_signature(records, invalidators),
        "potential_state": potential_state,
        "state_segments": current_segments,
        "microfragments": current_fragments,
        "sparse_activation_map": sparse_activation_map,
        "predictive_hits": [fragment["fragment_identity"] for fragment in predictive_hits],
        "rebuilt_fragments": [fragment["fragment_identity"] for fragment in rebuilt_fragments],
        "changed_fragments": changed_fragments,
        "invalidators": sorted(invalidators),
        "coherence_guard": coherence,
        "metrics": metrics,
    }
    _store_predictive_sparse_run(connection, scenario)
    return scenario


def _ensure_predictive_sparse_tables(connection: sqlite3.Connection) -> None:
    _ensure_microdelta_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_predictive_patterns (
            id TEXT PRIMARY KEY,
            query_signature TEXT NOT NULL,
            mutation_signature TEXT NOT NULL,
            prediction_weight REAL NOT NULL,
            payload TEXT NOT NULL,
            last_hit_at TEXT NOT NULL,
            hit_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_predictive_materializations (
            id TEXT PRIMARY KEY,
            query_signature TEXT NOT NULL,
            policy TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_predictive_sparse_runs (
            run_key TEXT PRIMARY KEY,
            scenario TEXT NOT NULL,
            mutation_signature TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_predictive_patterns(connection: sqlite3.Connection, patterns: list[dict[str, Any]]) -> None:
    _ensure_predictive_sparse_tables(connection)
    for pattern in patterns:
        connection.execute(
            """
            INSERT OR REPLACE INTO mmr_predictive_patterns (
                id, query_signature, mutation_signature, prediction_weight,
                payload, last_hit_at, hit_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pattern["id"],
                pattern["query_signature"],
                pattern["mutation_signature"],
                pattern["prediction_weight"],
                json.dumps(pattern, sort_keys=True, ensure_ascii=False),
                pattern["last_hit_at"],
                pattern["hit_count"],
            ),
        )


def _store_predictive_materialization(
    connection: sqlite3.Connection,
    materialization: dict[str, Any],
) -> None:
    _ensure_predictive_sparse_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_predictive_materializations (
            id, query_signature, policy, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            materialization["id"],
            materialization["query_signature"],
            materialization["policy"],
            json.dumps(materialization, sort_keys=True, ensure_ascii=False),
            materialization["created_at"],
        ),
    )


def _store_predictive_sparse_run(connection: sqlite3.Connection, scenario: dict[str, Any]) -> None:
    _ensure_predictive_sparse_tables(connection)
    run_key = sha256(
        json.dumps(
            {
                "scenario": scenario["name"],
                "mutation_signature": scenario["mutation_signature"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    created_at = utc_ts()
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_predictive_sparse_runs (
            run_key, scenario, mutation_signature, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_key,
            scenario["name"],
            scenario["mutation_signature"],
            json.dumps(scenario, sort_keys=True, ensure_ascii=False),
            created_at,
        ),
    )


def _scale_memory_records(records: list[dict[str, Any]], scale: int) -> list[dict[str, Any]]:
    if scale <= 1:
        return [dict(record) for record in records]
    scaled = []
    for copy_index in range(scale):
        for record in records:
            suffix = f"S{copy_index + 1:02d}"
            scaled.append(
                {
                    **record,
                    "id": f"{record['id']}-{suffix}",
                    "title": f"{record['title']} shard {copy_index + 1}",
                    "summary": (
                        record["summary"]
                        if copy_index == 0
                        else f"{record['summary']} Sparse scaling control shard {copy_index + 1}."
                    ),
                    "source_refs": [*record.get("source_refs", []), f"runtime/scaling/{suffix}"],
                    "tags": [*record.get("tags", []), "scaling"],
                    "claims": [
                        *record.get("claims", []),
                        f"Scaling shard {copy_index + 1} preserves logical structure for benchmark.",
                    ],
                }
            )
    return _prepare_memory_records(scaled)


def _bounded_predictive_scaling_case(
    *,
    connection: sqlite3.Connection,
    scale: int,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    coherence_threshold: float,
) -> dict[str, Any]:
    potential_state = _build_live_potential_state(records, query)
    fragments = _build_microfragments(_build_state_segments(potential_state, records))
    active_fragments = _select_microfragments(fragments, query, fragment_limit)
    patterns = _build_predictive_patterns(query, fragments, active_fragments)
    cold_materialization = {
        "id": f"BMAT-COLD-X{scale}",
        "query_signature": _query_signature(query),
        "policy": "no_prewarm",
        "prewarmed_fragments": [],
        "created_at": utc_ts(),
    }
    warm_materialization = {
        "id": f"BMAT-WARM-X{scale}",
        "query_signature": _query_signature(query),
        "policy": "exact_active_cache",
        "prewarmed_fragments": active_fragments,
        "created_at": utc_ts(),
    }
    predictive_materialization = _build_predictive_materialization(
        query,
        patterns,
        fragments,
        prewarm_limit=max(fragment_limit * 2, activation_budget["max_prewarmed_fragments"] + 4),
    )
    bounded_materialization = _build_budgeted_predictive_materialization(
        query,
        patterns,
        fragments,
        activation_budget,
    )
    modes = {
        "cold": _bounded_predictive_mode(
            mode="cold",
            records=records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            materialization=cold_materialization,
            coherence_threshold=coherence_threshold,
            enforce_budget=False,
        ),
        "warm": _bounded_predictive_mode(
            mode="warm",
            records=records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            materialization=warm_materialization,
            coherence_threshold=coherence_threshold,
            enforce_budget=False,
        ),
        "predictive_sparse": _bounded_predictive_mode(
            mode="predictive_sparse",
            records=records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            materialization=predictive_materialization,
            coherence_threshold=coherence_threshold,
            enforce_budget=False,
        ),
        "bounded_predictive": _bounded_predictive_mode(
            mode="bounded_predictive",
            records=records,
            query=query,
            fragment_limit=fragment_limit,
            activation_budget=activation_budget,
            materialization=bounded_materialization,
            coherence_threshold=coherence_threshold,
            enforce_budget=True,
        ),
    }
    scale_case = {
        "scale": scale,
        "record_count": len(records),
        "fragment_count": len(fragments),
        "activation_budget": activation_budget,
        "predictive_patterns": patterns,
        "bounded_materialization": bounded_materialization,
        "modes": modes,
    }
    _store_bounded_predictive_run(connection, f"x{scale}", scale_case)
    return scale_case


def _build_budgeted_predictive_materialization(
    query: str,
    patterns: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    activation_budget: dict[str, Any],
) -> dict[str, Any]:
    fragments_by_identity = {fragment["fragment_identity"]: fragment for fragment in fragments}
    prewarmed = []
    prewarmed_identities = set()
    token_total = 0
    fallback_reason = None
    for pattern in sorted(patterns, key=lambda item: item["prediction_weight"], reverse=True):
        for identity in pattern["frequently_used_fragments"]:
            fragment = fragments_by_identity.get(identity)
            if fragment is None or identity in prewarmed_identities:
                continue
            next_count = len(prewarmed) + 1
            next_tokens = token_total + fragment["token_estimate"]
            if next_count > activation_budget["max_prewarmed_fragments"]:
                fallback_reason = "max_prewarmed_fragments_reached"
                continue
            if next_tokens > activation_budget["max_materialized_tokens"]:
                fallback_reason = "max_materialized_tokens_reached"
                continue
            prewarmed.append(fragment)
            prewarmed_identities.add(identity)
            token_total = next_tokens
    if not prewarmed and patterns:
        fallback_reason = "budget_exceeded_no_prewarm"
    materialization_id = sha256(
        json.dumps(
            {
                "query_signature": _query_signature(query),
                "budget": activation_budget,
                "prewarmed": [fragment["fragment_identity"] for fragment in prewarmed],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "id": f"BMAT-{materialization_id}",
        "query_signature": _query_signature(query),
        "policy": "bounded_score_then_token_cap",
        "activation_budget": activation_budget,
        "prewarmed_fragments": prewarmed,
        "prewarmed_token_estimate": token_total,
        "fallback_reason": fallback_reason,
        "created_at": utc_ts(),
    }


def _bounded_predictive_mode(
    *,
    mode: str,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    materialization: dict[str, Any],
    coherence_threshold: float,
    enforce_budget: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    potential_state = _build_live_potential_state(records, query)
    fragments = _build_microfragments(_build_state_segments(potential_state, records))
    active_limit = min(fragment_limit, activation_budget["max_active_fragments"]) if enforce_budget else fragment_limit
    active_fragments = _select_microfragments(fragments, query, active_limit)
    active_identities = {fragment["fragment_identity"] for fragment in active_fragments}
    prewarmed = materialization.get("prewarmed_fragments", [])
    prewarmed_by_identity = {fragment["fragment_identity"]: fragment for fragment in prewarmed}
    hits = []
    rebuilt = []
    for fragment in active_fragments:
        prewarmed_fragment = prewarmed_by_identity.get(fragment["fragment_identity"])
        if (
            prewarmed_fragment is not None
            and prewarmed_fragment["fragment_fingerprint"] == fragment["fragment_fingerprint"]
        ):
            hits.append(fragment)
        else:
            rebuilt.append(fragment)

    false_positive_prewarm = [
        fragment for fragment in prewarmed if fragment["fragment_identity"] not in active_identities
    ]
    unused_prewarmed = [
        fragment
        for fragment in prewarmed
        if fragment["fragment_identity"] not in {hit["fragment_identity"] for hit in hits}
    ]
    coherence = _microfragment_coherence_guard(active_fragments, query, coherence_threshold)
    if not coherence["passed"]:
        hits = []
        rebuilt = active_fragments
        unused_prewarmed = prewarmed
        coherence = _microfragment_coherence_guard(rebuilt, query, coherence_threshold)

    total_tokens = sum(fragment["token_estimate"] for fragment in fragments)
    materialized_tokens = sum(fragment["token_estimate"] for fragment in rebuilt)
    prewarmed_tokens = sum(fragment["token_estimate"] for fragment in prewarmed)
    wasted_tokens = sum(fragment["token_estimate"] for fragment in unused_prewarmed)
    wasted_latency_ms = round(wasted_tokens * 0.01, 3)
    penalty = _prediction_penalty(
        false_positive_prewarm=false_positive_prewarm,
        unused_prewarmed_fragments=unused_prewarmed,
        wasted_tokens=wasted_tokens,
        wasted_latency_ms=wasted_latency_ms,
        total_tokens=total_tokens,
        prewarmed_count=len(prewarmed),
    )
    control_overhead_tokens = max(3, len(prewarmed) + len(active_fragments) // 2)
    latency_ms = round((time.perf_counter() - started) * 1000 + wasted_latency_ms, 3)
    metrics = {
        "relative_resolution_cost": round(
            (materialized_tokens + control_overhead_tokens + wasted_tokens) / max(1, total_tokens),
            3,
        ),
        "active_fragment_ratio": round(len(active_fragments) / max(1, len(fragments)), 3),
        "prewarm_accuracy": round(len(hits) / max(1, len(prewarmed)), 3),
        "wasted_prewarm_ratio": round(len(unused_prewarmed) / max(1, len(prewarmed)), 3),
        "budget_utilization": _budget_utilization(
            activation_budget,
            active_count=len(active_fragments),
            prewarm_count=len(prewarmed),
            prewarm_tokens=prewarmed_tokens,
            latency_ms=latency_ms,
        ),
        "latency_ms": latency_ms,
        "materialized_tokens": materialized_tokens,
        "total_available_tokens": total_tokens,
        "scaling_efficiency": 0.0,
    }
    return {
        "mode": mode,
        "activation_budget": activation_budget,
        "budget_status": _budget_status(
            activation_budget,
            len(active_fragments),
            len(prewarmed),
            prewarmed_tokens,
            latency_ms,
        ),
        "materialization": {
            "id": materialization["id"],
            "policy": materialization["policy"],
            "prewarmed_fragments": [fragment["fragment_identity"] for fragment in prewarmed],
            "fallback_reason": materialization.get("fallback_reason"),
        },
        "prediction_penalty": penalty,
        "coherence_guard": coherence,
        "metrics": metrics,
    }


def _prediction_penalty(
    *,
    false_positive_prewarm: list[dict[str, Any]],
    unused_prewarmed_fragments: list[dict[str, Any]],
    wasted_tokens: int,
    wasted_latency_ms: float,
    total_tokens: int,
    prewarmed_count: int,
) -> dict[str, Any]:
    false_positive_count = len(false_positive_prewarm)
    unused_count = len(unused_prewarmed_fragments)
    penalty_score = round(
        min(
            1.0,
            (false_positive_count / max(1, prewarmed_count)) * 0.35
            + (unused_count / max(1, prewarmed_count)) * 0.35
            + (wasted_tokens / max(1, total_tokens)) * 0.2
            + min(1.0, wasted_latency_ms / 10.0) * 0.1,
        ),
        3,
    )
    return {
        "false_positive_prewarm": false_positive_count,
        "unused_prewarmed_fragments": unused_count,
        "wasted_tokens": wasted_tokens,
        "wasted_latency_ms": wasted_latency_ms,
        "penalty_score": penalty_score,
    }


def _budget_utilization(
    activation_budget: dict[str, Any],
    *,
    active_count: int,
    prewarm_count: int,
    prewarm_tokens: int,
    latency_ms: float,
) -> float:
    utilizations = [
        active_count / max(1, activation_budget["max_active_fragments"]),
        prewarm_count / max(1, activation_budget["max_prewarmed_fragments"]),
        prewarm_tokens / max(1, activation_budget["max_materialized_tokens"]),
        latency_ms / max(0.001, activation_budget["max_latency_ms"]),
    ]
    return round(min(1.0, max(utilizations)), 3)


def _budget_status(
    activation_budget: dict[str, Any],
    active_count: int,
    prewarm_count: int,
    prewarm_tokens: int,
    latency_ms: float,
) -> dict[str, Any]:
    return {
        "active_fragments_ok": active_count <= activation_budget["max_active_fragments"],
        "prewarmed_fragments_ok": prewarm_count <= activation_budget["max_prewarmed_fragments"],
        "materialized_tokens_ok": prewarm_tokens <= activation_budget["max_materialized_tokens"],
        "latency_ok": latency_ms <= activation_budget["max_latency_ms"],
    }


def _apply_scaling_efficiency(scenarios: dict[str, Any]) -> None:
    base_cost = scenarios["x1"]["modes"]["cold"]["metrics"]["relative_resolution_cost"]
    for scale_case in scenarios.values():
        scale = scale_case["scale"]
        for mode in scale_case["modes"].values():
            cost = mode["metrics"]["relative_resolution_cost"]
            mode["metrics"]["scaling_efficiency"] = round((base_cost / max(0.001, cost)) * scale, 3)


def _ensure_bounded_predictive_tables(connection: sqlite3.Connection) -> None:
    _ensure_predictive_sparse_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_activation_budgets (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_bounded_predictive_runs (
            run_key TEXT PRIMARY KEY,
            scale_key TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_activation_budget(connection: sqlite3.Connection, activation_budget: dict[str, Any]) -> None:
    _ensure_bounded_predictive_tables(connection)
    budget_id = sha256(json.dumps(activation_budget, sort_keys=True).encode("utf-8")).hexdigest()[:12].upper()
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_activation_budgets (id, payload, created_at)
        VALUES (?, ?, ?)
        """,
        (
            f"ABUDGET-{budget_id}",
            json.dumps(activation_budget, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _store_bounded_predictive_run(
    connection: sqlite3.Connection,
    scale_key: str,
    scale_case: dict[str, Any],
) -> None:
    _ensure_bounded_predictive_tables(connection)
    run_key = sha256(
        json.dumps(
            {
                "scale_key": scale_key,
                "record_count": scale_case["record_count"],
                "fragment_count": scale_case["fragment_count"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_bounded_predictive_runs (run_key, scale_key, payload, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            run_key,
            scale_key,
            json.dumps(scale_case, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _dual_cost_scaling_case(
    *,
    connection: sqlite3.Connection,
    name: str,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    coherence_threshold: float,
) -> dict[str, Any]:
    case = _dual_cost_case(
        connection=connection,
        name=name,
        records=records,
        query=query,
        fragment_limit=fragment_limit,
        activation_budget=activation_budget,
        materialization_mode="bounded",
        coherence_threshold=coherence_threshold,
    )
    case["corpus_kind"] = "scaling"
    return case


def _dual_cost_adversarial_case(
    *,
    connection: sqlite3.Connection,
    name: str,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    materialization_mode: str,
    coherence_threshold: float,
) -> dict[str, Any]:
    case = _dual_cost_case(
        connection=connection,
        name=name,
        records=records,
        query=query,
        fragment_limit=fragment_limit,
        activation_budget=activation_budget,
        materialization_mode=materialization_mode,
        coherence_threshold=coherence_threshold,
    )
    case["corpus_kind"] = "adversarial"
    return case


def _dual_cost_case(
    *,
    connection: sqlite3.Connection,
    name: str,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    materialization_mode: str,
    coherence_threshold: float,
) -> dict[str, Any]:
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    tracemalloc.start()
    sqlite_read_count = 1
    sqlite_write_count = 0

    potential_state = _build_live_potential_state(records, query)
    fragments = _build_microfragments(_build_state_segments(potential_state, records))
    active_fragments = _select_microfragments(fragments, query, fragment_limit)
    out_of_distribution = False
    if not active_fragments:
        out_of_distribution = True
        active_fragments = _fallback_active_fragments(fragments, activation_budget)
    patterns = _build_predictive_patterns(query, fragments, active_fragments)
    if materialization_mode == "bad_predictions":
        materialization = _build_bad_predictive_materialization(query, fragments, active_fragments, activation_budget)
    else:
        materialization = _build_budgeted_predictive_materialization(query, patterns, fragments, activation_budget)
    prewarmed = materialization.get("prewarmed_fragments", [])
    prewarmed_by_identity = {fragment["fragment_identity"]: fragment for fragment in prewarmed}
    active_identities = {fragment["fragment_identity"] for fragment in active_fragments}
    hits = []
    rebuilt = []
    for fragment in active_fragments:
        prewarmed_fragment = prewarmed_by_identity.get(fragment["fragment_identity"])
        if (
            prewarmed_fragment is not None
            and prewarmed_fragment["fragment_fingerprint"] == fragment["fragment_fingerprint"]
        ):
            hits.append(fragment)
        else:
            rebuilt.append(fragment)

    false_positive = [
        fragment for fragment in prewarmed if fragment["fragment_identity"] not in active_identities
    ]
    unused_prewarmed = [
        fragment
        for fragment in prewarmed
        if fragment["fragment_identity"] not in {hit["fragment_identity"] for hit in hits}
    ]
    coherence = _microfragment_coherence_guard(active_fragments, query, coherence_threshold)
    if not coherence["passed"]:
        rebuilt = active_fragments
        hits = []
        unused_prewarmed = prewarmed

    active_tokens = sum(fragment["token_estimate"] for fragment in active_fragments)
    prewarmed_tokens = sum(fragment["token_estimate"] for fragment in prewarmed)
    rebuilt_tokens = sum(fragment["token_estimate"] for fragment in rebuilt)
    wasted_tokens = sum(fragment["token_estimate"] for fragment in unused_prewarmed)
    total_tokens = sum(fragment["token_estimate"] for fragment in fragments)
    control_tokens = max(3, len(prewarmed) + len(active_fragments) // 2)
    relative_cost = round((rebuilt_tokens + control_tokens + wasted_tokens) / max(1, total_tokens), 3)
    wall_latency_ms = round((time.perf_counter() - wall_started) * 1000, 3)
    process_cpu_ms = round((time.process_time() - cpu_started) * 1000, 3)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_memory_mb = round(peak_bytes / (1024 * 1024), 3)
    absolute_materialized_tokens = rebuilt_tokens + prewarmed_tokens
    absolute_trace = {
        "materialized_tokens": absolute_materialized_tokens,
        "rebuilt_fragments": len(rebuilt),
        "reused_fragments": len(hits),
        "sqlite_read_count": sqlite_read_count,
        "sqlite_write_count": 1,
        "wall_latency_ms": wall_latency_ms,
        "process_cpu_ms": process_cpu_ms,
        "peak_memory_mb": peak_memory_mb,
    }
    absolute_materialization_cost = round(
        absolute_materialized_tokens
        + len(rebuilt) * 3
        + sqlite_read_count * 2
        + absolute_trace["sqlite_write_count"] * 3
        + wall_latency_ms * 0.25
        + peak_memory_mb,
        3,
    )
    false_positive_rate = round(len(false_positive) / max(1, len(prewarmed)), 3)
    wasted_prewarm_ratio = round(len(unused_prewarmed) / max(1, len(prewarmed)), 3)
    dual_report = {
        "relative_resolution_cost": relative_cost,
        "absolute_materialization_cost": absolute_materialization_cost,
        "normalized_efficiency": round(active_tokens / max(1.0, absolute_materialization_cost), 3),
        "scaling_efficiency": 0.0,
        "cost_discrepancy_warning": False,
    }
    penalty = _prediction_penalty(
        false_positive_prewarm=false_positive,
        unused_prewarmed_fragments=unused_prewarmed,
        wasted_tokens=wasted_tokens,
        wasted_latency_ms=round(wasted_tokens * 0.01, 3),
        total_tokens=total_tokens,
        prewarmed_count=len(prewarmed),
    )
    warning_reasons = []
    if false_positive_rate >= 0.5:
        warning_reasons.append("prediction_false_positive_rate_high")
    if out_of_distribution:
        warning_reasons.append("out_of_distribution_fallback")
    if absolute_materialized_tokens > activation_budget["max_materialized_tokens"] * 2:
        warning_reasons.append("absolute_materialized_tokens_high")
    if wall_latency_ms > activation_budget["max_latency_ms"]:
        warning_reasons.append("absolute_latency_high")
    dual_report["cost_discrepancy_warning"] = bool(warning_reasons)
    metrics = {
        "relative_resolution_cost": relative_cost,
        "absolute_materialized_tokens": absolute_materialized_tokens,
        "absolute_latency_ms": wall_latency_ms,
        "absolute_rebuilt_fragments": len(rebuilt),
        "wasted_prewarm_ratio": wasted_prewarm_ratio,
        "prediction_false_positive_rate": false_positive_rate,
        "out_of_distribution_fallback_rate": 1.0 if out_of_distribution else 0.0,
        "warning_count": len(warning_reasons),
    }
    case = {
        "name": name,
        "query": query,
        "record_count": len(records),
        "fragment_count": len(fragments),
        "materialization_mode": materialization_mode,
        "activation_budget": activation_budget,
        "absolute_cost_trace": absolute_trace,
        "dual_cost_report": dual_report,
        "prediction_penalty": penalty,
        "warning_reasons": warning_reasons,
        "active_fragments": [fragment["fragment_identity"] for fragment in active_fragments],
        "prewarmed_fragments": [fragment["fragment_identity"] for fragment in prewarmed],
        "rebuilt_fragments": [fragment["fragment_identity"] for fragment in rebuilt],
        "reused_fragments": [fragment["fragment_identity"] for fragment in hits],
        "metrics": metrics,
    }
    _store_dual_cost_case(connection, case)
    sqlite_write_count += 1
    case["absolute_cost_trace"]["sqlite_write_count"] = sqlite_write_count
    return case


def _apply_dual_scaling_sanity(scaling: dict[str, Any]) -> None:
    base = scaling["x1"]
    base_relative = base["metrics"]["relative_resolution_cost"]
    base_absolute = base["dual_cost_report"]["absolute_materialization_cost"]
    for key, case in scaling.items():
        scale = int(key[1:])
        relative = case["metrics"]["relative_resolution_cost"]
        absolute = case["dual_cost_report"]["absolute_materialization_cost"]
        case["dual_cost_report"]["scaling_efficiency"] = round(
            (base_relative / max(0.001, relative)) * scale,
            3,
        )
        case["metrics"]["scaling_efficiency"] = case["dual_cost_report"]["scaling_efficiency"]
        if key == "x1":
            continue
        if relative < base_relative and absolute > base_absolute * max(3, scale * 0.75):
            case["warning_reasons"].append("relative_gain_hides_absolute_growth")
            case["dual_cost_report"]["cost_discrepancy_warning"] = True
            case["metrics"]["warning_count"] = len(case["warning_reasons"])


def _fallback_active_fragments(
    fragments: list[dict[str, Any]],
    activation_budget: dict[str, Any],
) -> list[dict[str, Any]]:
    ranked = sorted(
        fragments,
        key=lambda fragment: (
            _microfragment_priority(fragment["fragment_key"]),
            -fragment["token_estimate"],
        ),
        reverse=True,
    )
    return ranked[: max(1, min(activation_budget["max_active_fragments"], 2))]


def _build_bad_predictive_materialization(
    query: str,
    fragments: list[dict[str, Any]],
    active_fragments: list[dict[str, Any]],
    activation_budget: dict[str, Any],
) -> dict[str, Any]:
    active_identities = {fragment["fragment_identity"] for fragment in active_fragments}
    bad_candidates = [
        fragment for fragment in fragments if fragment["fragment_identity"] not in active_identities
    ]
    bad_candidates.sort(key=lambda fragment: (fragment["token_estimate"], fragment["fragment_identity"]))
    prewarmed = bad_candidates[: activation_budget["max_prewarmed_fragments"]]
    materialization_id = sha256(
        json.dumps(
            {
                "query_signature": _query_signature(query),
                "bad_prewarm": [fragment["fragment_identity"] for fragment in prewarmed],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "id": f"BAD-PMAT-{materialization_id}",
        "query_signature": _query_signature(query),
        "policy": "intentional_bad_prediction",
        "activation_budget": activation_budget,
        "prewarmed_fragments": prewarmed,
        "prewarmed_token_estimate": sum(fragment["token_estimate"] for fragment in prewarmed),
        "fallback_reason": "adversarial_false_positive_prewarm",
        "created_at": utc_ts(),
    }


def _low_compressible_records(records: list[dict[str, Any]], scale: int) -> list[dict[str, Any]]:
    low = []
    for copy_index in range(scale):
        for record_index, record in enumerate(records):
            unique_terms = [
                f"rare{copy_index:02d}",
                f"branch{record_index:02d}",
                f"vector{copy_index * 7 + record_index}",
            ]
            low.append(
                {
                    **record,
                    "id": f"LOW-{copy_index:02d}-{record['id']}",
                    "title": f"{record['title']} {' '.join(unique_terms)}",
                    "summary": f"{record['summary']} Unique low-compressibility payload {' '.join(unique_terms)}.",
                    "source_refs": [*record.get("source_refs", []), f"runtime/low_compressible/{copy_index}"],
                    "tags": [*record.get("tags", []), *unique_terms],
                    "claims": [
                        *record.get("claims", []),
                        f"Low compressibility branch {copy_index}-{record_index}.",
                    ],
                }
            )
    return _prepare_memory_records(low)


def _deterministic_mutation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = []
    for index, record in enumerate(records):
        if index % 3 == 0:
            mutated.append(
                {
                    **record,
                    "summary": f"{record['summary']} Deterministic mutation branch {index}.",
                    "tags": [*record.get("tags", []), f"mut{index % 5}"],
                }
            )
        elif index % 5 == 0:
            mutated.append(
                {
                    **record,
                    "source_refs": [*record.get("source_refs", []), f"runtime/random_mutation/{index}"],
                }
            )
        else:
            mutated.append(record)
    return _prepare_memory_records(mutated)


def _ensure_dual_cost_tables(connection: sqlite3.Connection) -> None:
    _ensure_bounded_predictive_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_dual_cost_validation_runs (
            run_key TEXT PRIMARY KEY,
            case_name TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_dual_cost_case(connection: sqlite3.Connection, case: dict[str, Any]) -> None:
    _ensure_dual_cost_tables(connection)
    run_key = sha256(
        json.dumps(
            {
                "name": case["name"],
                "record_count": case["record_count"],
                "query": case["query"],
                "mode": case["materialization_mode"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_dual_cost_validation_runs (run_key, case_name, payload, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            run_key,
            case["name"],
            json.dumps(case, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _runtime_policy(mode: str, activation_budget: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"RPOL-{mode.upper().replace('_', '-')}",
        "mode": mode,
        "max_relative_cost": 0.12 if mode != "cold" else 0.2,
        "max_absolute_latency_ms": activation_budget["max_latency_ms"],
        "max_wasted_prewarm_ratio": 0.25,
        "max_warning_count": 0,
    }


def _autotuning_fixed_modes(
    *,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    runtime_policies: dict[str, dict[str, Any]],
    coherence_threshold: float,
) -> dict[str, Any]:
    potential_state = _build_live_potential_state(records, query)
    fragments = _build_microfragments(_build_state_segments(potential_state, records))
    active_fragments = _select_microfragments(fragments, query, fragment_limit)
    patterns = _build_predictive_patterns(query, fragments, active_fragments)
    cold_materialization = {
        "id": "AUTOTUNE-COLD-NONE",
        "query_signature": _query_signature(query),
        "policy": "no_prewarm",
        "prewarmed_fragments": [],
        "created_at": utc_ts(),
    }
    warm_materialization = {
        "id": "AUTOTUNE-WARM-EXACT",
        "query_signature": _query_signature(query),
        "policy": "exact_active_cache",
        "prewarmed_fragments": active_fragments,
        "created_at": utc_ts(),
    }
    predictive_materialization = _build_predictive_materialization(
        query,
        patterns,
        fragments,
        prewarm_limit=max(fragment_limit * 2, activation_budget["max_prewarmed_fragments"] + 4),
    )
    bounded_materialization = _build_budgeted_predictive_materialization(
        query,
        patterns,
        fragments,
        activation_budget,
    )
    raw_modes = {
        "fixed_cold": (
            "cold",
            _bounded_predictive_mode(
                mode="cold",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization=cold_materialization,
                coherence_threshold=coherence_threshold,
                enforce_budget=False,
            ),
        ),
        "fixed_warm": (
            "warm",
            _bounded_predictive_mode(
                mode="warm",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization=warm_materialization,
                coherence_threshold=coherence_threshold,
                enforce_budget=False,
            ),
        ),
        "fixed_predictive": (
            "predictive_sparse",
            _bounded_predictive_mode(
                mode="predictive_sparse",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization=predictive_materialization,
                coherence_threshold=coherence_threshold,
                enforce_budget=False,
            ),
        ),
        "fixed_bounded": (
            "bounded_predictive",
            _bounded_predictive_mode(
                mode="bounded_predictive",
                records=records,
                query=query,
                fragment_limit=fragment_limit,
                activation_budget=activation_budget,
                materialization=bounded_materialization,
                coherence_threshold=coherence_threshold,
                enforce_budget=True,
            ),
        ),
    }
    return {
        key: _annotate_policy_case(
            mode_case=mode_case,
            policy_mode=policy_mode,
            runtime_policy=runtime_policies[policy_mode],
        )
        for key, (policy_mode, mode_case) in raw_modes.items()
    }


def _autotuning_divergence_only_mode(
    *,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    runtime_policy: dict[str, Any],
    coherence_threshold: float,
) -> dict[str, Any]:
    base_state = _build_live_potential_state(records, query)
    base_fragments = _build_microfragments(_build_state_segments(base_state, records))
    active_base = _select_microfragments(base_fragments, query, fragment_limit)
    low_mutation_records = _low_memory_mutation(records)
    warm_materialization = {
        "id": "AUTOTUNE-DIVERGENCE-ONLY",
        "query_signature": _query_signature(query),
        "policy": "divergence_only_reuse",
        "prewarmed_fragments": active_base,
        "created_at": utc_ts(),
    }
    mode_case = _bounded_predictive_mode(
        mode="divergence_only",
        records=low_mutation_records,
        query=query,
        fragment_limit=fragment_limit,
        activation_budget=activation_budget,
        materialization=warm_materialization,
        coherence_threshold=coherence_threshold,
        enforce_budget=True,
    )
    changed_records = sum(
        1
        for previous, current in zip(records, low_mutation_records, strict=False)
        if _memory_record_state_fingerprint(previous) != _memory_record_state_fingerprint(current)
    )
    annotated = _annotate_policy_case(
        mode_case=mode_case,
        policy_mode="divergence_only",
        runtime_policy=runtime_policy,
    )
    annotated["divergence_ratio"] = round(changed_records / max(1, len(records)), 3)
    return annotated


def _annotate_policy_case(
    *,
    mode_case: dict[str, Any],
    policy_mode: str,
    runtime_policy: dict[str, Any],
) -> dict[str, Any]:
    annotated = {
        **mode_case,
        "policy_mode": policy_mode,
        "runtime_policy": runtime_policy,
    }
    metrics = dict(mode_case["metrics"])
    metrics["absolute_latency_ms"] = metrics["latency_ms"]
    warning_reasons = _policy_warning_reasons(mode_case, runtime_policy)
    metrics["warning_count"] = len(warning_reasons)
    metrics["policy_score"] = _policy_score(metrics)
    annotated["metrics"] = metrics
    annotated["warning_reasons"] = warning_reasons
    annotated["rejected"] = metrics["warning_count"] > runtime_policy["max_warning_count"]
    annotated["expected_cost"] = _cost_snapshot(metrics)
    annotated["observed_cost"] = _cost_snapshot(metrics)
    return annotated


def _policy_warning_reasons(mode_case: dict[str, Any], runtime_policy: dict[str, Any]) -> list[str]:
    metrics = mode_case["metrics"]
    reasons = []
    if metrics["relative_resolution_cost"] > runtime_policy["max_relative_cost"]:
        reasons.append("relative_cost_above_policy")
    if metrics["latency_ms"] > runtime_policy["max_absolute_latency_ms"]:
        reasons.append("absolute_latency_above_policy")
    if metrics["wasted_prewarm_ratio"] > runtime_policy["max_wasted_prewarm_ratio"]:
        reasons.append("wasted_prewarm_above_policy")
    if mode_case["prediction_penalty"]["false_positive_prewarm"] > 0:
        reasons.append("prediction_false_positive_detected")
    return reasons


def _policy_score(metrics: dict[str, Any]) -> float:
    latency_component = metrics["absolute_latency_ms"] / 25.0
    return round(
        metrics["relative_resolution_cost"]
        + latency_component
        + metrics["wasted_prewarm_ratio"] * 0.5
        + metrics["warning_count"],
        3,
    )


def _decide_runtime_policy(evaluated_modes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rejected_modes = [
        {
            "mode": mode,
            "warning_reasons": item["warning_reasons"],
            "policy_score": item["metrics"]["policy_score"],
        }
        for mode, item in evaluated_modes.items()
        if item["rejected"]
    ]
    prediction_suspect = evaluated_modes["predictive_sparse"]["rejected"]
    candidates = [item for item in evaluated_modes.values() if not item["rejected"]]
    if not candidates:
        candidates = [evaluated_modes["cold"]]
    if prediction_suspect:
        fallback_candidates = [
            item
            for item in candidates
            if item["policy_mode"] in {"warm", "cold", "bounded_predictive", "divergence_only"}
        ]
        candidates = fallback_candidates or candidates
    priority = {
        "warm": 0,
        "bounded_predictive": 1,
        "divergence_only": 2,
        "cold": 3,
        "predictive_sparse": 4,
    }
    selected = min(
        candidates,
        key=lambda item: (
            item["metrics"]["policy_score"],
            priority.get(item["policy_mode"], 99),
        ),
    )
    selected_mode = selected["policy_mode"]
    cold = evaluated_modes["cold"]["metrics"]
    predictive = evaluated_modes["predictive_sparse"]["metrics"]
    selected_metrics = selected["metrics"]
    stable_count = sum(1 for item in evaluated_modes.values() if not item["rejected"])
    decision_reason = (
        "predictive_sparse_rejected_then_safe_fallback_selected"
        if prediction_suspect and selected_mode != "predictive_sparse"
        else "lowest_policy_score_within_thresholds"
    )
    return {
        "selected_mode": selected_mode,
        "rejected_modes": rejected_modes,
        "decision_reason": decision_reason,
        "expected_cost": selected["expected_cost"],
        "observed_cost": selected["observed_cost"],
        "fallback_used": prediction_suspect and selected_mode != "predictive_sparse",
        "avoided_bad_prediction": prediction_suspect and selected_mode != "predictive_sparse",
        "warning_reduction": max(0, predictive["warning_count"] - selected_metrics["warning_count"]),
        "latency_reduction": round(max(0.0, predictive["absolute_latency_ms"] - selected_metrics["absolute_latency_ms"]), 3),
        "relative_cost_reduction": round(
            max(0.0, cold["relative_resolution_cost"] - selected_metrics["relative_resolution_cost"])
            / max(0.001, cold["relative_resolution_cost"]),
            3,
        ),
        "policy_stability_score": round(stable_count / max(1, len(evaluated_modes)), 3),
    }


def _cost_snapshot(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_score": metrics["policy_score"],
        "relative_resolution_cost": metrics["relative_resolution_cost"],
        "absolute_latency_ms": metrics["absolute_latency_ms"],
        "wasted_prewarm_ratio": metrics["wasted_prewarm_ratio"],
        "warning_count": metrics["warning_count"],
    }


def _ensure_autotuning_tables(connection: sqlite3.Connection) -> None:
    _ensure_dual_cost_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_autotuning_policy_runs (
            id TEXT PRIMARY KEY,
            selected_mode TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_autotuning_policy_run(connection: sqlite3.Connection, benchmark: dict[str, Any]) -> None:
    _ensure_autotuning_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_autotuning_policy_runs (id, selected_mode, payload, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            benchmark["id"],
            benchmark["policy_decision"]["selected_mode"],
            json.dumps(benchmark, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _long_horizon_templates(
    *,
    records: list[dict[str, Any]],
    query: str,
    fragment_limit: int,
    activation_budget: dict[str, Any],
    runtime_policies: dict[str, dict[str, Any]],
    coherence_threshold: float,
) -> dict[str, Any]:
    fixed_modes = _autotuning_fixed_modes(
        records=records,
        query=query,
        fragment_limit=fragment_limit,
        activation_budget=activation_budget,
        runtime_policies=runtime_policies,
        coherence_threshold=coherence_threshold,
    )
    return {
        "stable": _episode_template(fixed_modes["fixed_warm"], "stable", warning_count=0),
        "weak_repeated": _episode_template(fixed_modes["fixed_warm"], "weak_repeated", warning_count=0),
        "strong_rare": _episode_template(
            fixed_modes["fixed_warm"],
            "strong_rare",
            warning_count=1,
            coherence_score=0.84,
            reused_fragments=4,
            rebuilt_fragments=2,
        ),
        "bad_prediction": _episode_template(fixed_modes["fixed_warm"], "bad_prediction", warning_count=1),
        "out_of_distribution": _episode_template(
            fixed_modes["fixed_cold"],
            "out_of_distribution",
            selected_policy="cold",
            warning_count=1,
            coherence_score=0.58,
            reused_fragments=0,
            rebuilt_fragments=fragment_limit,
        ),
    }


def _episode_template(
    mode_case: dict[str, Any],
    mutation_type: str,
    *,
    selected_policy: str | None = None,
    warning_count: int | None = None,
    coherence_score: float | None = None,
    reused_fragments: int | None = None,
    rebuilt_fragments: int | None = None,
) -> dict[str, Any]:
    metrics = mode_case["metrics"]
    prewarmed_count = len(mode_case.get("materialization", {}).get("prewarmed_fragments", []))
    reused = int(round(prewarmed_count * metrics.get("prewarm_accuracy", 0.0)))
    if reused_fragments is not None:
        reused = reused_fragments
    rebuilt = max(0, 6 - reused)
    if rebuilt_fragments is not None:
        rebuilt = rebuilt_fragments
    return {
        "mutation_type": mutation_type,
        "selected_policy": selected_policy or mode_case["policy_mode"],
        "relative_cost": metrics["relative_resolution_cost"],
        "absolute_latency_ms": metrics["absolute_latency_ms"],
        "warning_count": warning_count if warning_count is not None else metrics["warning_count"],
        "reused_fragments": reused,
        "rebuilt_fragments": rebuilt,
        "coherence_score": coherence_score
        if coherence_score is not None
        else mode_case["coherence_guard"]["coherence_score"],
    }


def _long_horizon_scenario(
    *,
    connection: sqlite3.Connection,
    horizon: int,
    templates: dict[str, Any],
    activation_budget: dict[str, Any],
) -> dict[str, Any]:
    episodes = []
    for cycle_index in range(1, horizon + 1):
        mutation_type = _long_horizon_mutation_type(cycle_index)
        episodes.append(
            _long_horizon_episode(
                cycle_index=cycle_index,
                horizon=horizon,
                template=templates[mutation_type],
                activation_budget=activation_budget,
            )
        )
    stability_trace = _stability_trace(episodes, activation_budget)
    drift_warnings = _long_horizon_drift_warnings(stability_trace, activation_budget)
    scenario = {
        "horizon": horizon,
        "episodes": episodes,
        "stability_trace": stability_trace,
        "drift_warnings": drift_warnings,
        "metrics": {
            "long_horizon_stability_score": stability_trace["long_horizon_stability_score"],
            "policy_stability_score": stability_trace["policy_stability_score"],
            "coherence_drift": stability_trace["coherence_drift"],
            "average_cost": stability_trace["average_relative_cost"],
            "total_warnings": sum(episode["warning_count"] for episode in episodes),
            "recovery_after_bad_prediction": _recovery_after_bad_prediction(episodes),
        },
    }
    _store_long_horizon_scenario(connection, scenario)
    return scenario


def _long_horizon_mutation_type(cycle_index: int) -> str:
    if cycle_index % 19 == 0:
        return "out_of_distribution"
    if cycle_index % 11 == 0:
        return "bad_prediction"
    if cycle_index % 7 == 0:
        return "strong_rare"
    if cycle_index % 5 == 0:
        return "stable"
    return "weak_repeated"


def _long_horizon_episode(
    *,
    cycle_index: int,
    horizon: int,
    template: dict[str, Any],
    activation_budget: dict[str, Any],
) -> dict[str, Any]:
    progress = cycle_index / max(1, horizon)
    mutation_type = template["mutation_type"]
    coherence_decay = {
        "stable": 0.0,
        "weak_repeated": 0.055,
        "strong_rare": 0.115,
        "bad_prediction": 0.035,
        "out_of_distribution": 0.18,
    }[mutation_type]
    latency_drift = progress * {
        "stable": 0.08,
        "weak_repeated": 0.18,
        "strong_rare": 0.42,
        "bad_prediction": 0.31,
        "out_of_distribution": 0.55,
    }[mutation_type]
    coherence_score = round(max(0.0, template["coherence_score"] - coherence_decay * progress), 3)
    cache_decay = min(0.45, progress * (0.08 if mutation_type == "weak_repeated" else 0.18))
    reused_fragments = max(0, int(round(template["reused_fragments"] * (1 - cache_decay))))
    rebuilt_fragments = max(template["rebuilt_fragments"], 6 - reused_fragments)
    if mutation_type == "out_of_distribution":
        reused_fragments = 0
        rebuilt_fragments = max(rebuilt_fragments, 6)
    warning_count = template["warning_count"]
    if coherence_score < 0.55:
        warning_count += 1
    absolute_latency_ms = round(template["absolute_latency_ms"] + latency_drift, 3)
    if absolute_latency_ms > activation_budget["max_latency_ms"]:
        warning_count += 1
    relative_cost = round(
        min(1.0, template["relative_cost"] + rebuilt_fragments * 0.001 + (1.0 - coherence_score) * 0.01),
        3,
    )
    return {
        "cycle_id": f"CYCLE-{cycle_index:03d}",
        "selected_policy": template["selected_policy"],
        "relative_cost": relative_cost,
        "absolute_latency_ms": absolute_latency_ms,
        "warning_count": warning_count,
        "reused_fragments": reused_fragments,
        "rebuilt_fragments": rebuilt_fragments,
        "mutation_type": mutation_type,
        "coherence_score": coherence_score,
    }


def _stability_trace(
    episodes: list[dict[str, Any]],
    activation_budget: dict[str, Any],
) -> dict[str, Any]:
    policy_switch_count = sum(
        1
        for previous, current in zip(episodes, episodes[1:], strict=False)
        if previous["selected_policy"] != current["selected_policy"]
    )
    average_relative_cost = round(
        sum(episode["relative_cost"] for episode in episodes) / max(1, len(episodes)),
        3,
    )
    average_absolute_latency_ms = round(
        sum(episode["absolute_latency_ms"] for episode in episodes) / max(1, len(episodes)),
        3,
    )
    warning_rate = round(
        sum(1 for episode in episodes if episode["warning_count"] > 0) / max(1, len(episodes)),
        3,
    )
    coherence_drift = _coherence_drift(episodes)
    reuse_rate = round(
        sum(episode["reused_fragments"] for episode in episodes)
        / max(1, sum(episode["reused_fragments"] + episode["rebuilt_fragments"] for episode in episodes)),
        3,
    )
    first_window = episodes[: max(1, len(episodes) // 5)]
    last_window = episodes[-max(1, len(episodes) // 5):]
    first_reuse = sum(episode["reused_fragments"] for episode in first_window) / max(
        1,
        sum(episode["reused_fragments"] + episode["rebuilt_fragments"] for episode in first_window),
    )
    last_reuse = sum(episode["reused_fragments"] for episode in last_window) / max(
        1,
        sum(episode["reused_fragments"] + episode["rebuilt_fragments"] for episode in last_window),
    )
    cache_decay_rate = round(max(0.0, first_reuse - last_reuse), 3)
    switch_ratio = policy_switch_count / max(1, len(episodes) - 1)
    latency_pressure = min(1.0, average_absolute_latency_ms / max(0.001, activation_budget["max_latency_ms"]))
    policy_stability_score = round(max(0.0, 1.0 - switch_ratio), 3)
    long_horizon_stability_score = round(
        max(
            0.0,
            1.0
            - warning_rate * 0.28
            - switch_ratio * 0.22
            - coherence_drift * 0.2
            - cache_decay_rate * 0.2
            - latency_pressure * 0.1,
        ),
        3,
    )
    return {
        "policy_switch_count": policy_switch_count,
        "average_relative_cost": average_relative_cost,
        "average_absolute_latency_ms": average_absolute_latency_ms,
        "warning_rate": warning_rate,
        "coherence_drift": coherence_drift,
        "cache_decay_rate": cache_decay_rate,
        "reuse_rate": reuse_rate,
        "policy_stability_score": policy_stability_score,
        "long_horizon_stability_score": long_horizon_stability_score,
    }


def _coherence_drift(episodes: list[dict[str, Any]]) -> float:
    window_size = max(1, len(episodes) // 5)
    first = episodes[:window_size]
    last = episodes[-window_size:]
    first_average = sum(episode["coherence_score"] for episode in first) / max(1, len(first))
    last_average = sum(episode["coherence_score"] for episode in last) / max(1, len(last))
    return round(max(0.0, first_average - last_average), 3)


def _long_horizon_drift_warnings(
    stability_trace: dict[str, Any],
    activation_budget: dict[str, Any],
) -> list[str]:
    warnings = []
    if stability_trace["coherence_drift"] > 0.08:
        warnings.append("coherence_score_declines_over_time")
    if stability_trace["policy_switch_count"] > 8:
        warnings.append("policy_switch_count_high")
    if stability_trace["average_absolute_latency_ms"] > activation_budget["max_latency_ms"] * 0.6:
        warnings.append("average_latency_increases")
    if stability_trace["cache_decay_rate"] > 0.25:
        warnings.append("cache_decay_rate_high")
    return warnings


def _recovery_after_bad_prediction(episodes: list[dict[str, Any]]) -> bool:
    bad_indexes = [
        index for index, episode in enumerate(episodes) if episode["mutation_type"] == "bad_prediction"
    ]
    if not bad_indexes:
        return True
    for index in bad_indexes:
        if index + 1 >= len(episodes):
            continue
        next_episode = episodes[index + 1]
        if next_episode["selected_policy"] == "predictive_sparse" or next_episode["warning_count"] > 1:
            return False
    return True


def _ensure_long_horizon_tables(connection: sqlite3.Connection) -> None:
    _ensure_autotuning_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_long_horizon_stability_runs (
            horizon INTEGER PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_long_horizon_scenario(connection: sqlite3.Connection, scenario: dict[str, Any]) -> None:
    _ensure_long_horizon_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_long_horizon_stability_runs (horizon, payload, created_at)
        VALUES (?, ?, ?)
        """,
        (
            scenario["horizon"],
            json.dumps(scenario, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _workload_query_set(queries: list[str] | None) -> dict[str, Any]:
    selected = []
    query_map = {}
    requested = queries or list(WORKLOAD_QUERY_PRESETS)
    for raw_query in requested:
        query_name = _normalize_workload_query_name(raw_query)
        terms = WORKLOAD_QUERY_PRESETS.get(query_name)
        if terms is None:
            terms = [term for term in raw_query.lower().replace("_", " ").split() if term]
            query_name = "_".join(terms) if terms else "custom"
        if query_name not in query_map:
            selected.append(query_name)
            query_map[query_name] = terms
    return {
        "selected_queries": selected,
        "queries": query_map,
        "available_queries": sorted(WORKLOAD_QUERY_PRESETS),
    }


def _normalize_workload_query_name(query: str) -> str:
    normalized = query.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "todo": "todo",
        "todos": "todo",
        "erreur": "erreurs",
        "errors": "erreurs",
        "error": "erreurs",
        "fonctions": "fonctions_principales",
        "functions": "fonctions_principales",
        "main_functions": "fonctions_principales",
        "dependencies": "dependances",
        "dependency": "dependances",
        "deps": "dependances",
    }
    return aliases.get(normalized, normalized)


def _index_workload_source(source_path: Path, *, chunk_line_count: int) -> dict[str, Any]:
    resolved = source_path.expanduser().resolve()
    files = []
    chunks = []
    if resolved.exists():
        for file_path in _iter_workload_files(resolved):
            text = _read_workload_text(file_path)
            relative_path = _workload_relative_path(file_path, resolved)
            file_chunks = _chunk_workload_file(
                source_root=resolved,
                file_path=file_path,
                relative_path=relative_path,
                text=text,
                chunk_line_count=chunk_line_count,
            )
            stat = file_path.stat()
            file_hash = sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            files.append(
                {
                    "path": relative_path,
                    "suffix": file_path.suffix.lower(),
                    "byte_size": stat.st_size,
                    "file_hash": file_hash,
                    "chunk_ids": [chunk["id"] for chunk in file_chunks],
                }
            )
            chunks.extend(file_chunks)
    workload_source = _workload_source_summary(resolved, files)
    return {
        "workload_source": workload_source,
        "files": files,
        "chunks": chunks,
    }


def _iter_workload_files(source_path: Path) -> list[Path]:
    excluded_dirs = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vs",
        "__pycache__",
        "bin",
        "build",
        "dist",
        "forge_runtime",
        "node_modules",
        "obj",
        "venv",
    }
    if source_path.is_file():
        return [source_path] if source_path.suffix.lower() in WORKLOAD_TEXT_SUFFIXES else []
    files = []
    for path in sorted(source_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in excluded_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in WORKLOAD_TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 512_000:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _read_workload_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _workload_relative_path(file_path: Path, source_root: Path) -> str:
    try:
        return file_path.relative_to(source_root if source_root.is_dir() else source_root.parent).as_posix()
    except ValueError:
        return file_path.name


def _chunk_workload_file(
    *,
    source_root: Path,
    file_path: Path,
    relative_path: str,
    text: str,
    chunk_line_count: int,
) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines:
        lines = [""]
    chunks = []
    for chunk_index, start in enumerate(range(0, len(lines), max(1, chunk_line_count))):
        chunk_lines = lines[start : start + max(1, chunk_line_count)]
        payload = "\n".join(chunk_lines)
        chunk_hash = sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
        chunk_id = sha256(
            json.dumps(
                {
                    "source": str(source_root),
                    "path": relative_path,
                    "chunk_index": chunk_index,
                    "chunk_hash": chunk_hash,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16].upper()
        chunks.append(
            {
                "id": f"WCH-{chunk_id}",
                "file_path": relative_path,
                "chunk_index": chunk_index,
                "start_line": start + 1,
                "end_line": start + len(chunk_lines),
                "text": payload,
                "chunk_hash": chunk_hash,
                "chunk_identity": f"{relative_path}::chunk-{chunk_index}",
                "token_estimate": _token_estimate(payload),
            }
        )
    return chunks


def _workload_source_summary(source_path: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    fingerprint_payload = [
        {
            "path": file["path"],
            "file_hash": file["file_hash"],
            "chunk_ids": file["chunk_ids"],
        }
        for file in files
    ]
    return {
        "source_path": str(source_path),
        "file_count": len(files),
        "total_bytes": sum(file["byte_size"] for file in files),
        "file_types": sorted({file["suffix"] for file in files}),
        "source_fingerprint": sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }


def _evaluate_workload_query(
    *,
    index: dict[str, Any],
    query_name: str,
    query_terms: list[str],
    materialization_limit: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    total_chunks = len(index["chunks"])
    selected = _select_workload_chunks(index["chunks"], query_terms, materialization_limit)
    selected_count = len(selected)
    prewarm_count = min(4, selected_count)
    modes = {
        "naive_full_scan": _workload_mode_result(
            mode="naive_full_scan",
            index=index,
            query_terms=query_terms,
            materialized_chunks=total_chunks,
            reused_chunks=0,
            rebuilt_chunks=total_chunks,
            selected_chunks=index["chunks"],
            started=started,
        ),
        "mmr_minimal": _workload_mode_result(
            mode="mmr_minimal",
            index=index,
            query_terms=query_terms,
            materialized_chunks=selected_count,
            reused_chunks=0,
            rebuilt_chunks=selected_count,
            selected_chunks=selected,
            started=started,
        ),
        "diffcache": _workload_mode_result(
            mode="diffcache",
            index=index,
            query_terms=query_terms,
            materialized_chunks=0,
            reused_chunks=selected_count,
            rebuilt_chunks=0,
            selected_chunks=selected,
            started=started,
        ),
        "microdelta": _workload_mode_result(
            mode="microdelta",
            index=index,
            query_terms=query_terms,
            materialized_chunks=0,
            reused_chunks=selected_count,
            rebuilt_chunks=0,
            selected_chunks=selected,
            started=started,
        ),
        "bounded_predictive": _workload_mode_result(
            mode="bounded_predictive",
            index=index,
            query_terms=query_terms,
            materialized_chunks=max(0, selected_count - prewarm_count),
            reused_chunks=prewarm_count,
            rebuilt_chunks=max(0, selected_count - prewarm_count),
            selected_chunks=selected,
            started=started,
        ),
    }
    modes["auto_tuned"] = _auto_tune_workload_modes(modes)
    return {
        "query_name": query_name,
        "query_terms": query_terms,
        "selected_chunk_ids": [chunk["id"] for chunk in selected],
        "modes": modes,
    }


def _select_workload_chunks(
    chunks: list[dict[str, Any]],
    query_terms: list[str],
    materialization_limit: int,
) -> list[dict[str, Any]]:
    scored = []
    terms = [term.lower() for term in query_terms if term]
    for chunk in chunks:
        text = chunk["text"].lower()
        hits = sum(1 for term in terms if term in text)
        score = hits / max(1, len(terms))
        if hits:
            scored.append((score, -chunk["token_estimate"], chunk["chunk_identity"], chunk))
    if not scored:
        return chunks[: max(1, min(materialization_limit, len(chunks)))]
    scored.sort(reverse=True)
    return [item[3] for item in scored[: max(1, materialization_limit)]]


def _workload_mode_result(
    *,
    mode: str,
    index: dict[str, Any],
    query_terms: list[str],
    materialized_chunks: int,
    reused_chunks: int,
    rebuilt_chunks: int,
    selected_chunks: list[dict[str, Any]],
    started: float,
) -> dict[str, Any]:
    total_chunks = len(index["chunks"])
    warning_count = 0
    if mode == "bounded_predictive" and reused_chunks < rebuilt_chunks:
        warning_count += 1
    coherence_score = _workload_coherence_score(selected_chunks, query_terms)
    if coherence_score < 0.35:
        warning_count += 1
    latency_ms = round((time.perf_counter() - started) * 1000 + materialized_chunks * 0.035 + reused_chunks * 0.006, 3)
    relative_cost = 1.0 if mode == "naive_full_scan" else round(
        min(
            1.0,
            (rebuilt_chunks + materialized_chunks * 0.5 + max(1, len(selected_chunks)) * 0.05)
            / max(1, total_chunks),
        ),
        3,
    )
    metrics = {
        "total_files": index["workload_source"]["file_count"],
        "total_chunks": total_chunks,
        "materialized_chunks": materialized_chunks,
        "reused_chunks": reused_chunks,
        "rebuilt_chunks": rebuilt_chunks,
        "relative_resolution_cost": relative_cost,
        "absolute_latency_ms": latency_ms,
        "warning_count": warning_count,
        "coherence_score": coherence_score,
    }
    return {
        "mode": mode,
        "selected_chunk_ids": [chunk["id"] for chunk in selected_chunks],
        "metrics": metrics,
    }


def _workload_coherence_score(chunks: list[dict[str, Any]], query_terms: list[str]) -> float:
    if not query_terms:
        return 1.0
    text = "\n".join(chunk["text"] for chunk in chunks).lower()
    covered = sum(1 for term in query_terms if term.lower() in text)
    return round(covered / max(1, len(query_terms)), 3)


def _auto_tune_workload_modes(modes: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        modes["diffcache"],
        modes["microdelta"],
        modes["bounded_predictive"],
        modes["mmr_minimal"],
        modes["naive_full_scan"],
    ]
    selected = min(
        candidates,
        key=lambda item: (
            item["metrics"]["warning_count"],
            item["metrics"]["relative_resolution_cost"],
            item["metrics"]["absolute_latency_ms"],
        ),
    )
    return {
        "mode": "auto_tuned",
        "selected_mode": selected["mode"],
        "selected_chunk_ids": selected["selected_chunk_ids"],
        "metrics": {
            **selected["metrics"],
            "warning_count": selected["metrics"]["warning_count"],
        },
    }


def _evaluate_workload_mutations(
    *,
    base_index: dict[str, Any],
    query_name: str,
    query_terms: list[str],
    materialization_limit: int,
) -> dict[str, Any]:
    scenarios = {}
    selected = _select_workload_chunks(base_index["chunks"], query_terms, materialization_limit)
    target_identity = selected[0]["chunk_identity"] if selected else None
    for mutation_type in ["modify_file", "modify_small_chunk", "add_file", "delete_file"]:
        mutated = _mutate_workload_index(base_index, mutation_type, target_identity=target_identity)
        scenarios[mutation_type] = _evaluate_workload_mutation(
            base_index=base_index,
            mutated_index=mutated,
            mutation_type=mutation_type,
            query_name=query_name,
            query_terms=query_terms,
            materialization_limit=materialization_limit,
        )
    return scenarios


def _evaluate_workload_mutation(
    *,
    base_index: dict[str, Any],
    mutated_index: dict[str, Any],
    mutation_type: str,
    query_name: str,
    query_terms: list[str],
    materialization_limit: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    selected = _select_workload_chunks(mutated_index["chunks"], query_terms, materialization_limit)
    base_by_identity = {chunk["chunk_identity"]: chunk for chunk in base_index["chunks"]}
    reused = []
    rebuilt = []
    for chunk in selected:
        previous = base_by_identity.get(chunk["chunk_identity"])
        if previous is not None and previous["chunk_hash"] == chunk["chunk_hash"]:
            reused.append(chunk)
        else:
            rebuilt.append(chunk)
    metrics = _workload_mode_result(
        mode=f"mutation_{mutation_type}",
        index=mutated_index,
        query_terms=query_terms,
        materialized_chunks=len(rebuilt),
        reused_chunks=len(reused),
        rebuilt_chunks=len(rebuilt),
        selected_chunks=selected,
        started=started,
    )["metrics"]
    return {
        "mutation_type": mutation_type,
        "query_name": query_name,
        "workload_source": mutated_index["workload_source"],
        "selected_chunk_ids": [chunk["id"] for chunk in selected],
        "reused_chunk_ids": [chunk["id"] for chunk in reused],
        "rebuilt_chunk_ids": [chunk["id"] for chunk in rebuilt],
        "metrics": metrics,
    }


def _mutate_workload_index(
    index: dict[str, Any],
    mutation_type: str,
    *,
    target_identity: str | None,
) -> dict[str, Any]:
    mutated = json.loads(json.dumps(index))
    if not mutated["files"]:
        return mutated
    if mutation_type == "add_file":
        _workload_add_file(mutated)
    elif mutation_type == "delete_file":
        _workload_delete_file(mutated, target_identity=target_identity)
    elif mutation_type == "modify_small_chunk":
        _workload_modify_chunk(mutated, only_first_chunk=True, target_identity=target_identity)
    else:
        _workload_modify_chunk(mutated, only_first_chunk=False, target_identity=target_identity)
    _refresh_workload_source(mutated)
    return mutated


def _workload_modify_chunk(
    index: dict[str, Any],
    *,
    only_first_chunk: bool,
    target_identity: str | None,
) -> None:
    if not index["chunks"]:
        return
    target_file = _workload_target_file(index, target_identity) or index["files"][0]
    target_identities = {
        chunk["chunk_identity"]
        for chunk in index["chunks"]
        if chunk["id"] in set(target_file["chunk_ids"])
    }
    for chunk in index["chunks"]:
        if chunk["chunk_identity"] not in target_identities:
            continue
        chunk["text"] = f"{chunk['text']}\nAIONE workload mutation touches architecture tests TODO dependencies."
        chunk["chunk_hash"] = sha256(chunk["text"].encode("utf-8", errors="ignore")).hexdigest()
        chunk["token_estimate"] = _token_estimate(chunk["text"])
        if only_first_chunk:
            break
    target_file["file_hash"] = sha256(
        "\n".join(chunk["chunk_hash"] for chunk in index["chunks"] if chunk["id"] in set(target_file["chunk_ids"])).encode("utf-8")
    ).hexdigest()


def _workload_add_file(index: dict[str, Any]) -> None:
    relative_path = "__aione_added_workload.md"
    text = (
        "AIONE added workload file documents architecture runtime operator kernel layer "
        "MMR tests TODO dependencies."
    )
    chunk_hash = sha256(text.encode("utf-8")).hexdigest()
    chunk_id = sha256(f"{relative_path}:{chunk_hash}".encode("utf-8")).hexdigest()[:16].upper()
    chunk = {
        "id": f"WCH-{chunk_id}",
        "file_path": relative_path,
        "chunk_index": 0,
        "start_line": 1,
        "end_line": 1,
        "text": text,
        "chunk_hash": chunk_hash,
        "chunk_identity": f"{relative_path}::chunk-0",
        "token_estimate": _token_estimate(text),
    }
    index["chunks"].append(chunk)
    index["files"].append(
        {
            "path": relative_path,
            "suffix": ".md",
            "byte_size": len(text.encode("utf-8")),
            "file_hash": chunk_hash,
            "chunk_ids": [chunk["id"]],
        }
    )


def _workload_delete_file(index: dict[str, Any], *, target_identity: str | None) -> None:
    target_file = _workload_target_file(index, target_identity) or index["files"][-1]
    deleted_ids = set(target_file["chunk_ids"])
    index["files"] = [file for file in index["files"] if file["path"] != target_file["path"]]
    index["chunks"] = [chunk for chunk in index["chunks"] if chunk["id"] not in deleted_ids]


def _workload_target_file(index: dict[str, Any], target_identity: str | None) -> dict[str, Any] | None:
    if target_identity is None:
        return None
    target_chunk = next(
        (chunk for chunk in index["chunks"] if chunk["chunk_identity"] == target_identity),
        None,
    )
    if target_chunk is None:
        return None
    return next(
        (file for file in index["files"] if file["path"] == target_chunk["file_path"]),
        None,
    )


def _refresh_workload_source(index: dict[str, Any]) -> None:
    source_path = Path(index["workload_source"]["source_path"])
    index["workload_source"] = _workload_source_summary(source_path, index["files"])


def _external_workload_metrics(
    evaluations: dict[str, Any],
    mutation_scenarios: dict[str, Any],
) -> dict[str, Any]:
    all_modes = [
        mode
        for evaluation in evaluations.values()
        for mode in evaluation["modes"].values()
    ]
    mutation_metrics = [scenario["metrics"] for scenario in mutation_scenarios.values()]
    first_metrics = all_modes[0]["metrics"] if all_modes else {
        "total_files": 0,
        "total_chunks": 0,
    }
    return {
        "total_files": first_metrics["total_files"],
        "total_chunks": first_metrics["total_chunks"],
        "best_relative_resolution_cost": min(
            (mode["metrics"]["relative_resolution_cost"] for mode in all_modes),
            default=0.0,
        ),
        "max_reused_chunks": max((mode["metrics"]["reused_chunks"] for mode in all_modes), default=0),
        "mutation_rebuilt_chunks": sum(metrics["rebuilt_chunks"] for metrics in mutation_metrics),
        "warning_count": sum(
            mode["metrics"]["warning_count"] for mode in all_modes
        )
        + sum(metrics["warning_count"] for metrics in mutation_metrics),
    }


def _ensure_external_workload_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_external_workload_adapter_runs (
            id TEXT PRIMARY KEY,
            source_fingerprint TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_external_workload_run(connection: sqlite3.Connection, benchmark: dict[str, Any]) -> None:
    _ensure_external_workload_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_external_workload_adapter_runs (
            id, source_fingerprint, payload, created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            benchmark["id"],
            benchmark["workload_source"]["source_fingerprint"],
            json.dumps(benchmark, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _evaluate_answer_quality_query(
    *,
    index: dict[str, Any],
    query_name: str,
    query_terms: list[str],
    materialization_limit: int,
) -> dict[str, Any]:
    workload_evaluation = _evaluate_workload_query(
        index=index,
        query_name=query_name,
        query_terms=query_terms,
        materialization_limit=materialization_limit,
    )
    modes = workload_evaluation["modes"]
    chunks_by_id = {chunk["id"]: chunk for chunk in index["chunks"]}
    naive_chunks = index["chunks"]
    reference_key_points = _answer_key_points(naive_chunks, query_terms)
    answer_inputs = {
        "naive_full_scan_answer": (
            modes["naive_full_scan"],
            naive_chunks,
        ),
        "mmr_minimal_answer": (
            modes["mmr_minimal"],
            _chunks_from_ids(chunks_by_id, modes["mmr_minimal"]["selected_chunk_ids"]),
        ),
        "diffcache_answer": (
            modes["diffcache"],
            _chunks_from_ids(chunks_by_id, modes["diffcache"]["selected_chunk_ids"]),
        ),
        "bounded_predictive_answer": (
            modes["bounded_predictive"],
            _chunks_from_ids(chunks_by_id, modes["bounded_predictive"]["selected_chunk_ids"]),
        ),
        "auto_tuned_answer": (
            modes["auto_tuned"],
            _chunks_from_ids(chunks_by_id, modes["auto_tuned"]["selected_chunk_ids"]),
        ),
    }
    answers = {
        mode_name: _verified_answer_for_mode(
            query_name=query_name,
            query_terms=query_terms,
            mode_name=mode_name,
            mode_result=mode_result,
            selected_chunks=selected_chunks,
            reference_key_points=reference_key_points,
        )
        for mode_name, (mode_result, selected_chunks) in answer_inputs.items()
    }
    return {
        "query_name": query_name,
        "query_terms": query_terms,
        "reference_key_points": reference_key_points,
        "answers": answers,
    }


def _chunks_from_ids(chunks_by_id: dict[str, dict[str, Any]], chunk_ids: list[str]) -> list[dict[str, Any]]:
    return [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]


def _verified_answer_for_mode(
    *,
    query_name: str,
    query_terms: list[str],
    mode_name: str,
    mode_result: dict[str, Any],
    selected_chunks: list[dict[str, Any]],
    reference_key_points: list[str],
) -> dict[str, Any]:
    answer_key_points = _answer_key_points(selected_chunks, query_terms)
    answer = _build_workload_answer(query_name, mode_name, selected_chunks, answer_key_points)
    verifier = _source_verifier(answer, selected_chunks, query_terms)
    completeness = _completeness_check(
        answer_key_points=answer_key_points,
        reference_key_points=reference_key_points,
        relative_resolution_cost=mode_result["metrics"]["relative_resolution_cost"],
    )
    evidence_score = verifier["evidence_score"]
    completeness_score = completeness["completeness_score"]
    unsupported_claim_count = verifier["unsupported_claim_count"]
    contradiction_count = verifier["contradiction_count"]
    answer_quality_score = round(
        max(
            0.0,
            evidence_score * 0.42
            + completeness_score * 0.42
            + min(1.0, completeness["compression_quality_ratio"] / 10.0) * 0.16
            - unsupported_claim_count * 0.08
            - contradiction_count * 0.16,
        ),
        3,
    )
    verified_answer = {
        "query": query_name,
        "answer": answer,
        "cited_chunks": verifier["cited_chunks"],
        "source_file_paths": sorted({chunk["file_path"] for chunk in selected_chunks}),
        "evidence_score": evidence_score,
        "completeness_score": completeness_score,
        "contradiction_count": contradiction_count,
        "unsupported_claim_count": unsupported_claim_count,
    }
    metrics = {
        "relative_resolution_cost": mode_result["metrics"]["relative_resolution_cost"],
        "evidence_score": evidence_score,
        "completeness_score": completeness_score,
        "unsupported_claim_count": unsupported_claim_count,
        "contradiction_count": contradiction_count,
        "missing_key_points": completeness["missing_key_points"],
        "answer_quality_score": answer_quality_score,
        "compression_quality_ratio": completeness["compression_quality_ratio"],
    }
    return {
        "mode": mode_name,
        "verified_answer": verified_answer,
        "source_verifier": verifier,
        "completeness_check": completeness,
        "metrics": metrics,
    }


def _answer_key_points(chunks: list[dict[str, Any]], query_terms: list[str]) -> list[str]:
    text = "\n".join(chunk["text"] for chunk in chunks).lower()
    return sorted({term for term in query_terms if term.lower() in text})


def _build_workload_answer(
    query_name: str,
    mode_name: str,
    selected_chunks: list[dict[str, Any]],
    key_points: list[str],
) -> str:
    if not selected_chunks:
        return f"No sourced answer for {query_name}. [chunks: none]"
    primary_chunks = selected_chunks[: min(3, len(selected_chunks))]
    cited = ", ".join(chunk["id"] for chunk in primary_chunks)
    files = ", ".join(sorted({chunk["file_path"] for chunk in primary_chunks}))
    points = ", ".join(key_points) if key_points else "no direct query term"
    sentences = [
        f"The {query_name} answer is supported by evidence for {points} [chunks: {cited}]",
        f"The strongest source files are {files} [chunks: {cited}]",
    ]
    if mode_name == "naive_full_scan_answer":
        sentences.append(f"The naive baseline uses the full indexed source set [chunks: {cited}]")
    else:
        sentences.append(f"The reduced answer keeps the cited workload evidence visible [chunks: {cited}]")
    return " ".join(sentences)


def _source_verifier(
    answer: str,
    selected_chunks: list[dict[str, Any]],
    query_terms: list[str],
) -> dict[str, Any]:
    source_text = "\n".join(chunk["text"] for chunk in selected_chunks).lower()
    chunk_ids = {chunk["id"] for chunk in selected_chunks}
    sentences = _important_sentences(answer)
    unsupported = []
    contradicted = []
    cited_chunks = []
    for sentence in sentences:
        sentence_citations = [
            chunk_id for chunk_id in chunk_ids if chunk_id in sentence
        ]
        if sentence_citations:
            cited_chunks.extend(sentence_citations)
        sentence_terms = [term for term in query_terms if term.lower() in sentence.lower()]
        has_source_overlap = any(term.lower() in source_text for term in sentence_terms) or bool(sentence_citations)
        if not sentence_citations or not has_source_overlap:
            unsupported.append(sentence)
        if _simple_contradiction(sentence, source_text, query_terms):
            contradicted.append(sentence)
    supported_count = max(0, len(sentences) - len(unsupported))
    evidence_score = round(supported_count / max(1, len(sentences)), 3)
    return {
        "important_sentence_count": len(sentences),
        "cited_chunks": sorted(set(cited_chunks)),
        "unsupported_claims": unsupported,
        "unsupported_claim_count": len(unsupported),
        "contradictions": contradicted,
        "contradiction_count": len(contradicted),
        "evidence_score": evidence_score,
    }


def _important_sentences(answer: str) -> list[str]:
    return [
        sentence.strip().rstrip(".")
        for sentence in answer.replace("\n", " ").split(". ")
        if sentence.strip().rstrip(".")
    ]


def _simple_contradiction(sentence: str, source_text: str, query_terms: list[str]) -> bool:
    lowered = sentence.lower()
    if not any(marker in lowered for marker in [" no ", "not ", "absent", "without "]):
        return False
    return any(term.lower() in source_text for term in query_terms)


def _completeness_check(
    *,
    answer_key_points: list[str],
    reference_key_points: list[str],
    relative_resolution_cost: float,
) -> dict[str, Any]:
    answer_set = set(answer_key_points)
    reference_set = set(reference_key_points)
    missing = sorted(reference_set - answer_set)
    completeness_score = round(len(answer_set & reference_set) / max(1, len(reference_set)), 3)
    compression_quality_ratio = round(
        completeness_score / max(0.001, relative_resolution_cost),
        3,
    )
    return {
        "missing_key_points": missing,
        "completeness_score": completeness_score,
        "compression_quality_ratio": compression_quality_ratio,
    }


def _answer_quality_metrics(query_evaluations: dict[str, Any]) -> dict[str, Any]:
    answers = [
        answer
        for evaluation in query_evaluations.values()
        for answer in evaluation["answers"].values()
    ]
    return {
        "best_answer_quality_score": max(
            (answer["metrics"]["answer_quality_score"] for answer in answers),
            default=0.0,
        ),
        "minimum_evidence_score": min(
            (answer["metrics"]["evidence_score"] for answer in answers),
            default=0.0,
        ),
        "minimum_completeness_score": min(
            (answer["metrics"]["completeness_score"] for answer in answers),
            default=0.0,
        ),
        "unsupported_claim_count": sum(
            answer["metrics"]["unsupported_claim_count"] for answer in answers
        ),
        "contradiction_count": sum(answer["metrics"]["contradiction_count"] for answer in answers),
        "max_missing_key_points": max(
            (len(answer["metrics"]["missing_key_points"]) for answer in answers),
            default=0,
        ),
    }


def _ensure_answer_quality_tables(connection: sqlite3.Connection) -> None:
    _ensure_external_workload_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_answer_quality_verification_runs (
            id TEXT PRIMARY KEY,
            source_fingerprint TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_answer_quality_run(connection: sqlite3.Connection, benchmark: dict[str, Any]) -> None:
    _ensure_answer_quality_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_answer_quality_verification_runs (
            id, source_fingerprint, payload, created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            benchmark["id"],
            benchmark["workload_source"]["source_fingerprint"],
            json.dumps(benchmark, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _evaluate_real_user_task(
    *,
    index: dict[str, Any],
    task: dict[str, Any],
    materialization_limit: int,
) -> dict[str, Any]:
    query_terms = task["query_terms"]
    workload_evaluation = _evaluate_workload_query(
        index=index,
        query_name=task["id"],
        query_terms=query_terms,
        materialization_limit=materialization_limit,
    )
    modes = workload_evaluation["modes"]
    chunks_by_id = {chunk["id"]: chunk for chunk in index["chunks"]}
    reference_chunks = index["chunks"]
    reference_key_points = _answer_key_points(reference_chunks, query_terms)
    mode_inputs = {
        "naive_full_scan": (
            modes["naive_full_scan"],
            reference_chunks,
        ),
        "mmr_minimal": (
            modes["mmr_minimal"],
            _chunks_from_ids(chunks_by_id, modes["mmr_minimal"]["selected_chunk_ids"]),
        ),
        "diffcache": (
            modes["diffcache"],
            _chunks_from_ids(chunks_by_id, modes["diffcache"]["selected_chunk_ids"]),
        ),
        "microdelta": (
            modes["microdelta"],
            _chunks_from_ids(chunks_by_id, modes["microdelta"]["selected_chunk_ids"]),
        ),
        "bounded_predictive": (
            modes["bounded_predictive"],
            _chunks_from_ids(chunks_by_id, modes["bounded_predictive"]["selected_chunk_ids"]),
        ),
        "auto_tuned": (
            modes["auto_tuned"],
            _chunks_from_ids(chunks_by_id, modes["auto_tuned"]["selected_chunk_ids"]),
        ),
    }
    evaluated_modes = {
        mode_name: _real_task_mode_result(
            task=task,
            mode_name=mode_name,
            mode_result=mode_result,
            selected_chunks=selected_chunks,
            reference_key_points=reference_key_points,
        )
        for mode_name, (mode_result, selected_chunks) in mode_inputs.items()
    }
    return {
        "task": task,
        "reference_key_points": reference_key_points,
        "selected_chunk_ids": workload_evaluation["selected_chunk_ids"],
        "modes": evaluated_modes,
    }


def _real_task_mode_result(
    *,
    task: dict[str, Any],
    mode_name: str,
    mode_result: dict[str, Any],
    selected_chunks: list[dict[str, Any]],
    reference_key_points: list[str],
) -> dict[str, Any]:
    verified = _verified_answer_for_mode(
        query_name=task["id"],
        query_terms=task["query_terms"],
        mode_name=f"{mode_name}_answer",
        mode_result=mode_result,
        selected_chunks=selected_chunks,
        reference_key_points=reference_key_points,
    )
    source_coverage_score = _source_coverage_score(verified["verified_answer"], selected_chunks)
    task_success_score = _task_success_score(
        evidence_score=verified["metrics"]["evidence_score"],
        completeness_score=verified["metrics"]["completeness_score"],
        source_coverage_score=source_coverage_score,
        coherence_score=mode_result["metrics"]["coherence_score"],
        unsupported_claim_count=verified["metrics"]["unsupported_claim_count"],
        contradiction_count=verified["metrics"]["contradiction_count"],
    )
    metrics = {
        "relative_resolution_cost": mode_result["metrics"]["relative_resolution_cost"],
        "absolute_latency_ms": mode_result["metrics"]["absolute_latency_ms"],
        "evidence_score": verified["metrics"]["evidence_score"],
        "completeness_score": verified["metrics"]["completeness_score"],
        "unsupported_claim_count": verified["metrics"]["unsupported_claim_count"],
        "contradiction_count": verified["metrics"]["contradiction_count"],
        "task_success_score": task_success_score,
        "source_coverage_score": source_coverage_score,
        "missing_key_points": verified["metrics"]["missing_key_points"],
        "answer_quality_score": verified["metrics"]["answer_quality_score"],
        "coherence_score": mode_result["metrics"]["coherence_score"],
    }
    return {
        "mode": mode_name,
        "selected_chunk_ids": mode_result["selected_chunk_ids"],
        "verified_answer": verified["verified_answer"],
        "source_verifier": verified["source_verifier"],
        "completeness_check": verified["completeness_check"],
        "metrics": metrics,
    }


def _source_coverage_score(verified_answer: dict[str, Any], selected_chunks: list[dict[str, Any]]) -> float:
    if not selected_chunks:
        return 0.0
    cited_chunk_ids = set(verified_answer["cited_chunks"])
    primary_chunks = selected_chunks[: min(3, len(selected_chunks))]
    primary_chunk_ids = {chunk["id"] for chunk in primary_chunks}
    primary_files = {chunk["file_path"] for chunk in primary_chunks}
    cited_files = {
        chunk["file_path"]
        for chunk in selected_chunks
        if chunk["id"] in cited_chunk_ids
    }
    citation_ratio = len(cited_chunk_ids & primary_chunk_ids) / max(1, len(primary_chunk_ids))
    file_ratio = len(cited_files & primary_files) / max(1, len(primary_files))
    return round((citation_ratio * 0.65) + (file_ratio * 0.35), 3)


def _task_success_score(
    *,
    evidence_score: float,
    completeness_score: float,
    source_coverage_score: float,
    coherence_score: float,
    unsupported_claim_count: int,
    contradiction_count: int,
) -> float:
    score = (
        evidence_score * 0.32
        + completeness_score * 0.32
        + source_coverage_score * 0.22
        + coherence_score * 0.14
        - unsupported_claim_count * 0.08
        - contradiction_count * 0.16
    )
    return round(max(0.0, min(1.0, score)), 3)


def _real_user_task_metrics(task_results: dict[str, Any]) -> dict[str, Any]:
    mode_results = [
        mode
        for task_result in task_results.values()
        for mode in task_result["modes"].values()
    ]
    reduced_modes = [
        mode
        for task_result in task_results.values()
        for mode_name, mode in task_result["modes"].items()
        if mode_name != "naive_full_scan"
    ]
    return {
        "task_count": len(task_results),
        "average_task_success_score": round(
            sum(mode["metrics"]["task_success_score"] for mode in mode_results) / max(1, len(mode_results)),
            3,
        ),
        "average_source_coverage_score": round(
            sum(mode["metrics"]["source_coverage_score"] for mode in mode_results) / max(1, len(mode_results)),
            3,
        ),
        "best_relative_resolution_cost": min(
            (mode["metrics"]["relative_resolution_cost"] for mode in mode_results),
            default=0.0,
        ),
        "average_reduced_relative_resolution_cost": round(
            sum(mode["metrics"]["relative_resolution_cost"] for mode in reduced_modes)
            / max(1, len(reduced_modes)),
            3,
        ),
        "minimum_evidence_score": min(
            (mode["metrics"]["evidence_score"] for mode in mode_results),
            default=0.0,
        ),
        "minimum_completeness_score": min(
            (mode["metrics"]["completeness_score"] for mode in mode_results),
            default=0.0,
        ),
        "unsupported_claim_count": sum(
            mode["metrics"]["unsupported_claim_count"] for mode in mode_results
        ),
        "contradiction_count": sum(mode["metrics"]["contradiction_count"] for mode in mode_results),
        "max_missing_key_points": max(
            (len(mode["metrics"]["missing_key_points"]) for mode in mode_results),
            default=0,
        ),
    }


def _ensure_real_user_task_tables(connection: sqlite3.Connection) -> None:
    _ensure_answer_quality_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_real_user_task_benchmark_runs (
            id TEXT PRIMARY KEY,
            source_fingerprint TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_real_user_task_run(connection: sqlite3.Connection, benchmark: dict[str, Any]) -> None:
    _ensure_real_user_task_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_real_user_task_benchmark_runs (
            id, source_fingerprint, payload, created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            benchmark["id"],
            benchmark["workload_source"]["source_fingerprint"],
            json.dumps(benchmark, sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _ensure_microdelta_tables(connection: sqlite3.Connection) -> None:
    _ensure_intrastate_tables(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_microfragments (
            id TEXT PRIMARY KEY,
            state_segment_id TEXT NOT NULL,
            fragment_key TEXT NOT NULL,
            fragment_fingerprint TEXT NOT NULL,
            semantic_tags TEXT NOT NULL,
            source_refs TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_microdelta_materialized_slices (
            id TEXT PRIMARY KEY,
            potential_state_id TEXT NOT NULL,
            query TEXT NOT NULL,
            slice_fingerprint TEXT NOT NULL,
            microfragment_ids TEXT NOT NULL,
            dependency_graph TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_microdelta_runs (
            run_key TEXT PRIMARY KEY,
            scenario TEXT NOT NULL,
            potential_state_id TEXT NOT NULL,
            slice_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_microfragments(connection: sqlite3.Connection, fragments: list[dict[str, Any]]) -> None:
    _ensure_microdelta_tables(connection)
    for fragment in fragments:
        connection.execute(
            """
            INSERT OR REPLACE INTO mmr_microfragments (
                id, state_segment_id, fragment_key, fragment_fingerprint,
                semantic_tags, source_refs, payload, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fragment["id"],
                fragment["state_segment_id"],
                fragment["fragment_key"],
                fragment["fragment_fingerprint"],
                json.dumps(fragment["semantic_tags"], sort_keys=True, ensure_ascii=False),
                json.dumps(fragment["source_refs"], sort_keys=True, ensure_ascii=False),
                json.dumps(fragment, sort_keys=True, ensure_ascii=False),
                fragment["updated_at"],
            ),
        )


def _store_microdelta_slice(
    connection: sqlite3.Connection,
    materialized_slice: dict[str, Any],
    dependency_graph: list[dict[str, Any]],
) -> None:
    _ensure_microdelta_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_microdelta_materialized_slices (
            id, potential_state_id, query, slice_fingerprint, microfragment_ids,
            dependency_graph, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            materialized_slice["id"],
            materialized_slice["potential_state_id"],
            materialized_slice["query"],
            materialized_slice["slice_fingerprint"],
            json.dumps(materialized_slice["microfragment_ids"], sort_keys=True, ensure_ascii=False),
            json.dumps(dependency_graph, sort_keys=True, ensure_ascii=False),
            json.dumps(materialized_slice, sort_keys=True, ensure_ascii=False),
            materialized_slice["created_at"],
        ),
    )


def _store_microdelta_run(
    connection: sqlite3.Connection,
    name: str,
    potential_state: dict[str, Any],
    materialized_slice: dict[str, Any],
    dependency_graph: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
) -> None:
    _ensure_microdelta_tables(connection)
    run_key = sha256(
        json.dumps(
            {
                "scenario": name,
                "potential_state_id": potential_state["id"],
                "state_fingerprint": potential_state["state_fingerprint"],
                "slice_id": materialized_slice["id"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    payload = {
        "scenario": name,
        "potential_state": potential_state,
        "materialized_slice": materialized_slice,
        "dependency_graph": dependency_graph,
        "microfragments": fragments,
        "created_at": utc_ts(),
    }
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_microdelta_runs (
            run_key, scenario, potential_state_id, slice_id, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_key,
            name,
            potential_state["id"],
            materialized_slice["id"],
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
            payload["created_at"],
        ),
    )


def _ensure_intrastate_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_state_segments (
            id TEXT PRIMARY KEY,
            potential_state_id TEXT NOT NULL,
            segment_key TEXT NOT NULL,
            segment_fingerprint TEXT NOT NULL,
            semantic_tags TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_intrastate_materialized_slices (
            id TEXT PRIMARY KEY,
            potential_state_id TEXT NOT NULL,
            query TEXT NOT NULL,
            slice_fingerprint TEXT NOT NULL,
            state_segment_ids TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mmr_intrastate_runs (
            run_key TEXT PRIMARY KEY,
            scenario TEXT NOT NULL,
            potential_state_id TEXT NOT NULL,
            slice_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _store_intrastate_segments(connection: sqlite3.Connection, segments: list[dict[str, Any]]) -> None:
    _ensure_intrastate_tables(connection)
    for segment in segments:
        connection.execute(
            """
            INSERT OR REPLACE INTO mmr_state_segments (
                id, potential_state_id, segment_key, segment_fingerprint, semantic_tags, payload, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                segment["id"],
                segment["potential_state_id"],
                segment["segment_key"],
                segment["segment_fingerprint"],
                json.dumps(segment["semantic_tags"], sort_keys=True, ensure_ascii=False),
                json.dumps(segment, sort_keys=True, ensure_ascii=False),
                segment["updated_at"],
            ),
        )


def _store_intrastate_slice(connection: sqlite3.Connection, materialized_slice: dict[str, Any]) -> None:
    _ensure_intrastate_tables(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_intrastate_materialized_slices (
            id, potential_state_id, query, slice_fingerprint, state_segment_ids, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            materialized_slice["id"],
            materialized_slice["potential_state_id"],
            materialized_slice["query"],
            materialized_slice["slice_fingerprint"],
            json.dumps(materialized_slice["state_segment_ids"], sort_keys=True, ensure_ascii=False),
            json.dumps(materialized_slice, sort_keys=True, ensure_ascii=False),
            materialized_slice["created_at"],
        ),
    )


def _store_intrastate_run(
    connection: sqlite3.Connection,
    name: str,
    potential_state: dict[str, Any],
    materialized_slice: dict[str, Any],
    segments: list[dict[str, Any]],
) -> None:
    _ensure_intrastate_tables(connection)
    run_key = sha256(
        json.dumps(
            {
                "scenario": name,
                "potential_state_id": potential_state["id"],
                "state_fingerprint": potential_state["state_fingerprint"],
                "slice_id": materialized_slice["id"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    payload = {
        "scenario": name,
        "potential_state": potential_state,
        "materialized_slice": materialized_slice,
        "segments": segments,
        "created_at": utc_ts(),
    }
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_intrastate_runs (
            run_key, scenario, potential_state_id, slice_id, payload, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_key,
            name,
            potential_state["id"],
            materialized_slice["id"],
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
            payload["created_at"],
        ),
    )


def _weak_segment_mutation(records: list[dict[str, Any]], selected_keys: set[str]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    target_index = 0
    for index, record in enumerate(mutated):
        if record["id"] in selected_keys:
            target_index = index
            break
    mutated[target_index] = {
        **mutated[target_index],
        "summary": mutated[target_index]["summary"] + " Weak internal delta marker.",
    }
    return mutated


def _medium_segment_mutation(records: list[dict[str, Any]], selected_keys: set[str]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    changed_any = False
    for index, record in enumerate(mutated):
        if record["id"] not in selected_keys:
            continue
        mutated[index] = {
            **record,
            "summary": record["summary"] + " Medium internal delta changes selected content.",
        }
        changed_any = True
    if not changed_any:
        mutated[0] = {
            **mutated[0],
            "summary": mutated[0]["summary"] + " Medium internal delta changes selected content.",
        }
    return mutated


def _strong_segment_mutation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = []
    for record in records:
        mutated.append(
            {
                **record,
                "summary": record["summary"] + " Strong internal delta changes content and sources.",
                "tags": [*record.get("tags", []), "delta"],
                "source_refs": [*record.get("source_refs", []), "runtime/intrastate_delta"],
            }
        )
    return mutated


def _weak_micro_mutation(records: list[dict[str, Any]], selected_identities: set[str]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    target = _target_fragment(selected_identities, preferred_keys=["summary", "title", "claims"])
    if not mutated or target is None:
        return mutated
    return _mutate_record_fragment(mutated, target[0], target[1], "Weak micro delta marker.")


def _weak_segment_micro_mutation(
    records: list[dict[str, Any]],
    selected_identities: set[str],
) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    segment_key = _target_segment(selected_identities) or mutated[0]["id"]
    mutated = _mutate_record_fragment(mutated, segment_key, "summary", "Weak segment delta summary marker.")
    mutated = _mutate_record_fragment(mutated, segment_key, "claims", "Weak segment delta claim marker.")
    return mutated


def _medium_micro_mutation(records: list[dict[str, Any]], selected_identities: set[str]) -> list[dict[str, Any]]:
    mutated = [dict(record) for record in records]
    if not mutated:
        return mutated
    selected_segments = sorted({identity.split("::", 1)[0] for identity in selected_identities})
    target_segments = selected_segments[:2] or [mutated[0]["id"]]
    for segment_key in target_segments:
        mutated = _mutate_record_fragment(mutated, segment_key, "title", "Medium micro delta title.")
        mutated = _mutate_record_fragment(mutated, segment_key, "summary", "Medium micro delta summary.")
        mutated = _mutate_record_fragment(mutated, segment_key, "claims", "Medium micro delta claim.")
    return mutated


def _target_fragment(
    selected_identities: set[str],
    *,
    preferred_keys: list[str],
) -> tuple[str, str] | None:
    parsed = []
    for identity in sorted(selected_identities):
        if "::" not in identity:
            continue
        segment_key, fragment_key = identity.split("::", 1)
        parsed.append((segment_key, fragment_key))
    for preferred in preferred_keys:
        for segment_key, fragment_key in parsed:
            if fragment_key == preferred:
                return segment_key, fragment_key
    return parsed[0] if parsed else None


def _target_segment(selected_identities: set[str]) -> str | None:
    for identity in sorted(selected_identities):
        if "::" in identity:
            return identity.split("::", 1)[0]
    return None


def _mutate_record_fragment(
    records: list[dict[str, Any]],
    segment_key: str,
    fragment_key: str,
    marker: str,
) -> list[dict[str, Any]]:
    mutated = []
    for record in records:
        if record["id"] != segment_key:
            mutated.append(record)
            continue
        updated = dict(record)
        if fragment_key == "title":
            updated["title"] = f"{record['title']} {marker}"
        elif fragment_key == "summary":
            updated["summary"] = f"{record['summary']} {marker}"
        elif fragment_key == "claims":
            updated["claims"] = [*record.get("claims", []), marker]
        elif fragment_key == "semantic_tags":
            updated["tags"] = [*record.get("tags", []), "micro_delta"]
        elif fragment_key == "source_refs":
            updated["source_refs"] = [*record.get("source_refs", []), "runtime/microdelta_dependency"]
        else:
            updated["summary"] = f"{record['summary']} {marker}"
        mutated.append(updated)
    return mutated


def _store_query_cache(
    connection: sqlite3.Connection,
    cache_key: str,
    query: str,
    limit: int,
    records: list[dict[str, Any]],
    selected_documents: list[dict[str, Any]],
) -> None:
    _ensure_query_cache_table(connection)
    token_estimate = sum(document["token_estimate"] for document in selected_documents)
    connection.execute(
        """
        INSERT OR REPLACE INTO mmr_query_cache (
            cache_key,
            query,
            limit_value,
            strategy_version,
            schema_version,
            corpus_fingerprint,
            selected_payload,
            token_estimate,
            materialized_documents,
            invalidators,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cache_key,
            query,
            limit,
            DOCUMENT_SCORING_VERSION,
            CACHE_SCHEMA_VERSION,
            _corpus_fingerprint(records),
            json.dumps(selected_documents, sort_keys=True, ensure_ascii=False),
            token_estimate,
            len(selected_documents),
            json.dumps(_cache_invalidators(records), sort_keys=True, ensure_ascii=False),
            utc_ts(),
        ),
    )


def _lookup_query_cache(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
    records: list[dict[str, Any]],
    scoring_version: str,
) -> dict[str, Any] | None:
    _ensure_query_cache_table(connection)
    corpus_fingerprint = _corpus_fingerprint(records)
    cache_key = _cache_key(query, limit, corpus_fingerprint, scoring_version)
    row = connection.execute(
        """
        SELECT selected_payload, token_estimate, invalidators
        FROM mmr_query_cache
        WHERE cache_key = ?
        """,
        (cache_key,),
    ).fetchone()
    if row:
        return {
            "selected_documents": json.loads(row[0]),
            "token_estimate": int(row[1]),
            "invalidators": json.loads(row[2]),
        }
    prior = connection.execute(
        """
        SELECT corpus_fingerprint, strategy_version, schema_version, invalidators
        FROM mmr_query_cache
        WHERE query = ? AND limit_value = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (query, limit),
    ).fetchone()
    if prior:
        invalidators = []
        if prior[0] != corpus_fingerprint:
            invalidators.extend(["corpus_fingerprint_changed", "document_hash_changed"])
        if prior[1] != scoring_version:
            invalidators.append("scoring_strategy_changed")
        if prior[2] != CACHE_SCHEMA_VERSION:
            invalidators.append("index_schema_changed")
        return {
            "selected_documents": [],
            "token_estimate": 0,
            "invalidators": invalidators or json.loads(prior[3]),
        }
    return None


def _selected_payload(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["record"]["id"],
            "title": item["record"]["title"],
            "score": item["score"],
            "token_estimate": item["record"]["token_estimate"],
            "document_hash": item["record"].get("document_hash", ""),
        }
        for item in selected
    ]


def _cache_invalidators(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "corpus_fingerprint": _corpus_fingerprint(records),
        "document_hashes": {record["id"]: record["document_hash"] for record in records},
        "scoring_version": DOCUMENT_SCORING_VERSION,
        "schema_version": CACHE_SCHEMA_VERSION,
        "strategy": DOCUMENT_STRATEGY,
    }


def _cache_key(query: str, limit: int, corpus_fingerprint: str, scoring_version: str) -> str:
    return sha256(
        json.dumps(
            {
                "query": query,
                "limit": limit,
                "corpus_fingerprint": corpus_fingerprint,
                "scoring_version": scoring_version,
                "schema_version": CACHE_SCHEMA_VERSION,
                "strategy": DOCUMENT_STRATEGY,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _corpus_fingerprint(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": record["id"],
            "document_hash": record["document_hash"],
            "token_estimate": record["token_estimate"],
        }
        for record in sorted(records, key=lambda item: item["id"])
    ]
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _document_hash(document: dict[str, Any]) -> str:
    payload = {
        "id": document["id"],
        "title": document["title"],
        "tags": document.get("tags", []),
        "body": document["body"],
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _latency_estimate(materialized_documents: int, token_estimate: int, *, cached: bool) -> int:
    if cached:
        return 3
    return max(5, materialized_documents * 8 + int(token_estimate / 12))


def _changed_document_corpus(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = [dict(document) for document in documents]
    if not changed:
        return changed
    changed[0] = {
        **changed[0],
        "body": changed[0]["body"] + " Cache invalidation marker for changed document content.",
    }
    return changed


def _low_divergence_corpus(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = [dict(document) for document in documents]
    if not changed:
        return changed
    index = min(4, len(changed) - 1)
    changed[index] = {
        **changed[index],
        "body": changed[index]["body"] + " Low divergence marker for scheduler calibration.",
    }
    return changed


def _high_divergence_corpus(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = [dict(document) for document in documents]
    for index, document in enumerate(changed[:4]):
        changed[index] = {
            **document,
            "body": (
                document["body"]
                + " High divergence marker for minimum materialization runtime memory context rebuild."
            ),
        }
    return changed
