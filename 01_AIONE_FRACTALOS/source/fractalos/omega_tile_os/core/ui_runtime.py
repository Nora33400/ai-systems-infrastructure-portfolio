from __future__ import annotations

from pathlib import Path

from .action_router import route_report
from .ai_dev_tool import ai_dev_report
from .autonomy_runtime import WORKLOAD_DOMAINS, autonomy_report
from .chrono_mesh import mission_journal_report
from .codex_worker import worker_report
from .corpus_deep_index import corpus_deep_index_report
from .desktop_runtime import desktop_catalog
from .events import read_events
from .formula_programs import formula_program_report
from .gpu_runtime import detect_gpu_runtime
from .mesh_federation import mesh_cache_report, mesh_daemon_snapshot, mesh_status
from .meta_supervisor import supervisor_report
from .native_desktop_stack import native_desktop_blueprint, native_package_catalog
from .native_userspace import package_manifest, userspace_alpha_report, vfs_mount_report
from .ollama_bridge import ollama_idea_report
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .research_fusion import research_fusion_report
from .scientific_formula_forge import scientific_formula_report
from .state import load_state, load_ui_state
from .storage_vfs import storage_mount_report
from .triple_kernel_runtime import triple_kernel_status
from ..tilemindfs.store import TileMindFS


UI_VIEWS = [
    {
        "id": "mission-control",
        "title": "Mission Control",
        "description": "Cluster, mesh, missions et etat global du noyau.",
    },
    {
        "id": "worker-studio",
        "title": "Worker Studio",
        "description": "Sessions IA, plans, reviews et ponts vers les missions.",
    },
    {
        "id": "autonomy-lab",
        "title": "Autonomy Lab",
        "description": "Lanes code, recherche, automation et evolution.",
    },
    {
        "id": "research-desk",
        "title": "Research Desk",
        "description": "Questions, hypotheses, sources et signaux recents.",
    },
    {
        "id": "automation-forge",
        "title": "Automation Forge",
        "description": "Pipelines, triggers, safeguards et suivi d execution.",
    },
    {
        "id": "ai-dev-forge",
        "title": "AI Dev Forge",
        "description": "Cent ameliorations locales pour coder, tester, debugger et faire evoluer l OS.",
    },
    {
        "id": "ollama-chat-forge",
        "title": "Ollama Chat Forge",
        "description": "Chatbot local qui transforme les idees en plans, agents et workloads verifiables.",
    },
    {
        "id": "supervisor-forge",
        "title": "Supervisor Forge",
        "description": "Meta-orchestrateur multi-agent pour expansion propre, priorisee et mesurable.",
    },
    {
        "id": "triple-kernel-forge",
        "title": "Triple Kernel Forge",
        "description": "Triangle Matter, Mind, Mesh avec ponts, primitives et synthese pilotable.",
    },
    {
        "id": "fractal-desktop",
        "title": "Fractal Desktop",
        "description": "Bureau persistant avec overlay d intention, preuves, energie et agents.",
    },
    {
        "id": "native-os-installer",
        "title": "Native OS Installer",
        "description": "Installation persistante VM/machine, login, desktop classique et catalogue de paquets.",
    },
    {
        "id": "userspace-vfs-alpha",
        "title": "Userspace VFS Alpha",
        "description": "Sessions, RAM VFS, home utilisateur, manifestes de paquets et pont TileMindFS.",
    },
    {
        "id": "storage-vfs-stage22",
        "title": "Storage VFS Stage22",
        "description": "Home persistant journalise, snapshots, rollback et preuves TileMindFS.",
    },
    {
        "id": "scientific-formula-lab",
        "title": "Scientific Formula Lab",
        "description": "Formules bornees pour stockage, RAM, CPU, GPU, securite, agents et simulation.",
    },
    {
        "id": "corpus-integration-lab",
        "title": "Corpus Integration Lab",
        "description": "Index global de F:\\FractalFormulaCorpus et ponts vers les sous-systemes OS.",
    },
    {
        "id": "system-observatory",
        "title": "System Observatory",
        "description": "Performance, RAM, TileMindFS, GPU et telemetrie.",
    },
    {
        "id": "timeline-center",
        "title": "Timeline Center",
        "description": "Flux recent des missions, workers et evenements systeme.",
    },
]


def available_views() -> list[dict[str, str]]:
    return list(UI_VIEWS)


