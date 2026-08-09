# Clean Install Test

Status: NOT RUN

Run this only on a clean Windows profile, VM or disposable folder.

## Checklist

- repository copied/cloned cleanly;
- dependencies installed only after approval;
- `npm run typecheck` passes;
- `npm run forge:test` passes;
- Windows HUD builds;
- `START_AIONE.ps1` starts expected components;
- `STATUS_AIONE.ps1` reports useful status;
- `STOP_AIONE.ps1` stops cleanly;
- rollback path is rehearsed.
