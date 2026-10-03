# TileMindFS memory fusion

This document formalizes the memory layer proposed for the central Agentic Forge/AIONE architecture.

## 1. Central model

```text
Forge / AIONE
   │
   ├── Planning & Causality
   ├── Policy & Approval
   │
   └── MemoryManager
          │
          ├── ACTIVE  → bounded hydrated context
          ├── HOT     → recent reusable cache
          ├── WARM    → compressed/indexed local cache
          └── COLD    → TileMindFS durable records
                         │
                         └── artifacts / checkpoints / references
```

TileMindFS is the durable addressable layer. The MemoryManager decides what must stay hydrated for execution. Forge owns task state and policy.

## 2. Context locality and memory

The existing locality model remains authoritative:

`L0 letter → L1 word → L2 sentence → L3 paragraph → L4 paragraph series → L5 short file → L6 medium file → L7 long file`.

A worker starts at the smallest sufficient locality. If the acceptance criteria, dependency graph, ambiguity, or verification scope require more context, the manager expands the locality and records that expansion in the checkpoint.

After the action, the worker contracts back to the smallest sufficient locality.

## 3. Token memory

Token memory is not a second source of truth. It is an execution/cache representation.

The canonical path is:

```text
content
  → normalize
  → content hash
  → canonical TileMindFS reference
  → bounded hydration
  → model tokenization / inference cache
```

Identical payloads can therefore share a canonical reference instead of being copied into every agent context.

Recommended reference shape:

```text
tile://task/T42/context/L3/paragraph/17
tile://task/T42/context/L4/series/5
tile://task/T42/checkpoint/latest
tile://task/T42/output/iteration-07
```

## 4. Memory aspirator

The aspirator is a recoverable eviction mechanism, not a deletion mechanism.

Sequence:

1. Detect inactive or low-value hydrated context.
2. Check whether it is dirty.
3. Checkpoint dirty state before release.
4. Deduplicate by canonical content hash.
5. Summarize/index only when the original reference remains recoverable.
6. Persist the record in TileMindFS.
7. Release the active cache.
8. Keep the stable reference for on-demand restoration.

No silent deletion is allowed.

## 5. Emergency memory compactor

When memory pressure becomes high, the compactor protects execution continuity:

```text
pressure
  → checkpoint
  → freeze mutation
  → compact/externalize reconstructible state
  → release cache
  → continue with references
  → restore on demand
```

The pressure thresholds in `config/agentic-forge/memory.json` are example operational defaults only. They must remain configurable and must be calibrated against the actual runtime.

## 6. RAM / VRAM / persistent memory

These resources are deliberately separated:

- **CPU RAM:** active context, orchestration state and local caches.
- **GPU VRAM:** model inference state and runtime cache.
- **TileMindFS:** persistent context, artifacts and checkpoints.

The architecture does not assume that the RTX 4060 and RTX 3060 VRAM form one automatically pooled memory space. GPU placement remains an explicit scheduler decision.

## 7. Interfaces

The minimum adapter contract is:

- `resolve(ref)`
- `hydrate(ref, locality)`
- `checkpoint(task_id, iteration_id)`
- `dedup(content_hash)`
- `evict(ref, policy)`
- `restore(ref)`
- `summarize(ref, target_locality)`

These interfaces let different memory, MCP, agent and tooling projects contribute capabilities without replacing the central policy model.

## 8. Upstream fusion boundary

External GitHub projects are capability references/adapters by default:

```text
Upstreams
   ↓
Capability adapters
   ↓
Forge Capability Gateway
   ↓
Memory / MCP / Skills / Tools / Agents / Subagents
   ↓
TileMindFS + isolated workers
```

No upstream repository is automatically vendored or executed. License/terms must be reviewed before copying, modifying, redistributing or enabling external code.

## 9. Safety and continuity invariants

- Network and external MCP remain deny-by-default.
- Agents cannot self-escalate.
- Human approval gates remain authoritative.
- Completed iterations remain immutable and addressable.
- Every eviction is recoverable.
- Every locality expansion is recorded.
- Provenance is retained for derived memory.
- Memory optimization must not silently change task semantics.
