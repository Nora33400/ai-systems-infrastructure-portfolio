# MMR Dual Cost Validation

Benchmark: MMR-DUAL-COST-VALIDATION-0001
Query: kernel proof memory
Strategy: dual_cost_validation
Result: warn
Warning count: 10

## Scaling Sanity Check

| Corpus | Relative cost | Absolute tokens | Absolute latency ms | Rebuilt | Reused | Wasted prewarm | False positive | OOD fallback | Warnings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| x1 | 0.126 | 122 | 3.603 | 2 | 4 | 0.0 | 0.0 | 0.0 | 0 |
| x5 | 0.021 | 117 | 19.815 | 2 | 4 | 0.0 | 0.0 | 0.0 | 0 |
| x10 | 0.01 | 108 | 37.14 | 2 | 4 | 0.0 | 0.0 | 0.0 | 1 |
| x25 | 0.004 | 108 | 92.055 | 2 | 4 | 0.0 | 0.0 | 0.0 | 1 |

## Adversarial Benchmark

| Scenario | Relative cost | Absolute tokens | Absolute latency ms | Rebuilt | Wasted prewarm | False positive | OOD fallback | Warnings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Compressible corpus | 0.01 | 108 | 36.413 | 2 | 0.0 | 0.0 | 0.0 | 1 |
| Low compressible corpus | 0.012 | 144 | 37.279 | 2 | 0.0 | 0.0 | 0.0 | 1 |
| Random mutations | 0.01 | 108 | 36.775 | 2 | 0.0 | 0.0 | 0.0 | 1 |
| Out of distribution query | 0.031 | 126 | 31.631 | 2 | 1.0 | 0.5 | 1.0 | 3 |
| Bad predictions | 0.041 | 164 | 36.471 | 6 | 1.0 | 1.0 | 0.0 | 2 |

## DualCostReport

Each case records `relative_resolution_cost`, `absolute_materialization_cost`, `normalized_efficiency`, `scaling_efficiency` and `cost_discrepancy_warning`.

## Internal Engineering Result

The project-designed dual-cost checks expose when normalized relative gains hide absolute materialization, latency, memory, or prediction waste. Results apply only to these deterministic local cases.
