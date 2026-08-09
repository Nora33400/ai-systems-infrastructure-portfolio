# FractalOS Usage Error Recovery

FractalOS now keeps a black-box log for usage errors and restart recovery.

## What Is Logged

- CLI parse errors.
- Unhandled runtime exceptions.
- Command context and traceback tail.
- Restart recovery reports and rollback decisions.

Reports live under `workspace/usage_errors` and `workspace/recovery/reports`.

## Restart Recovery Pipeline

1. Compile-scan all watched Python modules.
2. If a module is unavailable, restore the last known-good snapshot.
3. Run Doctor.
4. If Doctor passes and modules compile, capture a new known-good snapshot.
5. If a module still fails, queue a builder worker and code workload to reinforce the patch.

## Commands

```powershell
python -m omega_tile_os usage-errors --workspace .\workspace
python -m omega_tile_os restart-recovery --workspace .\workspace --reason manual-boot-check
```

## Rule

No broken module should become the new baseline. A patch must pass restart recovery
before it can become known-good state.
