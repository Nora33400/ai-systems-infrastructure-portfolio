from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.scientific_formula_forge import (
    scientific_formula_catalog,
    scientific_formula_plan,
    scientific_formula_report,
    score_scientific_formula,
)
from omega_tile_os.core.state import ensure_workspace


class ScientificFormulaForgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_catalog_contains_many_safe_local_hardware_formulas(self) -> None:
        catalog = scientific_formula_catalog(limit=10000)

        self.assertGreaterEqual(len(catalog), 120)
        self.assertTrue(all(item["local_only"] for item in catalog))
        self.assertTrue(any(item["sector"] == "storage" for item in catalog))
        self.assertTrue(any("D_eff" in item["equation"] for item in catalog))

    def test_formula_scoring_is_bounded_and_recommends_safe_candidates(self) -> None:
        formula = scientific_formula_catalog(target="storage", limit=1)[0]
        scored = score_scientific_formula(
            formula,
            {
                "stability": 0.82,
                "throughput": 0.78,
                "memory_guard": 0.70,
                "thermal": 0.84,
                "storage_gain": 0.55,
                "memory_heat": 0.40,
            },
        )

        self.assertGreaterEqual(scored["activation_score"], 0.0)
        self.assertLessEqual(scored["activation_score"], 1.0)
        self.assertTrue(scored["recommended"])
        self.assertGreater(scored["runtime_notes"]["storage_effective_capacity_hint"], 1.0)

    def test_plan_writes_report_and_updates_runtime_state(self) -> None:
        result = scientific_formula_plan(self.workspace, target="storage", limit=4)
        report = scientific_formula_report(self.workspace)

        self.assertEqual(len(result["selected"]), 4)
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertEqual(report["metrics"]["plans"], 1)
        self.assertEqual(report["last_plan"]["target"], "storage")


if __name__ == "__main__":
    unittest.main()
