from __future__ import annotations

FUSION_REGISTRY = {
    "identity": "FractalOS",
    "motherboard_target": {
        "vendor": "ASUSTeK COMPUTER INC.",
        "product": "TUF GAMING B550-PLUS WIFI II",
        "firmware_target": "UEFI x64",
    },
    "sources": [
        {
            "project": "OmegaSystem",
            "role": "cli_planning_seed_orchestrator",
            "absorbed_as": ["fractal_cli_grammar", "job_pipeline", "seed_store"],
        },
        {
            "project": "Omegafusion",
            "role": "daemon_command_router_dashboard",
            "absorbed_as": ["daemon_control_plane", "dynamic_command_router", "runtime_workspace"],
        },
        {
            "project": "omega_tilemind_os",
            "role": "core_runtime_tilemindfs_omega_ram",
            "absorbed_as": ["tile_storage", "memory_tiers", "coherence_planner", "state_kernel"],
        },
        {
            "project": "fractal_ecosystem_build_v6",
            "role": "forge_api_intent_to_artifacts",
            "absorbed_as": ["forge_jobs", "bundle_export", "worker_generation"],
        },
        {
            "project": "fractal_auto_evolution_realtime",
            "role": "analytics_command_center",
            "absorbed_as": ["executive_scoring", "futures_lab", "operations_pack"],
        },
        {
            "project": "local_ai_stack_pack",
            "role": "local_ai_infrastructure",
            "absorbed_as": ["ollama_bridge", "agent_board", "tailscale_ready_stack"],
        },
        {
            "project": "LAYER_HUD",
            "role": "overlay_hud",
            "absorbed_as": ["desktop_overlay", "multi_monitor_presence", "hotkey_surface"],
        },
        {
            "project": "hypi",
            "role": "idea_forge_experience",
            "absorbed_as": ["sessioned_idea_forge", "zip_export", "force_matrix_ui"],
        },
        {
            "project": "IA",
            "role": "identity_memory_agent_ethos",
            "absorbed_as": ["agent_identity", "memory_conventions", "human_context"],
        },
        {
            "project": "folder0001/OmegaSystem2.12",
            "role": "advanced_module_bank",
            "absorbed_as": [
                "memory_entropy_analyzer",
                "knowledge_compression_engine",
                "multi_agent_micro_kernel",
                "temporal_pattern_engine",
                "attention_stabilizer",
            ],
        },
    ],
    "boot": {
        "strategy": "custom_uefi_x64_bootloader_source",
        "fallbacks": ["startup.nsh", "builder_generated_iso_tree"],
        "note": "Hardware-specific full guarantee requires compile and real boot test on target firmware.",
    },
}
