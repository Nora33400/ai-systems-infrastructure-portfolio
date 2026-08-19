# FractalOS — Spécification détaillée
## Espaces 3D connectés, panneau propriétaire, demandes et contrats système
**Version 0.1 — Document de conception fonctionnelle et technique**  
**Date :** 22 juin 2026

> Objectif : transformer les idées InterSpace + Panneau propriétaire + Contrats FractalOS en documentation claire, implémentable et testable.

## Table des matières
1. Résumé exécutif
2. Glossaire
3. Principes fondateurs
4. Espaces 3D comme maps possédées
5. Types d’hébergement
6. Visibilité et droits
7. Attacher vs relier
8. Chargement inter-espace rapide
9. Transfert d’objets et de fichiers
10. Conteneurs inter-espaces
11. Flux d’objets
12. Données liées
13. Contrats de connexion entre espaces
14. Fractal Scratch Editor
15. Panneau propriétaire
16. Système de demandes
17. Relations et permissions
18. Contrats/Pactes système
19. Effets de non-respect
20. Modèles JSON
21. Architecture technique
22. Sécurité, abus et garde-fous
23. UX HUD permanent
24. Roadmap
25. Tests et smoke tests
26. Prompt dev consolidé

## 1. Résumé exécutif
FractalOS repose sur une idée centrale : un espace 3D est une map possédée, hébergée et gouvernée. Cette map peut être privée, publique, réservée à un groupe, attachée à d’autres maps, reliée par téléportation, ou synchronisée par des flux d’objets et de données. Le HUD permanent 2D sert d’interface racine pour utiliser, configurer, publier et administrer ces espaces.
Le système propriétaire ajoute une couche sociale : chaque propriétaire reçoit des demandes, crée des relations, attribue des permissions et peut proposer des pactes système. Ces pactes ne sont pas des contrats juridiques réels ; ils engagent seulement des fonctions internes à FractalOS : accès, titres, limitations, responsabilités et historique.

## 2. Glossaire
| Terme | Définition |
| --- | --- |
| Espace 3D / Map | Un monde navigable avec propriétaire, hôte, visibilité, objets, scripts, flux et HUD publié. |
| Propriétaire | Utilisateur, groupe ou entité qui contrôle les règles de l’espace. |
| HUD permanent 2D | Couche d’interface toujours disponible : navigation, demandes, contrats, crédits, inventaire, gestion. |
| Attacher | Placer deux espaces côte à côte avec continuité spatiale. |
| Relier | Connecter deux espaces par portail, téléportation, lien réseau ou terminal. |
| Conteneur inter-espace | Stock logique capable de recevoir, envoyer ou exposer des objets entre maps. |
| Flux | Transfert manuel, planifié, conditionnel ou continu d’objets/données. |
| Pacte système | Accord interne non légal qui donne/limite des fonctions FractalOS. |
| Demande X | Demande personnalisée extensible : ami, chat, image, équipe, association, espace, contrat. |

## 3. Principes fondateurs
- Un espace 3D est une map possédée, pas seulement une scène visuelle.
- Une map peut être hébergée par FractalOS, par un serveur local, par un groupe, ou par un hébergeur partenaire.
- Le propriétaire décide de la visibilité : privé, public, groupe sélectionné, local privé, local public.
- Les maps peuvent être attachées physiquement ou reliées logiquement.
- Les objets, assets, fichiers et données peuvent circuler entre espaces selon des contrats de permissions.
- Le HUD permanent reste la couche centrale pour gérer l’usage, les demandes, les flux et les droits.
- Un pacte FractalOS n’est pas un contrat légal : il limite ou débloque seulement des fonctions internes.
- Le système doit éviter la honte publique automatique : les statuts négatifs sont privés ou semi-privés par défaut.

## 4. Espaces 3D comme maps possédées
Chaque espace 3D est une unité de monde. Il contient une scène, des objets, des règles, un état, une configuration de HUD publiée, des permissions et éventuellement des connexions vers d’autres espaces. Le propriétaire peut créer plusieurs maps, les connecter, les cloner, les publier, les garder privées ou les réserver à une équipe.

