from __future__ import annotations

import json
import os
import re
import shlex
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .io import utc_ts, write_text
from .mmr import _index_workload_source, _select_workload_chunks, _token_estimate, _workload_coherence_score


PROJECT_QUEUE_SCHEMA_VERSION = "project-queue-orchestrator-v1"
PROJECT_STATUSES = {
    "idea",
    "designing",
    "valid",
    "building",
    "testing",
    "blocked",
    "done",
    "archived",
}
PROVIDER_MODES = {"mock", "nvidia_nim", "dry_run", "manual_review"}
REVIEW_STATUSES = {"pending_review", "accepted", "rejected"}
REAL_PROVIDER_MODES = {"nvidia_nim", "manual_review"}
DEFAULT_MAX_CHANGED_FILES = 8
DEFAULT_MAX_OUTPUT_TOKENS = 1200
DEFAULT_CONTEXT_TOKEN_BUDGET = 700
MIN_CONTEXT_EVIDENCE_SCORE = 0.15
MAX_PATCH_BYTES = 80_000
MAX_PATCH_FILES = 8
PATCH_STATUSES = {"proposed", "approved", "rejected", "applied", "failed", "failed_validation"}
VALIDATION_STATUSES = {"planned", "running", "passed", "failed", "rejected"}
DEFAULT_VALIDATION_COMMANDS = ["python -m compileall -q ."]
DEFAULT_ALLOWED_VALIDATION_COMMANDS = [
    "python -m pytest",
    "python -m aione_forge.cli",
    "python -m compileall",
]
FAILURE_STATUSES = {"open", "retrying", "resolved", "abandoned"}
DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bRemove-Item\b.*\b-Recurse\b",
    r"\bdel\b.*\b/s\b",
    r"\brmdir\b.*\b/s\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bdiskpart\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]


class LLMProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def design_project(self, *, title: str, description: str) -> dict[str, Any]:
        ...

    def execute_task(self, *, project: dict[str, Any], task: dict[str, Any], input_prompt: str) -> dict[str, Any]:
        ...


@dataclass
class MockLLMProvider:
    name: str = "mock"

    def available(self) -> bool:
        return True

    def design_project(self, *, title: str, description: str) -> dict[str, Any]:
        base_tasks = [
            {
                "title": "Clarify project contract",
                "description": f"Turn `{title}` into a concise CDC with scope, constraints and acceptance gates.",
            },
            {
                "title": "Initialize project workspace",
                "description": "Create README, CDC and task list files with traceable decisions.",
            },
            {
                "title": "Add validation path",
                "description": "Define tests, review gates and a minimal proof artifact before building.",
            },
            {
                "title": "Prepare first build slice",
                "description": "Select the smallest useful implementation slice and expected outputs.",
            },
        ]
        return {
            "provider": self.name,
            "used_fallback": False,
            "summary": f"Project `{title}` is ready for CDC drafting and initialization.",
            "cdc_sections": [
                "Objective",
                "Problem",
                "Scope",
                "Constraints",
                "Acceptance criteria",
                "Risks",
                "Initialization",
            ],
            "tasks": base_tasks,
            "notes": [
                "Mock provider is deterministic.",
                "External model output can replace this structure later.",
            ],
        }

    def execute_task(self, *, project: dict[str, Any], task: dict[str, Any], input_prompt: str) -> dict[str, Any]:
        summary = (
            f"Executed task `{task['title']}` for project `{project['title']}` using the mock provider. "
            "The execution produced a trace artifact and passed local validation."
        )
        artifact_body = "\n".join(
            [
                f"# Task Run - {task['title']}",
                "",
                f"Project: {project['title']}",
                f"Task: {task['title']}",
                "",
                "## Input Prompt",
                "",
                input_prompt,
                "",
                "## Output Summary",
                "",
                summary,
            ]
        )
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": summary,
            "changed_files": [],
            "patch_text": _mock_patch_text(project=project, task=task, summary=summary),
            "artifacts": [
                {
                    "name": "run_report",
                    "content": artifact_body,
                }
            ],
            "validation_status": "passed",
        }


@dataclass
class NvidiaNimProvider:
    api_key: str | None
    model: str | None = None
    endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    name: str = "nvidia_nim"

    def available(self) -> bool:
        return bool(self.api_key)

    def design_project(self, *, title: str, description: str) -> dict[str, Any]:
        if not self.available():
            fallback = MockLLMProvider().design_project(title=title, description=description)
            return {
                **fallback,
                "provider": self.name,
                "used_fallback": True,
                "fallback_reason": "NVIDIA_API_KEY is not set.",
            }
        fallback = MockLLMProvider().design_project(title=title, description=description)
        return {
            **fallback,
            "provider": self.name,
            "used_fallback": True,
            "fallback_reason": "NVIDIA NIM adapter is configured but network generation is disabled in v31.",
            "external_provider_ready": True,
        }

    def execute_task(self, *, project: dict[str, Any], task: dict[str, Any], input_prompt: str) -> dict[str, Any]:
        fallback = MockLLMProvider().execute_task(project=project, task=task, input_prompt=input_prompt)
        fallback.pop("patch_text", None)
        if not self.available():
            return {
                **fallback,
                "provider": self.name,
                "used_fallback": True,
                "fallback_reason": "NVIDIA_API_KEY is not set.",
            }
        if not self.model:
            return {
                **fallback,
                "provider": self.name,
                "used_fallback": True,
                "fallback_reason": "NVIDIA_NIM_MODEL is not set.",
                "external_provider_ready": True,
            }
        try:
            provider_output = self._chat_completion(input_prompt=input_prompt)
            parsed = _extract_json_object(provider_output) or {}
            output_summary = str(parsed.get("output_summary") or parsed.get("summary") or provider_output)
            proposed_changes = parsed.get("proposed_changes", [])
            if not isinstance(proposed_changes, list):
                proposed_changes = []
            changed_files = [
                str(change.get("path", ""))
                for change in proposed_changes
                if isinstance(change, dict) and change.get("path")
            ]
            patch_text = parsed.get("patch_text")
            return {
                "provider": self.name,
                "status": "done",
                "output_summary": output_summary,
                "changed_files": changed_files,
                "proposed_changes": proposed_changes,
                "patch_text": patch_text if isinstance(patch_text, str) else "",
                "artifacts": [
                    {
                        "name": "nvidia_nim_response",
                        "content": provider_output,
                    }
                ],
                "validation_status": "passed",
                "external_provider_ready": True,
                "model": self.model,
                "used_fallback": False,
                "review_required": True,
            }
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            return {
                **fallback,
                "provider": self.name,
                "used_fallback": True,
                "fallback_reason": f"NVIDIA NIM execution failed: {exc}",
                "external_provider_ready": True,
            }

    def _chat_completion(self, *, input_prompt: str) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an execution planner. Return strict JSON with keys: "
                        "output_summary, proposed_changes and optional patch_text. "
                        "proposed_changes must be an array of objects with operation, path and content. "
                        "patch_text must use === FILE: path === sections when present. "
                        "Only propose files inside the project folder and never include destructive shell commands."
                    ),
                },
                {"role": "user", "content": input_prompt},
            ],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"])


@dataclass
class DryRunProvider:
    name: str = "dry_run"

    def available(self) -> bool:
        return True

    def design_project(self, *, title: str, description: str) -> dict[str, Any]:
        fallback = MockLLMProvider().design_project(title=title, description=description)
        return {**fallback, "provider": self.name, "dry_run": True}

    def execute_task(self, *, project: dict[str, Any], task: dict[str, Any], input_prompt: str) -> dict[str, Any]:
        summary = (
            f"Dry-run execution for task `{task['title']}` in project `{project['title']}`. "
            "No project file was written."
        )
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": summary,
            "changed_files": [],
            "artifacts": [],
            "validation_status": "passed",
            "dry_run": True,
        }


@dataclass
class ManualReviewProvider:
    name: str = "manual_review"

    def available(self) -> bool:
        return True

    def design_project(self, *, title: str, description: str) -> dict[str, Any]:
        fallback = MockLLMProvider().design_project(title=title, description=description)
        return {**fallback, "provider": self.name, "review_required": True}

    def execute_task(self, *, project: dict[str, Any], task: dict[str, Any], input_prompt: str) -> dict[str, Any]:
        proposed_path = f"provider_outputs/task_{int(task['id']):04d}.md"
        summary = (
            f"Manual-review provider prepared a non-destructive change for `{task['title']}`. "
            "The change must be accepted before it is applied."
        )
        return {
            "provider": self.name,
            "status": "done",
            "output_summary": summary,
            "changed_files": [proposed_path],
            "proposed_changes": [
                {
                    "operation": "write",
                    "path": proposed_path,
                    "content": summary + "\n",
                }
            ],
            "artifacts": [
                {
                    "name": "manual_review_output",
                    "content": summary,
                }
            ],
            "validation_status": "passed",
            "review_required": True,
        }


def provider_from_env() -> LLMProvider:
    if os.environ.get("NVIDIA_API_KEY"):
        return NvidiaNimProvider(api_key=os.environ.get("NVIDIA_API_KEY"))
    return MockLLMProvider()


def provider_for_mode(mode: str | None) -> LLMProvider:
    provider_mode = mode or "mock"
    if provider_mode not in PROVIDER_MODES:
        raise ValueError(f"Unsupported provider mode: {provider_mode}")
    if provider_mode == "mock":
        return MockLLMProvider()
    if provider_mode == "nvidia_nim":
        return NvidiaNimProvider(
            api_key=os.environ.get("NVIDIA_API_KEY"),
            model=os.environ.get("NVIDIA_NIM_MODEL"),
            endpoint=os.environ.get(
                "NVIDIA_NIM_ENDPOINT",
                "https://integrate.api.nvidia.com/v1/chat/completions",
            ),
        )
    if provider_mode == "dry_run":
        return DryRunProvider()
    return ManualReviewProvider()


@dataclass
class ExecutionGuard:
    max_changed_files: int = DEFAULT_MAX_CHANGED_FILES
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    def validate(self, *, project: dict[str, Any], provider_result: dict[str, Any]) -> dict[str, Any]:
        project_dir = Path(project["project_dir"]).resolve()
        violations: list[str] = []
        safe_changes: list[dict[str, Any]] = []
        commands = [str(command) for command in provider_result.get("commands", [])]
        command_text = "\n".join(commands + [str(provider_result.get("output_summary", ""))])
        for pattern in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command_text, flags=re.IGNORECASE):
                violations.append(f"dangerous_command:{pattern}")

        proposed_changes = _normalize_proposed_changes(provider_result)
        if len(proposed_changes) > self.max_changed_files:
            violations.append(f"max_changed_files_exceeded:{len(proposed_changes)}>{self.max_changed_files}")

        for change in proposed_changes:
            safe_change, violation = _guard_change(project_dir, change)
            if violation:
                violations.append(violation)
            if safe_change:
                safe_changes.append(safe_change)

        output_tokens = _provider_output_tokens(provider_result)
        if output_tokens > self.max_output_tokens:
            violations.append(f"max_output_tokens_exceeded:{output_tokens}>{self.max_output_tokens}")

        return {
            "status": "blocked" if violations else "passed",
            "violations": violations,
            "safe_changes": safe_changes,
            "changed_file_count": len(proposed_changes),
            "max_changed_files": self.max_changed_files,
            "output_tokens": output_tokens,
            "max_output_tokens": self.max_output_tokens,
            "project_dir": str(project_dir),
        }


