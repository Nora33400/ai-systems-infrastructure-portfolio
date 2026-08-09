# Recovery Architecture

Status: **P2 transverse architecture**, grounded in selected P4-U primitives and a P4-I single-process harness.

## 1. Flow Evaluator

The evaluator consumes node, bus, queue, thermal, error, repair, and dependency observations. It produces a signed/hashed assessment, not a repair action. Confidence and evidence freshness must accompany every result so that a missing sensor is not treated as a healthy value.

Existing analogues include the [live blocker snapshot](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/live-blockers.mjs), [performance governor](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/perf_governor.py), and local benchmark/thermal guards.

## 2. Blocker

The Blocker prevents new admission, marks the affected failure domain, and requests checkpoint/drain where possible. It should isolate the narrowest safe scope: workload, block, dependency path, node, or topology. The copied implementation preserves root blockers and prevents a repair task from becoming a second root cause.

## 3. Activator

The Activator selects a safe response plan: pause, degrade, migrate, diagnose, repair, or retain isolation. It cannot declare success. This named component is not implemented as a standalone service in the selected source.

## 4. Reloader

The Reloader reconstructs the minimum necessary state from checkpoint, append-only events, configuration, and validated snapshots. Reload must be idempotent and must refuse a broken hash chain or incompatible schema.

## 5. Repair Scheduler

Repair work receives its own budget, retry count, cooldown, dependencies, and evidence. The implemented [repair retry planner](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/repair-retry.mjs) allows retry only from bounded failed states and refuses exhausted budgets.

## 6. Validation

Validation is separate from repair. It runs integrity checks, targeted tests, synthetic workload, dependency checks, and comparison with the pre-failure baseline. The [resilience manager](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/resilience-manager.mjs) refuses unverified backups and requires a restore test.

## 7. Progressive Reintegration

Successful validation moves the resource to `LIMITED_RETURN`, with restricted workload share, heightened observation, and rollback readiness. Only a completed soak returns it to `AVAILABLE`. This unified behavior is not yet implemented in the copied source.

## Evidence rules

Every transition should record:

- prior state and proposed state;
- observations and their freshness;
- policy/schema version;
- selected failure domain;
- repair attempt and budget;
- validation command and result;
- rollback point;
- previous-event hash and current-event hash.
