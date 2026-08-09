# AI Systems & Distributed Infrastructure Portfolio

Built and curated by a self-taught systems researcher focused on local AI infrastructure, resource control, recovery, memory/context systems, and evidence-driven engineering. Implementation was extensively AI-assisted; authorship boundaries and validation practice are disclosed in [Authorship and AI Assistance](AUTHORSHIP_AND_AI_ASSISTANCE.md).

## What this portfolio demonstrates

| Demonstrated result | Code and tests | Evidence | Limitation |
| --- | --- | --- | --- |
| **Bounded fault detection and recovery.** Existing blocker, retry and resilience mechanisms are exercised together through injected logical-worker failure, bounded retry, snapshot comparison, authorized restore, validation and return. | [integration harness](03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.mjs), [test](03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.test.mjs), [underlying primitives](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/) | [generated run](evidence/tests/flow-recovery-demo.json) and [release tests](evidence/tests/validation-summary.md) | One process and logical workers; no physical-node failover, network partition or real workload migration |
| **Measured local-model behavior under constrained hardware.** One four-request RTX 4060 run records 78.75 quality, 90.63% contract compliance, 48.021 tokens/s, 7,350 MiB peak VRAM and latency distributions; an RTX 3060 run preserves a fail-safe abort at 82 °C. | [benchmark harness](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/local-model-benchmark.mjs), [test](01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/local-model-benchmark.test.mjs) | [RTX 4060 JSON](evidence/benchmarks/local-model-benchmark-rtx4060.json), [thermal abort](evidence/benchmarks/local-model-benchmark-rtx3060-thermal-abort.json) | One model, four cases, one repetition; not a general performance claim |
| **Traceable requirement → system → evidence work.** A curated TypeScript slice links five source directives and explicit assumptions to schemas, autonomy/cognitive implementations, deterministic tests and bounded receipts. | [pipeline map](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md), [source](05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/src/), [tests](05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/tests/) | [release result](evidence/tests/validation-summary.md) and [historical negative result](evidence/tests/opti-tests.txt) | External integrations and most module concepts are excluded or remain P2 architecture |

**Not demonstrated:** production-scale cluster operation, distributed training, independent physical nodes, hyperscale/HPC throughput, production recovery SLOs, or independent scientific validation.

## Start here

1. [Flow / recovery integration](03_FLOW_RECOVERY_SYSTEM/README.md)
2. [Measured local-model evidence](evidence/benchmarks/README.md)
3. [Requirement-to-system slice](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md)
4. [Evidence matrix](EVIDENCE_MATRIX.md)
5. [Claim-by-claim evidence map](CLAIM_EVIDENCE_MAP.md)
6. [Reproduce the public evidence](REPRODUCE.md)
7. [Architecture overview](ARCHITECTURE_OVERVIEW.md)

## What I Build

I build local-first control planes around models and workloads: explicit contracts, schedulers, state machines, resource and thermal guards, append-only evidence, recovery paths, and tests. The emphasis is how work is admitted, routed, observed, constrained, recovered, measured and revised—not a claim that one local workstation is an industrial cluster.

## Core Technical Areas

- Heterogeneous CPU/GPU scheduling and bounded resource admission
- Local AI orchestration and dual-GPU experimentation
- Fault isolation, retry budgets, snapshots, rollback and reintegration
- Hierarchical memory, context compaction, provenance and reactivation
- Event/receipt integrity, deterministic hashes and audit trails
- Requirement decomposition into contracts, code, tests and documentation
- Falsifiability, negative evidence and conservative maturity labels

## Selected Systems

1. [AIONE / FractalOS](01_AIONE_FRACTALOS/README.md) — orchestration/MMR code, a local runtime/OS prototype, early x86_64 kernel source, tests and QEMU evidence.
2. [Cluster Block Architecture](02_CLUSTER_BLOCK_ARCHITECTURE/README.md) — P2/P0 architecture grounded in retained scheduler, GPU, mesh and thermal-guard code.
3. [Flow Recovery System](03_FLOW_RECOVERY_SYSTEM/README.md) — P4-I logical integration plus explicit physical-cluster limitations.
4. [Memory & Context Systems](04_MEMORY_CONTEXT_SYSTEMS/README.md) — tested thermal context tiles and linked memory/routing mechanisms.
5. [Requirement-to-System Pipeline](05_REQUIREMENT_TO_SYSTEM_PIPELINE/README.md) — compact, traceable TypeScript evidence slice.
6. [Experiments & Falsifiability](06_EXPERIMENTS_AND_FALSIFIABILITY/README.md) — project-designed MMR checks, local-model measurement and thermal negative evidence.
7. [Selected Prototypes](07_SELECTED_PROTOTYPES/README.md) — compact TimeWarp, routing, policy and repair mechanisms.

## What Is Implemented vs Experimental

| Label | Meaning |
| --- | --- |
| **P4-U** | Unit-level test evidence exists for the stated scope |
| **P4-I** | Integration/system behavior is exercised across components |
| **P4-M** | A runtime or hardware measurement artifact is retained |
| **P3** | Reviewable implementation exists without reproduced P4 evidence for that claim |
| **P2** | Architecture/contracts are documented; no functional-system claim |
| **P1** | A formal vocabulary or evaluation model exists |
| **P0** | Exploratory direction with unresolved assumptions |

Subtype is evidence metadata, not an automatic quality ranking. Synthetic telemetry remains synthetic even when its policy code is tested. See the [Evidence Matrix](EVIDENCE_MATRIX.md).

## Hardware Constraint

The recorded work used an AMD Ryzen 7 5700X, 32 GB RAM, RTX 4060 8 GB, RTX 3060 12 GB, Windows 11/WSL/Docker and local Ollama models. This is deliberately described as a constrained local laboratory, not industrial infrastructure.

## Evidence

- [Release validation summary](evidence/tests/validation-summary.md)
- [Final publication audit](FINAL_PUBLICATION_AUDIT.md)
- [Measured benchmark artifacts](evidence/benchmarks/README.md)
- [QEMU serial evidence](01_AIONE_FRACTALOS/evidence/qemu/README.md)
- [Selection and provenance](SELECTION_AND_PROVENANCE.md)
- [Security review](SECURITY_REVIEW.md)

## Repository Map

```text
01_AIONE_FRACTALOS/                 implementation, tests, QEMU evidence
02_CLUSTER_BLOCK_ARCHITECTURE/      conservative cluster/resource design
03_FLOW_RECOVERY_SYSTEM/            recovery architecture + integration demo
04_MEMORY_CONTEXT_SYSTEMS/          memory/context evidence mapping
05_REQUIREMENT_TO_SYSTEM_PIPELINE/  curated requirement → code → test slice
06_EXPERIMENTS_AND_FALSIFIABILITY/  measured and negative evidence
07_SELECTED_PROTOTYPES/             small explainable mechanisms
evidence/                           reproduced tests and measurements
tools/ and .github/workflows/       public validation and CI
```

## Research Philosophy

```text
Intent → context → constraints/contracts → architecture → implementation
       → tests → evidence → revision
```

## Disclaimer

This repository is a curated engineering portfolio, not a claim of established scientific discovery or production readiness. Local benchmarks are not generalized beyond their recorded hardware, model, workload and sample size. Architecture terms such as resource blocks, wear balancing, physical-node proximity repair or progressive reintegration remain at their evidenced maturity level.

No remote repository, e-mail or external publication was created during this release pass.
