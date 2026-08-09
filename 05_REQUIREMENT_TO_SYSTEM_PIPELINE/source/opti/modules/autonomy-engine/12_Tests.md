# Tests — Autonomy Engine

Le périmètre obligatoire couvre configuration, import YAML, dépendances, sélection, persistance, protocole JSON, sécurité des chemins et commandes, patch, capture de commande, timeout, retries Ollama, quarantaine, restauration, transitions, crash, verrou, événements et synchronisation documentaire.

Un test d'intégration Ollama réel est distinct des tests à doubles. La démonstration canari doit modifier utilement le dépôt, valider et reprendre après arrêt.

## Résultats du 2026-07-16

- compilation TypeScript : réussie ;
- 7 tests locaux réussis, 1 test Ollama isolé normalement ignoré dans la suite locale ;
- test Ollama réel : 1/1 réussi avec `qwen2.5-coder:14b` ;
- validation documentaire : 104 YAML, 8 JSON, 38 contrats et 918 Markdown, 0 erreur ;
- canari WQ-0008 et continuité WQ-0009/WQ-0010 : terminés après validation et reviewer indépendant ;
- arrêt/reprise : exercés réellement pendant le canari.

Source normative : SRC-0007.

## Résultats Phase 1 du 2026-07-18

- suite globale : 47 tests réussis, 2 intégrations Ollama isolées ignorées, 0 échec ;
- huit tests Phase 1 couvrent transitions, persistance/reprise, import canonique, politique, intégrité des receipts, projection hashée, commande sans shell et run-once sans service externe ;
- smoke canonique WQ-0042 : trois validations réussies, état SQLite COMPLETED et receipt vérifié.

Source normative : `SRC-0012:L107-L144`.

## Résultats Phase 2 du 2026-07-18

- suite globale : 55 tests réussis, 2 intégrations Ollama isolées ignorées, 0 échec ;
- huit tests Phase 2 couvrent cycles, dépendances absentes, branches indépendantes, verrous concurrents, retry temporisé, récursion, modes GPU, parsing de l'observateur et intégrité du receipt projeté ;
- le dry-run réel a observé RTX 3060 et RTX 4060 puis recommandé deux rôles sans lancer ni arrêter de processus.

Sources : `SRC-0012`, `SRC-0013`; preuves : `tests/autonomy/planning-phase2.test.ts` et WQ-0049.

## Résultats Phase 4 du 2026-07-23

- 17 tests dédiés utilisent uniquement des dépôts Git temporaires ;
- HEAD absent, baseline sale, traversées, hors-scope, `.env`, `.git` et patch altéré sont refusés ;
- worktree détaché, fichier suivi/non suivi, patch binaire déterministe, nettoyage double et reprises dirty/missing sont vérifiés ;
- branche, HEAD et statut canoniques restent identiques ; aucun remote, push ou merge n'est créé ;
- suite globale : 83 tests réussis, 2 intégrations Ollama isolées ignorées, 0 échec.

Source : `SRC-0017`; preuve : `tests/autonomy/isolated-workspace.test.ts`.
