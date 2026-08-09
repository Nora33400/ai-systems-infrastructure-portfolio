from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

STANDARD_FILES = [
    "README.md",
    "INSTALLATION.md",
    "CONFIGURATION.md",
    "FIRST_USE.md",
    "ADVANCED_USAGE.md",
    "BEST_PRACTICES.md",
    "INTERNAL_ARCHITECTURE.md",
    "API.md",
    "FAQ.md",
    "TROUBLESHOOTING.md",
    "EXAMPLES.md",
    "CHECKLIST.md",
]

TOPICS: list[dict[str, Any]] = [
    {
        "folder": "00_START_HERE",
        "title": "Start Here",
        "status": "Available",
        "purpose": "Point d'entree pour comprendre l'Alpha FractalOS/AIONE et savoir quels guides lire.",
        "available": ["README racine", "index documentaire", "statut Alpha", "carte projet"],
        "partial": ["documentation ancienne et nouvelle coexistent encore"],
        "todo": ["lier progressivement tous les nouveaux modules a cette arborescence"],
        "references": ["README.md", "DOC_INDEX.md", "ALPHA_STATUS.md", "PROJECT_MAP.md", "AGENTS.md"],
        "commands": ["Get-Content README.md", "Get-Content DOC_INDEX.md", "git status --short"],
    },
    {
        "folder": "01_INSTALLATION",
        "title": "Installation",
        "status": "Available",
        "purpose": "Installer et verifier les dependances locales du prototype Windows, Python, Node et .NET.",
        "available": ["scripts de validation", "lanceur fractalos", "projet WPF buildable"],
        "partial": ["installateur utilisateur final non signe"],
        "todo": ["creer un installateur release signe quand l'Alpha sera figee"],
        "references": ["scripts/validate_all.ps1", "scripts/validate_hud.ps1", "scripts/validate_python.ps1", "scripts/fractalos.ps1", "apps/windows_hud/AioneHud.csproj"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_all.ps1", "dotnet build apps/windows_hud/AioneHud.csproj -c Release"],
    },
    {
        "folder": "02_FIRST_START",
        "title": "First Start",
        "status": "Available",
        "purpose": "Premier lancement, guide Alpha, Showcase et modes publics/developpeur.",
        "available": ["Alpha Guide", "Alpha Showcase", "First launch state", "Safe Recovery"],
        "partial": ["parcours encore a tester sur plusieurs tailles d'ecran"],
        "todo": ["ajouter captures et tests manuels par profil utilisateur"],
        "references": ["apps/windows_hud/AlphaExperienceService.cs", "apps/windows_hud/AlphaGuideWindow.cs", "apps/windows_hud/AlphaShowcaseWindow.cs", "apps/windows_hud/AlphaModeService.cs", "DEMO.md"],
        "commands": ["fractalos", "dotnet run --project apps/windows_hud/AioneHud.csproj -c Release -- --ux-self-test"],
    },
    {
        "folder": "03_HUD",
        "title": "HUD",
        "status": "Available",
        "purpose": "Fenetre HUD principale, panneaux, sidebar, focus HUD/3D et flux utilisateur.",
        "available": ["OverlayWindow", "Sidebar", "Control Center", "fenetres dockables", "clear/pin HUD"],
        "partial": ["ergonomie finale encore iterative"],
        "todo": ["ajouter captures annotees et parcours par tache"],
        "references": ["apps/windows_hud/App.xaml.cs", "apps/windows_hud/OverlayWindow.cs", "apps/windows_hud/SidebarWindow.cs", "apps/windows_hud/ControlCenterWindow.cs", "apps/windows_hud/HudCloseBehaviorService.cs"],
        "commands": ["dotnet run --project apps/windows_hud/AioneHud.csproj -c Release"],
    },
    {
        "folder": "04_FORGE_IA",
        "title": "Forge IA",
        "status": "Partial",
        "purpose": "Runtime IA historique AIONE/MMR, couches de recherche et evolution vers agents locaux.",
        "available": ["tests AIONE", "aione_forge", "MMR", "runtime continu"],
        "partial": ["forge produit/recherche et HUD encore separes"],
        "todo": ["unifier Forge IA, Continuous Runtime et Agent Bridge dans une UI claire"],
        "references": ["aione_forge", "tests/test_aione_forge.py", "tests/test_aione_mmr.py", "fractal_dev_runtime/runtime.py", "docs/continuous-development-runtime-architecture.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_python.ps1"],
    },
    {
        "folder": "05_OPENWEBUI",
        "title": "OpenWebUI",
        "status": "Partial",
        "purpose": "Utiliser OpenWebUI comme interface de conversation supervisee vers les runtimes locaux.",
        "available": ["scripts start-openwebui", "OpenAPI runtime continu", "routes message/queue/creation"],
        "partial": ["OpenWebUI doit etre installe/configure localement par l'utilisateur"],
        "todo": ["ajouter un profil OpenWebUI importable avec outils limites"],
        "references": ["scripts/start-openwebui.ps1", "scripts/start-openwebui.sh", "fractal_dev_runtime/api.py", "docs/openwebui-mobile-access.md", "docs/agent-bridge/OPENWEBUI.md"],
        "commands": ["python -m fractal_dev_runtime --json openapi", "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-openwebui.ps1"],
    },
    {
        "folder": "06_MOBILE",
        "title": "Mobile",
        "status": "Available",
        "purpose": "Acces mobile local, Safari iPhone, Tailscale, pairing et controle distant prudent.",
        "available": ["Fractal Remote", "pairing 6 chiffres", "Tailscale docs", "routes mobiles agents/runtime"],
        "partial": ["QR/TLS final encore a renforcer"],
        "todo": ["ajouter QR encode reel et certificats locaux optionnels"],
        "references": ["apps/windows_hud/FractalRemoteControlService.cs", "apps/windows_hud/FractalRemoteWindow.cs", "docs/remote/FRACTAL_REMOTE.md", "docs/tailscale-private-access.md", "scripts/tailnet_status.ps1"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tailnet_status.ps1"],
    },
    {
        "folder": "07_RUNTIME",
        "title": "Runtime",
        "status": "Available",
        "purpose": "Runtime local, runner, daemon logique, et runtime continu persistant.",
        "available": ["RuntimeRunnerService", "SystemRuntimeServices", "ContinuousDevRuntime", "API locale"],
        "partial": ["daemon OS separe non livre"],
        "todo": ["service Windows optionnel quand la securite sera figee"],
        "references": ["apps/windows_hud/RuntimeRunnerService.cs", "apps/windows_hud/SystemRuntimeServices.cs", "fractal_dev_runtime/runtime.py", "fractal_dev_runtime/api.py", "RUNTIME.md"],
        "commands": ["python -m fractal_dev_runtime --json status", "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-runtime.ps1"],
    },
    {
        "folder": "08_WORKFLOW",
        "title": "Workflow",
        "status": "Available",
        "purpose": "Flux de developpement continu, backlog, priorites, approvals et validations.",
        "available": ["inbox idees", "priorite explicable", "scheduler prudent", "approvals", "validation scripts"],
        "partial": ["modification du depot utilisateur reste volontairement encadree"],
        "todo": ["brancher worktrees Git pour modifications reelles multi-agents"],
        "references": ["fractal_dev_runtime/runtime.py", "scripts/autonomy_plan.py", "scripts/autonomy_run.ps1", "CONTRIBUTING.md", "AGENTS.md"],
        "commands": ["python -m fractal_dev_runtime --json run-cycle --max-steps 1"],
    },
    {
        "folder": "09_MEMORY",
        "title": "Memory",
        "status": "Available",
        "purpose": "Memoire cyclique, compaction contexte et restauration de resumes.",
        "available": ["memory_items", "memory_summaries", "restore_memory", "docs cyclic-agent"],
        "partial": ["memoire IA locale non encore reliee a tous les agents externes"],
        "todo": ["ajouter recherche semantique locale et retention configurable"],
        "references": ["fractal_dev_runtime/runtime.py", "docs/cyclic-agent-memory.md", "docs/context-compaction.md", "apps/windows_hud/MemoryWindow.cs"],
        "commands": ["python -m fractal_dev_runtime --json memory-status"],
    },
    {
        "folder": "10_GPU",
        "title": "GPU",
        "status": "Partial",
        "purpose": "Detection GPU, repartition modeles, limites RAM/VRAM et profils runtime.",
        "available": ["nvidia-smi detection", "config GPU0/GPU1", "docs dual GPU", "performance window"],
        "partial": ["pinning reel des modeles Ollama par GPU depend de l'environnement"],
        "todo": ["tester profils RTX 3060/4060 avec modeles reels"],
        "references": ["fractal_dev_runtime/runtime.py", "docs/dual-gpu-agent-runtime.md", "apps/windows_hud/PerformanceWindow.cs", "scripts/runtime-diagnostics.ps1"],
        "commands": ["nvidia-smi", "python -m fractal_dev_runtime --json health"],
    },
    {
        "folder": "11_WIDGETS",
        "title": "Widgets",
        "status": "Available",
        "purpose": "Creation, configuration, presets, layout et bindings des widgets.",
        "available": ["WidgetPresetRegistry", "WidgetLayoutService", "WidgetConfigurationRegistry", "Creation Studio widgets"],
        "partial": ["editeur graphique complet encore progressif"],
        "todo": ["connecter les widgets Creation Studio a tous les panneaux HUD"],
        "references": ["apps/windows_hud/WidgetPresetRegistry.cs", "apps/windows_hud/WidgetLayoutService.cs", "apps/windows_hud/WidgetConfigurationRegistry.cs", "fractal_creation_studio/studio.py", "docs/widget-designer.md"],
        "commands": ["python -m fractal_creation_studio scenario --json"],
    },
    {
        "folder": "12_WINDOWS",
        "title": "Windows",
        "status": "Available",
        "purpose": "Fenetres HUD, spatial panels, dock, pin, persistence et publication.",
        "available": ["SpatialPanelWindow", "HudWindowBuilderWindow", "SpaceWindowManager", "Creation Studio Window model"],
        "partial": ["import/export graphique final encore a brancher"],
        "todo": ["publier les .fractalinterface directement en fenetres WPF editables"],
        "references": ["apps/windows_hud/HudWindowBuilderWindow.cs", "apps/windows_hud/SpaceWindowManagerWindow.cs", "apps/windows_hud/SpaceWindowService.cs", "fractal_creation_studio/studio.py", "docs/window-designer.md"],
        "commands": ["python -m fractal_creation_studio create-project Demo --json"],
    },
    {
        "folder": "13_MODULES",
        "title": "Modules",
        "status": "Available",
        "purpose": "Module Manager, templates, permissions, hosting et modules Creation Studio.",
        "available": ["ModuleManagerService", "ModuleCreatorWindow", "ModuleTemplateService", "ModuleWorkspaceStore"],
        "partial": ["execution module externe limitee par sandbox Alpha"],
        "todo": ["stabiliser contrat module executable signe"],
        "references": ["apps/windows_hud/ModuleManagerService.cs", "apps/windows_hud/ModuleCreatorWindow.cs", "apps/windows_hud/ModuleTemplateService.cs", "apps/windows_hud/ModuleWorkspaceStore.cs", "MODULE_MANAGER.md"],
        "commands": ["dotnet run --project apps/windows_hud/AioneHud.csproj -c Release -- --self-test"],
    },
    {
        "folder": "14_INTERFACE_2D",
        "title": "Interface 2D",
        "status": "Available",
        "purpose": "Design 2D HUD, themes, styles, surfaces, inspecteur et preview.",
        "available": ["StyleInspectorWindow", "ThemeManager", "SurfaceLayoutEditor", "Creation Studio styles"],
        "partial": ["preview runtime non encore rendu pixel-perfect WPF"],
        "todo": ["rendu visuel preview live et snapshots d'ecran"],
        "references": ["apps/windows_hud/StyleInspectorWindow.cs", "apps/windows_hud/ThemeManager.cs", "apps/windows_hud/SurfaceLayoutEditor.cs", "fractal_creation_studio/studio.py", "docs/theme-and-style-system.md"],
        "commands": ["python -m fractal_creation_studio scenario --json"],
    },
    {
        "folder": "15_INTERFACE_3D",
        "title": "Interface 3D",
        "status": "Available",
        "purpose": "Surfaces spatiales, viewport 3D, panneaux 3D et binding HUD/spatial.",
        "available": ["SpatialSceneViewport", "SpatialSurfaceService", "SpatialPanelWindow", "HudSpatialLayerService"],
        "partial": ["tests visuels multi-resolution encore manuels"],
        "todo": ["ajouter captures Playwright/bitmap pour scenes 3D si surface web disponible"],
        "references": ["apps/windows_hud/SpatialSceneViewport.cs", "apps/windows_hud/SpatialSurfaceService.cs", "apps/windows_hud/SpatialPanelWindow.cs", "apps/windows_hud/HudSpatialLayerService.cs", "docs/hud-spatial-binding.md"],
        "commands": ["dotnet run --project apps/windows_hud/AioneHud.csproj -c Release -- --ux-self-test"],
    },
    {
        "folder": "16_OBJECTS_3D",
        "title": "Objects 3D",
        "status": "Available",
        "purpose": "Catalogue, placement, inspection, import, transforms, blueprints et ressources 3D.",
        "available": ["EnvironmentObjectManagerService", "ObjectCatalogWindow", "ObjectInspectorWindow", "AssetImportPipeline", "Creation Studio Object3D"],
        "partial": ["PBR complet, animations importees et physique mesh restent limites"],
        "todo": ["ajouter parseurs riches et cache previews assets"],
        "references": ["apps/windows_hud/EnvironmentObjectManagerService.cs", "apps/windows_hud/ObjectCatalogWindow.cs", "apps/windows_hud/ObjectInspectorWindow.cs", "apps/windows_hud/AssetImportPipeline.cs", "docs/object-3d-editor.md"],
        "commands": ["python -m fractal_creation_studio scenario --json"],
    },
    {
        "folder": "17_INTERACTION",
        "title": "Interaction",
        "status": "Available",
        "purpose": "Focus souris, ReClick, selection, zones d'interaction et adressage de fonctions.",
        "available": ["InteractionManagerService", "ReClickEngineService", "SelectionManager", "InteractionZone model"],
        "partial": ["scripting runtime volontairement restreint"],
        "todo": ["editeur visuel d'evenements complet et debugger UI"],
        "references": ["apps/windows_hud/InteractionManagerService.cs", "apps/windows_hud/ReClickEngineService.cs", "apps/windows_hud/SelectionManager.cs", "fractal_creation_studio/studio.py", "docs/function-addressing.md"],
        "commands": ["python -m fractal_creation_studio scenario --json"],
    },
    {
        "folder": "18_PLUGINS",
        "title": "Plugins",
        "status": "Available",
        "purpose": "Plugins manifest-only, actions explicites, galerie locale et extensions Alpha.",
        "available": ["PluginManagerService", "PluginManagerWindow", "plugins d'exemple", "actions plugins P2"],
        "partial": ["code plugin arbitraire bloque en Alpha"],
        "todo": ["signature, sandbox forte, marketplace distante"],
        "references": ["apps/windows_hud/PluginManagerService.cs", "apps/windows_hud/PluginManagerWindow.cs", "plugins", "PLUGIN_GUIDE.md", "docs/ALPHA_P2_EXTENSIBILITY.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha_check.ps1"],
    },
    {
        "folder": "19_NETWORK",
        "title": "Network",
        "status": "Partial",
        "purpose": "Remote local, Tailscale, communaute P3, sessions et publication locale.",
        "available": ["Fractal Remote", "P3 local-only", "NetworkSpaceService", "tailnet scripts"],
        "partial": ["pas de cloud reel ni collaboration reseau temps reel"],
        "todo": ["TLS local, auth device robuste, federation future"],
        "references": ["apps/windows_hud/FractalRemoteControlService.cs", "apps/windows_hud/NetworkSpaceService.cs", "apps/windows_hud/AlphaP3NetworkCommunityService.cs", "docs/remote/FRACTAL_REMOTE.md", "docs/ALPHA_P3_NETWORK_COMMUNITY.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tailnet_status.ps1"],
    },
    {
        "folder": "20_SECURITY",
        "title": "Security",
        "status": "Available",
        "purpose": "Modes Alpha, permissions, approbations, secrets, sandbox et exposition reseau prudente.",
        "available": ["AlphaModeService", "ModulePermissionService", "Agent approvals", "Remote permissions"],
        "partial": ["audit externe et hardening production non faits"],
        "todo": ["model threat complet, secrets vault, TLS, signature plugins"],
        "references": ["SECURITY.md", "apps/windows_hud/AlphaModeService.cs", "apps/windows_hud/ModulePermissionService.cs", "docs/security-and-approvals.md", "docs/tool-security.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha_check.ps1"],
    },
    {
        "folder": "21_OPTIMIZATION",
        "title": "Optimization",
        "status": "Partial",
        "purpose": "Performance HUD, runtime, GPU, memoire et cout de rendu preview.",
        "available": ["PerformanceWindow", "diagnostics Alpha", "tool performance samples", "limits runtime"],
        "partial": ["profiling profond pas automatise"],
        "todo": ["captures FPS reels, traces ETW optionnelles, seuils par machine"],
        "references": ["apps/windows_hud/PerformanceWindow.cs", "apps/windows_hud/AlphaDiagnosticsService.cs", "fractal_creation_studio/studio.py", "docs/tool-performance-optimizer.md", "scripts/runtime-diagnostics.ps1"],
        "commands": ["python -m fractal_dev_runtime --json health"],
    },
    {
        "folder": "22_BACKUP",
        "title": "Backup",
        "status": "Available",
        "purpose": "Sauvegarde locale, snapshots, restoration runtime et hygiene Git.",
        "available": ["runtime backup/restore", "WorkspaceUndoManager", "Creation Studio snapshots", "scripts backup-runtime"],
        "partial": ["restauration destructive toujours manuelle/validee"],
        "todo": ["UI compare/restore pour snapshots Creation Studio"],
        "references": ["scripts/backup-runtime.ps1", "scripts/restore-runtime.ps1", "apps/windows_hud/WorkspaceUndoManager.cs", "fractal_creation_studio/studio.py", "GIT_CLEANUP_PLAN.md"],
        "commands": ["python -m fractal_dev_runtime backup --json"],
    },
    {
        "folder": "23_DEVELOPMENT",
        "title": "Development",
        "status": "Available",
        "purpose": "Contribuer au code, tester, respecter AGENTS et maintenir docs/code synchronises.",
        "available": ["AGENTS.md", "tests Python", "self-tests HUD", "validate_all"],
        "partial": ["CI distant non documente comme source de verite"],
        "todo": ["mettre en place hooks docs-as-code et checks de liens"],
        "references": ["AGENTS.md", "CONTRIBUTING.md", "scripts/validate_all.ps1", "tests", "apps/windows_hud/App.xaml.cs"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_all.ps1", "git diff --check"],
    },
    {
        "folder": "24_API",
        "title": "API",
        "status": "Available",
        "purpose": "API locale runtime, OpenAPI, routes agents/creation/tools et integration OpenWebUI.",
        "available": ["ContinuousDevApi", "OpenAPI JSON", "routes creation/tools/message"],
        "partial": ["WebSocket pas generalise dans toutes les surfaces"],
        "todo": ["schema OpenAPI exhaustif et clients generes"],
        "references": ["fractal_dev_runtime/api.py", "fractal_dev_runtime/runtime.py", "docs/agent-bridge/README.md", "docs/local-agent/openapi-fractal-agent.json"],
        "commands": ["python -m fractal_dev_runtime --json openapi"],
    },
    {
        "folder": "25_AUTONOMOUS_AGENTS",
        "title": "Autonomous Agents",
        "status": "Partial",
        "purpose": "Agents locaux, Codex Desktop observe, OpenCode/Aider/Ollama, autonomie bornee.",
        "available": ["Agent Bridge", "Local Agent Control", "Continuous Runtime", "autonomy scripts"],
        "partial": ["agents externes restent sous approbations et disponibilite outil"],
        "todo": ["worktrees reels par agent, resume robuste multi-session"],
        "references": ["apps/windows_hud/FractalAgentBridgeWindow.cs", "apps/windows_hud/FractalLocalAgentControlService.cs", "docs/agent-bridge/README.md", "docs/local-agent/INSTALLATION.md", "fractal_dev_runtime/runtime.py"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/doctor-fractal-agent-bridge.ps1"],
    },
    {
        "folder": "26_PROJECT_MANAGEMENT",
        "title": "Project Management",
        "status": "Available",
        "purpose": "Roadmap, backlog, priorites, lots P0/P1/P2/P3 et suivi Alpha.",
        "available": ["ROADMAP", "PROJECT_MAP", "Alpha status", "implementation backlog", "priority engine"],
        "partial": ["planning produit encore evolutif"],
        "todo": ["lier chaque item backlog a tests/docs/code"],
        "references": ["ROADMAP.md", "PROJECT_MAP.md", "ALPHA_STATUS.md", "docs/IMPLEMENTATION_BACKLOG.md", "docs/priority-engine.md"],
        "commands": ["Get-Content ROADMAP.md", "python -m fractal_dev_runtime --json status"],
    },
    {
        "folder": "27_BEST_PRACTICES",
        "title": "Best Practices",
        "status": "Available",
        "purpose": "Regles d'evolution, securite, tests, documentation synchronisee et petites iterations.",
        "available": ["AGENTS protocol", "security docs", "validation scripts", "doc structure"],
        "partial": ["lint liens docs pas encore automatise"],
        "todo": ["ajouter check doc drift dans validate_all"],
        "references": ["AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "docs/VALIDATION_CHECKLIST.md", "docs/DOCUMENTATION_SYSTEM.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_all.ps1"],
    },
    {
        "folder": "28_TROUBLESHOOTING",
        "title": "Troubleshooting",
        "status": "Available",
        "purpose": "Diagnostiquer build, runtime, agents, docs, reseau, HUD et tests.",
        "available": ["alpha_check", "project_diagnostic", "runtime diagnostics", "troubleshooting docs"],
        "partial": ["certains rapports racine peuvent fallback vers TEMP selon droits Windows"],
        "todo": ["centraliser tous les rapports dans un dossier writable configure"],
        "references": ["docs/troubleshooting.md", "scripts/alpha_check.ps1", "scripts/project_diagnostic.ps1", "scripts/runtime-diagnostics.ps1", "docs/agent-bridge/TROUBLESHOOTING.md"],
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha_check.ps1"],
    },
    {
        "folder": "29_FAQ",
        "title": "FAQ",
        "status": "Available",
        "purpose": "Questions frequentes utilisateur, developpeur, agent et testeur.",
        "available": ["FAQ par dossier", "guides Alpha", "known issues"],
        "partial": ["FAQ encore issue de l'etat code actuel, pas de retours utilisateurs larges"],
        "todo": ["alimenter depuis feedback Alpha"],
        "references": ["release_alpha/KNOWN_ISSUES.md", "release_alpha/FEEDBACK_TEMPLATE.md", "ALPHA_STATUS.md", "DOC_INDEX.md"],
        "commands": ["Get-Content ALPHA_STATUS.md"],
    },
    {
        "folder": "30_ADVANCED",
        "title": "Advanced",
        "status": "Partial",
        "purpose": "Fonctions avancees : Creation Studio, station TECH, ReClick, agents, runtime cyclique, API.",
        "available": ["Creation Studio V0", "Station TECH", "ReClick", "Agent Bridge", "Continuous Runtime"],
        "partial": ["plusieurs surfaces avancees restent experimentales"],
        "todo": ["stabiliser les flux avances avant promesse Alpha publique"],
        "references": ["fractal_creation_studio/studio.py", "docs/station/SPACE_MERCHANT_STATION.md", "docs/reclick/README.md", "docs/agent-bridge/README.md", "docs/continuous-development-runtime-architecture.md"],
        "commands": ["python -m fractal_creation_studio scenario --json", "python -m fractal_dev_runtime creation-scenario --json"],
    },
]


def bullet(items: list[str]) -> str:
    return "\n".join(f"- `{item}`" if "/" in item or "." in item else f"- {item}" for item in items) or "- Aucun."


def code_block(items: list[str]) -> str:
    if not items:
        return "```text\nAucune commande specifique.\n```"
    return "```powershell\n" + "\n".join(items) + "\n```"


def page_body(topic: dict[str, Any], filename: str) -> str:
    title = topic["title"]
    status = topic["status"]
    purpose = topic["purpose"]
    refs = bullet(topic["references"])
    available = bullet(topic["available"])
    partial = bullet(topic["partial"])
    todo = bullet(topic["todo"])
    commands = code_block(topic["commands"])
    page_title = filename.removesuffix(".md").replace("_", " ").title()

    common = f"""# {title} - {page_title}

Status actuel : {status}

Objectif : {purpose}

Cette page fait partie de la documentation structuree FractalOS/AIONE. Elle doit rester synchronisee avec le code reel. Une fonctionnalite absente doit etre marquee `A implementer` avant toute promesse utilisateur.

## Preuves dans le depot

{refs}

## Disponible maintenant

{available}

## Partiel ou experimental

{partial}

## A implementer ou renforcer

{todo}
"""

    if filename == "README.md":
        return common + f"""
## Ordre de lecture

1. `FIRST_USE.md`
2. `CONFIGURATION.md`
3. `INTERNAL_ARCHITECTURE.md`
4. `CHECKLIST.md`
5. `TROUBLESHOOTING.md`

## Commandes utiles

{commands}
"""
    if filename == "INSTALLATION.md":
        return common + f"""
## Installation ou verification

Ne pas reinstaller un outil qui fonctionne deja. Verifier d'abord les scripts et chemins existants.

{commands}

## Critere de reussite

- Les commandes se terminent sans erreur.
- Le statut documente correspond au code present.
- Les limites restent visibles dans `TROUBLESHOOTING.md`.
"""
    if filename == "CONFIGURATION.md":
        return common + """
## Configuration

Chercher d'abord les fichiers et services existants avant d'ajouter une nouvelle configuration.

Regles :

- preferer les chemins locaux existants ;
- ne pas exposer de service public par defaut ;
- ne pas stocker de secrets en clair ;
- documenter toute variable d'environnement ajoutee ;
- ajouter un reset ou une restauration quand une configuration peut casser l'usage.
"""
    if filename == "FIRST_USE.md":
        return common + f"""
## Premier usage

1. Lire le statut et les limites.
2. Lancer uniquement les commandes de verification.
3. Tester une action simple.
4. Verifier le resultat dans le HUD ou le fichier genere.
5. Noter toute difference dans `TROUBLESHOOTING.md`.

{commands}
"""
    if filename == "ADVANCED_USAGE.md":
        return common + """
## Usage avance

Avancer par petits lots :

- creer un checkpoint ou une sauvegarde ;
- tester sur un projet ou runtime local ;
- lancer les validations ;
- mettre a jour cette documentation ;
- ne promouvoir en `Disponible` qu'apres test.
"""
    if filename == "BEST_PRACTICES.md":
        return common + """
## Bonnes pratiques

- Ne pas documenter comme fini ce qui n'est pas branche au code.
- Preferer un exemple verifiable a une explication vague.
- Ajouter les limites connues pres de la fonctionnalite.
- Relier chaque nouvelle fonctionnalite a une commande ou un test.
- Garder les guides courts, mais multiplier les pages ciblees.
"""
    if filename == "INTERNAL_ARCHITECTURE.md":
        return common + """
## Architecture interne

Les references ci-dessus sont la source de verite. Avant modification :

1. lire les fichiers cites ;
2. verifier les tests existants ;
3. identifier les services reutilisables ;
4. eviter une abstraction nouvelle si un manager existe deja ;
5. documenter l'impact sur API, runtime et UI.
"""
    if filename == "API.md":
        return common + """
## API

Quand une API existe, documenter :

- route ou commande ;
- authentification ;
- entrees ;
- sorties ;
- erreurs ;
- limitations ;
- test associe.

Si aucune API n'existe encore pour ce domaine, marquer `A implementer` et decrire l'interface minimale attendue.
"""
    if filename == "FAQ.md":
        return common + """
## FAQ

### Est-ce disponible ?

Voir `Status actuel` et `Disponible maintenant`.

### Puis-je l'utiliser en production ?

Non. Le projet est encore Alpha locale.

### Que faire si une fonction est absente ?

La marquer `A implementer`, proposer une architecture, implementer, tester, puis mettre a jour ce dossier.
"""
    if filename == "TROUBLESHOOTING.md":
        return common + f"""
## Diagnostic

Commencer par les commandes verifiables :

{commands}

## Informations a collecter

- commande lancee ;
- sortie d'erreur ;
- statut Git ;
- fichiers modifies ;
- test qui echoue ;
- limite deja documentee ou nouvelle.
"""
    if filename == "EXAMPLES.md":
        return common + f"""
## Exemples

Exemple minimal a verifier :

{commands}

Ajouter ici les scenarios concrets au fil des implementations.
"""
    if filename == "CHECKLIST.md":
        return common + """
## Checklist

- [ ] Les fichiers cites existent.
- [ ] Le statut est exact.
- [ ] Les limites sont documentees.
- [ ] Une commande ou un test permet de verifier.
- [ ] La documentation a ete mise a jour apres modification du code.
- [ ] Aucune fonctionnalite absente n'est presentee comme terminee.
"""
    return common


def generate(docs_root: Path = DOCS, *, dry_run: bool = False) -> dict[str, Any]:
    written: list[str] = []
    for topic in TOPICS:
        folder = docs_root / topic["folder"]
        if not dry_run:
            os.makedirs(str(folder), exist_ok=True)
        for filename in STANDARD_FILES:
            path = folder / filename
            if not dry_run:
                path.write_text(page_body(topic, filename), encoding="utf-8")
            written.append(str(path))

    manifest = docs_root / "DOCUMENTATION_SYSTEM.md"
    manifest_text = (
        "# Documentation System\n\n"
        "Cette documentation est traitee comme une partie du produit FractalOS/AIONE.\n\n"
        "Regles:\n\n"
        "- chaque chapitre doit citer le code ou les docs existants ;\n"
        "- une fonctionnalite absente est marquee `A implementer` ;\n"
        "- apres chaque evolution code, mettre a jour le dossier concerne ;\n"
        "- les statuts autorises sont `Available`, `Partial`, `A implementer` ;\n"
        "- les validations doivent inclure les tests pertinents et `git diff --check`.\n\n"
        "Structure generee:\n\n"
        + "\n".join(f"- `docs/{topic['folder']}/` : {topic['title']} ({topic['status']})" for topic in TOPICS)
        + "\n"
    )
    if not dry_run:
        manifest.write_text(manifest_text, encoding="utf-8")
    written.append(str(manifest))
    return {
        "folders": len(TOPICS),
        "standard_files": len(STANDARD_FILES),
        "written": len(written),
        "manifest": str(manifest),
        "dry_run": dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the structured FractalOS documentation matrix.")
    parser.add_argument("--docs-root", default=str(DOCS), help="Target documentation root.")
    parser.add_argument("--dry-run", action="store_true", help="Compute the matrix without writing files.")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    result = generate(Path(args.docs_root).expanduser().resolve(), dry_run=args.dry_run)
    print(result)
