# Omega TileMind OS Architecture

## 1. Core runtime

The runtime manages:

- queued intents
- system state
- agents
- events
- generated artifacts

## 2. TileMindFS

The file substrate stores content as deduplicated compressed tiles.

Primary objects:

- tiles
- file manifests
- reconstruction outputs
- storage report

## 3. Planner

The planning subsystem uses a public score:

`L = dP - lambda*dE - mu*C - rho*R + eta*Omega`

Where:

- `dP` = performance gain
- `dE` = energy cost
- `C` = complexity
- `R` = risk
- `Omega` = coherence score

## 4. OmegaRAM

The fast memory layer is inspired by the FractalFormulaCorpus themes:

- `tableau_state_indexing`
- `cube_compression_gpu`
- `scheduler_control`
- `cacheHit` safe skip
- `ID_tableau` state identity

OmegaRAM provides:

- hot / warm / cold memory tiers
- compressed page storage
- tableau identities for memory addressing
- promotion and demotion under byte budgets
- coherence-aware heat accumulation
- fast cache lookup with safe reuse semantics

## 5. Control plane

Two local surfaces:

- CLI
- HTTP daemon

## 6. Visualization plane

The dashboard exposes:

- node status
- queue
- agents
- artifacts
- tile metrics
- RAM metrics
- recent events

## 7. Improvement over previous OS

Compared to the prior local OS scaffold, this version adds:

- a true file substrate
- stronger planning math
- a tiered fast memory subsystem
- richer daemon surface
- automatic artifact archival into TileMindFS
