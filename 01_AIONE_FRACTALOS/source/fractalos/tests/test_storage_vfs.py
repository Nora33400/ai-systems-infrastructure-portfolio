from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.state import ensure_workspace
from omega_tile_os.core.storage_vfs import (
    storage_mount_report,
    storage_read,
    storage_rollback,
    storage_snapshot,
    storage_verify,
    storage_write,
    write_storage_vfs_report,
)


class StorageVFSTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_mount_bootstraps_persistent_home(self) -> None:
        report = storage_mount_report(self.workspace)

        self.assertEqual(report["stage"], "stage22-storage-vfs-journal-alpha")
        self.assertEqual(report["mount"]["path"], "/home")
        self.assertGreaterEqual(report["file_count"], 1)
        self.assertTrue(report["truth"]["hosted_persistent_vfs"])

    def test_write_read_verify_and_rollback_last_write(self) -> None:
        first = storage_write(self.workspace, "/home/user/note.txt", "v1", owner="user")
        second = storage_write(self.workspace, "/home/user/note.txt", "v2", owner="user")
        read_after = storage_read(self.workspace, "/home/user/note.txt")
        rollback = storage_rollback(self.workspace, "last-write")
        read_rollback = storage_read(self.workspace, "/home/user/note.txt")
        verify = storage_verify(self.workspace)

        self.assertTrue(first["written"])
        self.assertTrue(second["journal_id"])
        self.assertEqual(read_after["text"], "v2")
        self.assertTrue(rollback["rolled_back"])
        self.assertEqual(read_rollback["text"], "v1")
        self.assertTrue(verify["ok"])

    def test_snapshot_restores_file_set(self) -> None:
        storage_write(self.workspace, "/home/user/a.txt", "alpha", owner="user")
        snap = storage_snapshot(self.workspace, label="before-change")
        storage_write(self.workspace, "/home/user/a.txt", "beta", owner="user")
        rollback = storage_rollback(self.workspace, snap["snapshot"]["id"])
        read = storage_read(self.workspace, "/home/user/a.txt")

        self.assertTrue(snap["snapshotted"])
        self.assertTrue(rollback["rolled_back"])
        self.assertEqual(read["text"], "alpha")

    def test_report_is_archived(self) -> None:
        result = write_storage_vfs_report(self.workspace)
        path = Path(result["report_path"])

        self.assertTrue(path.exists())
        self.assertTrue(result["tile_manifest"])
        self.assertIn("PersistenceScore", path.read_text(encoding="utf-8"))

    def test_rejects_paths_outside_home(self) -> None:
        result = storage_write(self.workspace, "/etc/passwd", "nope", owner="user")

        self.assertFalse(result["written"])
        self.assertEqual(result["reason"], "outside_persistent_home")


if __name__ == "__main__":
    unittest.main()
