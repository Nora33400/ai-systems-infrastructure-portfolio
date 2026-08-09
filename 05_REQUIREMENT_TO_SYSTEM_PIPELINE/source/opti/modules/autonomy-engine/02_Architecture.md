# Architecture — Autonomy Engine

## Composants requis

- chargeur documentaire et constructeur de contexte ciblé ;
- gestionnaire de tâches persistant ;
- planificateur dépendant des statuts et prérequis ;
- client Ollama configurable et résilient ;
- protocole JSON d'actions ;
- exécuteur de fichiers, patches et commandes borné au workspace ;
- validateur des critères et tests ;
- relecteur distinct ;
- store durable, verrou et récupération ;
- journal JSONL append-only avec masquage des secrets ;
- politique Git et points de reprise.

## Tranche verticale

Un orchestrateur séquentiel coordonne ces composants. Les modules cognitifs documentés restent des sources de contraintes, pas des dépendances runtime implémentées.

## Baseline testée

- runtime Node.js/TypeScript et un seul worker ;
- store SQLite durable en mode WAL et journal JSONL append-only sous `${LOCALAPPDATA}/AIONE/opti-runtime` ;
- modèles codeur et relecteur `qwen2.5-coder:14b` servis par Ollama local ;
- mutations de fichiers réalisées par le backend WSL Ubuntu avec confinement canonique au workspace ;
- validation légère après action, validation complète avant clôture et revue indépendante du diff ;
- Git local facultatif, sans commit automatique faute de baseline et sans push implicite.

Ces choix constituent la baseline opérationnelle D-0009 ; le recours à WSL reste une adaptation de portabilité à revalider, enregistrée sous A-0010.

Cette phrase décrit la baseline historique du 2026-07-16. D-0037 établit ensuite la baseline protégée `4c0e0a3` pour la seule Phase 4 ; les commits automatiques, push et fusions restent désactivés.

Source normative : SRC-0007.

## Extension de planification Phase 1

`SRC-0012:L25-L100` ajoute, sans remplacer la baseline, une machine d'états gardée, un Policy Engine, des tables SQLite additives, un Receipt Engine et un `PlanningKernel.runOnce`. Le premier worker de cette extension est `LOCAL_SYSTEM` : il ne modifie aucun code métier et ne fait qu'exécuter des validations déjà autorisées. Les ports Trello, Ollama, Codex et ChatGPT restent fermés dans cette phase. Architecture détaillée : `docs/autonomy-planning/architecture.yaml`.

## Extension de planification Phase 2

D-0024 complète le scheduler par une analyse du graphe, une sélection multi-branche bornée, un délai de retry persistant et des verrous atomiques pour tâches, chemins et GPU. `RecursionGuard` applique profondeur, nombre d'enfants, ascendance et preuve nouvelle. `ResourcePlanner` est une fonction pure validée par schéma; `NvidiaSmiObserver` ne fait qu'une requête en lecture seule. Aucune bascule matérielle ni exécution parallèle n'est active. Sources : `SRC-0012`, `SRC-0013:L104-L108`, `SRC-0013:L159-L184`.

## Extension Phase 4 — patches isolés

`IsolatedWorkspaceManager` dérive ses racines depuis le runtime local, crée un worktree détaché hors dépôt canonique et persiste ses métadonnées. L'orchestrateur n'active ce chemin que si `task.isolation.enabled` vaut `true`. Les lectures de contexte peuvent rester canoniques ; actions de mutation, commandes et validations sont alors résolues contre le worktree. Le diff `--binary --full-index` est validé contre `allowed_paths` et `forbidden_paths`, hashé puis conservé comme proposition. Le cleanup refuse toute perte non capturée et recovery est idempotent. Source : `SRC-0017`.
