from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import AioneLocalApi
from .forge import AioneForge
from .io import resolve_runtime_dir, write_json, write_text
from .mmr import (
    render_answer_quality_verification_status,
    render_external_workload_adapter_status,
    render_real_user_task_benchmark_status,
    run_answer_quality_verification,
    run_external_workload_adapter,
    run_real_user_task_benchmark,
)
from .project_queue import (
    ProjectQueue,
    provider_for_mode,
    render_context_pack_provider_prompting_status,
    render_failure_recovery_retry_loop_status,
    render_patch_proposal_apply_gate_status,
    render_post_patch_validation_loop_status,
    render_project_execution_loop_status,
    render_project_queue_orchestrator_status,
    render_real_provider_execution_guard_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aione-forge")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run Forge cycles")
    run.add_argument("--runtime-dir", default=None, help="Runtime output directory")
    run.add_argument("--target-workspace", default=".", help="AIONE target workspace")
    run.add_argument("--cycles", type=int, default=1, help="Number of cycles for non-continuous mode")
    run.add_argument("--continuous", action="store_true", help="Run until STOP_FORGE exists")
    run.add_argument("--sleep-seconds", type=float, default=30.0, help="Sleep between continuous cycles")

    status = sub.add_parser("status", help="Show Forge status")
    status.add_argument("--runtime-dir", default=None, help="Runtime output directory")
    status.add_argument("--target-workspace", default=".", help="AIONE target workspace")

    workload = sub.add_parser("workload", help="Evaluate MMR on a real file workload")
    workload.add_argument("--runtime-dir", default=None, help="Runtime output directory")
    workload.add_argument("--path", required=True, help="Folder or file to index")
    workload.add_argument("--queries", nargs="+", default=None, help="Queries or preset query names")
    workload.add_argument("--verify-answer", action="store_true", help="Verify answer quality and sources")
    workload.add_argument("--real-tasks", action="store_true", help="Run realistic developer-agent tasks")

    api = sub.add_parser("api", help="Run the local HTTP API")
    api.add_argument("--runtime-dir", default=None, help="Runtime output directory")
    api.add_argument("--target-workspace", default=".", help="AIONE target workspace")
    api.add_argument("--host", default="127.0.0.1", help="Bind host; keep 127.0.0.1 for local-only usage")
    api.add_argument("--port", type=int, default=8765, help="Bind port")
    api.add_argument("--api-token", default=None, help="Optional bearer token for API requests")

    project = sub.add_parser("project", help="Manage the AIONE project queue")
    project.add_argument("--runtime-dir", default=None, help="Runtime output directory")
    project_sub = project.add_subparsers(dest="project_command", required=True)

    project_add = project_sub.add_parser("add", help="Add a project idea to the queue")
    project_add.add_argument("--title", required=True, help="Project title")
    project_add.add_argument("--description", required=True, help="Project description")

    project_sub.add_parser("list", help="List queued projects")

    project_design = project_sub.add_parser("design", help="Generate CDC, README and initial tasks")
    project_design.add_argument("--id", type=int, required=True, help="Project id")

    project_validate = project_sub.add_parser("validate", help="Validate generated project initialization")
    project_validate.add_argument("--id", type=int, required=True, help="Project id")

    project_sub.add_parser("run-next", help="Run the next project queue transition")

    project_run_loop = project_sub.add_parser("run-loop", help="Execute queued project tasks")
    project_run_loop.add_argument("--max-steps", type=int, default=1, help="Maximum task execution steps")
    project_run_loop.add_argument(
        "--provider",
        choices=["mock", "nvidia_nim", "dry_run", "manual_review"],
        default="mock",
        help="Execution provider mode",
    )
    project_run_loop.add_argument(
        "--review-required",
        action="store_true",
        help="Queue provider output for manual review before applying changes",
    )
    project_run_loop.add_argument(
        "--use-context-pack",
        action="store_true",
        help="Build and send a bounded MMR context pack before each provider call",
    )

    project_status = project_sub.add_parser("status", help="Show one project status")
    project_status.add_argument("--id", type=int, required=True, help="Project id")

    project_context = project_sub.add_parser("context", help="Build a context pack for one task")
    project_context.add_argument("--id", type=int, required=True, help="Project id")
    project_context.add_argument("--task-id", type=int, required=True, help="Task id")

    project_review = project_sub.add_parser("review", help="Review guarded provider outputs")
    project_review_sub = project_review.add_subparsers(dest="review_command", required=True)
    project_review_sub.add_parser("list", help="List pending provider reviews")
    project_review_accept = project_review_sub.add_parser("accept", help="Accept and apply a provider review")
    project_review_accept.add_argument("--id", type=int, required=True, help="Review id")
    project_review_reject = project_review_sub.add_parser("reject", help="Reject a provider review")
    project_review_reject.add_argument("--id", type=int, required=True, help="Review id")

    project_patch = project_sub.add_parser("patch", help="Review and apply provider patch proposals")
    project_patch_sub = project_patch.add_subparsers(dest="patch_command", required=True)
    project_patch_sub.add_parser("list", help="List patch proposals")
    project_patch_show = project_patch_sub.add_parser("show", help="Show one patch proposal")
    project_patch_show.add_argument("--id", type=int, required=True, help="Patch proposal id")
    project_patch_apply = project_patch_sub.add_parser("apply", help="Apply one patch proposal")
    project_patch_apply.add_argument("--id", type=int, required=True, help="Patch proposal id")
    project_patch_reject = project_patch_sub.add_parser("reject", help="Reject one patch proposal")
    project_patch_reject.add_argument("--id", type=int, required=True, help="Patch proposal id")

    project_validate_patch = project_sub.add_parser("validate-patch", help="Run post-patch validation")
    project_validate_patch.add_argument("--id", type=int, required=True, help="Patch proposal id")

    project_validation = project_sub.add_parser("validation", help="Inspect post-patch validations")
    project_validation_sub = project_validation.add_subparsers(dest="validation_command", required=True)
    project_validation_sub.add_parser("list", help="List post-patch validation plans and runs")

    project_failures = project_sub.add_parser("failures", help="Inspect failure recovery records")
    project_failures_sub = project_failures.add_subparsers(dest="failures_command", required=True)
    project_failures_sub.add_parser("list", help="List failure records")
    project_failures_show = project_failures_sub.add_parser("show", help="Show one failure record")
    project_failures_show.add_argument("--id", type=int, required=True, help="Failure record id")

    project_retry = project_sub.add_parser("retry", help="Retry a failure record")
    project_retry.add_argument("--failure-id", type=int, required=True, help="Failure record id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        forge = AioneForge(runtime_dir=args.runtime_dir, target_workspace=args.target_workspace)
        result = forge.run(
            cycles=max(1, args.cycles),
            continuous=args.continuous,
            sleep_seconds=args.sleep_seconds,
        )
        print(
            json.dumps(
                {
                    "runtime_dir": str(result.runtime_dir),
                    "used_fallback": result.used_fallback,
                    "cycle": result.cycle,
                    "status": result.status,
                    "artifact_count": len(result.artifacts),
                    "artifacts": result.artifacts,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "status":
        forge = AioneForge(runtime_dir=args.runtime_dir, target_workspace=args.target_workspace)
        state = forge.load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.command == "workload":
        runtime_dir, used_fallback = resolve_runtime_dir(args.runtime_dir)
        benchmark = run_external_workload_adapter(
            runtime_dir / "stores" / "mmr_index.sqlite",
            source_path=Path(args.path),
            queries=args.queries,
        )
        report_path = runtime_dir / "reports" / "MMR_EXTERNAL_WORKLOAD_ADAPTER.md"
        artifact_path = runtime_dir / "kernel" / "mmr_external_workload_adapter.json"
        write_text(report_path, render_external_workload_adapter_status(benchmark))
        write_json(artifact_path, benchmark)
        answer_quality = None
        answer_report_path = runtime_dir / "reports" / "MMR_ANSWER_QUALITY_VERIFICATION.md"
        answer_artifact_path = runtime_dir / "kernel" / "mmr_answer_quality_verification.json"
        if args.verify_answer:
            answer_quality = run_answer_quality_verification(
                runtime_dir / "stores" / "mmr_index.sqlite",
                source_path=Path(args.path),
                queries=args.queries,
            )
            write_text(answer_report_path, render_answer_quality_verification_status(answer_quality))
            write_json(answer_artifact_path, answer_quality)
        real_tasks = None
        real_tasks_report_path = runtime_dir / "reports" / "MMR_REAL_USER_TASK_BENCHMARK.md"
        real_tasks_artifact_path = runtime_dir / "kernel" / "mmr_real_user_task_benchmark.json"
        if args.real_tasks:
            real_tasks = run_real_user_task_benchmark(
                runtime_dir / "stores" / "mmr_index.sqlite",
                source_path=Path(args.path),
            )
            write_text(real_tasks_report_path, render_real_user_task_benchmark_status(real_tasks))
            write_json(real_tasks_artifact_path, real_tasks)
        print(
            json.dumps(
                {
                    "runtime_dir": str(runtime_dir),
                    "used_fallback": used_fallback,
                    "status": benchmark["result"],
                    "report": str(report_path),
                    "artifact": str(artifact_path),
                    "answer_quality_report": str(answer_report_path) if answer_quality else None,
                    "answer_quality_artifact": str(answer_artifact_path) if answer_quality else None,
                    "real_tasks_report": str(real_tasks_report_path) if real_tasks else None,
                    "real_tasks_artifact": str(real_tasks_artifact_path) if real_tasks else None,
                    "metrics": benchmark["metrics"],
                    "answer_quality_metrics": answer_quality["metrics"] if answer_quality else None,
                    "real_tasks_metrics": real_tasks["metrics"] if real_tasks else None,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "api":
        app = AioneLocalApi(
            runtime_dir=args.runtime_dir,
            target_workspace=args.target_workspace,
            api_token=args.api_token,
        )
        print(
            json.dumps(
                {
                    "status": "listening",
                    "url": f"http://{args.host}:{args.port}",
                    "runtime_dir": str(app.runtime_dir),
                    "target_workspace": str(app.target_workspace),
                    "auth_required": bool(app.api_token),
                },
                indent=2,
                ensure_ascii=False,
            ),
            flush=True,
        )
        try:
            app.serve_forever(host=args.host, port=args.port)
        except KeyboardInterrupt:
            return 0
        return 0

    if args.command == "project":
        runtime_dir, used_fallback = resolve_runtime_dir(args.runtime_dir)
        provider_mode = args.provider if args.project_command == "run-loop" else "mock"
        queue = ProjectQueue(
            runtime_dir / "stores" / "project_queue.sqlite",
            projects_root=runtime_dir / "projects",
            provider=provider_for_mode(provider_mode),
        )
        if args.project_command == "add":
            result = queue.add_project(title=args.title, description=args.description)
            operation = {"action": "add", "project_id": result["project"]["id"], "created": result["created"]}
        elif args.project_command == "list":
            result = queue.list_projects()
            operation = {"action": "list"}
        elif args.project_command == "design":
            result = queue.design_project(args.id)
            operation = {"action": "design", "project_id": result["project"]["id"]}
        elif args.project_command == "validate":
            result = queue.validate_project(args.id)
            operation = {"action": "validate", "project_id": result["project"]["id"], "valid": result["valid"]}
        elif args.project_command == "run-next":
            result = queue.run_next()
            operation = {
                "action": "run-next",
                "project_id": result["project"]["id"] if result["project"] else None,
                "action_taken": result["action_taken"],
            }
        elif args.project_command == "run-loop":
            result = queue.run_loop(
                max_steps=args.max_steps,
                review_required=args.review_required,
                use_context_pack=args.use_context_pack,
            )
            operation = {
                "action": "run-loop",
                "max_steps": args.max_steps,
                "provider_mode": args.provider,
                "review_required": args.review_required,
                "use_context_pack": args.use_context_pack,
                "step_count": result["metrics"]["step_count"],
            }
        elif args.project_command == "status":
            result = queue.project_status(args.id)
            operation = {"action": "status", "project_id": result["project"]["id"]}
        elif args.project_command == "context":
            result = queue.build_context_pack(args.id, args.task_id)
            operation = {
                "action": "context",
                "project_id": args.id,
                "task_id": args.task_id,
                "evidence_score": result["context_pack"]["evidence_score"],
            }
        elif args.project_command == "review":
            if args.review_command == "list":
                result = queue.list_reviews()
                operation = {"action": "review-list", "review_count": result["metrics"]["review_count"]}
            elif args.review_command == "accept":
                result = queue.accept_review(args.id)
                operation = {"action": "review-accept", "review_id": args.id, "applied": result["applied"]}
            elif args.review_command == "reject":
                result = queue.reject_review(args.id)
                operation = {"action": "review-reject", "review_id": args.id, "rejected": result["rejected"]}
            else:
                parser.print_help()
                return 2
        elif args.project_command == "patch":
            if args.patch_command == "list":
                result = queue.list_patches()
                operation = {"action": "patch-list", "patch_count": result["metrics"]["patch_count"]}
            elif args.patch_command == "show":
                result = queue.show_patch(args.id)
                operation = {"action": "patch-show", "patch_id": args.id}
            elif args.patch_command == "apply":
                result = queue.apply_patch_proposal(args.id)
                operation = {"action": "patch-apply", "patch_id": args.id, "applied": result["applied"]}
            elif args.patch_command == "reject":
                result = queue.reject_patch_proposal(args.id)
                operation = {"action": "patch-reject", "patch_id": args.id, "rejected": result["rejected"]}
            else:
                parser.print_help()
                return 2
        elif args.project_command == "validate-patch":
            result = queue.validate_patch(args.id)
            operation = {
                "action": "validate-patch",
                "patch_id": args.id,
                "validated": result.get("validated", False),
                "passed": result.get("passed"),
            }
        elif args.project_command == "validation":
            if args.validation_command == "list":
                result = queue.list_validations()
                operation = {"action": "validation-list", "plan_count": result["metrics"]["plan_count"]}
            else:
                parser.print_help()
                return 2
        elif args.project_command == "failures":
            if args.failures_command == "list":
                result = queue.list_failures()
                operation = {"action": "failures-list", "failure_count": result["metrics"]["failure_count"]}
            elif args.failures_command == "show":
                result = queue.show_failure(args.id)
                operation = {"action": "failures-show", "failure_id": args.id}
            else:
                parser.print_help()
                return 2
        elif args.project_command == "retry":
            result = queue.retry_failure(args.failure_id)
            operation = {
                "action": "failure-retry",
                "failure_id": args.failure_id,
                "retried": result.get("retried", False),
            }
        else:
            parser.print_help()
            return 2

        snapshot = queue.snapshot(last_operation=operation)
        report_path = runtime_dir / "reports" / "PROJECT_QUEUE_ORCHESTRATOR.md"
        artifact_path = runtime_dir / "kernel" / "project_queue_orchestrator.json"
        write_text(report_path, render_project_queue_orchestrator_status(snapshot))
        write_json(artifact_path, snapshot)
        execution_report_path = runtime_dir / "reports" / "PROJECT_EXECUTION_LOOP.md"
        execution_artifact_path = runtime_dir / "kernel" / "project_execution_loop.json"
        if args.project_command == "run-loop":
            write_text(execution_report_path, render_project_execution_loop_status(result))
            write_json(execution_artifact_path, result)
        guard_snapshot = queue.guard_snapshot(last_operation=operation)
        guard_report_path = runtime_dir / "reports" / "REAL_PROVIDER_EXECUTION_GUARD.md"
        guard_artifact_path = runtime_dir / "kernel" / "real_provider_execution_guard.json"
        write_text(guard_report_path, render_real_provider_execution_guard_status(guard_snapshot))
        write_json(guard_artifact_path, guard_snapshot)
        context_snapshot = queue.context_snapshot(last_operation=operation)
        context_report_path = runtime_dir / "reports" / "CONTEXT_PACK_PROVIDER_PROMPTING.md"
        context_artifact_path = runtime_dir / "kernel" / "context_pack_provider_prompting.json"
        write_text(context_report_path, render_context_pack_provider_prompting_status(context_snapshot))
        write_json(context_artifact_path, context_snapshot)
        patch_snapshot = queue.patch_snapshot(last_operation=operation)
        patch_report_path = runtime_dir / "reports" / "PATCH_PROPOSAL_APPLY_GATE.md"
        patch_artifact_path = runtime_dir / "kernel" / "patch_proposal_apply_gate.json"
        write_text(patch_report_path, render_patch_proposal_apply_gate_status(patch_snapshot))
        write_json(patch_artifact_path, patch_snapshot)
        validation_snapshot = queue.validation_snapshot(last_operation=operation)
        validation_report_path = runtime_dir / "reports" / "POST_PATCH_VALIDATION_LOOP.md"
        validation_artifact_path = runtime_dir / "kernel" / "post_patch_validation_loop.json"
        write_text(validation_report_path, render_post_patch_validation_loop_status(validation_snapshot))
        write_json(validation_artifact_path, validation_snapshot)
        failure_snapshot = queue.failure_snapshot(last_operation=operation)
        failure_report_path = runtime_dir / "reports" / "FAILURE_RECOVERY_RETRY_LOOP.md"
        failure_artifact_path = runtime_dir / "kernel" / "failure_recovery_retry_loop.json"
        write_text(failure_report_path, render_failure_recovery_retry_loop_status(failure_snapshot))
        write_json(failure_artifact_path, failure_snapshot)
        print(
            json.dumps(
                {
                    "runtime_dir": str(runtime_dir),
                    "used_fallback": used_fallback,
                    "status": "ok",
                    "operation": operation,
                    "report": str(report_path),
                    "artifact": str(artifact_path),
                    "execution_report": str(execution_report_path) if args.project_command == "run-loop" else None,
                    "execution_artifact": str(execution_artifact_path) if args.project_command == "run-loop" else None,
                    "guard_report": str(guard_report_path),
                    "guard_artifact": str(guard_artifact_path),
                    "context_report": str(context_report_path),
                    "context_artifact": str(context_artifact_path),
                    "patch_report": str(patch_report_path),
                    "patch_artifact": str(patch_artifact_path),
                    "validation_report": str(validation_report_path),
                    "validation_artifact": str(validation_artifact_path),
                    "failure_report": str(failure_report_path),
                    "failure_artifact": str(failure_artifact_path),
                    "result": result,
                    "metrics": snapshot["metrics"],
                    "guard_metrics": guard_snapshot["metrics"],
                    "context_metrics": context_snapshot["metrics"],
                    "patch_metrics": patch_snapshot["metrics"],
                    "validation_metrics": validation_snapshot["metrics"],
                    "failure_metrics": failure_snapshot["metrics"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
