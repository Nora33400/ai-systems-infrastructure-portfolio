from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(workspace: Path, kind: str, payload: dict) -> None:
    path = workspace / "events" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": utc_now(), "kind": kind, "payload": payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def read_events(workspace: Path, limit: int = 50) -> list[dict]:
    path = workspace / "events" / "events.jsonl"
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        raw = line.strip()
        if not raw:
            continue
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            items.append(
                {
                    "ts": utc_now(),
                    "kind": "events_corrupt_line_skipped",
                    "payload": {"preview": raw[:160]},
                }
            )
    return items
