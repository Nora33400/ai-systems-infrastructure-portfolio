from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.state import ensure_workspace
from omega_tile_os.core.usage_blackbox import (
    log_usage_error,
    run_restart_recovery,
    snapshot_known_good_modules,
    usage_error_report,
)


class UsageBlackBoxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.workspace = self.root / "workspace"
        (self.root / "omega_tile_os" / "core").mkdir(parents=True)
        (self.root / "omega_tile_os").mkdir(exist_ok=True)
        (self.root / "omega_tile_os" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "omega_tile_os" / "core" / "__init__.py").write_text("", encoding="utf-8")
        self.module = self.root / "omega_tile_os" / "core" / "sample.py"
        self.module.write_text("VALUE = 1\n", encoding="utf-8")
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_logs_usage_error(self) -> None:
        entry = log_usage_error(self.workspace, "argparse", "bad command", command="omega bad")
        report = usage_error_report(self.workspace)

        self.assertEqual(entry["category"], "argparse")
        self.assertEqual(report["metrics"]["logged_errors"], 1)
        self.assertEqual(report["category_counts"]["argparse"], 1)

    def test_restart_recovery_rolls_back_broken_module(self) -> None:
        snapshot_known_good_modules(self.workspace, project_root=self.root, label="test-good")
        self.module.write_text("def broken(:\n", encoding="utf-8")

        recovery = run_restart_recovery(self.workspace, project_root=self.root, reason="test", run_doctor_check=False)

        self.assertEqual(recovery["after"]["failed_count"], 0)
        self.assertIn("VALUE = 1", self.module.read_text(encoding="utf-8"))
        self.assertTrue(Path(recovery["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
