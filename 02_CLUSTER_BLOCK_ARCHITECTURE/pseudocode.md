# Resource Scheduling Pseudocode

Status: **P2**.

```text
function schedule(task, global_schema, local_snapshots):
    template = global_schema.topology_for(task.class)
    candidates = instantiate(template, local_snapshots)

    feasible = []
    for topology in candidates:
        if violates_capacity(topology, task): continue
        if violates_policy(topology, task): continue
        if unhealthy_dependency(topology): continue
        if insufficient_thermal_headroom(topology): continue
        feasible.append(topology)

    if feasible is empty:
        degraded = propose_explicit_degradation(task)
        return REJECTED unless degraded is approved

    selected = argmin(feasible, risk_aware_cost)
    reservation = reserve_atomically(selected)
    if not reservation.ok: retry_with_fresh_snapshot()

    while task.active:
        observation = observe(selected)
        append_evidence(observation)

        if hard_safety_limit(observation):
            checkpoint(task)
            isolate(affected_blocks)
            migrate_or_degrade(task)

        else if rotation_benefit(observation) > rotation_cost(task):
            destination = select_equivalent_topology()
            checkpoint_validate_transfer(task, destination)

    validate_output(task)
    release(selected)
```

