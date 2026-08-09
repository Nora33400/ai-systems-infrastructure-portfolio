# Reconstruction sourcée — TileMindFS

Statut : PARTIALLY_DEFINED. Source principale : SRC-0003 ; compléments : SRC-0001, SRC-0002, SRC-0004.

## Identité proposée

TileMindFS est présenté comme un cœur mémoire et un système de connaissance, pas comme un système de fichiers. Une tuile n'est pas un fichier.

## Composition candidate d'une tuile

- état ;
- contexte ;
- relations ;
- résumé ;
- compression ;
- historique ;
- hash ;
- importance ;
- température ;
- version ;
- delta.

Ces champs sont explicitement énumérés, mais aucun type, invariant, encodage ou algorithme de hash n'est défini.

## Cycle de vie candidat

Seed Tile → Work Tiles → Summary Tiles → Frozen Tiles → Archive.

Le contexte gelé est proposé comme immuable, signé, compressé et reconstructible. Il ne serait pas rechargé intégralement : le système utiliserait une graine et un delta.

## Relations candidates

TileMindFS reçoit l'intégration d'un cycle réflexif dans l'architecture de SRC-0004 et contribue à l'état subjectif suivant. Les relations exactes avec CalContexte, RAMIV, Dynamic Context Compression et Cognitive Fabric ne sont pas normatives.

## Inconnues bloquantes

Identité d'une tuile, granularité, adressage, causalité des deltas, politique de température, signature, cohérence concurrente, déduplication, reconstruction, garbage collection, archivage, chiffrement, niveaux RAM/NVMe et migration.

