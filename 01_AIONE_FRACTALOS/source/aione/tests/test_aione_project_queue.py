from __future__ import annotations

import json
from pathlib import Path

from aione_forge.cli import main as cli_main
from aione_forge.project_queue import (
    ContextPackBuilder,
    DryRunProvider,
    ExecutionGuard,
    ManualReviewProvider,
    MockLLMProvider,
    NvidiaNimProvider,
    PatchParser,
    ProjectQueue,
    RetryPolicy,
    SafeCommandRunner,
    render_project_queue_orchestrator_status,
)


class DangerousProvider(MockLLMProvider):
    name = "mock"

    def execute_task(self, *, project: dict, task: dict, input_prompt: str) -> dict:
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": "Attempted dangerous command rm -rf /",
            "commands": ["rm -rf /"],
            "changed_files": ["../escape.txt"],
            "proposed_changes": [
                {
                    "operation": "write",
                    "path": "../escape.txt",
                    "content": "unsafe",
                }
            ],
            "artifacts": [],
            "validation_status": "passed",
        }


class RecordingProvider(MockLLMProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def execute_task(self, *, project: dict, task: dict, input_prompt: str) -> dict:
        self.prompts.append(input_prompt)
        return super().execute_task(project=project, task=task, input_prompt=input_prompt)


class PatchProvider(MockLLMProvider):
    def __init__(self, patch_text: str, *, name: str = "mock") -> None:
        self.name = name
        self.patch_text = patch_text

    def execute_task(self, *, project: dict, task: dict, input_prompt: str) -> dict:
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": f"Patch provider prepared `{task['title']}`.",
            "changed_files": [],
            "patch_text": self.patch_text,
            "artifacts": [{"name": "patch_provider", "content": "patch provider output"}],
            "validation_status": "passed",
        }


class RepairProvider(MockLLMProvider):
    def execute_task(self, *, project: dict, task: dict, input_prompt: str) -> dict:
        if "FailureRecord:" in task["description"]:
            patch_text = "=== FILE: broken.py ===\ndef fixed():\n    return 'ok'\n"
        else:
            patch_text = "=== FILE: broken.py ===\ndef broken(:\n    pass\n"
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": f"Repair provider handled `{task['title']}`.",
            "changed_files": [],
            "patch_text": patch_text,
            "artifacts": [{"name": "repair_provider", "content": "repair provider output"}],
            "validation_status": "passed",
        }


def test_project_queue_design_validate_and_run_next(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=MockLLMProvider(),
    )

    added = queue.add_project(title="Test", description="Projet test")

    assert added["created"] is True
    assert added["project"]["id"] == 1
    assert added["project"]["status"] == "idea"

    designed = queue.design_project(1)
    project = designed["project"]
    assert project["status"] == "designing"
    assert Path(project["project_dir"]).exists()
    assert Path(project["cdc_path"]).exists()
    assert Path(project["tasks_path"]).exists()
    assert Path(project["readme_path"]).exists()
    assert len(project["tasks"]) == 4
    assert "CDC - Test" in Path(project["cdc_path"]).read_text(encoding="utf-8")

    validated = queue.validate_project(1)
    assert validated["valid"] is True
    assert validated["project"]["status"] == "valid"
    assert validated["checks"]["task_count"] == 4

    run = queue.run_next()
    assert run["action_taken"] == "building"
    assert run["project"]["status"] == "building"

    snapshot = queue.snapshot(last_operation={"action": "test"})
    assert snapshot["metrics"]["project_count"] == 1
    assert snapshot["metrics"]["task_count"] == 4
    assert snapshot["metrics"]["doing_task_count"] == 1
    assert snapshot["provider"]["name"] == "mock"

    rendered = render_project_queue_orchestrator_status(snapshot)
    assert "Project Queue Orchestrator" in rendered
    assert "idea -> designing -> valid" in rendered


