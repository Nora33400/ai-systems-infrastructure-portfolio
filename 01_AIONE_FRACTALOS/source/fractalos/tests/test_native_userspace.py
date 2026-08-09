from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.native_userspace import (
    package_manifest,
    userspace_alpha_report,
    userspace_session_start,
    vfs_list,
    vfs_mount_report,
    vfs_read,
    vfs_write,
    write_userspace_alpha_report,
)
from omega_tile_os.core.storage_vfs import storage_read
from omega_tile_os.core.state import ensure_workspace


class NativeUserspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_session_and_mounts_are_initialized(self) -> None:
        session = userspace_session_start(self.workspace, "user")
        mounts = vfs_mount_report(self.workspace)

        self.assertTrue(session["started"])
        self.assertEqual(session["session"]["home"], "/home/user")
        self.assertGreaterEqual(mounts["node_count"], 8)
        self.assertEqual(mounts["mounts"][0]["path"], "/")

    def test_vfs_read_write_and_list(self) -> None:
        written = vfs_write(self.workspace, "/home/user/hello.txt", "hello fractal", owner="user")
        listed = vfs_list(self.workspace, "/home/user")
        read = vfs_read(self.workspace, "/home/user/hello.txt")

        self.assertTrue(written["written"])
        self.assertTrue(written["tile_manifest"])
        self.assertTrue(listed["listed"])
        self.assertTrue(read["read"])
        self.assertEqual(read["text"], "hello fractal")
        self.assertTrue(written["storage"]["written"])
        self.assertTrue(written["storage"]["journal_id"])
        stored = storage_read(self.workspace, "/home/user/hello.txt")
        self.assertTrue(stored["read"])
        self.assertEqual(stored["text"], "hello fractal")

    def test_package_manifest_exposes_runtime_domains(self) -> None:
        manifest = package_manifest(self.workspace)
        ids = {item["id"] for item in manifest["packages"]}

        self.assertIn("runtime.python", ids)
        self.assertIn("runtime.rust", ids)
        self.assertIn("runtime.java", ids)
        self.assertIn("browser.firefox-domain", ids)
        self.assertIn("office.libreoffice-domain", ids)

    def test_userspace_report_is_archived(self) -> None:
        result = write_userspace_alpha_report(self.workspace)
        path = Path(result["report_path"])
        report = userspace_alpha_report(self.workspace)

        self.assertTrue(path.exists())
        self.assertTrue(result["tile_manifest"])
        self.assertTrue(report["truth"]["runtime_vfs_usable"])
        self.assertTrue(report["truth"]["hosted_persistent_storage_vfs"])
        self.assertFalse(report["truth"]["persistent_native_disk_write"])


if __name__ == "__main__":
    unittest.main()
