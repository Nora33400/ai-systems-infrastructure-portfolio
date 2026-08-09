from __future__ import annotations

from pathlib import Path

from .autonomy_runtime import autonomy_report, evolve_ecosystem, run_workloads
from .codex_worker import run_worker_sessions, worker_report
from .events import append_event
from .formula_programs import formula_runtime_advice
from .mesh_federation import mesh_compact, mesh_consensus, mesh_daemon_snapshot, mesh_status
from .meta_supervisor import supervisor_report, supervisor_run
from .perf_governor import PerformanceGovernor
from .state import load_router_state, save_router_state, utc_now


SAFE_RISK_LEVELS = {"low", "nominal", "elevated"}
COOLDOWN_AFTER_FAILURE = 2
LOOP_ALLOWED_ACTIONS = {"perf-tune", "mesh-compact", "mesh-consensus", "worker-run", "autonomy-run", "autonomy-evolve", "supervisor-expand"}
CRITICAL_ALLOWED_ACTIONS = {"perf-tune", "mesh-compact"}


def _action(
    action_id: str,
    label: str,
    reason: str,
    view: str,
    safety: str,
    confidence: float,
    payload: dict | None = None,
) -> dict[str, object]:
    return {
        "id": action_id,
        "label": label,
        "reason": reason,
        "view": view,
        "safety": safety,
        "confidence": round(max(0.0, min(confidence, 1.0)), 3),
        "payload": payload or {},
    }


def _router_memory(workspace: Path) -> dict:
    state = load_router_state(workspace)
    state.setdefault("routes", [])
    state.setdefault("metrics", {"reports": 0, "executed": 0, "failed": 0, "skipped_by_cooldown": 0})
    state.setdefault("cooldowns", {})
    state.setdefault("last_loop", None)
    return state


def _apply_memory(recommendations: list[dict[str, object]], router_state: dict) -> list[dict[str, object]]:
    adjusted: list[dict[str, object]] = []
    cooldowns = dict(router_state.get("cooldowns", {}))
    for item in recommendations:
        action = dict(item)
        action_id = str(action["id"])
        cooldown = int(cooldowns.get(action_id, 0))
        if cooldown > 0:
            action["cooldown_remaining"] = cooldown
            action["confidence"] = round(float(action["confidence"]) * 0.35, 3)
            action["reason"] = f"{action['reason']} Cooldown actif apres erreur recente ({cooldown})."
        adjusted.append(action)
    adjusted.sort(key=lambda item: float(item["confidence"]), reverse=True)
    return adjusted


def _apply_formula_advice(recommendations: list[dict[str, object]], advice: dict[str, object]) -> list[dict[str, object]]:
    biases = dict(advice.get("action_biases", {}))
    if not biases:
        return recommendations
    adjusted: list[dict[str, object]] = []
    for item in recommendations:
        action = dict(item)
        action_id = str(action["id"])
        bias = float(biases.get(action_id, 0.0))
        if bias > 0:
            action["formula_bias"] = round(bias, 4)
            action["confidence"] = round(max(0.0, min(1.0, float(action["confidence"]) + bias)), 3)
            action["reason"] = f"{action['reason']} FormulaAdvisor +{bias:.3f}."
        adjusted.append(action)
    adjusted.sort(key=lambda item: float(item["confidence"]), reverse=True)
    return adjusted


def _decay_cooldowns(router_state: dict, selected_id: str) -> None:
    cooldowns = dict(router_state.get("cooldowns", {}))
    decayed = {}
    for action_id, value in cooldowns.items():
        current = int(value)
        if action_id == selected_id:
            decayed[action_id] = current
        elif current > 1:
            decayed[action_id] = current - 1
    router_state["cooldowns"] = decayed


def _remember_report(workspace: Path, report: dict[str, object]) -> None:
    router_state = _router_memory(workspace)
    metrics = router_state.setdefault("metrics", {})
    metrics["reports"] = int(metrics.get("reports", 0)) + 1
    router_state["last_report"] = {
        "ts": report["generated_at"],
        "next_action": report["next_action"],
        "risk_level": report["risk_level"],
        "stability_index": report["stability_index"],
        "signals": report["signals"],
    }
    save_router_state(workspace, router_state)


