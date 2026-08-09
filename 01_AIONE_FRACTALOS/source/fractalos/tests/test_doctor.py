from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.doctor import run_doctor, run_healer
from omega_tile_os.core.formula_programs import discover_formula_programs
from omega_tile_os.core.state import ensure_workspace, load_perf_state, save_perf_state


class DoctorTests(unittest.TestCase):
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
            "[module] Governor\n"
            "[domain] energy_perf\n"
            "F1: thermal_budget=max_safe(phi)\n"
            "[note] Thermal stabilization curve.\n\n"
            "## FORMULA 002\n"
            "[module] Router\n"
            "[domain] context_routing\n"
            "F1: route_score=omega(context,latency)\n"
            "[note] Route confidence amplifier.\n",
            encoding="utf-8",
        )
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=2)
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

    def test_doctor_reports_core_checks_without_failures(self) -> None:
        result = run_doctor(self.workspace)
        names = {item["name"] for item in result["checks"]}

        self.assertIn(result["status"], {"ok", "warn"})
        self.assertEqual(result["counts"]["fail"], 0)
        self.assertIn("workspace", names)
        self.assertIn("router", names)
        self.assertIn("formula-advice", names)
        self.assertIn("ui", names)
        self.assertIn("native-userspace", names)

        native = next(item for item in result["checks"] if item["name"] == "native-userspace")
        bare_metal = next(item for item in result["checks"] if item["name"] == "bare-metal-kernel")
        self.assertEqual(native["status"], "ok")
        self.assertGreaterEqual(native["details"]["node_count"], 10)
        self.assertIn("storage-vfs", names)
        self.assertEqual(bare_metal["details"]["stage"], "stage22-storage-vfs-journal-alpha")

    def test_healer_dry_run_plans_safe_repairs(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"]["formulas"]["stability_index"] = 0.18
        perf_state["last_sample"]["recommendations"]["risk_level"] = "critical"
        save_perf_state(self.workspace, perf_state)

        result = run_healer(self.workspace, apply=False)
        repair_ids = {item["id"] for item in result["planned_repairs"]}

        self.assertEqual(result["mode"], "dry-run")
        self.assertIn("perf-tune", repair_ids)
        self.assertTrue(all("heal_score" in item for item in result["planned_repairs"]))
        self.assertGreaterEqual(result["planned_repairs"][0]["heal_score"], result["planned_repairs"][-1]["heal_score"])
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertEqual(result["executed"], [])

    def test_healer_apply_executes_only_safe_repairs(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"]["formulas"]["stability_index"] = 0.18
        perf_state["last_sample"]["recommendations"]["risk_level"] = "critical"
        save_perf_state(self.workspace, perf_state)

        result = run_healer(self.workspace, apply=True)

        self.assertEqual(result["mode"], "apply")
        self.assertTrue(result["executed"])
        self.assertTrue(all(item["status"] in {"ok", "skipped"} for item in result["executed"]))
        self.assertIsNotNone(result["after"])
        self.assertTrue(Path(result["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
