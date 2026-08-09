from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import build_api
from .runtime import ContinuousDevRuntime, RuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fractal-continuous-dev", description="Fractal Continuous Development Runtime")
    parser.add_argument("--runtime-dir", default=None)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("diagnostics")
    sub.add_parser("openapi")
    sub.add_parser("creation-status")
    sub.add_parser("creation-scenario")
    sub.add_parser("tools-status")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("stop-after-current")
    sub.add_parser("emergency-stop")

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8795)
    serve.add_argument("--token", default=None)

    message = sub.add_parser("message")
    message.add_argument("message")

    add = sub.add_parser("add-idea")
    add.add_argument("text")
    add.add_argument("--urgency", type=int, default=5)
    add.add_argument("--impact", type=int, default=5)
    add.add_argument("--tags", default="")

    plan = sub.add_parser("plan")
    plan.add_argument("idea_id")

    approve = sub.add_parser("approve")
    approve.add_argument("idea_id")

    queue = sub.add_parser("queue")
    queue.add_argument("--limit", type=int, default=20)

    run = sub.add_parser("run-cycle")
    run.add_argument("--max-steps", type=int, default=1)
    run.add_argument("--wait-seconds", type=float, default=0.0)

    idea_worker = sub.add_parser("idea-worker")
    idea_worker.add_argument("--max-documents", type=int, default=80)

    sub.add_parser("import-ready")
    sub.add_parser("memory-status")

    restore_memory = sub.add_parser("memory-restore")
    restore_memory.add_argument("memory_id")

    backup = sub.add_parser("backup")
    backup.add_argument("--target", default=None)

    restore = sub.add_parser("restore")
    restore.add_argument("archive")

    sub.add_parser("self-test")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=args.runtime_dir, workspace_root=args.workspace))

    try:
        if args.command == "serve":
            api = build_api(runtime_dir=args.runtime_dir, workspace_root=args.workspace, token=args.token)
            print(f"Fractal Continuous Development Runtime: http://{args.host}:{args.port}")
            print(f"Token file: {api.runtime.runtime_dir / 'runtime-token.txt'}")
            api.serve_forever(host=args.host, port=args.port)
            return 0

        if args.command == "init":
            result = runtime.initialize()
        elif args.command == "status":
            result = runtime.status()
        elif args.command == "health":
            runtime.initialize()
            result = runtime.health()
        elif args.command == "diagnostics":
            runtime.initialize()
            result = {"markdown": runtime.diagnostics_report()}
        elif args.command == "openapi":
            result = runtime.openapi_spec()
        elif args.command == "creation-status":
            runtime.initialize()
            result = runtime.creation_studio_status()
        elif args.command == "creation-scenario":
            runtime.initialize()
            result = runtime.run_creation_studio_scenario()
        elif args.command == "tools-status":
            runtime.initialize()
            result = runtime.tool_customization_status()
        elif args.command == "pause":
            runtime.initialize()
            result = runtime.pause_runtime(reason="cli")
        elif args.command == "resume":
            runtime.initialize()
            result = runtime.resume_runtime()
        elif args.command == "stop-after-current":
            runtime.initialize()
            result = runtime.stop_after_current()
        elif args.command == "emergency-stop":
            runtime.initialize()
            result = runtime.emergency_stop()
        elif args.command == "message":
            runtime.initialize()
            result = runtime.interpret_message(args.message, source="cli")
        elif args.command == "add-idea":
            runtime.initialize()
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            result = runtime.add_idea(args.text, source="cli", urgency=args.urgency, impact=args.impact, tags=tags or None)
        elif args.command == "plan":
            runtime.initialize()
            result = runtime.plan_idea(args.idea_id)
        elif args.command == "approve":
            runtime.initialize()
            result = runtime.approve_idea(args.idea_id)
        elif args.command == "queue":
            runtime.initialize()
            result = {"queue": runtime.list_queue(limit=args.limit)}
        elif args.command == "run-cycle":
            runtime.initialize()
            result = runtime.run_cycle(max_steps=args.max_steps, wait_seconds=args.wait_seconds)
        elif args.command == "idea-worker":
            runtime.initialize()
            result = runtime.run_idea_worker(max_documents=args.max_documents)
        elif args.command == "import-ready":
            runtime.initialize()
            result = runtime.import_ready_ideas()
        elif args.command == "memory-status":
            runtime.initialize()
            result = runtime.memory_status()
        elif args.command == "memory-restore":
            runtime.initialize()
            result = runtime.restore_memory(args.memory_id)
        elif args.command == "backup":
            runtime.initialize()
            result = runtime.backup(args.target)
        elif args.command == "restore":
            result = runtime.restore(args.archive)
        elif args.command == "self-test":
            result = run_self_test(runtime)
        else:
            raise ValueError(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"component=fractal_dev_runtime.cli operation={args.command} cause={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_result(result))
    return 0


def render_result(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "summary" in result and isinstance(result["summary"], str):
            return result["summary"]
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def run_self_test(runtime: ContinuousDevRuntime) -> dict[str, object]:
    runtime.initialize()
    first = runtime.add_idea("Créer une console HUD capable d'écrire des commandes.", source="self-test", urgency=6, impact=7)
    second = runtime.add_idea("Cette idée est urgente : corriger un blocage de test critique.", source="self-test", urgency=9, impact=9, tags=["urgent"])
    runtime.plan_idea(first["id"])
    runtime.approve_idea(first["id"])
    runtime.plan_idea(second["id"])
    runtime.approve_idea(second["id"])
    queue = runtime.list_queue(limit=2)
    cycle = runtime.run_cycle(max_steps=2)
    generated = runtime.run_idea_worker(max_documents=5)
    imported = runtime.import_ready_ideas()
    memory = runtime.memory_status()
    return {
        "ok": True,
        "first": first["id"],
        "second": second["id"],
        "queue_first_before_run": queue[0]["id"] if queue else "",
        "executions": len(cycle["executions"]),
        "generated": len(generated["generated"]),
        "imported": len(imported["imported"]),
        "memory": memory,
    }


if __name__ == "__main__":
    raise SystemExit(main())
