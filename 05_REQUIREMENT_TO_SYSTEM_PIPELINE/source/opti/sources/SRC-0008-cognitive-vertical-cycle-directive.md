# MISSION CODEX — IMPLÉMENTER LE PREMIER CYCLE COGNITIF VERTICAL DE GPT COGNITIVE CONSTRUCTION

Tu travailles directement dans le dépôt actuel du projet.

Tu dois poursuivre le travail existant sans recréer l’architecture, sans réinitialiser la documentation et sans remplacer le moteur d’autonomie déjà implémenté.

## 1. ÉTAT ACTUEL À RESPECTER

Le projet possède déjà :

* une constitution documentaire structurée ;
* environ 1 000 fichiers documentaires ;
* un registre de modules ;
* des contrats machine YAML et JSON ;
* un graphe d’architecture ;
* une file de travail ;
* un moteur d’autonomie TypeScript ;
* une persistance SQLite ;
* une exécution locale avec Ollama ;
* des mécanismes de reprise, retry, quarantaine et restauration ;
* une journalisation JSONL ;
* des scripts PowerShell de démarrage, d’arrêt et de diagnostic.

Le moteur autonome est validé, mais aucun véritable code métier cognitif n’est encore implémenté.

La documentation existante est une source de contraintes et d’intentions. Elle ne prouve pas qu’une fonction est déjà développée.

Tu dois toujours distinguer :

* documenté ;
* proposé ;
* hypothétique ;
* implémenté ;
* testé ;
* validé.

## 2. OBJECTIF DE LA MISSION

Construire une première tranche cognitive verticale, petite mais entièrement fonctionnelle et vérifiable.

Le cycle cible est :

```text
Source Markdown
    ↓
Atomisation fidèle
    ↓
Construction de tuiles
    ↓
Graphe de provenance et de dépendances
    ↓
Sélection contextuelle
    ↓
Diagnostic de cohérence
    ↓
Réponse traçable
    ↓
Persistance des résultats
```

Cette tranche doit être testée initialement sur une seule source réelle :

```text
sources/SRC-0001-conversation-excerpt.md
```

Le système doit être capable de répondre à une question de test telle que :

```text
Quel rôle Cohérental doit-il réellement jouer ?
```

La réponse doit être reconstruite à partir des informations présentes dans la source, et non depuis une réponse codée en dur.

## 3. NON-OBJECTIFS

Tu ne dois pas :

* coder une « IA générale » ;
* implémenter tous les modules du projet ;
* générer plusieurs centaines de fichiers supplémentaires sans nécessité ;
* réécrire entièrement la documentation ;
* remplacer le moteur autonome existant ;
* créer une nouvelle architecture concurrente ;
* simuler des résultats inexistants ;
* déclarer une fonction terminée sans test ;
* utiliser une réponse codée en dur pour réussir la démonstration ;
* transformer Cohérental en simple calculateur de score ;
* utiliser un LLM pour masquer une absence de structure algorithmique ;
* supprimer ou affaiblir les mécanismes de provenance ;
* effectuer de commit automatique tant qu’aucun commit de référence sûr n’existe.

## 4. RÈGLE PRINCIPALE

Tu dois construire une capacité réelle, minimale et démontrable.

Chaque résultat doit être :

* persistant ;
* adressable ;
* traçable jusqu’à la source ;
* testable ;
* reproductible ;
* récupérable après interruption ;
* compatible avec le moteur autonome existant.

## 5. PHASE 0 — INSPECTION OBLIGATOIRE

Avant toute modification :

1. Lire les fichiers d’entrée principaux :

   * `README.md`
   * `PROJECT_STATE.md`
   * `MASTER_MODULE_REGISTRY.yaml`
   * `ARCHITECTURE_GRAPH.yaml`
   * `WORK_QUEUE.yaml`
   * `AGENTS.md`
   * les contrats des modules concernés ;
   * la documentation du moteur d’autonomie ;
   * le code actuel du moteur ;
   * les scripts de validation existants.

