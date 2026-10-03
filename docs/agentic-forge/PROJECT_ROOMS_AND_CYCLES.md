# Project rooms, planning cycles and superposition

The Forge planning model now treats a project as one canonical object that can be **projected into several contextual rooms at the same time**.

## 1. Why rooms

A single project may simultaneously require:

- strategy decisions;
- research;
- architecture;
- implementation;
- verification;
- operations;
- human review.

Duplicating the project into seven independent copies would fragment state. Instead, Forge keeps one `project_id` and creates room-local views.

```text
                         PROJECT P42
                             │
             ┌───────────────┼───────────────┐
             │               │               │
          RESEARCH       ARCHITECTURE       BUILD
             │               │               │
             └───────────────┼───────────────┘
                             │
                       VERIFICATION
                             │
                         OPERATIONS
                             │
                           REVIEW
```

This is **contextual superposition**, not duplicated source state.

## 2. Planning rooms

The initial room types are:

| Room | Primary responsibility |
|---|---|
| Strategy | objectives, priorities, constraints |
| Research | hypotheses, references, experiments |
| Architecture | interfaces, system design, dependencies |
| Build | implementation and integration |
| Verification | tests, audits, acceptance |
| Operations | runtime, resources, maintenance |
| Review | human decisions and merge gates |

A project can occupy several rooms simultaneously.

## 3. Overlapping cycles

Cycles are hierarchical but may overlap in wall-clock time:

```text
MACRO CYCLE
 ├── PROJECT CYCLE A
 │    ├── ITERATION 01
 │    ├── ITERATION 02
 │    └── ITERATION 03
 │
 └── PROJECT CYCLE B
      ├── ITERATION 01
      └── ITERATION 02
```

The active execution frontier is determined by dependencies, not by forcing every project into one global linear sequence.

A cycle can therefore be active while another cycle is researching its next dependency.

## 4. Superposition rule

For project `P42`:

```text
P42
 ├─ Strategy / Cycle-12
 ├─ Research / Cycle-12
 ├─ Architecture / Cycle-13
 ├─ Build / Iteration-07
 └─ Verification / pending
```

These are not five projects.

They are five **views of P42** with different local contexts.

Each view stores:

- `project_id`
- `room_id`
- `cycle_id`
- local objective;
- relevant references;
- unresolved dependencies;
- next action;
- approval state;
- latest checkpoint.

## 5. Room handoff

Rooms communicate through references rather than replaying their entire histories:

```text
Research
   │
   └── checkpoint R17
          │
          ▼
Architecture
   │
   └── derived design A08
          │
          ▼
Build
   │
   └── implementation B21
          │
          ▼
Verification
```

A handoff records the source room, target room, project, cycle, checkpoint and reason.

## 6. GitHub integration

GitHub becomes an artifact graph attached to the canonical project:

```text
PROJECT
  │
  ├── repository
  ├── branch
  ├── issue
  ├── pull request
  └── commit
```

These references do not create separate project identities.

The project remains the source-level identity; GitHub artifacts describe implementation state.

## 7. Conflict resolution

When several rooms modify related state:

1. retain one canonical `project_id`;
2. preserve each room's local context;
3. compare checkpoints and provenance;
4. merge only verified outputs;
5. record conflicts explicitly;
6. never silently overwrite a newer verified state.

## 8. Connection with TileMindFS

Room context is naturally addressable through TileMindFS:

```text
tile://project/P42/room/research/cycle/12
tile://project/P42/room/architecture/cycle/13
tile://project/P42/room/build/iteration/07
tile://project/P42/checkpoint/latest
```

Only the locality required by the active room is hydrated.

This combines:

```text
Project identity
      ↓
Room superposition
      ↓
Cycle / iteration graph
      ↓
Context locality
      ↓
TileMindFS memory
      ↓
Agent / subagent execution
      ↓
Verification
      ↓
Human approval
```

## 9. Invariant

**One project, many contextual views; one canonical identity, many overlapping cycles; one verified history, many bounded contexts.**