@dataclass
class ContextPackBuilder:
    token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET
    materialization_limit: int = 8
    min_evidence_score: float = MIN_CONTEXT_EVIDENCE_SCORE

    def build(self, *, project: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        project_dir = Path(project["project_dir"])
        index = _index_workload_source(project_dir, chunk_line_count=28)
        source_chunks = [
            chunk for chunk in index["chunks"] if not _is_generated_context_file(chunk["file_path"])
        ]
        query_terms = _context_query_terms(project, task)
        selected = _select_workload_chunks(source_chunks, query_terms, self.materialization_limit)
        budgeted = _budget_chunks(selected, self.token_budget)
        selected_files = sorted({chunk["file_path"] for chunk in budgeted})
        selected_chunks = [_context_chunk_summary(chunk) for chunk in budgeted]
        source_refs = [
            f"{chunk['file_path']}:{chunk['start_line']}-{chunk['end_line']}"
            for chunk in budgeted
        ]
        excluded_files = sorted(
            {chunk["file_path"] for chunk in source_chunks}
            - {chunk["file_path"] for chunk in budgeted}
        )
        total_tokens = sum(chunk.get("token_estimate", 0) for chunk in source_chunks)
        materialized_tokens = sum(chunk.get("token_estimate", 0) for chunk in budgeted)
        evidence_score = _workload_coherence_score(budgeted, query_terms) if budgeted else 0.0
        relative_cost = round(materialized_tokens / max(1, total_tokens), 3)
        return {
            "project_id": int(project["id"]),
            "task_id": int(task["id"]),
            "task_title": task["title"],
            "selected_files": selected_files,
            "selected_chunks": selected_chunks,
            "source_refs": source_refs,
            "key_facts": _context_key_facts(budgeted, query_terms),
            "relevant_tests": _context_relevant_tests(source_chunks, query_terms),
            "constraints": _context_constraints(project, budgeted),
            "excluded_summary": _excluded_summary(excluded_files, index["workload_source"]["file_count"]),
            "token_budget": self.token_budget,
            "materialized_tokens": materialized_tokens,
            "total_available_tokens": total_tokens,
            "relative_resolution_cost": relative_cost,
            "evidence_score": evidence_score,
            "query_terms": query_terms,
            "created_at": utc_ts(),
        }

    def provider_prompt(self, *, project: dict[str, Any], task: dict[str, Any], context_pack: dict[str, Any]) -> dict[str, Any]:
        system_prompt = (
            "You are an AIONE project execution provider. Use only the supplied context pack, "
            "respect the safety rules, and return traceable output."
        )
        safety_rules = [
            "Do not use destructive commands.",
            "Only propose changes inside the project directory.",
            "Keep outputs bounded and source-aware.",
            "If context evidence is insufficient, say what is missing instead of inventing facts.",
        ]
        output_contract = {
            "output_summary": "short sourced summary",
            "proposed_changes": "optional array of {operation,path,content}",
            "patch_text": "optional patch proposal using === FILE: path === sections",
            "changed_files": "optional array of project-relative files",
        }
        task_prompt = "\n".join(
            [
                f"Project: {project['title']}",
                f"Description: {project['description']}",
                f"Task: {task['title']}",
                f"Task description: {task['description']}",
                "Use the TaskContextPack below before deciding what to do.",
                json.dumps(context_pack, indent=2, ensure_ascii=False),
            ]
        )
        return {
            "system_prompt": system_prompt,
            "task_prompt": task_prompt,
            "context_pack": context_pack,
            "safety_rules": safety_rules,
            "output_contract": output_contract,
        }


@dataclass
class PatchParser:
    max_patch_bytes: int = MAX_PATCH_BYTES
    max_files: int = MAX_PATCH_FILES

    def parse(self, *, project: dict[str, Any], patch_text: str) -> dict[str, Any]:
        project_dir = Path(project["project_dir"]).resolve()
        if len(patch_text.encode("utf-8", errors="ignore")) > self.max_patch_bytes:
            raise ValueError("patch_too_large")
        sections = _split_patch_sections(patch_text)
        if not sections:
            raise ValueError("missing_file_sections")
        if len(sections) > self.max_files:
            raise ValueError("too_many_files")
        changes = []
        target_files = []
        for raw_path, content in sections:
            if "\x00" in content:
                raise ValueError("binary_patch_refused")
            target = Path(raw_path.strip())
            if not target.as_posix() or target.is_absolute():
                raise ValueError("invalid_patch_path")
            if _is_binary_patch_path(target):
                raise ValueError("binary_file_refused")
            resolved = (project_dir / target).resolve()
            if not _is_relative_to(resolved, project_dir):
                raise ValueError("patch_path_outside_project")
            safe_path = target.as_posix()
            materialized_content = content.strip("\n") + "\n"
            if _looks_like_unified_diff(content):
                original = resolved.read_text(encoding="utf-8") if resolved.exists() else ""
                materialized_content = _apply_unified_diff(original, content)
            target_files.append(safe_path)
            changes.append(
                {
                    "operation": "write",
                    "path": safe_path,
                    "resolved_path": str(resolved),
                    "content": materialized_content,
                }
            )
        return {
            "target_files": target_files,
            "changes": changes,
            "diff_text": patch_text,
            "risk_level": _patch_risk_level(changes, patch_text),
        }


@dataclass
class ApplyGate:
    guard: ExecutionGuard

    def apply(
        self,
        *,
        project: dict[str, Any],
        proposal: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        changes = proposal.get("parsed_changes", [])
        provider_result = {
            "output_summary": proposal.get("summary", ""),
            "proposed_changes": changes,
            "changed_files": proposal.get("target_files", []),
        }
        guard_report = self.guard.validate(project=project, provider_result=provider_result)
        if guard_report["status"] == "blocked":
            return {
                "status": "failed",
                "changed_files": [],
                "patch_report": "ApplyGate blocked patch: " + ", ".join(guard_report["violations"]),
                "guard_report": guard_report,
                "dry_run": dry_run,
            }
        target_root = Path(project["project_dir"]).resolve()
        if dry_run:
            target_root = Path(tempfile.mkdtemp(prefix="aione_patch_dry_run_")).resolve()
        changed_files = []
        for change in guard_report["safe_changes"]:
            relative = Path(change["resolved_path"]).resolve().relative_to(Path(project["project_dir"]).resolve())
            target = target_root / relative
            if change.get("operation") == "delete":
                if target.exists() and target.is_file():
                    target.unlink()
            else:
                write_text(target, str(change.get("content", "")))
            changed_files.append(str(target))
        return {
            "status": "applied",
            "changed_files": changed_files,
            "patch_report": (
                f"Patch {proposal['id']} applied in {'dry_run' if dry_run else 'project'} mode. "
                f"Changed files: {len(changed_files)}."
            ),
            "guard_report": guard_report,
            "dry_run": dry_run,
            "dry_run_root": str(target_root) if dry_run else None,
        }


@dataclass
class SafeCommandRunner:
    max_stdout_chars: int = 2000
    max_stderr_chars: int = 2000

    def run(
        self,
        *,
        command: str,
        cwd: Path,
        max_runtime_sec: int,
        allowed_commands: list[str],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        allowed, reason = self._validate_command(command=command, cwd=cwd, allowed_commands=allowed_commands)
        if not allowed:
            return {
                "command": command,
                "exit_code": -1,
                "stdout_tail": "",
                "stderr_tail": reason,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "passed": False,
            }
        args = shlex.split(command, posix=False)
        try:
            completed = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=max_runtime_sec,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            stdout_tail = completed.stdout[-self.max_stdout_chars :]
            stderr_tail = completed.stderr[-self.max_stderr_chars :]
            return {
                "command": command,
                "exit_code": int(completed.returncode),
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "passed": completed.returncode == 0,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "exit_code": -1,
                "stdout_tail": str(exc.stdout or "")[-self.max_stdout_chars :],
                "stderr_tail": "validation_timeout",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "passed": False,
            }
        except OSError as exc:
            return {
                "command": command,
                "exit_code": -1,
                "stdout_tail": "",
                "stderr_tail": f"validation_os_error:{exc}",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "passed": False,
            }

    def _validate_command(
        self,
        *,
        command: str,
        cwd: Path,
        allowed_commands: list[str],
    ) -> tuple[bool, str]:
        lowered = command.lower()
        for pattern in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command, flags=re.IGNORECASE):
                return False, f"dangerous_command:{pattern}"
        network_tokens = [
            "curl",
            "wget",
            "invoke-webrequest",
            "irm ",
            "iwr ",
            "http://",
            "https://",
            "pip install",
            "git clone",
            "ssh ",
            "scp ",
        ]
        if any(token in lowered for token in network_tokens):
            return False, "network_command_refused"
        try:
            args = shlex.split(command, posix=False)
        except ValueError as exc:
            return False, f"invalid_command:{exc}"
        if len(args) < 3 or args[0].lower() != "python" or args[1] != "-m":
            return False, "command_not_whitelisted"
        command_prefix = " ".join(args[:3])
        if not any(command_prefix == allowed or command_prefix.startswith(allowed + " ") for allowed in allowed_commands):
            return False, "command_not_whitelisted"
        project_dir = cwd.resolve()
        for arg in args[3:]:
            if arg.startswith("-"):
                continue
            if "://" in arg:
                return False, "network_path_refused"
            if "/" not in arg and "\\" not in arg and not arg.startswith("."):
                continue
            candidate = Path(arg)
            if not candidate.is_absolute():
                candidate = project_dir / candidate
            resolved = candidate.resolve()
            if not _is_relative_to(resolved, project_dir):
                return False, f"path_outside_project:{resolved}"
        return True, "allowed"


@dataclass
class RetryPolicy:
    max_retries_per_task: int = 2
    max_retries_per_project: int = 8
    retry_requires_review: bool = True
    stop_on_repeated_failure: bool = True


class ProjectQueue:
    def __init__(
        self,
        db_path: Path,
        *,
        projects_root: Path,
        provider: LLMProvider | None = None,
        guard: ExecutionGuard | None = None,
        context_builder: ContextPackBuilder | None = None,
        patch_parser: PatchParser | None = None,
        command_runner: SafeCommandRunner | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.db_path = db_path
        self.projects_root = projects_root
        self.provider = provider or MockLLMProvider()
        self.guard = guard or ExecutionGuard()
        self.context_builder = context_builder or ContextPackBuilder()
        self.patch_parser = patch_parser or PatchParser()
        self.command_runner = command_runner or SafeCommandRunner()
        self.retry_policy = retry_policy or RetryPolicy()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.projects_root.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            self.ensure_schema(connection)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                slug TEXT NOT NULL,
                project_dir TEXT,
                cdc_path TEXT,
                tasks_path TEXT,
                readme_path TEXT,
                provider_name TEXT NOT NULL,
                validation_report TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                action TEXT NOT NULL,
                status_before TEXT,
                status_after TEXT,
                provider_name TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                input_prompt TEXT NOT NULL,
                output_summary TEXT NOT NULL,
                changed_files TEXT NOT NULL,
                artifacts TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                execution_id INTEGER NOT NULL,
                provider_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                input_prompt TEXT NOT NULL,
                provider_response TEXT NOT NULL,
                guard_report TEXT NOT NULL,
                proposed_changes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(execution_id) REFERENCES task_executions(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_guard_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                provider_mode TEXT NOT NULL,
                input_prompt TEXT NOT NULL,
                provider_response TEXT NOT NULL,
                guard_report TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(execution_id) REFERENCES task_executions(id),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_context_packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                execution_id INTEGER,
                token_budget INTEGER NOT NULL,
                evidence_score REAL NOT NULL,
                relative_resolution_cost REAL NOT NULL,
                context_pack TEXT NOT NULL,
                provider_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(execution_id) REFERENCES task_executions(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patch_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                execution_id INTEGER,
                provider_mode TEXT NOT NULL,
                target_files TEXT NOT NULL,
                diff_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                parsed_changes TEXT NOT NULL,
                patch_report TEXT NOT NULL,
                diff_path TEXT,
                report_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(execution_id) REFERENCES task_executions(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                patch_id INTEGER NOT NULL,
                commands TEXT NOT NULL,
                max_runtime_sec INTEGER NOT NULL,
                allowed_commands TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(patch_id) REFERENCES patch_proposals(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                stdout_tail TEXT NOT NULL,
                stderr_tail TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES validation_plans(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS failure_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                patch_id INTEGER NOT NULL,
                validation_plan_id INTEGER NOT NULL,
                retry_task_id INTEGER,
                failing_command TEXT NOT NULL,
                stdout_tail TEXT NOT NULL,
                stderr_tail TEXT NOT NULL,
                failure_summary TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(patch_id) REFERENCES patch_proposals(id),
                FOREIGN KEY(validation_plan_id) REFERENCES validation_plans(id),
                FOREIGN KEY(retry_task_id) REFERENCES tasks(id)
            )
            """
        )

    def add_project(self, *, title: str, description: str) -> dict[str, Any]:
        now = utc_ts()
        slug = _slugify(title)
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM projects
                WHERE title = ? AND description = ? AND status != 'archived'
                ORDER BY id ASC
                LIMIT 1
                """,
                (title, description),
            ).fetchone()
            if existing is not None:
                project = _row_to_dict(existing)
                self._record_run(
                    connection,
                    project_id=project["id"],
                    action="add",
                    status_before=project["status"],
                    status_after=project["status"],
                    summary="Existing project returned.",
                    payload={"created": False},
                )
                connection.commit()
                return {"created": False, "project": self.get_project(project["id"], connection=connection)}

            cursor = connection.execute(
                """
                INSERT INTO projects (
                    title, description, status, slug, project_dir, cdc_path, tasks_path,
                    readme_path, provider_name, validation_report, created_at, updated_at
                )
                VALUES (?, ?, 'idea', ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?)
                """,
                (title, description, slug, self.provider.name, now, now),
            )
            project_id = int(cursor.lastrowid)
            self._record_run(
                connection,
                project_id=project_id,
                action="add",
                status_before=None,
                status_after="idea",
                summary="Project added to queue.",
                payload={"created": True},
            )
            connection.commit()
            return {"created": True, "project": self.get_project(project_id, connection=connection)}

    def list_projects(self) -> dict[str, Any]:
        return self.snapshot(last_operation={"action": "list"})

    def design_project(self, project_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            project = self.get_project(project_id, connection=connection)
            status_before = project["status"]
            design = self.provider.design_project(title=project["title"], description=project["description"])
            project_dir = self.projects_root / f"{project_id:04d}-{project['slug']}"
            project_dir.mkdir(parents=True, exist_ok=True)
            cdc_path = project_dir / "CDC.md"
            tasks_path = project_dir / "TASKS.md"
            readme_path = project_dir / "README.md"
            write_text(cdc_path, _render_project_cdc(project, design))
            write_text(tasks_path, _render_project_tasks(project, design))
            write_text(readme_path, _render_project_readme(project, design))
            now = utc_ts()
            connection.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            for position, task in enumerate(design["tasks"], start=1):
                connection.execute(
                    """
                    INSERT INTO tasks (
                        project_id, title, description, status, position, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 'queued', ?, ?, ?)
                    """,
                    (project_id, task["title"], task["description"], position, now, now),
                )
            connection.execute(
                """
                UPDATE projects
                SET status = 'designing',
                    project_dir = ?,
                    cdc_path = ?,
                    tasks_path = ?,
                    readme_path = ?,
                    provider_name = ?,
                    validation_report = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    str(project_dir),
                    str(cdc_path),
                    str(tasks_path),
                    str(readme_path),
                    design["provider"],
                    now,
                    project_id,
                ),
            )
            self._record_run(
                connection,
                project_id=project_id,
                action="design",
                status_before=status_before,
                status_after="designing",
                summary="Project CDC, README and task list generated.",
                payload={"design": design, "project_dir": str(project_dir)},
            )
            connection.commit()
            return {"project": self.get_project(project_id, connection=connection), "design": design}

    def validate_project(self, project_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            project = self.get_project(project_id, connection=connection)
            status_before = project["status"]
            tasks = self.get_tasks(project_id, connection=connection)
            missing = [
                label
                for label, path in [
                    ("project_dir", project.get("project_dir")),
                    ("CDC.md", project.get("cdc_path")),
                    ("TASKS.md", project.get("tasks_path")),
                    ("README.md", project.get("readme_path")),
                ]
                if not path or not Path(path).exists()
            ]
            checks = {
                "has_project_dir": bool(project.get("project_dir")) and Path(project["project_dir"]).exists(),
                "has_cdc": bool(project.get("cdc_path")) and Path(project["cdc_path"]).exists(),
                "has_tasks_file": bool(project.get("tasks_path")) and Path(project["tasks_path"]).exists(),
                "has_readme": bool(project.get("readme_path")) and Path(project["readme_path"]).exists(),
                "task_count": len(tasks),
                "missing": missing,
            }
            next_status = "valid" if not missing and tasks else "blocked"
            validation_report = "PASS" if next_status == "valid" else "BLOCKED"
            now = utc_ts()
            connection.execute(
                "UPDATE projects SET status = ?, validation_report = ?, updated_at = ? WHERE id = ?",
                (next_status, validation_report, now, project_id),
            )
            self._record_run(
                connection,
                project_id=project_id,
                action="validate",
                status_before=status_before,
                status_after=next_status,
                summary=f"Validation {validation_report}.",
                payload={"checks": checks},
            )
            connection.commit()
            return {
                "project": self.get_project(project_id, connection=connection),
                "checks": checks,
                "valid": next_status == "valid",
            }

    def run_next(self) -> dict[str, Any]:
        with self.connect() as connection:
            project = self._next_project(connection)
            if project is None:
                self._record_run(
                    connection,
                    project_id=None,
                    action="run-next",
                    status_before=None,
                    status_after=None,
                    summary="No runnable project in queue.",
                    payload={},
                )
                connection.commit()
                return {"project": None, "action_taken": "none"}
            project_id = int(project["id"])
            if project["status"] == "idea":
                result = self.design_project(project_id)
                return {"project": result["project"], "action_taken": "design"}
            if project["status"] == "designing":
                result = self.validate_project(project_id)
                return {"project": result["project"], "action_taken": "validate"}

            status_before = project["status"]
            now = utc_ts()
            next_task = connection.execute(
                """
                SELECT * FROM tasks
                WHERE project_id = ? AND status IN ('queued', 'todo')
                ORDER BY position ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if next_task is not None:
                connection.execute(
                    "UPDATE tasks SET status = 'doing', updated_at = ? WHERE id = ?",
                    (now, int(next_task["id"])),
                )
            connection.execute(
                "UPDATE projects SET status = 'building', updated_at = ? WHERE id = ?",
                (now, project_id),
            )
            self._record_run(
                connection,
                project_id=project_id,
                action="run-next",
                status_before=status_before,
                status_after="building",
                summary="Project moved to building and next task activated.",
                payload={"task_id": int(next_task["id"]) if next_task is not None else None},
            )
            connection.commit()
            return {"project": self.get_project(project_id, connection=connection), "action_taken": "building"}

    def run_loop(
        self,
        *,
        max_steps: int,
        review_required: bool = False,
        use_context_pack: bool = False,
    ) -> dict[str, Any]:
        steps = []
        for _ in range(max(1, max_steps)):
            step = self._run_execution_step(review_required=review_required, use_context_pack=use_context_pack)
            steps.append(step)
            if step["action_taken"] in {"none", "project_done", "project_blocked", "pending_review", "patch_proposed"}:
                break
        snapshot = self.snapshot(
            last_operation={
                "action": "run-loop",
                "max_steps": max_steps,
                "provider_mode": self.provider.name,
                "review_required": review_required,
                "use_context_pack": use_context_pack,
            }
        )
        return {
            "id": "PROJECT-EXECUTION-LOOP-0001",
            "schema_version": "project-execution-loop-v1",
            "steps": steps,
            "snapshot": snapshot,
            "metrics": _execution_loop_metrics(snapshot, steps),
            "created_at": utc_ts(),
        }

    def project_status(self, project_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            project = self.get_project(project_id, connection=connection)
            executions = self.get_task_executions(project_id, connection=connection)
        return {
            "project": project,
            "task_executions": executions,
            "metrics": {
                "task_count": len(project["tasks"]),
                "execution_count": len(executions),
                "done_task_count": sum(1 for task in project["tasks"] if task["status"] == "done"),
                "failed_task_count": sum(1 for task in project["tasks"] if task["status"] == "failed"),
            },
        }

    def build_context_pack(self, project_id: int, task_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            project = self.get_project(project_id, connection=connection)
            task = self._get_task(task_id, connection=connection)
            if int(task["project_id"]) != project_id:
                raise ValueError(f"Task {task_id} does not belong to project {project_id}")
            context_pack = self.context_builder.build(project=project, task=task)
            provider_prompt = self.context_builder.provider_prompt(
                project=project,
                task=task,
                context_pack=context_pack,
            )
            self._store_context_pack(
                connection,
                project=project,
                task=task,
                execution_id=None,
                context_pack=context_pack,
                provider_prompt=provider_prompt,
            )
            connection.commit()
        return {
            "id": "CONTEXT-PACK-PROVIDER-PROMPTING-0001",
            "schema_version": "context-pack-provider-prompting-v1",
            "project": {"id": project["id"], "title": project["title"]},
            "task": {"id": task["id"], "title": task["title"]},
            "context_pack": context_pack,
            "provider_prompt": provider_prompt,
            "metrics": _context_pack_metrics([context_pack]),
            "created_at": utc_ts(),
        }

    def context_snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            packs = [
                _decode_context_pack(_row_to_dict(row))
                for row in connection.execute("SELECT * FROM task_context_packs ORDER BY id ASC")
            ]
        context_packs = [pack["context_pack"] for pack in packs]
        return {
            "id": "CONTEXT-PACK-PROVIDER-PROMPTING-0001",
            "schema_version": "context-pack-provider-prompting-v1",
            "context_packs": packs,
            "metrics": _context_pack_metrics(context_packs),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def list_patches(self, *, status: str | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            patches = self.get_patches(connection=connection, status=status)
        return {
            "id": "PATCH-PROPOSAL-APPLY-GATE-0001",
            "schema_version": "patch-proposal-apply-gate-v1",
            "patches": patches,
            "metrics": _patch_metrics(patches),
            "created_at": utc_ts(),
        }

    def show_patch(self, patch_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            proposal = self._get_patch(patch_id, connection=connection)
        return {
            "id": "PATCH-PROPOSAL-APPLY-GATE-0001",
            "schema_version": "patch-proposal-apply-gate-v1",
            "patch": proposal,
            "created_at": utc_ts(),
        }

    def apply_patch_proposal(self, patch_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            proposal = self._get_patch(patch_id, connection=connection)
            if proposal["status"] not in {"proposed", "approved"}:
                return {"patch": proposal, "applied": False, "reason": "patch_not_applicable"}
            applied = self._apply_patch_proposal_locked(connection, proposal)
            next_status = applied["patch"]["status"]
            tasks = self.get_tasks(int(proposal["project_id"]), connection=connection)
            if next_status == "applied" and tasks and all(task["status"] == "done" for task in tasks):
                self._complete_project_if_ready(connection, int(proposal["project_id"]))
            connection.commit()
            return {
                "patch": applied["patch"],
                "applied": applied["applied"],
                "apply_result": applied["apply_result"],
            }

    def reject_patch_proposal(self, patch_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            proposal = self._get_patch(patch_id, connection=connection)
            if proposal["status"] == "rejected":
                return {"patch": proposal, "rejected": False, "reason": "already_rejected"}
            now = utc_ts()
            connection.execute(
                "UPDATE patch_proposals SET status = 'rejected', updated_at = ? WHERE id = ?",
                (now, patch_id),
            )
            self._record_run(
                connection,
                project_id=int(proposal["project_id"]),
                action="patch-reject",
                status_before=proposal["status"],
                status_after="rejected",
                summary=f"Patch {patch_id} rejected.",
                payload={"patch_id": patch_id},
            )
            connection.commit()
            return {"patch": self._get_patch(patch_id, connection=connection), "rejected": True}

    def patch_snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            patches = self.get_patches(connection=connection, status=None)
        return {
            "id": "PATCH-PROPOSAL-APPLY-GATE-0001",
            "schema_version": "patch-proposal-apply-gate-v1",
            "patches": patches,
            "metrics": _patch_metrics(patches),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def validate_patch(self, patch_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            proposal = self._get_patch(patch_id, connection=connection)
            if proposal["status"] not in {"applied", "failed_validation"}:
                return {
                    "patch": proposal,
                    "validated": False,
                    "reason": "patch_not_applied",
                    "latest_plan": self._latest_validation_plan(patch_id, connection=connection),
                }
            result = self._run_patch_validation_locked(
                connection,
                proposal=proposal,
                update_entities=True,
            )
            connection.commit()
            return result

    def list_validations(self) -> dict[str, Any]:
        with self.connect() as connection:
            plans = self.get_validation_plans(connection=connection)
            runs = self.get_validation_runs(connection=connection)
        return {
            "id": "POST-PATCH-VALIDATION-LOOP-0001",
            "schema_version": "post-patch-validation-loop-v1",
            "plans": plans,
            "runs": runs,
            "metrics": _validation_metrics(plans, runs),
            "created_at": utc_ts(),
        }

    def list_failures(self, *, status: str | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            failures = self.get_failures(connection=connection, status=status)
        return {
            "id": "FAILURE-RECOVERY-RETRY-LOOP-0001",
            "schema_version": "failure-recovery-retry-loop-v1",
            "failures": failures,
            "retry_policy": _retry_policy_snapshot(self.retry_policy),
            "metrics": _failure_metrics(failures),
            "created_at": utc_ts(),
        }

    def show_failure(self, failure_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            failure = self._get_failure(failure_id, connection=connection)
        return {
            "id": "FAILURE-RECOVERY-RETRY-LOOP-0001",
            "schema_version": "failure-recovery-retry-loop-v1",
            "failure": failure,
            "retry_policy": _retry_policy_snapshot(self.retry_policy),
            "created_at": utc_ts(),
        }

    def retry_failure(self, failure_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            failure = self._get_failure(failure_id, connection=connection)
            if failure["status"] == "resolved":
                return {"failure": failure, "retried": False, "reason": "failure_already_resolved"}
            if failure["retry_task_id"] is not None:
                task = self._get_task(int(failure["retry_task_id"]), connection=connection)
                connection.execute(
                    "UPDATE failure_records SET status = 'retrying', updated_at = ? WHERE id = ?",
                    (utc_ts(), failure_id),
                )
                connection.execute(
                    "UPDATE projects SET status = 'building', updated_at = ? WHERE id = ?",
                    (utc_ts(), int(failure["project_id"])),
                )
                self._record_run(
                    connection,
                    project_id=int(failure["project_id"]),
                    action="failure-retry",
                    status_before=failure["status"],
                    status_after="retrying",
                    summary=f"Retry task {task['id']} queued for failure {failure_id}.",
                    payload={"failure_id": failure_id, "retry_task_id": int(task["id"])},
                )
                connection.commit()
                return {
                    "failure": self._get_failure(failure_id, connection=connection),
                    "retry_task": task,
                    "retried": True,
                    "reused_existing_task": True,
                }
            retry = self._create_retry_task_for_failure_locked(connection, failure=failure)
            connection.commit()
            return retry

    def failure_snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            failures = self.get_failures(connection=connection, status=None)
        return {
            "id": "FAILURE-RECOVERY-RETRY-LOOP-0001",
            "schema_version": "failure-recovery-retry-loop-v1",
            "failures": failures,
            "retry_policy": _retry_policy_snapshot(self.retry_policy),
            "metrics": _failure_metrics(failures),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def validation_snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            plans = self.get_validation_plans(connection=connection)
            runs = self.get_validation_runs(connection=connection)
        return {
            "id": "POST-PATCH-VALIDATION-LOOP-0001",
            "schema_version": "post-patch-validation-loop-v1",
            "plans": plans,
            "runs": runs,
            "metrics": _validation_metrics(plans, runs),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def list_reviews(self, *, status: str | None = "pending_review") -> dict[str, Any]:
        with self.connect() as connection:
            reviews = self.get_reviews(connection=connection, status=status)
        return {
            "id": "PROJECT-REVIEW-QUEUE-0001",
            "schema_version": "project-review-queue-v1",
            "reviews": reviews,
            "metrics": _review_metrics(reviews),
            "created_at": utc_ts(),
        }

    def accept_review(self, review_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            review = self._get_review(review_id, connection=connection)
            if review["status"] != "pending_review":
                return {"review": review, "applied": False, "reason": "review_not_pending"}
            provider_result = review["provider_response"]
            guard_report = review["guard_report"]
            project = self.get_project(int(review["project_id"]), connection=connection)
            task = _row_to_dict(
                connection.execute("SELECT * FROM tasks WHERE id = ?", (int(review["task_id"]),)).fetchone()
            )
            changed_files = self._apply_safe_changes(guard_report.get("safe_changes", []))
            artifact_paths = self._write_execution_artifacts(
                project=project,
                task=task,
                execution_id=int(review["execution_id"]),
                provider_result=provider_result,
            )
            now = utc_ts()
            connection.execute(
                """
                UPDATE task_executions
                SET status = 'done',
                    output_summary = ?,
                    changed_files = ?,
                    artifacts = ?,
                    validation_status = 'passed',
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    provider_result.get("output_summary", ""),
                    json.dumps(changed_files, sort_keys=True, ensure_ascii=False),
                    json.dumps(artifact_paths, sort_keys=True, ensure_ascii=False),
                    now,
                    int(review["execution_id"]),
                ),
            )
            connection.execute(
                "UPDATE tasks SET status = 'done', updated_at = ? WHERE id = ?",
                (now, int(review["task_id"])),
            )
            connection.execute(
                "UPDATE review_queue SET status = 'accepted', reviewed_at = ? WHERE id = ?",
                (now, review_id),
            )
            self._record_run(
                connection,
                project_id=int(review["project_id"]),
                action="review-accept",
                status_before="pending_review",
                status_after="done",
                summary=f"Review {review_id} accepted and applied.",
                payload={"review_id": review_id, "changed_files": changed_files, "artifacts": artifact_paths},
            )
            tasks = self.get_tasks(int(review["project_id"]), connection=connection)
            if tasks and all(task["status"] == "done" for task in tasks):
                self._complete_project_if_ready(connection, int(review["project_id"]))
            connection.commit()
            return {
                "review": self._get_review(review_id, connection=connection),
                "applied": True,
                "changed_files": changed_files,
                "artifacts": artifact_paths,
            }

    def reject_review(self, review_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            review = self._get_review(review_id, connection=connection)
            if review["status"] != "pending_review":
                return {"review": review, "rejected": False, "reason": "review_not_pending"}
            now = utc_ts()
            connection.execute(
                """
                UPDATE task_executions
                SET status = 'failed',
                    validation_status = 'rejected',
                    output_summary = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (f"Review {review_id} rejected; provider output was not applied.", now, int(review["execution_id"])),
            )
            connection.execute(
                "UPDATE tasks SET status = 'blocked', updated_at = ? WHERE id = ?",
                (now, int(review["task_id"])),
            )
            connection.execute(
                "UPDATE projects SET status = 'blocked', validation_report = 'REJECTED', updated_at = ? WHERE id = ?",
                (now, int(review["project_id"])),
            )
            connection.execute(
                "UPDATE review_queue SET status = 'rejected', reviewed_at = ? WHERE id = ?",
                (now, review_id),
            )
            self._record_run(
                connection,
                project_id=int(review["project_id"]),
                action="review-reject",
                status_before="pending_review",
                status_after="rejected",
                summary=f"Review {review_id} rejected.",
                payload={"review_id": review_id},
            )
            connection.commit()
            return {"review": self._get_review(review_id, connection=connection), "rejected": True}

    def guard_snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            reviews = self.get_reviews(connection=connection, status=None)
            logs = [
                _decode_guard_log(_row_to_dict(row))
                for row in connection.execute("SELECT * FROM execution_guard_logs ORDER BY id ASC")
            ]
        return {
            "id": "REAL-PROVIDER-EXECUTION-GUARD-0001",
            "schema_version": "real-provider-execution-guard-v1",
            "provider_mode": self.provider.name,
            "provider_available": self.provider.available(),
            "review_required_for_real_providers": True,
            "guard": {
                "max_changed_files": self.guard.max_changed_files,
                "max_output_tokens": self.guard.max_output_tokens,
                "dangerous_patterns": DANGEROUS_COMMAND_PATTERNS,
            },
            "reviews": reviews,
            "guard_logs": logs,
            "metrics": _guard_metrics(reviews, logs),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def get_project(self, project_id: int, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        close = connection is None
        connection = connection or self.connect()
        try:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise ValueError(f"Project {project_id} not found")
            project = _row_to_dict(row)
            project["tasks"] = self.get_tasks(project_id, connection=connection)
            return project
        finally:
            if close:
                connection.close()

    def get_tasks(self, project_id: int, *, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY position ASC",
            (project_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def _get_task(self, task_id: int, *, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Task {task_id} not found")
        return _row_to_dict(row)

    def get_task_executions(
        self,
        project_id: int,
        *,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM task_executions WHERE project_id = ? ORDER BY id ASC",
            (project_id,),
        ).fetchall()
        return [_decode_execution(_row_to_dict(row)) for row in rows]

    def get_reviews(
        self,
        *,
        connection: sqlite3.Connection,
        status: str | None = "pending_review",
    ) -> list[dict[str, Any]]:
        if status is None:
            rows = connection.execute("SELECT * FROM review_queue ORDER BY id ASC").fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM review_queue WHERE status = ? ORDER BY id ASC",
                (status,),
            ).fetchall()
        return [_decode_review(_row_to_dict(row)) for row in rows]

    def get_patches(
        self,
        *,
        connection: sqlite3.Connection,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is None:
            rows = connection.execute("SELECT * FROM patch_proposals ORDER BY id ASC").fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM patch_proposals WHERE status = ? ORDER BY id ASC",
                (status,),
            ).fetchall()
        return [_decode_patch(_row_to_dict(row)) for row in rows]

    def get_validation_plans(self, *, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute("SELECT * FROM validation_plans ORDER BY id ASC").fetchall()
        return [_decode_validation_plan(_row_to_dict(row)) for row in rows]

    def get_validation_runs(self, *, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute("SELECT * FROM validation_runs ORDER BY id ASC").fetchall()
        return [_decode_validation_run(_row_to_dict(row)) for row in rows]

    def get_failures(
        self,
        *,
        connection: sqlite3.Connection,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is None:
            rows = connection.execute("SELECT * FROM failure_records ORDER BY id ASC").fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM failure_records WHERE status = ? ORDER BY id ASC",
                (status,),
            ).fetchall()
        return [_decode_failure(_row_to_dict(row)) for row in rows]

    def snapshot(self, *, last_operation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            projects = [_row_to_dict(row) for row in connection.execute("SELECT * FROM projects ORDER BY id ASC")]
            tasks = [_row_to_dict(row) for row in connection.execute("SELECT * FROM tasks ORDER BY project_id, position")]
            runs = [_row_to_dict(row) for row in connection.execute("SELECT * FROM runs ORDER BY id ASC")]
            task_executions = [
                _decode_execution(_row_to_dict(row))
                for row in connection.execute("SELECT * FROM task_executions ORDER BY id ASC")
            ]
        return {
            "id": "PROJECT-QUEUE-ORCHESTRATOR-0001",
            "schema_version": PROJECT_QUEUE_SCHEMA_VERSION,
            "provider": {
                "name": self.provider.name,
                "available": self.provider.available(),
                "nvidia_api_key_present": bool(os.environ.get("NVIDIA_API_KEY")),
            },
            "projects": projects,
            "tasks": tasks,
            "runs": runs,
            "task_executions": task_executions,
            "metrics": _project_queue_metrics(projects, tasks, runs, task_executions),
            "last_operation": last_operation or {},
            "created_at": utc_ts(),
        }

    def _next_project(self, connection: sqlite3.Connection) -> dict[str, Any] | None:
        for status in ["valid", "designing", "idea"]:
            row = connection.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY id ASC LIMIT 1",
                (status,),
            ).fetchone()
            if row is not None:
                return _row_to_dict(row)
        return None

    def _next_execution_project(self, connection: sqlite3.Connection) -> dict[str, Any] | None:
        for status in ["building", "valid"]:
            row = connection.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY id ASC LIMIT 1",
                (status,),
            ).fetchone()
            if row is not None:
                return _row_to_dict(row)
        return None

    def _run_execution_step(
        self,
        *,
        review_required: bool = False,
        use_context_pack: bool = False,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            project = self._next_execution_project(connection)
            if project is None:
                self._record_run(
                    connection,
                    project_id=None,
                    action="run-loop",
                    status_before=None,
                    status_after=None,
                    summary="No valid or building project available for execution.",
                    payload={},
                )
                connection.commit()
                return {"action_taken": "none", "project": None, "execution": None}

            project_id = int(project["id"])
            if project["status"] == "valid":
                connection.execute(
                    "UPDATE projects SET status = 'building', updated_at = ? WHERE id = ?",
                    (utc_ts(), project_id),
                )
                project = self.get_project(project_id, connection=connection)

            pending_patch = connection.execute(
                """
                SELECT * FROM patch_proposals
                WHERE project_id = ? AND status = 'proposed'
                ORDER BY id ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if pending_patch is not None:
                self._record_run(
                    connection,
                    project_id=project_id,
                    action="run-loop",
                    status_before=project["status"],
                    status_after=project["status"],
                    summary=f"Project is waiting for patch proposal {pending_patch['id']} review.",
                    payload={"patch_id": int(pending_patch["id"])},
                )
                return {
                    "action_taken": "patch_proposed",
                    "project": self.get_project(project_id, connection=connection),
                    "execution": None,
                    "patch": _decode_patch(_row_to_dict(pending_patch)),
                }

            next_task = connection.execute(
                """
                SELECT * FROM tasks
                WHERE project_id = ? AND status IN ('queued', 'todo')
                ORDER BY position ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if next_task is None:
                return self._complete_project_if_ready(connection, project_id)

            task = _row_to_dict(next_task)
            execution = self._execute_task(
                connection,
                project,
                task,
                review_required=review_required,
                use_context_pack=use_context_pack,
            )
            connection.commit()
            if execution["validation_status"] == "pending_review":
                action_taken = "pending_review"
            elif execution["validation_status"] == "patch_proposed":
                action_taken = "patch_proposed"
            else:
                action_taken = "task_executed"
            return {
                "action_taken": action_taken,
                "project": self.get_project(project_id, connection=connection),
                "execution": execution,
            }

    def _execute_task(
        self,
        connection: sqlite3.Connection,
        project: dict[str, Any],
        task: dict[str, Any],
        *,
        review_required: bool = False,
        use_context_pack: bool = False,
    ) -> dict[str, Any]:
        project_id = int(project["id"])
        task_id = int(task["id"])
        effective_review_required = review_required or _task_requires_review(task)
        input_prompt = _execution_prompt(project, task)
        context_pack: dict[str, Any] | None = None
        provider_prompt: dict[str, Any] | None = None
        if use_context_pack:
            context_pack = self.context_builder.build(project=project, task=task)
            provider_prompt = self.context_builder.provider_prompt(
                project=project,
                task=task,
                context_pack=context_pack,
            )
            input_prompt = _render_provider_prompt(provider_prompt)
        started_at = utc_ts()
        cursor = connection.execute(
            """
            INSERT INTO task_executions (
                project_id, task_id, status, input_prompt, output_summary, changed_files,
                artifacts, validation_status, started_at, finished_at
            )
            VALUES (?, ?, 'queued', ?, '', '[]', '[]', 'pending', NULL, NULL)
            """,
            (project_id, task_id, input_prompt),
        )
        execution_id = int(cursor.lastrowid)
        if context_pack is not None and provider_prompt is not None:
            self._store_context_pack(
                connection,
                project=project,
                task=task,
                execution_id=execution_id,
                context_pack=context_pack,
                provider_prompt=provider_prompt,
            )
            if context_pack["evidence_score"] < self.context_builder.min_evidence_score:
                output_summary = (
                    "Execution refused: context pack evidence_score "
                    f"{context_pack['evidence_score']} is below "
                    f"{self.context_builder.min_evidence_score}."
                )
                finished_at = utc_ts()
                connection.execute(
                    """
                    UPDATE task_executions
                    SET status = 'blocked',
                        output_summary = ?,
                        changed_files = '[]',
                        artifacts = '[]',
                        validation_status = 'low_evidence',
                        started_at = ?,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (output_summary, started_at, finished_at, execution_id),
                )
                connection.execute(
                    "UPDATE tasks SET status = 'blocked', updated_at = ? WHERE id = ?",
                    (finished_at, task_id),
                )
                connection.execute(
                    "UPDATE projects SET status = 'blocked', validation_report = 'LOW_EVIDENCE', updated_at = ? WHERE id = ?",
                    (finished_at, project_id),
                )
                self._record_run(
                    connection,
                    project_id=project_id,
                    action="context-pack-refused",
                    status_before="building",
                    status_after="blocked",
                    summary=output_summary,
                    payload={"task_id": task_id, "execution_id": execution_id, "context_pack": context_pack},
                )
                execution = connection.execute("SELECT * FROM task_executions WHERE id = ?", (execution_id,)).fetchone()
                return _decode_execution(_row_to_dict(execution))
        connection.execute(
            "UPDATE task_executions SET status = 'doing', started_at = ? WHERE id = ?",
            (started_at, execution_id),
        )
        connection.execute(
            "UPDATE tasks SET status = 'doing', updated_at = ? WHERE id = ?",
            (started_at, task_id),
        )
        try:
            provider_result = self.provider.execute_task(project=project, task=task, input_prompt=input_prompt)
            guard_report = self.guard.validate(project=project, provider_result=provider_result)
            self._journal_provider_exchange(
                connection,
                execution_id=execution_id,
                project_id=project_id,
                task_id=task_id,
                input_prompt=input_prompt,
                provider_result=provider_result,
                guard_report=guard_report,
            )
            patch_text = _provider_patch_text(provider_result)
            if guard_report["status"] == "blocked":
                status = "blocked"
                validation_status = "blocked"
                output_summary = "Execution blocked by guard: " + ", ".join(guard_report["violations"])
                changed_files = []
                artifact_paths = []
            elif patch_text:
                proposal = self._create_patch_proposal(
                    connection,
                    project=project,
                    task=task,
                    execution_id=execution_id,
                    provider_result=provider_result,
                    patch_text=patch_text,
                )
                artifact_paths = _patch_artifact_paths(proposal)
                if proposal["status"] == "failed":
                    status = "blocked"
                    validation_status = "patch_failed"
                    output_summary = proposal["patch_report"]
                    changed_files = []
                else:
                    requires_review = (
                        effective_review_required
                        or self.provider.name in REAL_PROVIDER_MODES
                        or bool(provider_result.get("review_required"))
                        or proposal["risk_level"] != "low"
                    )
                    if requires_review:
                        status = "blocked"
                        validation_status = "patch_proposed"
                        output_summary = f"Patch proposal {proposal['id']} is waiting for ApplyGate review."
                        changed_files = []
                    else:
                        applied = self._apply_patch_proposal_locked(connection, proposal)
                        apply_result = applied["apply_result"]
                        status = "done" if applied["applied"] else "blocked"
                        validation_status = (
                            "passed"
                            if applied["applied"]
                            else (
                                "failed_validation"
                                if applied["patch"]["status"] == "failed_validation"
                                else "patch_failed"
                            )
                        )
                        output_summary = (
                            provider_result.get("output_summary", "")
                            + f" Patch proposal {proposal['id']} "
                            + ("applied." if applied["applied"] else "failed.")
                        ).strip()
                        changed_files = apply_result["changed_files"]
                        run_artifacts = self._write_execution_artifacts(
                            project=project,
                            task=task,
                            execution_id=execution_id,
                            provider_result=provider_result,
                        )
                        artifact_paths = run_artifacts + applied["artifacts"]
            elif provider_result.get("dry_run") or self.provider.name == "dry_run":
                status = "done"
                validation_status = provider_result.get("validation_status", "passed")
                output_summary = provider_result.get("output_summary", "")
                changed_files = []
                artifact_paths = []
            elif effective_review_required or self.provider.name in REAL_PROVIDER_MODES or provider_result.get("review_required"):
                review_id = self._queue_review(
                    connection,
                    project_id=project_id,
                    task_id=task_id,
                    execution_id=execution_id,
                    input_prompt=input_prompt,
                    provider_result=provider_result,
                    guard_report=guard_report,
                )
                status = "blocked"
                validation_status = "pending_review"
                output_summary = (
                    f"Provider output is pending manual review in review_queue item {review_id}."
                )
                changed_files = []
                artifact_paths = []
            else:
                status = provider_result.get("status", "done")
                if status not in {"done", "failed", "blocked"}:
                    status = "done"
                validation_status = provider_result.get(
                    "validation_status",
                    "passed" if status == "done" else "failed",
                )
                output_summary = provider_result.get("output_summary", "")
                changed_files = _changed_file_paths(guard_report["safe_changes"])
                self._apply_safe_changes(guard_report["safe_changes"])
                artifact_paths = self._write_execution_artifacts(
                    project=project,
                    task=task,
                    execution_id=execution_id,
                    provider_result=provider_result,
                )
        except Exception as exc:  # pragma: no cover - defensive guard for external providers.
            status = "failed"
            validation_status = "failed"
            output_summary = f"Execution failed: {exc}"
            changed_files = []
            artifact_paths = []

        finished_at = utc_ts()
        task_status = "done" if status == "done" and validation_status == "passed" else status
        connection.execute(
            """
            UPDATE task_executions
            SET status = ?,
                output_summary = ?,
                changed_files = ?,
                artifacts = ?,
                validation_status = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (
                task_status,
                output_summary,
                json.dumps(changed_files, sort_keys=True, ensure_ascii=False),
                json.dumps(artifact_paths, sort_keys=True, ensure_ascii=False),
                validation_status,
                finished_at,
                execution_id,
            ),
        )
        connection.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (task_status, finished_at, task_id),
        )
        if task_status in {"failed", "blocked"} and validation_status not in {
            "pending_review",
            "patch_proposed",
            "failed_validation",
        }:
            connection.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                (task_status, finished_at, project_id),
            )
        self._record_run(
            connection,
            project_id=project_id,
            action="execute-task",
            status_before="building",
            status_after=task_status,
            summary=output_summary,
            payload={"task_id": task_id, "execution_id": execution_id, "artifacts": artifact_paths},
        )
        execution = connection.execute("SELECT * FROM task_executions WHERE id = ?", (execution_id,)).fetchone()
        return _decode_execution(_row_to_dict(execution))

    def _write_execution_artifacts(
        self,
        *,
        project: dict[str, Any],
        task: dict[str, Any],
        execution_id: int,
        provider_result: dict[str, Any],
    ) -> list[str]:
        project_dir = Path(project["project_dir"])
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / f"run_{execution_id:04d}.md"
        artifacts = provider_result.get("artifacts", [])
        content = artifacts[0]["content"] if artifacts else provider_result.get("output_summary", "")
        write_text(artifact_path, content)
        runs_path = project_dir / "RUNS.md"
        previous = runs_path.read_text(encoding="utf-8") if runs_path.exists() else f"# RUNS - {project['title']}\n"
        run_entry = "\n".join(
            [
                "",
                f"## Run {execution_id:04d} - {task['title']}",
                "",
                f"- Status: {provider_result.get('status', 'done')}",
                f"- Validation: {provider_result.get('validation_status', 'passed')}",
                f"- Artifact: artifacts/run_{execution_id:04d}.md",
                f"- Summary: {provider_result.get('output_summary', '')}",
                "",
            ]
        )
        write_text(runs_path, previous.rstrip() + "\n" + run_entry)
        return [str(artifact_path), str(runs_path)]

    def _apply_safe_changes(self, safe_changes: list[dict[str, Any]]) -> list[str]:
        changed_files: list[str] = []
        for change in safe_changes:
            target = Path(change["resolved_path"])
            operation = change.get("operation", "write")
            if operation == "delete":
                if target.exists() and target.is_file():
                    target.unlink()
                changed_files.append(str(target))
                continue
            if operation == "append" and target.exists():
                previous = target.read_text(encoding="utf-8")
                write_text(target, previous + str(change.get("content", "")))
            else:
                write_text(target, str(change.get("content", "")))
            changed_files.append(str(target))
        return changed_files

    def _queue_review(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: int,
        task_id: int,
        execution_id: int,
        input_prompt: str,
        provider_result: dict[str, Any],
        guard_report: dict[str, Any],
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO review_queue (
                project_id, task_id, execution_id, provider_mode, status, input_prompt,
                provider_response, guard_report, proposed_changes, created_at, reviewed_at
            )
            VALUES (?, ?, ?, ?, 'pending_review', ?, ?, ?, ?, ?, NULL)
            """,
            (
                project_id,
                task_id,
                execution_id,
                self.provider.name,
                input_prompt,
                json.dumps(provider_result, sort_keys=True, ensure_ascii=False),
                json.dumps(guard_report, sort_keys=True, ensure_ascii=False),
                json.dumps(guard_report.get("safe_changes", []), sort_keys=True, ensure_ascii=False),
                utc_ts(),
            ),
        )
        return int(cursor.lastrowid)

    def _journal_provider_exchange(
        self,
        connection: sqlite3.Connection,
        *,
        execution_id: int,
        project_id: int,
        task_id: int,
        input_prompt: str,
        provider_result: dict[str, Any],
        guard_report: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO execution_guard_logs (
                execution_id, project_id, task_id, provider_mode, input_prompt,
                provider_response, guard_report, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                project_id,
                task_id,
                self.provider.name,
                input_prompt,
                json.dumps(provider_result, sort_keys=True, ensure_ascii=False),
                json.dumps(guard_report, sort_keys=True, ensure_ascii=False),
                utc_ts(),
            ),
        )

    def _store_context_pack(
        self,
        connection: sqlite3.Connection,
        *,
        project: dict[str, Any],
        task: dict[str, Any],
        execution_id: int | None,
        context_pack: dict[str, Any],
        provider_prompt: dict[str, Any],
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO task_context_packs (
                project_id, task_id, execution_id, token_budget, evidence_score,
                relative_resolution_cost, context_pack, provider_prompt, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project["id"]),
                int(task["id"]),
                execution_id,
                int(context_pack["token_budget"]),
                float(context_pack["evidence_score"]),
                float(context_pack["relative_resolution_cost"]),
                json.dumps(context_pack, sort_keys=True, ensure_ascii=False),
                json.dumps(provider_prompt, sort_keys=True, ensure_ascii=False),
                utc_ts(),
            ),
        )
        self._write_context_pack_log(project=project, task=task, context_pack=context_pack)
        return int(cursor.lastrowid)

    def _write_context_pack_log(
        self,
        *,
        project: dict[str, Any],
        task: dict[str, Any],
        context_pack: dict[str, Any],
    ) -> None:
        project_dir = Path(project["project_dir"])
        packs_path = project_dir / "CONTEXT_PACKS.md"
        previous = (
            packs_path.read_text(encoding="utf-8")
            if packs_path.exists()
            else f"# CONTEXT_PACKS - {project['title']}\n"
        )
        lines = [
            "",
            f"## Task {task['id']} - {task['title']}",
            "",
            f"- Evidence score: {context_pack['evidence_score']}",
            f"- Relative cost: {context_pack['relative_resolution_cost']}",
            f"- Token budget: {context_pack['token_budget']}",
            f"- Materialized tokens: {context_pack['materialized_tokens']}",
            f"- Selected files: {', '.join(context_pack['selected_files'])}",
            "",
            "### Source refs",
            "",
        ]
        lines.extend(f"- `{source}`" for source in context_pack["source_refs"])
        lines.extend(
            [
                "",
                "### Excluded",
                "",
                context_pack["excluded_summary"],
                "",
            ]
        )
        write_text(packs_path, previous.rstrip() + "\n" + "\n".join(lines))

    def _create_patch_proposal(
        self,
        connection: sqlite3.Connection,
        *,
        project: dict[str, Any],
        task: dict[str, Any],
        execution_id: int,
        provider_result: dict[str, Any],
        patch_text: str,
    ) -> dict[str, Any]:
        now = utc_ts()
        summary = str(provider_result.get("output_summary", "Patch proposal generated by provider."))
        try:
            parsed = self.patch_parser.parse(project=project, patch_text=patch_text)
            target_files = parsed["target_files"]
            parsed_changes = parsed["changes"]
            risk_level = parsed["risk_level"]
            status = "proposed"
            patch_report = (
                f"Patch proposal accepted for ApplyGate review. "
                f"Files: {len(target_files)}. Risk: {risk_level}."
            )
        except ValueError as exc:
            target_files = []
            parsed_changes = []
            risk_level = "high"
            status = "failed"
            patch_report = f"PatchParser refused patch: {exc}"
        cursor = connection.execute(
            """
            INSERT INTO patch_proposals (
                project_id, task_id, execution_id, provider_mode, target_files,
                diff_text, summary, risk_level, status, parsed_changes,
                patch_report, diff_path, report_path, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                int(project["id"]),
                int(task["id"]),
                execution_id,
                self.provider.name,
                json.dumps(target_files, sort_keys=True, ensure_ascii=False),
                patch_text,
                summary,
                risk_level,
                status,
                json.dumps(parsed_changes, sort_keys=True, ensure_ascii=False),
                patch_report,
                now,
                now,
            ),
        )
        patch_id = int(cursor.lastrowid)
        proposal = self._get_patch(patch_id, connection=connection)
        report_paths = self._write_patch_files(
            connection,
            project=project,
            proposal=proposal,
            patch_report=patch_report,
        )
        connection.execute(
            """
            UPDATE patch_proposals
            SET diff_path = ?,
                report_path = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (report_paths["diff_path"], report_paths["report_path"], utc_ts(), patch_id),
        )
        return self._get_patch(patch_id, connection=connection)

    def _apply_patch_proposal_locked(
        self,
        connection: sqlite3.Connection,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        project = self.get_project(int(proposal["project_id"]), connection=connection)
        apply_result = ApplyGate(self.guard).apply(
            project=project,
            proposal=proposal,
            dry_run=proposal["provider_mode"] == "dry_run",
        )
        next_status = "applied" if apply_result["status"] == "applied" else "failed"
        now = utc_ts()
        validation_result: dict[str, Any] | None = None
        if next_status == "applied":
            validation_result = self._run_patch_validation_locked(
                connection,
                proposal={**proposal, "status": next_status},
                update_entities=False,
            )
            if not validation_result["passed"]:
                next_status = "failed_validation"
                apply_result["patch_report"] = (
                    apply_result["patch_report"]
                    + f" Post-patch validation failed in plan {validation_result['plan']['id']}."
                )
            else:
                apply_result["patch_report"] = (
                    apply_result["patch_report"]
                    + f" Post-patch validation passed in plan {validation_result['plan']['id']}."
                )
        report_paths = self._write_patch_files(
            connection,
            project=project,
            proposal={**proposal, "status": next_status},
            patch_report=apply_result["patch_report"],
        )
        connection.execute(
            """
            UPDATE patch_proposals
            SET status = ?,
                patch_report = ?,
                diff_path = ?,
                report_path = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                apply_result["patch_report"],
                report_paths["diff_path"],
                report_paths["report_path"],
                now,
                int(proposal["id"]),
            ),
        )
        if next_status == "applied":
            artifacts = [report_paths["diff_path"], report_paths["report_path"]]
            if validation_result is not None:
                artifacts.extend(validation_result["artifacts"])
            if proposal["execution_id"] is not None:
                connection.execute(
                    """
                    UPDATE task_executions
                    SET status = 'done',
                        validation_status = 'passed',
                        changed_files = ?,
                        artifacts = ?,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(apply_result["changed_files"], sort_keys=True, ensure_ascii=False),
                        json.dumps(artifacts, sort_keys=True, ensure_ascii=False),
                        now,
                        int(proposal["execution_id"]),
                    ),
                )
            connection.execute(
                "UPDATE tasks SET status = 'done', updated_at = ? WHERE id = ?",
                (now, int(proposal["task_id"])),
            )
        elif next_status == "failed_validation":
            artifacts = [report_paths["diff_path"], report_paths["report_path"]]
            if validation_result is not None:
                artifacts.extend(validation_result["artifacts"])
            if proposal["execution_id"] is not None:
                connection.execute(
                    """
                    UPDATE task_executions
                    SET status = 'blocked',
                        validation_status = 'failed_validation',
                        changed_files = ?,
                        artifacts = ?,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(apply_result["changed_files"], sort_keys=True, ensure_ascii=False),
                        json.dumps(artifacts, sort_keys=True, ensure_ascii=False),
                        now,
                        int(proposal["execution_id"]),
                    ),
                )
            connection.execute(
                "UPDATE tasks SET status = 'blocked', updated_at = ? WHERE id = ?",
                (now, int(proposal["task_id"])),
            )
            has_retry = bool(validation_result and validation_result.get("failure", {}).get("retry_task"))
            project_status = "building" if has_retry else "blocked"
            validation_report = "RETRY_QUEUED" if has_retry else "FAILED_VALIDATION"
            connection.execute(
                "UPDATE projects SET status = ?, validation_report = ?, updated_at = ? WHERE id = ?",
                (project_status, validation_report, now, int(proposal["project_id"])),
            )
        else:
            artifacts = [report_paths["diff_path"], report_paths["report_path"]]
        self._record_run(
            connection,
            project_id=int(proposal["project_id"]),
            action="patch-apply",
            status_before=proposal["status"],
            status_after=next_status,
            summary=apply_result["patch_report"],
            payload={
                "patch_id": int(proposal["id"]),
                "changed_files": apply_result["changed_files"],
                "validation_plan_id": validation_result["plan"]["id"] if validation_result else None,
            },
        )
        return {
            "patch": self._get_patch(int(proposal["id"]), connection=connection),
            "applied": next_status == "applied",
            "apply_result": apply_result,
            "validation": validation_result,
            "artifacts": artifacts,
        }

    def _run_patch_validation_locked(
        self,
        connection: sqlite3.Connection,
        *,
        proposal: dict[str, Any],
        update_entities: bool,
    ) -> dict[str, Any]:
        project = self.get_project(int(proposal["project_id"]), connection=connection)
        commands = list(DEFAULT_VALIDATION_COMMANDS)
        allowed_commands = list(DEFAULT_ALLOWED_VALIDATION_COMMANDS)
        max_runtime_sec = 30
        now = utc_ts()
        cursor = connection.execute(
            """
            INSERT INTO validation_plans (
                project_id, task_id, patch_id, commands, max_runtime_sec,
                allowed_commands, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
            """,
            (
                int(proposal["project_id"]),
                int(proposal["task_id"]),
                int(proposal["id"]),
                json.dumps(commands, sort_keys=True, ensure_ascii=False),
                max_runtime_sec,
                json.dumps(allowed_commands, sort_keys=True, ensure_ascii=False),
                now,
                now,
            ),
        )
        plan_id = int(cursor.lastrowid)
        runs: list[dict[str, Any]] = []
        for command in commands:
            run = self.command_runner.run(
                command=command,
                cwd=Path(project["project_dir"]),
                max_runtime_sec=max_runtime_sec,
                allowed_commands=allowed_commands,
            )
            connection.execute(
                """
                INSERT INTO validation_runs (
                    plan_id, command, exit_code, stdout_tail, stderr_tail,
                    duration_ms, passed, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    run["command"],
                    int(run["exit_code"]),
                    run["stdout_tail"],
                    run["stderr_tail"],
                    int(run["duration_ms"]),
                    1 if run["passed"] else 0,
                    utc_ts(),
                ),
            )
            runs.append(run)
        passed = all(run["passed"] for run in runs)
        status = "passed" if passed else "failed"
        connection.execute(
            "UPDATE validation_plans SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_ts(), plan_id),
        )
        plan = self._get_validation_plan(plan_id, connection=connection)
        persisted_runs = [
            _decode_validation_run(_row_to_dict(row))
            for row in connection.execute(
                "SELECT * FROM validation_runs WHERE plan_id = ? ORDER BY id ASC",
                (plan_id,),
            )
        ]
        artifacts = self._write_validation_files(project=project, plan=plan, runs=persisted_runs)
        failure_result: dict[str, Any] | None = None
        if passed:
            self._resolve_failures_for_patch_locked(connection, proposal=proposal)
        else:
            failure_result = self._record_failure_and_retry_locked(
                connection,
                proposal=proposal,
                plan=plan,
                runs=persisted_runs,
            )
        if update_entities:
            final_patch_status = "applied" if passed else "failed_validation"
            connection.execute(
                "UPDATE patch_proposals SET status = ?, updated_at = ? WHERE id = ?",
                (final_patch_status, utc_ts(), int(proposal["id"])),
            )
            if passed:
                if proposal["execution_id"] is not None:
                    connection.execute(
                        """
                        UPDATE task_executions
                        SET status = 'done',
                            validation_status = 'passed',
                            finished_at = ?
                        WHERE id = ?
                        """,
                        (utc_ts(), int(proposal["execution_id"])),
                    )
                connection.execute(
                    "UPDATE tasks SET status = 'done', updated_at = ? WHERE id = ?",
                    (utc_ts(), int(proposal["task_id"])),
                )
            else:
                if proposal["execution_id"] is not None:
                    connection.execute(
                        """
                        UPDATE task_executions
                        SET status = 'blocked',
                            validation_status = 'failed_validation',
                            finished_at = ?
                        WHERE id = ?
                        """,
                        (utc_ts(), int(proposal["execution_id"])),
                    )
                connection.execute(
                    "UPDATE tasks SET status = 'blocked', updated_at = ? WHERE id = ?",
                    (utc_ts(), int(proposal["task_id"])),
                )
                project_status = "building" if failure_result and failure_result.get("retry_task") else "blocked"
                validation_report = "RETRY_QUEUED" if project_status == "building" else "FAILED_VALIDATION"
                connection.execute(
                    "UPDATE projects SET status = ?, validation_report = ?, updated_at = ? WHERE id = ?",
                    (project_status, validation_report, utc_ts(), int(proposal["project_id"])),
                )
        self._record_run(
            connection,
            project_id=int(proposal["project_id"]),
            action="patch-validation",
            status_before="running",
            status_after=status,
            summary=f"Patch {proposal['id']} validation {status}.",
            payload={"patch_id": int(proposal["id"]), "plan_id": plan_id, "runs": persisted_runs},
        )
        return {
            "patch": self._get_patch(int(proposal["id"]), connection=connection),
            "plan": plan,
            "runs": persisted_runs,
            "passed": passed,
            "validated": True,
            "artifacts": artifacts,
            "failure": failure_result,
        }

    def _record_failure_and_retry_locked(
        self,
        connection: sqlite3.Connection,
        *,
        proposal: dict[str, Any],
        plan: dict[str, Any],
        runs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        failing_run = next((run for run in runs if not run["passed"]), runs[-1] if runs else {})
        failure_summary = _failure_summary(failing_run)
        retry_count = self._task_failure_count(
            connection,
            project_id=int(proposal["project_id"]),
            task_id=int(proposal["task_id"]),
        )
        now = utc_ts()
        cursor = connection.execute(
            """
            INSERT INTO failure_records (
                project_id, task_id, patch_id, validation_plan_id, retry_task_id,
                failing_command, stdout_tail, stderr_tail, failure_summary,
                status, retry_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (
                int(proposal["project_id"]),
                int(proposal["task_id"]),
                int(proposal["id"]),
                int(plan["id"]),
                str(failing_run.get("command", "")),
                str(failing_run.get("stdout_tail", "")),
                str(failing_run.get("stderr_tail", "")),
                failure_summary,
                retry_count,
                now,
                now,
            ),
        )
        failure_id = int(cursor.lastrowid)
        failure = self._get_failure(failure_id, connection=connection)
        retry = self._create_retry_task_for_failure_locked(connection, failure=failure)
        return retry

    def _create_retry_task_for_failure_locked(
        self,
        connection: sqlite3.Connection,
        *,
        failure: dict[str, Any],
    ) -> dict[str, Any]:
        allowed, reason = self._retry_allowed(connection, failure=failure)
        project = self.get_project(int(failure["project_id"]), connection=connection)
        if not allowed:
            connection.execute(
                "UPDATE failure_records SET status = 'abandoned', updated_at = ? WHERE id = ?",
                (utc_ts(), int(failure["id"])),
            )
            self._write_failure_files(
                project=project,
                failure=self._get_failure(int(failure["id"]), connection=connection),
                retry_task=None,
                retry_reason=reason,
                touched_files=self._get_patch(int(failure["patch_id"]), connection=connection).get("target_files", []),
            )
            return {
                "failure": self._get_failure(int(failure["id"]), connection=connection),
                "retry_task": None,
                "retried": False,
                "reason": reason,
            }
        original_task = self._get_task(int(failure["task_id"]), connection=connection)
        retry_position = int(original_task["position"]) + 1
        connection.execute(
            """
            UPDATE tasks
            SET position = position + 1,
                updated_at = ?
            WHERE project_id = ? AND position >= ?
            """,
            (utc_ts(), int(failure["project_id"]), retry_position),
        )
        now = utc_ts()
        title = f"Retry failure {failure['id']}: {original_task['title']}"
        patch = self._get_patch(int(failure["patch_id"]), connection=connection)
        description = _retry_task_description(failure=failure, retry_policy=self.retry_policy, patch=patch)
        cursor = connection.execute(
            """
            INSERT INTO tasks (
                project_id, title, description, status, position, created_at, updated_at
            )
            VALUES (?, ?, ?, 'queued', ?, ?, ?)
            """,
            (
                int(failure["project_id"]),
                title,
                description,
                retry_position,
                now,
                now,
            ),
        )
        retry_task_id = int(cursor.lastrowid)
        connection.execute(
            """
            UPDATE failure_records
            SET retry_task_id = ?,
                status = 'retrying',
                updated_at = ?
            WHERE id = ?
            """,
            (retry_task_id, utc_ts(), int(failure["id"])),
        )
        connection.execute(
            "UPDATE projects SET status = 'building', validation_report = 'RETRY_QUEUED', updated_at = ? WHERE id = ?",
            (utc_ts(), int(failure["project_id"])),
        )
        retry_task = self._get_task(retry_task_id, connection=connection)
        updated_failure = self._get_failure(int(failure["id"]), connection=connection)
        self._write_failure_files(
            project=project,
            failure=updated_failure,
            retry_task=retry_task,
            retry_reason="retry_task_created",
            touched_files=patch.get("target_files", []),
        )
        self._record_run(
            connection,
            project_id=int(failure["project_id"]),
            action="failure-retry-created",
            status_before="open",
            status_after="retrying",
            summary=f"Retry task {retry_task_id} created for failure {failure['id']}.",
            payload={"failure_id": int(failure["id"]), "retry_task_id": retry_task_id},
        )
        return {
            "failure": updated_failure,
            "retry_task": retry_task,
            "retried": True,
            "reason": "retry_task_created",
        }

    def _retry_allowed(self, connection: sqlite3.Connection, *, failure: dict[str, Any]) -> tuple[bool, str]:
        task_retry_count = self._task_failure_count(
            connection,
            project_id=int(failure["project_id"]),
            task_id=int(failure["task_id"]),
        )
        project_retry_count = self._project_failure_count(
            connection,
            project_id=int(failure["project_id"]),
        )
        if task_retry_count > self.retry_policy.max_retries_per_task:
            return False, "max_retries_per_task_exceeded"
        if project_retry_count > self.retry_policy.max_retries_per_project:
            return False, "max_retries_per_project_exceeded"
        if self.retry_policy.stop_on_repeated_failure:
            repeated = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM failure_records
                WHERE project_id = ?
                  AND task_id = ?
                  AND failing_command = ?
                  AND stderr_tail = ?
                """,
                (
                    int(failure["project_id"]),
                    int(failure["task_id"]),
                    str(failure["failing_command"]),
                    str(failure["stderr_tail"]),
                ),
            ).fetchone()
            if int(repeated["count"]) > self.retry_policy.max_retries_per_task + 1:
                return False, "repeated_failure_limit_exceeded"
        return True, "retry_allowed"

    def _task_failure_count(self, connection: sqlite3.Connection, *, project_id: int, task_id: int) -> int:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM failure_records WHERE project_id = ? AND task_id = ?",
            (project_id, task_id),
        ).fetchone()
        return int(row["count"])

    def _project_failure_count(self, connection: sqlite3.Connection, *, project_id: int) -> int:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM failure_records WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row["count"])

    def _resolve_failures_for_patch_locked(
        self,
        connection: sqlite3.Connection,
        *,
        proposal: dict[str, Any],
    ) -> None:
        rows = connection.execute(
            """
            SELECT * FROM failure_records
            WHERE retry_task_id = ? AND status IN ('open', 'retrying')
            ORDER BY id ASC
            """,
            (int(proposal["task_id"]),),
        ).fetchall()
        for row in rows:
            failure = _decode_failure(_row_to_dict(row))
            connection.execute(
                "UPDATE failure_records SET status = 'resolved', updated_at = ? WHERE id = ?",
                (utc_ts(), int(failure["id"])),
            )
            connection.execute(
                "UPDATE tasks SET status = 'done', updated_at = ? WHERE id = ?",
                (utc_ts(), int(failure["task_id"])),
            )
            project = self.get_project(int(failure["project_id"]), connection=connection)
            self._write_failure_files(
                project=project,
                failure=self._get_failure(int(failure["id"]), connection=connection),
                retry_task=self._get_task(int(proposal["task_id"]), connection=connection),
                retry_reason="resolved",
                touched_files=self._get_patch(int(failure["patch_id"]), connection=connection).get("target_files", []),
            )
            self._record_run(
                connection,
                project_id=int(failure["project_id"]),
                action="failure-resolved",
                status_before=failure["status"],
                status_after="resolved",
                summary=f"Failure {failure['id']} resolved by patch {proposal['id']}.",
                payload={"failure_id": int(failure["id"]), "patch_id": int(proposal["id"])},
            )

    def _write_patch_files(
        self,
        connection: sqlite3.Connection,
        *,
        project: dict[str, Any],
        proposal: dict[str, Any],
        patch_report: str,
    ) -> dict[str, str]:
        del connection
        project_dir = Path(project["project_dir"])
        patches_dir = project_dir / "patches"
        patches_dir.mkdir(parents=True, exist_ok=True)
        patch_id = int(proposal["id"])
        diff_path = patches_dir / f"patch_{patch_id:04d}.diff"
        report_path = patches_dir / f"patch_{patch_id:04d}_report.md"
        write_text(diff_path, proposal.get("diff_text", ""))
        report_lines = [
            f"# Patch {patch_id:04d} Report",
            "",
            f"- Project: {project['title']}",
            f"- Task id: {proposal['task_id']}",
            f"- Provider: {proposal['provider_mode']}",
            f"- Status: {proposal['status']}",
            f"- Risk: {proposal['risk_level']}",
            f"- Target files: {', '.join(proposal.get('target_files', [])) or 'none'}",
            "",
            "## Summary",
            "",
            proposal.get("summary", ""),
            "",
            "## ApplyGate",
            "",
            patch_report,
            "",
        ]
        write_text(report_path, "\n".join(report_lines))
        patches_index = project_dir / "PATCHES.md"
        previous = (
            patches_index.read_text(encoding="utf-8")
            if patches_index.exists()
            else f"# PATCHES - {project['title']}\n"
        )
        entry = "\n".join(
            [
                "",
                f"## Patch {patch_id:04d}",
                "",
                f"- Status: {proposal['status']}",
                f"- Risk: {proposal['risk_level']}",
                f"- Provider: {proposal['provider_mode']}",
                f"- Diff: patches/patch_{patch_id:04d}.diff",
                f"- Report: patches/patch_{patch_id:04d}_report.md",
                f"- Files: {', '.join(proposal.get('target_files', [])) or 'none'}",
                "",
            ]
        )
        write_text(patches_index, previous.rstrip() + "\n" + entry)
        return {"diff_path": str(diff_path), "report_path": str(report_path)}

    def _write_validation_files(
        self,
        *,
        project: dict[str, Any],
        plan: dict[str, Any],
        runs: list[dict[str, Any]],
    ) -> list[str]:
        project_dir = Path(project["project_dir"])
        validations_dir = project_dir / "validations"
        validations_dir.mkdir(parents=True, exist_ok=True)
        plan_id = int(plan["id"])
        validation_path = validations_dir / f"validation_{plan_id:04d}.md"
        lines = [
            f"# Validation {plan_id:04d}",
            "",
            f"- Project: {project['title']}",
            f"- Patch id: {plan['patch_id']}",
            f"- Task id: {plan['task_id']}",
            f"- Status: {plan['status']}",
            f"- Max runtime sec: {plan['max_runtime_sec']}",
            "",
            "## Commands",
            "",
        ]
        lines.extend(f"- `{command}`" for command in plan["commands"])
        lines.extend(["", "## Runs", ""])
        for run in runs:
            lines.extend(
                [
                    f"### `{run['command']}`",
                    "",
                    f"- Exit code: {run['exit_code']}",
                    f"- Duration ms: {run['duration_ms']}",
                    f"- Passed: {run['passed']}",
                    "",
                    "Stdout tail:",
                    "",
                    "```text",
                    run["stdout_tail"],
                    "```",
                    "",
                    "Stderr tail:",
                    "",
                    "```text",
                    run["stderr_tail"],
                    "```",
                    "",
                ]
            )
        write_text(validation_path, "\n".join(lines))
        index_path = project_dir / "VALIDATIONS.md"
        previous = (
            index_path.read_text(encoding="utf-8")
            if index_path.exists()
            else f"# VALIDATIONS - {project['title']}\n"
        )
        entry = "\n".join(
            [
                "",
                f"## Validation {plan_id:04d}",
                "",
                f"- Patch id: {plan['patch_id']}",
                f"- Task id: {plan['task_id']}",
                f"- Status: {plan['status']}",
                f"- Report: validations/validation_{plan_id:04d}.md",
                "",
            ]
        )
        write_text(index_path, previous.rstrip() + "\n" + entry)
        return [str(validation_path), str(index_path)]

    def _write_failure_files(
        self,
        *,
        project: dict[str, Any],
        failure: dict[str, Any],
        retry_task: dict[str, Any] | None,
        retry_reason: str,
        touched_files: list[str] | None = None,
    ) -> list[str]:
        project_dir = Path(project["project_dir"])
        failures_dir = project_dir / "failures"
        failures_dir.mkdir(parents=True, exist_ok=True)
        failure_id = int(failure["id"])
        failure_path = failures_dir / f"failure_{failure_id:04d}.md"
        touched_files = touched_files or []
        lines = [
            f"# Failure {failure_id:04d}",
            "",
            f"- Project: {project['title']}",
            f"- Task id: {failure['task_id']}",
            f"- Patch id: {failure['patch_id']}",
            f"- Validation plan id: {failure['validation_plan_id']}",
            f"- Status: {failure['status']}",
            f"- Retry reason: {retry_reason}",
            f"- Retry task id: {retry_task['id'] if retry_task else 'none'}",
            f"- Failing command: `{failure['failing_command']}`",
            f"- Files touched: {', '.join(touched_files) if touched_files else 'none'}",
            "",
            "## Failure Summary",
            "",
            failure["failure_summary"],
            "",
            "## Stdout Tail",
            "",
            "```text",
            failure["stdout_tail"],
            "```",
            "",
            "## Stderr Tail",
            "",
            "```text",
            failure["stderr_tail"],
            "```",
            "",
            "## Retry Task",
            "",
            retry_task["description"] if retry_task else "No retry task was created.",
            "",
        ]
        write_text(failure_path, "\n".join(lines))
        index_path = project_dir / "FAILURES.md"
        previous = (
            index_path.read_text(encoding="utf-8")
            if index_path.exists()
            else f"# FAILURES - {project['title']}\n"
        )
        entry = "\n".join(
            [
                "",
                f"## Failure {failure_id:04d}",
                "",
                f"- Status: {failure['status']}",
                f"- Patch id: {failure['patch_id']}",
                f"- Task id: {failure['task_id']}",
                f"- Retry task id: {retry_task['id'] if retry_task else 'none'}",
                f"- Report: failures/failure_{failure_id:04d}.md",
                "",
            ]
        )
        write_text(index_path, previous.rstrip() + "\n" + entry)
        return [str(failure_path), str(index_path)]

    def _get_failure(self, failure_id: int, *, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM failure_records WHERE id = ?", (failure_id,)).fetchone()
        if row is None:
            raise ValueError(f"Failure {failure_id} not found")
        return _decode_failure(_row_to_dict(row))

    def _get_patch(self, patch_id: int, *, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM patch_proposals WHERE id = ?", (patch_id,)).fetchone()
        if row is None:
            raise ValueError(f"Patch {patch_id} not found")
        return _decode_patch(_row_to_dict(row))

    def _get_validation_plan(self, plan_id: int, *, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM validation_plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None:
            raise ValueError(f"Validation plan {plan_id} not found")
        return _decode_validation_plan(_row_to_dict(row))

    def _latest_validation_plan(
        self,
        patch_id: int,
        *,
        connection: sqlite3.Connection,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM validation_plans WHERE patch_id = ? ORDER BY id DESC LIMIT 1",
            (patch_id,),
        ).fetchone()
        return _decode_validation_plan(_row_to_dict(row)) if row is not None else None

    def _get_review(self, review_id: int, *, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM review_queue WHERE id = ?", (review_id,)).fetchone()
        if row is None:
            raise ValueError(f"Review {review_id} not found")
        return _decode_review(_row_to_dict(row))

    def _complete_project_if_ready(
        self,
        connection: sqlite3.Connection,
        project_id: int,
    ) -> dict[str, Any]:
        project = self.get_project(project_id, connection=connection)
        tasks = project["tasks"]
        if tasks and all(task["status"] == "done" for task in tasks):
            now = utc_ts()
            connection.execute(
                "UPDATE projects SET status = 'testing', updated_at = ? WHERE id = ?",
                (now, project_id),
            )
            connection.execute(
                "UPDATE projects SET status = 'done', validation_report = 'PASS', updated_at = ? WHERE id = ?",
                (utc_ts(), project_id),
            )
            self._record_run(
                connection,
                project_id=project_id,
                action="complete-project",
                status_before="building",
                status_after="done",
                summary="All tasks are done; testing gate passed.",
                payload={"task_count": len(tasks)},
            )
            connection.commit()
            return {
                "action_taken": "project_done",
                "project": self.get_project(project_id, connection=connection),
                "execution": None,
            }
        connection.execute(
            "UPDATE projects SET status = 'blocked', validation_report = 'BLOCKED', updated_at = ? WHERE id = ?",
            (utc_ts(), project_id),
        )
        self._record_run(
            connection,
            project_id=project_id,
            action="complete-project",
            status_before=project["status"],
            status_after="blocked",
            summary="Project has no queued task but is not fully done.",
            payload={"task_count": len(tasks)},
        )
        connection.commit()
        return {
            "action_taken": "project_blocked",
            "project": self.get_project(project_id, connection=connection),
            "execution": None,
        }

    def _record_run(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: int | None,
        action: str,
        status_before: str | None,
        status_after: str | None,
        summary: str,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO runs (
                project_id, action, status_before, status_after, provider_name, summary, payload, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                action,
                status_before,
                status_after,
                self.provider.name,
                summary,
                json.dumps(payload, sort_keys=True, ensure_ascii=False),
                utc_ts(),
            ),
        )


def render_project_queue_orchestrator_status(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Project Queue Orchestrator",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        f"Provider: {snapshot['provider']['name']}",
        f"Provider available: {snapshot['provider']['available']}",
        f"NVIDIA_API_KEY present: {snapshot['provider']['nvidia_api_key_present']}",
        "",
        "## Metrics",
        "",
        f"Projects: {snapshot['metrics']['project_count']}",
        f"Tasks: {snapshot['metrics']['task_count']}",
        f"Task executions: {snapshot['metrics']['execution_count']}",
        f"Runs: {snapshot['metrics']['run_count']}",
        f"Runnable projects: {snapshot['metrics']['runnable_project_count']}",
        "",
        "## Projects",
        "",
        "| ID | Title | Status | Tasks | Project dir |",
        "| --- | --- | --- | --- | --- |",
    ]
    tasks_by_project: dict[int, int] = {}
    for task in snapshot["tasks"]:
        tasks_by_project[int(task["project_id"])] = tasks_by_project.get(int(task["project_id"]), 0) + 1
    for project in snapshot["projects"]:
        lines.append(
            f"| {project['id']} | {project['title']} | {project['status']} | "
            f"{tasks_by_project.get(int(project['id']), 0)} | {project.get('project_dir') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Task Executions",
            "",
            "| ID | Project | Task | Status | Validation | Artifacts |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for execution in snapshot.get("task_executions", [])[-20:]:
        lines.append(
            f"| {execution['id']} | {execution['project_id']} | {execution['task_id']} | "
            f"{execution['status']} | {execution['validation_status']} | {len(execution['artifacts'])} |"
        )
    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| ID | Project | Action | Before | After | Summary |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for run in snapshot["runs"][-20:]:
        lines.append(
            f"| {run['id']} | {run.get('project_id') or ''} | {run['action']} | "
            f"{run.get('status_before') or ''} | {run.get('status_after') or ''} | {run['summary']} |"
        )
    lines.extend(
        [
            "",
            "## Status Flow",
            "",
            "idea -> designing -> valid -> building -> testing -> done",
            "",
            "Blocked, archived and done projects are ignored by `run-next`.",
        ]
    )
    return "\n".join(lines)


def render_project_execution_loop_status(loop_result: dict[str, Any]) -> str:
    lines = [
        "# Project Execution Loop",
        "",
        f"Artifact: {loop_result['id']}",
        f"Schema: {loop_result['schema_version']}",
        f"Steps: {len(loop_result['steps'])}",
        "",
        "## Metrics",
        "",
        f"Executed tasks: {loop_result['metrics']['executed_task_count']}",
        f"Done executions: {loop_result['metrics']['done_execution_count']}",
        f"Failed executions: {loop_result['metrics']['failed_execution_count']}",
        f"Blocked executions: {loop_result['metrics']['blocked_execution_count']}",
        f"Projects done: {loop_result['metrics']['done_project_count']}",
        "",
        "## Steps",
        "",
        "| Step | Action | Project | Execution | Status | Validation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, step in enumerate(loop_result["steps"], start=1):
        project = step.get("project") or {}
        execution = step.get("execution") or {}
        lines.append(
            f"| {index} | {step['action_taken']} | {project.get('id', '')} | "
            f"{execution.get('id', '')} | {execution.get('status', '')} | "
            f"{execution.get('validation_status', '')} |"
        )
    lines.extend(
        [
            "",
            "## Execution Contract",
            "",
            "Each task execution records input prompt, output summary, changed files, artifacts, validation status, start time and finish time.",
        ]
    )
    return "\n".join(lines)


def render_real_provider_execution_guard_status(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Real Provider Execution Guard",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        f"Provider mode: {snapshot['provider_mode']}",
        f"Provider available: {snapshot['provider_available']}",
        "",
        "## Guard",
        "",
        f"Max changed files: {snapshot['guard']['max_changed_files']}",
        f"Max output tokens: {snapshot['guard']['max_output_tokens']}",
        "",
        "## Metrics",
        "",
        f"Guard logs: {snapshot['metrics']['guard_log_count']}",
        f"Blocked outputs: {snapshot['metrics']['blocked_output_count']}",
        f"Pending reviews: {snapshot['metrics']['pending_review_count']}",
        f"Accepted reviews: {snapshot['metrics']['accepted_review_count']}",
        f"Rejected reviews: {snapshot['metrics']['rejected_review_count']}",
        "",
        "## Review Queue",
        "",
        "| ID | Project | Task | Execution | Provider | Status | Changes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for review in snapshot["reviews"][-20:]:
        lines.append(
            f"| {review['id']} | {review['project_id']} | {review['task_id']} | "
            f"{review['execution_id']} | {review['provider_mode']} | {review['status']} | "
            f"{len(review['proposed_changes'])} |"
        )
    lines.extend(
        [
            "",
            "## Guard Logs",
            "",
            "| ID | Execution | Provider | Guard status | Violations |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for log in snapshot["guard_logs"][-20:]:
        guard_report = log["guard_report"]
        lines.append(
            f"| {log['id']} | {log['execution_id']} | {log['provider_mode']} | "
            f"{guard_report.get('status', '')} | {', '.join(guard_report.get('violations', []))} |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- `mock` applies deterministic safe outputs immediately.",
            "- `dry_run` executes without writing project files.",
            "- `nvidia_nim` and `manual_review` outputs are queued for review before application.",
            "- The guard blocks dangerous commands, paths outside the project and oversized outputs.",
        ]
    )
    return "\n".join(lines)


def render_context_pack_provider_prompting_status(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Context Pack Provider Prompting",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        "",
        "## Metrics",
        "",
        f"Context packs: {snapshot['metrics']['context_pack_count']}",
        f"Average evidence score: {snapshot['metrics']['average_evidence_score']}",
        f"Average relative cost: {snapshot['metrics']['average_relative_resolution_cost']}",
        f"Low evidence packs: {snapshot['metrics']['low_evidence_count']}",
        "",
        "## Packs",
        "",
        "| ID | Project | Task | Evidence | Cost | Files | Sources |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["context_packs"][-20:]:
        pack = row["context_pack"]
        lines.append(
            f"| {row['id']} | {row['project_id']} | {row['task_id']} | "
            f"{pack['evidence_score']} | {pack['relative_resolution_cost']} | "
            f"{len(pack['selected_files'])} | {len(pack['source_refs'])} |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- A TaskContextPack is built before the provider call when `--use-context-pack` is set.",
            "- Selected chunks are bounded by token budget and cite source refs.",
            "- ProviderPrompt includes system prompt, task prompt, context pack, safety rules and output contract.",
            "- Execution is refused when evidence score is too low.",
        ]
    )
    return "\n".join(lines)


def render_patch_proposal_apply_gate_status(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Patch Proposal Apply Gate",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        "",
        "## Metrics",
        "",
        f"Patch proposals: {snapshot['metrics']['patch_count']}",
        f"Proposed: {snapshot['metrics']['proposed_count']}",
        f"Applied: {snapshot['metrics']['applied_count']}",
        f"Rejected: {snapshot['metrics']['rejected_count']}",
        f"Failed: {snapshot['metrics']['failed_count']}",
        f"Failed validation: {snapshot['metrics']['failed_validation_count']}",
        f"High risk: {snapshot['metrics']['high_risk_count']}",
        "",
        "## Patch Queue",
        "",
        "| ID | Project | Task | Provider | Status | Risk | Files |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for patch in snapshot["patches"][-20:]:
        lines.append(
            f"| {patch['id']} | {patch['project_id']} | {patch['task_id']} | "
            f"{patch['provider_mode']} | {patch['status']} | {patch['risk_level']} | "
            f"{len(patch['target_files'])} |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- Provider patch output is converted into a PatchProposal before project writes.",
            "- PatchParser accepts `=== FILE: path ===` sections and rejects paths outside the project.",
            "- ApplyGate reuses ExecutionGuard, supports dry-run application and writes patch reports.",
            "- Real provider output or risk above low stays in `proposed` until explicit apply or reject.",
        ]
    )
    return "\n".join(lines)


def render_post_patch_validation_loop_status(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Post-Patch Validation Loop",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        "",
        "## Metrics",
        "",
        f"Validation plans: {snapshot['metrics']['plan_count']}",
        f"Validation runs: {snapshot['metrics']['run_count']}",
        f"Passed plans: {snapshot['metrics']['passed_plan_count']}",
        f"Failed plans: {snapshot['metrics']['failed_plan_count']}",
        f"Rejected command runs: {snapshot['metrics']['rejected_run_count']}",
        "",
        "## Plans",
        "",
        "| ID | Project | Task | Patch | Status | Commands |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for plan in snapshot["plans"][-20:]:
        lines.append(
            f"| {plan['id']} | {plan['project_id']} | {plan['task_id']} | "
            f"{plan['patch_id']} | {plan['status']} | {len(plan['commands'])} |"
        )
    lines.extend(["", "## Runs", "", "| ID | Plan | Command | Exit | Passed | Duration ms |", "| --- | --- | --- | --- | --- | --- |"])
    for run in snapshot["runs"][-20:]:
        lines.append(
            f"| {run['id']} | {run['plan_id']} | `{run['command']}` | "
            f"{run['exit_code']} | {run['passed']} | {run['duration_ms']} |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- Patch application creates a ValidationPlan.",
            "- SafeCommandRunner only allows whitelisted `python -m ...` commands.",
            "- A task is marked done only when the post-patch validation plan passes.",
            "- Failed validation marks the patch `failed_validation` and blocks the task.",
        ]
    )
    return "\n".join(lines)


def render_failure_recovery_retry_loop_status(snapshot: dict[str, Any]) -> str:
    policy = snapshot["retry_policy"]
    lines = [
        "# Failure Recovery Retry Loop",
        "",
        f"Artifact: {snapshot['id']}",
        f"Schema: {snapshot['schema_version']}",
        "",
        "## Retry Policy",
        "",
        f"Max retries per task: {policy['max_retries_per_task']}",
        f"Max retries per project: {policy['max_retries_per_project']}",
        f"Retry requires review: {policy['retry_requires_review']}",
        f"Stop on repeated failure: {policy['stop_on_repeated_failure']}",
        "",
        "## Metrics",
        "",
        f"Failures: {snapshot['metrics']['failure_count']}",
        f"Retrying: {snapshot['metrics']['retrying_count']}",
        f"Resolved: {snapshot['metrics']['resolved_count']}",
        f"Abandoned: {snapshot['metrics']['abandoned_count']}",
        "",
        "## Failure Records",
        "",
        "| ID | Project | Task | Patch | Plan | Status | Retry Task | Command |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for failure in snapshot["failures"][-20:]:
        lines.append(
            f"| {failure['id']} | {failure['project_id']} | {failure['task_id']} | "
            f"{failure['patch_id']} | {failure['validation_plan_id']} | {failure['status']} | "
            f"{failure.get('retry_task_id') or ''} | `{failure['failing_command']}` |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- Failed post-patch validation creates a FailureRecord.",
            "- A RetryTask captures the failed command, error tails, faulty patch and safety constraints.",
            "- Retry policy limits repeated attempts and can force review on retry tasks.",
            "- A following successful retry patch marks the failure resolved.",
        ]
    )
    return "\n".join(lines)


def _slugify(value: str) -> str:
    lowered = value.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "project"


def _render_project_cdc(project: dict[str, Any], design: dict[str, Any]) -> str:
    tasks = "\n".join(f"- {task['title']}: {task['description']}" for task in design["tasks"])
    return "\n".join(
        [
            f"# CDC - {project['title']}",
            "",
            "## Objective",
            "",
            design["summary"],
            "",
            "## Description",
            "",
            project["description"],
            "",
            "## Scope",
            "",
            "- Define the project contract.",
            "- Initialize the project files.",
            "- Keep validation gates explicit.",
            "",
            "## Acceptance Criteria",
            "",
            "- `CDC.md` exists.",
            "- `TASKS.md` exists.",
            "- `README.md` exists.",
            "- At least one task exists in the queue.",
            "",
            "## Initial Tasks",
            "",
            tasks,
        ]
    )


def _render_project_tasks(project: dict[str, Any], design: dict[str, Any]) -> str:
    lines = [f"# TASKS - {project['title']}", ""]
    for task in design["tasks"]:
        lines.append(f"- [ ] {task['title']}: {task['description']}")
    return "\n".join(lines)


def _render_project_readme(project: dict[str, Any], design: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {project['title']}",
            "",
            project["description"],
            "",
            "## Runtime Status",
            "",
            "- Queue status: designing",
            f"- Provider: {design['provider']}",
            f"- Provider fallback: {design.get('used_fallback', False)}",
            "",
            "## Files",
            "",
            "- `CDC.md`: project contract.",
            "- `TASKS.md`: initial task list.",
            "- `README.md`: project entry point.",
        ]
    )


def _project_queue_metrics(
    projects: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    task_executions: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = {status: 0 for status in sorted(PROJECT_STATUSES)}
    for project in projects:
        status_counts[project["status"]] = status_counts.get(project["status"], 0) + 1
    return {
        "project_count": len(projects),
        "task_count": len(tasks),
        "execution_count": len(task_executions),
        "run_count": len(runs),
        "status_counts": status_counts,
        "runnable_project_count": sum(
            1 for project in projects if project["status"] in {"idea", "designing", "valid"}
        ),
        "queued_task_count": sum(1 for task in tasks if task["status"] in {"queued", "todo"}),
        "todo_task_count": sum(1 for task in tasks if task["status"] in {"queued", "todo"}),
        "doing_task_count": sum(1 for task in tasks if task["status"] == "doing"),
        "done_task_count": sum(1 for task in tasks if task["status"] == "done"),
        "failed_task_count": sum(1 for task in tasks if task["status"] == "failed"),
        "done_execution_count": sum(1 for item in task_executions if item["status"] == "done"),
        "failed_execution_count": sum(1 for item in task_executions if item["status"] == "failed"),
        "blocked_execution_count": sum(1 for item in task_executions if item["status"] == "blocked"),
    }


def _execution_loop_metrics(snapshot: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    executions = snapshot.get("task_executions", [])
    return {
        "step_count": len(steps),
        "executed_task_count": sum(1 for step in steps if step["action_taken"] == "task_executed"),
        "done_execution_count": sum(1 for item in executions if item["status"] == "done"),
        "failed_execution_count": sum(1 for item in executions if item["status"] == "failed"),
        "blocked_execution_count": sum(1 for item in executions if item["status"] == "blocked"),
        "done_project_count": sum(1 for project in snapshot["projects"] if project["status"] == "done"),
        "building_project_count": sum(1 for project in snapshot["projects"] if project["status"] == "building"),
    }


def _execution_prompt(project: dict[str, Any], task: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Project: {project['title']}",
            f"Description: {project['description']}",
            f"Task: {task['title']}",
            f"Task description: {task['description']}",
            "Execute the smallest traceable step and return a validation-ready summary.",
        ]
    )


def _render_provider_prompt(provider_prompt: dict[str, Any]) -> str:
    return "\n".join(
        [
            "## System Prompt",
            provider_prompt["system_prompt"],
            "",
            "## Safety Rules",
            *[f"- {rule}" for rule in provider_prompt["safety_rules"]],
            "",
            "## Output Contract",
            json.dumps(provider_prompt["output_contract"], indent=2, ensure_ascii=False),
            "",
            "## Task Prompt",
            provider_prompt["task_prompt"],
        ]
    )


def _mock_patch_text(*, project: dict[str, Any], task: dict[str, Any], summary: str) -> str:
    task_id = int(task.get("id") or 0)
    safe_title = str(task.get("title", "task")).strip()
    return "\n".join(
        [
            f"=== FILE: provider_outputs/mock_task_{task_id:04d}.md ===",
            f"# Mock Provider Patch - {safe_title}",
            "",
            f"Project: {project['title']}",
            f"Task: {safe_title}",
            "",
            "## Summary",
            "",
            summary,
            "",
        ]
    )


def _provider_patch_text(provider_result: dict[str, Any]) -> str:
    for key in ["patch_text", "patch", "diff_text"]:
        value = provider_result.get(key)
        if isinstance(value, str) and "=== FILE:" in value:
            return value
    for artifact in provider_result.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        content = artifact.get("content")
        if isinstance(content, str) and "=== FILE:" in content:
            return content
    return ""


def _split_patch_sections(patch_text: str) -> list[tuple[str, str]]:
    marker = re.compile(r"^===\s*FILE:\s*(.*?)\s*===\s*$", flags=re.MULTILINE)
    matches = list(marker.finditer(patch_text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(patch_text)
        raw_path = match.group(1).strip()
        content = patch_text[start:end].strip("\r\n")
        if raw_path:
            sections.append((raw_path, content))
    return sections


def _looks_like_unified_diff(content: str) -> bool:
    lines = content.splitlines()
    return any(line.startswith("@@ ") for line in lines) and any(line.startswith(("--- ", "+++ ")) for line in lines)


def _is_binary_patch_path(path: Path) -> bool:
    return path.suffix.lower() in {
        ".bin",
        ".dll",
        ".exe",
        ".ico",
        ".jpg",
        ".jpeg",
        ".pdf",
        ".png",
        ".pyc",
        ".so",
        ".webp",
        ".zip",
    }


def _apply_unified_diff(original: str, diff_text: str) -> str:
    original_lines = original.splitlines(keepends=True)
    output: list[str] = []
    source_index = 0
    lines = diff_text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("@@ "):
            index += 1
            continue
        match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if match is None:
            raise ValueError("invalid_unified_diff_hunk")
        old_start = max(0, int(match.group(1)) - 1)
        output.extend(original_lines[source_index:old_start])
        source_index = old_start
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            hunk_line = lines[index]
            if hunk_line.startswith(" "):
                output.append(hunk_line[1:])
                source_index += 1
            elif hunk_line.startswith("-"):
                source_index += 1
            elif hunk_line.startswith("+"):
                output.append(hunk_line[1:])
            elif hunk_line.startswith("\\"):
                pass
            elif hunk_line.startswith(("--- ", "+++ ")):
                pass
            else:
                raise ValueError("invalid_unified_diff_line")
            index += 1
    output.extend(original_lines[source_index:])
    return "".join(output)


def _patch_risk_level(changes: list[dict[str, Any]], patch_text: str) -> str:
    patch_bytes = len(patch_text.encode("utf-8", errors="ignore"))
    if any(change.get("operation") == "delete" for change in changes):
        return "high"
    if len(changes) <= 2 and patch_bytes <= 12_000:
        return "low"
    if len(changes) <= 5 and patch_bytes <= 40_000:
        return "medium"
    return "high"


def _patch_artifact_paths(proposal: dict[str, Any]) -> list[str]:
    return [
        str(path)
        for path in [proposal.get("diff_path"), proposal.get("report_path")]
        if path
    ]


def _decode_execution(execution: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(execution)
    decoded["changed_files"] = json.loads(decoded.get("changed_files") or "[]")
    decoded["artifacts"] = json.loads(decoded.get("artifacts") or "[]")
    return decoded


def _decode_context_pack(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    decoded["context_pack"] = json.loads(decoded.get("context_pack") or "{}")
    decoded["provider_prompt"] = json.loads(decoded.get("provider_prompt") or "{}")
    return decoded


def _decode_review(review: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(review)
    decoded["provider_response"] = json.loads(decoded.get("provider_response") or "{}")
    decoded["guard_report"] = json.loads(decoded.get("guard_report") or "{}")
    decoded["proposed_changes"] = json.loads(decoded.get("proposed_changes") or "[]")
    return decoded


def _decode_patch(patch: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(patch)
    decoded["target_files"] = json.loads(decoded.get("target_files") or "[]")
    decoded["parsed_changes"] = json.loads(decoded.get("parsed_changes") or "[]")
    return decoded


def _decode_validation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(plan)
    decoded["commands"] = json.loads(decoded.get("commands") or "[]")
    decoded["allowed_commands"] = json.loads(decoded.get("allowed_commands") or "[]")
    return decoded


def _decode_validation_run(run: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(run)
    decoded["passed"] = bool(decoded.get("passed"))
    return decoded


def _decode_failure(failure: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(failure)
    if decoded.get("retry_task_id") is not None:
        decoded["retry_task_id"] = int(decoded["retry_task_id"])
    return decoded


def _decode_guard_log(log: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(log)
    decoded["provider_response"] = json.loads(decoded.get("provider_response") or "{}")
    decoded["guard_report"] = json.loads(decoded.get("guard_report") or "{}")
    return decoded


def _extract_json_object(value: str) -> dict[str, Any] | None:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _context_query_terms(project: dict[str, Any], task: dict[str, Any]) -> list[str]:
    raw = " ".join(
        [
            str(project.get("title", "")),
            str(project.get("description", "")),
            str(task.get("title", "")),
            str(task.get("description", "")),
            "cdc readme tasks tests validation architecture constraints",
        ]
    ).lower()
    terms = [
        term
        for term in re.findall(r"[a-z0-9_]{3,}", raw)
        if term
        not in {
            "the",
            "and",
            "for",
            "with",
            "into",
            "task",
            "project",
            "projet",
            "une",
            "des",
            "les",
            "dans",
        }
    ]
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped[:18]


def _is_generated_context_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    return (
        normalized == "runs.md"
        or normalized == "context_packs.md"
        or normalized.startswith("artifacts/")
        or normalized.startswith("provider_outputs/")
    )


def _budget_chunks(chunks: list[dict[str, Any]], token_budget: int) -> list[dict[str, Any]]:
    budgeted: list[dict[str, Any]] = []
    used = 0
    for chunk in chunks:
        chunk_tokens = int(chunk.get("token_estimate", 0))
        if not budgeted and chunk_tokens > token_budget:
            trimmed = dict(chunk)
            trimmed["text"] = _truncate_words(chunk["text"], max(1, int(token_budget / 1.4)))
            trimmed["token_estimate"] = _token_estimate(trimmed["text"])
            budgeted.append(trimmed)
            break
        if budgeted and used + chunk_tokens > token_budget:
            continue
        budgeted.append(chunk)
        used += chunk_tokens
        if used >= token_budget:
            break
    return budgeted


def _context_chunk_summary(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": chunk["id"],
        "file_path": chunk["file_path"],
        "chunk_index": chunk["chunk_index"],
        "start_line": chunk["start_line"],
        "end_line": chunk["end_line"],
        "token_estimate": chunk["token_estimate"],
        "text": _truncate_words(chunk["text"], 90),
    }


def _context_key_facts(chunks: list[dict[str, Any]], query_terms: list[str]) -> list[str]:
    facts: list[str] = []
    terms = [term.lower() for term in query_terms]
    for chunk in chunks:
        for line in chunk["text"].splitlines():
            stripped = line.strip(" -#\t")
            if len(stripped) < 8:
                continue
            lower = stripped.lower()
            if any(term in lower for term in terms) or not facts:
                facts.append(f"{chunk['file_path']}:{chunk['start_line']} - {_truncate_words(stripped, 24)}")
            if len(facts) >= 8:
                return facts
    return facts


def _context_relevant_tests(chunks: list[dict[str, Any]], query_terms: list[str]) -> list[str]:
    relevant = []
    terms = [term.lower() for term in query_terms]
    for chunk in chunks:
        path = chunk["file_path"].lower()
        text = chunk["text"].lower()
        if "test" not in path and "pytest" not in text:
            continue
        if terms and not any(term in text or term in path for term in terms):
            continue
        relevant.append(f"{chunk['file_path']}:{chunk['start_line']}-{chunk['end_line']}")
        if len(relevant) >= 6:
            break
    return relevant


def _context_constraints(project: dict[str, Any], chunks: list[dict[str, Any]]) -> list[str]:
    constraints = [
        "Modify only files inside the project directory.",
        "Keep execution traceable through task_executions and reports.",
    ]
    for chunk in chunks:
        if chunk["file_path"].lower().endswith("cdc.md"):
            for line in chunk["text"].splitlines():
                stripped = line.strip(" -#\t")
                if "acceptance" in stripped.lower() or "constraint" in stripped.lower():
                    constraints.append(_truncate_words(stripped, 24))
                if len(constraints) >= 6:
                    return constraints
    return constraints


def _failure_summary(run: dict[str, Any]) -> str:
    command = str(run.get("command", "unknown"))
    stderr = str(run.get("stderr_tail", "")).strip()
    stdout = str(run.get("stdout_tail", "")).strip()
    evidence = stderr or stdout or "No output captured."
    return f"Command `{command}` failed. Evidence: {_truncate_words(evidence, 40)}"


def _retry_task_description(
    *,
    failure: dict[str, Any],
    retry_policy: RetryPolicy,
    patch: dict[str, Any],
) -> str:
    touched = ", ".join(patch.get("target_files", [])) or "none"
    review = "true" if retry_policy.retry_requires_review else "false"
    return "\n".join(
        [
            f"FailureRecord: {failure['id']}",
            f"Retry requires review: {review}",
            "",
            "## Error",
            failure["failure_summary"],
            "",
            "## Faulty Patch",
            f"- Patch id: {failure['patch_id']}",
            f"- Files touched: {touched}",
            "",
            "## Failed Command",
            f"`{failure['failing_command']}`",
            "",
            "## Stdout Tail",
            failure["stdout_tail"],
            "",
            "## Stderr Tail",
            failure["stderr_tail"],
            "",
            "## Correction Hypothesis",
            "Inspect the touched files, repair the validation failure, and keep the smallest safe patch.",
            "",
            "## Safety Constraints",
            "- Only modify files inside the project directory.",
            "- Do not use destructive commands.",
            "- Keep the retry patch traceable and reviewable.",
        ]
    )


def _task_requires_review(task: dict[str, Any]) -> bool:
    return "retry requires review: true" in str(task.get("description", "")).lower()


def _excluded_summary(excluded_files: list[str], total_file_count: int) -> str:
    if not excluded_files:
        return "No indexed file was excluded from the context pack."
    preview = ", ".join(excluded_files[:8])
    remaining = max(0, len(excluded_files) - 8)
    suffix = f" and {remaining} more" if remaining else ""
    return f"Excluded {len(excluded_files)} of {total_file_count} indexed files: {preview}{suffix}."


def _context_pack_metrics(context_packs: list[dict[str, Any]]) -> dict[str, Any]:
    if not context_packs:
        return {
            "context_pack_count": 0,
            "average_evidence_score": 0.0,
            "average_relative_resolution_cost": 0.0,
            "low_evidence_count": 0,
        }
    return {
        "context_pack_count": len(context_packs),
        "average_evidence_score": round(
            sum(float(pack.get("evidence_score", 0.0)) for pack in context_packs) / len(context_packs),
            3,
        ),
        "average_relative_resolution_cost": round(
            sum(float(pack.get("relative_resolution_cost", 0.0)) for pack in context_packs) / len(context_packs),
            3,
        ),
        "low_evidence_count": sum(
            1 for pack in context_packs if float(pack.get("evidence_score", 0.0)) < MIN_CONTEXT_EVIDENCE_SCORE
        ),
    }


def _truncate_words(value: str, limit: int) -> str:
    words = value.split()
    if len(words) <= limit:
        return value
    return " ".join(words[:limit]) + "..."


def _normalize_proposed_changes(provider_result: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for change in provider_result.get("proposed_changes", []):
        if not isinstance(change, dict):
            continue
        normalized.append(
            {
                "operation": str(change.get("operation", "write")).lower(),
                "path": str(change.get("path", "")),
                "content": str(change.get("content", "")),
            }
        )
    if normalized:
        return normalized
    for path in provider_result.get("changed_files", []):
        if isinstance(path, str):
            normalized.append({"operation": "write", "path": path, "content": ""})
    return normalized


def _guard_change(project_dir: Path, change: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    operation = str(change.get("operation", "write")).lower()
    if operation not in {"write", "append", "delete"}:
        return None, f"unsupported_operation:{operation}"
    raw_path = str(change.get("path", "")).strip()
    if not raw_path:
        return None, "empty_change_path"
    target = Path(raw_path)
    if not target.is_absolute():
        target = project_dir / target
    resolved = target.resolve()
    if not _is_relative_to(resolved, project_dir):
        if operation == "delete":
            return None, f"delete_outside_project:{resolved}"
        return None, f"change_outside_project:{resolved}"
    return {
        "operation": operation,
        "path": raw_path,
        "resolved_path": str(resolved),
        "content": str(change.get("content", "")),
    }, None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _provider_output_tokens(provider_result: dict[str, Any]) -> int:
    parts = [str(provider_result.get("output_summary", ""))]
    for artifact in provider_result.get("artifacts", []):
        if isinstance(artifact, dict):
            parts.append(str(artifact.get("content", "")))
    for change in provider_result.get("proposed_changes", []):
        if isinstance(change, dict):
            parts.append(str(change.get("content", "")))
    return len("\n".join(parts).split())


def _changed_file_paths(safe_changes: list[dict[str, Any]]) -> list[str]:
    return [str(change["resolved_path"]) for change in safe_changes]


def _review_metrics(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "review_count": len(reviews),
        "pending_review_count": sum(1 for review in reviews if review["status"] == "pending_review"),
        "accepted_review_count": sum(1 for review in reviews if review["status"] == "accepted"),
        "rejected_review_count": sum(1 for review in reviews if review["status"] == "rejected"),
    }


def _patch_metrics(patches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "patch_count": len(patches),
        "proposed_count": sum(1 for patch in patches if patch["status"] == "proposed"),
        "approved_count": sum(1 for patch in patches if patch["status"] == "approved"),
        "applied_count": sum(1 for patch in patches if patch["status"] == "applied"),
        "rejected_count": sum(1 for patch in patches if patch["status"] == "rejected"),
        "failed_count": sum(1 for patch in patches if patch["status"] == "failed"),
        "failed_validation_count": sum(1 for patch in patches if patch["status"] == "failed_validation"),
        "high_risk_count": sum(1 for patch in patches if patch["risk_level"] == "high"),
    }


def _validation_metrics(plans: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "plan_count": len(plans),
        "run_count": len(runs),
        "passed_plan_count": sum(1 for plan in plans if plan["status"] == "passed"),
        "failed_plan_count": sum(1 for plan in plans if plan["status"] == "failed"),
        "running_plan_count": sum(1 for plan in plans if plan["status"] == "running"),
        "rejected_run_count": sum(
            1 for run in runs if run["exit_code"] == -1 and "refused" in run["stderr_tail"]
        ),
        "average_duration_ms": round(
            sum(int(run["duration_ms"]) for run in runs) / max(1, len(runs)),
            3,
        ),
    }


def _retry_policy_snapshot(policy: RetryPolicy) -> dict[str, Any]:
    return {
        "max_retries_per_task": policy.max_retries_per_task,
        "max_retries_per_project": policy.max_retries_per_project,
        "retry_requires_review": policy.retry_requires_review,
        "stop_on_repeated_failure": policy.stop_on_repeated_failure,
    }


def _failure_metrics(failures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "failure_count": len(failures),
        "open_count": sum(1 for failure in failures if failure["status"] == "open"),
        "retrying_count": sum(1 for failure in failures if failure["status"] == "retrying"),
        "resolved_count": sum(1 for failure in failures if failure["status"] == "resolved"),
        "abandoned_count": sum(1 for failure in failures if failure["status"] == "abandoned"),
        "retry_task_count": sum(1 for failure in failures if failure.get("retry_task_id") is not None),
    }


def _guard_metrics(reviews: list[dict[str, Any]], logs: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_logs = [log for log in logs if log["guard_report"].get("status") == "blocked"]
    return {
        **_review_metrics(reviews),
        "guard_log_count": len(logs),
        "blocked_output_count": len(blocked_logs),
        "accepted_output_count": sum(1 for log in logs if log["guard_report"].get("status") == "passed"),
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}
