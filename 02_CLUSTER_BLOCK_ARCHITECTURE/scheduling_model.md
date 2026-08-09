# Scheduling Model

Status: **P2 model**, with P3/P4-U local policy tests and P4-M bounded local measurements.

For a feasible topology `T` and task `J`, minimize:

```text
cost(T, J) =
    w_latency      · predicted_latency
  + w_thermal      · thermal_risk
  + w_error        · error_risk
  + w_dependency   · correlated_failure_risk
  + w_migration    · state_transfer_cost
  + w_wear         · long_horizon_duty_imbalance
  + w_energy       · estimated_energy
  - w_locality     · data_and_repair_locality
```

subject to:

```text
capacity(block) >= demand(J)
state(block) in {AVAILABLE, LIMITED_RETURN}
policy_allows(block, J)
all_required_dependencies_healthy(T)
thermal_headroom(block) >= minimum_headroom(J)
```

## Admission and rotation

- Reject work when no topology satisfies hard constraints.
- Prefer downscaling or delayed execution over unsafe oversubscription.
- Rotate only when predicted benefit exceeds checkpoint + transfer + warm-up cost.
- Use temperature hysteresis; a device stopped at 82 °C should not immediately resume at 81 °C.
- Keep a repair reserve so that saturation does not consume every diagnostic path.

The existing [FractalOS scheduler](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/hetero_scheduler.py) and [dual-GPU policy](../01_AIONE_FRACTALOS/source/aione/config/dual-gpu-development.json) provide concrete local mechanisms. Bus-aware multi-node scoring and wear accounting remain unimplemented.
