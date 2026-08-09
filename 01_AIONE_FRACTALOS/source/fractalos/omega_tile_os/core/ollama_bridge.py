from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_runtime import submit_workload
from .codex_worker import submit_worker_session
from .events import append_event
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import utc_now
from ..tilemindfs.store import TileMindFS


DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

FREE_AI_MODEL_CATALOG = [
    {
        "id": "qwen2.5-coder:7b",
        "family": "qwen2.5-coder",
        "roles": ["coder", "patcher", "reviewer", "planner"],
        "pull": "ollama pull qwen2.5-coder:7b",
        "size_hint": "medium",
        "context_hint": "code repair and multi-language implementation",
        "temperature": 0.15,
        "num_ctx": 8192,
        "source": "https://ollama.com/library/qwen2.5-coder",
    },
    {
        "id": "qwen2.5-coder:3b",
        "family": "qwen2.5-coder",
        "roles": ["coder", "patcher", "documenter"],
        "pull": "ollama pull qwen2.5-coder:3b",
        "size_hint": "small",
        "context_hint": "fast local code drafts and doc edits",
        "temperature": 0.18,
        "num_ctx": 8192,
        "source": "https://ollama.com/library/qwen2.5-coder",
    },
    {
        "id": "deepseek-coder-v2:16b",
        "family": "deepseek-coder-v2",
        "roles": ["coder", "patcher", "architect"],
        "pull": "ollama pull deepseek-coder-v2:16b",
        "size_hint": "large",
        "context_hint": "deeper code reasoning when RAM allows",
        "temperature": 0.12,
        "num_ctx": 8192,
        "source": "https://ollama.com/library/deepseek-coder-v2",
    },
    {
        "id": "deepseek-coder:6.7b",
        "family": "deepseek-coder",
        "roles": ["coder", "reviewer"],
        "pull": "ollama pull deepseek-coder:6.7b",
        "size_hint": "medium",
        "context_hint": "fallback code model with modest footprint",
        "temperature": 0.14,
        "num_ctx": 4096,
        "source": "https://ollama.com/library/deepseek-coder",
    },
    {
        "id": "llama3.2:3b",
        "family": "llama3.2",
        "roles": ["planner", "documenter", "summarizer", "chat"],
        "pull": "ollama pull llama3.2:3b",
        "size_hint": "small",
        "context_hint": "fast planning, summarization and chatbot work",
        "temperature": 0.25,
        "num_ctx": 8192,
        "source": "https://ollama.com/library/llama3.2",
    },
    {
        "id": "llama3.2:1b",
        "family": "llama3.2",
        "roles": ["documenter", "summarizer", "chat"],
        "pull": "ollama pull llama3.2:1b",
        "size_hint": "tiny",
        "context_hint": "edge-friendly summaries and status explanations",
        "temperature": 0.28,
        "num_ctx": 4096,
        "source": "https://ollama.com/library/llama3.2",
    },
]

AGENT_MODEL_ROLES = {
    "planner": "planner",
    "builder": "coder",
    "patcher": "patcher",
    "reviewer": "reviewer",
    "documenter": "documenter",
    "researcher": "summarizer",
    "evolver": "architect",
}


def _endpoint(value: str | None = None) -> str:
    return (value or os.environ.get("OLLAMA_HOST") or DEFAULT_ENDPOINT).rstrip("/")


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body or "{}")


def _get_json(url: str, timeout_s: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body or "{}")


