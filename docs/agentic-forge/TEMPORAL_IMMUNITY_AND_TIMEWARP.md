# Temporal Immunity + TimeWarp

## Goal

Give Forge/AIONE a temporal immune system: preserve verified invariants while allowing the project to evolve, branch, experiment, recover, and merge.

The system is not intended to freeze the project. It protects **verified identity, provenance, policy, coherence, and recovery points** while implementations remain replaceable.

## Architecture

```text
                    FORGE ORCHESTRATOR
                           |
          +----------------+----------------+
          |                |                |
   Creator Selector     Archivor      Temporal Immunity
          |                |                |
          +----------------+----------------+
                           |
                    TimeWarp Adapter
                           |
       +-------------------+-------------------+
       |                   |                   |
    branch              replay              rollback
       |                   |                   |
       +-------------------+-------------------+
                           |
                 Coherence / Verification
```

## Creator Selector

The Creator Selector answers **"who/what is the canonical origin of this project state?"**

It must not answer **"who is allowed to execute this action?"**.

That separation prevents authorship from becoming an implicit permission escalation.

## Archivor

The Archivor keeps immutable accepted checkpoints and provenance:

- project identity;
- creator binding;
- capability versions;
- policy versions;
- coherence reports;
- accepted outputs;
- TimeWarp transition records.

Archives are append-only after acceptance. Rollback changes the active timeline; it does not erase history.

## Temporal Immunity

Temporal immunity compares a proposed state transition against previously verified invariants.

A transition can therefore be:

- accepted;
- accepted after checkpoint;
- quarantined;
- rolled back to a verified checkpoint;
- sent to human review.

Examples of protected invariants:

```text
Identity
  + Provenance
  + Permission boundaries
  + Security policy
  + Coherence
  + Verification status
  + Resource safety
```

A changed implementation is not automatically a regression. The system distinguishes **intentional evolution** from **unverified or contradictory drift**.

## TimeWarp Connection

TimeWarp acts as the temporal event/checkpoint adapter.

Every transition should carry:

```text
parent_checkpoint
      -> transition
      -> verification
      -> archive
      -> new_checkpoint
```

Branching creates a new timeline reference while preserving the creator binding.

Merging requires coherence verification.

Rollback restores an active verified checkpoint but never deletes the archived timeline.

Replay uses bounded references rather than replaying the entire history into the model context.

## Orchestration Loop

```text
OBSERVE
  -> SELECT_CREATOR
  -> VERIFY_BASELINE
  -> CHECK_TEMPORAL_IMMUNITY
  -> EXECUTE_ISOLATED_TRANSITION
  -> VERIFY
  -> ARCHIVE
  -> COMMIT_TIMELINE
  -> CONTINUE

                    \\ failure / regression
                           |
                     QUARANTINE
                           |
                    RECOVER / REVIEW
```

## TileMindFS Compatibility

Checkpoint references can use stable TileMindFS identifiers:

```text
tile://project/<project_id>/timeline/<checkpoint_id>
tile://project/<project_id>/creator
tile://project/<project_id>/archive/<event_id>
tile://project/<project_id>/timewarp/<transition_id>
```

This keeps the temporal layer compatible with bounded context locality and avoids loading full project history.

## Security Invariants

- external network denied by default;
- external MCP denied by default;
- agents cannot self-escalate;
- creator selection does not grant permissions;
- permission changes require human approval;
- Git push and GitHub writes require human approval;
- destructive restoration is denied by default;
- archive history is never silently deleted.

## Intended Fusion

This branch is designed as an integration layer over the existing Forge architecture:

```text
AIONE / Forge
    |
    +-- Coherence
    +-- Economics
    +-- Project Rooms / Cycles
    +-- TileMindFS Memory
    +-- Long-Horizon Planning
    +-- Temporal Immunity
            |
            +-- Creator Selector
            +-- Archivor
            +-- TimeWarp Adapter
            +-- Recovery / Quarantine
```

The result is **one canonical project, many contextual views, many timelines, and one verified provenance chain**.
