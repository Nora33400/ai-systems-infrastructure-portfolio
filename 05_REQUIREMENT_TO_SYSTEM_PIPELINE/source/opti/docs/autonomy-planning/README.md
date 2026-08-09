# Mode autonome par planification — intégration v1

Statut : `TESTED` pour le noyau local Phase 1, la planification persistante Phase 2 et le rapport Ollama read-only Phase 3. Les phases 4 à 8 restent `PROPOSED` ou `BLOCKED` selon leurs dépendances.

Source normative : `SRC-0012`.

## Décision d'intégration

Le nouveau mode étend `autonomy-engine`. Il ne formalise pas `organum/scheduler`, dont le contrat historique reste hypothétique, et ne transforme pas `agent-fabric` en runtime multi-agent. Cette séparation préserve les modalités existantes tout en fournissant une infrastructure locale concrète.

## Autorité

- the owner : autorité finale et actions sensibles.
- Registres opti : vérité déclarative et décisionnelle.
- SQLite local : état d'exécution persistant et reconstructible.
- Receipts : preuve immuable des actions.
- Trello : projection optionnelle, actuellement désactivée et non configurée.
- Ollama, Codex et ChatGPT : adaptateurs de phases ultérieures ; leurs absences ne bloquent pas le noyau local.

## Phase 1 livrée

- contrat de tâche compatible avec `WORK_QUEUE.yaml` ;
- machine d'états explicite et transitions refusées lorsqu'elles sont invalides ;
- politique centrale validée par schéma ;
- extension SQLite pour exécutions, verrous, décisions, autorisations, changements externes, checkpoints et receipts ;
- receipts hashés et vérifiables ;
- cycle `run-once` déterministe pour tâches locales de validation sans agent externe ;
- arrêt global fail-closed par `AUTONOMY_DISABLED` ou sentinelle persistante : `run`, `run-once`, `bootstrap`, `retry-task` et le worker Ollama read-only refusent de démarrer ; seule une action explicite peut retirer la sentinelle ;
- commandes `doctor`, `run-once`, `tasks`, `task-show` et `receipts-verify` ;
- tests unitaires et smoke test local.

## Phase 2 livrée

- cycles de dépendances et références manquantes détectés avant sélection ;
- retries temporisés et branches indépendantes ;
- verrous atomiques multi-ressources avec conflits hiérarchiques de chemins ;
- récursion bornée par profondeur, enfants, ascendance et preuve nouvelle ;
- plan multi-candidats limité à deux tâches, sans lancer de parallélisme ;
- observation GPU `nvidia-smi` et recommandation de mode en `dry_run_only` ;
- commandes `plan-once` et `resources` ;
- sept tests Phase 2 et smoke WQ-0049.

## Phase 3 livrée

- paquet de tâche minimal avec critères, limites et contextes explicitement autorisés ;
- modèle read-only primaire et fallback local ;
- rapport strict validé par schéma, références fermées et rejet des patches ;
- table SQLite additive et vérification des hashes des rapports ;
- receipt de réussite ou d'échec sans transition canonique issue du modèle ;
- commande `ollama-readonly -Task WQ-XXXX` ;
- smoke WQ-0044 réel, avec premier échec conservé puis fallback 14B réussi.

## Non disponible dans cette phase

Les worktrees et patches de proposition Phase 4 sont actifs uniquement pour les tâches opt-in et sans apply canonique. Trello réel, Agenda, LiteLLM, patch produit par le worker Ollama read-only, revue Codex automatique, API ChatGPT, boucle planifiée Windows, bascule GPU et parallélisme d'exécution ne sont pas actifs. Leurs contrats cibles sont conservés comme propositions; aucune fausse disponibilité n'est déclarée.

## Fichiers conservés dans la copie publique

- [Rapport d'implémentation borné](implementation-report.md)
- [Architecture cible](architecture.yaml)
- [Machine d'états](task-state-machine.yaml)
- [Contrat de stockage](storage-contract.yaml)

Les audits de connecteurs, plans historiques et rapports de phases redondants ont été exclus de la tranche publique. Les résultats exécutés actuels se trouvent dans le dossier `evidence/tests` du portfolio.
