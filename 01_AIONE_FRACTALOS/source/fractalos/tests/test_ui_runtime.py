from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.autonomy_runtime import submit_workload
from omega_tile_os.core.codex_worker import submit_worker_session
from omega_tile_os.core.state import ensure_workspace, load_ui_state, save_ui_state
from omega_tile_os.core.ui_runtime import available_views, build_ui_model


class UiRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_available_views_lists_expected_surfaces(self) -> None:
        views = available_views()
        ids = {item["id"] for item in views}
        self.assertIn("mission-control", ids)
        self.assertIn("worker-studio", ids)
        self.assertIn("autonomy-lab", ids)
        self.assertIn("triple-kernel-forge", ids)
        self.assertIn("fractal-desktop", ids)
        self.assertIn("scientific-formula-lab", ids)
        self.assertIn("corpus-integration-lab", ids)
        self.assertIn("timeline-center", ids)

    def test_build_ui_model_returns_requested_view(self) -> None:
        submit_workload(self.workspace, "research", "Research lane", "Map a research lane.")
        worker = submit_worker_session(self.workspace, "builder", "Worker lane", "Map a worker lane.")
        model = build_ui_model(self.workspace, active_view="worker-studio")
        self.assertEqual(model["active_view"], "worker-studio")
        self.assertEqual(model["view"]["headline"], "Sessions IA, plans, reviews et transitions vers les missions.")
        self.assertGreaterEqual(len(model["views"]), 3)
        self.assertGreaterEqual(len(model["view"]["quick_actions"]), 1)
        self.assertGreaterEqual(len(model["recommended_views"]), 1)
        self.assertIn("detail_cards", model)
        self.assertIn("timeline", model)
        self.assertIn("router", model["snapshot"])
        self.assertIn("research_fusion", model["snapshot"])
        self.assertIn("formula_programs", model["snapshot"])
        self.assertIn(f"worker:{worker['id']}", {item.get("detail_key") for item in model["timeline"]})

    def test_build_ui_model_can_return_timeline_view(self) -> None:
        model = build_ui_model(self.workspace, active_view="timeline-center")
        self.assertEqual(model["active_view"], "timeline-center")
        self.assertIn("detail_cards", model)

    def test_build_ui_model_can_return_fractal_desktop_view(self) -> None:
        model = build_ui_model(self.workspace, active_view="fractal-desktop")
        self.assertEqual(model["active_view"], "fractal-desktop")
        self.assertEqual(model["snapshot"]["desktop"]["active_overlay"], "intent-lens")
        self.assertGreaterEqual(len(model["snapshot"]["desktop"]["overlays"]), 5)
        self.assertTrue(any(action["id"] == "desktop-overlay-cycle" for action in model["actions"]))

    def test_build_ui_model_can_return_scientific_formula_lab_view(self) -> None:
        model = build_ui_model(self.workspace, active_view="scientific-formula-lab")
        self.assertEqual(model["active_view"], "scientific-formula-lab")
        self.assertGreaterEqual(model["snapshot"]["scientific_formulas"]["catalog_total"], 100)
        self.assertTrue(any(action["id"] == "scientific-formula-plan" for action in model["actions"]))

    def test_build_ui_model_can_return_corpus_integration_lab_view(self) -> None:
        model = build_ui_model(self.workspace, active_view="corpus-integration-lab")
        self.assertEqual(model["active_view"], "corpus-integration-lab")
        self.assertIn("corpus_index", model["snapshot"])
        self.assertTrue(any(action["id"] == "corpus-index" for action in model["actions"]))

    def test_ui_state_is_exposed_in_model(self) -> None:
        ui_state = load_ui_state(self.workspace)
        ui_state["actions"].append(
            {
                "ts": "2026-04-21T00:00:00+00:00",
                "action_id": "perf-tune",
                "view": "mission-control",
                "status": "ok",
                "duration_ms": 12,
                "summary": "status=tuned",
                "result": {"status": "tuned"},
            }
        )
        ui_state["metrics"]["executed"] = 1
        ui_state["last_result"] = ui_state["actions"][-1]
        save_ui_state(self.workspace, ui_state)

        model = build_ui_model(self.workspace, active_view="mission-control")
        self.assertEqual(model["snapshot"]["ui"]["metrics"]["executed"], 1)
        self.assertEqual(model["snapshot"]["ui"]["last_result"]["action_id"], "perf-tune")
        self.assertTrue(any(item["kind"] == "ui_action" for item in model["timeline"]))


if __name__ == "__main__":
    unittest.main()