def _view_actions(active_view: str) -> list[dict[str, object]]:
    actions = {
        "mission-control": [
            {"id": "router-next", "label": "Run Smart Next Action", "kind": "button"},
            {"id": "router-loop", "label": "Run Guarded Autopilot", "kind": "button"},
            {"id": "mesh-consensus", "label": "Sync Cache Consensus", "kind": "button"},
            {"id": "mesh-compact", "label": "Compact Mesh State", "kind": "button"},
            {"id": "perf-tune", "label": "Apply Perf Tune", "kind": "button"},
        ],
        "worker-studio": [
            {"id": "worker-run", "label": "Run Worker Queue", "kind": "button"},
            {
                "id": "worker-submit",
                "label": "Create Worker Session",
                "kind": "form",
                "fields": [
                    {"name": "mode", "label": "Mode", "type": "select", "options": ["builder", "researcher", "automator", "evolver"]},
                    {"name": "title", "label": "Title", "type": "text"},
                    {"name": "objective", "label": "Objective", "type": "textarea"},
                    {"name": "scope", "label": "Scope", "type": "text"},
                ],
            },
        ],
        "autonomy-lab": [
            {"id": "autonomy-run", "label": "Run Autonomy Queue", "kind": "button"},
            {"id": "autonomy-evolve", "label": "Evolve Ecosystem", "kind": "button"},
            {
                "id": "autonomy-submit",
                "label": "Create Autonomy Workload",
                "kind": "form",
                "fields": [
                    {"name": "domain", "label": "Domain", "type": "select", "options": list(WORKLOAD_DOMAINS)},
                    {"name": "title", "label": "Title", "type": "text"},
                    {"name": "goal", "label": "Goal", "type": "textarea"},
                    {"name": "context", "label": "Context", "type": "text"},
                ],
            },
        ],
        "research-desk": [
            {"id": "autonomy-run", "label": "Run Research Queue", "kind": "button"},
            {
                "id": "autonomy-submit",
                "label": "New Research Track",
                "kind": "form",
                "defaults": {"domain": "research"},
                "fields": [
                    {"name": "domain", "label": "Domain", "type": "hidden"},
                    {"name": "title", "label": "Title", "type": "text"},
                    {"name": "goal", "label": "Goal", "type": "textarea"},
                    {"name": "context", "label": "Context", "type": "text"},
                ],
            },
        ],
        "automation-forge": [
            {"id": "mesh-consensus", "label": "Sync Forge Mesh", "kind": "button"},
            {
                "id": "autonomy-submit",
                "label": "New Automation Lane",
                "kind": "form",
                "defaults": {"domain": "automation"},
                "fields": [
                    {"name": "domain", "label": "Domain", "type": "hidden"},
                    {"name": "title", "label": "Title", "type": "text"},
                    {"name": "goal", "label": "Goal", "type": "textarea"},
                    {"name": "context", "label": "Context", "type": "text"},
                ],
            },
        ],
        "ai-dev-forge": [
            {"id": "ai-dev-plan", "label": "Generate AI Dev Plan", "kind": "button"},
            {"id": "ai-dev-plan-queue", "label": "Queue Safe Upgrades", "kind": "button"},
            {"id": "ai-dev-catalog", "label": "Browse 100 Improvements", "kind": "button"},
        ],
        "ollama-chat-forge": [
            {
                "id": "ollama-idea",
                "label": "Transform Idea Into Build Plan",
                "kind": "form",
                "fields": [
                    {"name": "idea", "label": "Idea", "type": "textarea"},
                    {"name": "queue_agents", "label": "Queue agents", "type": "checkbox"},
                    {"name": "run_workers", "label": "Run first worker safely", "type": "checkbox"},
                ],
            },
            {"id": "ollama-status", "label": "Check Local Ollama", "kind": "button"},
        ],
        "supervisor-forge": [
            {"id": "supervisor-plan", "label": "Compute Clean Growth Plan", "kind": "button"},
            {"id": "supervisor-run", "label": "Queue Supervised Expansion", "kind": "button"},
            {"id": "router-simulate", "label": "Simulate Before Running", "kind": "button"},
        ],
        "triple-kernel-forge": [
            {"id": "triple-kernel-status", "label": "Inspect Triangle Runtime", "kind": "button"},
            {"id": "triple-kernel-catalog", "label": "Browse 1200 Innovations", "kind": "button"},
            {"id": "triple-kernel-plan", "label": "Prioritize Triple Kernel Ideas", "kind": "button"},
            {"id": "triple-kernel-synthesize", "label": "Synthesize Primitives", "kind": "button"},
        ],
        "fractal-desktop": [
            {"id": "desktop-overlay", "label": "Inspect Persistent Overlay", "kind": "button"},
            {"id": "desktop-overlay-cycle", "label": "Cycle Overlay Lens", "kind": "button"},
            {"id": "desktop", "label": "Archive Desktop Snapshot", "kind": "button"},
        ],
        "native-os-installer": [
            {"id": "native-os-report", "label": "Write Native OS Report", "kind": "button"},
            {"id": "native-os-blueprint", "label": "Inspect Desktop Blueprint", "kind": "button"},
            {"id": "native-os-install-plan", "label": "Generate VM Install Plan", "kind": "button"},
            {"id": "native-os-app-catalog", "label": "Browse Package Catalog", "kind": "button"},
            {"id": "desktop-files", "label": "Open Tile Explorer Model", "kind": "button"},
            {"id": "desktop-packages", "label": "Open Package Center Model", "kind": "button"},
        ],
        "userspace-vfs-alpha": [
            {"id": "userspace-alpha-report", "label": "Write Userspace Report", "kind": "button"},
            {"id": "userspace-alpha-status", "label": "Inspect Userspace Status", "kind": "button"},
            {"id": "vfs-mounts", "label": "Inspect VFS Mounts", "kind": "button"},
            {"id": "vfs-ls-root", "label": "List Root VFS", "kind": "button"},
            {"id": "package-manifest", "label": "Read Package Manifest", "kind": "button"},
        ],
        "storage-vfs-stage22": [
            {"id": "storage-vfs-report", "label": "Write Storage VFS Report", "kind": "button"},
            {"id": "storage-vfs-status", "label": "Inspect Persistent Mount", "kind": "button"},
            {"id": "storage-vfs-write-demo", "label": "Write Demo Persistent File", "kind": "button"},
            {"id": "storage-vfs-snapshot", "label": "Create Snapshot", "kind": "button"},
            {"id": "storage-vfs-verify", "label": "Verify Journal", "kind": "button"},
        ],
        "scientific-formula-lab": [
            {"id": "scientific-formula-catalog", "label": "Browse Hardware Formulas", "kind": "button"},
            {"id": "scientific-formula-plan", "label": "Generate Formula Upgrade Plan", "kind": "button"},
            {"id": "scientific-formula-report", "label": "Inspect Formula Runtime", "kind": "button"},
        ],
        "corpus-integration-lab": [
            {"id": "corpus-report", "label": "Inspect Corpus Index", "kind": "button"},
            {"id": "corpus-index", "label": "Rebuild Corpus Index", "kind": "button"},
            {"id": "formula-discover", "label": "Synthesize Formula Programs", "kind": "button"},
        ],
        "system-observatory": [
            {"id": "router-next", "label": "Run Smart Next Action", "kind": "button"},
            {"id": "perf-tune", "label": "Apply Perf Tune", "kind": "button"},
            {"id": "mesh-consensus", "label": "Sync Peer State", "kind": "button"},
        ],
    }
    return actions.get(active_view, actions["mission-control"])


def _base_snapshot(workspace: Path) -> dict:
    return {
        "state": load_state(workspace),
        "tilemind": TileMindFS(workspace).report(),
        "ram": OmegaRAM(workspace).report(),
        "perf": PerformanceGovernor(workspace).report(),
        "gpu": detect_gpu_runtime(workspace),
        "mesh": mesh_status(workspace),
        "mesh_daemon": mesh_daemon_snapshot(workspace),
        "mesh_cache": mesh_cache_report(workspace),
        "journal": mission_journal_report(workspace),
        "events": read_events(workspace, limit=20),
        "autonomy": autonomy_report(workspace),
        "worker": worker_report(workspace),
        "ui": load_ui_state(workspace),
        "router": route_report(workspace),
        "research_fusion": research_fusion_report(workspace),
        "formula_programs": formula_program_report(workspace),
        "ai_dev": ai_dev_report(workspace),
        "ollama": ollama_idea_report(workspace),
        "supervisor": supervisor_report(workspace),
        "triple_kernel": triple_kernel_status(workspace),
        "desktop": desktop_catalog(workspace),
        "native_desktop": native_desktop_blueprint(workspace),
        "native_packages": native_package_catalog(workspace),
        "native_userspace": userspace_alpha_report(workspace),
        "native_vfs": vfs_mount_report(workspace),
        "storage_vfs": storage_mount_report(workspace),
        "package_manifest": package_manifest(workspace),
        "scientific_formulas": scientific_formula_report(workspace),
        "corpus_index": corpus_deep_index_report(workspace),
    }


def _event_detail_key(kind: str, payload: dict) -> str | None:
    identifier = payload.get("id") or payload.get("session_id")
    if "worker" in kind and identifier:
        return f"worker:{identifier}"
    if "autonomy" in kind and identifier:
        return f"autonomy:{identifier}"
    mission_id = payload.get("mission_id") or payload.get("checkpoint_mission_id")
    if "mission" in kind and mission_id:
        return f"mission:{mission_id}"
    return None


def _timeline(snapshot: dict) -> list[dict[str, str | None]]:
    items: list[dict[str, str]] = []
    for event in reversed(snapshot["journal"].get("recent_events", [])[-6:]):
        mission_id = str(event.get("mission_id", ""))
        items.append(
            {
                "kind": str(event.get("kind", "mission-event")),
                "title": mission_id or str(event.get("kind", "mission")),
                "ts": str(event.get("ts", "")),
                "detail_key": f"mission:{mission_id}" if mission_id else None,
            }
        )
    for event in reversed(snapshot["events"][-6:]):
        kind = str(event.get("kind", "event"))
        payload = event.get("payload", {})
        title = str(payload.get("title") or payload.get("id") or payload.get("checkpoint_mission_id") or kind)
        items.append(
            {
                "kind": kind,
                "title": title,
                "ts": str(event.get("ts", "")),
                "detail_key": _event_detail_key(kind, payload),
            }
        )
    for action in snapshot["ui"].get("actions", [])[-4:]:
        items.append(
            {
                "kind": "ui_action",
                "title": str(action.get("action_id", "ui-action")),
                "ts": str(action.get("ts", "")),
                "detail_key": None,
            }
        )
    items.sort(key=lambda item: item["ts"], reverse=True)
    return items[:8]


