from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_tile_os.core.future_fabric import execute_future_plan, orchestrate_jobs
from omega_tile_os.core.state import ensure_workspace


class FutureFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_orchestration_builds_multiple_waves(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "learned_profile": {"mode": "safe-adaptive"},
            "telemetry": {
                "cpu": {"utilization": 0.18},
                "gpus": [
                    {"name": "RTX 4060", "temperature_c": 49.0, "utilization": 0.03, "memory_utilization": 0.02, "power_draw_w": 25.0, "power_limit_w": 115.0},
                    {"name": "RTX 3060", "temperature_c": 52.0, "utilization": 0.08, "memory_utilization": 0.04, "power_draw_w": 35.0, "power_limit_w": 170.0},
                ],
            },
            "formulas": {
                "cpu_headroom": 0.82,
                "gpu_headroom": 0.74,
                "cpu_pressure": 0.22,
                "gpu_pressure": 0.08,
                "memory_guard": 0.52,
                "thermal_envelope": 0.78,
                "stability_index": 0.44,
                "throughput_index": 0.59,
            },
            "recommendations": {
                "recommended_concurrency": 6,
                "recommended_planner_top_k": 6,
                "recommended_resource_limit": 9.8,
                "recommended_hot_budget_bytes": 300000,
                "recommended_warm_budget_bytes": 1500000,
                "risk_level": "elevated",
            },
        }
        jobs = [
            {"job_id": "a", "vectorizable": True, "resource_estimate": 2.2, "complexity": 0.7, "risk": 0.15},
            {"job_id": "b", "latency_sensitive": True, "serial": True, "resource_estimate": 0.7, "complexity": 0.2, "risk": 0.05},
            {"job_id": "c", "resource_estimate": 1.3, "complexity": 0.5, "risk": 0.2},
            {"job_id": "d", "vectorizable": True, "resource_estimate": 2.0, "complexity": 0.6, "risk": 0.12},
            {"job_id": "e", "resource_estimate": 1.1, "complexity": 0.4, "risk": 0.08},
        ]

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            orchestration = orchestrate_jobs(self.workspace, jobs)

        self.assertGreaterEqual(len(orchestration["waves"]), 1)
        self.assertEqual(sum(len(wave["jobs"]) for wave in orchestration["waves"]), len(jobs))

    def test_future_run_stops_when_predicted_stability_is_too_low(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "learned_profile": {"mode": "safe-adaptive"},
            "telemetry": {
                "cpu": {"utilization": 0.86},
                "gpus": [
                    {"name": "RTX 4060", "temperature_c": 74.0, "utilization": 0.78, "memory_utilization": 0.61, "power_draw_w": 100.0, "power_limit_w": 115.0},
                ],
            },
            "formulas": {
                "cpu_headroom": 0.22,
                "gpu_headroom": 0.12,
                "cpu_pressure": 0.81,
                "gpu_pressure": 0.66,
                "memory_guard": 0.09,
                "thermal_envelope": 0.19,
                "stability_index": 0.14,
                "throughput_index": 0.24,
            },
            "recommendations": {
                "recommended_concurrency": 2,
                "recommended_planner_top_k": 2,
                "recommended_resource_limit": 3.2,
                "recommended_hot_budget_bytes": 262144,
                "recommended_warm_budget_bytes": 1048576,
                "risk_level": "critical",
            },
        }
        jobs = [{"job_id": "danger", "vectorizable": True, "resource_estimate": 3.5, "complexity": 0.9, "risk": 0.8}]

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            with patch("omega_tile_os.core.future_fabric.PerformanceGovernor.report", return_value=fake_report):
                result = execute_future_plan(self.workspace, jobs)

        self.assertEqual(result["executed_waves"], [])
        self.assertIn("low predicted stability", result["stop_reason"])

    def test_orchestration_respects_dependency_order(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "learned_profile": {"mode": "safe-adaptive"},
            "telemetry": {
                "cpu": {"utilization": 0.18},
                "gpus": [
                    {"name": "RTX 4060", "temperature_c": 49.0, "utilization": 0.03, "memory_utilization": 0.02, "power_draw_w": 25.0, "power_limit_w": 115.0},
                ],
            },
            "formulas": {
                "cpu_headroom": 0.82,
                "gpu_headroom": 0.74,
                "cpu_pressure": 0.22,
                "gpu_pressure": 0.08,
                "memory_guard": 0.52,
                "thermal_envelope": 0.78,
                "stability_index": 0.44,
                "throughput_index": 0.59,
            },
            "recommendations": {
                "recommended_concurrency": 4,
                "recommended_planner_top_k": 4,
                "recommended_resource_limit": 9.8,
                "recommended_hot_budget_bytes": 300000,
                "recommended_warm_budget_bytes": 1500000,
                "risk_level": "elevated",
            },
        }
        jobs = [
            {"job_id": "ingest", "resource_estimate": 0.8, "complexity": 0.2, "risk": 0.1},
            {"job_id": "embed", "vectorizable": True, "resource_estimate": 2.0, "complexity": 0.7, "risk": 0.2, "depends_on": ["ingest"]},
            {"job_id": "serve", "latency_sensitive": True, "resource_estimate": 0.6, "complexity": 0.25, "risk": 0.08, "depends_on": ["embed"]},
        ]

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            orchestration = orchestrate_jobs(self.workspace, jobs)

        flattened = [(wave["wave_id"], job["job_id"]) for wave in orchestration["waves"] for job in wave["jobs"]]
        order = {job_id: wave_id for wave_id, job_id in flattened}
        self.assertLessEqual(order["ingest"], order["embed"])
        self.assertLessEqual(order["embed"], order["serve"])


if __name__ == "__main__":
    unittest.main()