Un espace doit donc être identifié par : `space_id`, `owner_id`, `host_server_id`, `visibility_mode`, `published_hud_config_id`, `connection_list`, `permission_policy`, `storage_policy`, `economy_policy` et `audit_log`.

## 5. Types d’hébergement
Les espaces peuvent être contrôlés par différents hôtes : serveur FractalOS officiel, hébergeur local, serveur privé, serveur partenaire, serveur de groupe, instance événementielle. Chaque hôte expose des capacités différentes : disponibilité, stockage, nombre d’utilisateurs, bande passante, latence, règles de scripts, politique économique, sauvegardes et modération.

Un espace local privé peut fonctionner même avec un réseau limité. Un espace public global doit au contraire être indexé, modéré, sauvegardé et préchargeable.

## 6. Visibilité et droits d’accès
La visibilité d’un espace détermine qui peut le voir, y entrer et interagir. Les droits d’accès doivent être séparés des droits d’édition. Un visiteur public peut voir et utiliser, mais pas modifier. Un éditeur peut modifier certains modules. Un co-propriétaire peut gérer plus largement l’espace. Le propriétaire garde le contrôle ultime sauf transfert volontaire de propriété.

### Modes de visibilité recommandés
| Mode | Usage | Accès typique |
| --- | --- | --- |
| Privé | Atelier personnel, test, stockage | Propriétaire seulement |
| Public | Galerie, boutique, espace social | Tout utilisateur autorisé par serveur |
| Groupe sélectionné | Équipe, cercle privé, bêta-test | Liste blanche |
| Local privé | Machine personnelle / réseau domestique | Compte local ou LAN |
| Local public | Partage de proximité | Utilisateurs du réseau local |
| Marchand | Vente/échange d’assets | Visiteurs + règles économiques |
| Système | Espace géré par FractalOS | Règles globales |

## 7. Attacher vs relier des espaces
Attacher signifie créer une continuité spatiale : deux maps sont placées l’une à côté de l’autre, avec une porte, un couloir, un pont ou une zone de transition. Relier signifie créer une connexion logique sans proximité géométrique : portail, téléporteur, lien HUD, terminal, adresse fractale, ascenseur inter-espace.

Cette distinction est fondamentale pour l’expérience utilisateur. Attacher donne l’impression de marcher entre maps. Relier donne l’impression de voyager entre systèmes.

### Comparaison
| Connexion | Définition | Exemple | Difficulté technique |
| --- | --- | --- | --- |
| Attacher | Continuité géométrique entre maps | Maison ↔ Jardin ↔ Marché | Collision, streaming, frontières |
| Relier | Lien logique avec transition | Portail vers boutique distante | Handshake serveur, droits, cache |
| Flux | Connexion invisible de transport | Usine A envoie vers boutique B | File d’attente, quotas, logs |
| Lien de données | Partage ou miroir d’une variable | Stock global partagé | Conflits de synchronisation |

## 8. Chargement inter-espace rapide
Pour beaucoup d’utilisateurs et de serveurs, FractalOS doit éviter le chargement brutal. Le système doit précharger les métadonnées des espaces voisins, réserver une session côté serveur cible, charger les assets essentiels, puis streamer progressivement les détails. Le HUD doit afficher l’état : accès autorisé, chargement, serveur distant, file d’attente, erreur ou fallback.

Un InterSpaceGateway gère : découverte, access check, handshake, preload, cache local, session transfer et restauration du contexte utilisateur.

```text
Utilisateur approche d’un portail
→ préchargement metadata espace cible
→ vérification permissions
→ handshake serveur cible
→ préparation HUD publié
→ transition visuelle
→ streaming progressif des assets
→ entrée dans l’espace cible
```

## 9. Transfert d’objets, fichiers et assets
FractalOS doit permettre de déplacer des éléments entre maps. Quatre méthodes sont prévues : livraison interne, déménagement par lot, export/import de fichier `.fractalpack`, transfert serveur-à-serveur. Chaque transfert doit être signé, journalisé et limité par permissions.

