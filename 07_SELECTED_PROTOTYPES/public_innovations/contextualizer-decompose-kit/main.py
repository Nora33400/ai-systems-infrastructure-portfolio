from __future__ import annotations

import argparse
import json
from typing import Dict, List


def classify_entry(entry: str) -> str:
    low = entry.lower()
    if any(k in low for k in ["latence", "queue", "charge", "oscillation", "flux", "runtime"]):
        return "dynamic"
    return "static"


def decompose(context: str, entries: List[str]) -> Dict:
    rows = []
    for idx, item in enumerate(entries, start=1):
        kind = classify_entry(item)
        priority = "high" if kind == "dynamic" else "medium"
        rows.append({
            "id": f"arg-{idx:03d}",
            "kind": kind,
            "priority": priority,
            "text": item,
            "context": context,
        })
    return {
        "context": context,
        "static_count": sum(1 for r in rows if r["kind"] == "static"),
        "dynamic_count": sum(1 for r in rows if r["kind"] == "dynamic"),
        "arguments": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Contextualizer decompose kit")
    parser.add_argument("--context", required=True)
    parser.add_argument("--entries", required=True, help="JSON list of strings")
    args = parser.parse_args()

    data = decompose(args.context, json.loads(args.entries))
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
