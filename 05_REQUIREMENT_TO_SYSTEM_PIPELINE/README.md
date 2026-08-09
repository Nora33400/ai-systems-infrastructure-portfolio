# Requirement-to-System Pipeline

Evidence level: **P4-I for the retained autonomy/cognitive code slice; P2 for the seven retained module contracts**.

This section is intentionally narrow. It shows how selected requirements become assumptions, contracts, code, tests, and revision evidence without retaining the original repository's broad conceptual corpus.

## Evidence chain

```mermaid
flowchart LR
    S["Five retained source directives"] --> A["Assumptions and contradictions"]
    A --> C["Contracts and JSON schemas"]
    C --> G["Curated architecture graph"]
    G --> I["Autonomy and cognitive TypeScript"]
    I --> T["Public deterministic tests"]
    T --> E["Three bounded receipts and validation records"]
```

## Claim → source → test → evidence

| Claim | Source | Test | Result / limitation |
| --- | --- | --- | --- |
| A local task can move through guarded states and persist hashed receipts | [`src/autonomy`](source/opti/src/autonomy/) | [`planning-phase1.test.ts`](source/opti/tests/autonomy/planning-phase1.test.ts) | Integration-tested locally; the pre-redaction hash assertion is explicitly skipped in the public copy |
| Resource admission reacts to synthetic dual-GPU telemetry | [`resource-planner.ts`](source/opti/src/autonomy/resource-planner.ts) | [`planning-phase2.test.ts`](source/opti/tests/autonomy/planning-phase2.test.ts) | Unit/integration behavior with patched telemetry, not physical multi-node validation |
| Bounded cognitive stages produce schema-gated, provenance-linked artifacts | [`src/cognitive`](source/opti/src/cognitive/) | [`pipeline.integration.test.ts`](source/opti/tests/cognitive/pipeline.integration.test.ts) | Integration-tested with local fixtures; real Ollama calls remain optional/skipped |
| Recovery, context, hardware and module boundaries are specified | [selected contracts](source/opti/modules/) | Contract evidence files and open questions | P2 documentation unless linked to executable source above |

## Public slice

- [curated source manifest](source/opti/SOURCE_MANIFEST.yaml)
- [assumptions](source/opti/ASSUMPTION_REGISTER.md) and [contradictions](source/opti/CONTRADICTION_REGISTER.md)
- [curated architecture graph](source/opti/ARCHITECTURE_GRAPH.yaml)
- [autonomy](source/opti/src/autonomy/) and [cognitive](source/opti/src/cognitive/) implementation
- [runnable tests](source/opti/tests/)
- [schemas](source/opti/schemas/) and three receipts used by tests
- seven representative module contracts: autonomy engine, CalContexte, dynamic context compression, hardware runtime, IMMUNE, Organum, and TileMindFS

## Deliberate exclusions

The public copy removes 1,027 Opti files: unrelated conceptual modules, organization/connectors material, internal agent instructions, broad constitutional documentation, generated planning history, unused receipts, and the repository-wide documentation validator tied to that excluded corpus. The earlier redaction/hash failures remain recorded in [`opti-tests.txt`](../evidence/tests/opti-tests.txt); they were not rewritten into false historical success.

