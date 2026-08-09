# TraceRanker (TimeWarp v3)

Goal: exploit seed/ledger outcomes by ranking chains:
Action → Reaction → Repercussion (over time)

## Endpoints (daemon)
- GET `/api/trace/rank?n=12&reaction_s=120&repercussion_s=1800`
- GET `/api/trace/report?trace_id=<16hex>`

## Outputs
- `workspace/ledger/narratives.jsonl` (human readable)
- `workspace/ledger/context_traces.jsonl` (contextual formula/proof)

## How linking works (heuristics)
- time windows
- correlation keys (task_id, path, agent, task)
- confidence score in [0..1]
