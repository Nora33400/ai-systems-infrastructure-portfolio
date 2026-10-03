# Suggestion Matrix / Reference Fusion Engine

## Purpose

The Suggestion Matrix turns a suggestion from a single generated answer into a verifiable projection across multiple independent axes and references.

The engine exposes alternatives, evidence, dependencies, conflicts, costs, provenance, and temporal implications. It does not automatically choose a candidate for the human.

## Multi-reference model

A suggestion may reference a project, checkpoint, iteration, TileMindFS tile, capability, verification, provenance record, TimeWarp event, or alternative branch simultaneously.

```text
S-042
├── temporal_ref   → TimeWarp checkpoint
├── semantic_ref   → TileMindFS tile
├── causal_ref     → dependency graph
├── provenance_ref → creator/source
├── structural_ref → Forge architecture
├── evidence_ref   → verification
└── counterfact_ref → alternative branch
```

## Axes

1. temporal
2. semantic
3. structural
4. causal
5. resource
6. economic
7. security
8. provenance
9. coherence
10. creator
11. context
12. lifecycle

Missing information is represented as unknown rather than silently inferred.

## Pipeline

```text
NEW SUGGESTION
 → REFERENCE RESOLUTION
 → MULTI-AXIS PROJECTION
 → TEMPORAL IMMUNITY
 → COHERENCE
 → PROVENANCE
 → RESOURCE / ECONOMIC ANALYSIS
 → CANDIDATE SET
 → HUMAN SELECTION
 → TIMEWARP CHECKPOINT
 → EXECUTION
 → VERIFICATION
 → ARCHIVOR
```

## TimeWarp

A selected candidate can attach to a TimeWarp checkpoint and be tested on the current timeline, an isolated branch, a replay, or an alternative branch. Rollback restores a known checkpoint without deleting archived history.

## TileMindFS

References remain addressable instead of replaying the entire project history:

```text
tile://project/P42/context/L3/paragraph/17
tile://project/P42/checkpoint/latest
tile://project/P42/suggestion/S042
tile://project/P42/timewarp/TW07
```

The engine starts at the smallest contextual locality sufficient for verification and expands only when dependencies or acceptance criteria require it.

## Creator Selector

Creator identity describes origin/authorship and does not grant execution authority. Provenance conflicts quarantine the suggestion rather than silently reassigning its creator.

## AgenticMemory reference

`agentralabs/agentic-memory` is registered as a reference-only upstream. Its public repository describes persistent graph memory with temporal, semantic, causal, entity and procedural indexes, supersession chains, drift detection, hybrid retrieval, and MCP access. These capabilities are relevant to Reference Fusion, but upstream code is not automatically copied, executed, or enabled.

## Security

- network denied by default
- external MCP denied by default
- upstreams remain reference-only until license/security review
- no self-escalation
- no silent provenance reassignment
- no silent state overwrite
- human selection before execution
- protected actions require human approval
- accepted checkpoints remain immutable