def _detail_panel(snapshot: dict, detail_key: str | None) -> dict[str, object] | None:
    if not detail_key:
        return None
    if ":" not in detail_key:
        return None
    kind, identifier = detail_key.split(":", 1)
    if kind == "worker":
        for item in snapshot["worker"]["recent_done"]:
            if str(item.get("id")) == identifier:
                return {
                    "title": f"Worker Detail :: {item.get('title', identifier)}",
                    "items": [
                        f"mode={item.get('mode', 'unknown')}",
                        f"reflection_score={item.get('reflection_score', 'n/a')}",
                        f"spawned_autonomy={item.get('spawned_autonomy_id', 'none')}",
                        f"mission_bridge={item.get('mission_bridge', {}).get('checkpoint_mission_id', 'none')}",
                    ] + [str(path) for path in item.get("files", [])[:5]],
                }
    if kind == "autonomy":
        for collection in ("recent_done", "queued"):
            for item in snapshot["autonomy"][collection]:
                if str(item.get("id")) == identifier:
                    return {
                        "title": f"Autonomy Detail :: {item.get('title', identifier)}",
                        "items": [
                            f"domain={item.get('domain', 'unknown')}",
                            f"status={item.get('status', 'unknown')}",
                            f"goal={item.get('goal', '')}",
                        ] + [str(path) for path in item.get("files", [])[:4]],
                    }
    if kind == "mission":
        for event in snapshot["journal"].get("recent_events", []):
            if str(event.get("mission_id", "")) == identifier:
                return {
                    "title": f"Mission Detail :: {identifier}",
                    "items": [
                        f"kind={event.get('kind', 'mission-event')}",
                        f"ts={event.get('ts', '')}",
                        f"completed_jobs={event.get('completed_jobs', [])}",
                        f"inherited_completed_jobs={event.get('inherited_completed_jobs', [])}",
                    ],
                }
    return None


