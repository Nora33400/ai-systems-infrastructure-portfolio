# FractalOS — Matrice de complétion

État au 23 juin 2026, workspace v23.

| Domaine | État | Niveau | Validation / limite |
| --- | --- | --- | --- |
| HUD périphérique, dock et zone de notification | Validé | Fonctionnel | Masquage/restauration et processus en arrière-plan |
| Modules génériques et widgets configurables | Validé | Fonctionnel | Création, layout, préréglages et persistance |
| Hébergement HUD → surface 3D | Validé | Fonctionnel | Action réelle `→3D`, rendu et persistance |
| Retour surface 3D → HUD | Validé | Fonctionnel | Action réelle `→HUD` et suppression du placement actif |
| Mode HUD + 3D | Validé | Fonctionnel | Même entité visible dans les deux projections |
| Import scène → tableau 3D | Validé | Fonctionnel | Grille automatique sans chevauchement dans le test UX |
| Picking et actions sur surface | Validé | Prototype | Widgets d'action et déplacement local ; contrôles complexes incomplets |
| Contrôles AZERTY/QWERTY/personnalisés | Validé | Fonctionnel | Persistance, migration et auto-test UX |
| Regard libre et inversion souris | Validé | Prototype | Fonctionne sans bouton ; pas encore de recentrage infini du pointeur |
| Monde 3D plein écran et chunks | Validé | Prototype | Rendu/grille ; collisions, gravité et streaming absents |
| Scratching 2D/3D | Validé | Prototype avancé | Translation, rotation, échelle, surfaces liées et historique |
| Entité Universelle | Validé | Fondation | Source physique/conceptuelle ; certaines vues restent des caches compatibles |
| Nexus | Partiel | Visualisation | Vues présentes ; édition relationnelle avancée à poursuivre |
| Zones et espaces réseau | Partiel | Modèle local | Quatre localités et profils ; synchronisation réseau réelle absente |
| Overworld | Planifié | Architecture | Agrégation/streaming distribué non implémentés |
| FractalBridge | Partiel | Bus local | Événements internes actifs ; connecteurs externes déclaratifs |
| Automatisations visuelles | Partiel | Éditeur sûr | Simulation/configuration ; exécution arbitraire volontairement désactivée |
| OwnerManagementPanel | Validé | Fonctionnel localement | Propriété, visibilité, seed, spawn, audit et publication déclarative |
| RequestSystem / PactSystem | Planifié | Future phase | Pactes internes non juridiques uniquement |
| Tests HUD | Validé | Automatisé | `--self-test` |
| Tests du workflow utilisateur | Validé | Automatisé + UI | `--ux-self-test` et smoke test Windows UI Automation |
| Tests AIONE | Validé | Automatisé | 90/90 au 23 juin 2026 |
| Git | Bloqué | Infrastructure | `.git/index.lock` impossible à créer dans le dépôt actuel |

## Définition des niveaux

- Fonctionnel : utilisable dans le workflow actuel et persisté.
- Prototype avancé : chaîne principale opérationnelle, cas complexes encore limités.
- Fondation : modèle et invariants disponibles pour les fonctions suivantes.
- Visualisation : lecture opérationnelle, édition complète non garantie.
- Planifié : architecture documentée mais non implémentée.

Une fonction n'est marquée « Validé » que si elle possède une validation réelle dans la session ou dans les auto-tests du projet.
