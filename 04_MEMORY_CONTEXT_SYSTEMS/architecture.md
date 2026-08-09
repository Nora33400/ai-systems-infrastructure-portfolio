# Memory and Context Architecture

## Logical tiers

| Tier | Purpose | Typical placement | Reactivation target |
| --- | --- | --- | --- |
| Hot | Active prompt, working set, current dependency frontier | GPU VRAM / pinned RAM | Immediate |
| Warm | Recent validated tiles and likely next dependencies | RAM | Low latency |
| Cold | Persistent indexed context and snapshots | NVMe | Bounded retrieval + verification |
| Frozen | Rarely used immutable/archive material | Compressed archival storage | Explicit deep reconstruction |

The physical placements are design guidance, not a demonstrated automated tiering engine across all four levels.

## Tile indexing and dependency graphs

Context is represented as small, attributable units with IDs, provenance, hashes, importance/confidence, logical temperature, and typed anchors. Dependency edges allow reactivation to retrieve the smallest connected set satisfying an intent, rather than loading an entire historical corpus.

## Compaction and reconstruction

Compaction preserves source content hashes and a bounded reconstruction summary. Reconstruction is budgeted by characters/tokens and mode (`QUICK`, `OPERATIONAL`, `DEEP_DOCUMENTATION`, `REFLEXIVE`). The selected thermal tile implementation tests reversible logical compaction and detects snapshot or ledger tampering.

## Context reactivation

```text
intent
  → identify anchor tiles
  → expand dependency frontier under budget
  → verify hashes/provenance
  → rank by relevance + confidence + temperature
  → materialize bounded context
  → record usage and update logical temperature
```

## Model routing

The model router should choose a model from task complexity, role, context size, latency budget, VRAM, and quality requirements. The included router is minimal; the AIONE control-plane source contains a richer quality/capability ladder and local benchmark harness.

## Persistent contexts and reflection/evolution

Persistent context is not unrestricted transcript retention. It is a versioned set of claims, decisions, evidence, unresolved questions, and compacted source units. Reflection proposes changes; tests and policy decide whether they advance. Evolution remains bounded, logged, and reversible.