def _compact_result(result: dict) -> dict:
    keys = sorted(result.keys())
    if "error" in result:
        return {"error": result.get("error"), "message": result.get("message", ""), "keys": keys}
    summary = {"keys": keys}
    for key in ("processed", "queued", "recommendations", "actions"):
        if isinstance(result.get(key), list):
            summary[f"{key}_count"] = len(result[key])
    for key in ("queued_remaining", "report_path", "mission_id", "status"):
        if key in result:
            summary[key] = result[key]
    return summary


def _remember_execution(workspace: Path, action: dict[str, object], result: dict[str, object], report: dict[str, object]) -> dict:
    router_state = _router_memory(workspace)
    action_id = str(action["id"])
    status = "error" if result.get("error") else "ok"
    route = {
        "ts": utc_now(),
        "action_id": action_id,
        "status": status,
        "view": action.get("view"),
        "safety": action.get("safety"),
        "confidence": action.get("confidence"),
        "risk_level": report.get("risk_level"),
        "stability_index": report.get("stability_index"),
        "result": _compact_result(result),
    }
    router_state.setdefault("routes", []).append(route)
    router_state["routes"] = router_state["routes"][-80:]
    metrics = router_state.setdefault("metrics", {})
    metrics["executed"] = int(metrics.get("executed", 0)) + 1
    if status == "error":
        metrics["failed"] = int(metrics.get("failed", 0)) + 1
        router_state.setdefault("cooldowns", {})[action_id] = COOLDOWN_AFTER_FAILURE
    else:
        router_state.setdefault("cooldowns", {}).pop(action_id, None)
    _decay_cooldowns(router_state, action_id)
    router_state["last_route"] = route
    save_router_state(workspace, router_state)
    return route


