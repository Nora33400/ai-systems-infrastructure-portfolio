from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

KEYWORDS = {
    "obligation": re.compile(r"\b(must|shall|doit|obligatoire)\b", re.IGNORECASE),
    "interdiction": re.compile(r"\b(must not|shall not|interdit|forbidden|never)\b", re.IGNORECASE),
    "risk": re.compile(r"\b(risk|risque|danger|unsafe|incident)\b", re.IGNORECASE),
}


def classify(lines: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for line in lines:
        txt = line.strip()
        if not txt:
            continue
        tags = [name for name, rx in KEYWORDS.items() if rx.search(txt)]
        if not tags:
            continue
        out.append({"line": txt, "tags": ",".join(tags)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Policy Diff Guardian")
    ap.add_argument("--base", default="base_policy.txt")
    ap.add_argument("--candidate", default="candidate_policy.txt")
    ap.add_argument("--out", default="reports/policy_diff_report.json")
    args = ap.parse_args()

    base_path = Path(args.base)
    cand_path = Path(args.candidate)
    if not base_path.exists() or not cand_path.exists():
        raise SystemExit("Fichiers policy manquants. Cree base_policy.txt et candidate_policy.txt")

    base_lines = [x.strip() for x in base_path.read_text(encoding="utf-8").splitlines()]
    cand_lines = [x.strip() for x in cand_path.read_text(encoding="utf-8").splitlines()]

    base_set = {x for x in base_lines if x}
    cand_set = {x for x in cand_lines if x}

    added = sorted(list(cand_set - base_set))
    removed = sorted(list(base_set - cand_set))

    c_added = classify(added)
    c_removed = classify(removed)
    risk_delta = sum(1 for x in c_added if "risk" in x["tags"]) - sum(1 for x in c_removed if "risk" in x["tags"])

    report = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "base": str(base_path),
        "candidate": str(cand_path),
        "added_count": len(added),
        "removed_count": len(removed),
        "risk_delta": int(risk_delta),
        "added_controls": c_added,
        "removed_controls": c_removed,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "risk_delta": risk_delta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
