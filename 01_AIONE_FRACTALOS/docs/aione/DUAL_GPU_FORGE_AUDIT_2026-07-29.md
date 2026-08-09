# Audit de la Forge locale dual-GPU — 29 juillet 2026

## Résultat exécutif

La Forge a réellement fonctionné du 28 juillet au 29 juillet 2026 sur les deux
GPU. Elle a produit 4 533 paquets locaux, mais la boucle initiale privilégiait
le volume plutôt que la nouveauté. La production est conservée comme preuve,
le runtime est migré vers `S:` et la répétition automatique est maintenant
bloquée.

## Mesures observées

| Mesure | Valeur |
| --- | ---: |
| Paquets RTX 3060 | 1 164 |
| Paquets RTX 4060 | 3 369 |
| Total | 4 533 |
| Sujets source distincts | 73 |
| Répétition calculée | 98,39 % |
| Sorties avec structure complète | 4 490 |
| Structures complétées par l'orchestrateur | 652 |
| Paquets avec validation prédéfinie | 1 135 |
| Tokens de sortie | 2 845 813 |
| Mutation du dépôt canonique | 0 |
| Mutation d'un workspace isolé | 0 |

Les livrables contiennent bien analyse, possibilités, architecture, code
proposé, documentation, diagnostic, tests proposés et risques. Ils ne
constituent toutefois pas 4 533 modifications de logiciel: ce sont
principalement des propositions répétées autour d'un ensemble limité de tâches.

## Diagnostic

La sélection utilisait le compteur global modulo la liste de tâches. Après le
dernier candidat, elle reprenait au premier sans tenir compte du couple
tâche/focus déjà traité. L'intervalle de deux secondes amplifiait ce défaut.

Le moteur respectait néanmoins ses limites:

- aucune publication externe;
- aucune installation;
- aucun commit, push ou merge;
- aucune écriture dans le dépôt canonique;
- endpoints Ollama limités à `127.0.0.1`;
- garde thermique et reprise après refroidissement.

## Correction appliquée

Chaque voie possède maintenant un historique persistant indexé par:

```text
source + texte de tâche + focus + révision SHA-256 de la source
```

Une tâche n'est réexécutée que si sa source change. Si aucun travail nouveau
n'existe, la voie:

1. écrit une demande structurée dans
   `<DUAL_GPU_RUNTIME>\requests`;
2. publie le heartbeat `WAITING_BACKLOG`;
3. attend cinq minutes avant une nouvelle vérification;
4. ne consomme pas inutilement le GPU.

L'historique reconstruit contient 231 combinaisons pour la voie RTX 3060 et
257 pour la voie RTX 4060.

## Migration vers S:

Les copies ont été comparées par nombre de fichiers et nombre total d'octets:

| Source historique | Destination active |
| --- | --- |
| `<AIONE_WORKSPACE>` | `<AIONE_WORKSPACE>` |
| `<AIONE_RUNTIME>` | `<AIONE_RUNTIME>` |
| `<OLLAMA_HOME>` | `<OLLAMA_MODEL_STORE>` |
| `<LEGACY_AIONE_ROOT>` | `<EXCLUDED_LEGACY_AIONE_ROOT>` |
| `<LEGACY_WORKMESH_ROOT>` | `<EXCLUDED_LEGACY_WORKMESH_ROOT>` |

Les quatre tâches dual-GPU utilisent maintenant uniquement
`<AIONE_WORKSPACE>` comme workspace et
`<DUAL_GPU_RUNTIME>` comme runtime. Les modèles sont lus dans
`<OLLAMA_MODEL_STORE>`.

Les anciennes tâches AIONE encore configurées avec un chemin `C:` restent
désactivées. Elles ne doivent être réactivées qu'après conversion individuelle
de leurs chemins et de leurs stockages mutables.

Les exécutables système Node.js, PowerShell, Python et Ollama restent installés
sur `C:`. Ils peuvent être lus depuis ce disque, mais les données mutables de la
Forge dual-GPU sont sur `S:`.

## Validation

- copie sans fichier manquant ni différence de taille globale;
- endpoints `11434` et `11435` sains;
- modèles Ollama trouvés depuis `S:`;
- affinités CUDA par UUID confirmées dans les nouveaux journaux;
- deux workers lancés depuis `<AIONE_WORKSPACE>`;
- 24/24 tests Node de la Forge réussis, dont 8/8 tests dual-GPU;
- test d'intégration du Control Plane réussi depuis `S:`;
- deux demandes de renouvellement de backlog créées;
- aucun processus AIONE actif ne référence l'ancien dépôt ou runtime `C:`.

La validation après redémarrage complet de Windows reste à effectuer.

La commande agrégée `npm run forge:test` reste dépendante de l'exécutable
développeur `tsx`, actuellement absent. Aucun téléchargement n'a été effectué:
les 24 tests JavaScript et l'intégration ont été lancés directement avec Node.