### Méthodes de transfert
| Méthode | Description | Cas d’usage |
| --- | --- | --- |
| Livraison | Envoyer un ou plusieurs objets vers une destination | Objet acheté, ressource envoyée |
| Déménagement | Déplacer un lot dans un conteneur | Migration d’atelier, stockage |
| Export/import | Créer un paquet `.fractalpack` | Partage hors ligne, sauvegarde |
| Serveur-à-serveur | Transfert direct avec contrat | Économie inter-espaces |

## 10. Conteneurs inter-espaces
Un conteneur inter-espace est un stock logique. Il peut recevoir des objets, exposer une partie de son stock, envoyer automatiquement des lots, ou agir comme tampon entre deux maps. Il peut appartenir à un espace, à un utilisateur ou à un groupe. Le conteneur doit connaître ses règles : stock minimum, stock maximum, flux par période, délai, coût, droits de lecture/écriture et historique.

### Exemple RandomBox
```text
Espace A : Script RandomBox crée des boîtes
→ Conteneur_A_RandomBox stocke les boîtes
→ Contrat A→B autorise la réception
→ Flux envoie 20 boîtes / heure
→ Espace B reçoit dans Entrepôt_B
→ Boutique B vend ou distribue
```

## 11. Flux d’objets
Les flux peuvent être manuels, planifiés, conditionnels ou continus. Le système doit pouvoir régler quantité, fréquence, délai, priorité, coût, stock source minimum, stock cible maximum, visibilité et révocation. Le flux doit être visible depuis le HUD propriétaire et modifiable via l’éditeur Scratch.

| Type de flux | Règle | Exemple |
| --- | --- | --- |
| Manuel | Déclenché à la demande | Envoyer 10 boîtes maintenant |
| Planifié | Répété selon un intervalle | 20 boîtes toutes les 6h |
| Conditionnel | Déclenché selon état | Si stock B < 50, envoyer 25 |
| Continu | Débit régulier | 5 unités/min, max 100/h |

## 12. Données liées entre espaces
Certaines données peuvent être liées : inventaire partagé, compteur de production, mission, niveau, historique, score, réputation, météo, statut de script ou état d’objet. Il faut distinguer quatre modes : copie, synchronisation, miroir, délégation.

| Mode | Effet | Exemple |
| --- | --- | --- |
| Copie | La donnée est copiée puis vit séparément | Exporter une configuration |
| Synchronisée | Plusieurs espaces partagent une valeur | Stock global |
| Miroir | Un espace lit sans modifier | Boutique B affiche stock A |
| Déléguée | Un espace demande une action à un autre | B demande production à A |

## 13. Contrats de connexion entre espaces
Chaque connexion inter-espace doit être représentée par un contrat de connexion. Ce contrat définit source, cible, type, permissions, quotas, durée, conditions de révocation, historique, logs et effets en cas d’erreur. Une connexion n’accorde jamais un accès total : elle accorde seulement des droits précis.

### Permissions typiques
- Lire stock
- Recevoir objets
- Envoyer objets
- Créer objets
- Supprimer objets
- Déclencher script
- Modifier flux
- Voir historique
- Révoquer connexion

## 14. Fractal Scratch Editor
L’édition scratching est une interface nodale permettant de configurer des flux sans coder. Le propriétaire connecte des blocs : script, conteneur, filtre, délai, permission, destination, conversion économique. Cette interface doit générer une configuration lisible et testable, pas seulement un dessin.

```text
[Script RandomBox]
        ↓
[Conteneur A]
        ↓ quantité : 30
[Delay : 15 min]
        ↓
[Permission Check]
        ↓
[Entrepôt B]
```

## 15. Panneau propriétaire
Chaque propriétaire d’espace possède un panneau de gestion dans le HUD permanent. Il centralise demandes, relations, permissions, contrats, accès, connexions inter-espaces, transferts, associations, équipes et historique. Ce panneau est la console administrative de l’espace.

