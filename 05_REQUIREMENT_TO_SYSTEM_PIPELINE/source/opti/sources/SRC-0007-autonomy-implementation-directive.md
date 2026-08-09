# MISSION CODEX — CONSTRUIRE LA CONTINUITÉ AUTONOME DU DÉVELOPPEMENT

Tu travailles dans le projet :

`<LOCAL_WORKSPACE>`

La v0.1 documentaire existe déjà :

* 1 006 fichiers ;
* 902 fichiers Markdown ;
* 101 fichiers YAML ;
* 3 schémas JSON ;
* 37 modules et 12 sous-modules ;
* 37 contrats machine ;
* 27 reconstructions détaillées ;
* un graphe de 43 nœuds ;
* 6 sources préservées avec empreintes SHA-256 ;
* validation YAML, JSON, contrats, graphe et liens locaux réussie ;
* aucun code métier produit.

Les points d’entrée actuels sont notamment :

* `README.md`
* `PROJECT_STATE.md`
* `MASTER_MODULE_REGISTRY.yaml`
* `ARCHITECTURE_GRAPH.yaml`
* `WORK_QUEUE.yaml`
* `AGENTS.md`
* `ASSUMPTION_REGISTER.md`

## Correction de priorité

La prochaine étape prioritaire ne doit pas être l’atomisation exhaustive ligne par ligne des six sources.

Cette atomisation peut rester dans la file de travail, mais elle ne doit pas bloquer la construction du système.

La priorité absolue est maintenant de construire une première infrastructure autonome capable de :

1. lire la documentation existante ;
2. identifier une tâche réalisable ;
3. construire le contexte nécessaire ;
4. transmettre cette tâche à un agent codeur Ollama local ;
5. autoriser cet agent à consulter et modifier le projet de manière contrôlée ;
6. exécuter les tests et validations ;
7. corriger les erreurs ;
8. enregistrer les résultats ;
9. choisir automatiquement la tâche suivante ;
10. poursuivre sans nouvelle session Codex et sans validation humaine entre chaque tâche.

## Sens exact de « une seule itération »

Tu peux effectuer autant d’étapes internes que nécessaire durant la session Codex actuelle.

En revanche, le résultat de cette session doit être un système local persistant qui continue le développement après ton départ.

Il ne faut pas seulement générer :

* une architecture théorique ;
* une nouvelle documentation ;
* une simulation ;
* un script vide ;
* un orchestrateur contenant uniquement des stubs ;
* une démonstration qui s’arrête après une tâche fictive ;
* une file de tâches nécessitant que l’utilisateur relance Codex manuellement.

La dépendance aux futures itérations de Codex doit disparaître pour les tâches que l’agent local est capable de traiter.

## Objectif principal

Construire et démarrer un moteur d’autonomie local pour AIONE / La Forge, utilisant Ollama comme moteur de raisonnement et de génération de code.

Après ton intervention, l’utilisateur doit pouvoir lancer une commande locale unique, puis laisser le système :

* sélectionner les tâches ;
* analyser les dépendances ;
* charger le contexte ;
* coder ;
* tester ;
* examiner les résultats ;
* corriger ;
* sauvegarder l’état ;
* continuer.

Le fonctionnement par défaut est :

`GO BATCH OUI`

Cela signifie qu’aucune confirmation humaine n’est demandée entre deux tâches ordinaires.

## Principe architectural

Construis une tranche verticale réellement fonctionnelle avant d’étendre le système.

La première version doit utiliser un seul worker autonome séquentiel et fiable. Ne commence pas par un système distribué complexe ou plusieurs agents travaillant simultanément sur les mêmes fichiers.

La parallélisation pourra être ajoutée plus tard.

Le moteur doit au minimum posséder les composants suivants.

### 1. Chargeur documentaire

Créer un composant capable de lire et indexer les documents structurants :

* registre des modules ;
* graphe d’architecture ;
* contrats machine ;
* file de travail ;
* hypothèses ;
* statuts du projet ;
* dépendances entre modules ;
* critères d’acceptation ;
* fichiers liés à chaque tâche.

Il doit éviter de charger les 1 006 fichiers dans chaque prompt.

Il doit construire un paquet contextuel ciblé pour la tâche active.

### 2. Gestionnaire de tâches persistant

Créer une représentation persistante des tâches comprenant au minimum :

* identifiant ;
* titre ;
* module ;
* description ;
* dépendances ;
* priorité ;
* statut ;
* critères d’acceptation ;
* fichiers probablement concernés ;
* sources documentaires ;
* nombre de tentatives ;
* historique des exécutions ;
* blocages ;
* résultat des tests ;
* dernier agent ayant travaillé dessus ;
* date de mise à jour.

