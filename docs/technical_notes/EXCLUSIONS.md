# Exclusions and Selection Boundaries

## Excluded by rule

- Git histories and project `.git` folders
- Dependency directories and virtual environments
- Build products, compiled objects, ISO images, and bundled third-party binaries
- AI weights, Hugging Face/Ollama model stores, FAISS indexes, and large datasets
- Caches, temporary files, databases, WAL files, and routine logs
- Screenshots and personal media without a clear technical claim
- Publication, mail, calendar, and connected-service scripts/configuration

## Excluded for evidence quality

- Tens of thousands of repeated dual-GPU generated artifacts
- Continuous-observation snapshots that expose telemetry but add little review value
- Older `F:` copies where newer `S:` sources exist
- Rescue, backup, build-workspace, worktree, and restore-test duplicates
- Empty resource-governor placeholder directories
- Standalone names not found with a credible implementation, including Cadroscope, Cadrologie, ChronoScale, CCA-X, MouseCode, and Perception Search

## Third-party boundary

FractalOS contained Limine bootloader sources and binaries. They were excluded from the portfolio. Only original project kernel source, build descriptions, tests, and boot logs were selected. License compatibility for any future redistribution of third-party material must be checked independently.

## Why no screenshots

The discovery found captures and media, but none was needed to substantiate the selected systems claims. Source, tests, machine-readable output, and serial logs are stronger and easier to audit.

