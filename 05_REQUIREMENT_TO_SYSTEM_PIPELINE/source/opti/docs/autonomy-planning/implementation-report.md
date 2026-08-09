# Rapport d'implémentation — autonomie planifiée Phase 1

Date : 2026-07-18
Source normative : `SRC-0012`
Décisions : D-0018, D-0019, D-0020

## Résultat

La Phase 0 d'audit et la Phase 1 locale sont terminées. Le noyau fonctionne sans Trello, Ollama, Codex automatique ni API ChatGPT. WQ-0042 a parcouru une vraie transition persistante READY_LOCAL_AI → RUNNING_LOCAL_AI → VALIDATED → COMPLETED, exécuté trois validations locales, mis à jour `WORK_QUEUE.yaml` et créé un receipt hashé vérifié.

## Fichiers et surfaces inspectés

- démarrage canonique : `PROJECT_STATE.md`, `SOURCE_MANIFEST.yaml`, `MASTER_MODULE_REGISTRY.yaml`, `ARCHITECTURE_GRAPH.yaml`, `WORK_QUEUE.yaml`, `DECISION_LOG.md`, `ASSUMPTION_REGISTER.md` ;
- dépôt : `README.md`, `package.json`, `tsconfig.json`, `DEPENDENCY_REGISTER.yaml`, graphes, questions, contradictions et couverture ;
- contrats : `modules/autonomy-engine/`, `modules/agent-fabric/`, `modules/organum/05_Submodules/scheduler/`, `modules/tilemindfs/`, runtime Ollama et receipts constitutionnels ;
- exécution : tous les fichiers `src/autonomy/`, `schemas/agent-action.schema.json`, `schemas/task-state.schema.json`, `schemas/autonomy-event.schema.json` ;
- validation : tous les scripts `*-autonomy.ps1`, `test-all.ps1` et tous les tests `tests/autonomy/` ;
- persistance réelle : schéma SQLite lu en lecture seule, 49 tâches après import, événements et artefacts runtime hors dépôt ;
- projection : tous les contrats `docs/organization-node/`, sans connexion ni écriture Trello.

## Éléments réutilisés

`StateStore`, `TaskImporter`, `Scheduler`, `SecurityPolicy`, `Validator`, `RuntimeLock`, `StopController`, `RecoveryManager`, `EventLogger`, `OllamaClient`, `WorkspaceWriter` et la CLI existante ont été étendus. Aucun second moteur, aucune seconde base et aucun nouveau module métier n'ont été créés. `organum/scheduler` reste hypothétique.

## Éléments créés

- source `SRC-0012` et décisions d'autorité ;
- domaine `docs/autonomy-planning/` ;
- contrats et schémas de politique, tâche et receipt ;
- `TaskStateMachine`, `PolicyEngine`, `ReceiptEngine`, `PlanningKernel` ;
- configuration Trello désactivée et politique centrale ;
- tests Phase 1 et projection versionnée du receipt WQ-0042.

## Éléments modifiés

- types, store SQLite, scheduler, importeur, runtime, CLI, arrêt global et exécuteur de commandes ;
- scripts CLI ;
- contrat, preuves et documentation de `autonomy-engine` ;
- registres, graphe, file, couverture et état de reprise.

## Architecture retenue

Les définitions, décisions et politiques restent dans les fichiers versionnables. SQLite porte l'exécution, les verrous, checkpoints et receipts. Le `PlanningKernel` ne traite en Phase 1 que les tâches `LOCAL_SYSTEM`, `SAFE`, sans superviseur externe. Toute autre tâche est différée par politique. Les intégrations externes sont des ports optionnels et échouent fermés.

## Tests et smoke

- compilation TypeScript : réussie ;
- suite globale : 47 réussis, 2 Ollama ignorés, 0 échec ;
- tests Phase 1 : machine d'états, persistance, politique, intégrité/tamper des receipts, commande sans shell et run-once externe-free ;
- `doctor` : sain, Trello DISABLED, Codex/ChatGPT `manual_bundle`, aucune variable Trello complète ;
- smoke : exécution `EXE-c741e1cd-585a-43d1-82db-5bf37d5d9b28`, receipt `RCP-dc3ffa50-3883-4211-ab57-249ef3aad4b5`, trois validations réussies.

## Limitations réelles

- aucune baseline Git : worktree, commit automatique, push et fusion interdits ;
- Trello non configuré, non lu et non écrit ;
- Ollama n'est pas appelé par le noyau Phase 1 ;
- Codex et ChatGPT ne sont pas invoqués automatiquement ;
- aucun parallélisme, aucune récursion de sous-tâches et aucun patch isolé dans cette phase ;
- `node:sqlite` reste expérimental et le backend d'écriture WSL reste spécifique à cet hôte ;
- le corpus historique incomplet continue de bloquer les contrats métier, sans bloquer cette infrastructure.

## Risques

Le principal risque local est l'absence de commit de référence : l'isolation Git de Phase 4 ne peut pas être démontrée. Les risques externes sont l'identité, la confidentialité, les permissions, les conflits de synchronisation et la protection des secrets Trello. Le niveau SENSITIVE/CRITICAL reste bloqué pour the owner.

## Prochaine tâche prête

WQ-0043 est `READY_CODEX_REVIEW` : compléter la Phase 2 par cycles de dépendances, récursion bornée, verrous de ressources et continuation des branches indépendantes. Cette tâche est locale et ne requiert aucune décision de the owner.

## Décisions the owner restantes

- choisir une baseline Git avant la Phase 4 ;
- choisir Workspace/tableau Trello et permissions avant la Phase 7 ;
- décider identité, confidentialité, champs modifiables et gestion des conflits avant toute synchronisation bidirectionnelle ;
- autoriser séparément toute action sensible listée par la politique.
