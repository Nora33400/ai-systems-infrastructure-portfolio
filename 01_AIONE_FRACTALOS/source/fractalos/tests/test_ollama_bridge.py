from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.autonomy_runtime import autonomy_report
from omega_tile_os.core.codex_worker import worker_report
from omega_tile_os.core.ollama_bridge import create_ollama_idea_plan, ollama_status
from omega_tile_os.core.state import ensure_workspace


class OllamaBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ollama_status_falls_back_when_endpoint_is_unavailable(self) -> None:
        status = ollama_status(endpoint="http://127.0.0.1:1", timeout_s=0.1)
        self.assertFalse(status["available"])
        self.assertEqual(status["endpoint"], "http://127.0.0.1:1")

    def test_create_idea_plan_generates_report_without_ollama(self) -> None:
        result = create_ollama_idea_plan(
            self.workspace,
            "Construire un assistant local qui transforme les idees en patchs verifies.",
            endpoint="http://127.0.0.1:1",
            timeout_s=0.1,
        )
        self.assertIn(result["source"], {"fallback", "fallback-after-error"})
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertGreaterEqual(len(result["plan"]["milestones"]), 4)
        self.assertEqual(result["queued_workers"], [])

    def test_create_idea_plan_can_queue_agents_and_workloads(self) -> None:
        result = create_ollama_idea_plan(
            self.workspace,
            "Ajouter une forge de developpement local.",
            endpoint="http://127.0.0.1:1",
            timeout_s=0.1,
            queue_agents=True,
        )
        self.assertGreaterEqual(len(result["queued_workers"]), 1)
        self.assertGreaterEqual(len(result["queued_workloads"]), 1)
        self.assertGreaterEqual(worker_report(self.workspace)["status_counts"].get("queued", 0), 1)
        self.assertGreaterEqual(autonomy_report(self.workspace)["status_counts"].get("queued", 0), 1)


if __name__ == "__main__":
    unittest.main()
