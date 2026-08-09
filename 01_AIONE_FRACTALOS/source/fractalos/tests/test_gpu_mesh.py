from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_tile_os.core.gpu_runtime import gpu_execute_stub
from omega_tile_os.core.mesh_federation import mesh_accept_import, mesh_adopt_import, mesh_cache_manifest, mesh_cache_report, mesh_compact, mesh_consensus, mesh_daemon_snapshot, mesh_discover_peer, mesh_export_mission, mesh_flush_outbox, mesh_import_bundle, mesh_pulse, mesh_rank_targets, mesh_register, mesh_relay_local, mesh_route_mission, mesh_route_mission_dynamic, mesh_status, mesh_sync_peers, run_mesh_daemon
from omega_tile_os.core.ram_memory import OmegaRAM
from omega_tile_os.core.state import load_mission_journal
from omega_tile_os.core.state import ensure_workspace


class GpuMeshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self.jobs = [{"job_id": "alpha", "resource_estimate": 1.0, "complexity": 0.3, "risk": 0.1}]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_mesh_register_adds_node(self) -> None:
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8890", role="control")
        status = mesh_status(self.workspace)
        self.assertEqual(status["node_count"], 1)
        self.assertEqual(status["nodes"][0]["name"], "node-a")

    def test_gpu_probe_returns_stub_success(self) -> None:
        result = gpu_execute_stub(self.workspace, "gpu.1", size=32)
        self.assertTrue(result["ok"])
        self.assertIn(result["backend"], {"simulated", "torch-cuda"})

    def test_mesh_export_and_import_roundtrip(self) -> None:
        fake_checkpoint = {"mission_id": "abc123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        imported = mesh_import_bundle(self.workspace, Path(exported["export_path"]))
        self.assertEqual(imported["mission_id"], "abc123")

    def test_mesh_relay_local_copies_bundle_to_target_workspace(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "relay123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")
        relayed = mesh_relay_local(self.workspace, Path(exported["export_path"]), target_workspace)
        self.assertEqual(relayed["mission_id"], "relay123")
        self.assertTrue(Path(relayed["import_path"]).exists())
        other_tmp.cleanup()

    def test_mesh_import_pending_then_accept(self) -> None:
        fake_checkpoint = {"mission_id": "pend123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        pending = mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=False)
        self.assertFalse(bool(pending["accepted"]))
        accepted = mesh_accept_import(target_workspace, "pend123")
        self.assertTrue(accepted["accepted"])
        other_tmp.cleanup()

    def test_mesh_adopt_import_executes_accepted_mission(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "adopt123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")
        mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=True)
        adopted = mesh_adopt_import(target_workspace, "adopt123")
        self.assertTrue(adopted["adopted"])
        other_tmp.cleanup()

    def test_mesh_adopt_rebuilds_jobs_from_mission_when_bundle_jobs_missing(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "rebuild123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {
            "graph": {
                "nodes": [
                    {
                        "job_id": "alpha",
                        "wave_id": "wave-001",
                        "depends_on": [],
                    }
                ],
                "edges": [],
            },
            "orchestration": {
                "placements": [
                    {
                        "job_id": "alpha",
                        "resource_estimate": 1.0,
                        "complexity": 0.3,
                        "risk": 0.1,
                    }
                ]
            },
        }
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        export_path = Path(exported["export_path"])
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        payload.pop("jobs", None)
        export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        mesh_import_bundle(target_workspace, export_path, auto_accept=True)
        adopted = mesh_adopt_import(target_workspace, "rebuild123")
        self.assertTrue(adopted["adopted"])
        other_tmp.cleanup()

    def test_mesh_pulse_accepts_and_adopts_pending_imports(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "pulse123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=False)
        result = mesh_pulse(target_workspace)
        self.assertEqual(result["accepted"][0]["mission_id"], "pulse123")
        self.assertTrue(result["adopted"][0]["adopted"])
        other_tmp.cleanup()

    def test_mesh_compact_keeps_most_advanced_state(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "compact123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        export_path = Path(exported["export_path"])
        mesh_import_bundle(target_workspace, export_path, auto_accept=False)
        mesh_import_bundle(target_workspace, export_path, auto_accept=True)
        mesh_adopt_import(target_workspace, "compact123")
        compacted = mesh_compact(target_workspace)
        self.assertEqual(compacted["after"]["inbox"], 1)
        status = mesh_status(target_workspace)
        self.assertEqual(status["inbox"][0]["status"], "adopted")
        other_tmp.cleanup()

    def test_mesh_pulse_processes_high_priority_mission_first(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)

        high_jobs = [{"job_id": "high", "resource_estimate": 2.0, "complexity": 0.9, "risk": 0.9}]
        low_jobs = [{"job_id": "low", "resource_estimate": 0.3, "complexity": 0.1, "risk": 0.05}]
        high_checkpoint = {"mission_id": "high123", "snapshot": {"completed_jobs": ["high"]}}
        low_checkpoint = {"mission_id": "low123", "snapshot": {"completed_jobs": ["low"]}}
        high_mission = {
            "graph": {"nodes": [{"job_id": "high", "criticality": 0.92}], "edges": []},
            "causal_projection": {"wave_count": 3},
            "mission_envelope": {"risk_level": "critical"},
        }
        low_mission = {
            "graph": {"nodes": [{"job_id": "low", "criticality": 0.12}], "edges": []},
            "causal_projection": {"wave_count": 1},
            "mission_envelope": {"risk_level": "steady"},
        }

        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=low_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=low_mission):
                low_export = mesh_export_mission(self.workspace, low_jobs, "node-a")
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=high_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=high_mission):
                high_export = mesh_export_mission(self.workspace, high_jobs, "node-a")

        mesh_import_bundle(target_workspace, Path(low_export["export_path"]), auto_accept=False)
        mesh_import_bundle(target_workspace, Path(high_export["export_path"]), auto_accept=False)
        result = mesh_pulse(target_workspace)
        self.assertEqual(result["accepted"][0]["mission_id"], "high123")
        other_tmp.cleanup()

    def test_run_mesh_daemon_updates_heartbeat(self) -> None:
        result = run_mesh_daemon(self.workspace, interval_s=0.01, max_cycles=2, compact=True)
        daemon = mesh_daemon_snapshot(self.workspace)
        self.assertEqual(daemon["cycle_count"], 2)
        self.assertEqual(result["daemon"]["cycle_count"], 2)
        self.assertIsNotNone(daemon["heartbeat_at"])

    def test_mesh_export_queues_outbox_entry(self) -> None:
        fake_checkpoint = {"mission_id": "queue123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                mesh_export_mission(self.workspace, self.jobs, "node-a")
        status = mesh_status(self.workspace)
        self.assertEqual(status["outbox"][0]["status"], "queued")

    def test_mesh_flush_delivers_outbox_to_registered_node(self) -> None:
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8890", role="control")
        fake_checkpoint = {"mission_id": "flush123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                mesh_export_mission(self.workspace, self.jobs, "node-a")
        with patch("omega_tile_os.core.mesh_federation.mesh_push_bundle", return_value={"mission_id": "flush123", "accepted": {"accepted": True}}):
            flushed = mesh_flush_outbox(self.workspace)
        self.assertEqual(flushed["delivered"][0]["mission_id"], "flush123")
        status = mesh_status(self.workspace)
        self.assertEqual(status["outbox"][0]["status"], "delivered")

    def test_mesh_discover_peer_registers_remote_node(self) -> None:
        remote = {
            "name": "node-remote",
            "endpoint": "http://127.0.0.1:8891",
            "role": "peer",
            "heartbeat_at": "2026-04-19T20:00:00+00:00",
            "capabilities": {"mesh_push": True},
        }
        with patch("omega_tile_os.core.mesh_federation.mesh_fetch_descriptor", return_value=remote):
            with patch("omega_tile_os.core.mesh_federation.mesh_announce_to_peer", return_value={"accepted": True}):
                discovered = mesh_discover_peer(self.workspace, "http://127.0.0.1:8891", "http://127.0.0.1:8890")
        self.assertEqual(discovered["peer"]["name"], "node-remote")
        status = mesh_status(self.workspace)
        self.assertEqual(status["node_count"], 1)

    def test_mesh_sync_peers_refreshes_heartbeat(self) -> None:
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8891", role="peer")
        refreshed = {
            "name": "node-a",
            "endpoint": "http://127.0.0.1:8891",
            "role": "peer",
            "heartbeat_at": "2026-04-19T20:30:00+00:00",
            "capabilities": {"mesh_push": True, "known_nodes": 3},
        }
        with patch("omega_tile_os.core.mesh_federation.mesh_fetch_descriptor", return_value=refreshed):
            synced = mesh_sync_peers(self.workspace)
        self.assertEqual(synced["synced"][0]["heartbeat_at"], "2026-04-19T20:30:00+00:00")

    def test_mesh_rank_targets_prefers_online_remote_peer_when_stronger(self) -> None:
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8891", role="peer")
        registry = mesh_status(self.workspace)
        self.assertEqual(registry["node_count"], 1)
        with patch("omega_tile_os.core.mesh_federation.mesh_descriptor", return_value={
            "name": "local",
            "endpoint": "",
            "capabilities": {
                "risk_level": "critical",
                "recommended_concurrency": 1,
                "recommended_resource_limit": 3.0,
                "stability_index": 0.15,
            },
        }):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value={"mission_envelope": {"recommended_resource_limit": 8.0}}):
                updated = {
                    "name": "node-a",
                    "endpoint": "http://127.0.0.1:8891",
                    "role": "peer",
                    "availability": "online",
                    "capabilities": {
                        "risk_level": "low",
                        "recommended_concurrency": 8,
                        "recommended_resource_limit": 12.0,
                        "stability_index": 0.9,
                    },
                }
                with patch("omega_tile_os.core.mesh_federation._load_registry", return_value={"nodes": {"node-a": updated}, "relays": [], "inbox": [], "outbox": [], "daemon": {}}):
                    ranked = mesh_rank_targets(self.workspace, self.jobs)
        self.assertEqual(ranked["ranked_targets"][0]["name"], "node-a")

    def test_mesh_route_mission_executes_locally_when_local_best(self) -> None:
        with patch("omega_tile_os.core.mesh_federation.mesh_rank_targets", return_value={"ranked_targets": [{"name": "local", "is_local": True, "score": 0.9}]}):
            with patch("omega_tile_os.core.mesh_federation.execute_future_plan", return_value={"stop_reason": "completed"}):
                routed = mesh_route_mission(self.workspace, self.jobs)
        self.assertEqual(routed["route"], "local")
        self.assertEqual(routed["execution"]["stop_reason"], "completed")

    def test_mesh_route_mission_exports_when_remote_best(self) -> None:
        with patch("omega_tile_os.core.mesh_federation.mesh_rank_targets", return_value={"ranked_targets": [{"name": "node-a", "is_local": False, "score": 0.95}]}):
            with patch("omega_tile_os.core.mesh_federation.mesh_export_mission", return_value={"mission_id": "route123", "target_node": "node-a"}):
                with patch("omega_tile_os.core.mesh_federation.mesh_flush_outbox", return_value={"delivered": []}):
                    routed = mesh_route_mission(self.workspace, self.jobs)
        self.assertEqual(routed["route"], "remote")
        self.assertEqual(routed["exported"]["target_node"], "node-a")

    def test_mesh_route_mission_dynamic_migrates_remaining_jobs_to_remote(self) -> None:
        jobs = [
            {"job_id": "ingest", "resource_estimate": 0.7, "complexity": 0.2, "risk": 0.1},
            {"job_id": "embed", "resource_estimate": 2.2, "complexity": 0.8, "risk": 0.2, "depends_on": ["ingest"]},
        ]
        orchestration = {
            "waves": [
                {
                    "wave_id": "wave-001",
                    "jobs": [{"job_id": "ingest", "target_kind": "cpu", "target_device": "cpu.local"}],
                    "predicted_state": {"stability_index": 0.31, "cpu_pressure": 0.4, "gpu_pressure": 0.1},
                },
                {
                    "wave_id": "wave-002",
                    "jobs": [{"job_id": "embed", "target_kind": "gpu", "target_device": "gpu.1", "depends_on": ["ingest"]}],
                    "predicted_state": {"stability_index": 0.18, "cpu_pressure": 0.78, "gpu_pressure": 0.72},
                },
            ]
        }
        rankings = [
            [
                {"name": "local", "is_local": True, "score": 0.8},
                {"name": "node-a", "is_local": False, "score": 0.6},
            ],
            [
                {"name": "node-a", "is_local": False, "score": 0.7},
                {"name": "local", "is_local": True, "score": 0.4},
            ],
        ]
        with patch("omega_tile_os.core.mesh_federation.orchestrate_jobs", return_value=orchestration):
            with patch("omega_tile_os.core.mesh_federation._rank_targets_for_remaining", side_effect=rankings):
                with patch("omega_tile_os.core.mesh_federation.execute_wave_jobs", return_value={"results": [{"job_id": "ingest"}], "completed_jobs": {"ingest"}, "stop_reason": "completed"}):
                    with patch("omega_tile_os.core.mesh_federation.mesh_export_mission", return_value={"mission_id": "dyn123", "target_node": "node-a"}):
                        with patch("omega_tile_os.core.mesh_federation.mesh_flush_outbox", return_value={"delivered": [{"mission_id": "dyn123"}]}):
                            routed = mesh_route_mission_dynamic(self.workspace, jobs)
        self.assertEqual(routed["migration"]["target"]["name"], "node-a")
        self.assertEqual(routed["migration"]["remaining_jobs"], ["embed"])
        self.assertEqual(routed["migration"]["exported"]["target_node"], "node-a")

    def test_mesh_route_mission_dynamic_stays_local_when_local_remains_best(self) -> None:
        orchestration = {
            "waves": [
                {
                    "wave_id": "wave-001",
                    "jobs": [{"job_id": "alpha", "target_kind": "cpu", "target_device": "cpu.local"}],
                    "predicted_state": {"stability_index": 0.4, "cpu_pressure": 0.3, "gpu_pressure": 0.1},
                }
            ]
        }
        with patch("omega_tile_os.core.mesh_federation.orchestrate_jobs", return_value=orchestration):
            with patch("omega_tile_os.core.mesh_federation._rank_targets_for_remaining", return_value=[{"name": "local", "is_local": True, "score": 0.8}]):
                with patch("omega_tile_os.core.mesh_federation.execute_wave_jobs", return_value={"results": [{"job_id": "alpha"}], "completed_jobs": {"alpha"}, "stop_reason": "completed"}):
                    routed = mesh_route_mission_dynamic(self.workspace, self.jobs)
        self.assertIsNone(routed["migration"])
        self.assertEqual(routed["stop_reason"], "completed")

    def test_mesh_adopt_import_merges_inherited_completed_jobs(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "handoff123", "snapshot": {"completed_jobs": ["embed"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "embed"}, {"job_id": "serve"}], "edges": []}}
        jobs = [
            {"job_id": "embed", "resource_estimate": 1.0, "complexity": 0.5, "risk": 0.1},
            {"job_id": "serve", "resource_estimate": 0.3, "complexity": 0.2, "risk": 0.05},
        ]
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(
                    self.workspace,
                    jobs,
                    "node-a",
                    transfer_context={"completed_jobs": ["embed"], "cutover_wave_id": "wave-002"},
                )
        mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=True)
        deterministic_execution = {
            "mission_snapshots": [{"completed_jobs": ["serve"]}],
            "stop_reason": "completed",
            "executed_waves": [{"wave_id": "wave-001"}],
        }
        with patch(
            "omega_tile_os.core.mesh_federation.execute_future_plan",
            return_value=deterministic_execution,
        ):
            adopted = mesh_adopt_import(target_workspace, "handoff123")
        self.assertIn("embed", adopted["completed_jobs"])
        self.assertIn("serve", adopted["completed_jobs"])
        other_tmp.cleanup()

    def test_mesh_import_preserves_memory_capsule(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        fake_checkpoint = {"mission_id": "capsule123", "snapshot": {"completed_jobs": ["alpha"]}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(
                    self.workspace,
                    self.jobs,
                    "node-a",
                    transfer_context={"completed_jobs": ["alpha"]},
                )
        mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=True)
        journal = load_mission_journal(target_workspace)
        capsule = journal["missions"]["capsule123"]["memory_capsule"]
        self.assertIn("completed_jobs", capsule)
        self.assertIn("ram_context", capsule)
        other_tmp.cleanup()

    def test_mesh_adopt_import_hydrates_ram_from_capsule(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        OmegaRAM(self.workspace).put_text("alpha.note", "mission capsule payload", source="test")
        fake_checkpoint = {"mission_id": "hydrate123", "snapshot": {"completed_jobs": []}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")
        mesh_import_bundle(target_workspace, Path(exported["export_path"]), auto_accept=True)
        mesh_adopt_import(target_workspace, "hydrate123")
        restored = OmegaRAM(target_workspace).get("alpha.note")
        self.assertTrue(restored["found"])
        self.assertIn("mission capsule payload", restored["content"])
        other_tmp.cleanup()

    def test_shared_mesh_cache_reuses_payloads_on_second_export(self) -> None:
        OmegaRAM(self.workspace).put_text("alpha.note", "mission capsule payload", source="test")
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8890", role="peer")
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}

        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value={"mission_id": "cache123a", "snapshot": {"completed_jobs": []}}):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                first = mesh_export_mission(self.workspace, self.jobs, "node-a")
        first_payload = json.loads(Path(first["export_path"]).read_text(encoding="utf-8"))
        with patch("omega_tile_os.core.mesh_federation.mesh_push_bundle", return_value={"mission_id": "cache123", "accepted": {"accepted": True}}):
            mesh_flush_outbox(self.workspace)

        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value={"mission_id": "cache123b", "snapshot": {"completed_jobs": []}}):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                second = mesh_export_mission(self.workspace, self.jobs, "node-a")

        second_payload = json.loads(Path(second["export_path"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(first_payload["cache_stats"]["transferred_payloads"], 1)
        self.assertGreaterEqual(second_payload["cache_stats"]["reused_payloads"], 1)
        self.assertNotIn("content", second_payload["memory_capsule"]["ram_payloads"][0])
        self.assertTrue(second_payload["memory_capsule"]["ram_payloads"][0]["cached"])

    def test_mesh_adopt_import_hydrates_from_shared_cache_when_payload_body_is_omitted(self) -> None:
        other_tmp = tempfile.TemporaryDirectory()
        target_workspace = Path(other_tmp.name)
        ensure_workspace(target_workspace)
        OmegaRAM(self.workspace).put_text("alpha.note", "mission capsule payload", source="test")
        fake_checkpoint = {"mission_id": "cachehydrate123", "snapshot": {"completed_jobs": []}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                exported = mesh_export_mission(self.workspace, self.jobs, "node-a")

        export_path = Path(exported["export_path"])
        mesh_import_bundle(target_workspace, export_path, auto_accept=True)
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        payload["memory_capsule"]["ram_payloads"][0].pop("content", None)
        payload["memory_capsule"]["ram_payloads"][0]["cached"] = True
        export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        mesh_import_bundle(target_workspace, export_path, auto_accept=True)
        mesh_adopt_import(target_workspace, "cachehydrate123")
        restored = OmegaRAM(target_workspace).get("alpha.note")
        self.assertTrue(restored["found"])
        self.assertIn("mission capsule payload", restored["content"])

        report = mesh_cache_report(target_workspace)
        self.assertGreaterEqual(report["object_counts"]["ram"], 1)
        other_tmp.cleanup()

    def test_mesh_cache_manifest_lists_known_fingerprints(self) -> None:
        OmegaRAM(self.workspace).put_text("alpha.note", "mission capsule payload", source="test")
        fake_checkpoint = {"mission_id": "manifest123", "snapshot": {"completed_jobs": []}}
        fake_mission = {"graph": {"nodes": [{"job_id": "alpha"}], "edges": []}}
        with patch("omega_tile_os.core.mesh_federation.checkpoint_mission", return_value=fake_checkpoint):
            with patch("omega_tile_os.core.mesh_federation.compile_mission_graph", return_value=fake_mission):
                mesh_export_mission(self.workspace, self.jobs, "node-a")
        manifest = mesh_cache_manifest(self.workspace)
        self.assertGreaterEqual(manifest["entry_count"], 1)
        self.assertGreaterEqual(len(manifest["fingerprints"]), 1)

    def test_mesh_consensus_absorbs_remote_cache_manifest(self) -> None:
        mesh_register(self.workspace, "node-a", "http://127.0.0.1:8891", role="peer")
        remote_manifest = {
            "node_name": "node-a",
            "entry_count": 2,
            "fingerprints": ["abc123", "def456"],
            "categories": {"ram": 1, "manifests": 1},
        }
        with patch("omega_tile_os.core.mesh_federation.mesh_fetch_cache_manifest", return_value=remote_manifest):
            result = mesh_consensus(self.workspace, node_name="node-a")
        self.assertEqual(result["synced"][0]["known_entries"], 2)
        report = mesh_cache_report(self.workspace)
        self.assertEqual(report["per_node"]["node-a"], 2)


if __name__ == "__main__":
    unittest.main()
