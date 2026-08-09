# Evidence Matrix

Evidence levels describe only the artifacts in this repository. P4 does not mean production-ready. Its subtype states what kind of evidence exists: **P4-U** unit-level testing, **P4-I** integration/system testing, and **P4-M** direct runtime or hardware measurement. Mocked telemetry is identified in notes and never treated as physical-cluster evidence.

| Project | Capability | Evidence level | Code | Tests | Benchmark | Docs | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AIONE MMR | Sparse materialization, diff cache, bounded prediction | **P4-M** | [source](01_AIONE_FRACTALOS/source/aione/aione_forge/mmr.py) | [test](01_AIONE_FRACTALOS/source/aione/tests/test_aione_mmr.py) | [internal task report](01_AIONE_FRACTALOS/docs/aione/mmr_release_reports/MMR_REAL_USER_TASK_BENCHMARK.md) | [architecture](01_AIONE_FRACTALOS/docs/aione/ARCHITECTURE_AIONE_MMR.md) | Deterministic project-designed measurement; lexical/internal scoring, not independent model-quality validation |
| AIONE Forge | Controlled cycles, stores, contracts, API | **P4-I** | [source](01_AIONE_FRACTALOS/source/aione/aione_forge/) | [tests](01_AIONE_FRACTALOS/source/aione/tests/) | — | [section](01_AIONE_FRACTALOS/README.md) | Local integration/unit suite; no distributed deployment claim |
| FractalOS runtime | Local OS/runtime control plane | **P4-I** | [source](01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/) | [tests](01_AIONE_FRACTALOS/source/fractalos/tests/) | — | [architecture](01_AIONE_FRACTALOS/docs/fractalos/ARCHITECTURE.md) | One mesh-merge assertion remains an explicit expected failure |
| FractalOS bare metal | x86_64 kernel boot path | **P4-I** | [kernel](01_AIONE_FRACTALOS/source/fractalos/bare_metal/kernel/) | [source test](01_AIONE_FRACTALOS/source/fractalos/tests/test_bare_metal_kernel.py) | [QEMU logs](01_AIONE_FRACTALOS/evidence/qemu/README.md) | [boot audit](01_AIONE_FRACTALOS/docs/fractalos/FRACTALOS_BOOT_AUDIT_2026-04-25.md) | Boot evidence is QEMU integration, not physical hardware validation or a replacement OS |
| Local-model benchmark | Quality, compliance, latency, throughput, VRAM | **P4-M** | [harness](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/local-model-benchmark.mjs) | [test](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/local-model-benchmark.test.mjs) | [measured JSON](evidence/benchmarks/local-model-benchmark-rtx4060.json) | [summary](evidence/benchmarks/README.md) | One local model, four requests, one repetition; RTX 3060 record is a thermal abort |
| Thermal Context Tiles | Context temperature, compaction, reactivation, tamper detection | **P4-U** | [source](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.mjs) | [test](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.test.mjs) | — | [memory section](04_MEMORY_CONTEXT_SYSTEMS/README.md) | Deterministic local tests; no production memory-tier deployment claim |
| Flow recovery | Blocker snapshot, bounded retry, snapshot comparison and restore decision | **P4-I** | [integration harness](03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.mjs) | [test](03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.test.mjs) | [run JSON](evidence/tests/flow-recovery-demo.json) | [mapping](03_FLOW_RECOVERY_SYSTEM/README.md) | Logical workers in one process; no network partition, physical-node failover or real migration |
| Requirement-to-system pipeline | Sources → contracts → planners → tests | **P4-I** | [source](05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/src/) | [tests](05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/tests/) | — | [evidence chain](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md) | Curated public slice; exact release result is recorded under `evidence/tests` |
| Controlled research | Bounded source intake, adversarial checks, ledger behavior | **P4-U** | [source](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/controlled-research-lab.mjs) | [test](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/controlled-research-lab.test.mjs) | — | [method](06_EXPERIMENTS_AND_FALSIFIABILITY/README.md) | Synthetic/adversarial unit fixtures; generated hypotheses are not treated as validated facts |
| Heterogeneous scheduler | CPU/GPU job placement under budgets | **P3** | [source](01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/hetero_scheduler.py) | [test](01_AIONE_FRACTALOS/source/fractalos/tests/test_hetero_scheduler.py) | — | [scheduling model](02_CLUSTER_BLOCK_ARCHITECTURE/scheduling_model.md) | Local single-machine topology |
| Mesh federation | Node registration and workload export model | **P3** | [source](01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/mesh_federation.py) | — | — | [cluster mapping](02_CLUSTER_BLOCK_ARCHITECTURE/architecture.md) | Implemented prototype; no industrial multi-node measurement |
| Storage VFS | Journaled writes, snapshots, verification, rollback | **P3** | [source](01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/storage_vfs.py) | [test](01_AIONE_FRACTALOS/source/fractalos/tests/test_storage_vfs.py) | — | [Stage 22](01_AIONE_FRACTALOS/docs/fractalos/STORAGE_VFS_STAGE22.md) | Hosted experimental VFS, not production storage |
| TimeWarp | Frame compression, routing, rehydration | **P3** | [source](07_SELECTED_PROTOTYPES/timewarp/) | AST validation only | — | [prototype note](07_SELECTED_PROTOTYPES/README.md) | Small experimental implementation; one copy-only indentation repair |
| Local model router | Task-to-local-model routing | **P3** | [source](07_SELECTED_PROTOTYPES/local_model_router/router.py) | Smoke-tested | — | [README](07_SELECTED_PROTOTYPES/local_model_router/README.md) | Minimal prototype |
| Policy/recovery prototypes | Governors, policy diffs, error and repair experiments | **P3** | [source](07_SELECTED_PROTOTYPES/public_innovations/) | Four smoke cases | — | [index](07_SELECTED_PROTOTYPES/README.md) | Implemented sketches, not integrated services |
| Resource-block topology | Local blocks, global schemas, allocation, migration | **P2** | Related code only | — | — | [architecture](02_CLUSTER_BLOCK_ARCHITECTURE/architecture.md) | Block abstraction itself is not implemented |
| Flow lifecycle | Evaluator → Blocker → Activator → Reloader → repair → validation | **P2** | Partial primitives only | — | — | [state model](03_FLOW_RECOVERY_SYSTEM/state_model.md) | Exact lifecycle is proposed architecture |
| Maintenance calendars | Short/daily/weekly/long-term overlapping cycles | **P2** | Related scheduling code only | — | — | [maintenance model](03_FLOW_RECOVERY_SYSTEM/maintenance_calendars.md) | Not deployed as one unified scheduler |
| Cognitive module contracts | Architecture and failure contracts across selected modules | **P2** | Partial kernels | — | — | [selected modules](05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/modules/) | Most module folders are documentation, not runtime code |
| Evidence maturity model | P0–P4 claim discipline | **P1** | — | — | — | [this matrix](EVIDENCE_MATRIX.md) | Portfolio-level formal model |
| Health vector | NodeHealth, BusHealth, FlowStability, ThermalState, ErrorRate, Repairability, DependencyRisk | **P1** | — | — | — | [formalization](03_FLOW_RECOVERY_SYSTEM/health_model.md) | Variables are defined; unified evaluator is not implemented |
| Industrial multi-node scaling | Extension from local dual GPU to cluster scale | **P0** | — | — | — | [open questions](02_CLUSTER_BLOCK_ARCHITECTURE/README.md) | Explicit extrapolation only |
| Wear/proximity-aware repair | Wear balancing and locality-aware spare selection | **P0** | — | — | — | [architecture](02_CLUSTER_BLOCK_ARCHITECTURE/architecture.md) | Research direction without implementation evidence |

## Count by evidence level

| Level | Count |
| --- | ---: |
| P4-U | 2 |
| P4-I | 5 |
| P4-M | 2 |
| P3 | 5 |
| P2 | 4 |
| P1 | 2 |
| P0 | 2 |
