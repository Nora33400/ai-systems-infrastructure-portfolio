# Runtime — Autonomy Engine

Le runtime testé est Node.js 24/TypeScript sur Windows, avec scripts PowerShell. Ollama est joint par API locale configurable ; le canari a utilisé `qwen2.5-coder:14b`.

Le store durable reconstruit les tâches après crash ou redémarrage. Un verrou empêche une double exécution. Le journal append-only permet l'audit. Les sorties de commandes sont tronquées dans les prompts mais conservées en entier dans les logs.

Windows Controlled Folder Access bloque ici les écritures directes de Node dans `Documents`. Les dépendances, la base SQLite, les sauvegardes et les logs résident donc sous `${LOCALAPPDATA}/AIONE/opti-runtime/`; les mutations autorisées du workspace passent par le backend WSL configuré. Cette adaptation reste une contrainte d'environnement, pas une règle du domaine cognitif.

Source normative : SRC-0007.
