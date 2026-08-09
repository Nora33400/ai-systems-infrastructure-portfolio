# Tranche cognitive verticale testée

La projection CalContexte de la tranche sélectionne des tiles selon huit sous-scores visibles, un budget explicite et des raisons d'inclusion/exclusion. L'autorité de source ne suffit pas à sélectionner une tile sans correspondance de sujet ou pertinence lexicale. Le sous-score sémantique reste `null` tant qu'aucun embedding n'est disponible. Source de cette politique d'implémentation : `SRC-0008:L351-L420`.

Implémentation : `src/cognitive/calcontexte.ts`.  
Preuve : l'exécution `COG-EXE-242CFBBC-9F9E-49F6-8D27-EBBDA67A3AF0` a sélectionné uniquement `TILE-96DB81480963913F` pour la question sur Cohérental.

Statut de la tranche : `TESTED`. Statut global de CalContexte : `PARTIALLY_DEFINED`; sa vraie définition historique reste absente selon `SRC-0001:L273-L276`.