2. Identifier :

   * le langage et l’organisation exacte du runtime ;
   * les conventions de nommage ;
   * les formats de contrats ;
   * la base SQLite existante ;
   * la manière dont les tâches sont sélectionnées et exécutées ;
   * les mécanismes de receipts ;
   * les règles de validation documentaire ;
   * les emplacements prévus pour Organum, CalContexte, TileMindFS et Cohérental.

3. Produire un bref rapport d’inspection avant implémentation :

   * éléments réutilisables ;
   * éléments manquants ;
   * incompatibilités éventuelles ;
   * fichiers réellement nécessaires à modifier ;
   * plan de migration minimal.

Ne demande pas de confirmation si les éléments nécessaires sont présents.

Prends les décisions techniques locales les plus prudentes et documente-les.

## 6. ARCHITECTURE MINIMALE À IMPLÉMENTER

### 6.1 Modèle Atom

Créer une structure machine stable pour représenter une unité source indivisible.

Exemple conceptuel :

```yaml
atom_id: ATM-000001
source_id: SRC-0001
content: "Cohérental ne doit pas être un simple module qui attribue une note."
source_position:
  start_line: 120
  end_line: 120
content_hash: sha256:...
atom_type: statement
status: observed
created_at: ...
```

Champs minimaux :

* identifiant stable ;
* identifiant de la source ;
* contenu exact ;
* position dans la source ;
* empreinte du contenu ;
* type d’atome ;
* statut épistémique ;
* date de création ;
* version du schéma.

L’atome doit préserver le contenu source.

Ne pas résumer ni reformuler pendant l’atomisation.

### 6.2 Atomiseur Markdown

Implémenter un atomiseur déterministe pour Markdown.

Il doit au minimum reconnaître :

* titres ;
* paragraphes ;
* éléments de liste ;
* citations ;
* blocs de code ;
* séparateurs ;
* lignes isolées significatives.

Il doit :

* préserver les numéros de ligne ;
* produire des identifiants reproductibles lorsque la source ne change pas ;
* calculer une empreinte ;
* ignorer proprement le bruit purement structurel ;
* ne pas fusionner arbitrairement des affirmations différentes ;
* produire un rapport d’atomisation.

Ajouter des tests sur :

* texte simple ;
* listes ;
* titres ;
* blocs de code ;
* caractères Unicode ;
* lignes vides ;
* contenu répété ;
* modification partielle de la source.

### 6.3 Persistance des atomes

Réutiliser la base SQLite existante si son architecture le permet.

Sinon, créer une migration minimale compatible avec le runtime actuel.

Prévoir au minimum :

* table des sources ;
* table des atomes ;
* empreinte des sources ;
* version du parseur ;
* date d’import ;
* état de validité ;
* relation avec l’exécution ayant créé les données.

L’import doit être idempotent.

Une deuxième exécution sur une source inchangée ne doit pas dupliquer les atomes.

### 6.4 Modèle Tile

Une tuile représente un regroupement sémantique ou fonctionnel d’atomes.

Exemple conceptuel :

```yaml
tile_id: TILE-COHERENTAL-001
tile_type: architectural_requirement
subject: Cohérental
atom_ids:
  - ATM-000001
claims:
  - claim_id: CLM-000001
    content: Cohérental ne doit pas produire uniquement un score.
    epistemic_status: source_explicit
confidence:
  level: high
  basis: explicit_source
```

Une tuile doit contenir :

* identifiant ;
* type ;
* sujet ;
* liste d’atomes sources ;
* affirmations extraites ;
* statut épistémique ;
* provenance ;
* niveau de confiance ;
* version ;
* date de construction.

Les affirmations doivent distinguer :

* `source_explicit` ;
* `reconstructed` ;
* `inferred` ;
* `hypothetical` ;
* `normative`.

Une inférence ne doit jamais être enregistrée comme une observation directe.

### 6.5 Constructeur de tuiles

Créer une première méthode de construction hybride :

1. règles déterministes ;
2. regroupement lexical et structurel ;
3. appel facultatif à Ollama pour proposer des regroupements ou des affirmations ;
4. validation structurelle après l’appel au modèle ;
5. rejet des sorties invalides ;
6. conservation de la provenance.

L’utilisation d’Ollama ne doit pas être obligatoire pour lire les données persistées ni pour vérifier les liens de provenance.

