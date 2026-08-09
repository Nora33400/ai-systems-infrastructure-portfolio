from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_tile_os.core.action_router import execute_next_route, execute_route_loop, route_report, simulate_route_loop
from omega_tile_os.core.autonomy_runtime import submit_workload
from omega_tile_os.core.codex_worker import submit_worker_session
from omega_tile_os.core.formula_programs import discover_formula_programs
from omega_tile_os.core.state import ensure_workspace, load_perf_state, load_router_state, save_perf_state, save_router_state


class ActionRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        ensure_workspace(self.workspace)
        self._force_stable_perf()
        self.corpus = Path(self.tmp.name) / "corpus"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _force_stable_perf(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"] = {
            "telemetry": {},
            "formulas": {
                "cpu_headroom": 0.9,
                "gpu_headroom": 0.9,
                "cpu_pressure": 0.1,
                "gpu_pressure": 0.1,
                "memory_guard": 0.9,
                "thermal_envelope": 0.9,
                "stability_index": 0.82,
                "throughput_index": 0.86,
            },
            "recommendations": {
                "recommended_concurrency": 4,
                "recommended_planner_top_k": 4,
                "recommended_resource_limit": 10.0,
                "recommended_hot_budget_bytes": 262144,
                "recommended_warm_budget_bytes": 1048576,
                "risk_level": "low",
            },
        }
        save_perf_state(self.workspace, perf_state)

    def _force_elevated_perf(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"]["formulas"]["stability_index"] = 0.32
        perf_state["last_sample"]["recommendations"]["risk_level"] = "elevated"
        save_perf_state(self.workspace, perf_state)

    def _force_critical_perf(self) -> None:
        perf_state = load_perf_state(self.workspace)
        perf_state["last_sample"]["formulas"]["stability_index"] = 0.18
        perf_state["last_sample"]["recommendations"]["risk_level"] = "critical"
        save_perf_state(self.workspace, perf_state)

    def test_router_prefers_worker_queue_when_available(self) -> None:
        submit_worker_session(self.workspace, "builder", "Router Worker", "Build the next safe slice.")
        report = route_report(self.workspace)
        self.assertEqual(report["next_action"]["id"], "worker-run")
        self.assertEqual(report["next_action"]["payload"]["max_items"], 1)

    def test_router_executes_autonomy_queue(self) -> None:
        submit_workload(self.workspace, "research", "Router Research", "Map the next research lane.")
        result = execute_next_route(self.workspace)
        self.assertEqual(result["selected"]["id"], "autonomy-run")
        self.assertEqual(len(result["result"]["processed"]), 1)
        router_state = load_router_state(self.workspace)
        self.assertEqual(router_state["last_route"]["action_id"], "autonomy-run")
        self.assertEqual(router_state["metrics"]["executed"], 1)

    def test_router_falls_back_to_ecosystem_evolution_when_idle(self) -> None:
        report = route_report(self.workspace)
        self.assertEqual(report["next_action"]["id"], "supervisor-expand")
        self.assertGreaterEqual(len(report["recommendations"]), 1)

    def test_router_cooldown_penalizes_recently_failed_action(self) -> None:
        submit_workload(self.workspace, "research", "Router Research", "Map the next research lane.")
        router_state = load_router_state(self.workspace)
        router_state["cooldowns"]["autonomy-run"] = 2
        save_router_state(self.workspace, router_state)

        report = route_report(self.workspace)
        autonomy_action = next(item for item in report["recommendations"] if item["id"] == "autonomy-run")
        self.assertEqual(autonomy_action["cooldown_remaining"], 2)
        self.assertLess(autonomy_action["confidence"], 0.88)

    def test_router_loop_drains_bounded_autonomy_work(self) -> None:
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")
        submit_workload(self.workspace, "automation", "Router Automation B", "Map the next automation lane.")

        result = execute_route_loop(self.workspace, max_cycles=2)
        self.assertEqual(result["executed_count"], 2)
        self.assertTrue(all(item["action_id"] == "autonomy-run" for item in result["executed"]))
        router_state = load_router_state(self.workspace)
        self.assertEqual(router_state["metrics"]["loops"], 1)
        self.assertEqual(router_state["last_loop"]["executed_count"], 2)

    def test_router_loop_can_stop_on_elevated_risk(self) -> None:
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")
        self._force_elevated_perf()

        result = execute_route_loop(self.workspace, max_cycles=2, stop_on_elevated=True)
        self.assertEqual(result["stop_reason"], "elevated_risk_guard")
        self.assertEqual(result["executed_count"], 0)

    def test_router_simulate_does_not_mutate_queues(self) -> None:
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")
        before = route_report(self.workspace)["signals"]["queued_autonomy"]

        result = simulate_route_loop(self.workspace, max_cycles=3)
        after = route_report(self.workspace)["signals"]["queued_autonomy"]

        self.assertFalse(result["mutated_workspace"])
        self.assertEqual(before, after)
        self.assertEqual(result["simulated"][0]["action_id"], "autonomy-run")

    def test_router_simulate_respects_elevated_guard(self) -> None:
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")
        self._force_elevated_perf()

        result = simulate_route_loop(self.workspace, max_cycles=3, stop_on_elevated=True)
        self.assertEqual(result["stop_reason"], "elevated_risk_guard")
        self.assertEqual(result["would_execute_count"], 0)

    def test_router_includes_formula_advice_when_programs_are_installed(self) -> None:
        folder = self.corpus / "chunk_00001" / "00001"
        folder.mkdir(parents=True)
        (folder / "formula_001.txt").write_text(
            "# Formula\n\n"
            "## FORMULA 001\n"
            "[module] Router\n"
            "[domain] context_routing\n"
            "F1: route_score=omega(context,latency)\n"
            "[note] Route confidence amplifier.\n",
            encoding="utf-8",
        )
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=1)
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")

        report = route_report(self.workspace)

        self.assertIn("formula_advice", report)
        self.assertGreaterEqual(report["formula_advice"]["safe_program_count"], 1)
        self.assertIn("formula_bias", report["next_action"])

    def test_router_adds_protective_formula_action_under_elevated_risk(self) -> None:
        folder = self.corpus / "chunk_00001" / "00001"
        folder.mkdir(parents=True)
        (folder / "formula_001.txt").write_text(
            "# Formula\n\n"
            "## FORMULA 001\n"
            "[module] Governor\n"
            "[domain] energy_perf\n"
            "F1: thermal_budget=max_safe(phi)\n"
            "[note] Thermal stabilization curve.\n",
            encoding="utf-8",
        )
        discover_formula_programs(self.workspace, self.corpus, max_formula_files=1, max_programs=1)
        submit_workload(self.workspace, "research", "Router Research A", "Map the next research lane.")
        self._force_elevated_perf()

        report = route_report(self.workspace)
        ids = {item["id"] for item in report["recommendations"]}

        self.assertIn("perf-tune", ids)
        self.assertGreaterEqual(report["formula_advice"]["protective_program_count"], 1)
        self.assertEqual(report["next_action"]["id"], "perf-tune")

    def test_router_loop_allows_only_protective_action_under_critical_risk(self) -> None:
        self._force_critical_perf()

        result = execute_route_loop(self.workspace, max_cycles=1)

        self.assertEqual(result["executed_count"], 1)
        self.assertEqual(result["executed"][0]["action_id"], "perf-tune")


if __name__ == "__main__":
    unittest.main()
