# Directive humaine — mode autonome par planification

Date de réception : 2026-07-18
Auteur : the owner
Statut : directive humaine normative pour l'infrastructure d'autonomie d'opti
Portée : extension progressive de `autonomy-engine`; aucune promotion implicite des modules métier documentaires

## Mission et chaîne d'autorité

Concevoir puis implémenter progressivement un mode autonome par planification dans lequel :

- the owner reste l'autorité finale ;
- ChatGPT assure la supervision stratégique et cognitive ;
- Codex assure la supervision technique du dépôt ;
- une IA locale servie par Ollama exécute les tâches répétitives et peu risquées ;
- Trello sert d'interface humaine de planification ;
- les fichiers internes d'opti restent la source de vérité ;
- the owner intervient le moins possible ;
- aucune action sensible n'est exécutée sans autorisation explicite.

La cible doit être réellement exécutable, persistante, testable, extensible et capable de reprendre après interruption. L'architecture documentaire existante ne doit pas être réécrite arbitrairement.

Chaîne cible : the owner → ChatGPT Supervisor → Codex Technical Supervisor → Local Orchestrator → Ollama Local Worker → espace Git isolé → tests, receipts et état persistant → Trello et WORK_QUEUE.

Lorsqu'un superviseur externe est indisponible, les tâches sûres déjà autorisées peuvent continuer, la branche affectée est suspendue si une revue manque, les branches indépendantes continuent et aucun résultat ne doit être perdu.

## Principe de délégation minimale

Chaque niveau résout ce qui relève de son périmètre. L'IA locale exploite les contrats et son contexte, Codex vérifie techniquement le dépôt, ChatGPT applique les règles et décisions persistées, et the owner n'est sollicitée que pour la vision, une autorisation sensible, une action extérieure, une modification irréversible, une ambiguïté réellement indécidable ou un changement majeur de périmètre. Les questions non urgentes sont regroupées.

## Source de vérité et synchronisation

La vérité opérationnelle est locale et versionnée : `WORK_QUEUE.yaml`, `PROJECT_STATE.md`, graphes de dépendances, registre des modules, receipts et stockage local structuré. Trello est une projection synchronisée et désactivable. Les changements Trello autorisés deviennent des événements candidats vers la file interne. Les changements internes sont projetés vers Trello. Les conflits doivent être détectés, journalisés et résolus par une politique explicite.

## Composants cibles

### Meta Scheduler

Lire la file, vérifier les dépendances, sélectionner les tâches prêtes, créer des sous-tâches bornées, limiter la récursion, attribuer un agent, gérer délais, tentatives, suspension, reprise, annulation, boucles, branches indépendantes, priorités et receipts.

### Persistent State Store

Conserver tâches, exécutions, tentatives, dépendances, verrous, agents, rapports, décisions, autorisations, erreurs, changements Trello, receipts et checkpoints. SQLite est demandé si aucun stockage structuré équivalent n'existe. YAML/Markdown restent les contrats et la vérité déclarative ; SQLite porte l'état d'exécution reconstructible ; les receipts sont immuables.

### Trello Synchronizer

Intégration optionnelle, désactivable et configurable par variables `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`, sans secret dans Git. Elle doit retrouver/créer/mettre à jour/déplacer les cartes par `task_id`, gérer labels, checklists, commentaires synthétiques, changements manuels autorisés, conflits et simulation. Les noms de listes et labels sont configurables. Aucune disponibilité ne doit être prétendue avant configuration et test réels.

### Ollama Worker

Configuration attendue : endpoint local `http://127.0.0.1:11434`, modèle principal `qwen2.5-coder:14b`, repli `qwen2.5-coder:7b`, timeout 900 secondes. Le paquet de tâche contient objectif, contexte minimal, chemins autorisés/interdits, contrats, dépendances, tests, sécurité et sortie attendue.

Le worker peut analyser, rechercher, documenter, générer des tests, proposer un patch, modifier les seuls chemins autorisés et lancer les seules commandes autorisées. Il ne peut ni pousser, ni fusionner main, ni toucher aux secrets, publier, installer arbitrairement, supprimer massivement, changer la sécurité ou augmenter son autonomie.

### Isolated Workspace Manager

Toute tâche de modification utilise une branche, un worktree ou une copie temporaire contrôlée. Deux tâches ne modifient pas les mêmes fichiers sans verrou. Chaque exécution conserve branche, worktree, hash initial, fichiers, diff, commandes, tests et état final.

### Codex Review Gateway

Adaptateurs prévus : `manual_bundle`, `codex_cli`, `external_command`, `api_adapter`. Seul un adaptateur réellement disponible peut être déclaré fonctionnel. Le mode manuel doit générer tâche, objectif, contexte, diff, fichiers, commandes, tests, erreurs, rapport local, risques et décision attendue. Décisions : APPROVE, APPROVE_WITH_FIXES, RETURN_TO_LOCAL_AI, ESCALATE_TO_CHATGPT, REQUIRE_OWNER, REJECT.

### ChatGPT Strategic Gateway

Adaptateurs prévus : `manual_bundle`, `openai_api`, `external_command`. Le paquet contient uniquement état global, tâches terminées/bloquées, dérives, priorités, décisions et risques nécessaires. Décisions : CONTINUE, REPRIORITIZE, SPLIT_TASK, MERGE_TASKS, PAUSE_BRANCH, REQUEST_TECHNICAL_REVIEW, REQUIRE_OWNER, CANCEL_TASK.

### Receipt Engine

Chaque action significative produit un receipt horodaté, traçable, lié à la tâche et à l'exécution, non réécrit silencieusement et auditable. Champs minimaux : `receipt_id`, `task_id`, `execution_id`, `timestamp`, `actor`, `action`, `inputs_hash`, `outputs_hash`, `files_read`, `files_modified`, `commands`, `tests`, `decision`, `result`, `parent_receipt`.

