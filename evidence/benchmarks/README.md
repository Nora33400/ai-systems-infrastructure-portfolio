# Benchmark Evidence

## RTX 4060 local-model run

The sanitized [measured report](local-model-benchmark-rtx4060.json) records a local `qwen2.5-coder:7b` run on the RTX 4060 lane on 2026-08-03.

| Metric | Recorded value |
| --- | ---: |
| Cases / requests | 4 / 4 |
| Repetitions | 1 |
| Quality score | 78.75 |
| Contract compliance | 90.63 |
| Latency p50 | 30,336.182 ms |
| Latency p95 | 43,586.31 ms |
| Throughput | 48.021 tokens/s |
| Peak VRAM used | 7,350 MiB |

This is P4-M evidence for one recorded configuration, not a general model leaderboard. Deterministic consistency is `null` because only one repetition was run. The JSON retains the original checksum field, while portfolio sanitization of the GPU UUID means that checksum should be treated as provenance metadata rather than a checksum of the sanitized copy.

## RTX 3060 thermal abort

The [abort report](local-model-benchmark-rtx3060-thermal-abort.json) records a request stopped at the configured 82 °C threshold. It reports that generation was aborted without stopping the service, moving the model, downloading a model, or producing a quality score. This is evidence that the thermal guard took its fail-safe path; it is not a successful benchmark result.
