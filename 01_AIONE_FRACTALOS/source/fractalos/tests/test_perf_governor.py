from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.perf_governor import GovernorInputs, PerformanceGovernor, performance_formulas
from omega_tile_os.core.state import ensure_workspace, load_config


class PerformanceGovernorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self.config = load_config(self.workspace)
        self.governor = PerformanceGovernor(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stability_drops_when_thermal_headroom_collapses(self) -> None:
        cool = GovernorInputs(
            cpu_utilization=0.40,
            memory_utilization=0.42,
            cpu_temp_c=48.0,
            cpu_frequency_ratio=0.65,
            gpu_utilization=0.28,
            gpu_temp_c=46.0,
            gpu_memory_utilization=0.22,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=20 * 1024 * 1024 * 1024,
        )
        hot = GovernorInputs(
            cpu_utilization=0.88,
            memory_utilization=0.74,
            cpu_temp_c=80.0,
            cpu_frequency_ratio=0.95,
            gpu_utilization=0.84,
            gpu_temp_c=76.0,
            gpu_memory_utilization=0.81,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=6 * 1024 * 1024 * 1024,
        )

        cool_formulas = performance_formulas(cool, self.config)
        hot_formulas = performance_formulas(hot, self.config)

        self.assertGreater(cool_formulas["stability_index"], hot_formulas["stability_index"])
        self.assertGreater(cool_formulas["thermal_envelope"], hot_formulas["thermal_envelope"])
        self.assertGreater(cool_formulas["throughput_index"], hot_formulas["throughput_index"])

    def test_recommendations_reduce_concurrency_under_pressure(self) -> None:
        safe_inputs = GovernorInputs(
            cpu_utilization=0.35,
            memory_utilization=0.33,
            cpu_temp_c=47.0,
            cpu_frequency_ratio=0.55,
            gpu_utilization=0.20,
            gpu_temp_c=45.0,
            gpu_memory_utilization=0.18,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=22 * 1024 * 1024 * 1024,
        )
        stressed_inputs = GovernorInputs(
            cpu_utilization=0.96,
            memory_utilization=0.83,
            cpu_temp_c=81.0,
            cpu_frequency_ratio=0.99,
            gpu_utilization=0.91,
            gpu_temp_c=77.0,
            gpu_memory_utilization=0.88,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=3 * 1024 * 1024 * 1024,
        )

        safe_formulas = performance_formulas(safe_inputs, self.config)
        stressed_formulas = performance_formulas(stressed_inputs, self.config)
        safe_reco = self.governor._recommendations(safe_inputs, safe_formulas)
        stressed_reco = self.governor._recommendations(stressed_inputs, stressed_formulas)

        self.assertGreater(safe_reco["recommended_concurrency"], stressed_reco["recommended_concurrency"])
        self.assertGreater(safe_reco["recommended_resource_limit"], stressed_reco["recommended_resource_limit"])
        self.assertIn(stressed_reco["risk_level"], {"elevated", "critical"})

    def test_cache_budget_only_grows_when_memory_guard_is_good(self) -> None:
        roomy_inputs = GovernorInputs(
            cpu_utilization=0.30,
            memory_utilization=0.28,
            cpu_temp_c=50.0,
            cpu_frequency_ratio=0.60,
            gpu_utilization=0.18,
            gpu_temp_c=44.0,
            gpu_memory_utilization=0.12,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=24 * 1024 * 1024 * 1024,
        )
        tight_inputs = GovernorInputs(
            cpu_utilization=0.54,
            memory_utilization=0.80,
            cpu_temp_c=58.0,
            cpu_frequency_ratio=0.72,
            gpu_utilization=0.24,
            gpu_temp_c=51.0,
            gpu_memory_utilization=0.25,
            logical_cores=16,
            total_memory_bytes=32 * 1024 * 1024 * 1024,
            available_memory_bytes=4 * 1024 * 1024 * 1024,
        )

        roomy_formulas = performance_formulas(roomy_inputs, self.config)
        tight_formulas = performance_formulas(tight_inputs, self.config)
        roomy_reco = self.governor._recommendations(roomy_inputs, roomy_formulas)
        tight_reco = self.governor._recommendations(tight_inputs, tight_formulas)

        self.assertGreater(roomy_reco["recommended_hot_budget_bytes"], tight_reco["recommended_hot_budget_bytes"])
        self.assertGreater(roomy_reco["recommended_warm_budget_bytes"], tight_reco["recommended_warm_budget_bytes"])

    def test_hysteresis_limits_upward_jumps(self) -> None:
        previous = {
            "recommended_concurrency": 4,
            "recommended_planner_top_k": 4,
            "recommended_resource_limit": 8.0,
            "recommended_hot_budget_bytes": 300000,
            "recommended_warm_budget_bytes": 1600000,
            "risk_level": "low",
        }
        current = {
            "recommended_concurrency": 9,
            "recommended_planner_top_k": 9,
            "recommended_resource_limit": 12.0,
            "recommended_hot_budget_bytes": 600000,
            "recommended_warm_budget_bytes": 3200000,
            "risk_level": "low",
        }

        smoothed = self.governor._smooth_recommendations(current, previous)

        self.assertEqual(smoothed["recommended_concurrency"], 5)
        self.assertEqual(smoothed["recommended_planner_top_k"], 5)
        self.assertEqual(smoothed["recommended_resource_limit"], 8.64)
        self.assertEqual(smoothed["recommended_hot_budget_bytes"], 330000)
        self.assertEqual(smoothed["recommended_warm_budget_bytes"], 1760000)


if __name__ == "__main__":
    unittest.main()
