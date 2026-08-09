from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .action_router import route_report, simulate_route_loop
from .ai_dev_tool import ai_dev_report
from .autonomy_runtime import autonomy_report
from .codex_worker import worker_report
from .corpus_deep_index import corpus_deep_index_report
from .events import read_events
from .formula_programs import formula_program_report, formula_runtime_advice
from .gpu_runtime import detect_gpu_runtime
from .mesh_federation import mesh_cache_report, mesh_compact, mesh_daemon_snapshot, mesh_status
from .meta_supervisor import supervisor_report
from .native_desktop_stack import NATIVE_PACKAGE_CATALOG
from .native_userspace import vfs_mount_report
from .ollama_bridge import ollama_idea_report
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .research_fusion import research_fusion_report
from .scientific_formula_forge import scientific_formula_report
from .state import ensure_workspace, load_config, load_state, utc_now
from .storage_vfs import storage_mount_report, storage_verify
from .triple_kernel_runtime import triple_kernel_status
from .ui_runtime import available_views, build_ui_model
from .usage_blackbox import scan_module_availability, usage_error_report
from ..tilemindfs.store import TileMindFS


Status = str

SAFETY_WEIGHT = {
    "safe": 1.0,
    "read-only": 0.72,
    "manual": 0.18,
}

REPAIR_ACTION_IDS = {
    "perf-tune": "perf-tune",
    "mesh-compact": "mesh-compact",
    "gpu-diagnostic": "gpu-runtime",
    "ensure-workspace": "init",
    "formula-program-review": "formula-discover",
}


def _check(name: str, status: Status, summary: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "details": details or {},
    }


