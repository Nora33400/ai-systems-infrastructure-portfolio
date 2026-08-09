# AIONE / La Forge Autonomy Engine

- Identifiant : autonomy-engine
- Classification : enabling_module
- Statut : TESTED pour la tranche bootstrap de SRC-0007, l'orchestration verticale de SRC-0008 et les noyaux locaux de planification Phases 1 à 4 de SRC-0012/SRC-0013/SRC-0014/SRC-0017
- Normatif : true uniquement pour ces tranches bornées
- Sources : SRC-0007, SRC-0008, SRC-0012, SRC-0013, SRC-0014, SRC-0017

## Mission

Fournir une boucle locale persistante qui lit la documentation, sélectionne une tâche réalisable, construit un contexte ciblé, pilote un agent codeur Ollama par actions structurées, exécute et révise les changements, valide les critères, sauvegarde l'état et poursuit sans relance Codex.

## Limites

- un seul worker séquentiel dans la première version ;
- aucun code métier des modules cognitifs hypothétiques ;
- aucun accès hors workspace ;
- aucun push distant implicite ;
- aucune tâche terminée sur la seule affirmation du modèle ;
- aucune confirmation humaine entre tâches ordinaires en mode GO BATCH OUI.

## Implémentation vérifiée

- code TypeScript : `src/autonomy/` ;
- configuration : `config/autonomy.yaml` ;
- protocoles JSON : `schemas/agent-action.schema.json`, `schemas/task-state.schema.json`, `schemas/autonomy-event.schema.json` ;
- scripts Windows : `scripts/*-autonomy.ps1` ;
- tests : `tests/autonomy/` ;
- modèle réel validé : `qwen2.5-coder:14b` ;
- tâches autonomes terminées : WQ-0008, WQ-0009 et WQ-0010.
- cycle cognitif terminé : WQ-0011 à WQ-0020, exécution `COG-EXE-242CFBBC-9F9E-49F6-8D27-EBBDA67A3AF0`.
- noyau autonome planifié Phase 1 : WQ-0040 à WQ-0042 terminées, exécution `EXE-c741e1cd-585a-43d1-82db-5bf37d5d9b28`, receipt `RCP-dc3ffa50-3883-4211-ab57-249ef3aad4b5` ;
- planification persistante Phase 2 : cycles et dépendances absentes, retries temporisés, récursion bornée, verrous atomiques, branches indépendantes et planificateur bi-GPU en dry-run testés sous WQ-0043/WQ-0049 ;
- rapport Ollama read-only Phase 3 : paquet borné, schéma strict, fallback, persistance hashée et smoke réel sous WQ-0044 ;
- worktrees et patches isolés Phase 4 : opt-in explicite, mutations et tests routés vers un worktree détaché hors dépôt, patch binaire hashé, récupération/nettoyage idempotents et dépôt canonique inchangé sous WQ-0045 ;
- Trello, patches Ollama issus du worker read-only et passerelles externes restent désactivés ou différés. Un patch Phase 4 n'est jamais appliqué automatiquement.

Les preuves d'exécution sont persistées hors du dépôt protégé dans `${LOCALAPPDATA}/AIONE/opti-runtime/`. Source normative : SRC-0007.

## Curated public files

- [02_Architecture.md](02_Architecture.md)
- [04_Runtime.md](04_Runtime.md)
- [10_FailureCases.md](10_FailureCases.md)
- [11_Recovery.md](11_Recovery.md)
- [12_Tests.md](12_Tests.md)
- [18_CognitiveVerticalSlice.md](18_CognitiveVerticalSlice.md)
- [contract.yaml](contract.yaml)
- [evidence.yaml](evidence.yaml)
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)