def test_project_execution_loop_runs_tasks_to_done(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=MockLLMProvider(),
    )
    queue.add_project(title="Loop Test", description="Projet boucle")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=5)

    assert result["id"] == "PROJECT-EXECUTION-LOOP-0001"
    assert result["metrics"]["executed_task_count"] == 4
    assert result["metrics"]["done_execution_count"] == 4
    assert result["metrics"]["done_project_count"] == 1
    status = queue.project_status(1)
    assert status["project"]["status"] == "done"
    assert status["metrics"]["done_task_count"] == 4
    assert status["metrics"]["execution_count"] == 4
    project_dir = Path(status["project"]["project_dir"])
    assert (project_dir / "RUNS.md").exists()
    assert (project_dir / "artifacts" / "run_0001.md").exists()
    assert "Clarify project contract" in (project_dir / "RUNS.md").read_text(encoding="utf-8")


def test_project_queue_cli_generates_report_and_artifact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "Test",
            "--description",
            "Projet test",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "run-next"]) == 0

    report_path = runtime / "reports" / "PROJECT_QUEUE_ORCHESTRATOR.md"
    artifact_path = runtime / "kernel" / "project_queue_orchestrator.json"
    assert report_path.exists()
    assert artifact_path.exists()
    assert "Project Queue Orchestrator" in report_path.read_text(encoding="utf-8")

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["project_count"] == 1
    assert artifact["metrics"]["task_count"] == 4
    assert artifact["metrics"]["status_counts"]["building"] == 1
    assert artifact["last_operation"]["action"] == "run-next"

    project = artifact["projects"][0]
    assert Path(project["project_dir"]).exists()
    assert Path(project["cdc_path"]).exists()
    assert Path(project["tasks_path"]).exists()
    assert Path(project["readme_path"]).exists()


def test_project_execution_loop_cli_writes_report_and_artifact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "Loop Test",
            "--description",
            "Projet boucle",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "run-loop", "--max-steps", "5"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "status", "--id", "1"]) == 0

    report_path = runtime / "reports" / "PROJECT_EXECUTION_LOOP.md"
    artifact_path = runtime / "kernel" / "project_execution_loop.json"
    assert report_path.exists()
    assert artifact_path.exists()
    assert "Project Execution Loop" in report_path.read_text(encoding="utf-8")

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["executed_task_count"] == 4
    assert artifact["metrics"]["done_project_count"] == 1
    snapshot = artifact["snapshot"]
    assert snapshot["projects"][0]["status"] == "done"

    project_dir = Path(snapshot["projects"][0]["project_dir"])
    assert (project_dir / "RUNS.md").exists()
    assert (project_dir / "artifacts" / "run_0004.md").exists()


def test_project_queue_uses_mock_provider_by_default(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
    )

    assert queue.provider.name == "mock"


def test_nvidia_provider_without_key_queues_review_without_blocking_process(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=NvidiaNimProvider(api_key=None),
    )
    queue.add_project(title="NIM Test", description="Projet provider reel")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    reviews = queue.list_reviews()

    assert result["steps"][0]["action_taken"] == "pending_review"
    assert reviews["metrics"]["pending_review_count"] == 1
    assert reviews["reviews"][0]["provider_mode"] == "nvidia_nim"


def test_dry_run_does_not_write_project_execution_files(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=DryRunProvider(),
    )
    queue.add_project(title="Dry Run", description="Projet simulation")
    queue.design_project(1)
    queue.validate_project(1)
    project_dir = Path(queue.get_project(1)["project_dir"])

    result = queue.run_loop(max_steps=1)

    assert result["steps"][0]["execution"]["status"] == "done"
    assert result["steps"][0]["execution"]["artifacts"] == []
    assert not (project_dir / "RUNS.md").exists()
    assert not (project_dir / "artifacts").exists()


def test_execution_guard_blocks_dangerous_provider_output(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=DangerousProvider(),
        guard=ExecutionGuard(max_changed_files=2, max_output_tokens=100),
    )
    queue.add_project(title="Guard Test", description="Projet guard")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    guard_snapshot = queue.guard_snapshot()

    assert result["steps"][0]["execution"]["status"] == "blocked"
    assert guard_snapshot["metrics"]["blocked_output_count"] == 1
    assert not (tmp_path / "projects" / "escape.txt").exists()