### Policy Engine

Une politique centrale lisible, testable et validée par schéma définit continuation, retries, branches indépendantes, regroupement des questions, limites de récursion/parallélisme/durée, droits des agents et actions exigeant the owner. Niveaux : READ_ONLY, LOCAL_SAFE, PATCH_ISOLATED, CODEX_REVIEW_REQUIRED, CHATGPT_REVIEW_REQUIRED, OWNER_REQUIRED, FORBIDDEN.

the owner reste obligatoire pour publication, migration destructive, suppression massive, secrets, dépense, push main, installation système, sécurité ou accès externe. Une décision manquante bloque seulement la branche affectée.

## Cycle déterministe

1. Lire l'état.
2. Réconcilier SQLite avec WORK_QUEUE.
3. Réconcilier Trello si activé.
4. Libérer les exécutions abandonnées.
5. Vérifier les dépendances.
6. Sélectionner les tâches prêtes.
7. Vérifier les politiques.
8. Verrouiller les ressources.
9. Préparer le contexte.
10. Créer un espace isolé.
11. Lancer l'agent autorisé.
12. Vérifier le résultat.
13. Lancer les tests.
14. Produire le receipt.
15. Transmettre au superviseur requis.
16. Mettre à jour l'état.
17. Synchroniser Trello.
18. Libérer les ressources.

Le cycle doit pouvoir fonctionner une fois, en boucle, par CLI, via Windows Task Scheduler et éventuellement comme service local.

## États et tâches

États cibles : DISCOVERED, NEEDS_CONTEXT, READY_LOCAL_AI, RUNNING_LOCAL_AI, READY_CODEX_REVIEW, RUNNING_CODEX_REVIEW, NEEDS_CHATGPT_REVIEW, NEEDS_OWNER_DECISION, BLOCKED, FAILED_RETRYABLE, FAILED_FINAL, VALIDATED, COMPLETED, ARCHIVED, CANCELLED. Toutes les transitions sont explicites, validées et testées.

Une tâche peut définir : identifiant, titre, objectif, projet, statut, priorité, risque, dépendances, parent, profondeur, agent, superviseur, validateur, chemins autorisés/interdits, commandes autorisées, contexte, budget de ressources, politique de retry, critères d'acceptation, projection Trello et horodatages. La compatibilité avec `WORK_QUEUE.yaml` existant doit être préservée par migration ou adaptateur.

## CLI cible

Commandes attendues ou équivalentes : init, doctor, run-once, start, stop, status, tasks, task show/retry/pause/approve, trello sync, receipts verify, export-review vers Codex ou ChatGPT.

## Sécurité et observabilité

Sécurité par défaut : aucun secret Git, validation de chemins, prévention du path traversal, commandes sans shell arbitraire lorsque possible, liste blanche, timeout, sorties bornées, arrêt propre, verrous, journalisation, simulation, aucune publication/push main/suppression massive/installation système/permission élargie. Interrupteur global `AUTONOMY_DISABLED` par variable, sentinelle ou commande.

L'état JSON doit exposer tâche, agent, durée, ressources, dernière action, receipt, prochain contrôle, blocages, questions the owner, erreurs répétées, Trello, Ollama et superviseurs.

## Tests requis

Tests unitaires et d'intégration mockée pour machine d'états, dépendances, scheduler, politiques, verrous, reprise, échec, timeout, récursion, Trello simulé, Ollama simulé, modes manuels Codex/ChatGPT, receipts, intégrité, concurrence, non-régression et smoke test complet. Les intégrations extérieures sont mockables.

## Documentation requise

Documenter architecture, installation, configuration, lancement, simulation, Trello, Ollama, revues Codex/ChatGPT, politiques, dépannage, crash, sécurité, limites, arrêt et restauration. Distinguer honnêtement entièrement automatisé, semi-automatisé, manuel et indisponible.

## Phasage imposé

- Phase 0 Audit : dépôt, modules, contrats, doublons, rapport d'intégration ; ne rien réécrire inutilement.
- Phase 1 Noyau local : modèle de tâche, machine d'états, politiques, SQLite, receipts, CLI, `run-once`, tests ; fonctionne sans Trello, Ollama, Codex ou ChatGPT.
- Phase 2 Planification persistante : dépendances, priorités, reprise, verrouillage, tentatives, récursion, branches indépendantes, arrêt global.
- Phase 3 Ollama lecture seule.
- Phase 4 patches isolés.
- Phase 5 revue Codex.
- Phase 6 supervision ChatGPT.
- Phase 7 Trello.
- Phase 8 mode planifié, Windows Task Scheduler, doctor, observabilité et documentation complète.

Chaque phase doit inspecter, contractualiser, implémenter une tranche verticale minimale, tester, corriger, exécuter un smoke test, documenter, produire un receipt et actualiser `PROJECT_STATE.md` et `WORK_QUEUE.yaml`. Ne pas attendre une validation humaine entre petites étapes sûres.

## Conditions d'arrêt

Arrêt seulement pour action sensible, ambiguïté architecturale majeure indécidable, absence de fichiers essentiels ou décision irréversible de vision. Bloquer seulement la branche affectée, documenter le problème, continuer les tâches indépendantes et grouper la question.

## Première exécution demandée

Réaliser l'audit complet, la cartographie réutilisable, l'architecture cible, les contrats, les tâches `WORK_QUEUE`, la Phase 1 si compatible, ses tests, un smoke test et un rapport précis. Ne jamais prétendre qu'une intégration externe fonctionne avant configuration et test. Préserver traçabilité, reprise, compatibilité documentaire et autorité finale de the owner.
