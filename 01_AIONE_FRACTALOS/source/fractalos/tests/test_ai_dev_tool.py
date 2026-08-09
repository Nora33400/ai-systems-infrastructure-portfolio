from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.ai_dev_tool import ai_dev_catalog, ai_dev_plan, score_improvement
from omega_tile_os.core.state import ensure_workspace, load_perf_state, save_perf_state


class AiDevToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        ensure_workspace(self.workspace)
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"] = {
            "telemetry": {},
            "formulas": {
                "cpu_headroom": 0.9,
                "gpu_headroom": 0.9,
                "cpu_pressure": 0.12,
                "gpu_pressure": 0.1,
                "memory_guard": 0.86,
                "thermal_envelope": 0.9,
                "stability_index": 0.82,
                "throughput_index": 0.86,
            },
            "recommendations": {
                "recommended_concurrency": 4,
                "recommended_planner_top_k": 4,
                "recommended_resource_limit": 10.0,
                "recommended_hot_budget_bytes": 262144,
                "recommended_warm_budget_bytes": 1048576,
                "risk_level": "low",
            },
        }
        save_perf_state(self.workspace, perf_state)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ai_dev_catalog_contains_one_hundred_local_improvements(self) -> None:
        result = ai_dev_catalog()
        self.assertEqual(result["total_catalog"], 100)
        self.assertEqual(result["count"], 100)
        self.assertTrue(all(item["local_only"] for item in result["items"]))

    def test_score_improvement_is_bounded(self) -> None:
        item = ai_dev_catalog(limit=1)["items"][0]
        score = score_improvement(item, {"doctor_counts": {"warn": 1, "fail": 0}, "stability_index": 0.7, "risk_level": "elevated"})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_ai_dev_plan_writes_report_and_can_queue_workloads(self) -> None:
        result = ai_dev_plan(self.workspace, focus="testing", limit=4, queue=True)
        self.assertEqual(result["selected_count"], 4)
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertGreaterEqual(len(result["queued"]), 1)
        self.assertTrue(all("priority_score" in item for item in result["selected"]))


if __name__ == "__main__":
    unittest.main()
