from __future__ import annotations
import json, os, hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---- Event IO ----

def load_events_jsonl(path: str, max_events: int = 5000) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out=[]
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if len(out) >= max_events:
                break
    return out

def _ts(ev: Dict[str, Any]) -> float:
    t = ev.get("t_wall") or ev.get("timestamp")
    if not t:
        return 0.0
    try:
        return datetime.fromisoformat(str(t)).timestamp()
    except Exception:
        return 0.0

# ---- Classification ----

ACTION_TYPES = {
    "command.forge", "code.write", "apply.done", "doc.write"
}
REACTION_TYPES = {
    "test.run", "debug.report", "task.await_approval"
}
# "task.done" can carry omega_delta/result - we treat as reaction if it follows an action

def classify(ev: Dict[str, Any]) -> str:
    t = str(ev.get("type",""))
    if t in ACTION_TYPES:
        return "A"
    if t in REACTION_TYPES:
        return "R"
    if t == "task.done":
        # classify later by context
        return "D"
    return "O"

# ---- Linking heuristics ----

def _corr_keys(ev: Dict[str, Any]) -> Dict[str, Any]:
    # Extract correlation keys we can match between events
    r = {}
    for k in ("task_id","agent","cycle","epoch"):
        if k in ev:
            r[k]=ev[k]
    # sometimes nested
    task = ev.get("task") or ev.get("name")
    if task:
        r["task"]=task
    # path inside result/payload
    res = ev.get("result") or {}
    if isinstance(res, dict):
        p = res.get("path") or res.get("write",{}).get("path") if isinstance(res.get("write"), dict) else None
        if p: r["path"]=p
    payload = ev.get("payload") or {}
    if isinstance(payload, dict):
        p = payload.get("path")
        if p: r["path"]=p
        cmd = payload.get("command")
        if cmd: r["command"]=cmd
    return r

def link_confidence(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    ka=_corr_keys(a); kb=_corr_keys(b)
    score=0.0
    for key in ("task_id","path","agent","task"):
        if key in ka and key in kb and ka[key]==kb[key]:
            score += 1.0
    # small bonus if same cycle
    if "cycle" in ka and "cycle" in kb and ka["cycle"]==kb["cycle"]:
        score += 0.25
    return min(1.0, score / 3.0)  # normalize

def build_chains(events: List[Dict[str, Any]], reaction_s: int = 120, repercussion_s: int = 1800) -> List[Dict[str, Any]]:
    # Sort by time
    evs = sorted(events, key=_ts)
    actions=[e for e in evs if classify(e)=="A"]
    chains=[]
    for a in actions:
        t0=_ts(a)
        # pick best reaction within window
        candidates=[e for e in evs if t0 < _ts(e) <= t0 + reaction_s and (classify(e) in ("R","D"))]
        best=None; best_c=0.0
        for r in candidates:
            c=link_confidence(a,r)
            if c>best_c:
                best=r; best_c=c
        # repercussion: metrics/omega movement over longer window based on task.done events
        rep=[e for e in evs if (best and _ts(best) < _ts(e) <= _ts(best)+repercussion_s) or (not best and t0 < _ts(e) <= t0+repercussion_s)]
        omega_deltas=[]
        modes=[]
        for e in rep:
            if e.get("type")=="task.done" and "omega_delta" in e:
                try: omega_deltas.append(float(e.get("omega_delta",0.0)))
                except Exception: pass
            if e.get("type")=="cycle.begin" and "mode" in e:
                modes.append(str(e.get("mode")))
        chain={
            "trace_id": trace_id(a, best),
            "action": a,
            "reaction": best,
            "confidence": best_c,
            "repercussion": {
                "omega_delta_sum": sum(omega_deltas),
                "omega_delta_count": len(omega_deltas),
                "modes": modes[-8:]
            }
        }
        chains.append(chain)
    return chains

def trace_id(action: Dict[str, Any], reaction: Optional[Dict[str, Any]]) -> str:
    h=hashlib.sha1()
    h.update(json.dumps(action, sort_keys=True, default=str).encode("utf-8"))
    if reaction:
        h.update(json.dumps(reaction, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()[:16]

# ---- Scoring ----

@dataclass
class ScoreWeights:
    w_omega: float = 1.2
    w_conf: float = 1.0
    w_mode_penalty: float = 0.6   # penalize throttle/quarantine/stabilize
    w_reaction_bonus: float = 0.3

def score_chain(chain: Dict[str, Any], w: ScoreWeights = ScoreWeights()) -> float:
    rep = chain.get("repercussion",{}) or {}
    omega = float(rep.get("omega_delta_sum",0.0))
    conf = float(chain.get("confidence",0.0))
    modes = rep.get("modes",[]) or []
    penalty = 0.0
    for m in modes:
        if m in ("throttle_mode","quarantine_branch","stabilize_mode"):
            penalty += 1.0
    reaction_bonus = 1.0 if chain.get("reaction") is not None else 0.0
    return (w.w_omega*omega) + (w.w_conf*conf) + (w.w_reaction_bonus*reaction_bonus) - (w.w_mode_penalty*penalty)

def rank_chains(chains: List[Dict[str, Any]], top_k: int = 12) -> List[Dict[str, Any]]:
    out=[]
    for ch in chains:
        s=score_chain(ch)
        out.append({
            "trace_id": ch["trace_id"],
            "score": s,
            "confidence": ch.get("confidence",0.0),
            "omega_delta_sum": (ch.get("repercussion",{}) or {}).get("omega_delta_sum",0.0),
            "action_type": (ch.get("action") or {}).get("type"),
            "action_task": (ch.get("action") or {}).get("task_id") or (ch.get("action") or {}).get("task"),
            "reaction_type": (ch.get("reaction") or {}).get("type") if ch.get("reaction") else None,
            "t_action": (ch.get("action") or {}).get("t_wall"),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_k]
