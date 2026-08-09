from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.autonomy_runtime import autonomy_report
from unittest.mock import patch

from omega_tile_os.core.codex_worker import run_worker_sessions, submit_worker_session, worker_report, worker_to_mission
from omega_tile_os.core.ram_memory import OmegaRAM
from omega_tile_os.core.state import ensure_workspace, load_worker_state


class CodexWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_submit_worker_session_records_queue_entry(self) -> None:
        session = submit_worker_session(self.workspace, "builder", "Implement lane", "Plan and verify a coding lane.")
        state = load_worker_state(self.workspace)
        self.assertEqual(session["status"], "queued")
        self.assertEqual(state["metrics"]["submitted"], 1)
        self.assertEqual(state["sessions"][0]["mode"], "builder")

    def test_run_worker_sessions_generates_outputs_and_memory(self) -> None:
        session = submit_worker_session(self.workspace, "researcher", "Map evidence", "Design a research trace.")
        result = run_worker_sessions(self.workspace, max_items=1, auto_queue_autonomy=False)
        self.assertEqual(len(result["processed"]), 1)
        files = result["processed"][0]["files"]
        self.assertEqual(len(files), 5)
        restored = OmegaRAM(self.workspace).get(f"worker::researcher::{session['id']}::PLAN.md")
        self.assertTrue(restored["found"])
        report = worker_report(self.workspace)
        self.assertEqual(report["status_counts"]["done"], 1)

    def test_run_worker_sessions_can_spawn_autonomy_followup(self) -> None:
        submit_worker_session(self.workspace, "automator", "Automation lane", "Create a safer automation lane.")
        result = run_worker_sessions(self.workspace, max_items=1, auto_queue_autonomy=True)
        self.assertEqual(len(result["spawned_autonomy"]), 1)
        auto = autonomy_report(self.workspace)
        self.assertGreaterEqual(auto["status_counts"]["queued"], 1)

    def test_worker_to_mission_bridges_done_session(self) -> None:
        session = submit_worker_session(self.workspace, "builder", "Mission bridge", "Bridge worker to mission.")
        run_worker_sessions(self.workspace, max_items=1, auto_queue_autonomy=False)
        with patch("omega_tile_os.core.codex_worker.mesh_route_mission_dynamic", return_value={"mode": "dynamic-cluster-routing"}):
            bridged = worker_to_mission(self.workspace, str(session["id"]), route="dynamic")
        self.assertTrue(bridged["bridged"])
        self.assertEqual(bridged["execution"]["mode"], "dynamic-cluster-routing")


if __name__ == "__main__":
    unittest.main()
