# Agentic Forge GitHub integration

This layer integrates selected upstream projects as **external components/adapters**, not copied source code.

## Architecture

Phone/PWA + PC UI → AIONE/Forge Admin Orchestrator → Rank / Role / Skill / Tool / Resource / Action / Context / Approval policy → MCP gateway → local agents and external connectors.

## Selected upstream projects

| Project | Role | Integration mode |
|---|---|---|
| forge-agents/forge | agentic Forge base | adapter / optional submodule |
| JConradoN/agentforge | lightweight agentforge reference | adapter |
| ForgeAILab/forge | Forge implementation reference | adapter |
| LittleBlacky/AgenticFORGE | agentic workflow reference | adapter |
| adrien-morel/mcp-ollama-agent | Ollama + MCP bridge | local adapter |
| darthzen/ollama-code-mcp | Ollama coding MCP | local adapter |
| niklasmeixner-langdock/mcp-context-forge | MCP gateway/context reference | gateway adapter |
| microsoft/agent-forge | agent orchestration reference | orchestration adapter |
| teragrid/forge | Forge reference implementation | adapter |
| samhu1/openagent | open agent reference | adapter |
| pvnc228/local-coding-agent | local coding agent | coding adapter |

Each upstream repository stays isolated. No upstream source is silently vendored into this portfolio.

## Security model

- Core execution remains local-first.
- Network/external MCP access is denied unless explicitly enabled by policy.
- OAuth connectors are templates only until credentials and scopes are explicitly configured.
- Agents cannot promote themselves.
- Rank does not grant permissions automatically.
- Every write/execute/escalation action can require human approval.
- Git worktrees/sandboxes are the default isolation boundary.

## Permission chain

RANK → ROLE → SKILL → TOOL → RESOURCE → ACTION → CONTEXT → APPROVAL

Ranks: R0 observer, R1 worker, R2 coder, R3 executor, R4 delegator, R5 orchestrator, R6 admin, R7 root.

A higher rank never bypasses an explicit deny rule.

## Long-horizon planning

The Forge now has a persistent planning contract for long missions: ROOT → PHASE → ITERATION → SUBTASK → VERIFICATION. Iterations are referenceable records, not disposable prompt text. Replanning changes the unfinished frontier while preserving completed iteration history. See `docs/agentic-forge/LONG_HORIZON_PLANNING.md` and `config/agentic-forge/planning.json`.

## Central fusion proposal

The upstream projects are treated as a capability pool rather than as competing cores. Forge acts as the central integration layer and selects capabilities through adapters.

### Capability fusion

| Capability | Central Forge role |
|---|---|
| Agent runtime / workflow | Agent execution layer |
| Long-horizon planning | Adaptive causal decomposition |
| Context management | Context-locality selector |
| Memory | Persistent, addressable iteration memory |
| MCP | Tool/resource gateway |
| Local coding | Isolated coding workers |
| DAG/orchestration | Dependency and causal scheduler |
| Verification | Acceptance and composition gate |
| Policy/security | Rank → Role → Skill → Tool → Resource → Action → Context → Approval |

The central fusion does **not** mean copying all projects into one codebase. It means defining stable interfaces and selecting compatible capabilities while preserving provenance, isolation, and license boundaries.

### Fusion principles

1. **One central orchestrator** — Forge/AIONE owns task state, planning, scheduling and approval.
2. **Specialized capabilities** — upstream projects contribute bounded capabilities through adapters.
3. **Local-first execution** — local components are preferred; network access remains deny-by-default.
4. **Causal planning** — a child iteration cannot consume an output that its causal predecessor has not verified.
5. **Adaptive N** — the number of iterations is derived from complexity and locality, not fixed at five.
6. **Context locality** — hydrate the smallest sufficient context: letter → word → sentence → paragraph → paragraph series → short/medium/long file.
7. **License boundary** — open-source, free-to-use and license-free/unknown are distinct states; unknown terms remain reference-only until reviewed.
8. **No silent replacement** — an upstream capability cannot overwrite the central policy or human approval model.

### Target architecture

```text
                       CENTRAL FORGE / AIONE
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Planning & Causality   Context & Memory     Policy & Approval
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                       Capability Gateway
                              │
       ┌──────────┬───────────┼───────────┬──────────┐
       │          │           │           │          │
     Agents      MCP       Coding      DAG/Async   Verify
       │          │           │           │          │
       └──────────┴───────────┴───────────┴──────────┘
                              │
                    Local workers / adapters
```

The objective is a **central fusion architecture**, not a forced merger of unrelated upstream implementations.

## TileMindFS memory fusion

The central memory layer is now specified as **Forge/AIONE → MemoryManager → TileMindFS**. The manager separates ACTIVE/HOT/WARM/COLD memory, uses context locality to keep hydration bounded, deduplicates repeated payloads through canonical content hashes, and checkpoints before eviction. See `config/agentic-forge/memory.json` and `docs/agentic-forge/TILEMINDFS_MEMORY_INTEGRATION.md`.

The **memory aspirator** releases inactive hydrated context after a recoverable checkpoint. The **emergency compactor** performs checkpoint → compact/externalize → release → restore-on-demand under memory pressure. These are recoverable cache-management mechanisms, not silent deletion mechanisms.

### Expanded capability pool

The upstream registry now also tracks reference candidates for MCP ecosystems, MCP apps, coding-agent MCP, web tooling, long-term memory, subagents and agent security scanning. They remain disabled and reference-only until compatibility, license/terms, security and local-first constraints are reviewed.

Examples include:

- `perplexityai/modelcontextprotocol` — MCP ecosystem reference
- `modelcontextprotocol/ext-apps` — MCP app/extension reference
- `awslabs/mcp` — MCP tool-server collection reference
- `funkyfunc/coding-agents-mcp` — coding-agent MCP reference
- `web-mcp/web-mcp` — web-tooling MCP reference
- `GoodAI/goodai-ltm` — long-term-memory reference
- `edxeth/pi-subagents` — subagent runtime reference
- `vstorm-co/subagents-pydantic-ai` — typed subagent reference
- `snyk/agent-scan` — agent security scanning reference

The fusion rule remains **capability composition, not source-code accumulation**: Forge owns policy, planning and approvals; adapters expose bounded capabilities; TileMindFS owns durable addressable context; workers remain isolated.

## Project rooms and cycle superposition

Forge now models projects as a canonical `project_id` projected into multiple contextual rooms rather than duplicated into separate project copies. Strategy, research, architecture, build, verification, operations and review can therefore coexist while retaining one source identity.

Cycles may overlap in wall-clock time. Execution order is determined by causal dependencies and verification gates. Room handoffs use stable checkpoint references instead of replaying complete histories. GitHub repositories, branches, issues, pull requests and commits are linked artifacts of the project rather than separate project identities.

See `config/agentic-forge/project_rooms.json` and `docs/agentic-forge/PROJECT_ROOMS_AND_CYCLES.md`.
