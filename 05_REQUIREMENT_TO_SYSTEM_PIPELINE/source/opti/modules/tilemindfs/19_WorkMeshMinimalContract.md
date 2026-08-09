# Contrat minimal WorkMesh — preuve externe bornée

Statut de la tranche : `TESTED`. Statut global de TileMindFS : `PARTIALLY_DEFINED`.

## Provenance

- Source de portée : `SRC-0008`, tranche cognitive bornée ;
- dépôt de preuve : `C:/Dev/AIONE_WORKMESH/AIONE_WORKMESH_FORGE_v0.1` ;
- branche : `codex/tsk-p1-015-tilemindfs-minimal` ;
- commit local : `3a253f028f8cc401213f4784240a401a252d5d0e` ;
- receipt : `13_REPORTS/20260718_RCP_TSK-P1-015.yaml` ;
- Tester : `PASS`, 29/29 ; Reviewer : `APPROVE` ; suite WorkMesh : 52/52.

## Ce que la tranche prouve

- enregistrement de tuile fermé et versionné ;
- provenance et empreintes SHA-256 ;
- index déterministe portant version et prédécesseur ;
- températures logiques `HOT/WARM/COLD/FROZEN` ;
- compaction additive avec relations `COMPACTS` ;
- sélection bornée avec fermeture fail-closed des dépendances ;
- écriture atomique, reprise après `.tmp` et quarantaine récupérable ;
- conservation immuable du pilote historique WorkMesh.

## Ce qu'elle ne prouve pas

- service TileMindFS persistant ;
- placement physique RAM/NVMe/GPU ;
- algorithme général de formation des tuiles ;
- concurrence, signature, chiffrement ou garbage collection ;
- compatibilité automatique avec `schemas/tile.schema.json` d'opti ;
- migration des données opti ou du pilote WorkMesh ;
- définition historique complète du module.

La sélection lexicale du prototype WorkMesh est une interface de référence ; elle ne doit pas être appelée CalContexte. La prochaine tâche WorkMesh `TSK-P1-016` doit formaliser cette frontière.

