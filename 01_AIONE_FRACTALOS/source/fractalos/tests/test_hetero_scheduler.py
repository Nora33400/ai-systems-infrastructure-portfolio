from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_tile_os.core.hetero_scheduler import assign_jobs
from omega_tile_os.core.state import ensure_workspace


class HeterogeneousSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scheduler_prefers_gpu_for_vector_jobs(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "telemetry": {
                "cpu": {"utilization": 0.42},
                "gpus": [
                    {"name": "RTX 4060", "temperature_c": 50.0, "utilization": 0.05, "memory_utilization": 0.04, "power_draw_w": 30.0, "power_limit_w": 115.0},
                    {"name": "RTX 3060", "temperature_c": 60.0, "utilization": 0.25, "memory_utilization": 0.10, "power_draw_w": 60.0, "power_limit_w": 170.0},
                ],
            },
            "formulas": {"cpu_headroom": 0.82, "memory_guard": 0.50},
            "recommendations": {"recommended_concurrency": 8},
            "learned_profile": {"mode": "calibrated-balanced"},
        }
        jobs = [{"job_id": "matmul", "vectorizable": True, "complexity": 0.8, "risk": 0.2, "resource_estimate": 2.0}]

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            result = assign_jobs(self.workspace, jobs)

        self.assertEqual(result["placements"][0]["target_kind"], "gpu")
        self.assertEqual(result["placements"][0]["target_device"], "gpu.1")

    def test_scheduler_prefers_cpu_for_latency_sensitive_jobs(self) -> None:
        fake_report = {
            "mode": "safe-adaptive",
            "telemetry": {
                "cpu": {"utilization": 0.10},
                "gpus": [
                    {"name": "RTX 4060", "temperature_c": 66.0, "utilization": 0.40, "memory_utilization": 0.20, "power_draw_w": 70.0, "power_limit_w": 115.0},
                ],
            },
            "formulas": {"cpu_headroom": 0.86, "memory_guard": 0.62},
            "recommendations": {"recommended_concurrency": 10},
            "learned_profile": {"mode": "safe-adaptive"},
        }
        jobs = [{"job_id": "router", "latency_sensitive": True, "complexity": 0.3, "risk": 0.1, "resource_estimate": 0.5}]

        with patch("omega_tile_os.core.hetero_scheduler.PerformanceGovernor.report", return_value=fake_report):
            result = assign_jobs(self.workspace, jobs)

        self.assertEqual(result["placements"][0]["target_kind"], "cpu")
        self.assertEqual(result["placements"][0]["target_device"], "cpu.local")


if __name__ == "__main__":
    unittest.main()
