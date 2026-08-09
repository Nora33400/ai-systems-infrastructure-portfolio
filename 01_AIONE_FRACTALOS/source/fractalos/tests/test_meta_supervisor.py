from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.autonomy_runtime import autonomy_report
from omega_tile_os.core.codex_worker import worker_report
from omega_tile_os.core.meta_supervisor import supervisor_plan, supervisor_report, supervisor_run
from omega_tile_os.core.state import ensure_workspace, load_perf_state, save_perf_state


class MetaSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self._force_perf("low", 0.82)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _force_perf(self, risk: str, stability: float) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"] = {
            "telemetry": {},
            "formulas": {
                "cpu_headroom": 0.9,
                "gpu_headroom": 0.9,
                "cpu_pressure": 0.1,
                "gpu_pressure": 0.1,
                "memory_guard": 0.9,
                "thermal_envelope": 0.9,
                "stability_index": stability,
                "throughput_index": 0.8,
            },
            "recommendations": {
                "recommended_concurrency": 4,
                "recommended_planner_top_k": 4,
                "recommended_resource_limit": 10.0,
                "recommended_hot_budget_bytes": 262144,
                "recommended_warm_budget_bytes": 1048576,
                "risk_level": risk,
            },
        }
        save_perf_state(self.workspace, perf_state)

    def test_supervisor_selects_agents_when_growth_is_clean(self) -> None:
        plan = supervisor_plan(self.workspace)
        self.assertEqual(plan["mode"], "expand")
        self.assertGreater(plan["clean_growth_index"], 0.6)
        self.assertGreaterEqual(len(plan["selected_agents"]), 1)

    def test_supervisor_blocks_expansion_under_critical_risk(self) -> None:
        self._force_perf("critical", 0.12)
        plan = supervisor_plan(self.workspace)
        self.assertEqual(plan["mode"], "protect")
        self.assertEqual(plan["selected_agents"], [])

    def test_supervisor_run_queues_balanced_agents_and_archives_report(self) -> None:
        result = supervisor_run(self.workspace, max_lanes=2, queue=True)
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertGreaterEqual(len(result["queued_workers"]), 1)
        self.assertGreaterEqual(worker_report(self.workspace)["status_counts"].get("queued", 0), 1)
        self.assertGreaterEqual(autonomy_report(self.workspace)["status_counts"].get("queued", 0), 1)
        report = supervisor_report(self.workspace)
        self.assertEqual(report["report_count"], 1)


if __name__ == "__main__":
    unittest.main()
