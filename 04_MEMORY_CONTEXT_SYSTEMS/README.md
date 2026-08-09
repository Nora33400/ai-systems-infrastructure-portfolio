# Memory & Context Systems

Evidence level: **P4-U for thermal context tiles; P3/P2 for the broader hierarchy**.

## Implemented evidence

- [Thermal context tiles](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.mjs): temperature scoring, hysteresis, append-only hashed events, snapshots, compaction, expansion, anchored reconstruction, and integrity verification.
- [Thermal tile tests](../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/thermal-context-tiles.test.mjs): transition bands, budgets, reversible logical zip/unzip, tamper detection, and reload.
- [FractalOS RAM memory](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/core/ram_memory.py) and [TileMind store/planner](../01_AIONE_FRACTALOS/source/fractalos/omega_tile_os/tilemindfs/).
- [AIONE reflection memory](../01_AIONE_FRACTALOS/source/aione/aione_cognitive_engine/memory/reflection-memory.mjs) and [reflective engine tests](../01_AIONE_FRACTALOS/source/aione/aione_cognitive_engine/tests/reflective-engine.test.mjs).
- [Local model router prototype](../07_SELECTED_PROTOTYPES/local_model_router/router.py).
- Selected contracts for [dynamic context compression](../05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/modules/dynamic-context-compression/), [CalContexte](../05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/modules/calcontexte/), and [TileMindFS](../05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti/modules/tilemindfs/).

## Tier mapping

The copied thermal store uses `COLD`, `WARM`, `HOT`, and `BURNING`. The requested storage vocabulary uses `hot`, `warm`, `cold`, and `frozen`. They are related but not identical:

- `HOT` / `BURNING` in the implementation represent highly active logical context, not unsafe hardware temperature.
- `FROZEN` is not an implemented state in the copied thermal tile store; it is an architecture-level archival tier.
- Physical placement across GPU VRAM, RAM, NVMe, and archival storage remains a policy layer around the logical context state.

See [architecture.md](architecture.md) and [memory hierarchy diagram](diagrams/memory_hierarchy.md).
