# Tranche cognitive verticale testée

Cette tranche ne prétend pas implémenter TileMindFS dans son ensemble. Elle réalise uniquement la projection de stockage demandée par `SRC-0008:L220-L293` : atomes fidèles, tiles sourcées, claims verbatim, identifiants stables, versions et persistance SQLite.

Implémentation : `src/cognitive/markdown-atomizer.ts`, `src/cognitive/tile-builder.ts`, `src/cognitive/cognitive-store.ts`.  
Schémas : `schemas/atom.schema.json`, `schemas/tile.schema.json`.  
Preuve : exécution `COG-EXE-242CFBBC-9F9E-49F6-8D27-EBBDA67A3AF0`, 139 atomes, 16 tiles, 61 claims, reprise réussie.

Statut de la tranche : `TESTED`. Statut global de TileMindFS : `PARTIALLY_DEFINED`, car `SRC-0001:L273-L285` déclare que sa définition réelle, la hiérarchie RAM/NVMe et les tiles gelées manquent encore.