def _detail_cards(snapshot: dict, requested: str) -> list[dict[str, object]]:
    last_ui_result = snapshot["ui"].get("last_result") or {}
    cards = {
        "mission-control": [
            {
                "title": "Last UI Action",
                "items": [
                    f"action={last_ui_result.get('action_id', 'none')}",
                    f"status={last_ui_result.get('status', 'none')}",
                    f"summary={last_ui_result.get('summary', 'none')}",
                ],
            },
            {
                "title": "Action Router",
                "items": [
                    f"next={snapshot['router']['next_action']['id']}",
                    f"safety={snapshot['router']['next_action']['safety']}",
                    f"confidence={snapshot['router']['next_action']['confidence']}",
                    f"executed={snapshot['router']['memory']['metrics'].get('executed', 0)}",
                    f"loops={snapshot['router']['memory']['metrics'].get('loops', 0)}",
                    f"reason={snapshot['router']['next_action']['reason']}",
                ],
            },
            {
                "title": "Mission Timeline",
                "items": [f"{item['ts']} :: {item['kind']} :: {item['title']}" for item in _timeline(snapshot)] or ["none"],
            },
            {
                "title": "Peer State",
                "items": [f"{node['name']} :: {node.get('availability', 'unknown')}" for node in snapshot["mesh"]["nodes"][:6]] or ["none"],
            },
        ],
        "worker-studio": [
            {
                "title": "Recent Worker Files",
                "items": snapshot["worker"]["recent_done"][-1].get("files", []) if snapshot["worker"]["recent_done"] else ["none"],
            },
            {
                "title": "Mission Bridges",
                "items": [
                    str(item.get("mission_bridge", {}).get("checkpoint_mission_id", "no-bridge"))
                    for item in snapshot["worker"]["recent_done"][-3:]
                ] or ["none"],
            },
        ],
        "autonomy-lab": [
            {
                "title": "Queued Lanes",
                "items": [item["title"] for item in snapshot["autonomy"]["queued"][:8]] or ["none"],
            },
            {
                "title": "Recent Outputs",
                "items": [
                    path
                    for item in snapshot["autonomy"]["recent_done"][-2:]
                    for path in item.get("files", [])[:2]
                ] or ["none"],
            },
        ],
        "research-desk": [
            {
                "title": "Research Fusion",
                "items": [
                    f"runs={snapshot['research_fusion']['metrics'].get('runs', 0)}",
                    f"pdfs={snapshot['research_fusion']['metrics'].get('pdfs_ingested', 0)}",
                    f"formula_files={snapshot['research_fusion']['metrics'].get('formula_files_sampled', 0)}",
                    f"last={snapshot['research_fusion'].get('last_run', {}).get('report_path', 'none') if snapshot['research_fusion'].get('last_run') else 'none'}",
                ],
            },
            {
                "title": "Formula Programs",
                "items": [
                    f"programs={snapshot['formula_programs'].get('program_count', 0)}",
                    f"discoveries={snapshot['formula_programs']['metrics'].get('discoveries', 0)}",
                    f"installed={snapshot['formula_programs']['metrics'].get('installed', 0)}",
                    f"evolutions={snapshot['formula_programs']['metrics'].get('evolutions', 0)}",
                    f"last_domains={','.join(snapshot['formula_programs'].get('last_discovery', {}).get('domains', [])[:4]) if snapshot['formula_programs'].get('last_discovery') else 'none'}",
                ],
            },
            {
                "title": "Hypothesis Trail",
                "items": [item["title"] for item in snapshot["autonomy"]["recent_done"] if item.get("domain") == "research"] or ["none"],
            },
            {
                "title": "Signal Timeline",
                "items": [f"{item['ts']} :: {item['kind']}" for item in _timeline(snapshot)[:6]] or ["none"],
            },
        ],
        "automation-forge": [
            {
                "title": "Forge Queue",
                "items": [item["title"] for item in snapshot["autonomy"]["queued"] if item.get("domain") == "automation"] or ["none"],
            },
            {
                "title": "Relay Stream",
                "items": [f"{item['kind']} :: {item.get('ts', '')}" for item in snapshot["mesh"]["relays"][-8:]] or ["none"],
            },
        ],
        "ai-dev-forge": [
            {
                "title": "AI Dev Catalog",
                "items": [
                    f"total={snapshot['ai_dev'].get('catalog_total', 0)}",
                    f"categories={snapshot['ai_dev'].get('category_count', 0)}",
                    f"local_only={snapshot['ai_dev'].get('local_only')}",
                    f"safe_default={snapshot['ai_dev'].get('safe_default')}",
                ],
            },
            {
                "title": "Latest Plan",
                "items": [
                    f"reports={snapshot['ai_dev'].get('report_count', 0)}",
                    f"latest={snapshot['ai_dev'].get('latest_report') or 'none'}",
                ],
            },
            {
                "title": "Upgrade Domains",
                "items": [f"{key}={value}" for key, value in list(snapshot["ai_dev"].get("category_counts", {}).items())[:10]]
                or ["none"],
            },
        ],
        "ollama-chat-forge": [
            {
                "title": "Local Chat Engine",
                "items": [
                    f"available={snapshot['ollama'].get('status', {}).get('available')}",
                    f"endpoint={snapshot['ollama'].get('status', {}).get('endpoint')}",
                    f"models={len(snapshot['ollama'].get('status', {}).get('models', []))}",
                ],
            },
            {
                "title": "Idea Plans",
                "items": [
                    f"reports={snapshot['ollama'].get('report_count', 0)}",
                    f"latest={snapshot['ollama'].get('latest_report') or 'none'}",
                ],
            },
            {
                "title": "Build Flow",
                "items": [
                    "chatbot -> JSON plan",
                    "plan -> worker sessions",
                    "milestones -> autonomy workloads",
                    "verification -> doctor + tests + router",
                ],
            },
        ],
        "supervisor-forge": [
            {
                "title": "Clean Growth",
                "items": [
                    f"mode={snapshot['supervisor'].get('current_mode')}",
                    f"index={snapshot['supervisor'].get('clean_growth_index')}",
                    f"selected={snapshot['supervisor'].get('selected_count')}",
                    f"risk={snapshot['supervisor'].get('risk_level')}",
                ],
            },
            {
                "title": "Supervisor Memory",
                "items": [
                    f"reports={snapshot['supervisor'].get('report_count')}",
                    f"latest={snapshot['supervisor'].get('latest_report') or 'none'}",
                ],
            },
            {
                "title": "Better Than Linear Agent Flow",
                "items": [
                    "budget expansion before queueing",
                    "balance code/research/automation/ecosystem",
                    "archive every strategic decision",
                    "prefer stabilize when risk rises",
                ],
            },
        ],
        "triple-kernel-forge": [
            {
                "title": "Triangle Runtime",
                "items": [
                    f"catalog={snapshot['triple_kernel'].get('catalog_total')}",
                    f"builds={snapshot['triple_kernel'].get('build_count')}",
                    f"syntheses={snapshot['triple_kernel'].get('metrics', {}).get('syntheses')}",
                ],
            },
            {
                "title": "Recent Build",
                "items": [
                    f"id={(snapshot['triple_kernel'].get('runtime', {}).get('last_build') or {}).get('id') or 'none'}",
                    f"report={(snapshot['triple_kernel'].get('runtime', {}).get('last_build') or {}).get('report_path') or 'none'}",
                ],
            },
            {
                "title": "Topology Promise",
                "items": [
                    "matter handles hardware and timing",
                    "mind turns ideas into verified programs",
                    "mesh keeps growth coherent across services and memory",
                ],
            },
        ],
        "fractal-desktop": [
            {
                "title": "Persistent Overlay",
                "items": [
                    f"active={snapshot['desktop'].get('active_overlay')}",
                    f"overlays={len(snapshot['desktop'].get('overlays', []))}",
                    f"overlay_cycles={snapshot['desktop'].get('metrics', {}).get('overlay_cycles', 0)}",
                    f"mode={snapshot['desktop'].get('os_mode')}",
                ],
            },
            {
                "title": "Desktop Revolutions",
                "items": [
                    f"{item['id']} :: {item['title']}"
                    for item in snapshot["desktop"].get("revolutions", [])[:6]
                ] or ["none"],
            },
            {
                "title": "Always-On Signals",
                "items": [
                    f"{item['id']} :: {','.join(item.get('signals', []))}"
                    for item in snapshot["desktop"].get("overlays", [])[:6]
                ] or ["none"],
            },
        ],
        "native-os-installer": [
            {
                "title": "Truth Gate",
                "items": [
                    f"boots_now={snapshot['native_desktop']['truth']['boots_now']}",
                    f"classic_daily_driver_now={snapshot['native_desktop']['truth']['classic_daily_driver_now']}",
                    f"persistent_self_install_now={snapshot['native_desktop']['truth']['persistent_self_install_now']}",
                    f"reason={snapshot['native_desktop']['truth']['reason']}",
                ],
            },
            {
                "title": "Desktop Components",
                "items": [
                    f"{item['id']} :: {item['status']}"
                    for item in snapshot["native_desktop"].get("components", [])[:10]
                ] or ["none"],
            },
            {
                "title": "Package Domains",
                "items": [
                    f"{item['id']} :: {item['kind']} :: {item['phase']}"
                    for item in snapshot["native_packages"].get("packages", [])[:10]
                ] or ["none"],
            },
        ],
        "userspace-vfs-alpha": [
            {
                "title": "Userspace Truth",
                "items": [
                    f"runtime_vfs_usable={snapshot['native_userspace']['truth']['runtime_vfs_usable']}",
                    f"kernel_vfs_probe={snapshot['native_userspace']['truth']['native_kernel_vfs_probe']}",
                    f"persistent_native_disk_write={snapshot['native_userspace']['truth']['persistent_native_disk_write']}",
                    f"reason={snapshot['native_userspace']['truth']['reason']}",
                ],
            },
            {
                "title": "VFS Mounts",
                "items": [
                    f"{item['path']} :: {item['source']} :: {item['mode']}"
                    for item in snapshot["native_vfs"].get("mounts", [])
                ] or ["none"],
            },
            {
                "title": "Package Manifest",
                "items": [
                    f"{item['id']} :: {item['phase']}"
                    for item in snapshot["package_manifest"].get("packages", [])[:10]
                ] or ["none"],
            },
        ],
        "storage-vfs-stage22": [
            {
                "title": "Persistent Mount",
                "items": [
                    f"stage={snapshot['storage_vfs'].get('stage')}",
                    f"mount={snapshot['storage_vfs']['mount']['path']}::{snapshot['storage_vfs']['mount']['mode']}",
                    f"files={snapshot['storage_vfs'].get('file_count')}",
                    f"bytes={snapshot['storage_vfs'].get('byte_count')}",
                ],
            },
            {
                "title": "Journal And Rollback",
                "items": [
                    f"journal={snapshot['storage_vfs'].get('journal_count')}",
                    f"snapshots={snapshot['storage_vfs'].get('snapshot_count')}",
                    f"rollbacks={snapshot['storage_vfs'].get('metrics', {}).get('rollbacks')}",
                    f"verifications={snapshot['storage_vfs'].get('metrics', {}).get('verifications')}",
                ],
            },
            {
                "title": "Recent Persistent Files",
                "items": [
                    f"{item['path']} :: {item['size']} bytes :: {item['sha256'][:12]}"
                    for item in snapshot["storage_vfs"].get("files", [])[-8:]
                ] or ["none"],
            },
        ],
        "scientific-formula-lab": [
            {
                "title": "Formula Runtime",
                "items": [
                    f"catalog={snapshot['scientific_formulas'].get('catalog_total', 0)}",
                    f"targets={snapshot['scientific_formulas'].get('target_count', 0)}",
                    f"variants={snapshot['scientific_formulas'].get('variant_count', 0)}",
                    f"plans={snapshot['scientific_formulas'].get('metrics', {}).get('plans', 0)}",
                    f"corpus_coverage={(snapshot['scientific_formulas'].get('corpus_index') or {}).get('coverage_ratio', 0)}",
                ],
            },
            {
                "title": "Last Formula Plan",
                "items": [
                    f"target={(snapshot['scientific_formulas'].get('last_plan') or {}).get('target', 'none')}",
                    f"selected={(snapshot['scientific_formulas'].get('last_plan') or {}).get('selected_count', 0)}",
                    f"report={(snapshot['scientific_formulas'].get('last_plan') or {}).get('report_path', 'none')}",
                ],
            },
            {
                "title": "Hardware Sectors",
                "items": [
                    "storage-density",
                    "ram-morphology",
                    "thermal-throughput",
                    "proof-promotion",
                    "future-branching",
                ],
            },
        ],
        "corpus-integration-lab": [
            {
                "title": "Corpus Coverage",
                "items": [
                    f"indexed={(snapshot['corpus_index'].get('last_index') or {}).get('indexed_formula_files', 0)}",
                    f"total={(snapshot['corpus_index'].get('last_index') or {}).get('total_formula_files', 0)}",
                    f"coverage={(snapshot['corpus_index'].get('last_index') or {}).get('coverage_ratio', 0)}",
                    f"formulas={(snapshot['corpus_index'].get('last_index') or {}).get('formula_count', 0)}",
                ],
            },
            {
                "title": "Latest Corpus Report",
                "items": [
                    f"report={(snapshot['corpus_index'].get('last_index') or {}).get('report_path', 'none')}",
                    f"tile={(snapshot['corpus_index'].get('last_index') or {}).get('tile_manifest', 'none')}",
                ],
            },
            {
                "title": "Integration Routes",
                "items": [
                    "cube_compression_gpu -> TileMindFS + storage density",
                    "energy_perf -> thermal throughput",
                    "scheduler_control -> regime scheduling",
                    "proof_validation -> ProofState promotion",
                    "agent_orchestration -> Foundry workers",
                ],
            },
        ],
        "system-observatory": [
            {
                "title": "Smart Next Actions",
                "items": [
                    f"{item['id']} :: {item['safety']} :: {item['reason']}"
                    for item in snapshot["router"]["recommendations"]
                ],
            },
            {
                "title": "Router Memory",
                "items": [
                    f"{item.get('ts', '')} :: {item.get('status', 'unknown')} :: {item.get('action_id', 'route')}"
                    for item in reversed(snapshot["router"]["memory"].get("recent_routes", []))
                ] or ["none"],
            },
            {
                "title": "Telemetry Timeline",
                "items": [f"{item['ts']} :: {item['kind']}" for item in _timeline(snapshot)[:6]] or ["none"],
            },
            {
                "title": "Resource State",
                "items": [
                    f"hot_entries={snapshot['ram']['metrics']['hot_entries']}",
                    f"warm_entries={snapshot['ram']['metrics']['warm_entries']}",
                    f"tile_manifests={snapshot['tilemind']['manifest_count']}",
                ],
            },
        ],
        "timeline-center": [
            {
                "title": "UI Action Memory",
                "items": [
                    f"{item.get('ts', '')} :: {item.get('status', 'unknown')} :: {item.get('action_id', 'action')}"
                    for item in reversed(snapshot["ui"].get("actions", [])[-8:])
                ] or ["none"],
            },
            {
                "title": "Mission Timeline",
                "items": [f"{item['ts']} :: {item['kind']} :: {item['title']}" for item in _timeline(snapshot)] or ["none"],
            },
            {
                "title": "Worker Summary",
                "items": [f"{item.get('id')} :: {item.get('title')}" for item in snapshot["worker"]["recent_done"][:5]] or ["none"],
            },
            {
                "title": "Autonomy Summary",
                "items": [f"{item.get('id')} :: {item.get('title')}" for item in snapshot["autonomy"]["queued"][:5]] or ["none"],
            },
        ],
    }
    return cards.get(requested, [])


