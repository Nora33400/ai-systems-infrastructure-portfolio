from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.native_desktop_stack import (
    native_desktop_blueprint,
    native_installation_plan,
    native_package_catalog,
    write_native_desktop_report,
)
from omega_tile_os.core.state import ensure_workspace


class NativeDesktopStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_blueprint_tracks_desktop_install_and_truth_gates(self) -> None:
        blueprint = native_desktop_blueprint(self.workspace)
        component_ids = {item["id"] for item in blueprint["components"]}

        self.assertIn("login-greeter", component_ids)
        self.assertIn("global-search", component_ids)
        self.assertIn("tile-explorer", component_ids)
        self.assertIn("web-gateway", component_ids)
        self.assertIn("package-center", component_ids)
        self.assertFalse(blueprint["truth"]["classic_daily_driver_now"])
        self.assertFalse(blueprint["truth"]["persistent_self_install_now"])

    def test_package_catalog_includes_classic_and_fractal_domains(self) -> None:
        catalog = native_package_catalog(self.workspace)
        package_ids = {item["id"] for item in catalog["packages"]}

        self.assertIn("runtime.python", package_ids)
        self.assertIn("browser.firefox-domain", package_ids)
        self.assertIn("office.libreoffice-domain", package_ids)
        self.assertIn("fs.tilemindfs", package_ids)
        self.assertIn("compat.exe-domain", package_ids)

    def test_installation_plan_writes_report_and_vm_script(self) -> None:
        plan = native_installation_plan(self.workspace, target="vm", disk_size_gb=8, create_vm_disk=False)

        self.assertTrue(Path(plan["report_path"]).exists())
        self.assertTrue(Path(plan["start_script"]).exists())
        self.assertTrue(plan["persistent_install_truth"]["machine_install_blueprint_ready"])
        self.assertFalse(plan["persistent_install_truth"]["self_hosted_installer_ready"])
        self.assertIn("writable storage driver", plan["persistent_install_truth"]["blocking_native_gates"])

    def test_native_report_archives_to_tilemindfs(self) -> None:
        report = write_native_desktop_report(self.workspace)

        self.assertTrue(Path(report["report_path"]).exists())
        self.assertTrue(report["tile_manifest"])
        self.assertIn("install_plan", report)


if __name__ == "__main__":
    unittest.main()
