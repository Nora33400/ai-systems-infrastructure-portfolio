from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


DESKTOP_APPS = [
    {
        "id": "terminal",
        "title": "Fractal Terminal",
        "kind": "shell",
        "description": "Commande unifiee pour piloter FractalOS comme un environnement utilisateur.",
        "commands": ["help", "status", "apps", "services", "search <query>", "files", "packages", "login <role>", "open <app>", "run <service>"],
    },
    {
        "id": "welcome",
        "title": "Living Welcome",
        "kind": "onboarding",
        "description": "Menu d'accueil interactif avec premiers pas, etat doctor, tips overlay et actions recommandees.",
        "commands": ["onboarding-pack", "doctor", "classic-os-report"],
    },
    {
        "id": "start-menu",
        "title": "Fractal Start Menu",
        "kind": "launcher",
        "description": "Accueil façon OS moderne: applications, documents, paquets, agents et intentions recentes.",
        "commands": ["apps", "search <query>", "open <app>", "run <service>"],
    },
    {
        "id": "global-search",
        "title": "Fractal Search",
        "kind": "search",
        "description": "Recherche globale dans apps, services, overlays, paquets et surfaces TileMindFS.",
        "commands": ["search <query>"],
    },
    {
        "id": "tile-explorer",
        "title": "TileMind Explorer",
        "kind": "files",
        "description": "Explorateur fichier/tile pour manifests, objets dedupliques, compression et reconstruction.",
        "commands": ["files", "tile-report", "tile-reconstruct"],
    },
    {
        "id": "web-gateway",
        "title": "Web Gateway",
        "kind": "internet",
        "description": "Surface internet cible: navigateur isole, DNS/TLS, favoris et recherche web quand la pile reseau native arrive.",
        "commands": ["network-status", "open-browser-domain"],
    },
    {
        "id": "package-center",
        "title": "Package Center",
        "kind": "packages",
        "description": "Installateur de paquets signe avec rollback, runtimes Python/Rust/Java et domaines applicatifs.",
        "commands": ["packages", "install <package>", "native-os-app-catalog"],
    },
    {
        "id": "office-desk",
        "title": "Office Desk",
        "kind": "office",
        "description": "Cible bureautique: txt, documents, PDF, tableurs, exports et resume IA.",
        "commands": ["open-document", "summarize-document", "export-pdf"],
    },
    {
        "id": "media-center",
        "title": "Media Center",
        "kind": "media",
        "description": "Cible media: images, audio, video, codecs et lecture sous budget energie.",
        "commands": ["open-media", "inspect-codecs", "energy-playback"],
    },
    {
        "id": "settings",
        "title": "Settings + Doctor",
        "kind": "system",
        "description": "Parametres, sessions, recovery, mises a jour, rollback et politiques FractalOS.",
        "commands": ["doctor", "restart-recovery", "native-os-install-plan"],
    },
    {
        "id": "code-studio",
        "title": "Code Studio",
        "kind": "dev",
        "description": "Entree vers workers IA, AI Dev Forge, tests et patch planning.",
        "commands": ["worker-report", "ai-dev-plan", "supervisor-plan"],
    },
    {
        "id": "research-lab",
        "title": "Research Lab",
        "kind": "research",
        "description": "Recherche locale, corpus, PDF, formules et hypotheses.",
        "commands": ["research-fusion-report", "formula-programs", "formula-advice"],
    },
    {
        "id": "automation-center",
        "title": "Automation Center",
        "kind": "automation",
        "description": "Automations, lanes, router et workflows controles.",
        "commands": ["autonomy-report", "router-report", "router-simulate"],
    },
    {
        "id": "system-monitor",
        "title": "System Monitor",
        "kind": "system",
        "description": "Performance, RAM, GPU, doctor et healer.",
        "commands": ["doctor", "perf-report", "memory-report", "devices"],
    },
    {
        "id": "mesh-center",
        "title": "Mesh Center",
        "kind": "network",
        "description": "Noeuds, missions distribuees et federation locale.",
        "commands": ["mesh-status", "mesh-cache", "mission-journal"],
    },
    {
        "id": "install-center",
        "title": "Install Center",
        "kind": "installer",
        "description": "Plan d'installation persistante VM/machine avec slots A/B, etat, home et recovery.",
        "commands": ["native-os-install-plan", "build-iso", "boot-check"],
    },
]