def build_ui_model(workspace: Path, active_view: str = "mission-control", detail_key: str | None = None) -> dict:
    snapshot = _base_snapshot(workspace)
    requested = active_view if any(view["id"] == active_view for view in UI_VIEWS) else "mission-control"

    view_payloads = {
        "mission-control": {
            "headline": "Pilotage distribue du runtime et des missions.",
            "accent": "cluster",
            "quick_actions": [
                "python -m omega_tile_os mission-control --workspace .\\workspace",
                "python -m omega_tile_os mesh-status --workspace .\\workspace",
                "python -m omega_tile_os mesh-heartbeat --workspace .\\workspace",
            ],
            "focus": [
                f"mission_count={snapshot['journal']['mission_count']}",
                f"mesh_nodes={snapshot['mesh']['node_count']}",
                f"outbox_states={','.join(item['status'] for item in snapshot['mesh']['outbox'][:3]) or 'none'}",
            ],
            "sections": [
                {
                    "title": "Cluster",
                    "items": [
                        f"nodes={snapshot['mesh']['node_count']}",
                        f"inbox={len(snapshot['mesh']['inbox'])}",
                        f"outbox={len(snapshot['mesh']['outbox'])}",
                        f"missions={snapshot['journal']['mission_count']}",
                    ],
                },
                {
                    "title": "Daemon",
                    "items": [
                        f"status={snapshot['mesh_daemon']['status']}",
                        f"cycle_count={snapshot['mesh_daemon']['cycle_count']}",
                        f"cache_entries={snapshot['mesh_cache']['entry_count']}",
                    ],
                },
            ],
        },
        "worker-studio": {
            "headline": "Sessions IA, plans, reviews et transitions vers les missions.",
            "accent": "worker",
            "quick_actions": [
                "python -m omega_tile_os worker-report --workspace .\\workspace",
                "python -m omega_tile_os worker-run --workspace .\\workspace --max-items 1",
                "python -m omega_tile_os worker-mission --workspace .\\workspace --session-id <id> --route dynamic",
            ],
            "focus": [
                f"submitted={snapshot['worker']['metrics'].get('submitted', 0)}",
                f"processed={snapshot['worker']['metrics'].get('processed', 0)}",
                f"reflections={snapshot['worker']['metrics'].get('reflections', 0)}",
            ],
            "sections": [
                {
                    "title": "Worker",
                    "items": [
                        f"submitted={snapshot['worker']['metrics'].get('submitted', 0)}",
                        f"processed={snapshot['worker']['metrics'].get('processed', 0)}",
                        f"queued={snapshot['worker']['status_counts'].get('queued', 0)}",
                    ],
                },
                {
                    "title": "Recent Sessions",
                    "items": [item["title"] for item in snapshot["worker"]["recent_done"]] or ["none"],
                },
            ],
        },
        "autonomy-lab": {
            "headline": "Lanes de travail autonomes et cycles d evolution.",
            "accent": "autonomy",
            "quick_actions": [
                "python -m omega_tile_os autonomy-report --workspace .\\workspace",
                "python -m omega_tile_os autonomy-run --workspace .\\workspace --max-items 2",
                "python -m omega_tile_os autonomy-evolve --workspace .\\workspace",
            ],
            "focus": [
                f"submitted={snapshot['autonomy']['metrics'].get('submitted', 0)}",
                f"processed={snapshot['autonomy']['metrics'].get('processed', 0)}",
                f"queued={snapshot['autonomy']['status_counts'].get('queued', 0)}",
            ],
            "sections": [
                {
                    "title": "Autonomy",
                    "items": [
                        f"submitted={snapshot['autonomy']['metrics'].get('submitted', 0)}",
                        f"processed={snapshot['autonomy']['metrics'].get('processed', 0)}",
                        f"queued={snapshot['autonomy']['status_counts'].get('queued', 0)}",
                    ],
                },
                {
                    "title": "Domains",
                    "items": [f"{key}={value}" for key, value in snapshot["autonomy"]["domain_counts"].items()] or ["none"],
                },
            ],
        },
        "research-desk": {
            "headline": "Recherche, hypotheses et traces d evidence.",
            "accent": "research",
            "quick_actions": [
                "python -m omega_tile_os formula-discover --workspace .\\workspace --corpus F:\\FractalFormulaCorpus",
                "python -m omega_tile_os formula-simulate --workspace .\\workspace",
                "python -m omega_tile_os formula-evolve --workspace .\\workspace --queue-limit 4",
                "python -m omega_tile_os autonomy-submit --workspace .\\workspace --domain research --title \"Research lane\" --goal \"Formuler une nouvelle piste de recherche.\"",
                "python -m omega_tile_os ui-view --workspace .\\workspace --view research-desk",
            ],
            "focus": [
                f"research_done={len([item for item in snapshot['autonomy']['recent_done'] if item.get('domain') == 'research'])}",
                f"event_signals={len(snapshot['events'])}",
                f"formula_programs={snapshot['formula_programs'].get('program_count', 0)}",
                f"formula_evolutions={snapshot['formula_programs']['metrics'].get('evolutions', 0)}",
            ],
            "sections": [
                {
                    "title": "Formula Programs",
                    "items": [
                        f"{item.get('domain')} :: {item.get('kernel')}"
                        for item in snapshot["formula_programs"].get("recent_programs", [])[-6:]
                    ] or ["none"],
                },
                {
                    "title": "Recent Research",
                    "items": [item["title"] for item in snapshot["autonomy"]["recent_done"] if item.get("domain") == "research"] or ["none"],
                },
                {
                    "title": "Event Signals",
                    "items": [event["kind"] for event in snapshot["events"][:8]] or ["none"],
                },
            ],
        },
        "automation-forge": {
            "headline": "Design, safeguards et observation des automatismes.",
            "accent": "automation",
            "quick_actions": [
                "python -m omega_tile_os autonomy-submit --workspace .\\workspace --domain automation --title \"Automation lane\" --goal \"Construire un pipeline automatise robuste.\"",
                "python -m omega_tile_os mesh-consensus --workspace .\\workspace",
            ],
            "focus": [
                f"automation_queued={len([item for item in snapshot['autonomy']['queued'] if item.get('domain') == 'automation'])}",
                f"relay_events={len(snapshot['mesh']['relays'])}",
            ],
            "sections": [
                {
                    "title": "Automation Lane",
                    "items": [item["title"] for item in snapshot["autonomy"]["queued"] if item.get("domain") == "automation"] or ["none"],
                },
                {
                    "title": "Mesh Activity",
                    "items": [relay["kind"] for relay in snapshot["mesh"]["relays"][-6:]] or ["none"],
                },
            ],
        },
        "ai-dev-forge": {
            "headline": "Forge locale pour transformer l IA en accelerateur de developpement.",
            "accent": "worker",
            "quick_actions": [
                "python -m omega_tile_os ai-dev-catalog --workspace .\\workspace --limit 20",
                "python -m omega_tile_os ai-dev-plan --workspace .\\workspace --focus all --limit 15",
                "python -m omega_tile_os ai-dev-plan --workspace .\\workspace --focus testing --limit 5 --queue",
            ],
            "focus": [
                f"catalog_total={snapshot['ai_dev'].get('catalog_total', 0)}",
                f"reports={snapshot['ai_dev'].get('report_count', 0)}",
                f"local_only={snapshot['ai_dev'].get('local_only')}",
            ],
            "sections": [
                {
                    "title": "Major Improvements",
                    "items": [
                        f"{key}={value}" for key, value in list(snapshot["ai_dev"].get("category_counts", {}).items())[:8]
                    ] or ["none"],
                },
                {
                    "title": "Latest Output",
                    "items": [
                        f"latest_report={snapshot['ai_dev'].get('latest_report') or 'none'}",
                        f"safe_default={snapshot['ai_dev'].get('safe_default')}",
                    ],
                },
            ],
        },
        "ollama-chat-forge": {
            "headline": "Chat local pour concretiser les idees en agents de developpement.",
            "accent": "worker",
            "quick_actions": [
                "python -m omega_tile_os ollama-status --workspace .\\workspace",
                "python -m omega_tile_os ollama-idea --workspace .\\workspace --idea \"Decris ton idee\"",
                "python -m omega_tile_os ollama-idea --workspace .\\workspace --idea \"Decris ton idee\" --queue-agents",
            ],
            "focus": [
                f"ollama_available={snapshot['ollama'].get('status', {}).get('available')}",
                f"idea_reports={snapshot['ollama'].get('report_count', 0)}",
                f"latest={snapshot['ollama'].get('latest_report') or 'none'}",
            ],
            "sections": [
                {
                    "title": "Local Model",
                    "items": [
                        f"endpoint={snapshot['ollama'].get('status', {}).get('endpoint')}",
                        f"recommended_model={snapshot['ollama'].get('status', {}).get('recommended_model')}",
                    ],
                },
                {
                    "title": "Agent Handoff",
                    "items": [
                        "researcher maps the idea",
                        "builder structures code changes",
                        "automator verifies runs",
                        "evolver feeds the next OS upgrade",
                    ],
                },
            ],
        },
        "supervisor-forge": {
            "headline": "Meta-orchestration pour faire grandir FractalOS sans dette explosive.",
            "accent": "cluster",
            "quick_actions": [
                "python -m omega_tile_os supervisor-plan --workspace .\\workspace",
                "python -m omega_tile_os supervisor-run --workspace .\\workspace",
                "python -m omega_tile_os router-simulate --workspace .\\workspace --stop-on-elevated",
            ],
            "focus": [
                f"mode={snapshot['supervisor'].get('current_mode')}",
                f"clean_growth={snapshot['supervisor'].get('clean_growth_index')}",
                f"selected_agents={snapshot['supervisor'].get('selected_count')}",
            ],
            "sections": [
                {
                    "title": "Strategy",
                    "items": [
                        "multi-agent planning",
                        "queue pressure guard",
                        "domain balance",
                        "formula-aware stabilization",
                    ],
                },
                {
                    "title": "Current Decision",
                    "items": [
                        f"risk={snapshot['supervisor'].get('risk_level')}",
                        f"latest_report={snapshot['supervisor'].get('latest_report') or 'none'}",
                    ],
                },
            ],
        },
        "triple-kernel-forge": {
            "headline": "Triangle vivant pour relier noyau reel, intelligence locale et expansion propre.",
            "accent": "cluster",
            "quick_actions": [
                "python -m omega_tile_os triple-kernel-status --workspace .\\workspace",
                "python -m omega_tile_os triple-kernel-plan --workspace .\\workspace --limit 24",
                "python -m omega_tile_os triple-kernel-synthesize --workspace .\\workspace --limit 18 --queue",
            ],
            "focus": [
                f"catalog={snapshot['triple_kernel'].get('catalog_total')}",
                f"builds={snapshot['triple_kernel'].get('build_count')}",
                f"syntheses={snapshot['triple_kernel'].get('metrics', {}).get('syntheses')}",
            ],
            "sections": [
                {
                    "title": "Vertices",
                    "items": [
                        "Matter = hardware, memory, timing",
                        "Mind = plans, formulas, agent proofing",
                        "Mesh = services, storage, clean expansion",
                    ],
                },
                {
                    "title": "Current Runtime",
                    "items": [
                        f"last_build={(snapshot['triple_kernel'].get('runtime', {}).get('last_build') or {}).get('id') or 'none'}",
                        f"queued_followups={snapshot['triple_kernel'].get('metrics', {}).get('queued_followups')}",
                    ],
                },
            ],
        },
        "fractal-desktop": {
            "headline": "Bureau persistant: intention, preuves, energie et agents au-dessus de toutes les apps.",
            "accent": "desktop",
            "quick_actions": [
                "python -m omega_tile_os desktop-overlay --workspace .\\workspace",
                "python -m omega_tile_os desktop-overlay-cycle --workspace .\\workspace",
                "python -m omega_tile_os desktop --workspace .\\workspace",
            ],
            "focus": [
                f"active_overlay={snapshot['desktop'].get('active_overlay')}",
                f"overlays={len(snapshot['desktop'].get('overlays', []))}",
                f"revolutions={len(snapshot['desktop'].get('revolutions', []))}",
            ],
            "sections": [
                {
                    "title": "Overlay Plane",
                    "items": [
                        f"{item['id']} :: {item['persistence']}"
                        for item in snapshot["desktop"].get("overlays", [])
                    ] or ["none"],
                },
                {
                    "title": "Desktop Revolutions",
                    "items": [
                        f"{item['title']} :: {item['impact']}"
                        for item in snapshot["desktop"].get("revolutions", [])[:5]
                    ] or ["none"],
                },
            ],
        },
        "native-os-installer": {
            "headline": "Pont vers un OS utilisable: installation persistante, login, bureau, recherche, fichiers, web et paquets.",
            "accent": "desktop",
            "quick_actions": [
                "python -m omega_tile_os native-os-report --workspace .\\workspace",
                "python -m omega_tile_os native-os-install-plan --workspace .\\workspace --target vm --create-vm-disk",
                "python -m omega_tile_os desktop-login --workspace .\\workspace --role user",
                "python -m omega_tile_os desktop-search --workspace .\\workspace --query package",
                "python -m omega_tile_os desktop-files --workspace .\\workspace",
            ],
            "focus": [
                f"boots_now={snapshot['native_desktop']['truth']['boots_now']}",
                f"daily_driver={snapshot['native_desktop']['truth']['classic_daily_driver_now']}",
                f"components={len(snapshot['native_desktop'].get('components', []))}",
                f"packages={len(snapshot['native_packages'].get('packages', []))}",
            ],
            "sections": [
                {
                    "title": "Classic Surfaces",
                    "items": [
                        "login greeter",
                        "interactive home menu",
                        "global search bar",
                        "TileMind file explorer",
                        "terminal/cmd",
                        "web gateway",
                        "package center",
                        "office and media centers",
                    ],
                },
                {
                    "title": "Fractal Extensions",
                    "items": [
                        "intent overlay",
                        "proof ribbon",
                        "energy strip",
                        "agent orbit",
                        "formula lab",
                        "rollback-safe installer",
                    ],
                },
                {
                    "title": "Native Gates",
                    "items": [
                        "writable storage driver",
                        "native VFS",
                        "ring3 init and sessions",
                        "network stack",
                        "desktop compositor",
                        "signed package manager",
                    ],
                },
            ],
        },
        "userspace-vfs-alpha": {
            "headline": "Premiere matiere utilisateur native: sessions, fichiers RAM, manifests paquets et pont TileMindFS.",
            "accent": "desktop",
            "quick_actions": [
                "python -m omega_tile_os session-start --workspace .\\workspace --role user",
                "python -m omega_tile_os vfs-ls --workspace .\\workspace --path /",
                "python -m omega_tile_os vfs-read --workspace .\\workspace --path /etc/fractalos-release",
                "python -m omega_tile_os vfs-write --workspace .\\workspace --path /home/user/hello.txt --text \"FractalOS alive\"",
                "python -m omega_tile_os package-manifest --workspace .\\workspace",
            ],
            "focus": [
                f"nodes={snapshot['native_userspace'].get('node_count')}",
                f"packages={snapshot['native_userspace'].get('package_count')}",
                f"mounts={len(snapshot['native_vfs'].get('mounts', []))}",
                f"reads={snapshot['native_userspace'].get('metrics', {}).get('reads')}",
                f"writes={snapshot['native_userspace'].get('metrics', {}).get('writes')}",
            ],
            "sections": [
                {
                    "title": "Session Layer",
                    "items": [
                        "guest home",
                        "user home",
                        "admin install policy",
                        "doctor recovery policy",
                    ],
                },
                {
                    "title": "RAM VFS",
                    "items": [
                        "/",
                        "/etc/fractalos-release",
                        "/home/user/README.txt",
                        "/apps/packages.json",
                        "/tiles TileMindFS bridge",
                    ],
                },
                {
                    "title": "Next Native Gate",
                    "items": [
                        "replace RAM VFS with writable storage-backed VFS",
                        "make package manifests signed",
                        "launch init process from userspace table",
                    ],
                },
            ],
        },
        "storage-vfs-stage22": {
            "headline": "Home persistant journalise: chaque fichier devient une trace restaurable, verifiable et archivable.",
            "accent": "desktop",
            "quick_actions": [
                "python -m omega_tile_os storage-vfs-status --workspace .\\workspace",
                "python -m omega_tile_os storage-vfs-write --workspace .\\workspace --path /home/user/stage22.txt --text \"FractalOS persists\"",
                "python -m omega_tile_os storage-vfs-snapshot --workspace .\\workspace --label before-upgrade",
                "python -m omega_tile_os storage-vfs-verify --workspace .\\workspace",
                "python -m omega_tile_os storage-vfs-rollback --workspace .\\workspace --target last-write",
            ],
            "focus": [
                f"files={snapshot['storage_vfs'].get('file_count')}",
                f"journal={snapshot['storage_vfs'].get('journal_count')}",
                f"snapshots={snapshot['storage_vfs'].get('snapshot_count')}",
                f"stage={snapshot['storage_vfs'].get('stage')}",
            ],
            "sections": [
                {
                    "title": "Persistence Contract",
                    "items": [
                        "writes stay under workspace/storage_vfs/root",
                        "each write records before/after hashes",
                        "TileMindFS archives persistent material",
                        "rollback can restore last write or latest snapshot",
                    ],
                },
                {
                    "title": "Scientific Formula",
                    "items": [
                        "PersistenceScore = 0.34*has_files + 0.26*verify_ok + 0.20*journal_density + 0.20*snapshot_density",
                        "promote only if verify_ok and rollback path exists",
                        "native block driver remains the next hardware gate",
                    ],
                },
                {
                    "title": "Stage23 Bridge",
                    "items": [
                        "bind journal to persistent VM disk image",
                        "add MIME registry and file association layer",
                        "make installer replay home/state snapshots after boot",
                    ],
                },
            ],
        },
        "scientific-formula-lab": {
            "headline": "Formules scientifiques bornees pour augmenter stockage utile, debit, stabilite et confiance.",
            "accent": "research",
            "quick_actions": [
                "python -m omega_tile_os scientific-formula-catalog --workspace .\\workspace --limit 20",
                "python -m omega_tile_os scientific-formula-plan --workspace .\\workspace --target storage --limit 8",
                "python -m omega_tile_os scientific-formula-plan --workspace .\\workspace --limit 18 --queue",
            ],
            "focus": [
                f"catalog={snapshot['scientific_formulas'].get('catalog_total', 0)}",
                f"targets={snapshot['scientific_formulas'].get('target_count', 0)}",
                f"plans={snapshot['scientific_formulas'].get('metrics', {}).get('plans', 0)}",
            ],
            "sections": [
                {
                    "title": "Formula Families",
                    "items": [
                        "D_eff = (1 + H_dup + H_delta) * C_codec * A_heat",
                        "Q_safe = cores * S_stability * sqrt(T_headroom)",
                        "P_promote = min(T_tests, D_doctor, R_rollback) * C_confidence",
                    ],
                },
                {
                    "title": "Safety Contract",
                    "items": [
                        "reversible manifests",
                        "thermal and memory guards",
                        "doctor/tests before promotion",
                        "speculative branches cannot mutate stable state",
                    ],
                },
            ],
        },
        "corpus-integration-lab": {
            "headline": "Index complet du corpus formule et integration vers stockage, RAM, scheduler, preuves et agents.",
            "accent": "research",
            "quick_actions": [
                "python -m omega_tile_os corpus-report --workspace .\\workspace",
                "python -m omega_tile_os corpus-index --workspace .\\workspace --corpus F:\\FractalFormulaCorpus",
                "python -m omega_tile_os formula-discover --workspace .\\workspace --corpus F:\\FractalFormulaCorpus --max-formula-files 128 --max-programs 10",
            ],
            "focus": [
                f"indexed={(snapshot['corpus_index'].get('last_index') or {}).get('indexed_formula_files', 0)}",
                f"coverage={(snapshot['corpus_index'].get('last_index') or {}).get('coverage_ratio', 0)}",
                f"formula_blocks={(snapshot['corpus_index'].get('last_index') or {}).get('formula_count', 0)}",
            ],
            "sections": [
                {
                    "title": "Corpus State",
                    "items": [
                        f"total_files={(snapshot['corpus_index'].get('last_index') or {}).get('total_formula_files', 0)}",
                        f"indexed_files={(snapshot['corpus_index'].get('last_index') or {}).get('indexed_formula_files', 0)}",
                        f"equations={(snapshot['corpus_index'].get('last_index') or {}).get('equation_count', 0)}",
                    ],
                },
                {
                    "title": "OS Targets",
                    "items": [
                        "TileMindFS density",
                        "OmegaRAM morphology",
                        "Regime scheduler",
                        "ProofState promotion",
                        "Agent Foundry",
                    ],
                },
            ],
        },
        "system-observatory": {
            "headline": "Telemetrie profonde du systeme.",
            "accent": "observatory",
            "quick_actions": [
                "python -m omega_tile_os perf-report --workspace .\\workspace",
                "python -m omega_tile_os memory-report --workspace .\\workspace",
                "python -m omega_tile_os devices --workspace .\\workspace",
            ],
            "focus": [
                f"stability={snapshot['perf']['formulas']['stability_index']:.3f}",
                f"risk={snapshot['perf']['recommendations']['risk_level']}",
                f"gpu_native={'yes' if snapshot['gpu']['native_runtime_available'] else 'no'}",
            ],
            "sections": [
                {
                    "title": "Performance",
                    "items": [
                        f"stability={snapshot['perf']['formulas']['stability_index']:.3f}",
                        f"risk={snapshot['perf']['recommendations']['risk_level']}",
                        f"concurrency={snapshot['perf']['recommendations']['recommended_concurrency']}",
                    ],
                },
                {
                    "title": "Resources",
                    "items": [
                        f"tile_manifests={snapshot['tilemind']['manifest_count']}",
                        f"hot_ram={snapshot['ram']['metrics']['hot_entries']}",
                        f"gpu_native={'yes' if snapshot['gpu']['native_runtime_available'] else 'no'}",
                    ],
                },
            ],
        },
        "timeline-center": {
            "headline": "Flux vivant des missions, workers et lanes.",
            "accent": "cluster",
            "quick_actions": [
                "python -m omega_tile_os ui-view --workspace .\\workspace --view timeline-center",
                "python -m omega_tile_os mission-journal --workspace .\\workspace",
                "python -m omega_tile_os events --workspace .\\workspace --limit 20",
            ],
            "focus": [
                f"timeline_items={len(_timeline(snapshot))}",
                f"worker_done={snapshot['worker']['status_counts'].get('done', 0)}",
                f"autonomy_queued={snapshot['autonomy']['status_counts'].get('queued', 0)}",
            ],
            "sections": [
                {
                    "title": "Recent Flow",
                    "items": [f"{item['kind']} :: {item['title']}" for item in _timeline(snapshot)] or ["none"],
                },
                {
                    "title": "Watchpoints",
                    "items": [
                        f"mesh_nodes={snapshot['mesh']['node_count']}",
                        f"mission_count={snapshot['journal']['mission_count']}",
                        f"worker_processed={snapshot['worker']['metrics'].get('processed', 0)}",
                    ],
                },
            ],
        },
    }

    return {
        "active_view": requested,
        "views": available_views(),
        "view": view_payloads[requested],
        "actions": _view_actions(requested),
        "detail_cards": _detail_cards(snapshot, requested),
        "detail_panel": _detail_panel(snapshot, detail_key),
        "timeline": _timeline(snapshot),
        "recommended_views": [view for view in available_views() if view["id"] != requested][:3],
        "snapshot": {
            "node": snapshot["state"]["node"],
            "metrics": snapshot["state"]["metrics"],
            "mesh": snapshot["mesh"],
            "autonomy": snapshot["autonomy"],
            "worker": snapshot["worker"],
            "ui": {
                "metrics": snapshot["ui"].get("metrics", {}),
                "last_result": snapshot["ui"].get("last_result"),
                "recent_actions": snapshot["ui"].get("actions", [])[-8:],
            },
            "router": snapshot["router"],
            "research_fusion": snapshot["research_fusion"],
            "formula_programs": snapshot["formula_programs"],
            "ai_dev": snapshot["ai_dev"],
            "ollama": snapshot["ollama"],
            "supervisor": snapshot["supervisor"],
            "desktop": snapshot["desktop"],
            "native_desktop": snapshot["native_desktop"],
            "native_packages": snapshot["native_packages"],
            "native_userspace": snapshot["native_userspace"],
            "native_vfs": snapshot["native_vfs"],
            "storage_vfs": snapshot["storage_vfs"],
            "package_manifest": snapshot["package_manifest"],
            "scientific_formulas": snapshot["scientific_formulas"],
            "corpus_index": snapshot["corpus_index"],
            "perf": {
                "mode": snapshot["perf"]["mode"],
                "formulas": snapshot["perf"]["formulas"],
                "recommendations": snapshot["perf"]["recommendations"],
            },
        },
    }
