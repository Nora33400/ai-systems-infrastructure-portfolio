from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    try:
        tmp_path.replace(path)
    except PermissionError:
        # Windows can transiently refuse atomic replacement when another process
        # briefly holds a handle on the target file. Fall back to a direct write
        # so the runtime remains usable under short-lived concurrent probes.
        path.write_text(tmp_path.read_text(encoding="utf-8"), encoding="utf-8")
        tmp_path.unlink(missing_ok=True)


def _load_json_resilient(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    index = 0
    last_obj = None
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw):
            break
        try:
            obj, end = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            break
        last_obj = obj
        index = end
    if last_obj is None:
        raise json.JSONDecodeError("No valid JSON object found", raw, 0)
    return last_obj


def _merge_defaults(current: dict, defaults: dict) -> dict:
    merged = json.loads(json.dumps(current))
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = json.loads(json.dumps(value))
            continue
        if isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key] = _merge_defaults(merged[key], value)
    return merged


DEFAULT_CONFIG = {
    "weights": {
        "lambda": 0.45,
        "mu": 0.20,
        "rho": 0.25,
        "eta": 0.10,
    },
    "planner": {
        "default_top_k": 3,
        "default_resource_limit": 10.0,
        "baseline_top_k": 3,
        "baseline_resource_limit": 10.0,
    },
    "tilemindfs": {
        "tile_size": 8192,
        "min_chunk": 2048,
        "max_chunk": 16384,
        "boundary_mask": 4095,
    },
    "omega_ram": {
        "hot_budget_bytes": 262144,
        "warm_budget_bytes": 1048576,
        "baseline_hot_budget_bytes": 262144,
        "baseline_warm_budget_bytes": 1048576,
        "compression_threshold": 1024,
        "demotion_decay": 0.85,
        "promotion_heat": 2.4,
        "warm_heat": 1.2,
        "coherence_threshold": 0.66,
    },
    "performance_governor": {
        "mode": "safe-adaptive",
        "sample_interval_ms": 250,
        "cpu_target_utilization": 0.72,
        "cpu_safe_temp_c": 82.0,
        "cpu_idle_reference_c": 35.0,
        "gpu_target_utilization": 0.86,
        "gpu_safe_temp_c": 78.0,
        "gpu_idle_reference_c": 34.0,
        "memory_target_utilization": 0.78,
        "minimum_concurrency": 1,
        "thermal_unknown_penalty": 0.82,
        "hot_budget_cap_bytes": 67108864,
        "warm_budget_cap_bytes": 268435456,
    },
}


DEFAULT_STATE = {
    "node": {
        "name": "omega-tilemind-node",
        "mode": "local",
        "status": "idle",
        "version": "0.1.0",
        "performance_profile": "safe-adaptive",
        "created_at": None,
        "updated_at": None,
    },
    "metrics": {
        "ticks": 0,
        "processed_intents": 0,
        "queued_intents": 0,
    },
    "agents": [
        {"name": "planner", "status": "idle", "last_output": ""},
        {"name": "architect", "status": "idle", "last_output": ""},
        {"name": "builder", "status": "idle", "last_output": ""},
        {"name": "archivist", "status": "idle", "last_output": ""},
    ],
    "intents": [],
    "artifacts": [],
    "memory": {
        "recent_focus": "",
        "last_intent_title": "",
    },
}


