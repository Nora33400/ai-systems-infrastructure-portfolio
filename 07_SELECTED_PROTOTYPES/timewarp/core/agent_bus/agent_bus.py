from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Callable, List, Tuple
import time

from core.omega_clock.omega_clock import OmegaMetrics, delta_omega
from core.scheduler.scheduler import order, omega_budget
from core.coherence_guard.guard import GuardThresholds, decide

@dataclass
class AgentContext:
    workspace: str
    ledger_relpath: str
    policy: Dict[str, Any]
    thresholds: GuardThresholds
    shared_state: Dict[str, Any]

AgentFn = Callable[[AgentContext, Dict[str, Any]], Dict[str, Any]]

class AgentBus:
    def __init__(self):
        self._agents: Dict[str, Tuple[str, AgentFn]] = {}

    def register(self, agent_id: str, role: str, fn: AgentFn):
        self._agents[agent_id] = (role, fn)

    def list(self) -> List[Dict[str, str]]:
        return [{"id": k, "role": v[0]} for k, v in self._agents.items()]

    def run(self, agent_id: str, ctx: AgentContext, task: Dict[str, Any]) -> Dict[str, Any]:
        role, fn = self._agents[agent_id]
        ctx.shared_state["role"] = role
        return fn(ctx, task)

class Orchestrator:
    def __init__(self, bus: AgentBus, ledger_append_fn):
        self.bus = bus
        self.ledger_append_fn = ledger_append_fn
        self.omega = 0.0
        self.epoch = 0
        self.cycle = 0
        self.paused = False
        self.approvals = set()

    def set_paused(self, v: bool):
        self.paused = v

    def approve(self, approval_id: str):
        self.approvals.add(approval_id)

    def step(self, ctx: AgentContext, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.cycle += 1
        metrics = ctx.shared_state.get("metrics", {"C":0.92,"P":0.25,"N":0.06,"Q":1.0})
        mode, info = decide(metrics, ctx.thresholds)

        self.ledger_append_fn({"type":"cycle.begin","cycle":self.cycle,"epoch":self.epoch,"omega":self.omega,"mode":mode,"metrics":metrics,"info":info})

        if self.paused:
            self.ledger_append_fn({"type":"cycle.paused","cycle":self.cycle,"omega":self.omega})
            return {"ok": True, "mode": mode, "ran": None, "paused": True}

        if mode == "stabilize_mode":
            tasks = [t for t in tasks if t.get("kind") in ("stabilize","observe","debug")]
        elif mode == "quarantine_branch":
            tasks = [t for t in tasks if float(t.get("risk",1.0)) <= 0.25]

        tasks = order(tasks)
        if not tasks:
            self.ledger_append_fn({"type":"cycle.idle","cycle":self.cycle,"omega":self.omega})
            return {"ok": True, "mode": mode, "ran": None}

        # HYBRID dev-mode: Pulse-Weave (L/S/M) + Race-to-Useful (contract score)
        seed_cfg = ctx.shared_state.get("seed_cfg", {}) or {}
        dev_mode = str(seed_cfg.get("dev_mode","hybrid")).lower()
        if dev_mode in ("hybrid","pulse-weave","race-to-useful"):
            from core.dev_modes.hybrid import choose_task
            pattern = seed_cfg.get("weave_pattern") or ["L","S","M","L","L","S","S","M","L","M","M","S","M","M"]
            useful_threshold = float(seed_cfg.get("useful_threshold", 0.35))
            task, pick_info = choose_task(tasks, pattern=pattern, step_index=self.cycle,
                                         useful_threshold=useful_threshold, metrics=metrics)
            self.ledger_append_fn({"type":"task.pick","cycle":self.cycle,"mode":mode,"dev_mode":dev_mode,"pick":pick_info})
            if not task:
                self.ledger_append_fn({"type":"cycle.idle","cycle":self.cycle,"omega":self.omega})
                return {"ok": True, "mode": mode, "ran": None}
        else:
            task = tasks[0]
        b = omega_budget(task, base=160.0)
        if mode == "throttle_mode":
            b *= 0.55

        approval_id = task.get("requires_approval_id")
        if approval_id and approval_id not in self.approvals:
            self.ledger_append_fn({"type":"task.await_approval","task_id":task.get("task_id"),"approval_id":approval_id})
            return {"ok": True, "mode": mode, "ran": None, "awaiting_approval": approval_id}

        agent_id = task.get("agent","agent.planner")
        start = time.time()
        result = self.bus.run(agent_id, ctx, task)
        dur = time.time() - start

        W = float(result.get("work_done", 1.0))
        om = delta_omega(OmegaMetrics(W=W, C=float(metrics.get("C",1.0)), P=float(metrics.get("P",0.0)), N=float(metrics.get("N",0.0)), Q=float(metrics.get("Q",1.0))))
        self.omega += max(0.0, min(om, b))

        self.ledger_append_fn({"type":"task.done","task_id":task.get("task_id"),"task":task.get("name"),"agent":agent_id,
                               "cycle":self.cycle,"epoch":self.epoch,"omega":self.omega,"omega_delta":om,"omega_budget":b,
                               "duration_s":dur,"result":result})
        return {"ok": True, "mode": mode, "ran": task.get("name"), "agent": agent_id, "omega": self.omega, "paused": False}
