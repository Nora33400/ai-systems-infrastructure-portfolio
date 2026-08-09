import json, os
from datetime import datetime
from typing import Dict, Any, List

def append_event(path: str, event: Dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("t_wall", datetime.now().isoformat())
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def tail_events(path: str, n: int = 200) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out=[]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out[-n:]