| Onglet | Contenu |
| --- | --- |
| Demandes | Ami, chat, image, association, équipe, connexion espace, contrat, X |
| Relations | Amis, associés, membres, équipes, groupes, bloqués |
| Contrats | En attente, actifs, à régulariser, expirés, archivés |
| Permissions | Visiteurs, éditeurs, co-propriétaires, scripts, assets, crédits |
| InterSpace | Connexions, flux, conteneurs, livraisons, data links |
| Historique | Décisions, acceptations, refus, modifications, révocations |

## 16. Système de demandes
Une demande est un objet système structuré : type, demandeur, destinataire, espace concerné, message, permissions demandées, durée, contrat associé, statut, expiration, historique. Le propriétaire peut accepter, refuser, bloquer, archiver ou faire une contre-proposition.

| Type | Description | Permissions possibles |
| --- | --- | --- |
| Ami | Relation personnelle ou sociale | voir présence, envoyer message |
| Chat | Ouverture d’un canal de discussion | chat privé, chat équipe |
| Image | Demande d’envoi ou d’affichage visuel | voir, importer, publier |
| Association | Lien de collaboration souple | proposer asset, accès salon |
| Équipe | Participation structurée | éditer, tester, valider |
| Connexion espace | Relier deux maps | flux, portail, data link |
| Contrat | Créer un pacte système | droits liés au pacte |
| X | Demande personnalisée | définie par module/addon |

## 17. Relations et permissions
Les relations ne doivent pas être seulement des labels sociaux. Chaque relation correspond à un profil de permissions. Un ami n’est pas forcément un éditeur. Un associé n’est pas forcément un co-propriétaire. Une équipe peut donner un accès temporaire à certains outils seulement.

| Relation | Droits typiques | Limites |
| --- | --- | --- |
| Ami | chat, présence, invitation | pas d’édition par défaut |
| Associé | proposer assets, accéder salon | validation propriétaire |
| Équipe | tester, commenter, éditer limité | scope par projet |
| Éditeur | modifier certains objets | pas de transfert propriété |
| Co-propriétaire | gestion avancée | risque élevé, validation forte |
| Bloqué | aucune demande directe | historique conservé |

## 18. Contrats / pactes système
Les contrats FractalOS doivent être présentés comme des pactes système non juridiquement contraignants. Ils ne remplacent pas un contrat réel. Ils servent à formaliser des règles internes : droits, responsabilités, durée, récompenses, limitations, titres, visibilité et historique.

Un pacte peut être à sens unique, partagé, personnalisé ou appliqué à soi-même. Les deux personnes concernées restent responsables de leurs décisions lorsqu’elles acceptent un pacte mutuel.

| Type de pacte | Description | Exemple |
| --- | --- | --- |
| Sens unique | Une personne donne un cadre à une autre | Droit de tester un espace 7 jours |
| Self-pact | Engagement envers soi-même | Finir 3 tâches cette semaine |
| Partagé | Même contrat pour les deux | Collaboration 50/50 |
| Personnalisé | Rôles différents par participant | Nora propriétaire, Léo asset creator |
| Template | Modèle réutilisable | Contrat testeur, contrat vendeur |

## 19. Effets de non-respect
Si un pacte n’est pas respecté, FractalOS peut limiter certaines fonctions internes. Les effets doivent être proportionnés, réversibles et non humiliants par défaut. Les statuts négatifs doivent être privés ou visibles seulement des participants, sauf choix explicite et modéré.

| Effet | Recommandation |
| --- | --- |
| Limiter création de contrats | Oui, temporairement |
| Suspendre vente d’assets | Oui, si lié au pacte |
| Bloquer accès de base | Non |
| Titre public humiliant | Non par défaut |
| Titre neutre | Oui : Pacte à régulariser |
| Restauration après régularisation | Oui |

## 20. Workflows complets
Les workflows ci-dessous servent de base aux tests et à l’implémentation. Ils montrent comment les espaces, demandes, pactes et flux s’enchaînent.

