# Contrat minimal WorkMesh — preuve externe bornée

Statut de la tranche : `TESTED`. Statut global de CalContexte : `PARTIALLY_DEFINED`.

## Provenance

- source de portée : `SRC-0008:L347-L379`, tranche cognitive bornée ;
- dépôt de preuve : `C:/Dev/AIONE_WORKMESH/AIONE_WORKMESH_FORGE_v0.1` ;
- branche : `codex/tsk-p1-016-calcontexte-minimal` ;
- commit local : `34b3e0e15445060c260b0474f04cb53eef0db5c9` ;
- receipt : `13_REPORTS/20260718_RCP_TSK-P1-016.yaml` ;
- Tester : `PASS`, 37/37 ; Reviewer : `APPROVE` ; suite WorkMesh : 89/89 ; doctor/validate : 38/38 ; manifeste : 242/242.

## Ce que la tranche prouve

- requête fermée portant un contexte-objet à dix dimensions ;
- chaque dimension est `PRESENT` avec provenance ou `ABSENT` avec valeur nulle ;
- consommation d'enregistrements TileMindFS v1 validés ;
- sélection lexicale déterministe, exclusions, budget et ordre stable ;
- fermeture bornée des dépendances et signalement des dépendances manquantes ;
- contradictions actives signalées, contradictions retirées ignorées ;
- compilation structurée conservant contenu exact, provenance et empreinte d'intégrité ;
- refus fermé des identifiants, relations, fuseaux, doublons ou sélections forgés invalides.

## Ce qu'elle ne prouve pas

- définition historique complète de CalContexte ;
- sélection sémantique, embedding, modèle ou base vectorielle ;
- autorité ou fiabilité relative des sources ;
- poids, seuils et budgets généraux ;
- politiques temporelles ou planification multi-horizons ;
- compatibilité automatique avec les formats CalContexte d'opti ;
- service persistant, concurrence, projection externe ou migration de données.

La prochaine tâche WorkMesh `TSK-P1-017` porte sur TimeWarp et la reprise causale. Elle doit réutiliser les checkpoints existants sans assimiler TimeWarp à un simulateur ou gestionnaire de versions générique.
