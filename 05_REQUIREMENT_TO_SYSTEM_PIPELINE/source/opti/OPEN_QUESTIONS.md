# Questions ouvertes globales

## Critiques — sources

### OQ-0001 — Où est la conversation historique complète ?

Elle est annoncée comme la seule source officielle détaillant l'architecture, mais n'est pas dans le dépôt. Sans elle, la reconstruction fidèle ne peut pas dépasser l'amorce. Impact : tous les modules.

### OQ-0002 — Quels énoncés viennent de l'utilisateur et lesquels sont des propositions de l'assistant ?

`SRC-0001` est un extrait composite. La segmentation par locuteur et par tour est nécessaire pour distinguer intention, acceptation, objection et suggestion.

## Critiques — architecture

### OQ-0003 — Définition positive des modules protégés

Quelles responsabilités propres justifient la séparation de MODA, Cohérental, CorrexAI et CalContexte ?

### OQ-0004 — Contrat réel de TileMindFS

Le contrat WorkMesh `TSK-P1-015` @ `3a253f0` répond pour une tranche locale bornée à l'identité, l'index, la température logique, la compaction et la récupération. Restent ouverts : définition historique complète, service persistant, cohérence concurrente, tiering physique RAM/NVMe/GPU et migration opti.

### OQ-0005 — Contrat réel de CalContexte

Le contrat WorkMesh `TSK-P1-016` @ `34b3e0e` répond pour une tranche locale bornée : contexte-objet à dix dimensions sourcées/absentes, sélection lexicale d'enregistrements TileMindFS v1, exclusions, budget, dépendances, contradictions actives et compilation intègre. Restent ouverts : définition historique complète, autorité des sources, sémantique, poids et seuils, politiques multi-horizons, adaptation aux formats opti et intégration globale.

### OQ-0006 — Fonctionnement précis de DORA

Le corpus signale lui-même que cette connaissance manque.

### OQ-0011 — Autorité des quatre reconstructions ajoutées

Quels éléments de `SRC-0003` à `SRC-0006` reformulent fidèlement des décisions antérieures, lesquels sont des extensions acceptées, et lesquels restent de simples propositions de l'assistant ?

### OQ-0012 — Frontière CorrexAI / Cohérental / IMMUNE

Les extraits permettent une séparation candidate — vérification logique, homéostasie de cohérence, gestion distribuée des erreurs — mais les contrats d'escalade et les chevauchements doivent être validés.

### OQ-0013 — Cognitive Fabric ou Cognitive Bus

S'agit-il d'un nouveau module accepté, d'un alias d'Agent Fabric/EventBus, ou d'une proposition à rejeter ?

### OQ-0014 — Reflexive Witness

Le témoin réflexif est-il un module autonome, un sous-module de RPL ou une fonction de traçabilité transversale ?

### OQ-0015 — ExceptionProtocol et EDP

Le `ExceptionProtocol` de `SRC-0006` désigne-t-il EDP, une autorité distincte, ou une famille plus large de protocoles ? Ne pas fusionner avant réponse.

### OQ-0016 — « Boda » signifie-t-il MODA ?

`SRC-0006` en fait l'hypothèse explicitement. La correspondance n'est pas validée.

### OQ-0007 — Sémantique propre de TimeWarp

Le contrat WorkMesh `TSK-P1-017` @ `c242196` répond pour une tranche locale bornée à la continuité causale : événements, snapshots, divergences et plans de reprise/rollback non exécutables. Restent ouverts : propriété positive distinguant TimeWarp d'un simulateur générique, branches et fusions, simulations futures, réintégration de décision, signatures, namespace canonique, lignée arborescente, restauration séparément autorisée et service persistant.

### OQ-0008 — Définition de la subjectivité opératoire

Quelles capacités observables la constituent, et quelles affirmations phénoménales sont explicitement exclues ?

## Méthode

### OQ-0009 — La séquence des cinq briques est-elle décidée ou seulement recommandée ?

Elle est formulée comme une proposition dans `SRC-0002`; le registre conserve donc `PROPOSED_SEQUENCE`.

### OQ-0010 — Quel seuil autorise la Phase 1 d'implémentation des outils ?