def _guarded(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive diagnostic boundary
        return _check(name, "fail", f"{type(exc).__name__}: {exc}", {"exception": repr(exc)})


def _state_files_check(workspace: Path) -> dict[str, Any]:
    required = [
        "system_state.json",
        "omega_config.json",
        "omega_ram.json",
        "performance_governor.json",
        "mission_journal.json",
        "autonomy_runtime.json",
        "worker_runtime.json",
        "ui_runtime.json",
        "action_router.json",
        "research_fusion.json",
        "formula_programs.json",
        "corpus_deep_index.json",
        "desktop_runtime.json",
        "fractal_kernel.json",
        "triple_kernel_runtime.json",
        "scientific_formula_forge.json",
        "storage_vfs.json",
        "auto_upgrade.json",
        "usage_blackbox.json",
        "module_recovery.json",
    ]
    missing: list[str] = []
    invalid: list[str] = []
    for name in required:
        path = workspace / "state" / name
        if not path.exists():
            missing.append(name)
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            invalid.append(name)
    if invalid:
        return _check("state-files", "fail", f"{len(invalid)} invalid JSON state file(s).", {"missing": missing, "invalid": invalid})
    if missing:
        return _check("state-files", "warn", f"{len(missing)} state file(s) missing.", {"missing": missing, "invalid": invalid})
    return _check("state-files", "ok", "All required state files are present and valid JSON.")


def _workspace_check(workspace: Path) -> dict[str, Any]:
    required_dirs = ["state", "events", "memory", "tiles", "ram", "formula_programs"]
    missing = [name for name in required_dirs if not (workspace / name).exists()]
    if missing:
        return _check("workspace", "warn", f"{len(missing)} workspace folder(s) missing.", {"missing": missing})
    return _check("workspace", "ok", "Workspace folders are present.", {"path": str(workspace)})


def _perf_check(workspace: Path) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    risk = str(perf["recommendations"].get("risk_level", "unknown"))
    stability = float(perf["formulas"].get("stability_index", 0.0))
    status = "ok"
    if risk == "critical" or stability < 0.25:
        status = "warn"
    elif risk not in {"low", "nominal", "elevated"}:
        status = "warn"
    return _check(
        "performance",
        status,
        f"risk={risk}, stability={stability:.3f}",
        {
            "risk_level": risk,
            "stability_index": stability,
            "recommended_concurrency": perf["recommendations"].get("recommended_concurrency"),
        },
    )


def _formula_programs_check(workspace: Path) -> dict[str, Any]:
    report = formula_program_report(workspace)
    missing: list[str] = []
    for item in report.get("recent_programs", []):
        for key in ("program_path", "readme_path"):
            path = Path(str(item.get(key, "")))
            if not path.exists():
                missing.append(str(path))
    status = "ok"
    if int(report.get("program_count", 0)) == 0:
        status = "warn"
    if missing:
        status = "fail"
    return _check(
        "formula-programs",
        status,
        f"programs={report.get('program_count', 0)}, evolutions={report.get('metrics', {}).get('evolutions', 0)}",
        {"missing_files": missing, "metrics": report.get("metrics", {})},
    )


def _corpus_index_check(workspace: Path) -> dict[str, Any]:
    report = corpus_deep_index_report(workspace)
    last_index = report.get("last_index") or {}
    indexed = int(last_index.get("indexed_formula_files", 0) or 0)
    total = int(last_index.get("total_formula_files", 0) or 0)
    coverage = float(last_index.get("coverage_ratio", 0.0) or 0.0)
    status = "ok" if indexed and coverage >= 0.99 else "warn"
    return _check(
        "corpus-deep-index",
        status,
        f"indexed={indexed}/{total}, coverage={coverage:.3f}",
        {
            "metrics": report.get("metrics", {}),
            "last_index": last_index,
        },
    )


def _formula_advice_check(workspace: Path) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    advice = formula_runtime_advice(
        workspace,
        perf_report=perf,
        router_signals={
            "queued_autonomy": int(autonomy["status_counts"].get("queued", 0)),
            "queued_workers": int(worker["status_counts"].get("queued", 0)),
        },
    )
    status = "ok" if int(advice.get("program_count", 0)) else "warn"
    if perf["recommendations"].get("risk_level") in {"elevated", "critical"} and int(advice.get("protective_program_count", 0)) == 0:
        status = "warn"
    return _check(
        "formula-advice",
        status,
        f"safe={advice.get('safe_program_count', 0)}, protective={advice.get('protective_program_count', 0)}",
        {
            "action_biases": advice.get("action_biases", {}),
            "signals": advice.get("signals", {}),
        },
    )


def _router_check(workspace: Path) -> dict[str, Any]:
    report = route_report(workspace)
    action = report.get("next_action", {})
    risk = str(report.get("risk_level", "unknown"))
    status = "ok"
    if risk == "critical" and action.get("id") not in {"perf-tune", "mesh-compact"}:
        status = "fail"
    elif risk == "elevated" and action.get("safety") not in {"safe", "bounded", "network-bounded"}:
        status = "warn"
    return _check(
        "router",
        status,
        f"next={action.get('id', 'none')}, risk={risk}",
        {
            "next_action": action,
            "signals": report.get("signals", {}),
            "formula_biases": report.get("formula_advice", {}).get("action_biases", {}),
        },
    )


def _router_simulation_check(workspace: Path) -> dict[str, Any]:
    simulation = simulate_route_loop(workspace, max_cycles=3, stop_on_elevated=True)
    status = "ok"
    if simulation.get("mutated_workspace"):
        status = "fail"
    return _check(
        "router-simulation",
        status,
        f"stop={simulation.get('stop_reason')}, would_execute={simulation.get('would_execute_count')}",
        {
            "stop_reason": simulation.get("stop_reason"),
            "projected_signals": simulation.get("projected_signals", {}),
        },
    )


def _autonomy_check(workspace: Path) -> dict[str, Any]:
    report = autonomy_report(workspace)
    queued = int(report["status_counts"].get("queued", 0))
    status = "ok" if queued <= 12 else "warn"
    return _check(
        "autonomy",
        status,
        f"queued={queued}, processed={report['metrics'].get('processed', 0)}",
        {"status_counts": report.get("status_counts", {}), "domain_counts": report.get("domain_counts", {})},
    )


def _worker_check(workspace: Path) -> dict[str, Any]:
    report = worker_report(workspace)
    queued = int(report["status_counts"].get("queued", 0))
    status = "ok" if queued <= 8 else "warn"
    return _check(
        "worker",
        status,
        f"queued={queued}, processed={report['metrics'].get('processed', 0)}",
        {"status_counts": report.get("status_counts", {}), "mode_counts": report.get("mode_counts", {})},
    )


def _storage_check(workspace: Path) -> dict[str, Any]:
    tile = TileMindFS(workspace).report()
    ram = OmegaRAM(workspace).report()
    status = "ok"
    if int(ram.get("metrics", {}).get("hot_entries", 0)) + int(ram.get("metrics", {}).get("warm_entries", 0)) < 0:
        status = "fail"
    return _check(
        "storage",
        status,
        f"tile_manifests={tile.get('manifest_count', 0)}, ram_writes={ram.get('metrics', {}).get('writes', 0)}",
        {"tilemindfs": tile, "ram_metrics": ram.get("metrics", {})},
    )


def _mesh_check(workspace: Path) -> dict[str, Any]:
    mesh = mesh_status(workspace)
    daemon = mesh_daemon_snapshot(workspace)
    cache = mesh_cache_report(workspace)
    status = "ok"
    pending = len([item for item in mesh.get("outbox", []) if item.get("status") != "delivered"])
    if pending:
        status = "warn"
    return _check(
        "mesh",
        status,
        f"nodes={mesh.get('node_count', 0)}, pending_outbox={pending}",
        {"daemon_status": daemon.get("status"), "cache_entries": cache.get("entry_count", 0)},
    )


def _ui_check(workspace: Path) -> dict[str, Any]:
    views = available_views()
    required = {"mission-control", "worker-studio", "autonomy-lab", "research-desk", "fractal-desktop", "scientific-formula-lab", "system-observatory"}
    ids = {item["id"] for item in views}
    missing = sorted(required - ids)
    detail_cards = 0
    active_view = "unavailable"
    status = "ok" if not missing else "fail"
    try:
        model = build_ui_model(workspace, active_view="research-desk")
        detail_cards = len(model.get("detail_cards", []))
        active_view = str(model.get("active_view", "unknown"))
        if active_view != "research-desk":
            status = "fail"
    except KeyError as exc:
        status = "warn" if not missing else "fail"
        active_view = f"partial-telemetry:{exc}"
    return _check(
        "ui",
        status,
        f"views={len(views)}, active={active_view}",
        {"missing_views": missing, "detail_cards": detail_cards},
    )


def _research_check(workspace: Path) -> dict[str, Any]:
    report = research_fusion_report(workspace)
    runs = int(report.get("metrics", {}).get("runs", 0))
    status = "ok" if runs else "warn"
    return _check(
        "research-fusion",
        status,
        f"runs={runs}, pdfs={report.get('metrics', {}).get('pdfs_ingested', 0)}",
        {"last_run": report.get("last_run")},
    )


def _ai_dev_check(workspace: Path) -> dict[str, Any]:
    report = ai_dev_report(workspace)
    status = "ok"
    if int(report.get("catalog_total", 0)) < 100:
        status = "fail"
    elif not report.get("local_only") or not report.get("safe_default"):
        status = "warn"
    return _check(
        "ai-dev-tool",
        status,
        f"catalog={report.get('catalog_total', 0)}, reports={report.get('report_count', 0)}",
        {
            "category_count": report.get("category_count", 0),
            "latest_report": report.get("latest_report"),
            "local_only": report.get("local_only"),
            "safe_default": report.get("safe_default"),
        },
    )


def _ollama_check(workspace: Path) -> dict[str, Any]:
    report = ollama_idea_report(workspace)
    status = report.get("status", {})
    availability = "available" if status.get("available") else "fallback"
    return _check(
        "ollama-bridge",
        "ok",
        f"{availability}, reports={report.get('report_count', 0)}",
        {
            "available": status.get("available"),
            "endpoint": status.get("endpoint"),
            "models": status.get("models", []),
            "latest_report": report.get("latest_report"),
        },
    )


def _supervisor_check(workspace: Path) -> dict[str, Any]:
    report = supervisor_report(workspace)
    status = "ok"
    if report.get("risk_level") == "critical" and int(report.get("selected_count", 0)) > 0:
        status = "fail"
    return _check(
        "meta-supervisor",
        status,
        f"mode={report.get('current_mode')}, clean_growth={report.get('clean_growth_index')}",
        report,
    )


def _scientific_formula_check(workspace: Path) -> dict[str, Any]:
    report = scientific_formula_report(workspace)
    status = "ok"
    if int(report.get("catalog_total", 0)) < 100:
        status = "fail"
    elif not report.get("safe_default") or not report.get("local_only"):
        status = "warn"
    return _check(
        "scientific-formulas",
        status,
        f"catalog={report.get('catalog_total', 0)}, plans={report.get('metrics', {}).get('plans', 0)}",
        {
            "target_count": report.get("target_count", 0),
            "variant_count": report.get("variant_count", 0),
            "last_plan": report.get("last_plan"),
        },
    )


def _auto_upgrade_check(workspace: Path) -> dict[str, Any]:
    from .auto_upgrade import auto_upgrade_report

    report = auto_upgrade_report(workspace)
    metrics = report.get("metrics", {})
    status = "ok" if int(metrics.get("runs", 0)) else "warn"
    if int(report.get("program_status_counts", {}).get("invalid", 0)):
        status = "fail"
    return _check(
        "auto-upgrade",
        status,
        f"runs={metrics.get('runs', 0)}, cycles={metrics.get('cycles', 0)}, promoted={metrics.get('promoted_programs', 0)}",
        {
            "last_session": report.get("last_session"),
            "program_status_counts": report.get("program_status_counts", {}),
            "latest_report": report.get("latest_report"),
        },
    )


def _usage_blackbox_check(workspace: Path) -> dict[str, Any]:
    report = usage_error_report(workspace)
    metrics = report.get("metrics", {})
    status = "ok"
    if int(metrics.get("exceptions", 0)) > 0:
        status = "warn"
    if int(report.get("recovery_metrics", {}).get("rollbacks", 0)) > 0:
        status = "warn"
    return _check(
        "usage-blackbox",
        status,
        f"errors={metrics.get('logged_errors', 0)}, recoveries={metrics.get('recoveries', 0)}, rollbacks={metrics.get('rollbacks', 0)}",
        {
            "category_counts": report.get("category_counts", {}),
            "latest_recovery_report": report.get("latest_recovery_report"),
        },
    )


def _module_recovery_check(workspace: Path) -> dict[str, Any]:
    scan = scan_module_availability(workspace)
    status = "ok" if int(scan.get("failed_count", 0)) == 0 else "fail"
    return _check(
        "module-recovery",
        status,
        f"scanned={scan.get('scanned_count', 0)}, failed={scan.get('failed_count', 0)}",
        {
            "failures": scan.get("failures", []),
        },
    )


def _bare_metal_kernel_check(workspace: Path) -> dict[str, Any]:
    root = workspace.parent / "bare_metal" if workspace.name == "workspace" else workspace / "bare_metal"
    required = [
        "README.md",
        "TOOLCHAIN.md",
        "kernel/fractal_kernel.c",
        "kernel/boot.S",
        "kernel/include/fractal_kernel.h",
        "kernel/arch/x86_64/serial.c",
        "kernel/arch/x86_64/gdt.c",
        "kernel/arch/x86_64/idt.c",
        "kernel/arch/x86_64/pic.c",
        "kernel/arch/x86_64/keyboard.c",
        "kernel/arch/x86_64/timer.c",
        "kernel/core/syscall.c",
        "kernel/core/console.c",
        "kernel/core/task.c",
        "kernel/core/userspace.c",
        "kernel/core/regime.c",
        "kernel/core/semantic_memory.c",
        "kernel/core/universe.c",
        "kernel/core/illusion.c",
        "kernel/core/foundry.c",
        "kernel/core/proofstate.c",
        "kernel/core/desktop_plane.c",
        "kernel/core/scientific_formula.c",
        "kernel/core/vfs.c",
        "kernel/core/package.c",
        "kernel/core/storage_plane.c",
        "kernel/core/pmm.c",
        "kernel/core/heap.c",
        "kernel/core/slab.c",
        "kernel/core/vmm.c",
        "kernel/core/scheduler.c",
        "kernel/core/triple_kernel.c",
        "kernel/linker.ld",
        "limine/limine.conf",
        "Makefile",
        "build.ps1",
    ]
    missing = [rel for rel in required if not (root / rel).exists()]
    status = "ok" if not missing else "warn"
    return _check(
        "bare-metal-kernel",
        status,
        f"stage=stage22, files={len(required) - len(missing)}/{len(required)}",
        {
            "root": str(root),
            "missing": missing,
            "stage": "stage22-storage-vfs-journal-alpha",
        },
    )


def _native_userspace_check(workspace: Path) -> dict[str, Any]:
    vfs = vfs_mount_report(workspace)
    mounts = len(vfs.get("mounts", []))
    nodes = int(vfs.get("node_count", 0) or 0)
    packages = len(NATIVE_PACKAGE_CATALOG)
    status = "ok" if mounts >= 3 and nodes >= 10 and packages >= 12 else "warn"
    return _check(
        "native-userspace",
        status,
        f"mounts={mounts}, nodes={nodes}, packages={packages}",
        {
            "mounts": vfs.get("mounts", []),
            "node_count": nodes,
            "package_count": packages,
            "package_policy": "plan-only until native signatures, dependency solver and rollback slots are enforced",
        },
    )


def _storage_vfs_check(workspace: Path) -> dict[str, Any]:
    mount = storage_mount_report(workspace)
    verify = storage_verify(workspace)
    status = "ok" if verify.get("ok") and int(mount.get("file_count", 0) or 0) >= 1 else "warn"
    return _check(
        "storage-vfs",
        status,
        f"files={mount.get('file_count', 0)}, journal={mount.get('journal_count', 0)}, snapshots={mount.get('snapshot_count', 0)}",
        {
            "stage": mount.get("stage"),
            "mount": mount.get("mount"),
            "verify": verify,
            "truth": mount.get("truth", {}),
        },
    )


def _triple_kernel_runtime_check(workspace: Path) -> dict[str, Any]:
    status = triple_kernel_status(workspace)
    syntheses = int(status.get("metrics", {}).get("syntheses", 0))
    build_count = int(status.get("build_count", 0))
    level = "ok" if syntheses or build_count else "warn"
    return _check(
        "triple-kernel-runtime",
        level,
        f"catalog={status.get('catalog_total', 0)}, syntheses={syntheses}, builds={build_count}",
        {
            "catalog_total": status.get("catalog_total", 0),
            "last_build": status.get("runtime", {}).get("last_build"),
        },
    )


def _gpu_check(workspace: Path) -> dict[str, Any]:
    try:
        gpu = detect_gpu_runtime(workspace)
    except KeyError as exc:
        return _check("gpu", "warn", f"GPU telemetry incomplete: {exc}", {"gpus": [], "native_runtime_available": False})
    gpus = gpu.get("gpus", [])
    status = "ok" if gpus else "warn"
    return _check(
        "gpu",
        status,
        f"detected={len(gpus)}, native={gpu.get('native_runtime_available', False)}",
        {"gpus": gpus, "native_runtime_available": gpu.get("native_runtime_available", False)},
    )


def run_doctor(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    checks = [
        _guarded("workspace", lambda: _workspace_check(workspace)),
        _guarded("state-files", lambda: _state_files_check(workspace)),
        _guarded("config", lambda: _check("config", "ok", "Config loads with defaults merged.", {"keys": sorted(load_config(workspace).keys())})),
        _guarded("state", lambda: _check("state", "ok", "System state loads.", {"node": load_state(workspace).get("node", {})})),
        _guarded("performance", lambda: _perf_check(workspace)),
        _guarded("formula-programs", lambda: _formula_programs_check(workspace)),
        _guarded("corpus-deep-index", lambda: _corpus_index_check(workspace)),
        _guarded("formula-advice", lambda: _formula_advice_check(workspace)),
        _guarded("router", lambda: _router_check(workspace)),
        _guarded("router-simulation", lambda: _router_simulation_check(workspace)),
        _guarded("autonomy", lambda: _autonomy_check(workspace)),
        _guarded("worker", lambda: _worker_check(workspace)),
        _guarded("storage", lambda: _storage_check(workspace)),
        _guarded("mesh", lambda: _mesh_check(workspace)),
        _guarded("ui", lambda: _ui_check(workspace)),
        _guarded("research-fusion", lambda: _research_check(workspace)),
        _guarded("ai-dev-tool", lambda: _ai_dev_check(workspace)),
        _guarded("ollama-bridge", lambda: _ollama_check(workspace)),
        _guarded("meta-supervisor", lambda: _supervisor_check(workspace)),
        _guarded("scientific-formulas", lambda: _scientific_formula_check(workspace)),
        _guarded("auto-upgrade", lambda: _auto_upgrade_check(workspace)),
        _guarded("usage-blackbox", lambda: _usage_blackbox_check(workspace)),
        _guarded("module-recovery", lambda: _module_recovery_check(workspace)),
        _guarded("triple-kernel-runtime", lambda: _triple_kernel_runtime_check(workspace)),
        _guarded("bare-metal-kernel", lambda: _bare_metal_kernel_check(workspace)),
        _guarded("native-userspace", lambda: _native_userspace_check(workspace)),
        _guarded("storage-vfs", lambda: _storage_vfs_check(workspace)),
        _guarded("gpu", lambda: _gpu_check(workspace)),
        _guarded("events", lambda: _check("events", "ok", f"recent_events={len(read_events(workspace, limit=12))}")),
    ]
    counts = {
        "ok": len([item for item in checks if item["status"] == "ok"]),
        "warn": len([item for item in checks if item["status"] == "warn"]),
        "fail": len([item for item in checks if item["status"] == "fail"]),
    }
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "ok"
    next_actions: list[str] = []
    if status == "fail":
        next_actions.append("Inspect failed checks before running mutating commands.")
    if any(item["name"] == "performance" and item["status"] == "warn" for item in checks):
        next_actions.append("Run: python -m omega_tile_os perf-tune --workspace .\\workspace")
    if any(item["name"] == "mesh" and item["status"] == "warn" for item in checks):
        next_actions.append("Run: python -m omega_tile_os mesh-compact --workspace .\\workspace")
    if any(item["name"] == "formula-programs" and item["status"] == "warn" for item in checks):
        next_actions.append("Run formula-discover with a corpus path before formula-evolve.")
    if any(item["name"] == "triple-kernel-runtime" and item["status"] == "warn" for item in checks):
        next_actions.append("Run: python -m omega_tile_os triple-kernel-synthesize --workspace .\\workspace")
    return {
        "generated_at": utc_now(),
        "workspace": str(workspace),
        "status": status,
        "counts": counts,
        "checks": checks,
        "next_actions": next_actions,
    }


def _repair(
    repair_id: str,
    reason: str,
    safety: str,
    command: str,
    apply_fn: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": repair_id,
        "reason": reason,
        "safety": safety,
        "command": command,
        "apply_fn": apply_fn,
    }


def _planned_repairs(workspace: Path, doctor: dict[str, Any]) -> list[dict[str, Any]]:
    checks = {item["name"]: item for item in doctor.get("checks", [])}
    repairs: list[dict[str, Any]] = []

    workspace_check = checks.get("workspace", {})
    if workspace_check.get("status") == "warn":
        repairs.append(
            _repair(
                "ensure-workspace",
                "Recreate missing non-destructive workspace folders and default state files.",
                "safe",
                "python -m omega_tile_os init --workspace .\\workspace",
                lambda: (ensure_workspace(workspace) or {"ensured": True}),
            )
        )

    performance = checks.get("performance", {})
    router = checks.get("router", {})
    formula_advice = checks.get("formula-advice", {})
    if performance.get("status") == "warn" or str(router.get("details", {}).get("next_action", {}).get("id")) == "perf-tune":
        repairs.append(
            _repair(
                "perf-tune",
                "Apply bounded safe-adaptive performance tuning recommended by the governor or FormulaAdvisor.",
                "safe",
                "python -m omega_tile_os perf-tune --workspace .\\workspace",
                lambda: PerformanceGovernor(workspace).apply(),
            )
        )

    mesh = checks.get("mesh", {})
    action_biases = formula_advice.get("details", {}).get("action_biases", {})
    if mesh.get("status") == "warn" or float(action_biases.get("mesh-compact", 0.0) or 0.0) > 0.05:
        repairs.append(
            _repair(
                "mesh-compact",
                "Compact append-safe mesh history and reduce noisy relay state.",
                "safe",
                "python -m omega_tile_os mesh-compact --workspace .\\workspace",
                lambda: mesh_compact(workspace),
            )
        )

    formula_programs = checks.get("formula-programs", {})
    missing_files = formula_programs.get("details", {}).get("missing_files", [])
    if missing_files:
        repairs.append(
            _repair(
                "formula-program-review",
                "Formula program files are missing; manual rediscovery with the corpus path is safer than guessing a path.",
                "manual",
                "python -m omega_tile_os formula-discover --workspace .\\workspace --corpus <corpus-path>",
                None,
            )
        )

    gpu = checks.get("gpu", {})
    if gpu.get("status") == "warn":
        repairs.append(
            _repair(
                "gpu-diagnostic",
                "GPU native runtime was not confirmed; run a read-only device report before attempting GPU work.",
                "read-only",
                "python -m omega_tile_os devices --workspace .\\workspace",
                lambda: {"devices": "Run `devices` for detailed GPU/CPU placement context."},
            )
        )

    return _rank_repairs(repairs, checks)


def _doctor_severity(checks: dict[str, dict[str, Any]]) -> float:
    fail_count = len([item for item in checks.values() if item.get("status") == "fail"])
    warn_count = len([item for item in checks.values() if item.get("status") == "warn"])
    return min(1.0, 0.22 + 0.34 * warn_count + 0.55 * fail_count)


def _rank_repairs(repairs: list[dict[str, Any]], checks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    severity = _doctor_severity(checks)
    formula_biases = checks.get("formula-advice", {}).get("details", {}).get("action_biases", {})
    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(repairs):
        repair = dict(item)
        action_id = REPAIR_ACTION_IDS.get(str(repair["id"]), str(repair["id"]))
        formula_bias = float(formula_biases.get(action_id, 0.0) or 0.0)
        safety = SAFETY_WEIGHT.get(str(repair.get("safety", "manual")), 0.18)
        reversibility = 1.0 if repair.get("safety") in {"safe", "read-only"} else 0.35
        direct_need = 1.0
        if repair["id"] == "gpu-diagnostic":
            direct_need = 0.42
        if repair["id"] == "formula-program-review":
            direct_need = 0.65
        heal_score = min(1.0, 0.48 * severity + 0.26 * safety + 0.18 * min(1.0, formula_bias * 8.0) + 0.08 * reversibility)
        repair["heal_score"] = round(heal_score * direct_need, 4)
        repair["formula_bias"] = round(formula_bias, 4)
        repair["rank_formula"] = "HealScore=(0.48*severity + 0.26*safety + 0.18*formula_bias8 + 0.08*reversibility)*direct_need"
        repair["_rank_index"] = index
        ranked.append(repair)
    ranked.sort(key=lambda item: (float(item["heal_score"]), -int(item["_rank_index"])), reverse=True)
    for item in ranked:
        item.pop("_rank_index", None)
    return ranked


def run_healer(workspace: Path, apply: bool = False) -> dict[str, Any]:
    before = run_doctor(workspace)
    planned = _planned_repairs(workspace, before)
    visible_plan = [{key: value for key, value in item.items() if key != "apply_fn"} for item in planned]
    executed: list[dict[str, Any]] = []

    if apply:
        for item in planned:
            if item["safety"] not in {"safe", "read-only"}:
                executed.append(
                    {
                        "id": item["id"],
                        "status": "skipped",
                        "reason": "Manual repair requires explicit external context.",
                    }
                )
                continue
            apply_fn = item.get("apply_fn")
            if apply_fn is None:
                executed.append({"id": item["id"], "status": "skipped", "reason": "No automatic repair available."})
                continue
            try:
                result = apply_fn()
                executed.append({"id": item["id"], "status": "ok", "result_keys": sorted(result.keys())})
            except Exception as exc:  # pragma: no cover - defensive repair boundary
                executed.append({"id": item["id"], "status": "error", "error": f"{type(exc).__name__}: {exc}"})

    after = run_doctor(workspace) if apply else None
    result = {
        "generated_at": utc_now(),
        "workspace": str(workspace),
        "mode": "apply" if apply else "dry-run",
        "before": {
            "status": before["status"],
            "counts": before["counts"],
        },
        "planned_repairs": visible_plan,
        "executed": executed,
        "after": {
            "status": after["status"],
            "counts": after["counts"],
        }
        if after
        else None,
    }
    report_path = _write_healer_report(workspace, result)
    result["report_path"] = str(report_path)
    return result


def _write_healer_report(workspace: Path, result: dict[str, Any]) -> Path:
    root = workspace / "healer"
    root.mkdir(parents=True, exist_ok=True)
    existing = sorted(root.glob("heal_*.md"))
    path = root / f"heal_{len(existing) + 1:04d}.md"
    lines = [
        "# FractalOS Healer Report",
        "",
        f"- Generated at: {result['generated_at']}",
        f"- Mode: {result['mode']}",
        f"- Before: {result['before']['status']} {result['before']['counts']}",
    ]
    if result.get("after"):
        lines.append(f"- After: {result['after']['status']} {result['after']['counts']}")
    lines.extend(["", "## Planned Repairs"])
    for item in result.get("planned_repairs", []):
        lines.append(f"- {item['id']} score={item.get('heal_score', 'n/a')} safety={item.get('safety')} :: {item.get('reason')}")
    lines.extend(["", "## Executed"])
    if not result.get("executed"):
        lines.append("- none")
    for item in result.get("executed", []):
        lines.append(f"- {item.get('id')} :: {item.get('status')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
