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
