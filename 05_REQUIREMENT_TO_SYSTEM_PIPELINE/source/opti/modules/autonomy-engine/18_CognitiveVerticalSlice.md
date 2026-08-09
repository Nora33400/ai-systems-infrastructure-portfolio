# Orchestration du cycle cognitif vertical

Le moteur existant héberge une nouvelle machine persistante `created → ingested → tiles_built → graph_built → context_selected → diagnosed → answered → completed`, bornée par `SRC-0008:L104-L129` et `SRC-0008:L623-L630`.

Le store SQLite existant reçoit des tables préfixées `cog_`; aucun moteur de persistance concurrent n'est introduit. Chaque transition WQ-0011 à WQ-0020 produit un receipt JSON dans le store et sur disque. Les reprises utilisent le dernier artefact durable ; les échecs restent visibles et récupérables.

Implémentation : `src/cognitive/cognitive-pipeline.ts`, `src/cognitive/cli.ts`.  
Entrée PowerShell : `scripts/invoke-cognitive.ps1`.  
Preuve : `COG-EXE-242CFBBC-9F9E-49F6-8D27-EBBDA67A3AF0`, version finale 2, statut `completed`.
