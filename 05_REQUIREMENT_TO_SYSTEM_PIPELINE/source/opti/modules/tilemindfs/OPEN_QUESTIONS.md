# TileMindFS

## Q-tilemindfs-001 — Validation du rôle

La définition de travail est-elle une décision acceptée, une reconstruction fidèle ou une proposition à modifier ?

## Q-tilemindfs-002 — Contrat

Quelles entrées, sorties, dépendances, invariants et limites sont réellement fondatrices ?

## Q-tilemindfs-003 — Preuve

Quels tests, contre-exemples ou observations permettent de faire progresser `PARTIALLY_DEFINED` ?

## Q-tilemindfs-004 — Généralisation de la tranche

Comment généraliser la formation des tiles au-delà du regroupement lexical par sujet testé dans `SRC-0008` ? Le contrat WorkMesh `TSK-P1-015` tranche localement identité, index, températures, compaction et récupération, mais pas l'algorithme général, les migrations opti, la concurrence ni le placement RAM/NVMe/GPU.

## Q-tilemindfs-005 — Compatibilité opti ↔ WorkMesh

Quel adaptateur non destructif peut projeter les tuiles opti testées vers le contrat WorkMesh v1, alors que des champs obligatoires (importance, historique, timestamps, contradictions) manquent dans le format historique ? Aucune migration automatique n'est autorisée.
