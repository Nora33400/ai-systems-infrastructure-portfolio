# Recovery State Model

Status: **P2 documented architecture**.

The lifecycle intentionally returns to `AVAILABLE`; it is shown at both ends to make recovery closure explicit.

```text
AVAILABLE
  → OBSERVED
  → SUSPECT
  → RESTRICTED
  → ISOLATED
  → DIAGNOSTIC
  → REPAIRING
  → RELOADING
  → VALIDATING
  → LIMITED_RETURN
  → AVAILABLE
```

| State | Entry condition | Allowed work | Exit evidence |
| --- | --- | --- | --- |
| `AVAILABLE` | Validated and inside policy | Normal | Continuous observation |
| `OBSERVED` | Anomaly detected but unconfirmed | Existing work may continue under guard | Repeated/independent observation |
| `SUSPECT` | Evidence crosses suspicion threshold | No new high-risk work | Scope and confidence assessment |
| `RESTRICTED` | Safety action required but draining is possible | Reduced/readonly/low-risk work | Checkpoint or clean drain |
| `ISOLATED` | Failure domain removed from production | Diagnostics only | Isolation receipt |
| `DIAGNOSTIC` | Bounded diagnostic plan admitted | Read-only probes and tests | Cause classification and repairability |
| `REPAIRING` | Repair plan and retry budget approved | Repair procedure only | Repair receipt and resulting state |
| `RELOADING` | Reconstructable state exists | State recovery only | Hash/schema/checkpoint verification |
| `VALIDATING` | Reload/repair completed | Synthetic and targeted tests | Validation report |
| `LIMITED_RETURN` | Validation passed | Small guarded production share | Soak evidence and no regression |
| `AVAILABLE` | Soak completed | Normal | Closure receipt |

Any failed validation returns to `ISOLATED` or rolls back to the last verified generation. A non-repairable resource transitions to a retired state outside the happy-path sequence.

