from __future__ import annotations

from pathlib import Path

from aione_forge.kernel import AioneKernel
from aione_forge.operators import MemoryContextOperator
from aione_forge.stores import StoreBundle, relevance_score, render_store_status


def test_store_bundle_persists_kernel_records(tmp_path: Path) -> None:
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    stores = StoreBundle(tmp_path / "stores")
    status = stores.persist_kernel_result(kernel_result)

    assert status["knowledge_tiles"] == 1
    assert status["proof_capsules"] == 1
    assert status["patch_ledgers"] == 1
    assert status["raw_knowledge_tiles"] == 1
    assert (tmp_path / "stores" / "knowledge_tiles.jsonl").exists()
    assert (tmp_path / "stores" / "proof_capsules.jsonl").exists()
    assert (tmp_path / "stores" / "patch_ledgers.jsonl").exists()
    assert (tmp_path / "stores" / "store_index.json").exists()


def test_store_bundle_searches_knowledge_tiles(tmp_path: Path) -> None:
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    stores = StoreBundle(tmp_path / "stores")
    status = stores.persist_kernel_result(kernel_result)
    results = stores.search_knowledge("kernel")

    assert len(results) == 1
    assert results[0]["record"]["id"].startswith("KT-")
    assert "Results for `kernel`: 1" in render_store_status(status, results)


def test_store_bundle_filters_by_tag_status_proof_and_patch(tmp_path: Path) -> None:
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    stores = StoreBundle(tmp_path / "stores")
    stores.persist_kernel_result(kernel_result)

    assert len(stores.query_knowledge(tags=["kernel"])) == 1
    assert len(stores.query_knowledge(verification_status="partial")) == 1
    assert len(stores.query_knowledge(relation="MISSION-0001")) == 1
    assert len(stores.query_proofs(target_artifact="kernel/cycle_kernel.json")) == 1
    assert len(stores.query_proofs(status="passed")) == 1
    assert len(stores.query_patches(status="applied")) == 1
    assert len(stores.query_patches(file_touched="aione_forge/kernel.py")) == 1


def test_store_bundle_deduplicates_active_memory_by_identity(tmp_path: Path) -> None:
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    next_kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=2)
    stores = StoreBundle(tmp_path / "stores")
    first = stores.persist_kernel_result(kernel_result)
    second = stores.persist_kernel_result(next_kernel_result)

    assert first["knowledge_tiles"] == 1
    assert second["knowledge_tiles"] == 1
    assert second["patch_ledgers"] == 1
    assert second["raw_knowledge_tiles"] == 1
    assert second["inserted"]["knowledge_tile"] is False
    assert second["inserted"]["proof_capsule"] is False
    assert second["inserted"]["patch_ledger"] is False


def test_store_bundle_builds_relation_graph_and_context(tmp_path: Path) -> None:
    kernel_result = AioneKernel().run_intent("Construire AIONE avec une forge autonome verifiee.", cycle=1)
    stores = StoreBundle(tmp_path / "stores")
    stores.persist_kernel_result(kernel_result)

    graph = stores.relation_graph()
    weighted_graph = stores.weighted_relation_graph()
    context = stores.synthesize_context("kernel proof memory")

    assert kernel_result["knowledge_tile"]["id"] in graph
    assert kernel_result["mission"]["id"] in graph
    assert kernel_result["knowledge_tile"]["id"] in weighted_graph
    assert weighted_graph[kernel_result["knowledge_tile"]["id"]][0]["weight"] > 0
    assert context["operator"] == "MemoryContextOperator"
    assert context["state_counts"]["active"] == 1
    assert context["result_count"] == 1
    assert context["items"][0]["score"] > 0
    assert context["items"][0]["state"] == "active"


def test_memory_context_operator_scores_and_graphs_records() -> None:
    records = [
        {
            "id": "KT-1",
            "title": "Kernel memory tile",
            "summary": "Proof and memory for AIONE.",
            "tags": ["kernel", "memory"],
            "claims": ["proof exists"],
            "relations": ["MISSION-1"],
            "source_refs": [],
            "verification_status": "partial",
        }
    ]
    operator = MemoryContextOperator()

    graph = operator.build_relation_graph(records)
    weighted_graph = operator.build_weighted_relation_graph(records)
    context = operator.synthesize_context(records, "kernel proof")

    assert graph["KT-1"] == ["MISSION-1"]
    assert graph["MISSION-1"] == ["KT-1"]
    assert weighted_graph["KT-1"][0]["target"] == "MISSION-1"
    assert weighted_graph["KT-1"][0]["weight"] > 0
    assert context["operator"] == "MemoryContextOperator"
    assert context["items"][0]["id"] == "KT-1"
    assert context["items"][0]["state"] == "active"


def test_memory_context_operator_marks_state_and_fusion_candidates() -> None:
    records = [
        {
            "id": "KT-1",
            "title": "Kernel memory tile",
            "summary": "Proof and memory for AIONE.",
            "tags": ["kernel", "memory"],
            "claims": ["proof exists"],
            "relations": [],
            "source_refs": [],
            "verification_status": "partial",
            "usefulness_score": 0.8,
            "recency_score": 1.0,
        },
        {
            "id": "KT-2",
            "title": "Kernel memory tile",
            "summary": "Same concept.",
            "tags": ["kernel", "memory"],
            "claims": ["proof exists"],
            "relations": [],
            "source_refs": [],
            "verification_status": "partial",
            "usefulness_score": 0.8,
            "recency_score": 0.1,
        },
    ]
    operator = MemoryContextOperator()

    context = operator.synthesize_context(records, "kernel proof")

    assert operator.memory_state(records[0]) == "active"
    assert operator.memory_state(records[1]) == "stale"
    assert context["state_counts"]["active"] == 1
    assert context["state_counts"]["stale"] == 1
    assert context["fusion_candidates"][0]["ids"] == ["KT-1", "KT-2"]


def test_relevance_score_rewards_matching_terms() -> None:
    record = {
        "title": "Kernel memory tile",
        "summary": "Proof and memory for AIONE.",
        "tags": ["kernel", "memory"],
        "claims": ["proof exists"],
        "relations": [],
        "source_refs": [],
        "verification_status": "partial",
    }

    assert relevance_score(record, "kernel proof") > relevance_score(record, "unrelated")
