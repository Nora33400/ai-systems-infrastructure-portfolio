# Validation the owner — activation opérationnelle bornée

- Date : 2026-07-18
- Autorité : décision humaine explicite de the owner
- Pièce jointe : `pasted-text.txt`
- SHA-256 de la pièce jointe : `468b859d621ea20339184c06cf3aa575f40dc0f886ad85eff8ee4e8736ced974`
- Taille observée : 19 864 octets, 686 lignes

## Décisions confirmées

1. Le profil Google Agenda nommé `the configured owner profile` est le calendrier principal autorisé pour l'intégration et la planification dynamique. Le compte doit être vérifié avant toute écriture. Aucun événement personnel existant ne peut être modifié ou supprimé sans nécessité explicite.
2. Un `GO` explicite est accordé pour créer des cartes et restructurer progressivement le tableau Trello lié à opti et à l'orchestration agentique. L'inventaire, le dry-run, la préservation de l'existant, l'absence de doublon, la traçabilité et le rollback restent obligatoires.
3. WorkMesh doit avoir son propre dépôt Git, son historique et son cycle de développement, tout en restant un composant orchestré relié à opti par un contrat explicite. Les composants déjà fournis par opti ne doivent pas être dupliqués.
4. Une unique carte Trello pilote peut être créée sans nouvelle validation humaine lorsque le dry-run automatique ne détecte ni perte, ni collision, ni doublon critique. Le résultat doit être relu avant tout lot supplémentaire.
5. L'interdiction de fusion, récupération ou réinjection depuis `<EXCLUDED_VALIDATION_WORKSPACE>` reste absolue hors lot de réconciliation explicitement approuvé. La lecture seule comparative reste autorisée.

## Directive d'exécution

- enregistrer ces décisions dans les états machine ;
- vérifier le profil Google Agenda ;
- refaire l'inventaire Trello en lecture seule ;
- valider un dry-run ;
- créer et contrôler une seule carte pilote si le dry-run réussit ;
- initialiser le dépôt Git indépendant de WorkMesh s'il n'existe pas ;
- contractualiser la frontière opti–WorkMesh ;
- exécuter tests et contrôles de non-régression ;
- produire un checkpoint puis poursuivre la prochaine tâche prête.

## Mode opérationnel autorisé par la pièce jointe

Le mode `AUTONOMY_OPERATIONAL` autorise les changements locaux, réversibles, bornés et testés déjà couverts par les politiques du dépôt. Il privilégie le code fonctionnel, les tests, les corrections, la reprise et les preuves structurées. Il n'élargit pas les permissions sensibles et n'autorise ni publication, ni push distant, ni suppression irréversible, ni dépense, ni exposition de secret, ni synchronisation AIONE/AIONE-Validation.

La prochaine correction locale attestée dans opti reste `WQ-0052`, qui unifie l'arrêt global des deux chemins runtime. Son périmètre, ses fichiers autorisés et ses critères d'acceptation restent ceux de `WORK_QUEUE.yaml`.
