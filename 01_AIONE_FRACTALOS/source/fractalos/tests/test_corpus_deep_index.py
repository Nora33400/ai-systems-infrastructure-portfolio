from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.corpus_deep_index import build_corpus_deep_index, corpus_deep_index_report
from omega_tile_os.core.state import ensure_workspace


class CorpusDeepIndexTests(unittest.TestCase):
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
            "[module] TilePacker\n"
            "[domain] cube_compression_gpu\n"
            "F1: D_eff=(1+H_dup)*C_codec\n"
            "[note] Storage density lane.\n\n"
            "## FORMULA 002\n"
            "[module] TaskScheduler\n"
            "[domain] scheduler_control\n"
            "F1: Q_safe=cores*S_stability\n"
            "[note] Scheduler lane.\n",
            encoding="utf-8",
        )
        (self.corpus / "notes.pdf").write_bytes(b"%PDF-1.4")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_corpus_deep_index_maps_domains_to_os_axes(self) -> None:
        result = build_corpus_deep_index(self.workspace, self.corpus)

        self.assertEqual(result["total_formula_files"], 1)
        self.assertEqual(result["indexed_formula_files"], 1)
        self.assertEqual(result["formula_count"], 2)
        self.assertIn("cube_compression_gpu", result["top_domains"])
        self.assertIn("storage-density", result["sector_counts"])
        self.assertTrue(Path(result["report_path"]).exists())

        report = corpus_deep_index_report(self.workspace)
        self.assertEqual(report["metrics"]["indexes"], 1)
        self.assertEqual(report["last_index"]["coverage_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
