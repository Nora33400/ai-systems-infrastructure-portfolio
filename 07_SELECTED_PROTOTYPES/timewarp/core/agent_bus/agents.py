from typing import Dict, Any
import os, json
from core.agent_bus.cmdforge import create_command

def _tool(ctx, tool_name: str, **kwargs):
    return ctx.shared_state["tool"].call(ctx=ctx, role=ctx.shared_state["role"], tool_name=tool_name, **kwargs)

def _ledger(ctx, event: Dict[str, Any]):
    return _tool(ctx, "tool.ledger.append", workspace=ctx.workspace, relpath=ctx.ledger_relpath, event=event)

def planner_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    _ledger(ctx, {"type":"plan.emit","task_id":task.get("task_id"),"payload":task.get("payload",{})})
    return {"ok": True, "work_done": 1.4}

def coder_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    rel=p.get("path","artifacts/generated/hello.py")
    content=p.get("content","print('Hello OmegaFusion')\n")
    res=_tool(ctx,"tool.fs.write",workspace=ctx.workspace,relpath=rel,text=content)
    _ledger(ctx, {"type":"code.write","task_id":task.get("task_id"),"path":rel,"ok":res.get("ok")})
    return {"ok": bool(res.get("ok")), "work_done": 3.2 if res.get("ok") else 0.8, "write": res}

def debugger_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    args=p.get("args", ["python","-c","print('dbg')"])
    res=_tool(ctx,"tool.proc.run",workspace=ctx.workspace,args=args,timeout_s=int(p.get("timeout_s",60)))
    report={"ok":res.get("ok"),"returncode":res.get("returncode"),"stderr":res.get("stderr",""),"stdout":res.get("stdout","")}
    rep_path=p.get("report_path","artifacts/reports/debug_report.json")
    _tool(ctx,"tool.fs.write",workspace=ctx.workspace,relpath=rep_path,text=json.dumps(report,indent=2,ensure_ascii=False))
    _ledger(ctx, {"type":"debug.report","task_id":task.get("task_id"),"path":rep_path,"ok":report["ok"]})
    return {"ok": True, "work_done": 2.4, "debug": report}

def tester_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    tests_dir=os.path.join(ctx.workspace,"tests")
    if os.path.isdir(tests_dir):
        args=["python","-m","unittest","discover","-s","tests","-q"]
    else:
        args=p.get("args", ["python","-c","print('dummy tests: PASS')"])
    res=_tool(ctx,"tool.proc.run",workspace=ctx.workspace,args=args,timeout_s=int(p.get("timeout_s",60)))
    _ledger(ctx, {"type":"test.run","task_id":task.get("task_id"),"ok":res.get("ok"),"returncode":res.get("returncode")})
    return {"ok": bool(res.get("ok")), "work_done": 2.8 if res.get("ok") else 1.1, "test": res}

def applier_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    rel=p.get("path","artifacts/applied/result.txt")
    content=p.get("content","Applied change.\n")
    res=_tool(ctx,"tool.fs.write",workspace=ctx.workspace,relpath=rel,text=content)
    _ledger(ctx, {"type":"apply.done","task_id":task.get("task_id"),"path":rel,"ok":res.get("ok")})
    return {"ok": bool(res.get("ok")), "work_done": 2.1 if res.get("ok") else 0.7, "apply": res}

def doc_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    rel=p.get("path","docs/GENERATED.md")
    content=p.get("content","# Generated Documentation\n\nDocAgent wrote this.\n")
    res=_tool(ctx,"tool.fs.write",workspace=ctx.workspace,relpath=rel,text=content)
    _ledger(ctx, {"type":"doc.write","task_id":task.get("task_id"),"path":rel,"ok":res.get("ok")})
    return {"ok": bool(res.get("ok")), "work_done": 1.9 if res.get("ok") else 0.6, "doc": res}

def forge_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    p=task.get("payload",{})
    spec_text=p.get("spec","")
    ok, out = create_command(ctx.workspace, spec_text)
    _ledger(ctx, {"type":"command.forge", "task_id":task.get("task_id"), "ok":ok, "out":out})
    return {"ok": ok, "work_done": 2.6 if ok else 0.6, "out": out}


def trace_agent(ctx, task: Dict[str, Any]) -> Dict[str, Any]:
    """Build Action→Reaction→Repercussion chains from ledger and emit narratives."""
    from core.trace.trace_ranker import load_events_jsonl, build_chains, rank_chains
    from core.trace.narrative import natural_narrative, contextual_trace, dumps_jsonl

    p = task.get("payload", {}) or {}
    ledger_rel = p.get("ledger_path", ctx.ledger_relpath)
    nmax = int(p.get("max_events", 5000))
    reaction_s = int((p.get("windows") or {}).get("reaction_s", 120))
    repercussion_s = int((p.get("windows") or {}).get("repercussion_s", 1800))
    top_k = int(p.get("top_k", 12))

    # read ledger text via tool to keep workspace sandbox invariant
    # (but here we can directly read file because daemon already bounds workspace; for agent, use tool)
    # We'll use tool.fs.read for safety.
    read = _tool(ctx, "tool.fs.read", workspace=ctx.workspace, relpath=ledger_rel, max_bytes=2_000_000)
    if not read.get("ok"):
        _ledger(ctx, {"type":"trace.error","task_id":task.get("task_id"),"error":read.get("error")})
        return {"ok": False, "work_done": 0.6, "error": read.get("error")}

    # parse events
    txt = read.get("text","")
    evs=[]
    for line in txt.splitlines():
        line=line.strip()
        if not line: 
            continue
        try:
            evs.append(__import__("json").loads(line))
        except Exception:
            continue

    chains = build_chains(evs, reaction_s=reaction_s, repercussion_s=repercussion_s)
    ranked = rank_chains(chains, top_k=top_k)

    seed_ctx = p.get("seed_ctx") or {}
    seed_ctx["reaction_s"]=reaction_s
    seed_ctx["repercussion_s"]=repercussion_s

    out_nat = p.get("out_natural","ledger/narratives.jsonl")
    out_ctx = p.get("out_context","ledger/context_traces.jsonl")

    # emit narratives for top chains
    trace_count=0
    for item in ranked:
        tid=item["trace_id"]
        ch=next((c for c in chains if c.get("trace_id")==tid), None)
        if not ch:
            continue
        nat = natural_narrative(ch, seed_ctx=seed_ctx)
        ctxlog = contextual_trace(ch, seed_ctx=seed_ctx)
        _tool(ctx, "tool.fs.write", workspace=ctx.workspace, relpath=out_nat, text="")  # ensure exists (idempotent-ish)
        _tool(ctx, "tool.fs.write", workspace=ctx.workspace, relpath=out_ctx, text="")
        # append via ledger tool
        _tool(ctx, "tool.ledger.append", workspace=ctx.workspace, relpath=out_nat, event=nat)
        _tool(ctx, "tool.ledger.append", workspace=ctx.workspace, relpath=out_ctx, event=ctxlog)
        trace_count += 1

    _ledger(ctx, {"type":"trace.done","task_id":task.get("task_id"),"top_k":top_k,"emitted":trace_count})
    return {"ok": True, "work_done": 2.2, "top": ranked, "emitted": trace_count}