def route_report(workspace: Path) -> dict[str, object]:
    router_state = _router_memory(workspace)
    perf = PerformanceGovernor(workspace).report()
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    mesh = mesh_status(workspace)
    daemon = mesh_daemon_snapshot(workspace)
    supervisor = supervisor_report(workspace)
    risk = str(perf["recommendations"].get("risk_level", "unknown"))
    stability = float(perf["formulas"].get("stability_index", 0.0))
    queued_workers = int(worker["status_counts"].get("queued", 0))
    queued_autonomy = int(autonomy["status_counts"].get("queued", 0))
    delivered_outbox = len([item for item in mesh.get("outbox", []) if item.get("status") == "delivered"])
    pending_outbox = len([item for item in mesh.get("outbox", []) if item.get("status") != "delivered"])
    failed_routes = int(router_state.get("metrics", {}).get("failed", 0))

    recommendations: list[dict[str, object]] = []
    if risk not in SAFE_RISK_LEVELS or stability < 0.2:
        recommendations.append(
            _action(
                "perf-tune",
                "Stabiliser le profil performance",
                f"risk={risk}, stability={stability:.3f}: priorite a la stabilite avant d'executer plus de travail.",
                "system-observatory",
                "safe",
                0.94,
            )
        )
        recommendations.append(
            _action(
                "mesh-compact",
                "Compacter le mesh",
                "Action legere et append-safe pour reduire le bruit d'etat pendant pression systeme.",
                "mission-control",
                "safe",
                0.74,
            )
        )
    else:
        if queued_workers:
            recommendations.append(
                _action(
                    "worker-run",
                    "Executer une session worker",
                    f"{queued_workers} worker(s) en attente et profil thermique acceptable.",
                    "worker-studio",
                    "bounded",
                    0.91,
                    {"max_items": 1},
                )
            )
        if queued_autonomy:
            max_items = 2 if risk == "nominal" else 1
            recommendations.append(
                _action(
                    "autonomy-run",
                    "Executer la file autonomy",
                    f"{queued_autonomy} lane(s) en attente, max_items={max_items} selon risk={risk}.",
                    "autonomy-lab",
                    "bounded",
                    0.88,
                    {"max_items": max_items},
                )
            )
        if not queued_workers and not queued_autonomy:
            recommendations.append(
                _action(
                    "supervisor-expand",
                    "Expansion supervisee multi-agent",
                    f"Aucune file active: MetaSupervisor propose {supervisor.get('selected_count', 0)} agent(s), clean_growth={supervisor.get('clean_growth_index')}.",
                    "autonomy-lab",
                    "creative-safe",
                    0.86,
                )
            )
            recommendations.append(
                _action(
                    "autonomy-evolve",
                    "Faire evoluer l'ecosysteme",
                    "Fallback simple si le superviseur ne selectionne aucune lane.",
                    "autonomy-lab",
                    "creative-safe",
                    0.72,
                )
            )
        if pending_outbox:
            recommendations.append(
                _action(
                    "mesh-consensus",
                    "Synchroniser le mesh",
                    f"{pending_outbox} element(s) mesh non livres ou a reconcilier.",
                    "mission-control",
                    "network-bounded",
                    0.7,
                )
            )
        elif delivered_outbox > 5 or int(daemon.get("cycle_count", 0)) > 10:
            recommendations.append(
                _action(
                    "mesh-compact",
                    "Nettoyer l'historique mesh",
                    "Le mesh contient assez d'historique pour beneficier d'une compaction.",
                    "mission-control",
                    "safe",
                    0.66,
                )
            )

    if not recommendations:
        recommendations.append(
            _action(
                "mesh-consensus",
                "Pulse leger du systeme",
                "Etat calme: maintenir la coherence sans lancer de charge lourde.",
                "mission-control",
                "safe",
                0.55,
            )
        )

    signals = {
        "queued_workers": queued_workers,
        "queued_autonomy": queued_autonomy,
        "mesh_nodes": mesh.get("node_count", 0),
        "pending_outbox": pending_outbox,
        "failed_routes": failed_routes,
    }
    formula_advice = formula_runtime_advice(workspace, perf_report=perf, router_signals=signals)
    advice_biases = dict(formula_advice.get("action_biases", {}))
    existing_ids = {str(item["id"]) for item in recommendations}
    if risk in {"elevated", "critical"} and "perf-tune" in advice_biases and "perf-tune" not in existing_ids:
        recommendations.append(
            _action(
                "perf-tune",
                "Stabiliser via FormulaAdvisor",
                "Les programmes-formules protecteurs recommandent une stabilisation avant acceleration.",
                "system-observatory",
                "safe",
                0.86,
            )
        )
    recommendations = _apply_formula_advice(recommendations, formula_advice)
    recommendations = _apply_memory(recommendations, router_state)
    report = {
        "generated_at": utc_now(),
        "risk_level": risk,
        "stability_index": stability,
        "signals": signals,
        "formula_advice": formula_advice,
        "next_action": recommendations[0],
        "recommendations": recommendations[:5],
        "memory": {
            "metrics": router_state.get("metrics", {}),
            "last_route": router_state.get("last_route"),
            "cooldowns": router_state.get("cooldowns", {}),
            "recent_routes": router_state.get("routes", [])[-5:],
        },
    }
    return report


def execute_next_route(workspace: Path) -> dict[str, object]:
    report = route_report(workspace)
    action = dict(report["next_action"])
    action_id = str(action["id"])
    payload = dict(action.get("payload", {}))

    if action_id == "perf-tune":
        result = PerformanceGovernor(workspace).apply()
    elif action_id == "mesh-compact":
        result = mesh_compact(workspace)
    elif action_id == "mesh-consensus":
        result = mesh_consensus(workspace)
    elif action_id == "worker-run":
        result = run_worker_sessions(workspace, max_items=int(payload.get("max_items", 1)))
    elif action_id == "autonomy-run":
        result = run_workloads(workspace, max_items=int(payload.get("max_items", 1)))
    elif action_id == "autonomy-evolve":
        result = evolve_ecosystem(workspace, queue_followups=True)
    elif action_id == "supervisor-expand":
        result = supervisor_run(workspace, max_lanes=4, queue=True)
    else:
        result = {"error": "unsupported_route_action", "action_id": action_id}

    append_event(
        workspace,
        "action_router_executed",
        {
            "action_id": action_id,
            "view": action.get("view"),
            "safety": action.get("safety"),
            "confidence": action.get("confidence"),
        },
    )
    route = _remember_execution(workspace, action, result, report)
    return {
        "selected": action,
        "result": result,
        "route": route,
        "report": report,
    }