Définir les niveaux minimaux de couverture, validation et stabilité nécessaires avant tout code.

## Infrastructure autonome

### OQ-0017 — Quel backend d'écriture portable doit remplacer ou compléter WSL ?

Le backend WSL est validé sur cet hôte soumis au contrôle d'accès Windows, mais sa portabilité doit être vérifiée sur un autre poste et sur un environnement sans WSL.

### OQ-0018 — Quelle politique Git appliquer après la première baseline ?

RÉSOLUE partiellement le 2026-07-23 par D-0037 et `SRC-0017` : la baseline protégée est `4c0e0a3`, tag `baseline-before-agentic-calendar`, et WQ-0045 peut créer des worktrees détachés puis des patches de proposition. `git.auto_commit` reste désactivé ; push, fusion et application automatique des patches restent interdits. Toute politique de commit autonome plus large exige une décision séparée.

## Cycle cognitif vertical

### OQ-0019 — Quel contrat sémantique doit compléter la sélection lexicale ?

La tranche expose `semantic: null`. Faut-il utiliser `nomic-embed-text`, un autre modèle local ou une méthode symbolique, et comment versionner puis tester ce sous-score sans masquer les autres critères ?

### OQ-0020 — Quelles règles générales doivent former les tiles au-delà de SRC-0001 ?

Le regroupement par sujet canonique est déterministe et suffisant pour le canari. WorkMesh ajoute un contrat de compaction/version/température borné, mais ne tranche toujours ni la granularité générale, ni la fusion/fission, ni la migration opti, ni le service persistant.

## GPT Cognitive Constitution v0.1

### OQ-0021 — Où interposer l'application constitutionnelle automatique ?

Le moteur v0.1 valide des objets, transitions, capacités, réponses et fixtures de façon pure. Quelles écritures cognitives doivent obligatoirement appeler ce garde avant persistance, et selon quelle migration non destructive ? Impact : pipeline cognitif, autonomie-engine, Organum candidat. Source : `SRC-0009:L77-L102`.

### OQ-0022 — Quel modèle de version unifie transitions et reprises ?

La preuve historique utilise une version d'exécution finale 2; la machine constitutionnelle prototype peut incrémenter chaque transition simulée. Faut-il distinguer `artifact_version`, `execution_revision` et `resume_revision` ? Aucune migration de la preuve n'est autorisée sans amendement. Source : `SRC-0009:L234-L242`, `SRC-0009:L442-L473`.

### OQ-0023 — Quelles capacités fonctionnelles supplémentaires peuvent être activées ?

La v0.1 n'active que les capacités prouvées par les tranches existantes et conserve les autres comme `PROPOSED` ou absentes. Chaque futur grant exige preuve, scope, validation indépendante et tests négatifs. Source : `SRC-0009:L350-L385`.

## Nœud organisationnel vivant

### OQ-0024 — Quelle surface fait autorité sur les tâches ?

RÉSOLUE le 2026-07-18 par D-0018 et `SRC-0012:L7-L29` : les registres opti sont canoniques, SQLite porte l'exécution et Trello est une projection optionnelle. La politique détaillée de conflits reste un critère de WQ-0037/WQ-0038, pas une remise en question de l'autorité canonique.

### OQ-0025 — Quelle identité relie les objets externes ?

Valider l'utilisation de `AIONE Task ID` comme clé de corrélation et définir les règles de création, fusion, duplication, archivage et migration des cartes, événements, fils e-mail, fichiers, issues et threads Codex. Sources : `SRC-0007:L118-L140`, `SRC-0010:L7-L14`.

### OQ-0026 — Quelles permissions et données privées sont autorisées ?

Décider, pour Gmail, Calendar, Drive, Notion, GitHub, Trello et Codex, quels comptes, projets, dossiers, calendriers, labels et champs peuvent être lus, résumés, copiés ou modifiés. Les contenus privés complets et secrets restent exclus par défaut. Sources : `SRC-0005:L1107-L1113`, `SRC-0011:L13-L20`.

### OQ-0027 — Quel périmètre Trello faut-il créer ?

