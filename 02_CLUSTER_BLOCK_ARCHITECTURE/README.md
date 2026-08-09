# Cluster Block Architecture

Overall evidence level: **P2 architecture**, grounded in **P3, P4-U and P4-M local scheduler/dual-GPU evidence**.

## Purpose

This section formalizes a resource-block architecture for composing CPU, GPU, RAM, storage, bus, repair, and control resources into task-specific topologies. The exact “block” abstraction is not present as a finished runtime. Existing evidence supports the lower-level mechanisms: heterogeneous scheduling, GPU probes, mesh registration, resource budgets, thermal guards, isolated workers, and tests.

## Evidence boundary

| Capability | Status | Evidence |
| --- | --- | --- |
| Heterogeneous CPU/GPU scheduling | Implemented/tested locally | [scheduler](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/hetero_scheduler.py), [tests](../01_AIONE_FRACTALOS/source/fractalos/tests/test_hetero_scheduler.py) |
| GPU probing/runtime model | Implemented | [GPU runtime](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/gpu_runtime.py) |
| Node registration/export prototype | Implemented | [mesh federation](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/mesh_federation.py) |
| Dual-GPU role separation and thermal guard | Implemented policy/worker; locally audited | [sanitized policy](../01_AIONE_FRACTALOS/source/aione/config/dual-gpu-development.json), [audit](../01_AIONE_FRACTALOS/docs/aione/DUAL_GPU_FORGE_AUDIT_2026-07-29.md) |
| Resource blocks and global block-schema manager | Architecture only | [architecture](architecture.md) |
| Wear-balanced and proximity-aware repair blocks | Exploratory | [open design](architecture.md#repair-blocks-and-proximity) |

## Documents

- [Architecture](architecture.md)
- [State model](state_model.md)
- [Scheduling model](scheduling_model.md)
- [Pseudocode](pseudocode.md)
- [Topology diagram](diagrams/topology.md)

## Open questions before implementation

- How should topology latency and bus contention be measured across real nodes?
- Which resource dimensions are hard admission constraints versus optimization objectives?
- How should thermal history and hardware wear be normalized across device generations?
- What consistency model governs global schema changes while local managers continue scheduling?
- What evidence is sufficient before a repaired block may rejoin safety-critical work?

No answer in this section is presented as a demonstrated industrial result.
