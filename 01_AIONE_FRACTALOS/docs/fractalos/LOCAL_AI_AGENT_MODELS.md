# FractalOS Local AI Agent Models

FractalOS connects free/local-first Ollama models to its agent orchestrator.

## Default Roles

- Planner: `llama3.2:3b` or `qwen2.5-coder:7b`.
- Builder: `qwen2.5-coder:7b`.
- Patcher: `qwen2.5-coder:7b` or `deepseek-coder-v2:16b`.
- Reviewer: `qwen2.5-coder:7b` or `deepseek-coder:6.7b`.
- Documenter: `llama3.2:1b` or `llama3.2:3b`.
- Evolver: `deepseek-coder-v2:16b` when hardware allows.

## Pull Commands

```powershell
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull llama3.2:1b
ollama pull deepseek-coder:6.7b
ollama pull deepseek-coder-v2:16b
```

## Commands

```powershell
python -m omega_tile_os ai-model-catalog --workspace .\workspace
python -m omega_tile_os ai-model-plan --workspace .\workspace
python -m omega_tile_os ollama-idea --workspace .\workspace --idea "Ameliore le scheduler" --queue-agents
```

## Optimization

Coding and patching roles use lower temperature for deterministic edits. Documentation
and summarization roles use slightly higher temperature for clarity. If Ollama is not
available, FractalOS still produces a safe fallback plan and pull instructions.
