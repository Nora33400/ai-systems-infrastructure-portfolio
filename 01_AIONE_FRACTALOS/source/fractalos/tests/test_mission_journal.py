from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_tile_os.core.chrono_mesh import checkpoint_mission, mission_journal_report, replay_mission
from omega_tile_os.core.state import ensure_workspace


class MissionJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self.jobs = [
            {"job_id": "ingest", "resource_estimate": 0.7, "complexity": 0.2, "risk": 0.1},
            {"job_id": "embed", "vectorizable": True, "resource_estimate": 2.2, "complexity": 0.8, "risk": 0.2, "depends_on": ["ingest"]},
            {"job_id": "serve", "latency_sensitive": True, "resource_estimate": 0.6, "complexity": 0.25, "risk": 0.08, "depends_on": ["embed"]},
        ]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_checkpoint_writes_journal_entry(self) -> None:
        fake_execution = {
            "stop_reason": "completed",
            "executed_waves": [{"wave_id": "wave-001"}],
            "mission_snapshots": [{"wave_id": "wave-001", "completed_jobs": ["ingest", "embed", "serve"]}],
        }

        with patch("omega_tile_os.core.chrono_mesh.execute_future_plan", return_value=fake_execution):
            checkpoint = checkpoint_mission(self.workspace, self.jobs)

        report = mission_journal_report(self.workspace)
        self.assertEqual(report["mission_count"], 1)
        self.assertIn(checkpoint["mission_id"], report["missions"])

    def test_replay_skips_completed_jobs_before_from_job(self) -> None:
        fake_execution = {
            "stop_reason": "completed",
            "executed_waves": [],
            "mission_snapshots": [],
        }
        with patch("omega_tile_os.core.chrono_mesh.execute_future_plan", return_value=fake_execution):
            checkpoint_mission(self.workspace, self.jobs)
            replay = replay_mission(self.workspace, self.jobs, from_job="serve")

        self.assertEqual(replay["replay"]["already_completed"], ["embed", "ingest"])
        self.assertEqual(replay["replay"]["replayed_jobs"], ["serve"])


if __name__ == "__main__":
    unittest.main()