Toute sortie générée par un modèle doit enregistrer :

* modèle utilisé ;
* prompt ou empreinte du prompt ;
* date ;
* paramètres ;
* atomes fournis ;
* sortie brute ;
* sortie validée ;
* erreurs éventuelles.

### 6.6 Graphe de provenance et de dépendances

Implémenter un graphe minimal reliant :

* sources ;
* atomes ;
* tuiles ;
* affirmations ;
* réponses ;
* exécutions.

Types de relations minimales :

```text
derived_from
contains
supports
contradicts
depends_on
clarifies
replaces
example_of
implies
implements
used_in_response
```

Chaque relation doit contenir :

* identifiant ;
* nœud source ;
* nœud cible ;
* type ;
* provenance ;
* confiance ;
* justification ;
* statut ;
* date.

Les relations générées automatiquement doivent rester séparées des relations explicitement déclarées dans les sources.

### 6.7 CalContexte minimal

Implémenter une première sélection contextuelle.

Entrée :

* question utilisateur ;
* budget maximal ;
* filtres optionnels ;
* types de tuiles autorisés.

Sortie :

* tuiles sélectionnées ;
* score détaillé par critère ;
* chemins de dépendances suivis ;
* contradictions récupérées ;
* éléments exclus ;
* raison de chaque inclusion ou exclusion.

Critères minimaux :

* proximité lexicale ;
* proximité sémantique si un modèle d’embedding existant est disponible ;
* correspondance du sujet ;
* dépendances du graphe ;
* autorité de la source ;
* statut épistémique ;
* fraîcheur ;
* présence de contradictions ;
* budget contextuel.

Le score final ne doit jamais masquer les sous-scores.

Exemple :

```yaml
selection:
  tile_id: TILE-COHERENTAL-001
  selected: true
  scores:
    lexical: 0.82
    semantic: 0.91
    dependency: 0.70
    source_authority: 1.0
  reasons:
    - Le sujet correspond directement à Cohérental.
    - La tuile contient une exigence architecturale explicite.
```

### 6.8 Cohérental minimal

Cohérental ne doit pas produire seulement une note globale.

Il doit analyser l’ensemble sélectionné et produire un diagnostic structuré.

Sortie minimale :

```yaml
coherence:
  compatible_claims: []
  tensions: []
  contradictions: []
  missing_dependencies: []
  ambiguous_terms: []
  unsupported_inferences: []
  duplicated_claims: []
  obsolete_claims: []
  suggested_resolutions: []
```

Chaque élément détecté doit référencer :

* affirmations concernées ;
* tuiles concernées ;
* atomes sources ;
* justification ;
* confiance ;
* méthode de détection.

Les contradictions doivent être distinguées des simples tensions ou différences de niveau d’abstraction.

### 6.9 Générateur de réponse traçable

Implémenter un pipeline capable de produire une réponse à partir :

* de la question ;
* du contexte sélectionné ;
* du diagnostic Cohérental ;
* des affirmations autorisées.

La réponse doit distinguer clairement :

* ce qui est explicitement déclaré ;
* ce qui est reconstruit ;
* ce qui est inféré ;
* ce qui demeure inconnu.

Elle doit produire simultanément :

1. une réponse lisible ;
2. un objet machine traçable.

Exemple de sortie machine :

```yaml
answer:
  text: |
    Cohérental doit agir comme un système de diagnostic...
  used_tiles:
    - TILE-COHERENTAL-001
  used_atoms:
    - ATM-000001
  explicit_claims:
    - CLM-000001
  inferred_claims: []
  unresolved_questions: []
  confidence: high
```

Le texte final peut être généré avec Ollama, mais il doit être contraint par les affirmations autorisées.

Le modèle ne doit pas inventer des affirmations absentes du contexte.

Ajouter une vérification post-génération permettant de détecter les phrases non soutenues.

## 7. INTÉGRATION AU MOTEUR AUTONOME

Ajouter les tâches suivantes à la file existante en respectant son format réel :

