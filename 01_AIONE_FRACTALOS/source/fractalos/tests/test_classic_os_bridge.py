from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.classic_os_bridge import (
    classic_capability_report,
    onboarding_pack,
    write_classic_os_report,
)
from omega_tile_os.core.state import ensure_workspace


class ClassicOSBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_capability_report_answers_user_classic_os_questions(self) -> None:
        report = classic_capability_report(self.workspace)
        ids = {item["id"] for item in report["capabilities"]}

        self.assertIn("desktop-office", ids)
        self.assertIn("persistent-install", ids)
        self.assertIn("internet-browser", ids)
        self.assertIn("common-file-extensions", ids)
        self.assertIn("video-playback", ids)
        self.assertIn("exe-compatibility", ids)
        self.assertFalse(report["summary"]["bare_metal_daily_driver"])
        self.assertTrue(report["summary"]["hosted_control_plane_usable"])

    def test_onboarding_pack_exposes_first_run_tips(self) -> None:
        pack = onboarding_pack(self.workspace)

        self.assertGreaterEqual(len(pack["tips"]), 5)
        self.assertIn("python -m omega_tile_os doctor --workspace .\\workspace", pack["first_commands"])
        self.assertIn("intent-lens", pack["overlays"])

    def test_report_is_written_to_workspace_and_tilemindfs(self) -> None:
        result = write_classic_os_report(self.workspace)
        report_path = Path(result["report_path"])

        self.assertTrue(report_path.exists())
        self.assertTrue(result["tile_manifest"])
        self.assertIn("Classic OS Bridge", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