DESKTOP_SERVICES = [
    {
        "id": "doctor-watch",
        "title": "Doctor Watch",
        "description": "Surveille les checks de sante et recommande les reparations.",
        "safe_command": "python -m omega_tile_os doctor --workspace .\\workspace",
        "risk": "read-only",
    },
    {
        "id": "router-guard",
        "title": "Router Guard",
        "description": "Simule la prochaine action sans muter le workspace.",
        "safe_command": "python -m omega_tile_os router-simulate --workspace .\\workspace --stop-on-elevated",
        "risk": "read-only",
    },
    {
        "id": "supervisor-brain",
        "title": "Supervisor Brain",
        "description": "Calcule si l'OS doit grandir, stabiliser ou proteger.",
        "safe_command": "python -m omega_tile_os supervisor-plan --workspace .\\workspace",
        "risk": "read-only",
    },
    {
        "id": "memory-index",
        "title": "Memory Index",
        "description": "Expose OmegaRAM et TileMindFS comme memoire utilisateur.",
        "safe_command": "python -m omega_tile_os memory-report --workspace .\\workspace",
        "risk": "read-only",
    },
    {
        "id": "native-install-planner",
        "title": "Native Install Planner",
        "description": "Prepare profil VM persistant, slots disque et script QEMU sans ecriture dangereuse sur machine physique.",
        "safe_command": "python -m omega_tile_os native-os-install-plan --workspace .\\workspace --target vm",
        "risk": "read-only",
    },
    {
        "id": "package-index",
        "title": "Package Index",
        "description": "Expose runtimes, navigateur, bureautique, media, IA locale et compatibilite comme paquets cibles.",
        "safe_command": "python -m omega_tile_os native-os-app-catalog --workspace .\\workspace",
        "risk": "read-only",
    },
    {
        "id": "desktop-search-index",
        "title": "Desktop Search Index",
        "description": "Indexe les apps, overlays, services et paquets pour la barre de recherche.",
        "safe_command": "python -m omega_tile_os desktop-search --workspace .\\workspace --query fractal",
        "risk": "read-only",
    },
]

DESKTOP_OVERLAYS = [
    {
        "id": "intent-lens",
        "title": "Intent Lens",
        "role": "Capture les objectifs utilisateur au-dessus de toutes les apps.",
        "persistence": "always-on",
        "signals": ["active_goal", "risk", "next_action"],
    },
    {
        "id": "proof-ribbon",
        "title": "Proof Ribbon",
        "role": "Expose preuves, tests, doctor et niveau de confiance des actions.",
        "persistence": "always-on",
        "signals": ["doctor", "tests", "attestation"],
    },
    {
        "id": "energy-strip",
        "title": "Energy Strip",
        "role": "Rend visibles chaleur, budget, RAM, queue pressure et perf.",
        "persistence": "adaptive",
        "signals": ["stability", "concurrency", "memory"],
    },
    {
        "id": "agent-orbit",
        "title": "Agent Orbit",
        "role": "Montre workers, autonomie, Ollama et superviseur comme une flotte locale.",
        "persistence": "adaptive",
        "signals": ["workers", "autonomy", "supervisor"],
    },
    {
        "id": "command-veil",
        "title": "Command Veil",
        "role": "Permet de piloter l OS sans quitter l application courante.",
        "persistence": "summonable",
        "signals": ["shell", "apps", "services"],
    },
    {
        "id": "search-ribbon",
        "title": "Search Ribbon",
        "role": "Rend la recherche persistante au-dessus du bureau, des fichiers, des agents et des paquets.",
        "persistence": "summonable",
        "signals": ["apps", "tiles", "packages"],
    },
    {
        "id": "session-shield",
        "title": "Session Shield",
        "role": "Montre le role courant, les permissions et les changements qui exigent admin/doctor.",
        "persistence": "adaptive",
        "signals": ["role", "permission", "rollback"],
    },
]

