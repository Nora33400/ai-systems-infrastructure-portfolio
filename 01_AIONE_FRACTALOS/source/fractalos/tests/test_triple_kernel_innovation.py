from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.state import ensure_workspace
from omega_tile_os.core.triple_kernel_innovation import triple_kernel_catalog, triple_kernel_plan


class TripleKernelInnovationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_catalog_contains_twelve_hundred_innovations(self) -> None:
        catalog = triple_kernel_catalog()
        self.assertEqual(catalog["total"], 1200)
        self.assertEqual(len(catalog["vertices"]), 3)

    def test_plan_writes_report(self) -> None:
        result = triple_kernel_plan(self.workspace, limit=12, queue=False)
        self.assertEqual(result["selected_count"], 12)
        self.assertTrue(Path(result["report_path"]).exists())

    def test_plan_can_queue_workers_and_workloads(self) -> None:
        result = triple_kernel_plan(self.workspace, limit=6, queue=True)
        self.assertGreaterEqual(len(result["queued_workers"]), 1)
        self.assertGreaterEqual(len(result["queued_workloads"]), 1)


if __name__ == "__main__":
    unittest.main()
