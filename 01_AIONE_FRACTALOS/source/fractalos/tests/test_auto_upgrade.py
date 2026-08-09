from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.auto_upgrade import auto_upgrade_report, run_auto_upgrade_session
from omega_tile_os.core.doctor import run_doctor
from omega_tile_os.core.state import ensure_workspace


class AutoUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_auto_upgrade_generates_reports_and_programs(self) -> None:
        result = run_auto_upgrade_session(
            self.workspace,
            duration_minutes=0.01,
            cycle_delay_seconds=0,
            max_cycles=1,
            programs_per_cycle=2,
            run_tests=False,
            run_bare_metal_build=False,
        )
        report = auto_upgrade_report(self.workspace)

        self.assertEqual(result["cycles"], 1)
        self.assertTrue(Path(result["final_report"]).exists())
        self.assertTrue(Path(result["docs"]["project_doc"]).exists())
        self.assertGreaterEqual(report["program_count"], 2)
        self.assertEqual(report["metrics"]["runs"], 1)
        self.assertEqual(report["metrics"]["cycles"], 1)

    def test_doctor_knows_auto_upgrade_state(self) -> None:
        result = run_doctor(self.workspace)
        names = {item["name"] for item in result["checks"]}

        self.assertIn("auto-upgrade", names)
        self.assertEqual(result["counts"]["fail"], 0)


if __name__ == "__main__":
    unittest.main()