Statuts minimaux :

* `pending`
* `ready`
* `running`
* `testing`
* `reviewing`
* `completed`
* `retryable_failure`
* `blocked`
* `quarantined`
* `cancelled`

Le système doit reconstruire son état après fermeture, crash ou redémarrage du PC.

### 3. Planificateur de tâches

Le planificateur doit :

* lire les dépendances ;
* détecter les tâches prêtes ;
* éviter les tâches bloquées ;
* privilégier les briques d’infrastructure nécessaires aux autres modules ;
* limiter les conflits de fichiers ;
* sélectionner une tâche réalisable avec les capacités actuelles ;
* ne pas considérer une tâche hypothétique comme une exigence validée ;
* respecter la séparation entre proposé, hypothétique et normatif.

Il ne doit pas sélectionner une tâche dont les prérequis ne sont pas satisfaits.

### 4. Adaptateur Ollama

Créer un adaptateur configurable vers l’API locale Ollama.

Le modèle ne doit pas être figé dans le code. Le modèle par défaut peut être défini dans la configuration, avec possibilité de sélectionner notamment un modèle codeur déjà installé.

Prévoir au minimum :

* URL Ollama configurable ;
* nom du modèle configurable ;
* température ;
* taille maximale du contexte ;
* timeout ;
* nombre de tentatives ;
* journalisation ;
* vérification de disponibilité ;
* message d’erreur clair si Ollama est arrêté ;
* reprise automatique quand Ollama redevient disponible.

Ne jamais déclarer l’intégration Ollama fonctionnelle si seuls des mocks ont été utilisés.

Les mocks sont autorisés pour les tests unitaires, mais une validation réelle avec l’API Ollama locale est obligatoire.

### 5. Protocole d’actions de l’agent

L’agent local ne doit pas recevoir un simple prompt demandant « code cette tâche » puis renvoyer librement du texte.

Créer un protocole structuré, validé par schéma JSON, permettant au modèle de demander des actions.

Actions minimales :

* `list_directory`
* `read_file`
* `read_file_range`
* `search_text`
* `inspect_git_diff`
* `apply_patch`
* `create_file`
* `delete_file`
* `run_command`
* `run_tests`
* `report_blocker`
* `finish_task`

Chaque action doit être validée avant exécution.

Le moteur doit refuser :

* les chemins hors du workspace autorisé ;
* les chemins utilisant une traversée non autorisée ;
* les commandes destructrices globales ;
* l’accès non nécessaire aux secrets ;
* la suppression massive non justifiée ;
* les opérations système hors du projet ;
* les réponses ne respectant pas le schéma.

Si la réponse du modèle est invalide :

1. tenter une réparation structurée ;
2. redemander une sortie conforme ;
3. journaliser l’échec ;
4. arrêter ou mettre en quarantaine après le seuil configuré.

### 6. Boucle agentique

Implémenter réellement la machine d’état suivante :

`DISCOVER`

→ `SELECT_TASK`

→ `BUILD_CONTEXT`

→ `PLAN`

→ `EXECUTE_ACTION`

→ `OBSERVE_RESULT`

→ `EXECUTE_ACTION`

→ `RUN_TESTS`

→ `REVIEW_DIFF`

→ `FIX_IF_NEEDED`

→ `VALIDATE_ACCEPTANCE`

→ `SAVE_RESULT`

→ `SELECT_NEXT_TASK`

La boucle d’actions doit permettre à l’agent de :

* lire plusieurs fichiers ;
* rechercher des symboles ;
* modifier plusieurs fichiers ;
* lancer des commandes ;
* observer les erreurs ;
* corriger son travail ;
* relancer les tests ;
* terminer uniquement lorsque les critères d’acceptation sont vérifiés.

Ne limite pas arbitrairement chaque tâche à une seule réponse Ollama.

### 7. Exécution contrôlée des commandes

Créer un exécuteur de commandes limité au workspace.

Il doit :

* enregistrer la commande ;
* enregistrer le répertoire de travail ;
* capturer stdout ;
* capturer stderr ;
* capturer le code de sortie ;
* appliquer un timeout ;
* limiter la taille des sorties injectées au modèle ;
* conserver la sortie complète dans les logs ;
* détecter les processus bloqués ;
* pouvoir interrompre une commande ;
* empêcher les commandes explicitement interdites.

