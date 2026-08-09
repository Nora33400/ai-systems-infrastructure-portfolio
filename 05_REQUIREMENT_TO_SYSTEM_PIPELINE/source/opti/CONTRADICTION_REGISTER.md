# Registre des contradictions et tensions

## Contradictions confirmées

Aucune contradiction de domaine ne peut être confirmée comme telle à partir des quatorze sources ; plusieurs ambiguïtés, chevauchements et tensions d'implémentation restent toutefois ouverts.

## Ambiguïtés à ne pas résoudre arbitrairement

| ID | Éléments en tension | Traitement actuel |
|---|---|---|
| AMB-0001 | Le texte porte le titre « Phase 1 » mais ordonne d'abord une « Phase 0 ». | Le dépôt se déclare en Phase 0; la numérotation globale reste ouverte. |
| AMB-0002 | Une séquence de cinq briques est proposée, puis TileMindFS + CalContexte + moteur Ollama sont décrits comme meilleur point de départ. | Conserver les deux formulations; ne pas supprimer Documentation Engine et Knowledge Graph. |
| AMB-0003 | Le contrat CalContexte montre des dépendances, mais il est introduit par « par exemple ». | Classer les dépendances comme hypothétiques, non comme graphe normatif. |
| AMB-0004 | CorrexAI est appelé « système immunitaire » dans `SRC-0003`, tandis qu'IMMUNE est défini comme réseau immunitaire distribué dans `SRC-0005`. | Conserver deux modules; documenter des périmètres candidats distincts et ouvrir OQ-0012. |
| AMB-0005 | `SRC-0006` reconstruit Cohérental tout en déclarant ne pas avoir retrouvé sa spécification exacte. | Conserver le contenu comme proposition détaillée, jamais comme souvenir historique certain. |
| AMB-0006 | REX est présenté avec un « nom possible », mais son comportement et ses états sont détaillés. | Statut `PARTIALLY_DEFINED`, nom et contrat encore proposés. |
| AMB-0007 | `SRC-0007` exige des mutations bornées au workspace, alors que le contrôle d'accès Windows de cet hôte bloque les écritures directes de Node.js dans `Documents`. | Conserver l'état et les logs dans `${LOCALAPPDATA}` et effectuer les mutations du workspace par WSL avec contrôle canonique des chemins. Il s'agit d'une tension opérationnelle, pas d'une décision de domaine. |
| AMB-0008 | `SRC-0008` impose à la projection Cohérental de refuser un score unique, tandis que `SRC-0001` ne formule pas cette propriété de Cohérental. | Attribuer la politique d'implémentation à `SRC-0008` uniquement ; ne pas la présenter comme définition historique extraite de `SRC-0001`. |
| AMB-0009 | La question de démonstration demande le rôle « réel » de Cohérental, mais `SRC-0001:L273-L278` dit précisément que la raison de sa séparation avec CorrexAI n'est pas connue. | Produire une réponse traçable qui expose cette inconnue et les contraintes de non-fusion, sans importer l'exemple de réponse de `SRC-0008`. |
| AMB-0010 | L'exécution historique termine en version 2, tandis que la machine constitutionnelle prototype peut journaliser une révision à chaque transition simulée. | Conserver la version 2 dans la fixture; ouvrir OQ-0022 et interdire toute migration silencieuse du runtime ou de la preuve. |
| AMB-0011 | `SRC-0010` demande des parties autonomes capables d'entraîner l'autonomie d'autres éléments, tandis que la baseline `SRC-0007` impose un seul worker et que Agent Fabric, PRIOR, Cognitive Fabric, AEGIS-NET et Organum ne sont pas formalisés. | Documenter une trajectoire progressive; ne pas transformer la demande en runtime multi-agent ou en propagation autonome pendant la Phase 0. |
| AMB-0012 | Trello est demandé comme « nœud vivant », mais AIONE possède déjà le registre persistant, les dépendances et les preuves. | RÉSOLU par D-0018 : registres opti canoniques, SQLite pour l'exécution, Trello projection optionnelle. Les conflits champ par champ restent à tester avant synchronisation. |
| AMB-0013 | `SRC-0014` propose Kernel, Registry, Supervisor et Agent Factory alors qu'`autonomy-engine`, Organum, Agent Fabric et plusieurs registres existent déjà avec des maturités différentes. | D-0026 traite le Kernel comme frontière logique composée de l'existant; aucun renommage, alias ou second runtime n'est créé. Les frontières Agent Factory/Agent Fabric restent OQ-0031. |
| AMB-0014 | Le chemin planifié échoue fermé sur l'arrêt global, tandis que l'ancien `Orchestrator.run()` efface sa sentinelle au démarrage et utilise un autre domaine de statuts. | Ne pas lancer de boucle longue; WQ-0052 est READY pour harmoniser l'arrêt et documenter les domaines sans fusionner leurs machines d'états. |
| AMB-0015 | L'ancien inventaire déclarait Trello non callable et distant inconnu, tandis que la session actuelle expose un connecteur read-only et le tableau `acceuil`. | Remplacer seulement l'observation datée : Trello est lisible et non vide, mais toujours non intégré et sans écriture autorisée. |
| AMB-0016 | Google Agenda répond avec un profil `the configured owner profile` alors que les autres projections sont au nom de the owner. | RÉSOLU par D-0032 : the owner confirme ce profil comme calendrier principal ; les écritures personnelles restent protégées. |
| AMB-0017 | WorkMesh Forge et opti possèdent chacun un registre de tâches présenté comme canonique. | Résolu par D-0028 : autorité par périmètre, WorkMesh interprojets et opti interne ; échanges par références et événements, aucune double écriture silencieuse. |