```text
WQ-0011 — Définir et valider le schéma Atom
WQ-0012 — Implémenter l’atomiseur Markdown
WQ-0013 — Ajouter la persistance idempotente des atomes
WQ-0014 — Définir et valider le schéma Tile
WQ-0015 — Construire les premières tuiles
WQ-0016 — Créer le graphe de provenance
WQ-0017 — Implémenter CalContexte minimal
WQ-0018 — Implémenter Cohérental minimal
WQ-0019 — Implémenter la réponse traçable
WQ-0020 — Exécuter le test cognitif vertical
```

Adapte les identifiants uniquement s’ils sont déjà utilisés.

Respecte les dépendances :

```text
WQ-0011
  ↓
WQ-0012
  ↓
WQ-0013
  ↓
WQ-0014
  ↓
WQ-0015
  ↓
WQ-0016
  ↓
WQ-0017
  ↓
WQ-0018
  ↓
WQ-0019
  ↓
WQ-0020
```

Chaque tâche doit produire un receipt contenant :

* identifiant de tâche ;
* entrées ;
* fichiers lus ;
* fichiers modifiés ;
* commandes exécutées ;
* résultats des tests ;
* artefacts produits ;
* état avant ;
* état après ;
* erreurs ;
* décisions ;
* limites connues.

Le moteur doit pouvoir reprendre le circuit après un arrêt entre deux tâches.

## 8. INTERFACE DE COMMANDE MINIMALE

Créer ou étendre une commande permettant d’exécuter le circuit.

Exemple indicatif à adapter à l’architecture réelle :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 `
  -Source sources/SRC-0001-conversation-excerpt.md `
  -Question "Quel rôle Cohérental doit-il réellement jouer ?"
