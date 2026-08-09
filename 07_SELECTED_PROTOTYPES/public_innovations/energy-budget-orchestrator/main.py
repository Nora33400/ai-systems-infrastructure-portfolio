from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class Task:
    task_id: str
    domain: str
    value: int
    watts: int
    latency_ms: int


def select_tasks(tasks: List[Task], watt_budget: int) -> List[Task]:
    # 0/1 knapsack by watts -> maximize value.
    n = len(tasks)
    cap = max(1, int(watt_budget))
    dp = [[0] * (cap + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        t = tasks[i - 1]
        for w in range(cap + 1):
            keep = dp[i - 1][w]
            take = -1
            if t.watts <= w:
                take = dp[i - 1][w - t.watts] + t.value
            dp[i][w] = max(keep, take)

    out: List[Task] = []
    w = cap
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            t = tasks[i - 1]
            out.append(t)
            w -= t.watts
    out.reverse()
    return out


def default_tasks() -> List[Task]:
    return [
        Task("T-vision", "vision", 82, 120, 90),
        Task("T-search", "semantic", 75, 80, 60),
        Task("T-proof", "safety", 94, 110, 130),
        Task("T-sim", "simulation", 88, 140, 180),
        Task("T-audio", "signal", 55, 50, 40),
        Task("T-plan", "planning", 70, 45, 35),
        Task("T-ui", "ux", 48, 30, 20),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Energy Budget Orchestrator")
    ap.add_argument("--watt-budget", type=int, default=260)
    ap.add_argument("--out", default="reports/energy_plan.json")
    args = ap.parse_args()

    tasks = default_tasks()
    selected = select_tasks(tasks, int(args.watt_budget))

    used = sum(t.watts for t in selected)
    value = sum(t.value for t in selected)
    avg_latency = (sum(t.latency_ms for t in selected) / max(1, len(selected)))

    report = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "watt_budget": int(args.watt_budget),
        "used_watts": int(used),
        "total_value": int(value),
        "avg_latency_ms": round(avg_latency, 3),
        "selected_tasks": [asdict(t) for t in selected],
        "dropped_tasks": [asdict(t) for t in tasks if t.task_id not in {x.task_id for x in selected}],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "selected": len(selected), "used_watts": used}, ensure_ascii=False))


if __name__ == "__main__":
    main()
