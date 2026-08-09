# Récupération — Autonomy Engine

Le moteur écrit l'état durable après chaque transition significative, journalise avant et après les actions, utilise un verrou local et réévalue les tâches interrompues.

Git fournit le point de reprise lorsque le dépôt possède une base sûre. Un échec conserve logs et diff ; la restauration n'efface jamais silencieusement des modifications préexistantes.

L'arrêt normal passe par un marqueur de demande d'arrêt et termine l'action atomique courante avant de libérer le verrou.

La démonstration a exercé l'arrêt coopératif, la reprise d'une tâche `running`, la remise en file après quarantaine et la restauration d'un fichier créé lors d'une tentative échouée. Les manifests sont conservés par tâche et tentative sous `${LOCALAPPDATA}/AIONE/opti-runtime/state/backups`.

Source normative : SRC-0007.

En Phase 2, une exécution `RUNNING` récupérée devient `ABANDONED` et ses verrous sont libérés. Une tâche interrompue reçoit un `next_retry_at` calculé depuis sa politique. Les plans dry-run sont reconstructibles et leur dernier snapshot est conservé comme métadonnée, sans créer de travail matériel. Sources : `SRC-0012`, `SRC-0013`.

En Phase 4, un worktree interrompu et autorisé est converti en patch hashé avant suppression. Un worktree disparu est pruné puis marqué `CLEANED`; une modification interdite passe à `RECOVERY_REQUIRED` sans effacement. Cleanup et recovery peuvent être rejoués sans erreur. Source : `SRC-0017`.