DESKTOP_REVOLUTIONS = [
    {
        "id": "screen-as-control-plane",
        "title": "Screen as Control Plane",
        "impact": "L ecran n est plus une pile de fenetres, mais une couche de pilotage persistante.",
    },
    {
        "id": "apps-as-organisms",
        "title": "Apps as Organisms",
        "impact": "Les apps exposent energie, memoire, evolution, preuve et relation aux agents.",
    },
    {
        "id": "intent-first-desktop",
        "title": "Intent First Desktop",
        "impact": "Les commandes partent d objectifs et produisent plans, agents, tests et promotions.",
    },
    {
        "id": "proof-visible-ui",
        "title": "Proof Visible UI",
        "impact": "Chaque action importante porte sa confiance, son origine et son etat de verification.",
    },
    {
        "id": "local-industrial-cell",
        "title": "Local Industrial Cell",
        "impact": "Le PC devient atelier logiciel local avec foundry, workers, recherche et archivage.",
    },
    {
        "id": "classic-os-plus-fractal",
        "title": "Classic OS Plus Fractal",
        "impact": "Les fonctions Windows/Linux attendues deviennent des surfaces classiques augmentees par preuve, agents, recherche et rollback.",
    },
    {
        "id": "installable-living-system",
        "title": "Installable Living System",
        "impact": "Installation persistante par slots, home TileMindFS, packages signes et doctor de redemarrage.",
    },
]

DESKTOP_SESSION_ROLES = {
    "guest": {"risk": "low", "can_install": False, "can_patch": False},
    "user": {"risk": "medium", "can_install": False, "can_patch": False},
    "admin": {"risk": "high", "can_install": True, "can_patch": False},
    "doctor": {"risk": "protective", "can_install": False, "can_patch": True},
}


def _desktop_state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    return workspace / "state" / "desktop_runtime.json"


def _load_desktop_state(workspace: Path) -> dict[str, Any]:
    path = _desktop_state_path(workspace)
    if not path.exists():
        state = {
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
        path.write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")
        return state
    state = json.loads(path.read_text(encoding="utf-8"))
    state.setdefault("overlay_cycles", [])
    state.setdefault("active_overlay", "intent-lens")
    metrics = state.setdefault("metrics", {})
    metrics.setdefault("commands", 0)
    metrics.setdefault("opened_apps", 0)
    metrics.setdefault("service_runs", 0)
    metrics.setdefault("overlay_cycles", 0)
    return state


def _save_desktop_state(workspace: Path, state: dict[str, Any]) -> None:
    _desktop_state_path(workspace).write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def desktop_catalog(workspace: Path) -> dict[str, Any]:
    state = _load_desktop_state(workspace)
    perf = PerformanceGovernor(workspace).report()
    active_overlay = str(state.get("active_overlay") or "intent-lens")
    return {
        "apps": DESKTOP_APPS,
        "services": DESKTOP_SERVICES,
        "overlays": DESKTOP_OVERLAYS,
        "revolutions": DESKTOP_REVOLUTIONS,
        "active_overlay": active_overlay,
        "metrics": state.get("metrics", {}),
        "active_session": state.get("active_session"),
        "opened_recent": state.get("opened_apps", [])[-8:],
        "service_recent": state.get("service_runs", [])[-8:],
        "overlay_recent": state.get("overlay_cycles", [])[-8:],
        "os_mode": "fractal-desktop-preview",
        "host_requirements": ["FractalOS control plane", "Python runtime", "optional Ollama"],
        "kernel_boundary": "The control plane previews the persistent desktop; the bare-metal line now owns a desktop-plane subsystem.",
        "risk_level": perf["recommendations"].get("risk_level"),
    }


def desktop_overlay_status(workspace: Path) -> dict[str, Any]:
    catalog = desktop_catalog(workspace)
    active = next((item for item in DESKTOP_OVERLAYS if item["id"] == catalog["active_overlay"]), DESKTOP_OVERLAYS[0])
    return {
        "active": active,
        "overlays": DESKTOP_OVERLAYS,
        "revolutions": DESKTOP_REVOLUTIONS,
        "metrics": catalog.get("metrics", {}),
        "risk_level": catalog.get("risk_level"),
    }


def desktop_cycle_overlay(workspace: Path) -> dict[str, Any]:
    state = _load_desktop_state(workspace)
    current = str(state.get("active_overlay") or DESKTOP_OVERLAYS[0]["id"])
    ids = [item["id"] for item in DESKTOP_OVERLAYS]
    next_index = (ids.index(current) + 1) % len(ids) if current in ids else 0
    active_overlay = ids[next_index]
    state["active_overlay"] = active_overlay
    cycle = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "active_overlay": active_overlay,
    }
    state.setdefault("overlay_cycles", []).append(cycle)
    state["overlay_cycles"] = state["overlay_cycles"][-80:]
    metrics = state.setdefault("metrics", {})
    metrics["overlay_cycles"] = int(metrics.get("overlay_cycles", 0)) + 1
    _save_desktop_state(workspace, state)
    append_event(workspace, "desktop_overlay_cycled", {"active_overlay": active_overlay})
    return {"cycled": True, "active_overlay": active_overlay, "cycle": cycle}


