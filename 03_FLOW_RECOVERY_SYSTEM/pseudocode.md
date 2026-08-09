# Recovery Pseudocode

Status: **P2**.

```text
on observation(event):
    vector = evaluate_health(event, recent_evidence)
    append_evidence(vector)

    if hard_limit(vector) or risk(vector) >= isolate_threshold:
        scope = smallest_safe_failure_domain(vector)
        block_new_admission(scope)
        checkpoint_or_drain(scope)
        isolate(scope)

        diagnosis = run_bounded_diagnostics(scope)
        if not diagnosis.repairable:
            retain_isolation_or_retire(scope)
            return

        repair = schedule_repair(scope, retry_budget, cooldown)
        if not repair.ok:
            rollback_or_retain_isolation(scope)
            return

        state = reload_from_verified_checkpoint(scope)
        if not verify_hashes_and_schema(state):
            rollback_or_retain_isolation(scope)
            return

        validation = run_targeted_and_synthetic_tests(scope)
        if not validation.ok:
            rollback_or_retain_isolation(scope)
            return

        set_state(scope, LIMITED_RETURN)
        if soak_passes(scope): set_state(scope, AVAILABLE)
        else: rollback_and_isolate(scope)
```

