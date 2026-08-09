# Guide de démarrage opérationnel de l'autonomie

## Installation
Exécutez la commande suivante pour installer l'autonomie : 
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-autonomy.ps1
```

## Démarrage
Les noyaux locaux Phases 1 à 3 se diagnostiquent sans service externe :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 doctor
```

Pour exécuter une seule tâche locale `LOCAL_SYSTEM` sûre :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 run-once
```

L'ancienne boucle Ollama séquentielle reste disponible pour les tâches explicitement autorisées :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-autonomy.ps1
```
Elle exige Ollama et les modèles configurés; `run-once` local ne les exige pas.

Pour demander un rapport Ollama strictement read-only sur une tâche existante :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 ollama-readonly -Task WQ-0044
```
Cette commande n'expose au modèle ni écriture, ni commande, ni transition de tâche. Elle persiste le rapport et un receipt pour revue indépendante.

Pour calculer un plan Phase 2 sans lancer d'agent :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 plan-once
```

Pour observer les GPU et simuler une demande de deux workers lorsque the owner est explicitement inactive :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 resources -RequestedWorkers 2 -UserIdle
```
Cette commande reste `dry_run_only`; elle ne charge ni modèle et ne change aucun réglage GPU.

## Statut
Pour vérifier le statut de l'autonomie, exécutez : 
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/status-autonomy.ps1
```

Vues JSON supplémentaires :
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 tasks
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 task-show -Task WQ-0042
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-autonomy.ps1 receipts-verify
```

## Arrêt
Pour arrêter l'autonomie, utilisez la commande suivante : 
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-autonomy.ps1
```

La boucle historique utilise `qwen2.5-coder:14b`. Le worker read-only essaie `qwen2.5-coder:7b`, puis `qwen2.5-coder:14b` en fallback. Les emplacements de l'état et des logs sont définis dans `config/autonomy.yaml`.

## Politique et arrêt global

La politique d'autonomie est `config/autonomy-policy.yaml` et doit satisfaire `schemas/autonomy-policy.schema.json`. La politique matérielle est `config/resource-policy.yaml` et doit satisfaire `schemas/resource-policy.schema.json`. La variable `AUTONOMY_DISABLED=1` bloque `run-once`. Le fichier sentinelle d'arrêt reste géré par la commande `stop`.

## Intégrations

- Trello : `DISABLED`, configuration candidate dans `config/trello.yaml`, aucun secret dans le dépôt ;
- Codex : `manual_bundle` prévu, aucune invocation automatique implémentée ;
- ChatGPT : `manual_bundle` prévu, aucune API configurée ;
- worktrees/commits : indisponibles tant qu'aucune baseline Git n'existe ;
- Ollama : rapport read-only Phase 3 testé; aucun patch ou changement d'état par le modèle. Il reste hors du cycle Phase 1 `run-once`.
- LiteLLM : non trouvé et non autorisé à l'installation ; tâche WQ-0050 bloquée ;
- GPU : observation et recommandation seulement, aucune bascule automatique.

Architecture et limites : `docs/autonomy-planning/README.md`.

## États et Logs
L'emplacement de l'état est : `${LOCALAPPDATA}/AIONE/opti-runtime/state/autonomy.db`
L'emplacement des logs est : `${LOCALAPPDATA}/AIONE/opti-runtime/logs/autonomy-events.jsonl`
