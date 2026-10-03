# Long-horizon Agentic Forge

This layer turns a long mission into a persistent task reference and a graph of bounded iterations.

## Core idea
The root task is the durable reference. The agent does not keep the entire mission in a prompt. Instead, each iteration is a first-class child record linked to the root:

ROOT → PHASE → ITERATION → SUBTASK → VERIFICATION

Each iteration records its own plan version, objective, dependencies, inputs, outputs, checkpoint and acceptance criteria. Completed iterations remain addressable by ID and are summarized into the parent context rather than copied wholesale into every future prompt.

## Planning/execution cycle
1. Create the root mission.
2. Decompose it into phases and iterations.
3. Resolve dependencies as a DAG.
4. Select only ready iterations.
5. Hydrate the worker with references: parent summary + active constraints + dependency outputs + latest checkpoint.
6. Execute in an isolated workspace.
7. Verify.
8. Persist the iteration checkpoint.
9. Update the root progress.
10. Replan only the unfinished frontier when the state changes.
11. Keep the historical iterations immutable and referenceable.

## Why this improves the existing Forge
The current portfolio policy already separates rank, role, skill, tool, resource, action, context and approval. This extension adds time/horizon state: a task can survive sessions, model changes, worker failures and replanning without losing the original reference.

The external references are deliberately separated:
- AgenticPlanning: persistent goals, decisions and commitments.
- ForgeAILab/forge: parent/child tasks, dependencies, ordered subtasks and project-scoped execution.
- longrunning_mcp_tools: asynchronous request/response pattern for work that must not block an agent call.
- Agentic Control Framework: task graph + context retrieval + next-action selection.
- Zenith: repeated gap finding, revisable plans, independent verification and disciplined stopping.

These projects are references/adapters; their code is not silently copied into this repository.

## Context rule
Do not send the complete historical transcript to every worker.

Use stable references instead:

Context(iteration) = RootSummary + ActiveConstraints + DependencyOutputs + LatestCheckpoint + RelevantArtifacts

A worker can explicitly request an older iteration by ID when its output is relevant. This makes context growth approximately proportional to the active frontier rather than the whole history.

## Replanning
A failed iteration does not erase the original plan. It creates a new plan revision and marks the affected unfinished nodes as needs_replan.

Completed iterations stay immutable. New iterations reference:
- supersedes_iteration_id when replacing an unfinished attempt;
- derived_from_iteration_ids when building on completed work;
- source_plan_version for reproducibility.

## Safety
Long-running does not mean autonomous without limits. The existing deny-by-default policy remains authoritative. Network, external MCP, OAuth, GitHub writes, pushes, permission changes and destructive actions stay gated by policy/human approval.

## Example
A root mission can become:
- R0: Design Forge vNext
  - P1: Architecture
    - I1.1: inventory existing adapters
    - I1.2: define task graph
    - I1.3: define checkpoint schema
  - P2: Implementation
    - I2.1: implement planner
    - I2.2: implement scheduler
    - I2.3: implement verifier
  - P3: Validation
    - I3.1: fault/replan tests
    - I3.2: persistence/restart tests
    - I3.3: approval-boundary tests

The orchestrator only expands the next useful frontier. It does not regenerate the entire mission on every turn.