Prévoir une configuration des commandes autorisées ou des familles de commandes autorisées.

Le moteur peut utiliser PowerShell comme lanceur Windows, mais le cœur doit rester testable.

### 8. Validation et tests

Une tâche ne peut pas devenir `completed` uniquement parce que le modèle affirme qu’elle est terminée.

Le système doit vérifier :

* les critères d’acceptation documentaires ;
* les tests associés au module ;
* les tests nouvellement créés ;
* les validateurs YAML et JSON existants ;
* les contrats machine ;
* les liens locaux lorsque pertinent ;
* les erreurs de compilation ;
* les erreurs TypeScript ou Python selon le module ;
* le diff final ;
* l’absence de fichiers manifestement accidentels.

Une validation globale légère doit être exécutée après chaque tâche.

Une validation globale plus complète doit être configurable après un nombre déterminé de tâches.

### 9. Relecteur automatique

Après le codage, lancer une phase de revue distincte.

Le relecteur doit vérifier au minimum :

* conformité à la tâche ;
* absence de régression évidente ;
* erreurs logiques ;
* tests manquants ;
* gestion d’erreurs ;
* sécurité des chemins et commandes ;
* cohérence avec les contrats ;
* apparition de nouveaux `TODO`, mocks ou stubs injustifiés ;
* modifications hors périmètre.

Le relecteur peut employer le même modèle Ollama avec un rôle et un prompt différents.

Il ne doit pas approuver aveuglément le résumé produit par l’agent codeur.

### 10. Sauvegarde, Git et retour arrière

Utiliser Git comme mécanisme de traçabilité lorsque possible.

Avant chaque tâche :

* vérifier l’état du dépôt ;
* enregistrer un snapshot ou point de reprise ;
* détecter les modifications préexistantes ;
* ne pas écraser silencieusement le travail utilisateur.

Après une tâche validée :

* produire un diff ;
* créer un commit local explicite si la configuration l’autorise ;
* relier le commit à l’identifiant de tâche.

Après un échec :

* conserver les logs ;
* restaurer le dernier état sûr si nécessaire ;
* éviter de laisser le dépôt dans un état partiellement cassé ;
* marquer la tentative dans l’historique.

Si le dossier n’est pas encore un dépôt Git, mettre en place une initialisation locale prudente après avoir vérifié les fichiers à exclure.

Aucun push distant ne doit être effectué sans configuration explicite.

### 11. Journal d’événements

Créer un journal append-only permettant de comprendre exactement ce qui s’est passé.

Événements minimaux :

* démarrage du moteur ;
* arrêt ;
* tâche sélectionnée ;
* contexte construit ;
* requête envoyée à Ollama ;
* action demandée ;
* action acceptée ou refusée ;
* commande exécutée ;
* fichier modifié ;
* test lancé ;
* résultat de validation ;
* retry ;
* rollback ;
* tâche terminée ;
* tâche bloquée ;
* erreur interne.

Ne pas enregistrer en clair des secrets détectés.

### 12. Arrêt et reprise

Le moteur doit pouvoir :

* être arrêté proprement ;
* reprendre la tâche interrompue ;
* détecter une tâche restée en `running` après un crash ;
* réévaluer cette tâche au démarrage ;
* éviter les doubles exécutions ;
* utiliser un verrou local ;
* fournir une commande de statut ;
* fournir une commande d’arrêt.

Il ne doit pas nécessiter que l’utilisateur retrouve manuellement la dernière tâche exécutée.

## Conditions autorisant l’arrêt de l’autonomie

Le moteur ne doit s’arrêter que pour une raison explicite :

1. file de tâches réalisables vide ;
2. dépendance humaine réellement indispensable ;
3. Ollama indisponible au-delà de la politique configurée ;
4. limite de budget ou de temps configurée ;
5. nombre maximal d’échecs consécutifs atteint ;
6. erreur de sécurité ;
7. commande d’arrêt utilisateur ;
8. contradiction documentaire impossible à résoudre automatiquement.

Une simple erreur de compilation ne constitue pas automatiquement un blocage humain.

Le système doit d’abord :

* analyser l’erreur ;
* tenter une correction ;
* relancer les tests ;
* essayer une stratégie alternative ;
* isoler la tâche si elle reste impossible ;
* continuer avec une autre tâche indépendante lorsque cela est possible.

## Gestion des blocages

Un blocage doit contenir :

