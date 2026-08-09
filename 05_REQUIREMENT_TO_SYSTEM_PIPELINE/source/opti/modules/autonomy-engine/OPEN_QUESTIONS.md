# Questions ouvertes — Autonomy Engine

- Le modèle `qwen2.5-coder:14b` est validé pour le canari ; faut-il comparer le débit et la fidélité avec les modèles Qwen3 Coder installés ?
- La limite de 40 actions et les gardes anti-boucle ont fonctionné, mais leur calibration sur des tâches de code plus complexes reste à mesurer.
- Le backend WSL est nécessaire dans ce workspace protégé ; quel backend portable adopter sur une machine sans WSL ?
- RÉSOLU pour Phase 4 par D-0037 : baseline protégée `4c0e0a3`, tag `baseline-before-agentic-calendar`; les patches isolés sont autorisés comme propositions. Les commits d'agent, apply canonique, push et fusion restent désactivés.
- `node:sqlite` est encore signalé expérimental par Node 24 ; faut-il figer cette dépendance ou adopter une bibliothèque SQLite externe ?
- RÉSOLU par D-0018 : les registres opti sont canoniques et Trello une projection. Restent ouverts l'identité, les permissions, la confidentialité et les conflits avant activation Trello.
- RÉSOLU par WQ-0043 : cycles, verrous et branches indépendantes sont testés ensemble dans la tranche Phase 2.
- Quels capteurs locaux et quelle hystérésis peuvent autoriser une bascule matérielle réelle sans gêner the owner ? Voir OQ-0029.
- Quand autoriser et contractualiser LiteLLM sans en faire une dépendance du noyau ? Voir OQ-0030.
