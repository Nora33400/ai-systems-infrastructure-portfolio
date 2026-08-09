# Portfolio Index

## Recommended review path

For a 15-minute technical review:

1. Read the [main README](README.md) and [Evidence Matrix](EVIDENCE_MATRIX.md).
2. Inspect the [FractalOS heterogeneous scheduler](01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/hetero_scheduler.py) and its [tests](01_AIONE_FRACTALOS/source/fractalos/tests/test_hetero_scheduler.py).
3. Inspect the [thermal context store](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.mjs) and [test suite](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.test.mjs).
4. Run or inspect the [flow/recovery integration harness](03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.mjs), then compare it with the implemented [resilience manager](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/resilience-manager.mjs) and [bounded repair retry](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/repair-retry.mjs).
5. Follow the [requirement-to-system evidence chain](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md).
6. Read the [measured RTX 4060 summary](evidence/benchmarks/README.md) and the [test records](evidence/tests/README.md).

## Section map

| Section | Primary question | Best evidence |
| --- | --- | --- |
| [01 — AIONE / FractalOS](01_AIONE_FRACTALOS/README.md) | What was actually built? | Python/Node source, tests, kernel source, QEMU logs |
| [02 — Cluster Block Architecture](02_CLUSTER_BLOCK_ARCHITECTURE/README.md) | How could heterogeneous resources be composed safely? | Scheduler/GPU/mesh code plus P2 model |
| [03 — Flow Recovery](03_FLOW_RECOVERY_SYSTEM/README.md) | How are faults isolated and work reintroduced? | Blocker, resilience, retry, snapshot/rollback code and tests |
| [04 — Memory & Context](04_MEMORY_CONTEXT_SYSTEMS/README.md) | How is limited memory used deliberately? | Thermal tiles, hash chain, compaction, RAM and TileMind code |
| [05 — Requirement Pipeline](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md) | Can an idea become a verifiable system? | Source manifests, contracts, state machines, code, tests |
| [06 — Experiments](06_EXPERIMENTS_AND_FALSIFIABILITY/README.md) | Are claims measurable and falsifiable? | MMR reports, local benchmark JSON, controlled-research tests |
| [07 — Prototypes](07_SELECTED_PROTOTYPES/README.md) | What smaller mechanisms were explored? | Compact Python prototypes with explicit limitations |

## Evidence and audit documents

- [Selection and Provenance](SELECTION_AND_PROVENANCE.md)
- [Claim Evidence Map](CLAIM_EVIDENCE_MAP.md)
- [Reproduction Guide](REPRODUCE.md)
- [Evidence Matrix](EVIDENCE_MATRIX.md)
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Security Review](SECURITY_REVIEW.md)
- [Source Provenance](docs/source_provenance/PROVENANCE.md)
- [Exclusions](docs/technical_notes/EXCLUSIONS.md)
- [Validation records](evidence/tests/README.md)
- [Final Release Gate](FINAL_RELEASE_GATE.md)