def execute_route_loop(workspace: Path, max_cycles: int = 3, stop_on_elevated: bool = False) -> dict[str, object]:
    bounded_cycles = max(1, min(int(max_cycles), 10))
    executed: list[dict[str, object]] = []
    stop_reason = "max_cycles"
    sticky_action_id: str | None = None

    for index in range(bounded_cycles):
        report = route_report(workspace)
        risk = str(report.get("risk_level", "unknown"))
        action_id = str(report["next_action"]["id"])
        signals = report.get("signals", {})
        if sticky_action_id == "autonomy-run" and int(signals.get("queued_autonomy", 0)) > 0 and not stop_on_elevated:
            action_id = "autonomy-run"
        elif sticky_action_id == "worker-run" and int(signals.get("queued_workers", 0)) > 0 and not stop_on_elevated:
            action_id = "worker-run"

        if risk not in SAFE_RISK_LEVELS and action_id not in CRITICAL_ALLOWED_ACTIONS:
            if sticky_action_id in {"autonomy-run", "worker-run"} and not stop_on_elevated:
                pass
            else:
                stop_reason = f"risk_blocked:{risk}"
                break
        if stop_on_elevated and risk == "elevated" and action_id not in {"perf-tune", "mesh-compact"}:
            stop_reason = "elevated_risk_guard"
            break
        if action_id not in LOOP_ALLOWED_ACTIONS:
            stop_reason = f"unsupported_action:{action_id}"
            break

        if action_id == str(report["next_action"]["id"]):
            result = execute_next_route(workspace)
        elif action_id == "autonomy-run":
            result_payload = {"max_items": 1}
            raw_result = run_workloads(workspace, max_items=1)
            action = _action(
                "autonomy-run",
                "Executer la file autonomy",
                "Continuation d'un batch borne deja engage pour drainer proprement la file.",
                "autonomy-lab",
                "bounded",
                0.82,
                result_payload,
            )
            append_event(
                workspace,
                "action_router_executed",
                {"action_id": action_id, "view": action.get("view"), "safety": action.get("safety"), "confidence": action.get("confidence")},
            )
            route = _remember_execution(workspace, action, raw_result, report)
            result = {"selected": action, "result": raw_result, "route": route, "report": report}
        else:
            raw_result = run_worker_sessions(workspace, max_items=1)
            action = _action(
                "worker-run",
                "Executer une session worker",
                "Continuation d'un batch borne deja engage pour drainer proprement la file.",
                "worker-studio",
                "bounded",
                0.84,
                {"max_items": 1},
            )
            append_event(
                workspace,
                "action_router_executed",
                {"action_id": action_id, "view": action.get("view"), "safety": action.get("safety"), "confidence": action.get("confidence")},
            )
            route = _remember_execution(workspace, action, raw_result, report)
            result = {"selected": action, "result": raw_result, "route": route, "report": report}

        executed.append(
            {
                "cycle": index + 1,
                "action_id": action_id,
                "status": result["route"]["status"],
                "safety": result["selected"].get("safety"),
                "confidence": result["selected"].get("confidence"),
                "summary": result["route"]["result"],
            }
        )
        if result["route"]["status"] == "error":
            stop_reason = "route_error"
            break

        sticky_action_id = action_id if action_id in {"autonomy-run", "worker-run"} else None

        remaining_report = route_report(workspace)
        signals = remaining_report.get("signals", {})
        if (
            int(signals.get("queued_workers", 0)) == 0
            and int(signals.get("queued_autonomy", 0)) == 0
            and str(remaining_report["next_action"]["id"]) in {"autonomy-evolve", "mesh-consensus", "supervisor-expand"}
            and executed
        ):
            stop_reason = "queues_drained"
            break
    else:
        stop_reason = "max_cycles"

    router_state = _router_memory(workspace)
    metrics = router_state.setdefault("metrics", {})
    metrics["loops"] = int(metrics.get("loops", 0)) + 1
    router_state["last_loop"] = {
        "ts": utc_now(),
        "max_cycles": bounded_cycles,
        "executed_count": len(executed),
        "stop_reason": stop_reason,
        "executed": executed,
    }
    save_router_state(workspace, router_state)
    append_event(
        workspace,
        "action_router_loop_completed",
        {"executed_count": len(executed), "stop_reason": stop_reason, "max_cycles": bounded_cycles},
    )
    return {
        "stop_reason": stop_reason,
        "executed_count": len(executed),
        "executed": executed,
        "final_report": route_report(workspace),
    }


