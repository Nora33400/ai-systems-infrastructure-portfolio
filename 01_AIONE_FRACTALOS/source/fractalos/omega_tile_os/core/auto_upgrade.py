from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from .action_router import execute_route_loop, simulate_route_loop
from .autonomy_runtime import autonomy_report, evolve_ecosystem
from .codex_worker import run_worker_sessions, worker_report
from .events import append_event
from .formula_programs import evolve_formula_programs, formula_program_report
from .fractal_kernel import kernel_boot
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .scientific_formula_forge import scientific_formula_plan, scientific_formula_report
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


OPTIMIZED_USER_REQUEST = (
    "Fais tourner FractalOS en mode auto-upgrade pendant environ une heure. "
    "A chaque cycle, genere un plan de mise a jour et des programmes candidats, "
    "verifie-les avec doctor, simulation, tests et build kernel quand possible, "
    "redemarre en safe-mode, reteste, puis integre uniquement les candidats prouves. "
    "Archive tout dans des rapports et une documentation lisible."
)

UPGRADE_AXES = [
    {
        "id": "proofstate-promotion-gate",
        "domain": "security-proof",
        "formula": "P_promote = min(D_doctor, T_tests, B_build, S_safe_boot) * C_confidence",
        "target": "ProofState + AutoUpgradeKernel",
        "intent": "Ne promouvoir que les etats passes par doctor, tests, build et redemarrage safe.",
        "risk": 0.08,
        "value": 0.96,
    },
    {
        "id": "timeforge-cycle",
        "domain": "time-simulation",
        "formula": "T_cycle = min(T_budget, T_safe) / (1 + Q_queue + R_risk)",
        "target": "ActionRouter + FutureFabric",
        "intent": "Transformer chaque heure en cycles courts, mesurables, rollbackables.",
        "risk": 0.12,
        "value": 0.88,
    },
    {
        "id": "matterfs-density",
        "domain": "storage-density",
        "formula": "D_eff = (1 + H_dup + H_delta) * C_codec * A_heat",
        "target": "TileMindFS",
        "intent": "Compacter les rapports, programmes et etats sans jamais detruire les originaux.",
        "risk": 0.10,
        "value": 0.92,
    },
    {
        "id": "semantic-ram-retention",
        "domain": "memory-indexing",
        "formula": "R_keep = sigmoid(2H_access + C_context - P_pressure)",
        "target": "OmegaRAM",
        "intent": "Garder chaud ce qui sert a l'auto-developpement et demoter le reste.",
        "risk": 0.10,
        "value": 0.89,
    },
    {
        "id": "agent-foundry-lanes",
        "domain": "agent-foundry",
        "formula": "A_gain = min(W_workers, B_budget) * P_proof * (1 - R_risk)",
        "target": "Worker Studio + Autonomy Lab",
        "intent": "Creer des lanes IA bornees qui planifient, produisent, verifient et documentent.",
        "risk": 0.18,
        "value": 0.93,
    },
    {
        "id": "thermal-sustained-build",
        "domain": "thermal-energy",
        "formula": "Q_safe = cores * S_stability * sqrt(T_headroom)",
        "target": "PerformanceGovernor",
        "intent": "Maintenir une vitesse longue duree sans chauffe ni degradation.",
        "risk": 0.06,
        "value": 0.86,
    },
    {
        "id": "desktop-overlay-control",
        "domain": "ui-control-plane",
        "formula": "U_focus = I_goal * P_overlay / (1 + N_noise)",
        "target": "Fractal Desktop Overlay",
        "intent": "Faire du desktop un tableau de bord persistant au-dessus des apps.",
        "risk": 0.09,
        "value": 0.84,
    },
    {
        "id": "corpus-formula-ingestion",
        "domain": "research-integration",
        "formula": "I_use = C_coverage * log10(N_formulas) * S_relevance",
        "target": "Corpus Integration Lab",
        "intent": "Utiliser le corpus de formules comme carburant de priorisation et non comme texte passif.",
        "risk": 0.07,
        "value": 0.94,
    },
]


def _state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "auto_upgrade.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp_path.replace(path)


