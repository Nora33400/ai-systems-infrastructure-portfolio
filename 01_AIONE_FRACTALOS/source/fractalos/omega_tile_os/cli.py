from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.action_router import execute_next_route, execute_route_loop, route_report, simulate_route_loop
from .core.ai_dev_tool import ai_dev_catalog, ai_dev_plan
from .core.auto_upgrade import auto_upgrade_report, run_auto_upgrade_session
from .core.autonomy_runtime import autonomy_report, evolve_ecosystem, run_workloads, submit_workload
from .core.codex_worker import run_worker_sessions, submit_worker_session, worker_report, worker_to_mission
from .core.classic_os_bridge import classic_capability_report, onboarding_pack, write_classic_os_report
from .core.corpus_deep_index import build_corpus_deep_index, corpus_deep_index_report
from .core.doctor import run_doctor, run_healer
from .core.desktop_runtime import desktop_catalog, desktop_cycle_overlay, desktop_login, desktop_open_app, desktop_overlay_status, desktop_package_center, desktop_run_service, desktop_search, desktop_shell, desktop_snapshot, desktop_tile_explorer
from .core.engine import submit_intent, tick
from .core.events import read_events
from .core.fractal_kernel import kernel_archive, kernel_boot, kernel_schedule, kernel_status, kernel_syscall
from .core.chrono_mesh import checkpoint_mission, compile_mission_graph, mission_journal_report, replay_mission, simulate_mission_recovery
from .core.future_fabric import execute_future_plan, orchestrate_jobs
from .core.formula_programs import discover_formula_programs, evolve_formula_programs, formula_program_report, formula_runtime_advice, simulate_formula_programs
from .core.gpu_runtime import detect_gpu_runtime, gpu_execute_stub, mission_control_snapshot
from .core.hetero_scheduler import assign_jobs, available_devices
from .core.mesh_federation import mesh_accept_import, mesh_adopt_import, mesh_cache_manifest, mesh_cache_report, mesh_compact, mesh_consensus, mesh_daemon_cycle, mesh_daemon_snapshot, mesh_discover_peer, mesh_export_mission, mesh_flush_outbox, mesh_import_bundle, mesh_pulse, mesh_rank_targets, mesh_register, mesh_relay_local, mesh_route_mission, mesh_route_mission_dynamic, mesh_status, mesh_sync_peers, run_mesh_daemon
from .core.meta_supervisor import supervisor_plan, supervisor_report, supervisor_run
from .core.native_desktop_stack import native_desktop_blueprint, native_installation_plan, native_package_catalog, write_native_desktop_report
from .core.native_userspace import package_manifest, userspace_alpha_report, userspace_session_start, vfs_list, vfs_mount_report, vfs_read, vfs_write, write_userspace_alpha_report
from .core.ollama_bridge import ai_model_orchestrator_plan, create_ollama_idea_plan, free_ai_model_catalog, ollama_status
from .core.perf_governor import PerformanceGovernor
from .core.perf_lab import calibration_report, run_safe_benchmark
from .core.ram_memory import OmegaRAM
from .core.research_fusion import research_fusion_report, run_research_fusion
from .core.scientific_formula_forge import scientific_formula_catalog, scientific_formula_plan, scientific_formula_report
from .core.state import ensure_workspace, load_state
from .core.storage_vfs import storage_mount_report, storage_read, storage_rollback, storage_snapshot, storage_verify, storage_write, write_storage_vfs_report
from .core.triple_kernel_innovation import triple_kernel_catalog, triple_kernel_plan
from .core.triple_kernel_runtime import triple_kernel_status, triple_kernel_synthesize
from .core.ui_runtime import available_views, build_ui_model
from .core.usage_blackbox import UsageArgumentParser, install_usage_error_hook, run_restart_recovery, usage_error_report
from .daemon import serve_daemon
from .dashboard import serve_dashboard
from .tilemindfs.planner import load_jobs_file, plan_jobs
from .tilemindfs.store import TileMindFS