* la tâche concernée ;
* les faits observés ;
* les fichiers concernés ;
* les commandes exécutées ;
* les erreurs exactes ;
* les tentatives déjà effectuées ;
* la raison pour laquelle l’agent ne peut pas continuer ;
* les informations humaines réellement nécessaires ;
* les autres tâches pouvant continuer malgré ce blocage.

Ne jamais écrire seulement : « intervention humaine nécessaire ».

## Choix technologique recommandé

Le projet AIONE utilise déjà Node, TypeScript et TSX.

Privilégie donc :

* TypeScript pour le moteur d’autonomie ;
* Node.js pour l’exécution ;
* PowerShell pour les scripts de lancement Windows ;
* un stockage local durable léger, par exemple SQLite ou une solution équivalente fiable ;
* YAML ou JSON pour les fichiers de configuration lisibles ;
* JSONL pour les journaux append-only lorsque pertinent ;
* schémas JSON pour les réponses d’agents et les événements.

Tu peux adapter ce choix si l’analyse réelle du dépôt démontre qu’une autre solution déjà présente est nettement plus cohérente.

Toute déviation doit être justifiée par les fichiers existants, pas par préférence abstraite.

## Arborescence attendue

Adapte les noms à la structure réelle, mais fournis au minimum l’équivalent de :

* `src/autonomy/`

  * orchestrateur ;
  * scheduler ;
  * context builder ;
  * Ollama client ;
  * agent protocol ;
  * action executor ;
  * validator ;
  * reviewer ;
  * state store ;
  * recovery manager ;
  * logger ;
  * security policy.
* `config/autonomy.yaml`
* `schemas/agent-action.schema.json`
* `schemas/task-state.schema.json`
* `schemas/autonomy-event.schema.json`
* `scripts/bootstrap-autonomy.ps1`
* `scripts/run-autonomy.ps1`
* `scripts/status-autonomy.ps1`
* `scripts/stop-autonomy.ps1`
* `tests/autonomy/`
* `state/`, exclu de Git lorsque nécessaire ;
* `logs/`, exclu de Git lorsque nécessaire ;
* une documentation opérationnelle concise.

Ne crée pas des centaines de nouveaux fichiers sans nécessité.

## Configuration minimale

La configuration doit permettre de définir :

* workspace ;
* URL Ollama ;
* modèle codeur ;
* modèle relecteur ;
* nombre maximal d’actions par tâche ;
* nombre maximal de retries ;
* timeout des commandes ;
* commandes autorisées ;
* commandes interdites ;
* répertoires autorisés ;
* politique Git ;
* fréquence des validations globales ;
* limite d’échecs consécutifs ;
* nombre maximal de tâches par session, avec valeur illimitée ou très élevée possible ;
* comportement en cas d’Ollama indisponible ;
* mode `dry-run` ;
* niveau de logs.

## Intégration avec la documentation existante

Ne remplace pas la documentation existante.

Utilise-la comme base de vérité et comme source de contraintes.

Le système doit être capable de convertir ou importer `WORK_QUEUE.yaml` dans son état persistant.

Il doit ensuite synchroniser les changements importants vers un fichier lisible par l’humain.

Lorsqu’une tâche est terminée, mettre à jour au minimum :

* son statut ;
* ses preuves de validation ;
* les fichiers modifiés ;
* les tests exécutés ;
* le commit éventuel ;
* les décisions prises ;
* les hypothèses nouvelles ;
* les blocages restants.

Préserver strictement la distinction entre :

* faits observés ;
* exigences normatives ;
* propositions ;
* hypothèses ;
* reconstructions ;
* décisions prises pendant l’implémentation.

## Première démonstration obligatoire

Ne termine pas cette mission après avoir simplement compilé le moteur.

Effectue une démonstration réelle de bout en bout.

La démonstration doit :

1. démarrer le moteur ;
2. contacter réellement Ollama ;
3. sélectionner une petite tâche non destructive ;
4. construire son contexte depuis la documentation ;
5. laisser l’agent demander des lectures ou recherches ;
6. produire une modification réelle et utile ;
7. exécuter les tests ou validateurs associés ;
8. effectuer une revue automatique ;
9. enregistrer l’état ;
10. marquer la tâche comme terminée seulement si elle est réellement validée ;
11. sélectionner automatiquement la tâche suivante ou prouver que la boucle peut le faire ;
12. survivre à un arrêt et une reprise contrôlés.

Choisis une tâche canari suffisamment petite pour limiter les risques, mais ne crée pas une fausse tâche sans utilité uniquement pour réussir la démonstration.

La tâche canari peut concerner l’infrastructure autonome elle-même si aucun code métier n’est encore assez défini.

