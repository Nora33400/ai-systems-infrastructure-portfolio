from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.ollama_bridge import ai_model_orchestrator_plan, free_ai_model_catalog, select_free_ai_model
from omega_tile_os.core.state import ensure_workspace


class AIModelOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_catalog_filters_by_role(self) -> None:
        coder_models = free_ai_model_catalog(role="coder")

        self.assertTrue(coder_models)
        self.assertTrue(all("coder" in item["roles"] for item in coder_models))

    def test_selects_installed_matching_model(self) -> None:
        selected = select_free_ai_model(["qwen2.5-coder:7b"], "patcher")

        self.assertTrue(selected["installed"])
        self.assertEqual(selected["model"], "qwen2.5-coder:7b")

    def test_model_plan_writes_report_with_fallback_when_ollama_absent(self) -> None:
        result = ai_model_orchestrator_plan(self.workspace, endpoint="http://127.0.0.1:9")

        self.assertIn("recommendations", result)
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertTrue(result["recommendations"]["missing_pull_commands"])


if __name__ == "__main__":
    unittest.main()
