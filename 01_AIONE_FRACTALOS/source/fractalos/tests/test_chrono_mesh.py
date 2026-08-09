from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_tile_os.core.chrono_mesh import compile_mission_graph, simulate_mission_recovery
from omega_tile_os.core.state import ensure_workspace


class ChronoMeshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self.jobs = [
            {"job_id": "ingest", "resource_estimate": 0.7, "complexity": 0.2, "risk": 0.1},
            {"job_id": "embed", "vectorizable": True, "resource_estimate": 2.2, "complexity": 0.8, "risk": 0.2, "depends_on": ["ingest"]},
            {"job_id": "serve", "latency_sensitive": True, "serial": True, "resource_estimate": 0.6, "complexity": 0.25, "risk": 0.08, "depends_on": ["embed"]},
        ]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compile_mission_graph_creates_dependency_edges(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "learned_profile": {"mode": "safe-adaptive"},
            "telemetry": {"cpu": {"utilization": 0.12}, "gpus": []},
            "formulas": {
                "cpu_headroom": 0.82,
                "gpu_headroom": 0.7,
                "cpu_pressure": 0.22,
                "gpu_pressure": 0.0,
                "memory_guard": 0.45,
                "thermal_envelope": 0.75,
                "stability_index": 0.41,
                "throughput_index": 0.56,
            },
            "recommendations": {
                "recommended_concurrency": 6,
                "recommended_planner_top_k": 6,
                "recommended_resource_limit": 10.0,
                "recommended_hot_budget_bytes": 280000,
                "recommended_warm_budget_bytes": 1200000,
                "risk_level": "elevated",
            },
        }

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            with patch("omega_tile_os.core.chrono_mesh.PerformanceGovernor.report", return_value=fake_report):
                mission = compile_mission_graph(self.workspace, self.jobs)

        self.assertEqual(len(mission["graph"]["nodes"]), 3)
        self.assertEqual(len(mission["graph"]["edges"]), 2)
        self.assertEqual(mission["graph"]["edges"][0]["from"], "ingest")

    def test_recovery_marks_descendants_of_failed_job(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "learned_profile": {"mode": "safe-adaptive"},
            "telemetry": {"cpu": {"utilization": 0.12}, "gpus": []},
            "formulas": {
                "cpu_headroom": 0.82,
                "gpu_headroom": 0.7,
                "cpu_pressure": 0.22,
                "gpu_pressure": 0.0,
                "memory_guard": 0.45,
                "thermal_envelope": 0.75,
                "stability_index": 0.41,
                "throughput_index": 0.56,
            },
            "recommendations": {
                "recommended_concurrency": 6,
                "recommended_planner_top_k": 6,
                "recommended_resource_limit": 10.0,
                "recommended_hot_budget_bytes": 280000,
                "recommended_warm_budget_bytes": 1200000,
                "risk_level": "elevated",
            },
        }
        fake_execution = {"executed_waves": [], "stop_reason": "completed"}

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            with patch("omega_tile_os.core.chrono_mesh.PerformanceGovernor.report", return_value=fake_report):
                with patch("omega_tile_os.core.chrono_mesh.execute_future_plan", return_value=fake_execution):
                    recovery = simulate_mission_recovery(self.workspace, self.jobs, failed_jobs=["embed"])

        self.assertEqual(recovery["failed_jobs"], ["embed"])
        self.assertEqual(recovery["recovery_actions"][0]["job_id"], "embed")
        self.assertIn("serve", recovery["recovery_actions"][0]["blocked_descendants"])


if __name__ == "__main__":
    unittest.main()
