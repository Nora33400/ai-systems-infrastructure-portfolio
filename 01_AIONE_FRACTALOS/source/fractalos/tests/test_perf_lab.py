from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.perf_lab import build_benchmark_policy, calibration_report, derive_learned_profile, summarize_history
from omega_tile_os.core.state import ensure_workspace, load_perf_state, save_perf_state


class PerformanceLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_policy_stops_on_persistent_critical_risk(self) -> None:
        report = {
            "formulas": {
                "stability_index": 0.24,
                "throughput_index": 0.32,
                "thermal_envelope": 0.31,
                "cpu_pressure": 0.81,
            },
            "recommendations": {
                "recommended_concurrency": 3,
                "risk_level": "critical",
            },
        }
        previous = {"risk_level": "elevated"}

        policy = build_benchmark_policy(report, previous)

        self.assertTrue(policy.should_stop)
        self.assertEqual(policy.reason, "critical risk persisted")

    def test_policy_runs_when_headroom_is_acceptable(self) -> None:
        report = {
            "formulas": {
                "stability_index": 0.58,
                "throughput_index": 0.61,
                "thermal_envelope": 0.72,
                "cpu_pressure": 0.29,
            },
            "recommendations": {
                "recommended_concurrency": 8,
                "risk_level": "low",
            },
        }

        policy = build_benchmark_policy(report)

        self.assertFalse(policy.should_stop)
        self.assertGreaterEqual(policy.workers, 1)
        self.assertGreaterEqual(policy.batch_size, 128)

    def test_history_summary_reports_pressure_wave(self) -> None:
        history = [
            {
                "formulas": {"stability_index": 0.6, "throughput_index": 0.65, "cpu_pressure": 0.2},
                "recommendations": {"risk_level": "low"},
            },
            {
                "formulas": {"stability_index": 0.5, "throughput_index": 0.55, "cpu_pressure": 0.4},
                "recommendations": {"risk_level": "elevated"},
            },
            {
                "formulas": {"stability_index": 0.45, "throughput_index": 0.5, "cpu_pressure": 0.35},
                "recommendations": {"risk_level": "elevated"},
            },
        ]

        summary = summarize_history(history)

        self.assertEqual(summary["risk_peak"], "elevated")
        self.assertGreater(summary["pressure_wave"], 0.0)
        self.assertLessEqual(summary["stability_min"], summary["stability_mean"])

    def test_learned_profile_stays_safe_under_mixed_campaigns(self) -> None:
        campaigns = [
            {"summary": {"stability_mean": 0.44, "throughput_mean": 0.55, "pressure_wave": 0.07, "risk_peak": "elevated"}},
            {"summary": {"stability_mean": 0.47, "throughput_mean": 0.58, "pressure_wave": 0.05, "risk_peak": "low"}},
        ]

        profile = derive_learned_profile(campaigns)

        self.assertIsNotNone(profile)
        self.assertIn(profile["mode"], {"calibrated-safe", "safe-adaptive"})
        self.assertGreaterEqual(profile["performance_governor"]["thermal_unknown_penalty"], 0.82)

    def test_calibration_report_reads_persisted_profile(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["campaigns"] = [
            {"summary": {"stability_mean": 0.55, "throughput_mean": 0.63, "pressure_wave": 0.04, "risk_peak": "low"}}
        ]
        perf_state["learned_profile"] = derive_learned_profile(perf_state["campaigns"])
        save_perf_state(self.workspace, perf_state)

        report = calibration_report(self.workspace)

        self.assertEqual(report["campaign_count"], 1)
        self.assertEqual(report["learned_profile"]["mode"], "calibrated-balanced")


if __name__ == "__main__":
    unittest.main()
