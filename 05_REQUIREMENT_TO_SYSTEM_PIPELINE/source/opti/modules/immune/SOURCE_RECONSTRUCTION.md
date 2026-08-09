# Reconstruction sourcée — IMMUNE

Statut : PARTIALLY_DEFINED. Source : SRC-0005.

## Nature

IMMUNE n'est pas un doctor unique, mais un réseau distribué : détection, diagnostic, confinement, simulation, réparation, validation, mémoire de l'erreur et prévention.

## Catégories citées

Perception, sémantique, raisonnement, supposition, dépendance, code, configuration, ressource, temps, coordination, objectif, priorité, personnalité, mémoire, sécurité et communication.

## Anticipation

Le système doit estimer succès direct, succès après adaptation, échec récupérable et échec destructif. Une probabilité faible d'échec destructif peut imposer un snapshot.

Il compare également probabilité par itération, coût, itérations attendues, temps, risque et coût de récupération.

## Progression par preuve

Test minimal → observation → validation → étape suivante. Les actions réversibles et les checkpoints précèdent l'extension.

## Dégradation et récupération

Un module passe en DEGRADED, est redirigé et diagnostiqué ; une version candidate est testée en miroir avant refresh. Le reste du système continue avec les ressources stables.

## Mémoire de l'erreur

Chaque cas conserve déclencheur, hypothèses, preuve d'invalidation, actions gaspillées et protocole corrigé.

