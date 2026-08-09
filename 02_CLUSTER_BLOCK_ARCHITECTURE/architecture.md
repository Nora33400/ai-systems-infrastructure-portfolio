# Resource-Block Architecture

Status: **P2 documented architecture**.

## Block definition

A resource block is a typed, observable, schedulable unit. It may represent one GPU partition, a CPU pool, a RAM budget, an NVMe extent, a bus/I/O path, a repair reserve, or a control service. Every block exposes:

- immutable identity and resource type;
- capacity and task-specific capability tags;
- current allocation and queue pressure;
- thermal, error, and health observations;
- dependency and locality edges;
- allowed transitions and repair policy;
- evidence references for the last state change.

The abstraction is intended to make composition explicit. It does not imply that all hardware supports physical partitioning; a block can be a software budget around a shared device.

## Individual block configuration

```yaml
block_id: gpu.quality.0
kind: gpu
capabilities: [inference, validation]
capacity:
  vram_mib: 8192
limits:
  temperature_stop_c: 82
  temperature_resume_c: 74
locality:
  node: workstation.0
  bus: pcie.segment.1
state: AVAILABLE
evidence_head: sha256:...
```

The example is a schema illustration, not a copied live configuration.

## Task-specific block topologies

A task requests a topology rather than a single device. A local coding workload could request a development-model GPU block, a validation-model GPU block, a CPU test block, a memory/context block, and an evidence ledger. A storage-repair workload could replace the second GPU with a repair block near the affected storage/bus path.

Topology construction follows three passes:

1. **Feasibility:** reject candidates violating capacity, policy, locality, or health constraints.
2. **Risk-aware scoring:** rank feasible topologies by latency, thermal headroom, error rate, dependency risk, and migration cost.
3. **Reservation:** acquire resources atomically or abandon the topology without a partial start.

## Local and global managers

The **Local Block Manager** owns fast telemetry, reservations, local dependency edges, immediate isolation, and safe degradation for one node. It must continue operating under a cached, versioned policy if the global manager is unavailable.

The **Global Block-Schema Manager** owns portable block types, topology templates, compatibility rules, schema versions, and placement goals. It proposes allocations but does not bypass a local safety refusal.

```text
global intent and topology template
    ↓
candidate node/block sets
    ↓
local feasibility and health veto
    ↓
atomic reservation
    ↓
execution + observation
    ↓
evidence + global learning
```

## Adaptive resource allocation

Allocation changes should be event-driven and hysteretic. The manager may resize CPU/RAM budgets, move context tiers, lower concurrency, select a smaller model, or migrate work. It must avoid oscillation by using minimum residency time, stop/resume bands, and migration cost.

## Thermal rotation and wear balancing

Thermal rotation selects an equivalent block with greater headroom before a hard limit is reached. Wear balancing adds a long-horizon cost for devices or paths with disproportionate duty cycles. Existing code provides thermal thresholds and local lane roles; historical wear accounting is not implemented in the selected source.

## Repair blocks and proximity

A repair block is held outside normal saturation and can run diagnostics, reconstruction, or validation. Proximity-aware selection prefers a block close enough to inspect the same data or bus path while avoiding the suspected failure domain. This is exploratory because the portfolio contains no measured multi-node locality model.

## Bus and I/O awareness

Bus health is not inferred solely from node health. The topology records PCIe/storage/network path dependencies so that repeated transfer errors can isolate a path without declaring every attached compute block defective. Current source contains topology and telemetry primitives, not a unified BusHealth implementation.

## Workload migration and graceful degradation

Migration requires a checkpoint, destination reservation, dependency validation, state transfer, replay boundary, and source release only after destination validation. If no equivalent destination exists, degradation should be explicit: smaller context, lower concurrency, alternate model, read-only mode, or delayed work. Silent quality reduction is forbidden.