def desktop_open_app(workspace: Path, app_id: str) -> dict[str, Any]:
    app = next((item for item in DESKTOP_APPS if item["id"] == app_id), None)
    if not app:
        return {"opened": False, "reason": "app_not_found", "app_id": app_id}
    state = _load_desktop_state(workspace)
    event = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "app_id": app_id,
        "title": app["title"],
        "commands": app.get("commands", []),
    }
    state.setdefault("opened_apps", []).append(event)
    state["opened_apps"] = state["opened_apps"][-80:]
    metrics = state.setdefault("metrics", {})
    metrics["opened_apps"] = int(metrics.get("opened_apps", 0)) + 1
    _save_desktop_state(workspace, state)
    append_event(workspace, "desktop_app_opened", {"app_id": app_id, "title": app["title"]})
    return {"opened": True, "app": app, "session": event}


def desktop_run_service(workspace: Path, service_id: str) -> dict[str, Any]:
    service = next((item for item in DESKTOP_SERVICES if item["id"] == service_id), None)
    if not service:
        return {"started": False, "reason": "service_not_found", "service_id": service_id}
    state = _load_desktop_state(workspace)
    run = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "service_id": service_id,
        "title": service["title"],
        "status": "planned",
        "safe_command": service["safe_command"],
        "risk": service["risk"],
    }
    state.setdefault("service_runs", []).append(run)
    state["service_runs"] = state["service_runs"][-120:]
    metrics = state.setdefault("metrics", {})
    metrics["service_runs"] = int(metrics.get("service_runs", 0)) + 1
    _save_desktop_state(workspace, state)
    append_event(workspace, "desktop_service_planned", {"service_id": service_id, "title": service["title"]})
    return {"started": True, "service": service, "run": run}


def desktop_search(workspace: Path, query: str) -> dict[str, Any]:
    normalized = query.strip().lower()
    catalog = desktop_catalog(workspace)
    results: list[dict[str, Any]] = []
    for kind, collection in [
        ("app", catalog["apps"]),
        ("service", catalog["services"]),
        ("overlay", catalog["overlays"]),
        ("revolution", catalog["revolutions"]),
    ]:
        for item in collection:
            haystack = json.dumps(item, ensure_ascii=True).lower()
            if not normalized or normalized in haystack:
                results.append(
                    {
                        "kind": kind,
                        "id": item.get("id", item.get("title", kind)),
                        "title": item.get("title", item.get("id", kind)),
                        "summary": item.get("description") or item.get("role") or item.get("impact", ""),
                    }
                )
    tile_report = TileMindFS(workspace).report()
    if not normalized or "tile" in normalized or "file" in normalized or "explorer" in normalized:
        results.append(
            {
                "kind": "tilemindfs",
                "id": "tilemindfs-report",
                "title": "TileMindFS",
                "summary": f"{tile_report['manifest_count']} manifests, {tile_report['unique_tile_objects']} unique tiles",
            }
        )
    append_event(workspace, "desktop_search", {"query": query, "results": len(results)})
    return {"query": query, "results": results[:30], "total": len(results)}


def desktop_tile_explorer(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    store = TileMindFS(workspace)
    report = store.report()
    manifests = []
    for path in sorted(store.manifests_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:12]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(
            {
                "manifest_id": payload.get("manifest_id"),
                "source_name": payload.get("source_name"),
                "raw_size": payload.get("raw_size"),
                "tile_count": payload.get("tile_count"),
                "reused_tiles": payload.get("reused_tiles"),
            }
        )
    append_event(workspace, "desktop_tile_explorer", {"manifests": len(manifests)})
    return {
        "mode": "tile_explorer",
        "report": report,
        "recent_manifests": manifests,
        "capabilities": [
            "deduplicated tile inventory",
            "manifest reconstruction",
            "compression ratio visibility",
            "future native VFS bridge",
        ],
    }


def desktop_package_center(workspace: Path) -> dict[str, Any]:
    # Local import keeps the desktop runtime independent from package planning.
    from .native_desktop_stack import native_package_catalog

    catalog = native_package_catalog(workspace)
    append_event(workspace, "desktop_package_center", {"packages": len(catalog["packages"])})
    return {
        "mode": "package_center",
        "packages": catalog["packages"],
        "by_kind": catalog["by_kind"],
        "policy": catalog["install_policy"],
    }


def desktop_login(workspace: Path, role: str) -> dict[str, Any]:
    normalized = role.strip().lower()
    if normalized not in DESKTOP_SESSION_ROLES:
        return {"logged_in": False, "reason": "unknown_role", "roles": sorted(DESKTOP_SESSION_ROLES)}
    state = _load_desktop_state(workspace)
    session = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "role": normalized,
        "policy": DESKTOP_SESSION_ROLES[normalized],
    }
    state.setdefault("sessions", []).append(session)
    state["sessions"] = state["sessions"][-80:]
    state["active_session"] = session
    _save_desktop_state(workspace, state)
    append_event(workspace, "desktop_login", {"role": normalized, "session_id": session["id"]})
    return {"logged_in": True, "session": session}