Quel Workspace, quel nom de tableau, quels membres et quel niveau d'abonnement utiliser ? Faut-il un tableau portefeuille unique, un tableau par projet, ou un tableau portefeuille plus des tableaux projet ? La structure de listes et champs proposée ne vaut pas décision. Sources : `SRC-0010:L7-L14`, `SRC-0011:L7-L15`.

### OQ-0028 — Où héberger le callback et les secrets Trello ?

Les webhooks exigent une URL HTTPS accessible et une autorisation OAuth ou jeton. Définir l'hébergement, le stockage des secrets, la rotation, la vérification des signatures, la reprise et le mode dégradé avant toute synchronisation. Source : `SRC-0011:L7-L15`.

## Gouverneur local et ressources

### OQ-0029 — Quels signaux locaux peuvent autoriser une bascule matérielle réelle ?

La Phase 2 observe `nvidia-smi` et accepte des signaux explicites d'activité, plein écran et jeu, mais ne contrôle aucun processus. Avant toute bascule, définir la source fiable de l'activité the owner, les seuils, l'hystérésis, les checkpoints et le rollback. Source : `SRC-0013:L159-L178`.

### OQ-0030 — Quand et comment introduire LiteLLM ?

LiteLLM est demandé comme cible prioritaire de routage mais n'est pas installé lors de l'audit local du 2026-07-18. Décider séparément l'installation, les fournisseurs permis, les secrets, les budgets, le mode hors ligne et la phase d'intégration. Source : `SRC-0013:L127-L157`, `SRC-0013:L180-L184`.

## Kernel et évolution récursive

### OQ-0031 — Quelle frontière sépare Agent Factory et Agent Fabric ?

L'Agent Factory est proposée comme configuration générique d'exécuteurs tandis qu'Agent Fabric possède une identité conceptuelle historique partiellement définie. Déterminer rôles, capacités, version, révocation et relation sans les déclarer alias. Source : `SRC-0014:L102-L116`.

### OQ-0032 — Quel besoin justifierait une Registry Facade ou une migration de stockage ?

Les fichiers versionnés sont canoniques et SQLite porte l'exécution. Définir les requêtes ou contraintes impossibles à satisfaire par cette fédération avant d'introduire PostgreSQL ou une nouvelle base. Source : `SRC-0014:L74-L78`.

### OQ-0033 — Quelles données peuvent constituer un profil opérationnel de the owner ?

Décider catégories autorisées, provenance, durée de conservation, correction, export, révocation et accès. Sans preuve, « que ferait the owner ? » reste `UNKNOWN`; le profil ne doit pas être fusionné avec Personality, subjectivité ou identité. Source : `SRC-0014:L96-L100`.

### OQ-0034 — Quelles métriques rendent Budget et Energy opératoires ?

Définir unités, sources de mesure, seuils, fenêtres, coûts de collecte et effets autorisés avant que fatigue GPU, modèle, projet, mémoire ou utilisateur influence une décision. Source : `SRC-0014:L84-L88`.

## Orchestration connectée et capacité

### OQ-0035 — Quel compte Google Agenda est autorisé ?

RÉSOLUE par D-0032 et `SRC-0016:L9-L9` : le profil `the configured owner profile` est le calendrier principal autorisé. Toute écriture ou modification d'événement personnel reste séparément bornée.

### OQ-0036 — Quel premier lot Trello peut être écrit ?

RÉSOLUE pour le pilote par D-0033 et `SRC-0016:L10-L12` : une seule carte peut être créée après snapshot, contrôle de doublon et dry-run validé. Toute restructuration ou second lot reste hors de cette autorisation.

### OQ-0037 — Faut-il initialiser Git dans WorkMesh Forge ?

RÉSOLUE par D-0034 et `SRC-0016:L11-L11` : WorkMesh doit avoir un dépôt Git local indépendant. Aucun remote ou push n'est implicite.

### OQ-0038 — Quelles données de capacité personnelle peuvent être utilisées ?

Définir sources Agenda, catégories privées, granularité, conservation, correction et visibilité avant de calculer une capacité de the owner ou une prévision. Source : `SRC-0015:L57-L63`.
