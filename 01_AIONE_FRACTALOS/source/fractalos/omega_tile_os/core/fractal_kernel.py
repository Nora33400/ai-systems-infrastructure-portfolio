from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_runtime import autonomy_report
from .codex_worker import worker_report
from .desktop_runtime import desktop_catalog
from .events import append_event
from .formula_programs import formula_runtime_advice
from .meta_supervisor import supervisor_report
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


KERNEL_SERVICES = [
    {
        "id": "capability-manager",
        "ring": 0,
        "purpose": "Attribuer des droits bornes aux agents, apps et services.",
        "capabilities": ["read_state", "write_memory", "queue_safe_work"],
    },
    {
        "id": "scheduler",
        "ring": 0,
        "purpose": "Choisir combien d'agents peuvent tourner selon risque, stabilite et pression de file.",
        "capabilities": ["schedule_worker", "schedule_autonomy", "throttle"],
    },
    {
        "id": "memory-bus",
        "ring": 0,
        "purpose": "Relier OmegaRAM, TileMindFS et rapports systeme.",
        "capabilities": ["read_memory", "archive_report", "promote_context"],
    },
    {
        "id": "agent-bus",
        "ring": 1,
        "purpose": "Connecter chatbot, workers, autonomy lanes et superviseur.",
        "capabilities": ["queue_agent", "queue_workload", "reflect"],
    },
    {
        "id": "desktop-host",
        "ring": 2,
        "purpose": "Presenter apps et services comme un environnement utilisateur.",
        "capabilities": ["open_app", "plan_service"],
    },
    {
        "id": "desktop-plane",
        "ring": 1,
        "purpose": "Maintenir un overlay persistant d intention, preuves, energie et agents au-dessus des apps.",
        "capabilities": ["inspect_overlay", "cycle_overlay", "archive_desktop"],
    },
    {
        "id": "scientific-formula-plane",
        "ring": 1,
        "purpose": "Transformer des formules bornees en politiques materielles reversibles.",
        "capabilities": ["score_formula", "plan_formula_upgrade", "archive_formula_report"],
    },
]

SYSCALLS = {
    "kernel.status": {"capability": "read_state", "mutates": False},
    "kernel.schedule": {"capability": "schedule_worker", "mutates": False},
    "kernel.archive": {"capability": "archive_report", "mutates": True},
    "desktop.open": {"capability": "open_app", "mutates": True},
    "desktop.overlay": {"capability": "inspect_overlay", "mutates": False},
    "desktop.overlay.cycle": {"capability": "cycle_overlay", "mutates": True},
    "formula.scientific.plan": {"capability": "plan_formula_upgrade", "mutates": True},
    "agent.queue": {"capability": "queue_agent", "mutates": True},
    "memory.promote": {"capability": "promote_context", "mutates": True},
}


def _kernel_state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "fractal_kernel.json"


def _load_kernel_state(workspace: Path) -> dict[str, Any]:
    path = _kernel_state_path(workspace)
    if not path.exists():
        state = {
            "boot_count": 0,
            "syscalls": [],
            "last_boot": None,
            "metrics": {
                "archives": 0,
                "syscalls": 0,
                "denied": 0,
            },
        }
        path.write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")
        return state
    return json.loads(path.read_text(encoding="utf-8"))


def _save_kernel_state(workspace: Path, state: dict[str, Any]) -> None:
    _kernel_state_path(workspace).write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def _queue_pressure(workspace: Path) -> float:
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    queued = int(autonomy["status_counts"].get("queued", 0)) + int(worker["status_counts"].get("queued", 0))
    return min(1.0, queued / 24.0)


def kernel_boot(workspace: Path) -> dict[str, Any]:
    state = _load_kernel_state(workspace)
    state["boot_count"] = int(state.get("boot_count", 0)) + 1
    state["last_boot"] = utc_now()
    _save_kernel_state(workspace, state)
    append_event(workspace, "fractal_kernel_booted", {"boot_count": state["boot_count"]})
    return kernel_status(workspace)