### Workflow A — Connexion de deux espaces
- Le propriétaire de B demande une connexion à A.
- Le propriétaire de A reçoit une demande InterSpace.
- A vérifie les permissions demandées : lire stock, recevoir objets, voir historique.
- A propose un contrat de connexion limité.
- B accepte.
- Le SpaceConnectionContract est créé.
- Le flux d’objets peut démarrer.

### Workflow B — Association utilisateur
- Léo demande une association à Nora.
- La demande contient chat équipe + proposer assets + partage revenus.
- Nora répond par contre-proposition : 14 jours, 10 assets max, 15 %.
- Léo accepte.
- Le pacte personnalisé est actif.
- Les permissions sont accordées automatiquement.
- Si le pacte est rompu, seules les permissions liées sont suspendues.

## 21. Modèles JSON
Les modèles ci-dessous sont simplifiés. Ils servent à documenter les entités centrales, pas à figer définitivement l’implémentation.

### space
```json
{
  "id": "space_a",
  "name": "Atelier RandomBox",
  "owner_id": "user_nora",
  "host": "local_server_01",
  "visibility": "private",
  "published_hud_config": "hud_config_a"
}
```

### connection
```json
{
  "id": "conn_a_to_b_boxes",
  "type": "object_flow",
  "source_space": "space_a",
  "target_space": "space_b",
  "source_container": "container_randombox_a",
  "target_container": "warehouse_boxes_b",
  "permissions": {
    "target_can_read_stock": true,
    "target_can_receive": true,
    "target_can_modify_source_script": false
  },
  "flow_rules": {
    "quantity": 20,
    "frequency": "1h",
    "delivery_delay": "10m",
    "target_min_stock": 30,
    "target_max_stock": 200
  }
}
```

### request
```json
{
  "id": "req_001",
  "type": "association",
  "from_user": "user_leo",
  "to_owner": "user_nora",
  "space_id": "space_gallery_fractal",
  "message": "Je veux proposer des assets pour ta galerie.",
  "requested_permissions": [
    "chat.team",
    "asset.propose",
    "credit.revenue_share"
  ],
  "status": "pending",
  "attached_pact_id": "pact_001"
}
```

### pact
```json
{
  "id": "pact_001",
  "type": "personalized",
  "legal_binding": false,
  "system_binding": true,
  "participants": [
    {
      "user_id": "user_nora",
      "role": "owner",
      "permissions": [
        "asset.validate",
        "space.manage",
        "pact.close"
      ]
    },
    {
      "user_id": "user_leo",
      "role": "associate",
      "permissions": [
        "asset.propose",
        "chat.team"
      ]
    }
  ],
  "duration": "14d",
  "failure_effects": {
    "limit_permissions": [
      "asset.propose",
      "credit.revenue_share"
    ],
    "title": "Pacte à régulariser",
    "visibility": "participants_only"
  }
}
```

## 22. Architecture technique recommandée
L’architecture doit séparer l’affichage, les données, les permissions et les flux. Un module ne doit pas être lié à une fenêtre unique. Un espace ne doit pas être lié à un serveur unique sans abstraction. Un pacte ne doit pas être seulement du texte : il doit appliquer des permissions système vérifiables.

```text
FractalOS
├─ PermanentHud2D
├─ SpaceRegistry
├─ SpaceConnectionManager
├─ InterSpaceGateway
├─ InterSpaceTransferService
├─ InterSpaceContainerSystem
├─ DataLinkSystem
├─ OwnerManagementPanel
├─ RequestSystem
├─ RelationshipManager
├─ PactSystem
├─ PermissionEngine
├─ ReputationTitleSystem
└─ FractalScratchEditor
```

## 23. Sécurité, abus et garde-fous
Les connexions sociales, contrats, images, scripts, transferts et monnaies internes créent des risques. Les garde-fous doivent être intégrés dès le début : permissions minimales, révocation, sandbox scripts, anti-spam des demandes, visibilité contrôlée des statuts, logs, limites de flux, confirmation pour co-propriété, exports signés et contrôle parental/modération si espaces publics.

