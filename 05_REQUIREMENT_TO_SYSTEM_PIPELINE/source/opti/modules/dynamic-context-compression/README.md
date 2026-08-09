# Dynamic Context Compression

- Identifiant : `dynamic-context-compression`
- Classification : `core_candidate`
- Statut : `PARTIALLY_DEFINED`
- Normatif : `false`
- Sources : `SRC-0003`

## Définition de travail

Compression structurelle de relations, intentions, dépendances, deltas et historique permettant une reconstruction par seed et delta plutôt qu'un rechargement intégral.

Cette définition conserve la modalité des sources. Elle n'autorise ni implémentation ni promotion automatique vers `FORMALIZED`.

## Frontière protégée

Ne pas réduire la compression à un résumé textuel irréversible.

## Curated public files

- [02_Architecture.md](02_Architecture.md)
- [04_Runtime.md](04_Runtime.md)
- [10_FailureCases.md](10_FailureCases.md)
- [11_Recovery.md](11_Recovery.md)
- [12_Tests.md](12_Tests.md)
- [contract.yaml](contract.yaml)
- [evidence.yaml](evidence.yaml)
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)
- [SOURCE_RECONSTRUCTION.md](SOURCE_RECONSTRUCTION.md)