def kernel_status(workspace: Path) -> dict[str, Any]:
    state = _load_kernel_state(workspace)
    perf = PerformanceGovernor(workspace).report()
    supervisor = supervisor_report(workspace)
    desktop = desktop_catalog(workspace)
    advice = formula_runtime_advice(
        workspace,
        perf_report=perf,
        router_signals={
            "queued_autonomy": int(autonomy_report(workspace)["status_counts"].get("queued", 0)),
            "queued_workers": int(worker_report(workspace)["status_counts"].get("queued", 0)),
        },
    )
    risk = str(perf["recommendations"].get("risk_level", "unknown"))
    stability = float(perf["formulas"].get("stability_index", 0.0))
    pressure = _queue_pressure(workspace)
    kernel_score = round(max(0.0, min(1.0, 0.42 * stability + 0.24 * (1.0 - pressure) + 0.18 * (0.0 if risk == "critical" else 0.55 if risk == "elevated" else 1.0) + 0.16 * min(1.0, int(advice.get("program_count", 0)) / 8.0))), 4)
    mode = "protect" if risk == "critical" else "stabilize" if pressure > 0.65 or risk == "elevated" else "expand"
    return {
        "generated_at": utc_now(),
        "kernel": {
            "name": "FractalOS Control Kernel",
            "version": "0.2.0",
            "mode": mode,
            "score": kernel_score,
            "boundary": "control plane for build, agents and services; the real hardware kernel source lives in bare_metal/kernel",
        },
        "real_kernel": {
            "name": "FractalOS Bare Metal Kernel",
            "arch": "x86_64",
            "boot_protocol": "Limine",
            "entry": "_start -> fractal_kernel_main",
            "source_root": str((workspace.parent / "bare_metal").resolve()) if workspace.name == "workspace" else "bare_metal",
            "stage": "stage20-scientific-formula-hardware-plane",
            "next_subsystems": ["filesystem", "process-address-spaces", "ipc-primitives", "process-scheduler", "ring3-transition", "topology-graph"],
        },
        "services": KERNEL_SERVICES,
        "syscalls": SYSCALLS,
        "risk_level": risk,
        "stability_index": stability,
        "queue_pressure": round(pressure, 4),
        "supervisor": supervisor,
        "desktop": {
            "apps": len(desktop["apps"]),
            "services": len(desktop["services"]),
            "mode": desktop["os_mode"],
        },
        "formula_advice": {
            "program_count": advice.get("program_count", 0),
            "protective_program_count": advice.get("protective_program_count", 0),
            "action_biases": advice.get("action_biases", {}),
        },
        "state": {
            "boot_count": state.get("boot_count", 0),
            "last_boot": state.get("last_boot"),
            "metrics": state.get("metrics", {}),
        },
    }


def kernel_schedule(workspace: Path) -> dict[str, Any]:
    status = kernel_status(workspace)
    mode = status["kernel"]["mode"]
    risk = status["risk_level"]
    if mode == "protect":
        decision = {
            "max_workers": 0,
            "max_autonomy": 0,
            "allowed_actions": ["doctor", "perf-tune", "mesh-compact"],
            "reason": "critical risk: protect hardware and state before expanding",
        }
    elif mode == "stabilize":
        decision = {
            "max_workers": 1,
            "max_autonomy": 1 if status["queue_pressure"] < 0.8 else 0,
            "allowed_actions": ["worker-run", "router-simulate", "doctor", "perf-tune"],
            "reason": f"risk={risk}, queue_pressure={status['queue_pressure']}: bounded execution only",
        }
    else:
        decision = {
            "max_workers": 2,
            "max_autonomy": 2,
            "allowed_actions": ["supervisor-run", "worker-run", "autonomy-run", "router-loop"],
            "reason": "clean state: expansion allowed with supervisor budget",
        }
    return {
        "generated_at": utc_now(),
        "kernel_mode": mode,
        "decision": decision,
        "status": status,
    }


def kernel_syscall(workspace: Path, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    state = _load_kernel_state(workspace)
    spec = SYSCALLS.get(name)
    allowed = spec is not None
    if not allowed:
        state.setdefault("metrics", {})["denied"] = int(state.setdefault("metrics", {}).get("denied", 0)) + 1
        result = {"ok": False, "error": "unknown_syscall", "name": name}
    elif name == "kernel.status":
        result = {"ok": True, "result": kernel_status(workspace)}
    elif name == "kernel.schedule":
        result = {"ok": True, "result": kernel_schedule(workspace)}
    elif name == "kernel.archive":
        result = {"ok": True, "result": kernel_archive(workspace)}
    else:
        result = {"ok": True, "planned": True, "name": name, "payload": payload, "capability": spec["capability"]}
    state.setdefault("syscalls", []).append({"ts": utc_now(), "name": name, "ok": result.get("ok", False)})
    state["syscalls"] = state["syscalls"][-120:]
    state.setdefault("metrics", {})["syscalls"] = int(state.setdefault("metrics", {}).get("syscalls", 0)) + 1
    _save_kernel_state(workspace, state)
    append_event(workspace, "fractal_kernel_syscall", {"name": name, "ok": result.get("ok", False)})
    return result


def kernel_archive(workspace: Path) -> dict[str, Any]:
    status = kernel_status(workspace)
    root = workspace / "kernel"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"KERNEL_{len(list(root.glob('KERNEL_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Kernel Report",
        "",
        f"- Generated at: {status['generated_at']}",
        f"- Mode: {status['kernel']['mode']}",
        f"- Score: {status['kernel']['score']}",
        f"- Risk: {status['risk_level']}",
        f"- Queue pressure: {status['queue_pressure']}",
        f"- Real kernel: {status['real_kernel']['source_root']}",
        "",
        "## Services",
    ]
    for service in KERNEL_SERVICES:
        lines.append(f"- ring{service['ring']}::{service['id']} :: {service['purpose']}")
    lines.extend(["", "## Syscalls"])
    for name, spec in SYSCALLS.items():
        lines.append(f"- {name} :: capability={spec['capability']} mutates={spec['mutates']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"fractal_kernel::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="fractal_kernel",
    )
    state = _load_kernel_state(workspace)
    state.setdefault("metrics", {})["archives"] = int(state.setdefault("metrics", {}).get("archives", 0)) + 1
    _save_kernel_state(workspace, state)
    append_event(workspace, "fractal_kernel_archived", {"report_path": str(path)})
    return {
        "report_path": str(path),
        "tile_manifest": tile.get("manifest_id", ""),
        "status": status,
    }