| Risque | Garde-fou |
| --- | --- |
| Spam de demandes | limite par période, blocage, filtre par type |
| Vol d’asset | permissions lecture/export séparées, logs |
| Script malveillant | sandbox, permissions explicites, revue |
| Humiliation par titres | visibilité privée par défaut |
| Connexion inter-espace abusive | contrat révocable, quotas |
| Donnée sensible exposée | mode miroir sans écriture, consentement |

## 24. UX HUD permanent
Le HUD permanent doit donner accès à : demandes, contrats, relations, espaces, flux, livraisons, inventaire, crédits, notifications, erreurs et configuration. En mode propriétaire, il affiche les outils d’édition et d’administration. En mode visiteur, il affiche uniquement l’interface publiée par le propriétaire.

### Vue propriétaire recommandée
- Boîte de réception des demandes
- Contrats actifs
- Connexions inter-espaces
- Flux et conteneurs
- Permissions par rôle
- Journal d’activité
- Actions rapides : accepter, refuser, contre-proposer, suspendre, révoquer

## 25. Roadmap de développement
La roadmap doit commencer par les entités de données et les permissions, puis l’interface, puis les flux automatiques. Le système de contrat doit exister avant les transferts inter-espaces publics afin d’éviter des connexions sans gouvernance.

1. SpaceRegistry + VisibilityMode
2. OwnerManagementPanel minimal
3. RequestSystem + statuts
4. RelationshipManager + PermissionEngine
5. PactSystem non légal
6. SpaceConnectionContract
7. InterSpaceContainerSystem
8. Manual Transfer
9. ObjectFlow planifié
10. DataLinkSystem
11. FractalScratchEditor
12. Fast InterSpace Gateway
13. Tests complets + logs + audit

## 26. Tests et smoke tests
Les tests doivent valider les comportements métier, pas seulement le lancement de l’application. Chaque fonction importante doit avoir un cas propriétaire, un cas visiteur, un cas refusé, un cas révocation et un cas persistance.

| Test | Résultat attendu |
| --- | --- |
| Créer espace A/B | IDs uniques, propriétaires corrects |
| Demande connexion A→B | Demande visible dans panneau propriétaire |
| Contrat accepté | Permissions appliquées |
| Flux 20/h | Transferts respectent fréquence et stock max |
| Révocation | Flux stoppé, droits retirés |
| Demande association | Contre-proposition possible |
| Pacte personnalisé | Droits différents par participant |
| Non-respect pacte | Limitation proportionnée, accès de base conservé |
| Sauvegarde/reload | Contrats, demandes et flux restaurés |

## 27. Prompt dev consolidé
Le prompt suivant peut être donné à une IA de code ou à un développeur pour transformer cette spécification en tâches d’implémentation.

```text
Implémente dans FractalOS un système InterSpace + OwnerManagement + PactSystem.
Objectif : gérer des espaces 3D comme maps possédées, hébergées, visibles selon droits, connectables entre elles, avec transferts d’objets/données, demandes utilisateurs, relations et pactes système non juridiques.
Créer : SpaceRegistry, VisibilityMode, SpaceConnectionManager, InterSpaceGateway, InterSpaceTransferService, InterSpaceContainerSystem, DataLinkSystem, OwnerManagementPanel, RequestSystem, RelationshipManager, PactSystem, PermissionEngine, ReputationTitleSystem, FractalScratchEditor.
Tester : création espaces, propriétaires, demandes, contre-propositions, contrats, permissions, flux, stock min/max, révocation, sauvegarde/rechargement, mode propriétaire vs visiteur.
Contraintes : aucun pacte n’est un contrat légal réel ; pas de titre humiliant public par défaut ; accès de base toujours conservé ; scripts sandboxés ; exports et connexions journalisés.
```

## 28. Conclusion
Cette brique transforme FractalOS en réseau de maps possédées et connectées. Les espaces peuvent produire, stocker, transférer, vendre, partager et synchroniser. Le propriétaire administre demandes, relations et contrats depuis le HUD permanent. Les pactes système donnent une structure aux collaborations sans prétendre être des contrats juridiques. La prochaine étape est de convertir cette documentation en tâches GitHub, classes, fichiers et tests automatisés.
