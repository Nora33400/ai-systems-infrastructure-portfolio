# Cas d'échec — Autonomy Engine

- Ollama arrêté ou modèle absent ;
- réponse JSON invalide ou réparation impossible ;
- chemin hors workspace ou traversée ;
- commande interdite ou destructive ;
- timeout, processus bloqué ou sortie excessive ;
- tests échoués après retries ;
- tâche running abandonnée par crash ;
- diff hors périmètre ;
- dépôt sale ou modifications utilisateur concurrentes ;
- contradiction documentaire ;
- verrou orphelin ou double instance.
- cycle de dépendances, dépendance inconnue ou conflit hiérarchique de chemins ;
- retry demandé avant son échéance ;
- activité the owner inconnue, plein écran, jeu ou température GPU au seuil ;
- sortie `nvidia-smi` absente ou mal formée.

Chaque blocage conserve faits, fichiers, commandes, erreurs exactes, tentatives, besoin humain réel et tâches indépendantes encore possibles.

Les essais du canari ont effectivement couvert réponse répétitive, dépassement du budget d'actions, quarantaine, retry explicite, restauration par sauvegarde, arrêt coopératif et reprise. L'absence de baseline Git empêche actuellement de démontrer le rollback par commit ; la restauration de fichiers par sauvegarde est opérationnelle.

Source normative : SRC-0007.
