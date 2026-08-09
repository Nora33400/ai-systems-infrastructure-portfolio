# Hybrid Dev Mode (Mode 1 + Mode 2)

This ZIP enables a hybrid strategy:
- **Mode 1 (Pulse-Weave):** follow an L/S/M pattern (Long/Short/Medium).
- **Mode 2 (Race-to-Useful):** prefer tasks that have a usefulness contract (goal/proof/integration/rollback).

## Seed config
`workspace/seeds/active.seed.json`

```json
{
  "dev_mode": "hybrid",
  "weave_pattern": ["L","S","M","L","L","S","S","M","L","M","M","S","M","M"],
  "task_timeboxes": {"S": 20, "M": 60, "L": 240},
  "useful_threshold": 0.35
}
```

## Coherence behavior ("coherence 100%" idea)
- If **C** is low or **N** is high → the system forces **S** tasks.
- If **P** is high and desired is **L** → the system degrades to **M** tasks.
- Every pick is logged as `task.pick` into the main ledger.
