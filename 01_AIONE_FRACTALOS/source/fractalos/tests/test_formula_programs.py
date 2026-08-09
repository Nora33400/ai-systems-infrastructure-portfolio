from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.formula_programs import (
    discover_formula_programs,
    evaluate_formula_program,
    evolve_formula_programs,
    formula_runtime_advice,
    formula_program_report,
    simulate_formula_programs,
)
from omega_tile_os.core.state import ensure_workspace


class FormulaProgramTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        self.corpus = Path(self.tmp.name) / "corpus"
        ensure_workspace(self.workspace)
        folder = self.corpus / "chunk_00001" / "00001"
        folder.mkdir(parents=True)
        (folder / "formula_001.txt").write_text(
            "# Formula\n\n"
            "## FORMULA 001\n"
            "[module] TaskScheduler\n"
            "[domain] scheduler_control\n"
            "F1: dispatch_t=TopK_admissible(prio_i)\n"
            "[note] Batch dispatch under resource constraints.\n\n"
            "## FORMULA 002\n"
            "[module] TaskScheduler\n"
            "[domain] scheduler_control\n"
            "F1: route_score=omega(prio,latency)\n"
            "[note] Priority routing curve.\n\n"
            "## FORMULA 003\n"
            "[module] SecurityGuardianUsersHard\n"
            "[domain] risk_security\n"
            "F1: ISO_test_pass=1[QEMU_boot]\n"
            "[note] VM validation criterion.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_discover_formula_programs_installs_safe_program_specs(self) -> None:
        result = discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
        self.assertEqual(result["last_discovery"]["program_count"], 2)
        self.assertEqual(len(result["installed"]), 2)
        for item in result["installed"]:
            program_path = Path(item["program_path"])
            self.assertTrue(program_path.exists())
            self.assertIn("PROGRAM.json", str(program_path))

        report = formula_program_report(self.workspace)
        self.assertEqual(report["program_count"], 2)
        self.assertEqual(report["metrics"]["discoveries"], 1)
        self.assertEqual(report["metrics"]["installed"], 2)

    def test_evaluate_formula_program_keeps_outputs_bounded(self) -> None:
        program = {
            "id": "risk-security-test",
            "domain": "risk_security",
            "kernel": "guarded_execution_score",
            "weights": {"performance": 0.1, "energy": 0.1, "complexity": 0.1, "risk": 0.5, "coherence": 0.2},
        }
        result = evaluate_formula_program(
            program,
            {
                "performance_pressure": 99,
                "energy_pressure": -4,
                "complexity_pressure": 0.4,
                "risk_pressure": 0.1,
                "coherence": 2,
            },
        )
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)
        self.assertGreaterEqual(result["recommendation"]["guard_threshold"], 0.5)
        self.assertLessEqual(result["recommendation"]["guard_threshold"], 0.8)

    def test_simulate_formula_programs_evaluates_installed_programs(self) -> None:
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
        result = simulate_formula_programs(self.workspace)
        self.assertEqual(result["evaluation_count"], 2)
        self.assertTrue(all(0.0 <= item["score"] <= 1.0 for item in result["evaluations"]))
        report = formula_program_report(self.workspace)
        self.assertEqual(report["metrics"]["evaluations"], 2)

    def test_evolve_formula_programs_queues_safe_followups(self) -> None:
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
        result = evolve_formula_programs(self.workspace, queue_limit=2)
        self.assertGreaterEqual(len(result["queued"]), 1)
        self.assertTrue(Path(result["report_path"]).exists())
        report = formula_program_report(self.workspace)
        self.assertEqual(report["metrics"]["evolutions"], 1)
        self.assertEqual(report["last_evolution"]["queued_count"], len(result["queued"]))

    def test_formula_runtime_advice_emits_bounded_action_biases(self) -> None:
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
        advice = formula_runtime_advice(
            self.workspace,
            perf_report={
                "formulas": {"cpu_pressure": 0.22, "throughput_index": 0.82, "stability_index": 0.76},
                "recommendations": {"risk_level": "low"},
            },
            router_signals={"queued_autonomy": 2, "queued_workers": 1},
        )
        self.assertGreaterEqual(advice["safe_program_count"], 1)
        self.assertTrue(advice["action_biases"])
        self.assertTrue(all(0.0 < value <= 0.08 for value in advice["action_biases"].values()))

    def test_formula_runtime_advice_can_emit_protective_biases_under_risk(self) -> None:
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
        advice = formula_runtime_advice(
            self.workspace,
            perf_report={
                "formulas": {"cpu_pressure": 0.40, "throughput_index": 0.46, "stability_index": 0.44},
                "recommendations": {"risk_level": "elevated"},
            },
            router_signals={"queued_autonomy": 4, "queued_workers": 0},
        )
        self.assertGreaterEqual(advice["protective_program_count"], 1)
        self.assertTrue(advice["protective_biases"])
        self.assertTrue(all(0.0 < value <= 0.10 for value in advice["protective_biases"].values()))


if __name__ == "__main__":
    unittest.main()
