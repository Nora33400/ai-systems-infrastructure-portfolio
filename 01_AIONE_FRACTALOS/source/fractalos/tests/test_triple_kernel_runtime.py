from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.state import ensure_workspace
from omega_tile_os.core.triple_kernel_runtime import triple_kernel_status, triple_kernel_synthesize


class TripleKernelRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_status_reports_empty_runtime_before_build(self) -> None:
        status = triple_kernel_status(self.workspace)
        self.assertEqual(status["catalog_total"], 1200)
        self.assertEqual(status["build_count"], 0)

    def test_synthesize_creates_runtime_build_and_report(self) -> None:
        result = triple_kernel_synthesize(self.workspace, limit=9, queue=True)
        self.assertEqual(result["build"]["primitive_count"], 9)
        self.assertEqual(len(result["bridges"]), 3)
        self.assertTrue(Path(result["report_path"]).exists())
        status = triple_kernel_status(self.workspace)
        self.assertEqual(status["build_count"], 1)
        self.assertGreaterEqual(status["metrics"]["syntheses"], 1)


if __name__ == "__main__":
    unittest.main()
