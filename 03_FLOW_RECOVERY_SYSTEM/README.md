# Flow / Recovery System

Evidence level: **P4-I for a deterministic single-machine integration harness and tested primitives; P2 for an operational multi-node service**.

The portfolio contains implemented blocker snapshots, resilience policy, bounded repair retry, immune/runtime guards, journaled storage, snapshots, rollback, and tests. A small [integration harness](flow_recovery_demo.mjs) now exercises detection, bounded retry, corruption comparison, authorized restore, validation, and return for logical workers in one process. It does not demonstrate physical-node failover, network partitions, or production workload migration.

Run it with:

```bash
node --test 03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.test.mjs
node 03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.mjs --out evidence/tests/flow-recovery-demo.json
```

## Requested lifecycle

```text
Flow Evaluator
  → Blocker
  → Activator
  → Reloader
  → Repair Scheduler
  → Validation
  → Progressive Reintegration
```

## Implemented mapping

| Lifecycle role | Existing evidence | Status |
| --- | --- | --- |
| Flow Evaluator | [live blocker snapshot](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/live-blockers.mjs), FractalOS health/performance components | Partial implementation |
| Blocker | [live-blockers](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/live-blockers.mjs) and [tests](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/live-blockers.test.mjs) | Implemented/tested |
| Activator | Admission/scheduler behavior, without this exact named service | Architecture mapping |
| Reloader | Runtime restart/recovery and state reload primitives, without this exact unified service | Architecture mapping |
| Repair Scheduler | [bounded repair retry](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/repair-retry.mjs) and queue behavior | Partial implementation/tested |
| Validation | Test gates, restore verification, and VFS verification | Implemented across components |
| Progressive Reintegration | Limited-return state is formalized here | Architecture only |

## Documents

- [Architecture and evidence mapping](architecture.md)
- [State model](state_model.md)
- [Health model](health_model.md)
- [Overlapping maintenance calendars](maintenance_calendars.md)
- [Pseudocode](pseudocode.md)
- [Recovery diagram](diagrams/recovery_flow.md)