def ensure_workspace(workspace: Path) -> None:
    for rel in [
        "state",
        "events",
        "artifacts",
        "memory",
        "intents",
        "tiles",
        "tiles/objects",
        "tiles/manifests",
        "plans",
        "reconstruct",
        "ram",
        "ram/pages",
    ]:
        (workspace / rel).mkdir(parents=True, exist_ok=True)

    state_path = workspace / "state" / "system_state.json"
    config_path = workspace / "state" / "omega_config.json"
    ram_path = workspace / "state" / "omega_ram.json"
    perf_path = workspace / "state" / "performance_governor.json"
    mission_journal_path = workspace / "state" / "mission_journal.json"
    autonomy_path = workspace / "state" / "autonomy_runtime.json"
    worker_path = workspace / "state" / "worker_runtime.json"
    ui_path = workspace / "state" / "ui_runtime.json"
    router_path = workspace / "state" / "action_router.json"
    research_path = workspace / "state" / "research_fusion.json"
    formula_programs_path = workspace / "state" / "formula_programs.json"
    corpus_deep_index_path = workspace / "state" / "corpus_deep_index.json"
    desktop_path = workspace / "state" / "desktop_runtime.json"
    kernel_path = workspace / "state" / "fractal_kernel.json"
    triple_kernel_runtime_path = workspace / "state" / "triple_kernel_runtime.json"
    scientific_formula_path = workspace / "state" / "scientific_formula_forge.json"
    auto_upgrade_path = workspace / "state" / "auto_upgrade.json"
    usage_blackbox_path = workspace / "state" / "usage_blackbox.json"
    module_recovery_path = workspace / "state" / "module_recovery.json"
    notes_path = workspace / "memory" / "notes.md"

    if not config_path.exists():
        _atomic_write_json(config_path, DEFAULT_CONFIG)

    if not state_path.exists():
        state = json.loads(json.dumps(DEFAULT_STATE))
        now = utc_now()
        state["node"]["created_at"] = now
        state["node"]["updated_at"] = now
        _atomic_write_json(state_path, state)

    if not ram_path.exists():
        ram_state = {
            "entries": {},
            "tableau_index": {},
            "metrics": {
                "hot_entries": 0,
                "warm_entries": 0,
                "cold_entries": 0,
                "hot_bytes": 0,
                "warm_bytes": 0,
                "cold_bytes": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "promotions": 0,
                "demotions": 0,
                "writes": 0,
                "reads": 0,
            },
        }
        _atomic_write_json(ram_path, ram_state)

    if not perf_path.exists():
        perf_state = {
            "last_sample": None,
            "last_tuning": None,
            "history": [],
            "campaigns": [],
            "learned_profile": None,
        }
        _atomic_write_json(perf_path, perf_state)

    if not mission_journal_path.exists():
        mission_state = {
            "missions": {},
            "events": [],
        }
        _atomic_write_json(mission_journal_path, mission_state)

    if not autonomy_path.exists():
        autonomy_state = {
            "workloads": [],
            "cycles": [],
            "metrics": {
                "submitted": 0,
                "processed": 0,
                "evolution_cycles": 0,
            },
        }
        _atomic_write_json(autonomy_path, autonomy_state)

    if not worker_path.exists():
        worker_state = {
            "sessions": [],
            "metrics": {
                "submitted": 0,
                "processed": 0,
                "reflections": 0,
            },
        }
        _atomic_write_json(worker_path, worker_state)

    if not ui_path.exists():
        ui_state = {
            "actions": [],
            "metrics": {
                "executed": 0,
                "failed": 0,
            },
            "last_result": None,
        }
        _atomic_write_json(ui_path, ui_state)

    if not router_path.exists():
        router_state = {
            "routes": [],
            "metrics": {
                "reports": 0,
                "executed": 0,
                "failed": 0,
                "skipped_by_cooldown": 0,
                "loops": 0,
            },
            "last_route": None,
            "last_loop": None,
            "cooldowns": {},
        }
        _atomic_write_json(router_path, router_state)

    if not research_path.exists():
        research_state = {
            "runs": [],
            "metrics": {
                "runs": 0,
                "pdfs_ingested": 0,
                "formula_files_sampled": 0,
                "followups_queued": 0,
            },
            "last_run": None,
        }
        _atomic_write_json(research_path, research_state)

    if not formula_programs_path.exists():
        formula_programs_state = {
            "programs": [],
            "metrics": {
                "discoveries": 0,
                "installed": 0,
                "evaluations": 0,
                "evolutions": 0,
                "queued_followups": 0,
            },
            "last_discovery": None,
            "last_evolution": None,
        }
        _atomic_write_json(formula_programs_path, formula_programs_state)

    if not corpus_deep_index_path.exists():
        corpus_deep_index_state = {
            "metrics": {
                "indexes": 0,
            },
            "last_index": None,
        }
        _atomic_write_json(corpus_deep_index_path, corpus_deep_index_state)

    if not desktop_path.exists():
        desktop_state = {
            "sessions": [],
            "opened_apps": [],
            "service_runs": [],
            "overlay_cycles": [],
            "active_overlay": "intent-lens",
            "metrics": {
                "commands": 0,
                "opened_apps": 0,
                "service_runs": 0,
                "overlay_cycles": 0,
            },
        }
        _atomic_write_json(desktop_path, desktop_state)

    if not kernel_path.exists():
        kernel_state = {
            "boot_count": 0,
            "syscalls": [],
            "last_boot": None,
            "metrics": {
                "archives": 0,
                "syscalls": 0,
                "denied": 0,
            },
        }
        _atomic_write_json(kernel_path, kernel_state)

    if not triple_kernel_runtime_path.exists():
        triple_kernel_runtime_state = {
            "builds": [],
            "metrics": {
                "syntheses": 0,
                "queued_followups": 0,
            },
            "last_build": None,
        }
        _atomic_write_json(triple_kernel_runtime_path, triple_kernel_runtime_state)

    if not scientific_formula_path.exists():
        scientific_formula_state = {
            "metrics": {
                "plans": 0,
                "queued": 0,
            },
            "last_plan": None,
        }
        _atomic_write_json(scientific_formula_path, scientific_formula_state)

    if not auto_upgrade_path.exists():
        auto_upgrade_state = {
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
        _atomic_write_json(auto_upgrade_path, auto_upgrade_state)

    if not usage_blackbox_path.exists():
        usage_blackbox_state = {
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
        _atomic_write_json(usage_blackbox_path, usage_blackbox_state)

    if not module_recovery_path.exists():
        module_recovery_state = {
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
        _atomic_write_json(module_recovery_path, module_recovery_state)

    if not notes_path.exists():
        notes_path.write_text("# Omega Mind\n\n- Workspace initialized.\n", encoding="utf-8")


def load_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "system_state.json")


def save_state(workspace: Path, state: dict) -> None:
    ensure_workspace(workspace)
    state["node"]["updated_at"] = utc_now()
    state["metrics"]["queued_intents"] = len([item for item in state["intents"] if item["status"] == "queued"])
    _atomic_write_json(workspace / "state" / "system_state.json", state)


def load_config(workspace: Path) -> dict:
    ensure_workspace(workspace)
    path = workspace / "state" / "omega_config.json"
    current = _load_json_resilient(path)
    merged = _merge_defaults(current, DEFAULT_CONFIG)
    if merged != current:
        _atomic_write_json(path, merged)
    return merged


def save_config(workspace: Path, config: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "omega_config.json", config)


def load_ram_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "omega_ram.json")


def save_ram_state(workspace: Path, ram_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "omega_ram.json", ram_state)


def load_perf_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "performance_governor.json")


def save_perf_state(workspace: Path, perf_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "performance_governor.json", perf_state)


def load_mission_journal(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "mission_journal.json")


def save_mission_journal(workspace: Path, mission_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "mission_journal.json", mission_state)


def load_autonomy_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "autonomy_runtime.json")


def save_autonomy_state(workspace: Path, autonomy_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "autonomy_runtime.json", autonomy_state)


def load_worker_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "worker_runtime.json")


def save_worker_state(workspace: Path, worker_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "worker_runtime.json", worker_state)


def load_ui_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "ui_runtime.json")


def save_ui_state(workspace: Path, ui_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "ui_runtime.json", ui_state)


def load_router_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "action_router.json")


def save_router_state(workspace: Path, router_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "action_router.json", router_state)


def load_research_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "research_fusion.json")


def save_research_state(workspace: Path, research_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "research_fusion.json", research_state)


def load_formula_program_state(workspace: Path) -> dict:
    ensure_workspace(workspace)
    return _load_json_resilient(workspace / "state" / "formula_programs.json")


def save_formula_program_state(workspace: Path, formula_program_state: dict) -> None:
    ensure_workspace(workspace)
    _atomic_write_json(workspace / "state" / "formula_programs.json", formula_program_state)