def _load_state(workspace: Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        state = {
            "sessions": [],
            "metrics": {
                "runs": 0,
                "cycles": 0,
                "generated_programs": 0,
                "promoted_programs": 0,
                "rejected_programs": 0,
                "safe_restarts": 0,
                "integrated_restarts": 0,
                "test_runs": 0,
            },
            "last_session": None,
        }
        _atomic_write_json(path, state)
        return state
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(_state_path(workspace), state)


def _project_root(workspace: Path) -> Path:
    return workspace.parent if workspace.name == "workspace" else workspace


def _auto_root(workspace: Path) -> Path:
    root = workspace / "auto_upgrade"
    for name in ("programs", "reports", "docs", "runs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _compact_doctor(doctor: dict[str, Any]) -> dict[str, Any]:
    warn_names = [item["name"] for item in doctor.get("checks", []) if item.get("status") == "warn"]
    fail_names = [item["name"] for item in doctor.get("checks", []) if item.get("status") == "fail"]
    return {
        "status": doctor.get("status"),
        "counts": doctor.get("counts", {}),
        "warn_names": warn_names,
        "fail_names": fail_names,
    }


def _score_axis(axis: dict[str, Any], cycle_index: int, perf: dict[str, Any], formula_report: dict[str, Any]) -> float:
    formulas = dict(perf.get("formulas", {}))
    recommendations = dict(perf.get("recommendations", {}))
    stability = float(formulas.get("stability_index", 0.65) or 0.65)
    throughput = float(formulas.get("throughput_index", 0.65) or 0.65)
    risk_level = str(recommendations.get("risk_level", "low"))
    risk_guard = {"low": 1.0, "nominal": 0.92, "elevated": 0.74, "critical": 0.35}.get(risk_level, 0.65)
    corpus = dict(formula_report.get("corpus_index") or {})
    corpus_boost = 0.08 * float(corpus.get("coverage_ratio", 0.0) or 0.0)
    cadence = 1.0 - min(0.12, (cycle_index % 5) * 0.015)
    value = float(axis["value"])
    risk = float(axis["risk"])
    score = value * (0.38 * stability + 0.22 * throughput + 0.24 * risk_guard + 0.16 * (1.0 - risk) + corpus_boost) * cadence
    return round(max(0.0, min(1.0, score)), 4)


def _plan_cycle(workspace: Path, cycle_index: int, programs_per_cycle: int) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    formula_report = scientific_formula_report(workspace)
    worker = worker_report(workspace)
    autonomy = autonomy_report(workspace)
    scored = []
    for axis in UPGRADE_AXES:
        scored.append({**axis, "score": _score_axis(axis, cycle_index, perf, formula_report)})
    scored.sort(key=lambda item: float(item["score"]), reverse=True)
    selected = scored[: max(1, min(programs_per_cycle, len(scored)))]
    return {
        "cycle": cycle_index,
        "generated_at": utc_now(),
        "optimized_request": OPTIMIZED_USER_REQUEST,
        "selected_axes": selected,
        "signals": {
            "perf_risk": perf.get("recommendations", {}).get("risk_level"),
            "stability": perf.get("formulas", {}).get("stability_index"),
            "throughput": perf.get("formulas", {}).get("throughput_index"),
            "queued_workers": worker.get("status_counts", {}).get("queued", 0),
            "queued_autonomy": autonomy.get("status_counts", {}).get("queued", 0),
            "formula_catalog": formula_report.get("catalog_total", 0),
            "corpus_coverage": (formula_report.get("corpus_index") or {}).get("coverage_ratio", 0.0),
        },
    }


def _program_payload(session_id: str, cycle_index: int, axis: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    program_id = f"auto-{cycle_index:03d}-{axis['id']}-{uuid4().hex[:8]}"
    safety_score = round(max(0.0, min(1.0, float(axis["score"]) * (1.0 - 0.55 * float(axis["risk"])))), 4)
    return {
        "schema": "fractalos.auto_upgrade_program.v1",
        "id": program_id,
        "session_id": session_id,
        "cycle": cycle_index,
        "created_at": utc_now(),
        "status": "candidate",
        "axis": axis["id"],
        "domain": axis["domain"],
        "target": axis["target"],
        "intent": axis["intent"],
        "formula": axis["formula"],
        "selection_score": axis["score"],
        "safety_score": safety_score,
        "implementation_contract": {
            "mode": "reversible-program",
            "writes": "workspace/auto_upgrade + queued bounded worker/autonomy tasks",
            "forbidden": ["destructive filesystem operations", "unverified kernel mutation", "hardware overclocking"],
            "rollback": "candidate remains data-only until promotion gates pass",
        },
        "verification_contract": {
            "doctor_required": True,
            "router_simulation_required": True,
            "safe_restart_required": True,
            "unit_tests_required_when_requested": True,
            "bare_metal_build_required_when_requested": True,
        },
        "runtime_plan": [
            "Generate candidate program",
            "Archive in TileMindFS and OmegaRAM",
            "Run doctor and route simulation",
            "Boot FractalOS control kernel in safe validation mode",
            "Retest after safe boot",
            "Promote only if fail count stays zero",
        ],
        "cycle_signals": plan["signals"],
    }


def _render_program(program: dict[str, Any]) -> str:
    lines = [
        f"# Auto Upgrade Program :: {program['id']}",
        "",
        f"- Session: {program['session_id']}",
        f"- Cycle: {program['cycle']}",
        f"- Status: {program['status']}",
        f"- Domain: {program['domain']}",
        f"- Target: {program['target']}",
        f"- Selection score: {program['selection_score']}",
        f"- Safety score: {program['safety_score']}",
        "",
        "## Intent",
        str(program["intent"]),
        "",
        "## Formula",
        f"`{program['formula']}`",
        "",
        "## Runtime Plan",
    ]
    lines.extend(f"- {item}" for item in program["runtime_plan"])
    lines.extend(
        [
            "",
            "## Promotion Gate",
            "- doctor fail count must be 0",
            "- router simulation must stay read-only",
            "- safe restart must complete",
            "- tests/build must pass when requested",
            "",
        ]
    )
    return "\n".join(lines)


def _write_program(workspace: Path, program: dict[str, Any]) -> dict[str, Any]:
    root = _auto_root(workspace) / "programs" / str(program["id"])
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "PROGRAM.json"
    md_path = root / "PROGRAM.md"
    json_path.write_text(json.dumps(program, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_render_program(program), encoding="utf-8")
    tile = TileMindFS(workspace).store_file(md_path)
    OmegaRAM(workspace).put_text(
        key=f"auto_upgrade::program::{program['id']}",
        text=md_path.read_text(encoding="utf-8"),
        source="auto_upgrade",
    )
    return {
        "id": program["id"],
        "status": program["status"],
        "domain": program["domain"],
        "target": program["target"],
        "json_path": str(json_path),
        "report_path": str(md_path),
        "tile_manifest": tile.get("manifest_id", ""),
        "safety_score": program["safety_score"],
    }


def _generate_programs(workspace: Path, session_id: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    generated = []
    for axis in plan["selected_axes"]:
        generated.append(_write_program(workspace, _program_payload(session_id, int(plan["cycle"]), axis, plan)))
    append_event(workspace, "auto_upgrade_programs_generated", {"session_id": session_id, "count": len(generated)})
    return generated


def _run_command(command: list[str], cwd: Path, timeout_s: int) -> dict[str, Any]:
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout = completed.stdout[-4000:]
        stderr = completed.stderr[-4000:]
        return {
            "command": command,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "duration_s": round(time.monotonic() - started, 3),
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "ok": False,
            "duration_s": round(time.monotonic() - started, 3),
            "timeout_s": timeout_s,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "error": "timeout",
        }


def _verify_cycle(workspace: Path, run_tests: bool, run_bare_metal_build: bool) -> dict[str, Any]:
    from .doctor import run_doctor

    project_root = _project_root(workspace)
    doctor = run_doctor(workspace)
    route_simulation = simulate_route_loop(workspace, max_cycles=3, stop_on_elevated=True)
    commands = []
    if run_tests:
        commands.append(
            _run_command(
                [sys.executable, "-m", "unittest", "discover", "-s", str(project_root / "tests")],
                cwd=project_root,
                timeout_s=900,
            )
        )
    if run_bare_metal_build and (project_root / "bare_metal" / "build.ps1").exists():
        commands.append(
            _run_command(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(project_root / "bare_metal" / "build.ps1"),
                ],
                cwd=project_root,
                timeout_s=300,
            )
        )
    ok = (
        int(doctor.get("counts", {}).get("fail", 0)) == 0
        and not bool(route_simulation.get("mutated_workspace"))
        and all(item.get("ok") for item in commands)
    )
    return {
        "ok": ok,
        "doctor": _compact_doctor(doctor),
        "route_simulation": {
            "stop_reason": route_simulation.get("stop_reason"),
            "would_execute_count": route_simulation.get("would_execute_count"),
            "mutated_workspace": route_simulation.get("mutated_workspace"),
        },
        "commands": commands,
    }


def _safe_restart(workspace: Path, session_id: str, cycle_index: int) -> dict[str, Any]:
    boot = kernel_boot(workspace)
    from .usage_blackbox import run_restart_recovery

    recovery = run_restart_recovery(workspace, reason=f"auto-upgrade-safe-restart:{session_id}:{cycle_index}", apply=True, run_doctor_check=True)
    result = {
        "ts": utc_now(),
        "session_id": session_id,
        "cycle": cycle_index,
        "mode": "safe-validation",
        "boot_count": boot.get("state", {}).get("boot_count"),
        "kernel_mode": boot.get("kernel", {}).get("mode"),
        "risk_level": boot.get("risk_level"),
        "recovery": {
            "failed_after": recovery.get("after", {}).get("failed_count"),
            "rollbacks": len([item for item in recovery.get("rollbacks", []) if item.get("rolled_back")]),
            "report_path": recovery.get("report_path"),
        },
    }
    append_event(workspace, "auto_upgrade_safe_restart", result)
    return result


def _integrated_restart(workspace: Path, session_id: str, cycle_index: int) -> dict[str, Any]:
    boot = kernel_boot(workspace)
    result = {
        "ts": utc_now(),
        "session_id": session_id,
        "cycle": cycle_index,
        "mode": "integrated",
        "boot_count": boot.get("state", {}).get("boot_count"),
        "kernel_mode": boot.get("kernel", {}).get("mode"),
        "risk_level": boot.get("risk_level"),
    }
    append_event(workspace, "auto_upgrade_integrated_restart", result)
    return result


def _promote_programs(workspace: Path, programs: list[dict[str, Any]], verification: dict[str, Any], safe_verification: dict[str, Any]) -> dict[str, Any]:
    promoted = []
    rejected = []
    can_promote = bool(verification.get("ok")) and bool(safe_verification.get("ok"))
    for item in programs:
        json_path = Path(str(item["json_path"]))
        program = json.loads(json_path.read_text(encoding="utf-8"))
        if can_promote and float(item.get("safety_score", 0.0)) >= 0.52:
            program["status"] = "promoted"
            program["promoted_at"] = utc_now()
            promoted.append(_write_program(workspace, program))
        else:
            program["status"] = "rejected"
            program["rejected_at"] = utc_now()
            program["rejection_reason"] = "promotion_gate_failed"
            rejected.append(_write_program(workspace, program))
    append_event(workspace, "auto_upgrade_programs_promoted", {"promoted": len(promoted), "rejected": len(rejected)})
    return {
        "promoted": promoted,
        "rejected": rejected,
    }


def _write_cycle_report(workspace: Path, session: dict[str, Any], cycle: dict[str, Any]) -> str:
    root = _auto_root(workspace) / "reports"
    path = root / f"AUTO_UPGRADE_{session['id']}_CYCLE_{int(cycle['cycle']):03d}.md"
    lines = [
        f"# FractalOS Auto Upgrade Cycle {cycle['cycle']}",
        "",
        f"- Session: {session['id']}",
        f"- Generated at: {cycle['ts']}",
        f"- Decision: {cycle['decision']}",
        f"- Promoted: {len(cycle['promotion']['promoted'])}",
        f"- Rejected: {len(cycle['promotion']['rejected'])}",
        "",
        "## Plan",
        f"- Optimized request: {OPTIMIZED_USER_REQUEST}",
    ]
    for axis in cycle["plan"]["selected_axes"]:
        lines.append(f"- {axis['id']} :: score={axis['score']} :: target={axis['target']}")
    lines.extend(["", "## Verification"])
    lines.append(f"- Before safe restart: ok={cycle['verification']['ok']} doctor={cycle['verification']['doctor']}")
    lines.append(f"- After safe restart: ok={cycle['safe_verification']['ok']} doctor={cycle['safe_verification']['doctor']}")
    if cycle["verification"].get("commands"):
        lines.append("")
        lines.append("## Commands")
        for command in cycle["verification"]["commands"]:
            lines.append(f"- ok={command.get('ok')} rc={command.get('returncode')} duration={command.get('duration_s')} :: {' '.join(command.get('command', []))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"auto_upgrade::cycle::{session['id']}::{cycle['cycle']}",
        text=path.read_text(encoding="utf-8"),
        source="auto_upgrade",
    )
    cycle["cycle_report_path"] = str(path)
    cycle["cycle_tile_manifest"] = tile.get("manifest_id", "")
    return str(path)


def _write_session_report(workspace: Path, session: dict[str, Any], final: bool = False) -> str:
    root = _auto_root(workspace) / "reports"
    suffix = "FINAL" if final else "LIVE"
    path = root / f"AUTO_UPGRADE_{session['id']}_{suffix}.md"
    decisions = Counter(str(item.get("decision", "unknown")) for item in session.get("cycles", []))
    lines = [
        "# FractalOS Auto Upgrade Session",
        "",
        f"- Session: {session['id']}",
        f"- Status: {session['status']}",
        f"- Started at: {session['started_at']}",
        f"- Updated at: {session.get('updated_at')}",
        f"- Duration target seconds: {session['duration_seconds']}",
        f"- Cycles completed: {len(session.get('cycles', []))}",
        f"- Decision counts: {dict(decisions)}",
        "",
        "## Optimized Request",
        OPTIMIZED_USER_REQUEST,
        "",
        "## Promotion Model",
        "- plan -> candidate programs -> doctor/route simulation/tests/build -> safe restart -> retest -> promotion -> integrated restart",
        "- candidates stay reversible data programs until the proof gate passes",
        "- hardware safety stays under PerformanceGovernor and no overclocking is attempted",
        "",
        "## Cycles",
    ]
    for cycle in session.get("cycles", []):
        lines.append(
            f"- cycle {cycle['cycle']}: decision={cycle['decision']} promoted={len(cycle['promotion']['promoted'])} rejected={len(cycle['promotion']['rejected'])} report={cycle.get('cycle_report_path')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"auto_upgrade::session::{session['id']}::{suffix.lower()}",
        text=path.read_text(encoding="utf-8"),
        source="auto_upgrade",
    )
    return str(path)


def write_auto_upgrade_documentation(workspace: Path) -> dict[str, str]:
    ensure_workspace(workspace)
    project_root = _project_root(workspace)
    docs_path = project_root / "docs" / "AUTO_UPGRADE_MODE.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_text = (
        "# FractalOS Auto Upgrade Mode\n\n"
        "Auto Upgrade Mode is the guarded self-evolution loop for FractalOS.\n\n"
        "## Optimized request\n"
        f"{OPTIMIZED_USER_REQUEST}\n\n"
        "## Pipeline\n"
        "1. Observe runtime telemetry, queues, corpus coverage and formula plans.\n"
        "2. Generate bounded upgrade programs in `workspace/auto_upgrade/programs`.\n"
        "3. Run doctor, route simulation, optional unit tests and optional bare-metal build.\n"
        "4. Reboot the FractalOS control kernel in safe-validation mode.\n"
        "5. Retest after safe boot.\n"
        "6. Promote only the candidates that pass every gate.\n"
        "7. Reboot again in integrated mode and archive reports.\n\n"
        "## Scientific safety formulas\n"
        "- Promotion: `P_promote = min(D_doctor, T_tests, B_build, S_safe_boot) * C_confidence`.\n"
        "- Sustained performance: `Q_safe = cores * S_stability * sqrt(T_headroom)`.\n"
        "- Effective storage: `D_eff = (1 + H_dup + H_delta) * C_codec * A_heat`.\n"
        "- Semantic RAM: `R_keep = sigmoid(2H_access + C_context - P_pressure)`.\n\n"
        "## Commands\n"
        "```powershell\n"
        "python -m omega_tile_os auto-upgrade --workspace .\\workspace --duration-minutes 60 --cycle-delay 60 --run-tests\n"
        "python -m omega_tile_os auto-upgrade-report --workspace .\\workspace\n"
        "```\n\n"
        "## Guardrails\n"
        "- The loop does not overclock hardware.\n"
        "- Generated programs are data-first and reversible.\n"
        "- Kernel/source mutations require tests and explicit implementation work.\n"
        "- A failed doctor/test/build gate rejects candidates instead of integrating them.\n"
    )
    docs_path.write_text(docs_text, encoding="utf-8")
    workspace_doc = _auto_root(workspace) / "docs" / f"AUTO_UPGRADE_RUNBOOK_{len(list((_auto_root(workspace) / 'docs').glob('AUTO_UPGRADE_RUNBOOK_*.md'))) + 1:04d}.md"
    workspace_doc.write_text(docs_text, encoding="utf-8")
    TileMindFS(workspace).store_file(docs_path)
    TileMindFS(workspace).store_file(workspace_doc)
    return {
        "project_doc": str(docs_path),
        "workspace_doc": str(workspace_doc),
    }


def auto_upgrade_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    reports = sorted((_auto_root(workspace) / "reports").glob("AUTO_UPGRADE_*.md"))
    programs = sorted((_auto_root(workspace) / "programs").glob("*/PROGRAM.json"))
    status_counts = Counter()
    for program_path in programs:
        try:
            status_counts[json.loads(program_path.read_text(encoding="utf-8")).get("status", "unknown")] += 1
        except json.JSONDecodeError:
            status_counts["invalid"] += 1
    return {
        "generated_at": utc_now(),
        "metrics": state.get("metrics", {}),
        "last_session": state.get("last_session"),
        "session_count": len(state.get("sessions", [])),
        "program_count": len(programs),
        "program_status_counts": dict(status_counts),
        "latest_report": str(reports[-1]) if reports else None,
        "optimized_request": OPTIMIZED_USER_REQUEST,
    }


def run_auto_upgrade_session(
    workspace: Path,
    duration_minutes: float = 60.0,
    cycle_delay_seconds: float = 60.0,
    max_cycles: int | None = None,
    programs_per_cycle: int = 3,
    corpus_root: Path | None = None,
    run_tests: bool = False,
    run_bare_metal_build: bool = True,
) -> dict[str, Any]:
    ensure_workspace(workspace)
    docs = write_auto_upgrade_documentation(workspace)
    state = _load_state(workspace)
    session = {
        "id": uuid4().hex[:12],
        "status": "running",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "duration_seconds": max(1, int(float(duration_minutes) * 60)),
        "cycle_delay_seconds": max(0.0, float(cycle_delay_seconds)),
        "max_cycles": max_cycles,
        "run_tests": run_tests,
        "run_bare_metal_build": run_bare_metal_build,
        "docs": docs,
        "cycles": [],
        "optimized_request": OPTIMIZED_USER_REQUEST,
    }
    state.setdefault("sessions", []).append(session)
    state["sessions"] = state["sessions"][-20:]
    state.setdefault("metrics", {})["runs"] = int(state.setdefault("metrics", {}).get("runs", 0)) + 1
    state["last_session"] = {"id": session["id"], "status": session["status"], "started_at": session["started_at"]}
    _save_state(workspace, state)
    append_event(workspace, "auto_upgrade_session_started", {"session_id": session["id"], "duration_seconds": session["duration_seconds"]})

    start = time.monotonic()
    end = start + session["duration_seconds"]
    cycle_index = 0
    stop_reason = "duration_elapsed"

    try:
        while time.monotonic() < end:
            if max_cycles is not None and cycle_index >= max(1, int(max_cycles)):
                stop_reason = "max_cycles"
                break
            cycle_index += 1
            plan = _plan_cycle(workspace, cycle_index, programs_per_cycle)
            programs = _generate_programs(workspace, session["id"], plan)
            formula_plan = scientific_formula_plan(workspace, limit=max(3, programs_per_cycle), queue=False)
            formula_evolution = evolve_formula_programs(
                workspace,
                corpus_root=corpus_root,
                refresh=bool(corpus_root) and cycle_index == 1,
                max_formula_files=6,
                max_programs=6,
                queue_limit=2,
            )
            verification = _verify_cycle(workspace, run_tests=run_tests, run_bare_metal_build=run_bare_metal_build)
            safe_restart = _safe_restart(workspace, session["id"], cycle_index)
            safe_verification = _verify_cycle(workspace, run_tests=run_tests, run_bare_metal_build=run_bare_metal_build)
            promotion = _promote_programs(workspace, programs, verification, safe_verification)
            integrated_restart = None
            decision = "rejected"
            if promotion["promoted"]:
                route_loop = execute_route_loop(workspace, max_cycles=2, stop_on_elevated=True)
                worker_drain = run_worker_sessions(workspace, max_items=1)
                ecosystem = evolve_ecosystem(workspace, queue_followups=True)
                integrated_restart = _integrated_restart(workspace, session["id"], cycle_index)
                decision = "promoted"
            else:
                route_loop = {"skipped": True, "reason": "no_promoted_program"}
                worker_drain = {"skipped": True, "reason": "no_promoted_program"}
                ecosystem = {"skipped": True, "reason": "no_promoted_program"}

            cycle = {
                "cycle": cycle_index,
                "ts": utc_now(),
                "decision": decision,
                "plan": plan,
                "programs": programs,
                "formula_plan": {
                    "report_path": formula_plan.get("report_path"),
                    "selected_count": len(formula_plan.get("selected", [])),
                },
                "formula_evolution": {
                    "report_path": formula_evolution.get("evolution", {}).get("report_path"),
                    "queued_count": len(formula_evolution.get("queued", [])),
                },
                "verification": verification,
                "safe_restart": safe_restart,
                "safe_verification": safe_verification,
                "promotion": promotion,
                "route_loop": route_loop,
                "worker_drain": {
                    "processed_count": len(worker_drain.get("processed", [])) if isinstance(worker_drain, dict) else 0,
                    "queued_remaining": worker_drain.get("queued_remaining") if isinstance(worker_drain, dict) else None,
                },
                "ecosystem": {
                    "report_path": ecosystem.get("report_path") if isinstance(ecosystem, dict) else None,
                    "queued_count": len(ecosystem.get("queued", [])) if isinstance(ecosystem, dict) else 0,
                },
                "integrated_restart": integrated_restart,
            }
            _write_cycle_report(workspace, session, cycle)
            session.setdefault("cycles", []).append(cycle)
            session["updated_at"] = utc_now()
            _write_session_report(workspace, session, final=False)

            state = _load_state(workspace)
            metrics = state.setdefault("metrics", {})
            metrics["cycles"] = int(metrics.get("cycles", 0)) + 1
            metrics["generated_programs"] = int(metrics.get("generated_programs", 0)) + len(programs)
            metrics["promoted_programs"] = int(metrics.get("promoted_programs", 0)) + len(promotion["promoted"])
            metrics["rejected_programs"] = int(metrics.get("rejected_programs", 0)) + len(promotion["rejected"])
            metrics["safe_restarts"] = int(metrics.get("safe_restarts", 0)) + 1
            metrics["integrated_restarts"] = int(metrics.get("integrated_restarts", 0)) + (1 if integrated_restart else 0)
            metrics["test_runs"] = int(metrics.get("test_runs", 0)) + len(verification.get("commands", [])) + len(safe_verification.get("commands", []))
            state["last_session"] = {"id": session["id"], "status": "running", "updated_at": session["updated_at"], "cycles": len(session["cycles"])}
            if state.get("sessions"):
                state["sessions"][-1] = session
            _save_state(workspace, state)
            append_event(workspace, "auto_upgrade_cycle_completed", {"session_id": session["id"], "cycle": cycle_index, "decision": decision})

            remaining = end - time.monotonic()
            if remaining <= 0:
                stop_reason = "duration_elapsed"
                break
            delay = min(float(session["cycle_delay_seconds"]), remaining)
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    except Exception as exc:
        stop_reason = "error"
        session["error"] = f"{type(exc).__name__}: {exc}"
        append_event(workspace, "auto_upgrade_session_error", {"session_id": session["id"], "error": session["error"]})

    session["status"] = "completed" if stop_reason in {"duration_elapsed", "max_cycles"} else stop_reason
    session["completed_at"] = utc_now()
    session["updated_at"] = session["completed_at"]
    session["stop_reason"] = stop_reason
    final_report = _write_session_report(workspace, session, final=True)

    state = _load_state(workspace)
    if state.get("sessions"):
        state["sessions"][-1] = session
    state["last_session"] = {
        "id": session["id"],
        "status": session["status"],
        "completed_at": session["completed_at"],
        "cycles": len(session.get("cycles", [])),
        "final_report": final_report,
    }
    _save_state(workspace, state)
    append_event(workspace, "auto_upgrade_session_completed", {"session_id": session["id"], "stop_reason": stop_reason, "cycles": len(session.get("cycles", []))})
    return {
        "session_id": session["id"],
        "status": session["status"],
        "stop_reason": stop_reason,
        "cycles": len(session.get("cycles", [])),
        "final_report": final_report,
        "live_report": str(_auto_root(workspace) / "reports" / f"AUTO_UPGRADE_{session['id']}_LIVE.md"),
        "docs": docs,
        "optimized_request": OPTIMIZED_USER_REQUEST,
    }
