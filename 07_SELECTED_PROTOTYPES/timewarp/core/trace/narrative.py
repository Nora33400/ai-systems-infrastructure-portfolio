from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, Optional

def _t(ev: Optional[Dict[str, Any]]) -> str:
    if not ev: return "?"
    return str(ev.get("t_wall") or ev.get("timestamp") or "?")

def natural_narrative(chain: Dict[str, Any], seed_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    a=chain.get("action"); r=chain.get("reaction"); rep=chain.get("repercussion",{}) or {}
    seed_ctx = seed_ctx or {}
    dom = (seed_ctx.get("context") or {}).get("domain") or seed_ctx.get("domain") or "OmegaFusion"
    goal = seed_ctx.get("goal") or "?"
    omega = float(rep.get("omega_delta_sum",0.0))
    conf = float(chain.get("confidence",0.0))
    modes = rep.get("modes",[]) or []
    lines=[]
    lines.append(f"[{dom}] Goal={goal}")
    lines.append(f"Action ({_t(a)}): {a.get('type')} (task_id={a.get('task_id','?')})")
    if r:
        lines.append(f"Reaction ({_t(r)}): {r.get('type')} (confidence={conf:.2f})")
    else:
        lines.append(f"Reaction: none detected (confidence={conf:.2f})")
    lines.append(f"Repercussion: ω_sum={omega:.3f} across {rep.get('omega_delta_count',0)} deltas; recent modes={modes[-3:]}")
    if omega > 0.5:
        lines.append("Conclusion: net positive impact (productive + stable).")
    elif omega < -0.2:
        lines.append("Conclusion: negative impact detected (needs stabilization).")
    else:
        lines.append("Conclusion: neutral / unclear impact (collect more evidence).")
    return {
        "trace_id": chain.get("trace_id"),
        "type": "narrative.natural",
        "t_wall": datetime.now().isoformat(),
        "text": "\n".join(lines),
        "meta": {"confidence": conf, "omega_sum": omega}
    }

def contextual_trace(chain: Dict[str, Any], seed_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    a=chain.get("action"); r=chain.get("reaction"); rep=chain.get("repercussion",{}) or {}
    seed_ctx = seed_ctx or {}
    ctx = seed_ctx.get("context") or {}
    omega = float(rep.get("omega_delta_sum",0.0))
    conf = float(chain.get("confidence",0.0))
    modes = rep.get("modes",[]) or []
    proof = {
        "link_confidence": conf,
        "windows": {"reaction_s": seed_ctx.get("reaction_s",120), "repercussion_s": seed_ctx.get("repercussion_s",1800)},
        "modes_tail": modes[-8:],
    }
    claim = "Impact(A)>0" if omega>0.5 else ("Impact(A)<0" if omega<-0.2 else "Impact(A)≈0")
    return {
        "trace_id": chain.get("trace_id"),
        "type": "narrative.context",
        "t_wall": datetime.now().isoformat(),
        "CTX": {
            "seed_id": seed_ctx.get("seed_id"),
            "goal": seed_ctx.get("goal"),
            "domain": ctx.get("domain"),
            "observer": ctx.get("observer"),
            "scope": ctx.get("scope")
        },
        "A": {"type": a.get("type") if a else None, "task_id": a.get("task_id") if a else None, "t": _t(a)},
        "R": {"type": r.get("type") if r else None, "t": _t(r)},
        "P": {"omega_sum": omega, "omega_count": rep.get("omega_delta_count",0)},
        "Proof": proof,
        "Claim": claim
    }

def dumps_jsonl(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"