## Tests obligatoires du moteur

Créer au minimum des tests couvrant :

* parsing de la configuration ;
* import de la file YAML ;
* résolution des dépendances ;
* sélection d’une tâche prête ;
* refus d’une tâche bloquée ;
* persistance et reprise ;
* validation du protocole JSON ;
* refus d’un chemin hors workspace ;
* refus d’une commande interdite ;
* application d’un patch ;
* capture stdout/stderr ;
* timeout de commande ;
* retry après réponse Ollama invalide ;
* quarantaine après trop d’échecs ;
* rollback ou restauration ;
* passage correct des états ;
* reprise après crash simulé ;
* détection du verrou ;
* journalisation des événements ;
* synchronisation vers la documentation lisible.

Ajouter un test d’intégration réel Ollama, distinct des tests utilisant des mocks.

## Critères d’acceptation globaux

La mission est réussie uniquement si :

* le moteur est réellement exécutable ;
* les scripts Windows fonctionnent ;
* une commande unique démarre la boucle ;
* Ollama est réellement interrogé ;
* l’agent peut lire, modifier et tester dans le workspace ;
* les actions sont validées par schéma ;
* les chemins hors projet sont refusés ;
* l’état survit au redémarrage ;
* une tâche réelle a été traitée de bout en bout ;
* les échecs ne détruisent pas le dépôt ;
* le moteur peut passer automatiquement à la tâche suivante ;
* la documentation et l’état machine sont synchronisés ;
* les tests du moteur passent ;
* les validateurs documentaires existants passent encore ;
* aucun code métier fictif n’est présenté comme terminé ;
* aucun stub critique ne reste dans la chaîne principale ;
* aucune nouvelle session Codex n’est nécessaire pour poursuivre les tâches ordinaires.

## Interdictions

Ne pas :

* reprendre l’atomisation exhaustive comme priorité ;
* produire seulement un plan ;
* produire seulement des fichiers Markdown ;
* remplacer les fichiers existants par une nouvelle architecture abstraite ;
* créer un « orchestrateur » qui se contente d’imprimer la prochaine tâche ;
* considérer une réponse textuelle Ollama comme une modification de code ;
* utiliser exclusivement un agent mock ;
* marquer une tâche terminée sans preuve ;
* demander une confirmation à l’utilisateur entre chaque tâche ;
* coder directement les 37 modules à la main avant de construire l’autonomie ;
* supprimer ou fusionner les statuts proposé, hypothétique et normatif ;
* exécuter des opérations destructrices hors workspace ;
* cacher les erreurs ou les tests non exécutés ;
* arrêter au premier problème récupérable ;
* laisser des fonctions principales en `TODO`, `pass`, `NotImplemented`, ou simulation silencieuse.

## Ordre d’exécution imposé

1. Examiner le dépôt et ses instructions.
2. Identifier les validateurs et scripts existants.
3. Vérifier l’état Git et protéger les modifications actuelles.
4. Construire la tranche verticale minimale du moteur.
5. Écrire les tests du moteur.
6. Connecter réellement Ollama.
7. Importer une partie de `WORK_QUEUE.yaml`.
8. Exécuter une tâche canari réelle.
9. Tester l’arrêt et la reprise.
10. Corriger les problèmes observés.
11. Lancer les validations globales.
12. Démarrer ou préparer le démarrage immédiat de la boucle autonome continue.
13. Mettre à jour `PROJECT_STATE.md` et `WORK_QUEUE.yaml` avec les preuves réelles.

## Rapport final demandé

À la fin, ne fournis pas seulement la liste des fichiers créés.

Indique précisément :

* la commande exacte pour installer les dépendances ;
* la commande exacte pour démarrer l’autonomie ;
* la commande exacte pour consulter son état ;
* la commande exacte pour l’arrêter ;
* le modèle Ollama réellement testé ;
* la tâche canari exécutée ;
* les fichiers réellement modifiés par l’agent local ;
* les tests exécutés ;
* leurs résultats ;
* la manière dont la reprise a été testée ;
* l’emplacement de la base d’état ;
* l’emplacement des logs ;
* le dernier identifiant de tâche ;
* la prochaine tâche sélectionnée ;
* les limitations réellement restantes ;
* tout blocage empêchant une autonomie continue véritable.

Ne revendique jamais un fonctionnement qui n’a pas été exécuté et observé.

Commence maintenant par examiner les fichiers existants, puis implémente le système. Ne t’arrête pas après l’analyse ou la rédaction d’un nouveau plan.