def build_parser() -> argparse.ArgumentParser:
    parser = UsageArgumentParser(prog="omega_tile_os", description="Omega TileMind OS local kernel")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.add_argument("--workspace", required=True)

    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--workspace", required=True)
    submit_parser.add_argument("--title", required=True)
    submit_parser.add_argument("--intent", required=True)

    tick_parser = sub.add_parser("tick")
    tick_parser.add_argument("--workspace", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--workspace", required=True)

    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--workspace", required=True)

    heal_parser = sub.add_parser("heal")
    heal_parser.add_argument("--workspace", required=True)
    heal_parser.add_argument("--apply", action="store_true")

    usage_errors_parser = sub.add_parser("usage-errors")
    usage_errors_parser.add_argument("--workspace", required=True)

    restart_recovery_parser = sub.add_parser("restart-recovery")
    restart_recovery_parser.add_argument("--workspace", required=True)
    restart_recovery_parser.add_argument("--reason", default="manual")
    restart_recovery_parser.add_argument("--no-apply", action="store_true")
    restart_recovery_parser.add_argument("--no-doctor", action="store_true")

    ai_dev_catalog_parser = sub.add_parser("ai-dev-catalog")
    ai_dev_catalog_parser.add_argument("--workspace", required=True)
    ai_dev_catalog_parser.add_argument("--category", default=None)
    ai_dev_catalog_parser.add_argument("--limit", type=int, default=100)

    ai_dev_plan_parser = sub.add_parser("ai-dev-plan")
    ai_dev_plan_parser.add_argument("--workspace", required=True)
    ai_dev_plan_parser.add_argument("--focus", default="all")
    ai_dev_plan_parser.add_argument("--limit", type=int, default=12)
    ai_dev_plan_parser.add_argument("--queue", action="store_true")

    ollama_status_parser = sub.add_parser("ollama-status")
    ollama_status_parser.add_argument("--workspace", required=True)
    ollama_status_parser.add_argument("--endpoint", default=None)

    ollama_idea_parser = sub.add_parser("ollama-idea")
    ollama_idea_parser.add_argument("--workspace", required=True)
    ollama_idea_parser.add_argument("--idea", required=True)
    ollama_idea_parser.add_argument("--model", default=None)
    ollama_idea_parser.add_argument("--endpoint", default=None)
    ollama_idea_parser.add_argument("--queue-agents", action="store_true")
    ollama_idea_parser.add_argument("--run-workers", action="store_true")
    ollama_idea_parser.add_argument("--timeout", type=float, default=20.0)

    ai_model_catalog_parser = sub.add_parser("ai-model-catalog")
    ai_model_catalog_parser.add_argument("--workspace", required=True)
    ai_model_catalog_parser.add_argument("--role", default=None)

    ai_model_plan_parser = sub.add_parser("ai-model-plan")
    ai_model_plan_parser.add_argument("--workspace", required=True)
    ai_model_plan_parser.add_argument("--endpoint", default=None)

    supervisor_plan_parser = sub.add_parser("supervisor-plan")
    supervisor_plan_parser.add_argument("--workspace", required=True)
    supervisor_plan_parser.add_argument("--max-lanes", type=int, default=4)

    supervisor_run_parser = sub.add_parser("supervisor-run")
    supervisor_run_parser.add_argument("--workspace", required=True)
    supervisor_run_parser.add_argument("--max-lanes", type=int, default=4)
    supervisor_run_parser.add_argument("--no-queue", action="store_true")

    supervisor_report_parser = sub.add_parser("supervisor-report")
    supervisor_report_parser.add_argument("--workspace", required=True)

    desktop_parser = sub.add_parser("desktop")
    desktop_parser.add_argument("--workspace", required=True)

    desktop_shell_parser = sub.add_parser("desktop-shell")
    desktop_shell_parser.add_argument("--workspace", required=True)
    desktop_shell_parser.add_argument("--command", dest="shell_command", required=True)

    desktop_open_parser = sub.add_parser("desktop-open")
    desktop_open_parser.add_argument("--workspace", required=True)
    desktop_open_parser.add_argument("--app", required=True)

    desktop_service_parser = sub.add_parser("desktop-service")
    desktop_service_parser.add_argument("--workspace", required=True)
    desktop_service_parser.add_argument("--service", required=True)

    desktop_overlay_parser = sub.add_parser("desktop-overlay")
    desktop_overlay_parser.add_argument("--workspace", required=True)

    desktop_overlay_cycle_parser = sub.add_parser("desktop-overlay-cycle")
    desktop_overlay_cycle_parser.add_argument("--workspace", required=True)

    desktop_search_parser = sub.add_parser("desktop-search")
    desktop_search_parser.add_argument("--workspace", required=True)
    desktop_search_parser.add_argument("--query", required=True)

    desktop_files_parser = sub.add_parser("desktop-files")
    desktop_files_parser.add_argument("--workspace", required=True)

    desktop_packages_parser = sub.add_parser("desktop-packages")
    desktop_packages_parser.add_argument("--workspace", required=True)

    desktop_login_parser = sub.add_parser("desktop-login")
    desktop_login_parser.add_argument("--workspace", required=True)
    desktop_login_parser.add_argument("--role", choices=["guest", "user", "admin", "doctor"], required=True)

    classic_os_report_parser = sub.add_parser("classic-os-report")
    classic_os_report_parser.add_argument("--workspace", required=True)

    classic_os_capabilities_parser = sub.add_parser("classic-os-capabilities")
    classic_os_capabilities_parser.add_argument("--workspace", required=True)

    onboarding_pack_parser = sub.add_parser("onboarding-pack")
    onboarding_pack_parser.add_argument("--workspace", required=True)

    native_os_report_parser = sub.add_parser("native-os-report")
    native_os_report_parser.add_argument("--workspace", required=True)

    native_os_blueprint_parser = sub.add_parser("native-os-blueprint")
    native_os_blueprint_parser.add_argument("--workspace", required=True)

    native_os_install_parser = sub.add_parser("native-os-install-plan")
    native_os_install_parser.add_argument("--workspace", required=True)
    native_os_install_parser.add_argument("--target", choices=["vm", "machine"], default="vm")
    native_os_install_parser.add_argument("--disk-size-gb", type=int, default=32)
    native_os_install_parser.add_argument("--create-vm-disk", action="store_true")

    native_os_app_catalog_parser = sub.add_parser("native-os-app-catalog")
    native_os_app_catalog_parser.add_argument("--workspace", required=True)

    userspace_report_parser = sub.add_parser("userspace-alpha-report")
    userspace_report_parser.add_argument("--workspace", required=True)

    userspace_status_parser = sub.add_parser("userspace-alpha-status")
    userspace_status_parser.add_argument("--workspace", required=True)

    session_start_parser = sub.add_parser("session-start")
    session_start_parser.add_argument("--workspace", required=True)
    session_start_parser.add_argument("--role", choices=["guest", "user", "admin", "doctor"], default="user")

    vfs_mount_parser = sub.add_parser("vfs-mounts")
    vfs_mount_parser.add_argument("--workspace", required=True)

    vfs_ls_parser = sub.add_parser("vfs-ls")
    vfs_ls_parser.add_argument("--workspace", required=True)
    vfs_ls_parser.add_argument("--path", default="/")

    vfs_read_parser = sub.add_parser("vfs-read")
    vfs_read_parser.add_argument("--workspace", required=True)
    vfs_read_parser.add_argument("--path", required=True)

    vfs_write_parser = sub.add_parser("vfs-write")
    vfs_write_parser.add_argument("--workspace", required=True)
    vfs_write_parser.add_argument("--path", required=True)
    vfs_write_parser.add_argument("--text", required=True)
    vfs_write_parser.add_argument("--owner", default="user")

    package_manifest_parser = sub.add_parser("package-manifest")
    package_manifest_parser.add_argument("--workspace", required=True)

    storage_vfs_report_parser = sub.add_parser("storage-vfs-report")
    storage_vfs_report_parser.add_argument("--workspace", required=True)

    storage_vfs_status_parser = sub.add_parser("storage-vfs-status")
    storage_vfs_status_parser.add_argument("--workspace", required=True)

    storage_vfs_write_parser = sub.add_parser("storage-vfs-write")
    storage_vfs_write_parser.add_argument("--workspace", required=True)
    storage_vfs_write_parser.add_argument("--path", required=True)
    storage_vfs_write_parser.add_argument("--text", required=True)
    storage_vfs_write_parser.add_argument("--owner", default="user")

    storage_vfs_read_parser = sub.add_parser("storage-vfs-read")
    storage_vfs_read_parser.add_argument("--workspace", required=True)
    storage_vfs_read_parser.add_argument("--path", required=True)

    storage_vfs_snapshot_parser = sub.add_parser("storage-vfs-snapshot")
    storage_vfs_snapshot_parser.add_argument("--workspace", required=True)
    storage_vfs_snapshot_parser.add_argument("--label", default="manual")

    storage_vfs_rollback_parser = sub.add_parser("storage-vfs-rollback")
    storage_vfs_rollback_parser.add_argument("--workspace", required=True)
    storage_vfs_rollback_parser.add_argument("--target", default="last-write")

    storage_vfs_verify_parser = sub.add_parser("storage-vfs-verify")
    storage_vfs_verify_parser.add_argument("--workspace", required=True)

    kernel_boot_parser = sub.add_parser("kernel-boot")
    kernel_boot_parser.add_argument("--workspace", required=True)

    kernel_status_parser = sub.add_parser("kernel-status")
    kernel_status_parser.add_argument("--workspace", required=True)

    kernel_schedule_parser = sub.add_parser("kernel-schedule")
    kernel_schedule_parser.add_argument("--workspace", required=True)

    kernel_archive_parser = sub.add_parser("kernel-archive")
    kernel_archive_parser.add_argument("--workspace", required=True)

    kernel_syscall_parser = sub.add_parser("kernel-syscall")
    kernel_syscall_parser.add_argument("--workspace", required=True)
    kernel_syscall_parser.add_argument("--name", required=True)
    kernel_syscall_parser.add_argument("--payload-json", default="{}")

    triple_kernel_catalog_parser = sub.add_parser("triple-kernel-catalog")
    triple_kernel_catalog_parser.add_argument("--workspace", required=True)
    triple_kernel_catalog_parser.add_argument("--vertex", default=None)
    triple_kernel_catalog_parser.add_argument("--limit", type=int, default=1200)

    triple_kernel_plan_parser = sub.add_parser("triple-kernel-plan")
    triple_kernel_plan_parser.add_argument("--workspace", required=True)
    triple_kernel_plan_parser.add_argument("--limit", type=int, default=24)
    triple_kernel_plan_parser.add_argument("--queue", action="store_true")

    triple_kernel_status_parser = sub.add_parser("triple-kernel-status")
    triple_kernel_status_parser.add_argument("--workspace", required=True)

    triple_kernel_synthesize_parser = sub.add_parser("triple-kernel-synthesize")
    triple_kernel_synthesize_parser.add_argument("--workspace", required=True)
    triple_kernel_synthesize_parser.add_argument("--limit", type=int, default=18)
    triple_kernel_synthesize_parser.add_argument("--queue", action="store_true")

    events_parser = sub.add_parser("events")
    events_parser.add_argument("--workspace", required=True)
    events_parser.add_argument("--limit", type=int, default=20)

    autonomy_submit_parser = sub.add_parser("autonomy-submit")
    autonomy_submit_parser.add_argument("--workspace", required=True)
    autonomy_submit_parser.add_argument("--domain", choices=["code", "research", "automation", "ecosystem"], required=True)
    autonomy_submit_parser.add_argument("--title", required=True)
    autonomy_submit_parser.add_argument("--goal", required=True)
    autonomy_submit_parser.add_argument("--context", default="")

    autonomy_run_parser = sub.add_parser("autonomy-run")
    autonomy_run_parser.add_argument("--workspace", required=True)
    autonomy_run_parser.add_argument("--max-items", type=int, default=1)

    autonomy_report_parser = sub.add_parser("autonomy-report")
    autonomy_report_parser.add_argument("--workspace", required=True)

    autonomy_evolve_parser = sub.add_parser("autonomy-evolve")
    autonomy_evolve_parser.add_argument("--workspace", required=True)
    autonomy_evolve_parser.add_argument("--no-queue", action="store_true")

    worker_submit_parser = sub.add_parser("worker-submit")
    worker_submit_parser.add_argument("--workspace", required=True)
    worker_submit_parser.add_argument("--mode", choices=["builder", "researcher", "automator", "evolver"], required=True)
    worker_submit_parser.add_argument("--title", required=True)
    worker_submit_parser.add_argument("--objective", required=True)
    worker_submit_parser.add_argument("--scope", default="")

    worker_run_parser = sub.add_parser("worker-run")
    worker_run_parser.add_argument("--workspace", required=True)
    worker_run_parser.add_argument("--max-items", type=int, default=1)
    worker_run_parser.add_argument("--no-autonomy", action="store_true")

    worker_report_parser = sub.add_parser("worker-report")
    worker_report_parser.add_argument("--workspace", required=True)

    worker_mission_parser = sub.add_parser("worker-mission")
    worker_mission_parser.add_argument("--workspace", required=True)
    worker_mission_parser.add_argument("--session-id", required=True)
    worker_mission_parser.add_argument("--route", choices=["dynamic", "checkpoint"], default="dynamic")

    ui_views_parser = sub.add_parser("ui-views")
    ui_views_parser.add_argument("--workspace", required=True)

    ui_view_parser = sub.add_parser("ui-view")
    ui_view_parser.add_argument("--workspace", required=True)
    ui_view_parser.add_argument("--view", required=True)

    router_parser = sub.add_parser("router-report")
    router_parser.add_argument("--workspace", required=True)

    router_next_parser = sub.add_parser("router-next")
    router_next_parser.add_argument("--workspace", required=True)

    router_loop_parser = sub.add_parser("router-loop")
    router_loop_parser.add_argument("--workspace", required=True)
    router_loop_parser.add_argument("--max-cycles", type=int, default=3)
    router_loop_parser.add_argument("--stop-on-elevated", action="store_true")

    router_sim_parser = sub.add_parser("router-simulate")
    router_sim_parser.add_argument("--workspace", required=True)
    router_sim_parser.add_argument("--max-cycles", type=int, default=3)
    router_sim_parser.add_argument("--stop-on-elevated", action="store_true")

    research_fusion_parser = sub.add_parser("research-fusion")
    research_fusion_parser.add_argument("--workspace", required=True)
    research_fusion_parser.add_argument("--corpus", required=True)
    research_fusion_parser.add_argument("--pdf", nargs="*", default=[])
    research_fusion_parser.add_argument("--max-formula-files", type=int, default=12)
    research_fusion_parser.add_argument("--queue-followups", action="store_true")

    research_fusion_report_parser = sub.add_parser("research-fusion-report")
    research_fusion_report_parser.add_argument("--workspace", required=True)

    corpus_index_parser = sub.add_parser("corpus-index")
    corpus_index_parser.add_argument("--workspace", required=True)
    corpus_index_parser.add_argument("--corpus", required=True)
    corpus_index_parser.add_argument("--max-files", type=int, default=None)

    corpus_report_parser = sub.add_parser("corpus-report")
    corpus_report_parser.add_argument("--workspace", required=True)

    formula_discover_parser = sub.add_parser("formula-discover")
    formula_discover_parser.add_argument("--workspace", required=True)
    formula_discover_parser.add_argument("--corpus", required=True)
    formula_discover_parser.add_argument("--max-formula-files", type=int, default=8)
    formula_discover_parser.add_argument("--max-programs", type=int, default=6)
    formula_discover_parser.add_argument("--no-install", action="store_true")

    formula_programs_parser = sub.add_parser("formula-programs")
    formula_programs_parser.add_argument("--workspace", required=True)

    formula_simulate_parser = sub.add_parser("formula-simulate")
    formula_simulate_parser.add_argument("--workspace", required=True)
    formula_simulate_parser.add_argument("--performance-pressure", type=float, default=0.52)
    formula_simulate_parser.add_argument("--energy-pressure", type=float, default=0.32)
    formula_simulate_parser.add_argument("--complexity-pressure", type=float, default=0.36)
    formula_simulate_parser.add_argument("--risk-pressure", type=float, default=0.24)
    formula_simulate_parser.add_argument("--coherence", type=float, default=0.72)

    formula_evolve_parser = sub.add_parser("formula-evolve")
    formula_evolve_parser.add_argument("--workspace", required=True)
    formula_evolve_parser.add_argument("--corpus", default=None)
    formula_evolve_parser.add_argument("--refresh", action="store_true")
    formula_evolve_parser.add_argument("--max-formula-files", type=int, default=8)
    formula_evolve_parser.add_argument("--max-programs", type=int, default=6)
    formula_evolve_parser.add_argument("--queue-limit", type=int, default=4)

    formula_advice_parser = sub.add_parser("formula-advice")
    formula_advice_parser.add_argument("--workspace", required=True)

    scientific_catalog_parser = sub.add_parser("scientific-formula-catalog")
    scientific_catalog_parser.add_argument("--workspace", required=True)
    scientific_catalog_parser.add_argument("--target", default=None)
    scientific_catalog_parser.add_argument("--limit", type=int, default=120)

    scientific_plan_parser = sub.add_parser("scientific-formula-plan")
    scientific_plan_parser.add_argument("--workspace", required=True)
    scientific_plan_parser.add_argument("--target", default=None)
    scientific_plan_parser.add_argument("--limit", type=int, default=18)
    scientific_plan_parser.add_argument("--queue", action="store_true")

    scientific_report_parser = sub.add_parser("scientific-formula-report")
    scientific_report_parser.add_argument("--workspace", required=True)

    auto_upgrade_parser = sub.add_parser("auto-upgrade")
    auto_upgrade_parser.add_argument("--workspace", required=True)
    auto_upgrade_parser.add_argument("--duration-minutes", type=float, default=60.0)
    auto_upgrade_parser.add_argument("--cycle-delay", type=float, default=60.0)
    auto_upgrade_parser.add_argument("--max-cycles", type=int, default=None)
    auto_upgrade_parser.add_argument("--programs-per-cycle", type=int, default=3)
    auto_upgrade_parser.add_argument("--corpus", default=None)
    auto_upgrade_parser.add_argument("--run-tests", action="store_true")
    auto_upgrade_parser.add_argument("--no-bare-metal-build", action="store_true")

    auto_upgrade_report_parser = sub.add_parser("auto-upgrade-report")
    auto_upgrade_report_parser.add_argument("--workspace", required=True)

    tile_store_parser = sub.add_parser("tile-store")
    tile_store_parser.add_argument("--workspace", required=True)
    tile_store_parser.add_argument("--file", required=True)
    tile_store_parser.add_argument("--mode", choices=["cdc", "fixed"], default="cdc")
    tile_store_parser.add_argument("--tile-size", type=int, default=None)

    tile_reconstruct_parser = sub.add_parser("tile-reconstruct")
    tile_reconstruct_parser.add_argument("--workspace", required=True)
    tile_reconstruct_parser.add_argument("--manifest", required=True)
    tile_reconstruct_parser.add_argument("--output", required=True)

    tile_report_parser = sub.add_parser("tile-report")
    tile_report_parser.add_argument("--workspace", required=True)

    memory_put_parser = sub.add_parser("memory-put")
    memory_put_parser.add_argument("--workspace", required=True)
    memory_put_parser.add_argument("--key", required=True)
    memory_put_parser.add_argument("--text", required=True)

    memory_get_parser = sub.add_parser("memory-get")
    memory_get_parser.add_argument("--workspace", required=True)
    memory_get_parser.add_argument("--key", required=True)

    memory_report_parser = sub.add_parser("memory-report")
    memory_report_parser.add_argument("--workspace", required=True)

    perf_sample_parser = sub.add_parser("perf-sample")
    perf_sample_parser.add_argument("--workspace", required=True)

    perf_report_parser = sub.add_parser("perf-report")
    perf_report_parser.add_argument("--workspace", required=True)

    perf_tune_parser = sub.add_parser("perf-tune")
    perf_tune_parser.add_argument("--workspace", required=True)

    perf_benchmark_parser = sub.add_parser("perf-benchmark")
    perf_benchmark_parser.add_argument("--workspace", required=True)
    perf_benchmark_parser.add_argument("--seconds", type=float, default=6.0)

    perf_calibration_parser = sub.add_parser("perf-calibration")
    perf_calibration_parser.add_argument("--workspace", required=True)

    schedule_parser = sub.add_parser("schedule")
    schedule_parser.add_argument("--workspace", required=True)
    schedule_parser.add_argument("--jobs", required=True)
    schedule_parser.add_argument("--output", choices=["text", "json"], default="text")

    devices_parser = sub.add_parser("devices")
    devices_parser.add_argument("--workspace", required=True)

    future_plan_parser = sub.add_parser("future-plan")
    future_plan_parser.add_argument("--workspace", required=True)
    future_plan_parser.add_argument("--jobs", required=True)
    future_plan_parser.add_argument("--output", choices=["text", "json"], default="text")

    future_run_parser = sub.add_parser("future-run")
    future_run_parser.add_argument("--workspace", required=True)
    future_run_parser.add_argument("--jobs", required=True)
    future_run_parser.add_argument("--output", choices=["text", "json"], default="text")

    mission_graph_parser = sub.add_parser("mission-graph")
    mission_graph_parser.add_argument("--workspace", required=True)
    mission_graph_parser.add_argument("--jobs", required=True)
    mission_graph_parser.add_argument("--output", choices=["text", "json"], default="text")

    mission_recovery_parser = sub.add_parser("mission-recovery")
    mission_recovery_parser.add_argument("--workspace", required=True)
    mission_recovery_parser.add_argument("--jobs", required=True)
    mission_recovery_parser.add_argument("--failed", nargs="*", default=[])
    mission_recovery_parser.add_argument("--output", choices=["text", "json"], default="text")

    mission_checkpoint_parser = sub.add_parser("mission-checkpoint")
    mission_checkpoint_parser.add_argument("--workspace", required=True)
    mission_checkpoint_parser.add_argument("--jobs", required=True)

    mission_replay_parser = sub.add_parser("mission-replay")
    mission_replay_parser.add_argument("--workspace", required=True)
    mission_replay_parser.add_argument("--jobs", required=True)
    mission_replay_parser.add_argument("--from-job", default=None)
    mission_replay_parser.add_argument("--output", choices=["text", "json"], default="text")

    mission_journal_parser = sub.add_parser("mission-journal")
    mission_journal_parser.add_argument("--workspace", required=True)

    gpu_runtime_parser = sub.add_parser("gpu-runtime")
    gpu_runtime_parser.add_argument("--workspace", required=True)

    gpu_probe_parser = sub.add_parser("gpu-probe")
    gpu_probe_parser.add_argument("--workspace", required=True)
    gpu_probe_parser.add_argument("--device", required=True)
    gpu_probe_parser.add_argument("--size", type=int, default=96)

    mesh_register_parser = sub.add_parser("mesh-register")
    mesh_register_parser.add_argument("--workspace", required=True)
    mesh_register_parser.add_argument("--name", required=True)
    mesh_register_parser.add_argument("--endpoint", required=True)
    mesh_register_parser.add_argument("--role", default="worker")

    mesh_status_parser = sub.add_parser("mesh-status")
    mesh_status_parser.add_argument("--workspace", required=True)

    mesh_export_parser = sub.add_parser("mesh-export")
    mesh_export_parser.add_argument("--workspace", required=True)
    mesh_export_parser.add_argument("--jobs", required=True)
    mesh_export_parser.add_argument("--target-node", required=True)

    mesh_import_parser = sub.add_parser("mesh-import")
    mesh_import_parser.add_argument("--workspace", required=True)
    mesh_import_parser.add_argument("--bundle", required=True)
    mesh_import_parser.add_argument("--pending", action="store_true")

    mesh_relay_parser = sub.add_parser("mesh-relay")
    mesh_relay_parser.add_argument("--workspace", required=True)
    mesh_relay_parser.add_argument("--bundle", required=True)
    mesh_relay_parser.add_argument("--target-workspace", required=True)

    mesh_accept_parser = sub.add_parser("mesh-accept")
    mesh_accept_parser.add_argument("--workspace", required=True)
    mesh_accept_parser.add_argument("--mission-id", required=True)

    mesh_adopt_parser = sub.add_parser("mesh-adopt")
    mesh_adopt_parser.add_argument("--workspace", required=True)
    mesh_adopt_parser.add_argument("--mission-id", required=True)

    mesh_pulse_parser = sub.add_parser("mesh-pulse")
    mesh_pulse_parser.add_argument("--workspace", required=True)

    mesh_compact_parser = sub.add_parser("mesh-compact")
    mesh_compact_parser.add_argument("--workspace", required=True)

    mesh_flush_parser = sub.add_parser("mesh-flush")
    mesh_flush_parser.add_argument("--workspace", required=True)

    mesh_cache_parser = sub.add_parser("mesh-cache")
    mesh_cache_parser.add_argument("--workspace", required=True)

    mesh_cache_manifest_parser = sub.add_parser("mesh-cache-manifest")
    mesh_cache_manifest_parser.add_argument("--workspace", required=True)
    mesh_cache_manifest_parser.add_argument("--limit", type=int, default=256)

    mesh_consensus_parser = sub.add_parser("mesh-consensus")
    mesh_consensus_parser.add_argument("--workspace", required=True)
    mesh_consensus_parser.add_argument("--node", required=False)

    mesh_discover_parser = sub.add_parser("mesh-discover")
    mesh_discover_parser.add_argument("--workspace", required=True)
    mesh_discover_parser.add_argument("--endpoint", required=True)
    mesh_discover_parser.add_argument("--local-endpoint", required=True)

    mesh_sync_parser = sub.add_parser("mesh-sync")
    mesh_sync_parser.add_argument("--workspace", required=True)

    mesh_rank_parser = sub.add_parser("mesh-rank")
    mesh_rank_parser.add_argument("--workspace", required=True)
    mesh_rank_parser.add_argument("--jobs", required=True)

    mesh_route_parser = sub.add_parser("mesh-route")
    mesh_route_parser.add_argument("--workspace", required=True)
    mesh_route_parser.add_argument("--jobs", required=True)

    mesh_route_dynamic_parser = sub.add_parser("mesh-route-dynamic")
    mesh_route_dynamic_parser.add_argument("--workspace", required=True)
    mesh_route_dynamic_parser.add_argument("--jobs", required=True)

    mesh_daemon_parser = sub.add_parser("mesh-daemon")
    mesh_daemon_parser.add_argument("--workspace", required=True)
    mesh_daemon_parser.add_argument("--interval", type=float, default=5.0)
    mesh_daemon_parser.add_argument("--cycles", type=int, default=1)
    mesh_daemon_parser.add_argument("--no-compact", action="store_true")

    mesh_heartbeat_parser = sub.add_parser("mesh-heartbeat")
    mesh_heartbeat_parser.add_argument("--workspace", required=True)

    mission_control_parser = sub.add_parser("mission-control")
    mission_control_parser.add_argument("--workspace", required=True)

    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--workspace", required=True)
    plan_parser.add_argument("--jobs", required=True)
    plan_parser.add_argument("--resource-limit", type=float, default=None)
    plan_parser.add_argument("--top-k", type=int, default=None)
    plan_parser.add_argument("--output", choices=["text", "json"], default="text")

    daemon_parser = sub.add_parser("daemon")
    daemon_parser.add_argument("--workspace", required=True)
    daemon_parser.add_argument("--host", default="127.0.0.1")
    daemon_parser.add_argument("--port", type=int, default=8890)

    dashboard_parser = sub.add_parser("dashboard")
    dashboard_parser.add_argument("--workspace", required=True)
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", type=int, default=8891)

    return parser


def format_plan_text(result: dict) -> str:
    lines = [
        "Omega TileMind Planner",
        f"resource_limit: {result['resource_limit']}",
        f"top_k: {result['top_k']}",
        f"total_resource: {result['total_resource']}",
        "",
        "Selected jobs:",
    ]
    for item in result["selected"]:
        lines.append(
            f"- {item.get('job_id', 'job')} score={item['score']:.4f} omega={item['omega']:.4f} resource={item.get('resource_estimate', 0.0)}"
        )
    if not result["selected"]:
        lines.append("- none")
    placements = result.get("scheduler", {}).get("placements", [])
    if placements:
        lines.extend(["", "Placements:"])
        for item in placements:
            lines.append(
                f"- {item.get('job_id', 'job')} -> {item['target_device']} ({item['target_kind']}) score={item['scheduler_score']:.4f}"
            )
    return "\n".join(lines)


def cmd_status(workspace: Path) -> int:
    state = load_state(workspace)
    perf_report = PerformanceGovernor(workspace).report()
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    summary = {
        "node": state["node"],
        "metrics": state["metrics"],
        "queued_titles": [item["title"] for item in state["intents"] if item["status"] == "queued"],
        "recent_artifacts": state["artifacts"][-5:],
        "tilemindfs": TileMindFS(workspace).report(),
        "omega_ram": OmegaRAM(workspace).report(),
        "performance_governor": {
            "mode": perf_report["mode"],
            "formulas": perf_report["formulas"],
            "recommendations": perf_report["recommendations"],
        },
        "autonomy": autonomy,
        "worker": worker,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


def main() -> None:
    install_usage_error_hook()
    parser = build_parser()
    args = parser.parse_args()
    workspace = Path(getattr(args, "workspace", ".")).resolve()

    if args.command == "init":
        ensure_workspace(workspace)
        print(f"Workspace initialized at {workspace}")
        return

    if args.command == "submit":
        print(json.dumps(submit_intent(workspace, args.title, args.intent), indent=2, ensure_ascii=True))
        return

    if args.command == "tick":
        print(json.dumps(tick(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "status":
        raise SystemExit(cmd_status(workspace))

    if args.command == "doctor":
        print(json.dumps(run_doctor(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "heal":
        print(json.dumps(run_healer(workspace, apply=args.apply), indent=2, ensure_ascii=True))
        return

    if args.command == "usage-errors":
        print(json.dumps(usage_error_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "restart-recovery":
        print(
            json.dumps(
                run_restart_recovery(
                    workspace,
                    reason=args.reason,
                    apply=not args.no_apply,
                    run_doctor_check=not args.no_doctor,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "ai-dev-catalog":
        print(json.dumps(ai_dev_catalog(category=args.category, limit=args.limit), indent=2, ensure_ascii=True))
        return

    if args.command == "ai-dev-plan":
        print(json.dumps(ai_dev_plan(workspace, focus=args.focus, limit=args.limit, queue=args.queue), indent=2, ensure_ascii=True))
        return

    if args.command == "ollama-status":
        print(json.dumps(ollama_status(endpoint=args.endpoint), indent=2, ensure_ascii=True))
        return

    if args.command == "ollama-idea":
        print(
            json.dumps(
                create_ollama_idea_plan(
                    workspace,
                    args.idea,
                    model=args.model,
                    endpoint=args.endpoint,
                    timeout_s=args.timeout,
                    queue_agents=args.queue_agents,
                    run_workers=args.run_workers,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "ai-model-catalog":
        print(json.dumps({"models": free_ai_model_catalog(role=args.role)}, indent=2, ensure_ascii=True))
        return

    if args.command == "ai-model-plan":
        print(json.dumps(ai_model_orchestrator_plan(workspace, endpoint=args.endpoint), indent=2, ensure_ascii=True))
        return

    if args.command == "supervisor-plan":
        print(json.dumps(supervisor_plan(workspace, max_lanes=args.max_lanes), indent=2, ensure_ascii=True))
        return

    if args.command == "supervisor-run":
        print(json.dumps(supervisor_run(workspace, max_lanes=args.max_lanes, queue=not args.no_queue), indent=2, ensure_ascii=True))
        return

    if args.command == "supervisor-report":
        print(json.dumps(supervisor_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop":
        print(json.dumps(desktop_snapshot(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-shell":
        print(json.dumps(desktop_shell(workspace, args.shell_command), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-open":
        print(json.dumps(desktop_open_app(workspace, args.app), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-service":
        print(json.dumps(desktop_run_service(workspace, args.service), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-overlay":
        print(json.dumps(desktop_overlay_status(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-overlay-cycle":
        print(json.dumps(desktop_cycle_overlay(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-search":
        print(json.dumps(desktop_search(workspace, args.query), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-files":
        print(json.dumps(desktop_tile_explorer(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-packages":
        print(json.dumps(desktop_package_center(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "desktop-login":
        print(json.dumps(desktop_login(workspace, args.role), indent=2, ensure_ascii=True))
        return

    if args.command == "classic-os-report":
        print(json.dumps(write_classic_os_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "classic-os-capabilities":
        print(json.dumps(classic_capability_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "onboarding-pack":
        print(json.dumps(onboarding_pack(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "native-os-report":
        print(json.dumps(write_native_desktop_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "native-os-blueprint":
        print(json.dumps(native_desktop_blueprint(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "native-os-install-plan":
        print(
            json.dumps(
                native_installation_plan(
                    workspace,
                    target=args.target,
                    disk_size_gb=args.disk_size_gb,
                    create_vm_disk=args.create_vm_disk,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "native-os-app-catalog":
        print(json.dumps(native_package_catalog(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "userspace-alpha-report":
        print(json.dumps(write_userspace_alpha_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "userspace-alpha-status":
        print(json.dumps(userspace_alpha_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "session-start":
        print(json.dumps(userspace_session_start(workspace, args.role), indent=2, ensure_ascii=True))
        return

    if args.command == "vfs-mounts":
        print(json.dumps(vfs_mount_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "vfs-ls":
        print(json.dumps(vfs_list(workspace, args.path), indent=2, ensure_ascii=True))
        return

    if args.command == "vfs-read":
        print(json.dumps(vfs_read(workspace, args.path), indent=2, ensure_ascii=True))
        return

    if args.command == "vfs-write":
        print(json.dumps(vfs_write(workspace, args.path, args.text, owner=args.owner), indent=2, ensure_ascii=True))
        return

    if args.command == "package-manifest":
        print(json.dumps(package_manifest(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-report":
        print(json.dumps(write_storage_vfs_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-status":
        print(json.dumps(storage_mount_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-write":
        print(json.dumps(storage_write(workspace, args.path, args.text, owner=args.owner), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-read":
        print(json.dumps(storage_read(workspace, args.path), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-snapshot":
        print(json.dumps(storage_snapshot(workspace, label=args.label), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-rollback":
        print(json.dumps(storage_rollback(workspace, target=args.target), indent=2, ensure_ascii=True))
        return

    if args.command == "storage-vfs-verify":
        print(json.dumps(storage_verify(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "kernel-boot":
        print(json.dumps(kernel_boot(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "kernel-status":
        print(json.dumps(kernel_status(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "kernel-schedule":
        print(json.dumps(kernel_schedule(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "kernel-archive":
        print(json.dumps(kernel_archive(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "kernel-syscall":
        print(json.dumps(kernel_syscall(workspace, args.name, json.loads(args.payload_json)), indent=2, ensure_ascii=True))
        return

    if args.command == "triple-kernel-catalog":
        print(json.dumps(triple_kernel_catalog(vertex=args.vertex, limit=args.limit), indent=2, ensure_ascii=True))
        return

    if args.command == "triple-kernel-plan":
        print(json.dumps(triple_kernel_plan(workspace, limit=args.limit, queue=args.queue), indent=2, ensure_ascii=True))
        return

    if args.command == "triple-kernel-status":
        print(json.dumps(triple_kernel_status(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "triple-kernel-synthesize":
        print(json.dumps(triple_kernel_synthesize(workspace, limit=args.limit, queue=args.queue), indent=2, ensure_ascii=True))
        return

    if args.command == "events":
        print(json.dumps(read_events(workspace, limit=args.limit), indent=2, ensure_ascii=True))
        return

    if args.command == "autonomy-submit":
        print(json.dumps(submit_workload(workspace, args.domain, args.title, args.goal, context=args.context), indent=2, ensure_ascii=True))
        return

    if args.command == "autonomy-run":
        print(json.dumps(run_workloads(workspace, max_items=args.max_items), indent=2, ensure_ascii=True))
        return

    if args.command == "autonomy-report":
        print(json.dumps(autonomy_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "autonomy-evolve":
        print(json.dumps(evolve_ecosystem(workspace, queue_followups=not args.no_queue), indent=2, ensure_ascii=True))
        return

    if args.command == "worker-submit":
        print(json.dumps(submit_worker_session(workspace, args.mode, args.title, args.objective, scope=args.scope), indent=2, ensure_ascii=True))
        return

    if args.command == "worker-run":
        print(json.dumps(run_worker_sessions(workspace, max_items=args.max_items, auto_queue_autonomy=not args.no_autonomy), indent=2, ensure_ascii=True))
        return

    if args.command == "worker-report":
        print(json.dumps(worker_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "worker-mission":
        print(json.dumps(worker_to_mission(workspace, args.session_id, route=args.route), indent=2, ensure_ascii=True))
        return

    if args.command == "ui-views":
        print(json.dumps({"views": available_views()}, indent=2, ensure_ascii=True))
        return

    if args.command == "ui-view":
        print(json.dumps(build_ui_model(workspace, active_view=args.view), indent=2, ensure_ascii=True))
        return

    if args.command == "router-report":
        print(json.dumps(route_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "router-next":
        print(json.dumps(execute_next_route(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "router-loop":
        print(
            json.dumps(
                execute_route_loop(workspace, max_cycles=args.max_cycles, stop_on_elevated=args.stop_on_elevated),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "router-simulate":
        print(
            json.dumps(
                simulate_route_loop(workspace, max_cycles=args.max_cycles, stop_on_elevated=args.stop_on_elevated),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "research-fusion":
        print(
            json.dumps(
                run_research_fusion(
                    workspace,
                    Path(args.corpus).resolve(),
                    [Path(item).resolve() for item in args.pdf],
                    max_formula_files=args.max_formula_files,
                    queue_followups=args.queue_followups,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "research-fusion-report":
        print(json.dumps(research_fusion_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "corpus-index":
        print(json.dumps(build_corpus_deep_index(workspace, Path(args.corpus).resolve(), max_files=args.max_files), indent=2, ensure_ascii=True))
        return

    if args.command == "corpus-report":
        print(json.dumps(corpus_deep_index_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "formula-discover":
        print(
            json.dumps(
                discover_formula_programs(
                    workspace,
                    Path(args.corpus).resolve(),
                    max_formula_files=args.max_formula_files,
                    max_programs=args.max_programs,
                    install=not args.no_install,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "formula-programs":
        print(json.dumps(formula_program_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "formula-simulate":
        print(
            json.dumps(
                simulate_formula_programs(
                    workspace,
                    signals={
                        "performance_pressure": args.performance_pressure,
                        "energy_pressure": args.energy_pressure,
                        "complexity_pressure": args.complexity_pressure,
                        "risk_pressure": args.risk_pressure,
                        "coherence": args.coherence,
                    },
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "formula-evolve":
        print(
            json.dumps(
                evolve_formula_programs(
                    workspace,
                    corpus_root=Path(args.corpus).resolve() if args.corpus else None,
                    refresh=args.refresh,
                    max_formula_files=args.max_formula_files,
                    max_programs=args.max_programs,
                    queue_limit=args.queue_limit,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "formula-advice":
        perf = PerformanceGovernor(workspace).report()
        autonomy = autonomy_report(workspace)
        worker = worker_report(workspace)
        print(
            json.dumps(
                formula_runtime_advice(
                    workspace,
                    perf_report=perf,
                    router_signals={
                        "queued_autonomy": int(autonomy["status_counts"].get("queued", 0)),
                        "queued_workers": int(worker["status_counts"].get("queued", 0)),
                    },
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "scientific-formula-catalog":
        print(json.dumps({"formulas": scientific_formula_catalog(target=args.target, limit=args.limit)}, indent=2, ensure_ascii=True))
        return

    if args.command == "scientific-formula-plan":
        print(json.dumps(scientific_formula_plan(workspace, target=args.target, limit=args.limit, queue=args.queue), indent=2, ensure_ascii=True))
        return

    if args.command == "scientific-formula-report":
        print(json.dumps(scientific_formula_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "auto-upgrade":
        print(
            json.dumps(
                run_auto_upgrade_session(
                    workspace,
                    duration_minutes=args.duration_minutes,
                    cycle_delay_seconds=args.cycle_delay,
                    max_cycles=args.max_cycles,
                    programs_per_cycle=args.programs_per_cycle,
                    corpus_root=Path(args.corpus).resolve() if args.corpus else None,
                    run_tests=args.run_tests,
                    run_bare_metal_build=not args.no_bare_metal_build,
                ),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "auto-upgrade-report":
        print(json.dumps(auto_upgrade_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "tile-store":
        result = TileMindFS(workspace).store_file(Path(args.file).resolve(), mode=args.mode, tile_size=args.tile_size)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "tile-reconstruct":
        result = TileMindFS(workspace).reconstruct(args.manifest, Path(args.output).resolve())
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "tile-report":
        print(json.dumps(TileMindFS(workspace).report(), indent=2, ensure_ascii=True))
        return

    if args.command == "memory-put":
        print(json.dumps(OmegaRAM(workspace).put_text(key=args.key, text=args.text, source="cli"), indent=2, ensure_ascii=True))
        return

    if args.command == "memory-get":
        print(json.dumps(OmegaRAM(workspace).get(args.key), indent=2, ensure_ascii=True))
        return

    if args.command == "memory-report":
        print(json.dumps(OmegaRAM(workspace).report(), indent=2, ensure_ascii=True))
        return

    if args.command == "perf-sample":
        print(json.dumps(PerformanceGovernor(workspace).sample(), indent=2, ensure_ascii=True))
        return

    if args.command == "perf-report":
        print(json.dumps(PerformanceGovernor(workspace).report(), indent=2, ensure_ascii=True))
        return

    if args.command == "perf-tune":
        print(json.dumps(PerformanceGovernor(workspace).apply(), indent=2, ensure_ascii=True))
        return

    if args.command == "perf-benchmark":
        print(json.dumps(run_safe_benchmark(workspace, duration_s=args.seconds), indent=2, ensure_ascii=True))
        return

    if args.command == "perf-calibration":
        print(json.dumps(calibration_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "devices":
        print(json.dumps(available_devices(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "schedule":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = assign_jobs(workspace, jobs)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            lines = ["FractalOS Heterogeneous Scheduler", ""]
            for item in result["placements"]:
                lines.append(
                    f"- {item.get('job_id', 'job')} -> {item['target_device']} ({item['target_kind']}) score={item['scheduler_score']:.4f}"
                )
            if not result["placements"]:
                lines.append("- none")
            print("\n".join(lines))
        return

    if args.command == "future-plan":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = orchestrate_jobs(workspace, jobs)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            lines = ["FractalOS Future Fabric", ""]
            for wave in result["waves"]:
                lines.append(
                    f"- {wave['wave_id']} stability={wave['predicted_state']['stability_index']:.4f} jobs={len(wave['jobs'])}"
                )
            if not result["waves"]:
                lines.append("- none")
            print("\n".join(lines))
        return

    if args.command == "future-run":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = execute_future_plan(workspace, jobs)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            lines = [f"FractalOS Future Fabric Run", f"stop_reason: {result['stop_reason']}", ""]
            for wave in result["executed_waves"]:
                lines.append(
                    f"- {wave['wave_id']} stability={wave['predicted_state']['stability_index']:.4f} executed={len(wave['results'])}"
                )
            if not result["executed_waves"]:
                lines.append("- none")
            print("\n".join(lines))
        return

    if args.command == "mission-graph":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = compile_mission_graph(workspace, jobs)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            lines = ["FractalOS Chrono Mesh", ""]
            for node in result["graph"]["nodes"]:
                lines.append(
                    f"- {node['job_id']} wave={node['wave_id']} retry={node['retry_budget']} recovery={node['recovery_mode']}"
                )
            if not result["graph"]["nodes"]:
                lines.append("- none")
            print("\n".join(lines))
        return

    if args.command == "mission-recovery":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = simulate_mission_recovery(workspace, jobs, failed_jobs=list(args.failed))
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            lines = ["FractalOS Mission Recovery", ""]
            for action in result["recovery_actions"]:
                lines.append(
                    f"- {action['job_id']} -> {action['recommended_action']} retry={action['retry_budget']}"
                )
            if not result["recovery_actions"]:
                lines.append("- none")
            print("\n".join(lines))
        return

    if args.command == "mission-checkpoint":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        print(json.dumps(checkpoint_mission(workspace, jobs), indent=2, ensure_ascii=True))
        return

    if args.command == "mission-replay":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = replay_mission(workspace, jobs, from_job=args.from_job)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            print(f"mission_id: {result['mission_id']}\nreplayed_jobs: {len(result['replay']['replayed_jobs'])}\nstop_reason: {result['replay']['stop_reason']}")
        return

    if args.command == "mission-journal":
        print(json.dumps(mission_journal_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "gpu-runtime":
        print(json.dumps(detect_gpu_runtime(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "gpu-probe":
        print(json.dumps(gpu_execute_stub(workspace, args.device, size=args.size), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-register":
        print(json.dumps(mesh_register(workspace, args.name, args.endpoint, role=args.role), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-status":
        print(json.dumps(mesh_status(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-export":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        print(json.dumps(mesh_export_mission(workspace, jobs, args.target_node), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-import":
        print(
            json.dumps(
                mesh_import_bundle(workspace, Path(args.bundle).resolve(), auto_accept=not args.pending),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "mesh-relay":
        print(
            json.dumps(
                mesh_relay_local(workspace, Path(args.bundle).resolve(), Path(args.target_workspace).resolve()),
                indent=2,
                ensure_ascii=True,
            )
        )
        return

    if args.command == "mesh-accept":
        print(json.dumps(mesh_accept_import(workspace, args.mission_id), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-adopt":
        print(json.dumps(mesh_adopt_import(workspace, args.mission_id), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-pulse":
        print(json.dumps(mesh_pulse(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-compact":
        print(json.dumps(mesh_compact(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-flush":
        print(json.dumps(mesh_flush_outbox(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-cache":
        print(json.dumps(mesh_cache_report(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-cache-manifest":
        print(json.dumps(mesh_cache_manifest(workspace, limit=args.limit), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-consensus":
        print(json.dumps(mesh_consensus(workspace, node_name=args.node), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-discover":
        print(json.dumps(mesh_discover_peer(workspace, args.endpoint, args.local_endpoint), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-sync":
        print(json.dumps(mesh_sync_peers(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-rank":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        print(json.dumps(mesh_rank_targets(workspace, jobs), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-route":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        print(json.dumps(mesh_route_mission(workspace, jobs), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-route-dynamic":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        print(json.dumps(mesh_route_mission_dynamic(workspace, jobs), indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-daemon":
        result = run_mesh_daemon(
            workspace,
            interval_s=args.interval,
            max_cycles=max(args.cycles, 1),
            compact=not args.no_compact,
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "mesh-heartbeat":
        print(json.dumps(mesh_daemon_snapshot(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "mission-control":
        print(json.dumps(mission_control_snapshot(workspace), indent=2, ensure_ascii=True))
        return

    if args.command == "plan":
        jobs = load_jobs_file(Path(args.jobs).resolve())
        result = plan_jobs(workspace, jobs, resource_limit=args.resource_limit, top_k=args.top_k)
        if args.output == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            print(format_plan_text(result))
        return

    if args.command == "daemon":
        ensure_workspace(workspace)
        serve_daemon(workspace, args.host, args.port)
        return

    if args.command == "dashboard":
        ensure_workspace(workspace)
        serve_dashboard(workspace, args.host, args.port)
        return


if __name__ == "__main__":
    main()
