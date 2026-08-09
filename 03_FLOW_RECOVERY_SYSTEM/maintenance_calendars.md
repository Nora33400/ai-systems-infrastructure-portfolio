# Overlapping Maintenance Calendars

Status: **P2 architecture**.

Maintenance uses multiple horizons because a single periodic loop either reacts too slowly or performs expensive work too often.

| Horizon | Typical scope | Example actions |
| --- | --- | --- |
| Short cycle | Seconds to minutes | heartbeat, queue stall, thermal limit, free RAM/disk, failed dependency |
| Daily cycle | Trend and recoverability | ledger integrity, backup creation, sample restore, error-rate drift, capacity review |
| Weekly cycle | Deeper falsification | full restore test, benchmark sample, dependency audit, failure-injection rehearsal, wear balance |
| Long-term | Version/lifecycle | schema migration rehearsal, hardware trend, retention, retirement, architecture revision |

## Overlap rules

- Calendars are independent triggers feeding one maintenance queue.
- Equivalent work deduplicates by action + target + evidence version.
- Safety incidents preempt routine maintenance.
- A weekly task may satisfy the same day’s daily task only if it meets or exceeds its acceptance criteria.
- Maintenance concurrency is limited so that diagnostics do not become a resource failure.
- Failed maintenance creates an incident; it is not silently rescheduled forever.
- Long-running work checkpoints so that short-cycle safety actions can interrupt it.

The AIONE source contains short-loop workers, daily intelligence, week-soak analysis, and recovery policies. Their integration into this exact unified calendar model is not claimed.

