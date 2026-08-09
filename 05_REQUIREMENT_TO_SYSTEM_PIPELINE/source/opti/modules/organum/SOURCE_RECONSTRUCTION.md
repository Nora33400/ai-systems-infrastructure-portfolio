# Reconstruction sourcée — Organum

Statut : PARTIALLY_DEFINED. Sources : SRC-0001, SRC-0006.

## Ce qui est réellement disponible

SRC-0001 propose pour Organum une vaste arborescence avec Registry, Refresh, Scheduler, Migration, Rollback et EventBus, sans définir leurs contrats.

SRC-0006 place Organum à la fin d'une séparation des rôles d'exception :

REX détecte l'urgence → Cohérental vérifie → ExceptionProtocol détermine la permission → Witness journalise → Organum exécute ou bloque.

## Limite

Ce placement permet de décrire Organum comme autorité d'exécution candidate, mais ne suffit pas à reconstruire sa vision historique, sa philosophie, son runtime ou ses API. Les sous-modules restent HYPOTHETICAL.