def test_review_accept_applies_guarded_changes(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=ManualReviewProvider(),
    )
    queue.add_project(title="Review Accept", description="Projet review")
    queue.design_project(1)
    queue.validate_project(1)

    queue.run_loop(max_steps=1)
    reviews = queue.list_reviews()
    review_id = reviews["reviews"][0]["id"]
    target = Path(queue.get_project(1)["project_dir"]) / "provider_outputs" / "task_0001.md"
    assert not target.exists()

    accepted = queue.accept_review(review_id)

    assert accepted["applied"] is True
    assert target.exists()
    assert queue.list_reviews(status=None)["reviews"][0]["status"] == "accepted"
    assert queue.project_status(1)["project"]["tasks"][0]["status"] == "done"


def test_review_reject_does_not_apply_changes(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=ManualReviewProvider(),
    )
    queue.add_project(title="Review Reject", description="Projet review")
    queue.design_project(1)
    queue.validate_project(1)

    queue.run_loop(max_steps=1)
    review_id = queue.list_reviews()["reviews"][0]["id"]
    target = Path(queue.get_project(1)["project_dir"]) / "provider_outputs" / "task_0001.md"
    rejected = queue.reject_review(review_id)

    assert rejected["rejected"] is True
    assert not target.exists()
    assert queue.list_reviews(status=None)["reviews"][0]["status"] == "rejected"
    assert queue.project_status(1)["project"]["status"] == "blocked"


def test_project_review_cli_accepts_manual_review_output(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "CLI Review",
            "--description",
            "Projet review CLI",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate", "--id", "1"]) == 0
    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "run-loop",
            "--max-steps",
            "1",
            "--provider",
            "manual_review",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "review", "list"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "review", "accept", "--id", "1"]) == 0

    report_path = runtime / "reports" / "REAL_PROVIDER_EXECUTION_GUARD.md"
    artifact_path = runtime / "kernel" / "real_provider_execution_guard.json"
    assert report_path.exists()
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["accepted_review_count"] == 1
    assert (runtime / "projects" / "0001-cli-review" / "provider_outputs" / "task_0001.md").exists()


def test_context_pack_contains_sources_and_respects_budget(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=MockLLMProvider(),
        context_builder=ContextPackBuilder(token_budget=80),
    )
    queue.add_project(title="Context Test", description="Projet contexte")
    queue.design_project(1)

    result = queue.build_context_pack(1, 1)
    pack = result["context_pack"]

    assert pack["source_refs"]
    assert pack["selected_files"]
    assert pack["materialized_tokens"] <= pack["token_budget"]
    assert pack["evidence_score"] > 0
    assert (Path(queue.get_project(1)["project_dir"]) / "CONTEXT_PACKS.md").exists()


def test_context_pack_low_evidence_refuses_provider_call(tmp_path: Path) -> None:
    provider = RecordingProvider()
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=provider,
        context_builder=ContextPackBuilder(min_evidence_score=1.1),
    )
    queue.add_project(title="Low Evidence", description="Projet contexte")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1, use_context_pack=True)

    assert result["steps"][0]["execution"]["validation_status"] == "low_evidence"
    assert provider.prompts == []
    assert queue.project_status(1)["project"]["status"] == "blocked"


def test_provider_receives_context_pack_prompt(tmp_path: Path) -> None:
    provider = RecordingProvider()
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=provider,
    )
    queue.add_project(title="Prompt Context", description="Projet contexte")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1, use_context_pack=True)

    assert result["steps"][0]["execution"]["status"] == "done"
    assert provider.prompts
    assert "TaskContextPack" in provider.prompts[0]
    assert "## Safety Rules" in provider.prompts[0]
    assert queue.context_snapshot()["metrics"]["context_pack_count"] == 1


def test_dry_run_with_context_pack_does_not_write_execution_files(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=DryRunProvider(),
    )
    queue.add_project(title="Dry Context", description="Projet contexte")
    queue.design_project(1)
    queue.validate_project(1)
    project_dir = Path(queue.get_project(1)["project_dir"])

    result = queue.run_loop(max_steps=1, use_context_pack=True)

    assert result["steps"][0]["execution"]["status"] == "done"
    assert result["steps"][0]["execution"]["artifacts"] == []
    assert (project_dir / "CONTEXT_PACKS.md").exists()
    assert not (project_dir / "RUNS.md").exists()
    assert not (project_dir / "artifacts").exists()


