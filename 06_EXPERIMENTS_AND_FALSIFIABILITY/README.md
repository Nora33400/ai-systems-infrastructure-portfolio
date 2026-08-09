# Experiments & Falsifiability

Evidence level: **P4-U for specific deterministic tests and P4-M for recorded local measurements**.

## Experimental discipline

A claim is useful only when its failure conditions are visible. The selected work uses several mechanisms to make architecture challengeable:

- baseline versus candidate comparisons;
- deterministic hashes and explicit provenance;
- adversarial/negative cases;
- fixed resource and token budgets;
- thermal stop conditions;
- separation of relative cost from absolute cost;
- contradiction and unsupported-claim counters;
- test gates before promotion;
- retained failures and abort reports.

## Selected experiments

### Minimum Materialization Runtime

The copied [MMR reports](../01_AIONE_FRACTALOS/docs/aione/mmr_release_reports/) cover dual-cost validation, long-horizon simulated cycles, an external workload adapter, answer-quality checks, and seven reported real-user task types. The reports are historical project artifacts. Their headline results must be interpreted with the implementation and [tests](../01_AIONE_FRACTALOS/source/aione/tests/test_aione_mmr.py), not as independent scientific validation.

### Local model benchmark

The [sanitized RTX 4060 report](../evidence/benchmarks/local-model-benchmark-rtx4060.json) contains four requests at one repetition. It records quality, contract compliance, p50/p95 latency, tokens per second, GPU samples, individual results, and a checksum. The [summary](../evidence/benchmarks/README.md) states the exact limitations.

### Thermal abort

The [RTX 3060 abort report](../evidence/benchmarks/local-model-benchmark-rtx3060-thermal-abort.json) is useful negative evidence: the run crossed 82 °C and did not produce a quality report. A safe abort is not counted as benchmark success.

### Controlled research lab

The [implementation](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/controlled-research-lab.mjs) restricts source URLs, refuses embedded credentials, detects prompt-injection patterns, and records research cycles. The [test suite](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/controlled-research-lab.test.mjs) is reproduced in the selected Node test record.

## Falsification checklist

For any new result:

1. State hardware, software, model, seed, workload, and repetition count.
2. Preserve raw result and failure/abort artifacts.
3. Define success before running the test.
4. Separate correctness, quality, cost, latency, and safety metrics.
5. Include negative and boundary cases.
6. Compare with a baseline where meaningful.
7. Avoid generalizing beyond the sampled environment.
8. Downgrade the evidence level when reproduction fails.

## Known insufficiencies

- The selected local-model run has only one repetition.
- MMR tasks and scoring were designed within the project and are not independent benchmarks.
- Dual-GPU audit history found extreme repetition in early generated output; the audit is retained because it documents the failure and correction.
- No industrial cluster, network-failure, or multi-node thermal-rotation benchmark is present.
