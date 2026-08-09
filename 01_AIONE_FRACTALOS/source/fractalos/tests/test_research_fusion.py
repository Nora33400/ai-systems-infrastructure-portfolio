from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.research_fusion import _decode_pdf_literal, research_fusion_report, run_research_fusion, scan_formula_corpus
from omega_tile_os.core.state import ensure_workspace


class ResearchFusionTests(unittest.TestCase):
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
            "[module] TaskScheduler\n"
            "[domain] scheduler_control\n"
            "F1: dispatch_t=TopK_admissible(prio_i)\n"
            "[note] Batch dispatch under resource constraints.\n\n"
            "## FORMULA 002\n"
            "[module] SecurityGuardianUsersHard\n"
            "[domain] risk_security\n"
            "F1: ISO_test_pass=1[QEMU_boot]\n"
            "[note] VM validation criterion.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scan_formula_corpus_counts_domains(self) -> None:
        result = scan_formula_corpus(self.corpus, max_files=1)
        self.assertEqual(result["formula_count"], 2)
        self.assertEqual(result["domain_counts"]["scheduler_control"], 1)
        self.assertEqual(result["domain_counts"]["risk_security"], 1)

    def test_pdf_literal_decoder_supports_octal_accents(self) -> None:
        self.assertEqual(_decode_pdf_literal(b"Avanc\\351es"), "Avancées")

    def test_run_research_fusion_writes_report_and_state(self) -> None:
        result = run_research_fusion(self.workspace, self.corpus, [], max_formula_files=1)
        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists())
        self.assertIn("FractalOS Research Fusion", report_path.read_text(encoding="utf-8"))
        report = research_fusion_report(self.workspace)
        self.assertEqual(report["metrics"]["runs"], 1)
        self.assertEqual(report["last_run"]["formula_count"], 2)

    def test_run_research_fusion_can_queue_followups(self) -> None:
        result = run_research_fusion(self.workspace, self.corpus, [], max_formula_files=1, queue_followups=True)
        self.assertGreaterEqual(len(result["queued"]), 1)
        report = research_fusion_report(self.workspace)
        self.assertGreaterEqual(report["metrics"]["followups_queued"], 1)


if __name__ == "__main__":
    unittest.main()