def test_project_context_cli_writes_report_and_artifact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "CLI Context",
            "--description",
            "Projet contexte CLI",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "context", "--id", "1", "--task-id", "1"]) == 0

    report_path = runtime / "reports" / "CONTEXT_PACK_PROVIDER_PROMPTING.md"
    artifact_path = runtime / "kernel" / "context_pack_provider_prompting.json"
    assert report_path.exists()
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["context_pack_count"] == 1
    assert artifact["context_packs"][0]["context_pack"]["source_refs"]


def test_patch_valid_applied(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/result.md ===\n# Result\n\nPatch applied.\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Apply", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    project_dir = Path(queue.get_project(1)["project_dir"])
    patches = queue.list_patches(status=None)

    assert result["steps"][0]["execution"]["status"] == "done"
    assert (project_dir / "provider_outputs" / "result.md").exists()
    assert (project_dir / "PATCHES.md").exists()
    assert (project_dir / "VALIDATIONS.md").exists()
    assert patches["patches"][0]["status"] == "applied"
    assert queue.list_validations()["metrics"]["passed_plan_count"] == 1


def test_patch_outside_project_rejected(tmp_path: Path) -> None:
    patch_text = "=== FILE: ../escape.md ===\nunsafe\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Outside", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    patches = queue.list_patches(status=None)

    assert result["steps"][0]["execution"]["validation_status"] == "patch_failed"
    assert patches["patches"][0]["status"] == "failed"
    assert not (tmp_path / "projects" / "escape.md").exists()


def test_patch_too_large_rejected(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/large.md ===\n" + ("x" * 256)
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
        patch_parser=PatchParser(max_patch_bytes=80),
    )
    queue.add_project(title="Patch Large", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    patches = queue.list_patches(status=None)

    assert result["steps"][0]["execution"]["validation_status"] == "patch_failed"
    assert patches["patches"][0]["patch_report"].endswith("patch_too_large")


def test_patch_binary_file_rejected(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/image.png ===\nnot really an image\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Binary", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    patches = queue.list_patches(status=None)

    assert result["steps"][0]["execution"]["validation_status"] == "patch_failed"
    assert patches["patches"][0]["patch_report"].endswith("binary_file_refused")


def test_patch_dry_run_without_target_modification(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/dry.md ===\n# Dry\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text, name="dry_run"),
    )
    queue.add_project(title="Patch Dry", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)
    project_dir = Path(queue.get_project(1)["project_dir"])

    result = queue.run_loop(max_steps=1)
    patch = queue.list_patches(status=None)["patches"][0]

    assert result["steps"][0]["execution"]["status"] == "done"
    assert patch["status"] == "applied"
    assert not (project_dir / "provider_outputs" / "dry.md").exists()


def test_patch_review_required_blocks_auto_apply(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/review.md ===\n# Review\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Review", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)
    project_dir = Path(queue.get_project(1)["project_dir"])

    result = queue.run_loop(max_steps=2, review_required=True)
    patch = queue.list_patches(status=None)["patches"][0]

    assert result["steps"][0]["action_taken"] == "patch_proposed"
    assert patch["status"] == "proposed"
    assert not (project_dir / "provider_outputs" / "review.md").exists()


def test_patch_reject_sets_status_rejected(tmp_path: Path) -> None:
    patch_text = "=== FILE: provider_outputs/reject.md ===\n# Reject\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Reject", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)
    queue.run_loop(max_steps=1, review_required=True)
    patch_id = queue.list_patches(status=None)["patches"][0]["id"]

    result = queue.reject_patch_proposal(patch_id)

    assert result["rejected"] is True
    assert queue.list_patches(status=None)["patches"][0]["status"] == "rejected"


def test_patch_apply_fails_when_validation_fails(tmp_path: Path) -> None:
    patch_text = "=== FILE: broken.py ===\ndef broken(:\n    pass\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Patch Invalid", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    result = queue.run_loop(max_steps=1)
    patch = queue.list_patches(status=None)["patches"][0]
    validations = queue.list_validations()
    status = queue.project_status(1)

    assert result["steps"][0]["execution"]["validation_status"] == "failed_validation"
    assert patch["status"] == "failed_validation"
    assert validations["metrics"]["failed_plan_count"] == 1
    assert status["project"]["tasks"][0]["status"] == "blocked"
    failures = queue.list_failures()
    retry_task = next(
        task for task in queue.project_status(1)["project"]["tasks"] if task["id"] == failures["failures"][0]["retry_task_id"]
    )
    assert failures["metrics"]["failure_count"] == 1
    assert failures["metrics"]["retry_task_count"] == 1
    assert "FailureRecord:" in retry_task["description"]


def test_retry_failure_reuses_retry_task_with_error_context(tmp_path: Path) -> None:
    patch_text = "=== FILE: broken.py ===\ndef broken(:\n    pass\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
    )
    queue.add_project(title="Retry Context", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)
    queue.run_loop(max_steps=1)
    failure = queue.list_failures()["failures"][0]

    result = queue.retry_failure(failure["id"])

    assert result["retried"] is True
    assert result["retry_task"]["id"] == failure["retry_task_id"]
    assert "Failed Command" in result["retry_task"]["description"]
    assert "broken.py" in result["retry_task"]["description"]


def test_retry_policy_blocks_infinite_retry_loop(tmp_path: Path) -> None:
    patch_text = "=== FILE: broken.py ===\ndef broken(:\n    pass\n"
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=PatchProvider(patch_text),
        retry_policy=RetryPolicy(max_retries_per_task=0, max_retries_per_project=0),
    )
    queue.add_project(title="Retry Block", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    queue.run_loop(max_steps=1)
    failure = queue.list_failures()["failures"][0]

    assert failure["status"] == "abandoned"
    assert failure["retry_task_id"] is None
    assert queue.project_status(1)["project"]["status"] == "blocked"


def test_failure_resolved_when_retry_patch_passes(tmp_path: Path) -> None:
    queue = ProjectQueue(
        tmp_path / "stores" / "project_queue.sqlite",
        projects_root=tmp_path / "projects",
        provider=RepairProvider(),
        retry_policy=RetryPolicy(retry_requires_review=False),
    )
    queue.add_project(title="Retry Resolve", description="Projet patch")
    queue.design_project(1)
    queue.validate_project(1)

    first = queue.run_loop(max_steps=1)
    failure = queue.list_failures()["failures"][0]
    second = queue.run_loop(max_steps=1)
    resolved = queue.list_failures()["failures"][0]
    status = queue.project_status(1)

    assert first["steps"][0]["execution"]["validation_status"] == "failed_validation"
    assert second["steps"][0]["execution"]["validation_status"] == "passed"
    assert resolved["status"] == "resolved"
    assert status["project"]["tasks"][0]["status"] == "done"
    assert status["project"]["tasks"][1]["id"] == failure["retry_task_id"]
    assert status["project"]["tasks"][1]["status"] == "done"


def test_safe_command_runner_refuses_dangerous_command(tmp_path: Path) -> None:
    result = SafeCommandRunner().run(
        command="rm -rf .",
        cwd=tmp_path,
        max_runtime_sec=5,
        allowed_commands=["python -m compileall"],
    )

    assert result["passed"] is False
    assert result["exit_code"] == -1
    assert result["stderr_tail"].startswith("dangerous_command:")


def test_project_validate_patch_cli_writes_report_and_artifact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "CLI Validate Patch",
            "--description",
            "Projet validation patch CLI",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "run-loop", "--max-steps", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate-patch", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validation", "list"]) == 0

    report_path = runtime / "reports" / "POST_PATCH_VALIDATION_LOOP.md"
    artifact_path = runtime / "kernel" / "post_patch_validation_loop.json"
    assert report_path.exists()
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["passed_plan_count"] >= 1


def test_project_patch_cli_writes_report_and_artifact(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "add",
            "--title",
            "CLI Patch",
            "--description",
            "Projet patch CLI",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "design", "--id", "1"]) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "validate", "--id", "1"]) == 0
    assert cli_main(
        [
            "project",
            "--runtime-dir",
            str(runtime),
            "run-loop",
            "--max-steps",
            "1",
            "--review-required",
        ]
    ) == 0
    assert cli_main(["project", "--runtime-dir", str(runtime), "patch", "list"]) == 0

    report_path = runtime / "reports" / "PATCH_PROPOSAL_APPLY_GATE.md"
    artifact_path = runtime / "kernel" / "patch_proposal_apply_gate.json"
    assert report_path.exists()
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["metrics"]["proposed_count"] == 1
