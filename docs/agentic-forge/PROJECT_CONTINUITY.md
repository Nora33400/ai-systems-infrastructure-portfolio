# Project Continuity & Stable Boundary Architecture

## Objective
Connect the complete project and its coherent branches through stable input/output points so work can move between branches without losing identity, provenance, verification state or rollback capability.

The continuity layer is deliberately non-destructive.

## Core rule
> A branch may connect to another branch through a verified contract; it may never silently overwrite the state from which it originated.

## Stable input points
- project manifest
- branch and commit identity
- archived checkpoint
- provenance record
- validated artifact
- human-approved request

## Stable output points
- verified artifact
- test receipt
- coherence report
- archived checkpoint
- promotion proposal
- rollback target
- human-review request

## Branch continuity
Branches are connected as a graph rather than flattened into one undifferentiated state.

origin -> branch -> isolated work -> verification -> checkpoint -> candidate merge -> coherence closure -> promotion

A branch retains identity, origin/parent, purpose, provenance, entry contract, exit contract and verification state.

## Complete-project continuity graph
project <-> branch <-> worktree <-> module <-> capability <-> reference <-> checkpoint <-> worker <-> interface

Edges: derived_from, depends_on, verified_by, compatible_with, branches_from, merges_into, exposes, consumes, archived_as.

## Failure continuity
| Failure | Response |
|---|---|
| Missing input | Stop at boundary |
| Invalid contract | Quarantine |
| Coherence failure | Branch and preserve |
| Verification failure | Reject promotion |
| Resource pressure | Checkpoint, degrade or stop |
| Unexpected state change | Temporal immunity + rollback |
| Network loss | Continue locally when safe |

## Local-first continuity
The local core remains the authoritative execution boundary. Android/tablet and iPhone interfaces are clients. External workers are untrusted until their outputs pass the same verification pipeline. Cloud capacity never becomes project authority merely because it has more compute.

Network, external MCP and OAuth remain denied by default.

## Merge continuity
A merge is not considered complete merely because Git can mechanically merge files. A valid project merge requires branch identity, provenance continuity, dependency coherence, policy compatibility, temporal consistency, resource feasibility, verification, rollback target and explicit promotion.

Conflicts are preserved and quarantined rather than silently discarded.

## Continuity invariant
> The project can grow across branches without losing a stable identity, and it can recover from a failed transition without destroying the history that explains how it got there.
