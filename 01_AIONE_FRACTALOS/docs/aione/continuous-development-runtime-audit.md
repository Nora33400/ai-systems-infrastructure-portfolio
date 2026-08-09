# Fractal Continuous Development Runtime - Audit initial

Date: 2026-07-11
Workspace: `<AIONE_WORKSPACE>`

## Etat actuel

Le depot contient environ 523 fichiers suivis ou candidats, avec une base principale C#/.NET WPF pour le HUD et une couche Python `aione_forge` deja orientee runtime, memoire, agents, SQLite et file projet.

Langages et projets detectes:

- C# / .NET 10 WPF: `apps/windows_hud/AioneHud.csproj`.
- Python: package `aione_forge`, scripts runtime et tests.
- TypeScript: tests ecosysteme sous `src/tests`.
- PowerShell et shell: scripts de validation, cockpit, tailnet, agent bridge.
- JSON/Markdown: manifests plugins, documentation, backlog et schemas.

Points d'entree principaux:

- HUD Windows: `apps/windows_hud/App.xaml.cs`.
- API locale existante AIONE: `aione_forge/api.py`.
- CLI AIONE Forge: `aione_forge/cli.py`.
- Agent Bridge: `apps/windows_hud/FractalAgentBridgeWindow.cs`, `FractalLocalAgentControlService.cs`, `FractalAgentBridgeProviders.cs`.
- Scripts cockpit/OpenWebUI: `scripts/cockpit_start.ps1`, `scripts/tailnet_start.ps1`.

## Composants reutilisables

- `aione_forge.project_queue`: file projet SQLite, context packs, validation guards, providers prudents.
- `aione_forge.api`: serveur HTTP local sans dependance externe.
- `Fractal Agent Bridge`: detection Codex/OpenCode/Aider/Ollama, prompt mobile, commandes Git/tests/checkpoints.
- `Fractal Remote`: acces mobile local/Tailscale deja borne par permissions.
- Scripts `validate_all.ps1`, `alpha_check.ps1`, `doctor-fractal-agent-bridge.ps1`.
- Documentation `docs/local-agent` et `docs/agent-bridge`.

## Integrations locales detectees

- Git: present.
- Ollama: present et API locale active.
- OpenCode: present.
- Aider: present.
- Docker: CLI present, daemon non actif lors du doctor precedent.
- WSL: present.
- Tailscale: present, IP detectee `100.103.116.16`.
- OpenSSH client: present.
- OpenSSH Server: non confirme.
- Python: 3.13.
- .NET SDK: 10.0.301.

Modeles Ollama connus:

- `qwen3-coder:30b-a3b-q4_K_M`
- `qwen3-coder:30b`
- `qwen2.5-coder:14b`
- `qwen2.5-coder:7b`
- `nomic-embed-text:latest`

GPU detectes precedemment:

- NVIDIA GeForce RTX 3060, 12 Go.
- NVIDIA GeForce RTX 4060, 8 Go.

## Fonctions absentes ou incompletes

- Pas encore de runtime persistant dedie aux idees, priorites, dependances, executions continues et memoire cyclique.
- Pas encore de base SQLite unique avec les tables demandees pour backlog, evenements, contextes, memoires, approvals, health et git workspaces.
- Pas encore d'API OpenAPI dediee a OpenWebUI pour commander ce runtime.
- Pas encore de worker d'idees separe qui produit des Markdown prets a importer.
- Pas encore de scheduler continu evenementiel separant files `Critical`, `Urgent`, `HighPriority`, etc.
- Pas encore de verticale automatique qui prend une idee, calcule la priorite, demande approbation, cree une tache, execute sur depot de test, teste, compacte et passe a la suite.

## Risques

- Le workspace Git est deja tres sale a cause de gros lots precedents; le runtime ne doit pas ecraser ces changements.
- Docker/OpenWebUI ne doit pas etre force si Docker Desktop n'est pas actif.
- Les agents locaux ne doivent pas recevoir de shell arbitraire ni acces hors workspace.
- Les donnees runtime SQLite doivent rester locales et ignorees par Git.
- Le service mobile doit rester en `127.0.0.1` par defaut; LAN/Tailscale doivent etre explicites.
- Les operations Git destructrices, commit, push, merge et deploiement doivent rester bloquees sans validation.

## Plan d'integration

1. Creer un package Python `fractal_dev_runtime` reutilisant les conventions AIONE: SQLite, serveur HTTP local, CLI et scripts.
2. Stocker l'etat dans `%LOCALAPPDATA%\AIONE\ContinuousDevRuntime` par defaut, ou dans un dossier passe en argument pour les tests.
3. Creer l'arborescence `agent-workspace/ideas/{inbox,analyzed,ready,rejected,duplicates,archived}`, `plans`, `reports`, `memory`, `executions`.
4. Fournir une API locale authentifiee avec `/openapi.json`, routes runtime, idees, queue, approvals, memoire, idea-worker.
5. Implementer une verticale sure sur depot de test isole, jamais directement sur le depot utilisateur.
6. Ajouter scripts PowerShell et shell pour start/stop/pause/resume/status/diagnostics/OpenWebUI/coding-agent/idea-agent/backup/restore.
7. Ajouter tests automatises couvrant persistance, priorite, scheduler, compaction, worker idee, import Markdown, API et reprise.

## Migrations

Premiere migration: `continuous-dev-runtime-v1`.

Elle cree les tables minimales demandees:

`projects`, `repositories`, `ideas`, `idea_relations`, `initiatives`, `epics`, `features`, `tasks`, `task_dependencies`, `priority_scores`, `plans`, `approvals`, `executions`, `execution_events`, `agents`, `context_packages`, `memory_items`, `memory_summaries`, `memory_relations`, `documents`, `generated_ideas`, `validation_reports`, `git_workspaces`, `settings`, `system_health`, `audit_events`.

Les anciennes donnees ne sont pas migrees automatiquement. Les imports se font par documents Markdown ou par API.
