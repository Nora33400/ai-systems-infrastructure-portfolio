# Selection and Provenance

## Selection method

The portfolio was assembled from copies of existing local projects. Selection favored artifacts that directly support systems-engineering review: implementation source, runnable tests, machine-readable contracts, bounded runtime evidence, measured benchmark output, failure records, and architecture documents with explicit maturity limits.

Seven sections were retained because they collectively demonstrate orchestration, resource scheduling, recovery, memory/context handling, requirement traceability, measurement, and small executable prototypes. Project names alone were not a selection criterion.

## Exclusions

Duplicate archives, recovery copies, generated workspaces, continuous runtime snapshots, large research corpora, caches, model weights, dependency trees, databases, temporary files, publication helpers, and third-party boot tooling were excluded. These artifacts either duplicated stronger attributable evidence, carried privacy risk, were regenerable, or weakened reviewability.

The requirement-to-system section was reduced from 1,226 to 199 source/evidence files. It retains the executable TypeScript slice and representative contracts while removing broad conceptual documentation unrelated to the application claim.

## Provenance guarantees

- Every retained project artifact was copied into this independent portfolio directory.
- Original source projects were not moved, renamed, edited, or deleted.
- Copy-only changes are documented in the final audits and Git diff.
- Historical test/benchmark records are labeled separately from release-gate reproductions.
- Architecture-only material is not presented as implemented code.
- No external publication, repository creation, e-mail, or remote write occurred during preparation.

## Sanitation

The public copy removes or neutralizes personal names, account identifiers, personal e-mail addresses, profile-root paths, GPU UUIDs, runtime databases, operational prompts, private logs, connected-service state, and obsolete publication commands. Placeholder e-mail addresses use the reserved `.invalid` domain.

Four bounded QEMU serial logs are intentionally retained because they are direct boot evidence. The root ignore rules unignore only that evidence directory while continuing to reject arbitrary logs.

## Evidence retained

- AIONE and FractalOS implementation/test slices
- four QEMU serial logs and associated boot documentation
- one completed local-model benchmark and one thermal-abort record
- a deterministic single-machine flow/recovery integration demonstration
- a curated requirement → contract → code → test TypeScript slice
- compact TimeWarp, routing, policy, and repair prototypes
- reproduced release-gate test records and negative evidence

## Attribution limitations

AI assistants were used extensively; see [AUTHORSHIP_AND_AI_ASSISTANCE.md](AUTHORSHIP_AND_AI_ASSISTANCE.md). Some historical documents have mixed or incomplete line-level provenance, so the repository uses an all-rights-reserved licensing notice instead of asserting a clean repository-wide open-source license. Dependencies are referenced, not vendored.

