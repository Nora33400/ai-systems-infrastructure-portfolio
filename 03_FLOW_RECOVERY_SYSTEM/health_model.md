# Health Model

Status: **P1 formalized model**. No unified evaluator using these exact fields is claimed.

| Signal | Meaning | Example evidence |
| --- | --- | --- |
| `NodeHealth` | Aggregate ability of a node to accept and complete work | CPU/RAM availability, daemon liveness, failed jobs |
| `BusHealth` | Health of PCIe, storage, or network transfer paths | retries, corrected errors, throughput collapse, link reset |
| `FlowStability` | Whether queue and execution behavior remain bounded | queue growth, oscillation, timeout variance, repeated migration |
| `ThermalState` | Thermal headroom and trend, with hysteresis | temperature, slope, throttling, stop/resume band |
| `ErrorRate` | Failure frequency normalized by workload | failed operations per unit work/time |
| `Repairability` | Confidence that a bounded repair can restore service | known cause, verified backup, spare capacity, retry history |
| `DependencyRisk` | Probability/impact of correlated failure through shared dependencies | shared bus, model, storage, control plane, or power path |

## Decision vector

```text
HealthVector = {
  NodeHealth,
  BusHealth,
  FlowStability,
  ThermalState,
  ErrorRate,
  Repairability,
  DependencyRisk,
  confidence,
  observed_at,
  evidence_refs
}
```

The evaluator must preserve uncertainty. A stale or absent `BusHealth` signal lowers confidence; it must not default to healthy. Hard safety limits override aggregate scores.

