# Curated Requirement-to-System Reference Slice

This directory is a public portfolio subset, not the full original repository.

It retains five requirement/source directives, a curated manifest and architecture graph, assumptions and contradictions, seven representative module contracts, TypeScript autonomy/cognitive implementations, schemas, deterministic tests, and three receipts referenced by tests.

## Reproduce

From this directory with Node.js 24+:

```bash
npm install --ignore-scripts
npm test
```

The test command compiles the retained TypeScript tree and runs every compiled test under `tests/autonomy` and `tests/cognitive`. Real Ollama integrations are expected to skip when no endpoint is configured. One historical receipt hash check is explicitly skipped because public redaction changed the receipt content; schema validation remains active.

## Maturity boundary

- `src/autonomy` and `src/cognitive`: implemented and tested within the recorded local scope.
- `modules/*`: selected architecture/contracts; these documents are not themselves executable proof.
- synthetic GPU telemetry: scheduling-policy evidence only, not physical cluster validation.
- external connectors and canonical source mutation: excluded or disabled.

