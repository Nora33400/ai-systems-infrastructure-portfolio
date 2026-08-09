from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    lane: str


ROUTES = {
    "analysis": ModelRoute(provider="ollama", model="qwen2.5-coder:7b", lane="cpu_reasoning"),
    "planning": ModelRoute(provider="ollama", model="mistral:7b", lane="cpu_reasoning"),
    "code": ModelRoute(provider="ollama", model="deepseek-coder:6.7b", lane="gpu_code"),
    "testing": ModelRoute(provider="ollama", model="codellama:7b", lane="gpu_code"),
    "documentation": ModelRoute(provider="ollama", model="llama3.1:8b", lane="cpu_writer"),
    "chat": ModelRoute(provider="ollama", model="llama3.1:8b", lane="interactive"),
}


def pick_route(task_type: str, *, fallback: str = "chat") -> dict[str, Any]:
    key = str(task_type or "").strip().lower()
    row = ROUTES.get(key) or ROUTES.get(fallback) or ROUTES["chat"]
    return {"task_type": key, "provider": row.provider, "model": row.model, "lane": row.lane}


if __name__ == "__main__":
    for t in ["analysis", "planning", "code", "testing", "documentation", "chat"]:
        print(json.dumps(pick_route(t), ensure_ascii=False))
