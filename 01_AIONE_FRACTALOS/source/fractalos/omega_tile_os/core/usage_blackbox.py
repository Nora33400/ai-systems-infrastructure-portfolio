from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

from .autonomy_runtime import submit_workload
from .codex_worker import submit_worker_session
from .events import append_event
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


WATCHED_MODULE_GLOBS = [
    "omega_tile_os/*.py",
    "omega_tile_os/core/*.py",
    "omega_tile_os/tilemindfs/*.py",
    "fractal_os/*.py",
]


def _state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "usage_blackbox.json"


def _recovery_state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "module_recovery.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp_path.replace(path)


def _load_state(workspace: Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        state = {
            "metrics": {
                "logged_errors": 0,
                "parse_errors": 0,
                "exceptions": 0,
                "recoveries": 0,
                "rollbacks": 0,
            },
            "recent_errors": [],
            "last_error": None,
        }
        _atomic_write_json(path, state)
        return state
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(_state_path(workspace), state)


def _load_recovery_state(workspace: Path) -> dict[str, Any]:
    path = _recovery_state_path(workspace)
    if not path.exists():
        state = {
            "known_good": {},
            "recoveries": [],
            "metrics": {
                "snapshots": 0,
                "scans": 0,
                "rollbacks": 0,
                "reinforcement_tasks": 0,
            },
            "last_scan": None,
            "last_recovery": None,
        }
        _atomic_write_json(path, state)
        return state
    return json.loads(path.read_text(encoding="utf-8"))


def _save_recovery_state(workspace: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(_recovery_state_path(workspace), state)


def _workspace_from_argv(argv: list[str] | None = None) -> Path:
    argv = list(argv or sys.argv[1:])
    for index, item in enumerate(argv):
        if item == "--workspace" and index + 1 < len(argv):
            return Path(argv[index + 1]).resolve()
        if item.startswith("--workspace="):
            return Path(item.split("=", 1)[1]).resolve()
    cwd = Path.cwd()
    if (cwd / "workspace").exists():
        return (cwd / "workspace").resolve()
    return cwd.resolve()


def project_root_from_workspace(workspace: Path) -> Path:
    return workspace.parent if workspace.name == "workspace" else workspace


def _error_root(workspace: Path) -> Path:
    root = workspace / "usage_errors"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    return root


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def log_usage_error(
    workspace: Path | None,
    category: str,
    message: str,
    *,
    command: str | None = None,
    exc_info: tuple[type[BaseException], BaseException, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = (workspace or _workspace_from_argv()).resolve()
    ensure_workspace(workspace)
    trace = ""
    if exc_info:
        trace = "".join(traceback.format_exception(*exc_info))[-8000:]
    entry = {
        "id": _hash_text(f"{utc_now()}::{category}::{message}::{command or ''}"),
        "ts": utc_now(),
        "category": category,
        "message": message,
        "command": command or " ".join(sys.argv),
        "traceback_tail": trace,
        "context": context or {},
    }
    root = _error_root(workspace)
    with (root / "USAGE_ERRORS.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    state = _load_state(workspace)
    metrics = state.setdefault("metrics", {})
    metrics["logged_errors"] = int(metrics.get("logged_errors", 0)) + 1
    if category == "argparse":
        metrics["parse_errors"] = int(metrics.get("parse_errors", 0)) + 1
    if "exception" in category:
        metrics["exceptions"] = int(metrics.get("exceptions", 0)) + 1
    state["last_error"] = entry
    state["recent_errors"] = (state.get("recent_errors", []) + [entry])[-80:]
    _save_state(workspace, state)
    append_event(workspace, "usage_error_logged", {"id": entry["id"], "category": category})
    return entry


class UsageArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log_usage_error(_workspace_from_argv(), "argparse", message, command=" ".join(sys.argv))
        super().error(message)


def install_usage_error_hook() -> None:
    if getattr(sys, "_fractalos_usage_hook", False):
        return
    previous = sys.excepthook

    def _hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        if not issubclass(exc_type, KeyboardInterrupt):
            try:
                log_usage_error(
                    _workspace_from_argv(),
                    "unhandled_exception",
                    f"{exc_type.__name__}: {exc}",
                    command=" ".join(sys.argv),
                    exc_info=(exc_type, exc, tb),
                )
            except Exception:
                pass
        previous(exc_type, exc, tb)

    sys.excepthook = _hook
    setattr(sys, "_fractalos_usage_hook", True)


def _watched_module_paths(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in WATCHED_MODULE_GLOBS:
        paths.extend(project_root.glob(pattern))
    return sorted({path.resolve() for path in paths if path.is_file() and path.suffix == ".py"})


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_known_good_modules(workspace: Path, *, project_root: Path | None = None, label: str = "doctor-ok") -> dict[str, Any]:
    ensure_workspace(workspace)
    project_root = (project_root or project_root_from_workspace(workspace)).resolve()
    recovery = _load_recovery_state(workspace)
    snapshot_root = workspace / "recovery" / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    captured = []
    for path in _watched_module_paths(project_root):
        rel = path.relative_to(project_root).as_posix()
        digest = _digest_file(path)
        target = snapshot_root / rel.replace("/", "__") / f"{digest[:16]}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)
        recovery.setdefault("known_good", {})[rel] = {
            "path": str(target),
            "digest": digest,
            "captured_at": utc_now(),
            "label": label,
        }
        captured.append(rel)
    metrics = recovery.setdefault("metrics", {})
    metrics["snapshots"] = int(metrics.get("snapshots", 0)) + len(captured)
    recovery["last_snapshot"] = {
        "ts": utc_now(),
        "label": label,
        "count": len(captured),
    }
    _save_recovery_state(workspace, recovery)
    append_event(workspace, "module_recovery_snapshot", {"count": len(captured), "label": label})
    return {"captured_count": len(captured), "label": label, "project_root": str(project_root)}


def scan_module_availability(workspace: Path, *, project_root: Path | None = None) -> dict[str, Any]:
    ensure_workspace(workspace)
    project_root = (project_root or project_root_from_workspace(workspace)).resolve()
    failures = []
    scanned = []
    for path in _watched_module_paths(project_root):
        rel = path.relative_to(project_root).as_posix()
        scanned.append(rel)
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append({"module": rel, "error": str(exc)[-2000:]})
    recovery = _load_recovery_state(workspace)
    metrics = recovery.setdefault("metrics", {})
    metrics["scans"] = int(metrics.get("scans", 0)) + 1
    recovery["last_scan"] = {
        "ts": utc_now(),
        "scanned": len(scanned),
        "failures": failures,
    }
    _save_recovery_state(workspace, recovery)
    return {
        "generated_at": utc_now(),
        "project_root": str(project_root),
        "scanned_count": len(scanned),
        "failed_count": len(failures),
        "failures": failures,
    }


def _rollback_module(workspace: Path, project_root: Path, rel_module: str, recovery: dict[str, Any]) -> dict[str, Any]:
    known = dict(recovery.get("known_good", {}).get(rel_module) or {})
    snapshot = Path(str(known.get("path", "")))
    target = project_root / rel_module
    if not snapshot.exists():
        return {"module": rel_module, "rolled_back": False, "reason": "no_known_good_snapshot"}
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, target)
    return {
        "module": rel_module,
        "rolled_back": True,
        "snapshot": str(snapshot),
        "target": str(target),
        "digest": known.get("digest"),
    }


def _write_recovery_report(workspace: Path, recovery: dict[str, Any]) -> Path:
    root = workspace / "recovery" / "reports"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"RESTART_RECOVERY_{len(list(root.glob('RESTART_RECOVERY_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Restart Recovery",
        "",
        f"- Generated at: {recovery['generated_at']}",
        f"- Reason: {recovery['reason']}",
        f"- Before failed modules: {recovery['before']['failed_count']}",
        f"- Rollbacks: {len([item for item in recovery['rollbacks'] if item.get('rolled_back')])}",
        f"- After failed modules: {recovery['after']['failed_count']}",
        f"- Doctor status: {recovery.get('doctor', {}).get('status', 'skipped')}",
        "",
        "## Rollbacks",
    ]
    if recovery["rollbacks"]:
        for item in recovery["rollbacks"]:
            lines.append(f"- {item.get('module')} :: rolled_back={item.get('rolled_back')} reason={item.get('reason', 'ok')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Reinforcement"])
    for item in recovery.get("reinforcement", []):
        lines.append(f"- {item.get('kind')} :: {item.get('id')} :: {item.get('title')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"restart_recovery::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="usage_blackbox",
    )
    return path


def run_restart_recovery(
    workspace: Path,
    *,
    project_root: Path | None = None,
    reason: str = "manual",
    apply: bool = True,
    run_doctor_check: bool = True,
) -> dict[str, Any]:
    ensure_workspace(workspace)
    project_root = (project_root or project_root_from_workspace(workspace)).resolve()
    before = scan_module_availability(workspace, project_root=project_root)
    recovery_state = _load_recovery_state(workspace)
    rollbacks = []
    if apply:
        for failure in before["failures"]:
            rollbacks.append(_rollback_module(workspace, project_root, str(failure["module"]), recovery_state))
    after = scan_module_availability(workspace, project_root=project_root)
    doctor_summary: dict[str, Any] = {"status": "skipped"}
    if run_doctor_check:
        from .doctor import run_doctor

        doctor = run_doctor(workspace)
        doctor_summary = {
            "status": doctor.get("status"),
            "counts": doctor.get("counts", {}),
            "warnings": [item["name"] for item in doctor.get("checks", []) if item.get("status") == "warn"],
            "failures": [item["name"] for item in doctor.get("checks", []) if item.get("status") == "fail"],
        }
        if int(doctor.get("counts", {}).get("fail", 0)) == 0 and int(after.get("failed_count", 0)) == 0:
            snapshot_known_good_modules(workspace, project_root=project_root, label=f"restart-recovery:{reason}")
    reinforcement = []
    if after["failed_count"] or doctor_summary.get("status") == "fail" or any(not item.get("rolled_back") for item in rollbacks):
        title = f"Reinforce restart patch after {reason}"
        goal = (
            "Inspect unavailable modules after restart, strengthen the patch, add tests, "
            "and preserve rollback to the last working version."
        )
        worker = submit_worker_session(
            workspace,
            "builder",
            title,
            goal,
            scope=f"Failures after recovery: {after['failures']}. Rollbacks: {rollbacks}",
        )
        workload = submit_workload(
            workspace,
            "code",
            title,
            goal,
            context=f"Generated by UsageBlackBox restart recovery. Doctor={doctor_summary}",
        )
        reinforcement = [
            {"kind": "worker", "id": worker["id"], "title": worker["title"]},
            {"kind": "autonomy", "id": workload["id"], "title": workload["title"]},
        ]
    recovery = {
        "generated_at": utc_now(),
        "reason": reason,
        "project_root": str(project_root),
        "applied": apply,
        "before": before,
        "rollbacks": rollbacks,
        "after": after,
        "doctor": doctor_summary,
        "reinforcement": reinforcement,
    }
    report_path = _write_recovery_report(workspace, recovery)
    recovery["report_path"] = str(report_path)
    state = _load_state(workspace)
    metrics = state.setdefault("metrics", {})
    metrics["recoveries"] = int(metrics.get("recoveries", 0)) + 1
    metrics["rollbacks"] = int(metrics.get("rollbacks", 0)) + len([item for item in rollbacks if item.get("rolled_back")])
    _save_state(workspace, state)
    recovery_state = _load_recovery_state(workspace)
    recovery_state.setdefault("recoveries", []).append(recovery)
    recovery_state["recoveries"] = recovery_state["recoveries"][-40:]
    recovery_state["last_recovery"] = recovery
    recovery_state.setdefault("metrics", {})["rollbacks"] = int(recovery_state.setdefault("metrics", {}).get("rollbacks", 0)) + len(
        [item for item in rollbacks if item.get("rolled_back")]
    )
    recovery_state.setdefault("metrics", {})["reinforcement_tasks"] = int(recovery_state.setdefault("metrics", {}).get("reinforcement_tasks", 0)) + len(reinforcement)
    _save_recovery_state(workspace, recovery_state)
    append_event(
        workspace,
        "restart_recovery_completed",
        {"reason": reason, "failed_after": after["failed_count"], "rollbacks": len(rollbacks), "report_path": str(report_path)},
    )
    return recovery


def usage_error_report(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    state = _load_state(workspace)
    recovery = _load_recovery_state(workspace)
    errors = list(state.get("recent_errors", []))
    categories = Counter(str(item.get("category", "unknown")) for item in errors)
    reports = sorted((workspace / "recovery" / "reports").glob("RESTART_RECOVERY_*.md"))
    return {
        "generated_at": utc_now(),
        "metrics": state.get("metrics", {}),
        "recent_error_count": len(errors),
        "category_counts": dict(categories),
        "last_error": state.get("last_error"),
        "recovery_metrics": recovery.get("metrics", {}),
        "last_recovery": recovery.get("last_recovery"),
        "latest_recovery_report": str(reports[-1]) if reports else None,
    }