def desktop_shell(workspace: Path, command: str) -> dict[str, Any]:
    normalized = command.strip()
    state = _load_desktop_state(workspace)
    metrics = state.setdefault("metrics", {})
    metrics["commands"] = int(metrics.get("commands", 0)) + 1
    _save_desktop_state(workspace, state)

    if normalized in {"help", "?"}:
        result = {
            "type": "help",
            "commands": [
                "help",
                "status",
                "apps",
                "services",
                "search <query>",
                "files",
                "packages",
                "login <guest|user|admin|doctor>",
                "overlay",
                "overlay cycle",
                "revolutions",
                "open <app-id>",
                "run <service-id>",
            ],
        }
    elif normalized == "status":
        result = {"type": "status", "catalog": desktop_catalog(workspace)}
    elif normalized == "apps":
        result = {"type": "apps", "apps": DESKTOP_APPS}
    elif normalized == "services":
        result = {"type": "services", "services": DESKTOP_SERVICES}
    elif normalized.startswith("search "):
        result = {"type": "search", "result": desktop_search(workspace, normalized.split(" ", 1)[1].strip())}
    elif normalized in {"files", "tiles", "explorer"}:
        result = {"type": "files", "result": desktop_tile_explorer(workspace)}
    elif normalized in {"packages", "package-center"}:
        result = {"type": "packages", "result": desktop_package_center(workspace)}
    elif normalized.startswith("login "):
        result = {"type": "login", "result": desktop_login(workspace, normalized.split(" ", 1)[1].strip())}
    elif normalized in {"overlay", "overlays"}:
        result = {"type": "overlay", "result": desktop_overlay_status(workspace)}
    elif normalized == "overlay cycle":
        result = {"type": "overlay-cycle", "result": desktop_cycle_overlay(workspace)}
    elif normalized == "revolutions":
        result = {"type": "revolutions", "revolutions": DESKTOP_REVOLUTIONS}
    elif normalized.startswith("open "):
        result = {"type": "open", "result": desktop_open_app(workspace, normalized.split(" ", 1)[1].strip())}
    elif normalized.startswith("run "):
        result = {"type": "service", "result": desktop_run_service(workspace, normalized.split(" ", 1)[1].strip())}
    else:
        result = {"type": "error", "error": "unknown_desktop_command", "command": normalized}

    append_event(workspace, "desktop_shell_command", {"command": normalized, "type": result["type"]})
    return result


def desktop_snapshot(workspace: Path) -> dict[str, Any]:
    catalog = desktop_catalog(workspace)
    report_path = _write_desktop_report(workspace, catalog)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"desktop_runtime::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="desktop_runtime",
    )
    return {
        "catalog": catalog,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }


def _write_desktop_report(workspace: Path, catalog: dict[str, Any]) -> Path:
    root = workspace / "desktop"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"DESKTOP_{len(list(root.glob('DESKTOP_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Desktop Runtime",
        "",
        f"- Generated at: {utc_now()}",
        f"- Mode: {catalog['os_mode']}",
        f"- Risk level: {catalog.get('risk_level')}",
        "",
        "## Boundary",
        str(catalog["kernel_boundary"]),
        "",
        "## Apps",
    ]
    for app in catalog["apps"]:
        lines.append(f"- {app['id']} :: {app['title']} :: {app['description']}")
    lines.extend(["", "## Services"])
    for service in catalog["services"]:
        lines.append(f"- {service['id']} :: {service['title']} :: {service['safe_command']}")
    lines.extend(["", "## Persistent Overlays"])
    for overlay in catalog["overlays"]:
        lines.append(f"- {overlay['id']} :: {overlay['title']} :: {overlay['role']}")
    lines.extend(["", "## Revolutions"])
    for item in catalog["revolutions"]:
        lines.append(f"- {item['id']} :: {item['title']} :: {item['impact']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
