from __future__ import annotations

import argparse
import json
from typing import Dict, List


SAFE_ALLOWLIST = {"System", "explorer.exe", "svchost.exe", "dwm.exe", "Memory Compression"}


def process_score(proc: Dict, threshold_mb: int) -> int:
    score = 0
    name = str(proc.get("name", ""))
    rss_mb = int(proc.get("rss_mb", 0))
    cpu = float(proc.get("cpu_pct", 0.0))

    if rss_mb > threshold_mb:
        score += 3
    if cpu > 15:
        score += 2
    if name.lower().startswith("chrome") or name.lower().startswith("code"):
        score += 1
    if name in SAFE_ALLOWLIST:
        score = 0
    return score


def suggest_close(processes: List[Dict], threshold_mb: int = 700, close_score: int = 4) -> Dict:
    rows = []
    for p in processes:
        s = process_score(p, threshold_mb)
        rows.append({**p, "score": s, "candidate_close": s >= close_score})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return {
        "count": len(rows),
        "candidates": [r for r in rows if r["candidate_close"]],
        "all": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Process Governor")
    parser.add_argument("--processes", required=True, help="JSON list")
    parser.add_argument("--threshold-mb", type=int, default=700)
    parser.add_argument("--close-score", type=int, default=4)
    args = parser.parse_args()

    processes = json.loads(args.processes)
    result = suggest_close(processes, args.threshold_mb, args.close_score)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
