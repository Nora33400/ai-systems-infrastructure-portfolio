# Reconstruction sourcée — Dynamic Context Compression

Statut : PARTIALLY_DEFINED. Source : SRC-0003.

## Rupture proposée

La compression ne réduit pas seulement un texte. Elle conserve relation, intention, structure, dépendances, delta et historique.

Une conversation très longue deviendrait une combinaison de structure, relations, résumé, delta et seed, conçue pour être reconstructible.

## Frozen Context

Cycle candidat : chaud → tiède → froid → gelé. Le gelé ne change plus, est signé, compressé et reconstructible. La recharge se ferait par seed et delta, jamais nécessairement par contexte complet.

## Questions de formalisation

Perte acceptable, fidélité structurelle, preuve de reconstruction, causalité des deltas, signature, version, compatibilité, seuils de température, consolidation, accès partiel et mesure de dérive.

