from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.autonomy_runtime import autonomy_report, evolve_ecosystem, run_workloads, submit_workload
from omega_tile_os.core.ram_memory import OmegaRAM
from omega_tile_os.core.state import ensure_workspace, load_autonomy_state


class AutonomyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_submit_workload_records_queue_entry(self) -> None:
        workload = submit_workload(self.workspace, "code", "Build parser", "Add a safer parser pipeline.")
        state = load_autonomy_state(self.workspace)
        self.assertEqual(workload["status"], "queued")
        self.assertEqual(state["metrics"]["submitted"], 1)
        self.assertEqual(state["workloads"][0]["domain"], "code")

    def test_run_workloads_generates_artifacts_and_ram_entries(self) -> None:
        workload = submit_workload(self.workspace, "research", "Map signals", "Study workspace event signals.")
        result = run_workloads(self.workspace, max_items=1)
        self.assertEqual(len(result["processed"]), 1)
        files = result["processed"][0]["files"]
        self.assertEqual(len(files), 3)
        restored = OmegaRAM(self.workspace).get(f"autonomy::research::{workload['id']}::RESEARCH_MAP.md")
        self.assertTrue(restored["found"])
        report = autonomy_report(self.workspace)
        self.assertEqual(report["status_counts"]["done"], 1)

    def test_evolve_ecosystem_queues_followups_for_missing_domains(self) -> None:
        submit_workload(self.workspace, "code", "Code lane", "Strengthen code execution.")
        run_workloads(self.workspace, max_items=1)
        evolution = evolve_ecosystem(self.workspace, queue_followups=True)
        self.assertTrue(Path(evolution["report_path"]).exists())
        self.assertGreaterEqual(len(evolution["queued"]), 1)
        queued_domains = {item["domain"] for item in evolution["queued"]}
        self.assertIn("research", queued_domains)
        report = autonomy_report(self.workspace)
        self.assertGreaterEqual(report["status_counts"]["queued"], 1)


if __name__ == "__main__":
    unittest.main()