def ollama_status(endpoint: str | None = None, timeout_s: float = 2.0) -> dict[str, Any]:
    base = _endpoint(endpoint)
    try:
        tags = _get_json(f"{base}/api/tags", timeout_s=timeout_s)
        models = [str(item.get("name", "")) for item in tags.get("models", []) if item.get("name")]
        recommendations = ai_model_recommendations(models)
        return {
            "available": True,
            "endpoint": base,
            "models": models,
            "recommended_model": recommendations["default_model"],
            "free_model_recommendations": recommendations,
        }
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        recommendations = ai_model_recommendations([])
        return {
            "available": False,
            "endpoint": base,
            "models": [],
            "recommended_model": recommendations["default_model"],
            "free_model_recommendations": recommendations,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _ollama_generate(endpoint: str, model: str, prompt: str, timeout_s: float) -> str:
    options = model_options(model)
    result = _post_json(
        f"{endpoint}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        },
        timeout_s=timeout_s,
    )
    return str(result.get("response", "")).strip()


def free_ai_model_catalog(role: str | None = None) -> list[dict[str, Any]]:
    if not role:
        return list(FREE_AI_MODEL_CATALOG)
    normalized = role.strip().lower()
    return [item for item in FREE_AI_MODEL_CATALOG if normalized in item["roles"]]


def _model_matches(installed: str, model_id: str) -> bool:
    installed = installed.lower()
    model_id = model_id.lower()
    family = model_id.split(":", 1)[0]
    return installed == model_id or installed.startswith(family + ":") or installed == family


def select_free_ai_model(models: list[str], role: str = "planner") -> dict[str, Any]:
    candidates = free_ai_model_catalog(role) or free_ai_model_catalog()
    for candidate in candidates:
        for installed in models:
            if _model_matches(installed, candidate["id"]):
                return {
                    "role": role,
                    "model": installed,
                    "installed": True,
                    "pull": candidate["pull"],
                    "options": model_options(installed, role=role),
                    "source": candidate["source"],
                    "reason": f"installed model matches {candidate['family']}",
                }
    fallback = candidates[0] if candidates else FREE_AI_MODEL_CATALOG[0]
    return {
        "role": role,
        "model": fallback["id"],
        "installed": False,
        "pull": fallback["pull"],
        "options": model_options(fallback["id"], role=role),
        "source": fallback["source"],
        "reason": "model not installed yet; use pull command or fallback plan",
    }


def model_options(model: str, role: str | None = None) -> dict[str, Any]:
    spec = next((item for item in FREE_AI_MODEL_CATALOG if _model_matches(model, item["id"])), None)
    options = {
        "temperature": float(spec.get("temperature", 0.2)) if spec else 0.2,
        "num_ctx": int(spec.get("num_ctx", 4096)) if spec else 4096,
    }
    normalized_role = (role or "").lower()
    if normalized_role in {"coder", "patcher", "reviewer"}:
        options["temperature"] = min(options["temperature"], 0.16)
    if normalized_role in {"documenter", "summarizer", "chat"}:
        options["temperature"] = max(options["temperature"], 0.22)
    return options


def ai_model_recommendations(models: list[str]) -> dict[str, Any]:
    assignments = {}
    for agent_role, model_role in AGENT_MODEL_ROLES.items():
        assignments[agent_role] = select_free_ai_model(models, model_role)
    missing = []
    for item in assignments.values():
        if not item["installed"] and item["pull"] not in missing:
            missing.append(item["pull"])
    default = assignments.get("planner", {}).get("model") or DEFAULT_MODEL
    return {
        "default_model": default,
        "assignments": assignments,
        "missing_pull_commands": missing[:6],
        "local_first": True,
        "free_models_only": True,
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _fallback_plan(idea: str, perf: dict[str, Any]) -> dict[str, Any]:
    risk = str(perf["recommendations"].get("risk_level", "unknown"))
    concurrency = perf["recommendations"].get("recommended_concurrency", 1)
    return {
        "title": "Local Idea Build Plan",
        "summary": idea.strip(),
        "risk_level": risk,
        "milestones": [
            {
                "id": "map",
                "title": "Cartographier l idee",
                "goal": "Identifier les modules touches, les entrees, les sorties et les invariants.",
                "agent_mode": "researcher",
                "domain": "research",
                "checks": ["doctor", "ui-view ai-dev-forge"],
            },
            {
                "id": "design",
                "title": "Structurer le plan d action",
                "goal": "Transformer l idee en specifications, interfaces et patchs atomiques.",
                "agent_mode": "builder",
                "domain": "code",
                "checks": ["unit-tests-targeted"],
            },
            {
                "id": "build",
                "title": "Construire prudemment",
                "goal": "Implementer une premiere version reversible avec traces et memoire.",
                "agent_mode": "builder",
                "domain": "code",
                "checks": ["unittest-discover"],
            },
            {
                "id": "verify",
                "title": "Verifier et stabiliser",
                "goal": "Executer tests, doctor, routeur et performance governor avant integration large.",
                "agent_mode": "automator",
                "domain": "automation",
                "checks": ["doctor", "router-simulate", "unittest-discover"],
            },
            {
                "id": "evolve",
                "title": "Apprendre et proposer la suite",
                "goal": "Archiver le resultat et generer les prochaines ameliorations locales.",
                "agent_mode": "evolver",
                "domain": "ecosystem",
                "checks": ["ai-dev-plan", "memory-report"],
            },
        ],
        "agent_pipeline": [
            "chatbot -> idea-plan",
            "planner -> worker sessions",
            "builder -> code workload",
            "reviewer -> tests + doctor",
            "evolver -> next queued improvements",
        ],
        "safety_rules": [
            "Pas de commande destructive automatique.",
            f"Limiter les runs selon le risk_level={risk} et concurrency={concurrency}.",
            "Archiver chaque plan dans TileMindFS et OmegaRAM.",
            "Preferer une execution bornee quand le risque est elevated ou critical.",
        ],
    }


def _normalize_plan(raw: dict[str, Any], idea: str, perf: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_plan(idea, perf)
    plan = dict(fallback)
    for key in ("title", "summary", "agent_pipeline", "safety_rules"):
        if raw.get(key):
            plan[key] = raw[key]
    milestones = raw.get("milestones")
    if isinstance(milestones, list) and milestones:
        normalized = []
        for index, item in enumerate(milestones[:8], start=1):
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "code")).lower()
            if domain not in {"code", "research", "automation", "ecosystem"}:
                domain = "code"
            agent_mode = str(item.get("agent_mode", "builder")).lower()
            if agent_mode not in {"builder", "researcher", "automator", "evolver"}:
                agent_mode = "builder"
            normalized.append(
                {
                    "id": str(item.get("id", f"step-{index}")),
                    "title": str(item.get("title", f"Step {index}")),
                    "goal": str(item.get("goal", item.get("description", "Implementer cette etape."))),
                    "agent_mode": agent_mode,
                    "domain": domain,
                    "checks": [str(check) for check in item.get("checks", [])[:6]] if isinstance(item.get("checks"), list) else [],
                }
            )
        if normalized:
            plan["milestones"] = normalized
    plan["risk_level"] = str(perf["recommendations"].get("risk_level", "unknown"))
    plan["generated_at"] = utc_now()
    return plan


def _plan_prompt(idea: str, perf: dict[str, Any]) -> str:
    return (
        "Tu es le planificateur local de FractalOS. Transforme l'idee utilisateur en plan d'action clair, "
        "executable par des agents de dev locaux, avec verification et garde-fous.\n"
        "Reponds uniquement en JSON valide avec les champs: title, summary, milestones, agent_pipeline, safety_rules.\n"
        "Chaque milestone doit avoir: id, title, goal, agent_mode(builder|researcher|automator|evolver), "
        "domain(code|research|automation|ecosystem), checks.\n\n"
        f"Telemetry: risk_level={perf['recommendations'].get('risk_level')}, "
        f"stability={perf['formulas'].get('stability_index')}, "
        f"concurrency={perf['recommendations'].get('recommended_concurrency')}.\n"
        f"Idee: {idea}\n"
    )


def create_ollama_idea_plan(
    workspace: Path,
    idea: str,
    model: str | None = None,
    endpoint: str | None = None,
    timeout_s: float = 20.0,
    queue_agents: bool = False,
    run_workers: bool = False,
) -> dict[str, Any]:
    perf = PerformanceGovernor(workspace).report()
    base = _endpoint(endpoint)
    selected_model = model or DEFAULT_MODEL
    status = ollama_status(base, timeout_s=min(timeout_s, 3.0))
    raw_text = ""
    source = "fallback"
    raw_plan: dict[str, Any] = {}
    model_plan = status.get("free_model_recommendations", ai_model_recommendations([]))
    planner_assignment = dict(model_plan.get("assignments", {}).get("planner", select_free_ai_model([], "planner")))
    if model is None:
        selected_model = str(planner_assignment.get("model") or selected_model)
    if status.get("available"):
        try:
            raw_text = _ollama_generate(base, selected_model, _plan_prompt(idea, perf), timeout_s=timeout_s)
            raw_plan = _extract_json_object(raw_text) or {}
            source = "ollama" if raw_plan else "ollama-unstructured-fallback"
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raw_text = f"{type(exc).__name__}: {exc}"
            source = "fallback-after-error"
    plan = _normalize_plan(raw_plan, idea, perf)
    plan["model_assignments"] = model_plan.get("assignments", {})
    plan["missing_pull_commands"] = model_plan.get("missing_pull_commands", [])
    plan_id = uuid4().hex[:12]
    report_path = _write_idea_plan_report(workspace, plan_id, idea, plan, source, selected_model, base, raw_text)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"ollama_idea::{plan_id}",
        text=report_path.read_text(encoding="utf-8"),
        source="ollama_bridge",
    )

    queued_workers: list[dict[str, Any]] = []
    queued_workloads: list[dict[str, Any]] = []
    worker_run: dict[str, Any] | None = None
    if queue_agents:
        for milestone in plan.get("milestones", [])[:6]:
            queued_workers.append(
                submit_worker_session(
                    workspace,
                    str(milestone["agent_mode"]),
                    f"IdeaPlan {plan_id} :: {milestone['title']}",
                    str(milestone["goal"]),
                    scope=f"From Ollama idea plan {plan_id}. Checks: {', '.join(milestone.get('checks', [])) or 'none'}",
                )
            )
            queued_workloads.append(
                submit_workload(
                    workspace,
                    str(milestone["domain"]),
                    f"IdeaBuild {plan_id} :: {milestone['title']}",
                    str(milestone["goal"]),
                    context=f"Generated from chatbot idea: {idea[:500]}",
                )
            )
    if run_workers and queued_workers:
        from .codex_worker import run_worker_sessions

        max_items = 1 if plan.get("risk_level") in {"elevated", "critical"} else min(2, len(queued_workers))
        worker_run = run_worker_sessions(workspace, max_items=max_items, auto_queue_autonomy=False)

    append_event(
        workspace,
        "ollama_idea_plan_created",
        {
            "plan_id": plan_id,
            "source": source,
            "queued_workers": len(queued_workers),
            "queued_workloads": len(queued_workloads),
            "report_path": str(report_path),
        },
    )
    return {
        "plan_id": plan_id,
        "source": source,
        "ollama": status,
        "model": selected_model,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
        "plan": plan,
        "queued_workers": queued_workers,
        "queued_workloads": queued_workloads,
        "worker_run": worker_run,
    }