def simulate_route_loop(workspace: Path, max_cycles: int = 3, stop_on_elevated: bool = False) -> dict[str, object]:
    report = route_report(workspace)
    bounded_cycles = max(1, min(int(max_cycles), 10))
    signals = dict(report.get("signals", {}))
    simulated: list[dict[str, object]] = []
    risk = str(report.get("risk_level", "unknown"))
    stop_reason = "max_cycles"

    for index in range(bounded_cycles):
        queued_workers = int(signals.get("queued_workers", 0))
        queued_autonomy = int(signals.get("queued_autonomy", 0))
        pending_outbox = int(signals.get("pending_outbox", 0))

        if risk not in SAFE_RISK_LEVELS:
            stop_reason = f"risk_blocked:{risk}"
            break

        if stop_on_elevated and risk == "elevated" and (queued_workers or queued_autonomy):
            stop_reason = "elevated_risk_guard"
            break

        if queued_workers:
            action = _action(
                "worker-run",
                "Simulation worker",
                f"Simulated worker execution from queued_workers={queued_workers}.",
                "worker-studio",
                "bounded",
                0.91,
                {"max_items": 1},
            )
            signals["queued_workers"] = max(0, queued_workers - 1)
        elif queued_autonomy:
            max_items = 2 if risk in {"low", "nominal"} else 1
            action = _action(
                "autonomy-run",
                "Simulation autonomy",
                f"Simulated autonomy execution from queued_autonomy={queued_autonomy}.",
                "autonomy-lab",
                "bounded",
                0.88,
                {"max_items": max_items},
            )
            signals["queued_autonomy"] = max(0, queued_autonomy - max_items)
        elif pending_outbox:
            action = _action(
                "mesh-consensus",
                "Simulation mesh consensus",
                f"Simulated reconciliation from pending_outbox={pending_outbox}.",
                "mission-control",
                "network-bounded",
                0.7,
            )
            signals["pending_outbox"] = 0
        else:
            action = _action(
                "autonomy-evolve",
                "Simulation ecosystem evolve",
                "Simulated generation of one balanced follow-up lane.",
                "autonomy-lab",
                "creative-safe",
                0.82,
            )
            signals["queued_autonomy"] = int(signals.get("queued_autonomy", 0)) + 1
            stop_reason = "would_generate_followup"

        simulated.append(
            {
                "cycle": index + 1,
                "action_id": action["id"],
                "safety": action["safety"],
                "confidence": action["confidence"],
                "payload": action["payload"],
                "signals_after": dict(signals),
                "reason": action["reason"],
            }
        )

        if stop_reason == "would_generate_followup":
            break
        if int(signals.get("queued_workers", 0)) == 0 and int(signals.get("queued_autonomy", 0)) == 0 and int(signals.get("pending_outbox", 0)) == 0:
            stop_reason = "queues_would_drain"
            break
    else:
        stop_reason = "max_cycles"

    return {
        "simulated_at": utc_now(),
        "stop_reason": stop_reason,
        "would_execute_count": len(simulated),
        "simulated": simulated,
        "initial_report": report,
        "projected_signals": signals,
        "mutated_workspace": False,
    }
