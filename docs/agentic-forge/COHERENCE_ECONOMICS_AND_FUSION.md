# Coherence, economics and clean fusion

## 1. Coherence
A project has one canonical identity while rooms, cycles and iterations hold bounded contextual views. Coherence checks identity, dependencies, versions, temporal validity, semantic conflicts, resources, policy and verification.

## 2. Economics
Execution should minimize active tokens, RAM, VRAM, latency, duplication and recalculation while preserving correctness, provenance, security and reversibility. Value includes result value, reuse, time saved, token saved and human leverage. Cost includes compute, memory, tokens, latency, storage and risk.

Operational heuristic: expected value divided by total execution cost. This is a scheduling heuristic, not a financial guarantee.

## 3. Capability registry
Forge owns canonical capability identity. External projects contribute adapters. A capability moves from reference to candidate to adapter to tested to trusted to core-compatible only after required checks.

## 4. Fusion contract
Integration follows:
discover -> interface -> capability -> license -> security -> resource -> coherence -> isolate -> verify -> promote.

No external code is silently vendored. Network and external MCP remain deny-by-default.

## 5. Economic scheduler
The scheduler may choose CPU, RTX 4060, RTX 3060, or parallel local workers according to task requirements. GPU memory is not treated as automatically pooled. Causal dependencies and shared mutable state constrain parallelism.

## 6. State integrity
Economics never overrides policy. Coherence never silently resolves conflicts. Verification gates promotion. Completed verified records remain immutable and addressable.

## 7. Combined architecture
Project Graph -> Rooms/Cycles -> Coherence -> Planning/DAG -> Context/TileMindFS -> Capability Gateway -> Economic Scheduler + Policy -> isolated local workers -> Verify -> Review.

The result is a composable architecture rather than a monolithic merge of unrelated upstream projects.