```

Ou une commande TypeScript équivalente :

```text
npm run cognitive -- ingest sources/SRC-0001-conversation-excerpt.md
npm run cognitive -- ask "Quel rôle Cohérental doit-il réellement jouer ?"
```

La commande doit permettre au minimum :

* ingestion d’une source ;
* consultation des atomes ;
* consultation des tuiles ;
* consultation des relations ;
* soumission d’une question ;
* affichage du diagnostic ;
* affichage de la réponse et de sa provenance.

## 9. TEST COGNITIF VERTICAL OBLIGATOIRE

Exécuter réellement le scénario suivant.

### Étape A — Ingestion

Importer :

```text
sources/SRC-0001-conversation-excerpt.md
```

Vérifier :

* source enregistrée ;
* empreinte calculée ;
* atomes créés ;
* positions de lignes valides ;
* aucune duplication après seconde ingestion.

### Étape B — Construction

Construire les tuiles et relations nécessaires.

Vérifier qu’au moins une tuile pertinente pour Cohérental est produite depuis les passages réels de la source.

### Étape C — Question

Poser :

```text
Quel rôle Cohérental doit-il réellement jouer ?
```

### Étape D — Sélection

Vérifier que CalContexte retrouve les tuiles pertinentes et explique leur sélection.

### Étape E — Diagnostic

Vérifier que Cohérental identifie au minimum :

* le refus d’un simple score unique ;
* la nécessité d’un diagnostic plus structuré ;
* les éventuels éléments encore non définis.

Ces résultats doivent venir des sources disponibles.

### Étape F — Réponse

Produire une réponse traçable avec :

* texte lisible ;
* identifiants de tuiles ;
* identifiants d’atomes ;
* statuts épistémiques ;
* incertitudes ;
* éléments manquants.

### Étape G — Reprise

Interrompre ou simuler une interruption contrôlée avant la fin du pipeline.

Relancer le moteur.

Vérifier :

* absence de duplication ;
* reprise au bon état ;
* conservation des données ;
* conservation des receipts ;
* résultat final identique ou explicitement versionné.

## 10. TESTS À AJOUTER

Ajouter au minimum :

### Tests unitaires

* génération stable des identifiants ;
* calcul d’empreintes ;
* parsing Markdown ;
* persistance idempotente ;
* validation des schémas ;
* création des relations ;
* calcul des scores contextuels ;
* détection de contradiction ;
* vérification de provenance ;
* rejet d’une sortie LLM invalide.

### Tests d’intégration

* source → atomes ;
* atomes → tuiles ;
* tuiles → graphe ;
* question → sélection ;
* sélection → diagnostic ;
* diagnostic → réponse ;
* redémarrage → reprise.

### Tests négatifs

* source absente ;
* source vide ;
* YAML invalide ;
* sortie Ollama non conforme ;
* modèle Ollama indisponible ;
* base verrouillée ;
* atome orphelin ;
* tuile sans provenance ;
* relation circulaire non autorisée ;
* réponse contenant une affirmation non soutenue.

### Test réel

Utiliser le modèle Ollama déjà validé dans le projet, sauf incompatibilité constatée.

Prévoir un mode déterministe sans LLM pour les tests structurels.

## 11. DOCUMENTATION À METTRE À JOUR

Modifier uniquement les documents concernés.

Mettre à jour au minimum :

* état du projet ;
* file de travail ;
* registre des modules concernés ;
* graphe d’architecture ;
* journal des décisions ;
* guide de démarrage ;
* guide de diagnostic ;
* contrats machine ;
* documentation du nouveau circuit cognitif.

Ne marque comme implémenté que ce qui est réellement exécuté et testé.

Pour chaque module, indiquer :

```yaml
documentation_status: ...
implementation_status: ...
test_status: ...
validation_status: ...
```

## 12. GESTION DES ERREURS ET DU RISQUE

En cas de problème :

1. conserver l’état précédent ;
2. enregistrer l’erreur ;
3. produire un receipt d’échec ;
4. restaurer les fichiers si nécessaire ;
5. placer uniquement la tâche concernée en quarantaine ;
6. ne pas bloquer les tâches indépendantes ;
7. ne pas masquer l’erreur par une documentation optimiste.

Ne supprime aucune donnée source.

Ne modifie pas les empreintes des sources historiques.

Ne transforme jamais une hypothèse en fait validé.

## 13. CRITÈRES D’ACCEPTATION

La mission est réussie seulement si :

* le projet compile ;
* les validations YAML et JSON passent ;
* les tests existants restent valides ;
* les nouveaux tests passent ;
* la source est atomisée réellement ;
* les atomes sont persistés ;
* les tuiles conservent leur provenance ;
* le graphe relie correctement les objets ;
* CalContexte justifie ses sélections ;
* Cohérental produit un diagnostic structuré ;
* la réponse référence les sources utilisées ;
* une affirmation non soutenue peut être détectée ;
* le pipeline reprend après interruption ;
* aucune donnée n’est dupliquée après reprise ;
* le moteur autonome exécute les tâches ajoutées ;
* aucun résultat n’est codé en dur pour la question de démonstration.

## 14. RAPPORT FINAL ATTENDU

À la fin, fournir un rapport factuel contenant :

### État général

* réussite complète ;
* réussite partielle ;
* échec contrôlé.

### Modifications

* fichiers créés ;
* fichiers modifiés ;
* migrations ;
* contrats ajoutés ;
* commandes ajoutées.

### Tests

* nombre total ;
* réussis ;
* échoués ;
* ignorés ;
* tests réels Ollama ;
* tests de reprise.

### Démonstration

Afficher :

* question posée ;
* réponse produite ;
* tuiles utilisées ;
* atomes utilisés ;
* diagnostic Cohérental ;
* incertitudes détectées.

### Limites restantes

Lister précisément ce qui n’est pas encore implémenté.

### Prochaines tâches

Proposer uniquement les tâches devenues réalisables grâce à cette tranche.

## 15. MODE D’EXÉCUTION

GO BATCH : OUI.

Procède de manière autonome.

Inspecte, implémente, teste, corrige et valide dans la même mission.

Ne t’arrête pas après la création des schémas.

Ne t’arrête pas après un prototype non intégré.

Ne demande pas de validation intermédiaire lorsqu’une décision locale sûre peut être prise.

En cas de difficulté non bloquante, choisis la solution la plus :

* minimale ;
* réversible ;
* testable ;
* compatible avec l’existant ;
* traçable.

L’objectif n’est pas de prétendre que GPT Cognitive Construction est terminé.

L’objectif est d’obtenir son premier cycle cognitif réel, fermé, persistant, traçable et vérifié.
