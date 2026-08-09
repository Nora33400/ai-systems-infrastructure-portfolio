from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.desktop_runtime import (
    desktop_catalog,
    desktop_cycle_overlay,
    desktop_login,
    desktop_overlay_status,
    desktop_package_center,
    desktop_search,
    desktop_shell,
    desktop_tile_explorer,
)
from omega_tile_os.core.state import ensure_workspace


class DesktopRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_desktop_catalog_exposes_persistent_overlays_and_revolutions(self) -> None:
        catalog = desktop_catalog(self.workspace)

        self.assertEqual(catalog["active_overlay"], "intent-lens")
        self.assertGreaterEqual(len(catalog["overlays"]), 5)
        self.assertGreaterEqual(len(catalog["revolutions"]), 5)
        self.assertIn("desktop-plane", catalog["kernel_boundary"])

    def test_desktop_overlay_can_cycle_and_report_status(self) -> None:
        cycled = desktop_cycle_overlay(self.workspace)
        status = desktop_overlay_status(self.workspace)

        self.assertTrue(cycled["cycled"])
        self.assertEqual(status["active"]["id"], cycled["active_overlay"])
        self.assertEqual(status["metrics"]["overlay_cycles"], 1)

    def test_desktop_shell_exposes_overlay_commands(self) -> None:
        help_result = desktop_shell(self.workspace, "help")
        overlay_result = desktop_shell(self.workspace, "overlay")
        cycle_result = desktop_shell(self.workspace, "overlay cycle")
        revolutions_result = desktop_shell(self.workspace, "revolutions")

        self.assertIn("overlay", help_result["commands"])
        self.assertEqual(overlay_result["type"], "overlay")
        self.assertEqual(cycle_result["type"], "overlay-cycle")
        self.assertEqual(revolutions_result["type"], "revolutions")

    def test_desktop_exposes_classic_os_surfaces(self) -> None:
        catalog = desktop_catalog(self.workspace)
        app_ids = {item["id"] for item in catalog["apps"]}

        self.assertIn("tile-explorer", app_ids)
        self.assertIn("web-gateway", app_ids)
        self.assertIn("package-center", app_ids)
        self.assertIn("office-desk", app_ids)
        self.assertIn("install-center", app_ids)

    def test_search_files_packages_and_login_are_modeled(self) -> None:
        search = desktop_search(self.workspace, "package")
        files = desktop_tile_explorer(self.workspace)
        packages = desktop_package_center(self.workspace)
        login = desktop_login(self.workspace, "user")
        shell = desktop_shell(self.workspace, "packages")

        self.assertGreater(search["total"], 0)
        self.assertEqual(files["mode"], "tile_explorer")
        self.assertGreaterEqual(len(packages["packages"]), 8)
        self.assertTrue(login["logged_in"])
        self.assertEqual(shell["type"], "packages")


if __name__ == "__main__":
    unittest.main()
