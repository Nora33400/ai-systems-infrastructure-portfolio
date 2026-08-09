# AIONE / FractalOS

Evidence level: **P4-U/P4-I/P4-M for explicitly linked tests and measurements; P3/P2 elsewhere**.

This section contains compact copies from two related implementation lines:

- **AIONE**: local AI orchestration, Minimum Materialization Runtime (MMR), controlled research, context systems, evidence, recovery, and model/worker governance.
- **FractalOS**: an experimental local runtime/OS line with heterogeneous scheduling, GPU and mesh abstractions, TileMind storage, RAM tiers, snapshot/rollback behavior, and an early x86_64 kernel.

## What is implemented

- A Python MMR with state segments, cache reuse, divergence-aware materialization, bounded prediction, quality verification, and tests.
- Python Forge/runtime components and a copied test suite.
- Node.js control-plane components for blockers, recovery, context authority, model evaluation, controlled research, and bounded evolution.
- A FractalOS Python runtime with scheduler, GPU, mesh, VFS, memory, mission, recovery, and observability modules.
- Early x86_64 kernel source and historical QEMU BIOS/UEFI serial captures.

## What is not claimed

- Production cluster reliability or datacenter-scale operation
- A complete daily-use operating system
- Scientific validation beyond the supplied tests and local measurements
- Autonomous canonical modification without human review

## Source map

```text
source/aione/
├── aione_forge/              MMR and Forge Python implementation
├── tests/                    Python tests
├── forge-control/autonomy/   Node control-plane components and tests
├── aione_cognitive_engine/   reflection/evolution prototype and tests
└── config/                   selected, sanitized policies

source/fractalos/
├── omega_tile_os/            experimental runtime
├── fractal_os/               fusion/build wrapper
├── bare_metal/kernel/        x86_64 kernel source
├── boot/ and builder/        selected build source
└── tests/                    Python test suite
```

## Evidence

- [AIONE MMR architecture](docs/aione/ARCHITECTURE_AIONE_MMR.md)
- [MMR real-task report](docs/aione/mmr_release_reports/MMR_REAL_USER_TASK_BENCHMARK.md)
- [Dual-GPU audit](docs/aione/DUAL_GPU_FORGE_AUDIT_2026-07-29.md)
- [FractalOS architecture](docs/fractalos/ARCHITECTURE.md)
- [Boot audit](docs/fractalos/FRACTALOS_BOOT_AUDIT_2026-04-25.md)
- [QEMU serial captures](evidence/qemu/README.md)
- [Reproduced test records](../evidence/tests/README.md)

Copied historical reports may describe the state at their original date. Current portfolio claims are limited by the [Evidence Matrix](../EVIDENCE_MATRIX.md).