def ai_model_orchestrator_plan(workspace: Path, endpoint: str | None = None) -> dict[str, Any]:
    status = ollama_status(endpoint=endpoint, timeout_s=2.5)
    recommendations = status.get("free_model_recommendations", ai_model_recommendations([]))
    report_path = _write_model_orchestrator_report(workspace, status, recommendations)
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"ai_model_orchestrator::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="ollama_bridge",
    )
    append_event(
        workspace,
        "ai_model_orchestrator_planned",
        {
            "available": status.get("available"),
            "missing": len(recommendations.get("missing_pull_commands", [])),
            "report_path": str(report_path),
        },
    )
    return {
        "generated_at": utc_now(),
        "status": status,
        "catalog": free_ai_model_catalog(),
        "recommendations": recommendations,
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
    }


def _write_idea_plan_report(
    workspace: Path,
    plan_id: str,
    idea: str,
    plan: dict[str, Any],
    source: str,
    model: str,
    endpoint: str,
    raw_text: str,
) -> Path:
    root = workspace / "ollama_ideas"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"IDEA_PLAN_{plan_id}.md"
    lines = [
        "# FractalOS Ollama Idea Plan",
        "",
        f"- Plan id: {plan_id}",
        f"- Generated at: {plan.get('generated_at')}",
        f"- Source: {source}",
        f"- Model: {model}",
        f"- Endpoint: {endpoint}",
        f"- Risk level: {plan.get('risk_level')}",
        "",
        "## Idea",
        idea.strip(),
        "",
        "## Summary",
        str(plan.get("summary", "")),
        "",
        "## Milestones",
    ]
    for item in plan.get("milestones", []):
        lines.append(f"- {item['id']} :: {item['title']} [{item['agent_mode']}/{item['domain']}]")
        lines.append(f"  Goal: {item['goal']}")
        lines.append(f"  Checks: {', '.join(item.get('checks', [])) or 'none'}")
    lines.extend(["", "## Agent Pipeline"])
    lines.extend(f"- {item}" for item in plan.get("agent_pipeline", []))
    lines.extend(["", "## Local Free AI Model Assignments"])
    assignments = dict(plan.get("model_assignments", {}))
    if assignments:
        for role, item in assignments.items():
            lines.append(
                f"- {role}: {item.get('model')} installed={item.get('installed')} pull=`{item.get('pull')}`"
            )
    else:
        lines.append("- no model assignment generated")
    if plan.get("missing_pull_commands"):
        lines.extend(["", "## Missing Pull Commands"])
        lines.extend(f"- `{item}`" for item in plan.get("missing_pull_commands", []))
    lines.extend(["", "## Safety Rules"])
    lines.extend(f"- {item}" for item in plan.get("safety_rules", []))
    if raw_text and source != "ollama":
        lines.extend(["", "## Raw Local LLM Note", raw_text[:2000]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_model_orchestrator_report(workspace: Path, status: dict[str, Any], recommendations: dict[str, Any]) -> Path:
    root = workspace / "ollama_ideas"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"AI_MODEL_ORCHESTRATOR_{len(list(root.glob('AI_MODEL_ORCHESTRATOR_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Local AI Model Orchestrator",
        "",
        f"- Generated at: {utc_now()}",
        f"- Ollama available: {status.get('available')}",
        f"- Endpoint: {status.get('endpoint')}",
        f"- Free/local-first: {recommendations.get('free_models_only')}",
        "",
        "## Assignments",
    ]
    for role, item in dict(recommendations.get("assignments", {})).items():
        lines.append(f"- {role}: {item.get('model')} installed={item.get('installed')} reason={item.get('reason')}")
    lines.extend(["", "## Pull Missing Models"])
    missing = list(recommendations.get("missing_pull_commands", []))
    lines.extend(f"- `{item}`" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## Optimization Rules"])
    for item in FREE_AI_MODEL_CATALOG:
        lines.append(f"- {item['id']} :: roles={','.join(item['roles'])} :: options=temp {item['temperature']} ctx {item['num_ctx']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def ollama_idea_report(workspace: Path) -> dict[str, Any]:
    root = workspace / "ollama_ideas"
    reports = sorted(root.glob("IDEA_PLAN_*.md")) if root.exists() else []
    model_reports = sorted(root.glob("AI_MODEL_ORCHESTRATOR_*.md")) if root.exists() else []
    latest = reports[-1] if reports else None
    return {
        "report_count": len(reports),
        "latest_report": str(latest) if latest else None,
        "model_orchestrator_report_count": len(model_reports),
        "latest_model_orchestrator_report": str(model_reports[-1]) if model_reports else None,
        "status": ollama_status(timeout_s=1.0),
    }
