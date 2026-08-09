from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fractal_creation_studio import FractalCreationStudio, StudioConfig


SCHEMA_VERSION = "continuous-dev-runtime-v1"
IDEA_STATUSES = {
    "Inbox",
    "NeedsAnalysis",
    "NeedsClarification",
    "Analyzed",
    "Planned",
    "AwaitingApproval",
    "Approved",
    "Ready",
    "Queued",
    "InProgress",
    "Blocked",
    "Testing",
    "Validation",
    "RevisionRequired",
    "Completed",
    "Deferred",
    "Rejected",
    "Archived",
}
TASK_STATUSES = {
    "Ready",
    "Queued",
    "InProgress",
    "Blocked",
    "Testing",
    "Validation",
    "Completed",
    "Failed",
    "Deferred",
    "Cancelled",
}
QUEUE_ORDER = ["Critical", "Urgent", "HighPriority", "Normal", "Maintenance", "Documentation", "Experiments", "Deferred"]
MEMORY_LEVELS = ["Focus", "SessionActive", "ProjectHot", "ProjectCompacted", "Archive"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_runtime_dir() -> Path:
    configured = os.environ.get("FRACTAL_CDR_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "AIONE" / "ContinuousDevRuntime"
    return Path.home() / ".aione" / "continuous-dev-runtime"


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def read_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, timeout: int = 60) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except FileNotFoundError as exc:
        return {
            "success": False,
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"Timeout after {timeout}s",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


@dataclass(frozen=True)
class RuntimeConfig:
    runtime_dir: Path
    workspace_root: Path
    db_path: Path
    agent_workspace: Path
    bind_host: str = "127.0.0.1"
    port: int = 8795
    coding_agent_gpu: str = "0"
    idea_agent_gpu: str = "1"
    coding_model: str = ""
    idea_model: str = ""
    max_ram_percent: int = 85
    max_gpu0_vram_percent: int = 88
    max_gpu1_vram_percent: int = 80
    max_disk_usage_percent: int = 92
    max_parallel_read_tasks: int = 2
    max_parallel_write_tasks: int = 1
    max_context_tokens: int = 12000
    max_task_duration_seconds: int = 900

    @staticmethod
    def build(runtime_dir: str | Path | None = None, workspace_root: str | Path = ".") -> "RuntimeConfig":
        resolved_runtime = Path(runtime_dir).expanduser().resolve() if runtime_dir else default_runtime_dir().resolve()
        workspace = Path(workspace_root).expanduser().resolve()
        return RuntimeConfig(
            runtime_dir=resolved_runtime,
            workspace_root=workspace,
            db_path=resolved_runtime / "continuous_dev_runtime.sqlite",
            agent_workspace=resolved_runtime / "agent-workspace",
            bind_host=os.environ.get("FRACTAL_CDR_BIND_HOST", "127.0.0.1"),
            port=int(os.environ.get("FRACTAL_CDR_PORT", "8795")),
            coding_agent_gpu=os.environ.get("CODING_AGENT_GPU", "0"),
            idea_agent_gpu=os.environ.get("IDEA_AGENT_GPU", "1"),
            coding_model=os.environ.get("CODING_AGENT_MODEL", ""),
            idea_model=os.environ.get("IDEA_AGENT_MODEL", ""),
            max_ram_percent=int(os.environ.get("MAX_RAM_PERCENT", "85")),
            max_gpu0_vram_percent=int(os.environ.get("MAX_GPU0_VRAM_PERCENT", "88")),
            max_gpu1_vram_percent=int(os.environ.get("MAX_GPU1_VRAM_PERCENT", "80")),
            max_disk_usage_percent=int(os.environ.get("MAX_DISK_USAGE_PERCENT", "92")),
            max_parallel_read_tasks=int(os.environ.get("MAX_PARALLEL_READ_TASKS", "2")),
            max_parallel_write_tasks=int(os.environ.get("MAX_PARALLEL_WRITE_TASKS", "1")),
            max_context_tokens=int(os.environ.get("MAX_CONTEXT_TOKENS", "12000")),
            max_task_duration_seconds=int(os.environ.get("MAX_TASK_DURATION", "900")),
        )


class ContinuousDevRuntime:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig.build()
        self.runtime_dir = self.config.runtime_dir
        self.db_path = self.config.db_path
        self.agent_workspace = self.config.agent_workspace

    def initialize(self) -> dict[str, Any]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_agent_workspace()
        with self.connect() as connection:
            self._ensure_schema(connection)
            self._ensure_default_settings(connection)
            self._record_event(connection, service="runtime", action="initialize", result="ok", message="Runtime initialized.")
        return self.status()

    def connect(self) -> sqlite3.Connection:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def add_idea(
        self,
        original_text: str,
        *,
        author: str = "the owner",
        source: str = "openwebui",
        conversation_id: str = "",
        project: str = "FractalOS",
        module: str = "",
        category: str = "feature",
        tags: list[str] | None = None,
        priority_manual: int = 0,
        urgency: int = 5,
        impact: int = 5,
        strategic_value: int = 5,
        effort: int = 5,
        risk: int = 3,
        confidence: float = 0.75,
        dependencies: list[str] | None = None,
        related: list[str] | None = None,
    ) -> dict[str, Any]:
        if not original_text.strip():
            raise ValueError("Idea text is required.")
        self.initialize()
        title = self._title_from_text(original_text)
        description = self._description_from_text(original_text)
        tags = tags or self._tags_from_text(original_text)
        dependencies = dependencies or []
        related = related or []
        now = utc_now()
        with self.connect() as connection:
            idea_id = self._next_id(connection, "ideas", "IDEA")
            score = self.calculate_priority(
                priority_manual=priority_manual,
                urgency=urgency,
                impact=impact,
                strategic_value=strategic_value,
                effort=effort,
                risk=risk,
                confidence=confidence,
                dependencies=dependencies,
                status="Inbox",
            )
            history = [{"at": now, "action": "created", "source": source, "message": original_text}]
            connection.execute(
                """
                INSERT INTO ideas(
                    id, original_text, title, description, author, source, conversation_id,
                    created_at, updated_at, project, module, category, tags_json,
                    priority_manual, priority_calculated, urgency, impact, strategic_value,
                    effort, risk, confidence, dependencies_json, related_json, plans_json,
                    tasks_json, status, history_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    idea_id,
                    original_text,
                    title,
                    description,
                    author,
                    source,
                    conversation_id,
                    now,
                    now,
                    project,
                    module,
                    category,
                    json.dumps(tags, ensure_ascii=False),
                    priority_manual,
                    score["score"],
                    urgency,
                    impact,
                    strategic_value,
                    effort,
                    risk,
                    confidence,
                    json.dumps(dependencies, ensure_ascii=False),
                    json.dumps(related, ensure_ascii=False),
                    "[]",
                    "[]",
                    "Inbox",
                    json.dumps(history, ensure_ascii=False),
                ),
            )
            self._store_priority_score(connection, target_type="idea", target_id=idea_id, score=score)
            self._record_event(connection, service="idea-inbox", action="add_idea", result="ok", idea_id=idea_id, message=title)
            return self.get_idea(idea_id, connection=connection)

    def get_idea(self, idea_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = connection is None
        conn = connection or self.connect()
        try:
            row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
            if row is None:
                raise KeyError(f"Idea not found: {idea_id}")
            return self._idea_from_row(row)
        finally:
            if owns_connection:
                conn.close()

    def list_ideas(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM ideas WHERE status = ? ORDER BY priority_calculated DESC, created_at ASC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM ideas ORDER BY priority_calculated DESC, created_at ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._idea_from_row(row) for row in rows]

    def update_idea_status(self, idea_id: str, status: str, *, reason: str = "") -> dict[str, Any]:
        if status not in IDEA_STATUSES:
            raise ValueError(f"Invalid idea status: {status}")
        with self.connect() as connection:
            idea = self.get_idea(idea_id, connection=connection)
            history = idea["history"] + [{"at": utc_now(), "action": "status", "status": status, "reason": reason}]
            connection.execute(
                "UPDATE ideas SET status = ?, updated_at = ?, history_json = ? WHERE id = ?",
                (status, utc_now(), json.dumps(history, ensure_ascii=False), idea_id),
            )
            self._record_event(connection, service="idea-inbox", action="update_status", result="ok", idea_id=idea_id, message=status)
            return self.get_idea(idea_id, connection=connection)

    def increase_urgency(self, idea_id: str, amount: int = 2) -> dict[str, Any]:
        with self.connect() as connection:
            idea = self.get_idea(idea_id, connection=connection)
            urgency = min(10, int(idea["urgency"]) + amount)
            score = self.calculate_priority(
                priority_manual=idea["priority_manual"],
                urgency=urgency,
                impact=idea["impact"],
                strategic_value=idea["strategic_value"],
                effort=idea["effort"],
                risk=idea["risk"],
                confidence=idea["confidence"],
                dependencies=idea["dependencies"],
                status=idea["status"],
            )
            history = idea["history"] + [{"at": utc_now(), "action": "urgency+", "new_urgency": urgency}]
            connection.execute(
                "UPDATE ideas SET urgency = ?, priority_calculated = ?, updated_at = ?, history_json = ? WHERE id = ?",
                (urgency, score["score"], utc_now(), json.dumps(history, ensure_ascii=False), idea_id),
            )
            self._store_priority_score(connection, target_type="idea", target_id=idea_id, score=score)
            return self.get_idea(idea_id, connection=connection)

    def plan_idea(self, idea_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            idea = self.get_idea(idea_id, connection=connection)
            plan_id = self._next_id(connection, "plans", "PLAN")
            body = self._render_plan(idea)
            connection.execute(
                """
                INSERT INTO plans(id, idea_id, task_id, title, body, status, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (plan_id, idea_id, "", f"Plan - {idea['title']}", body, "AwaitingApproval", utc_now(), utc_now()),
            )
            plans = idea["plans"] + [plan_id]
            history = idea["history"] + [{"at": utc_now(), "action": "planned", "plan_id": plan_id}]
            connection.execute(
                "UPDATE ideas SET status = ?, plans_json = ?, history_json = ?, updated_at = ? WHERE id = ?",
                ("AwaitingApproval", json.dumps(plans), json.dumps(history, ensure_ascii=False), utc_now(), idea_id),
            )
            approval = self._create_approval(
                connection,
                target_type="plan",
                target_id=plan_id,
                title=f"Approuver {idea['title']}",
                description="Validation requise avant creation de tache executable.",
                risk="medium",
            )
            self._record_event(connection, service="planning", action="plan_idea", result="ok", idea_id=idea_id, message=plan_id)
            return {"plan": self._plan_from_row(connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()), "approval": approval}

    def approve_idea(self, idea_id: str, *, decided_by: str = "the owner") -> dict[str, Any]:
        with self.connect() as connection:
            idea = self.get_idea(idea_id, connection=connection)
            if not idea["plans"]:
                self.plan_idea(idea_id)
                idea = self.get_idea(idea_id, connection=connection)
            task = self._create_task_from_idea(connection, idea)
            history = idea["history"] + [{"at": utc_now(), "action": "approved", "task_id": task["id"], "by": decided_by}]
            connection.execute(
                "UPDATE ideas SET status = ?, tasks_json = ?, history_json = ?, updated_at = ? WHERE id = ?",
                ("Ready", json.dumps(idea["tasks"] + [task["id"]]), json.dumps(history, ensure_ascii=False), utc_now(), idea_id),
            )
            connection.execute(
                """
                UPDATE approvals SET status = ?, decided_at = ?, decided_by = ?
                WHERE target_id IN (SELECT id FROM plans WHERE idea_id = ?) AND status = 'Pending'
                """,
                ("Approved", utc_now(), decided_by, idea_id),
            )
            self._record_event(connection, service="approval", action="approve_idea", result="ok", idea_id=idea_id, task_id=task["id"])
            return {"idea": self.get_idea(idea_id, connection=connection), "task": task}

    def list_queue(self, *, limit: int = 20) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('Ready','Queued','Blocked','InProgress','Testing','Validation')
                ORDER BY
                    CASE queue
                        WHEN 'Critical' THEN 0
                        WHEN 'Urgent' THEN 1
                        WHEN 'HighPriority' THEN 2
                        WHEN 'Normal' THEN 3
                        WHEN 'Maintenance' THEN 4
                        WHEN 'Documentation' THEN 5
                        WHEN 'Experiments' THEN 6
                        ELSE 7
                    END,
                    priority_score DESC,
                    created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._task_from_row(row) for row in rows]

    def run_cycle(self, *, max_steps: int = 1, wait_seconds: float = 0.0) -> dict[str, Any]:
        self.initialize()
        results: list[dict[str, Any]] = []
        for _ in range(max_steps):
            state = self._runtime_state()
            if state["emergency_stop"]:
                break
            if state["paused"]:
                break
            self.import_ready_ideas()
            task = self._next_ready_task()
            if task is None:
                self._maybe_wait(wait_seconds)
                break
            result = self.execute_task(task["id"])
            results.append(result)
            if self._runtime_state()["stop_after_current"]:
                self.pause_runtime(reason="stop-after-current reached")
                break
        return {"action": "run_cycle", "executions": results, "status": self.status()}

    def execute_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            task = self._get_task(connection, task_id)
            if task["status"] == "Blocked":
                return {"status": "skipped", "reason": task["blocked_reason"], "task": task}
            execution_id = self._next_id(connection, "executions", "EXEC")
            context = self.create_context_package(task_id, connection=connection)
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                ("InProgress", utc_now(), task_id),
            )
            connection.execute(
                """
                INSERT INTO executions(id, task_id, status, started_at, completed_at, result_summary, sandbox_path, context_package_id)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (execution_id, task_id, "Running", utc_now(), "", "", "", context["id"]),
            )
            self._record_event(connection, service="coding-agent", action="start_task", result="ok", task_id=task_id, execution_id=execution_id)

        sandbox = self._prepare_demo_repository(task_id)
        output = self._apply_safe_demo_change(sandbox, task_id)
        validation = run_command(["python", "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=sandbox, timeout=90)
        status = "Completed" if output["success"] and validation["success"] else "Failed"
        summary = "Demo repository task completed and tests passed." if status == "Completed" else "Demo repository task failed validation."
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), task_id),
            )
            connection.execute(
                "UPDATE executions SET status = ?, completed_at = ?, result_summary = ?, sandbox_path = ? WHERE id = ?",
                (status, utc_now(), summary, str(sandbox), execution_id),
            )
            connection.execute(
                """
                INSERT INTO validation_reports(id, task_id, execution_id, status, command, output, created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    self._next_id(connection, "validation_reports", "VAL"),
                    task_id,
                    execution_id,
                    "passed" if validation["success"] else "failed",
                    "python -m unittest discover -s tests -q",
                    json.dumps(validation, ensure_ascii=False),
                    utc_now(),
                ),
            )
            self._record_execution_event(
                connection,
                execution_id=execution_id,
                task_id=task_id,
                action="validate",
                result="passed" if validation["success"] else "failed",
                message=summary,
                payload={"sandbox": str(sandbox), "validation": validation},
            )
            memory = self.compact_context(task_id, execution_id=execution_id, connection=connection)
            self._record_event(connection, service="scheduler", action="complete_task", result=status, task_id=task_id, execution_id=execution_id)
        return {
            "task_id": task_id,
            "execution_id": execution_id,
            "status": status,
            "summary": summary,
            "sandbox": str(sandbox),
            "validation": validation,
            "memory_summary": memory,
        }

    def create_context_package(self, task_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = connection is None
        conn = connection or self.connect()
        try:
            task = self._get_task(conn, task_id)
            idea = self.get_idea(task["idea_id"], connection=conn) if task["idea_id"] else {}
            active_docs = self._select_relevant_documents(task)
            package_id = self._next_id(conn, "context_packages", "CTX")
            content = {
                "task": {
                    "id": task["id"],
                    "title": task["title"],
                    "description": task["description"],
                    "acceptance": task["acceptance"],
                    "dependencies": task["dependencies"],
                    "queue": task["queue"],
                    "priority_score": task["priority_score"],
                },
                "idea": {
                    "id": idea.get("id", ""),
                    "original_text": idea.get("original_text", ""),
                    "status": idea.get("status", ""),
                },
                "documents": active_docs,
                "budgets": {
                    "max_context_tokens": self.config.max_context_tokens,
                    "max_files": 12,
                    "max_log_chars": 8000,
                    "dependency_depth": 1,
                },
            }
            conn.execute(
                """
                INSERT INTO context_packages(id, task_id, created_at, token_budget, char_budget, file_budget, content_json, provenance_json)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    package_id,
                    task_id,
                    utc_now(),
                    self.config.max_context_tokens,
                    60000,
                    12,
                    json.dumps(content, ensure_ascii=False),
                    json.dumps({"source": "continuous-dev-runtime", "workspace": str(self.config.workspace_root)}, ensure_ascii=False),
                ),
            )
            return {"id": package_id, "content": content}
        finally:
            if owns_connection:
                conn.close()

    def compact_context(
        self,
        task_id: str,
        *,
        execution_id: str = "",
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        owns_connection = connection is None
        conn = connection or self.connect()
        try:
            task = self._get_task(conn, task_id)
            summary_id = self._next_id(conn, "memory_summaries", "MEMSUM")
            body = "\n".join(
                [
                    f"# Memory Summary - {task['id']}",
                    "",
                    f"Task: {task['title']}",
                    f"Status: {task['status']}",
                    f"Priority: {task['priority_score']}",
                    f"Queue: {task['queue']}",
                    f"Execution: {execution_id}",
                    "",
                    "## Decisions",
                    "- Sources complètes conservees sur disque.",
                    "- Contexte actif compacte apres validation.",
                    "- Restauration disponible via l'identifiant de memoire.",
                ]
            )
            path = self.agent_workspace / "memory" / f"{summary_id}.md"
            write_text(path, body)
            conn.execute(
                """
                INSERT INTO memory_summaries(id, memory_item_id, level, summary, provenance_json, confidence, restorable, created_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    summary_id,
                    task_id,
                    "ProjectCompacted",
                    body,
                    json.dumps(
                        {
                            "task_id": task_id,
                            "execution_id": execution_id,
                            "path": str(path),
                            "workspace": str(self.config.workspace_root),
                        },
                        ensure_ascii=False,
                    ),
                    0.86,
                    1,
                    utc_now(),
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_items(id, level, title, body, source_type, source_id, provenance_json, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    self._next_id(conn, "memory_items", "MEM"),
                    "Archive",
                    f"Execution archive {task_id}",
                    body,
                    "execution",
                    execution_id,
                    json.dumps({"summary_id": summary_id, "task_id": task_id}, ensure_ascii=False),
                    utc_now(),
                    utc_now(),
                ),
            )
            return {"id": summary_id, "path": str(path), "level": "ProjectCompacted", "restorable": True}
        finally:
            if owns_connection:
                conn.close()

    def memory_status(self) -> dict[str, Any]:
        self.initialize()
        with self.connect() as connection:
            levels = {}
            for level in MEMORY_LEVELS:
                levels[level] = {
                    "items": connection.execute("SELECT COUNT(*) FROM memory_items WHERE level = ?", (level,)).fetchone()[0],
                    "summaries": connection.execute("SELECT COUNT(*) FROM memory_summaries WHERE level = ?", (level,)).fetchone()[0],
                }
            return {"levels": levels, "workspace": str(self.agent_workspace / "memory")}

    def restore_memory(self, memory_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM memory_summaries WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(f"Memory summary not found: {memory_id}")
            provenance = read_json(row["provenance_json"], {})
            self._record_event(connection, service="memory", action="restore", result="ok", message=memory_id)
            return {
                "id": row["id"],
                "level": row["level"],
                "summary": row["summary"],
                "provenance": provenance,
                "path": provenance.get("path", ""),
            }

    def run_idea_worker(self, *, max_documents: int = 80) -> dict[str, Any]:
        self.initialize()
        findings = self._scan_for_idea_sources(max_documents=max_documents)
        generated: list[dict[str, Any]] = []
        with self.connect() as connection:
            for finding in findings[:5]:
                fingerprint = stable_hash(finding["title"] + finding["source"])
                existing = connection.execute("SELECT id FROM generated_ideas WHERE fingerprint = ?", (fingerprint,)).fetchone()
                if existing is not None:
                    continue
                idea_id = self._next_id(connection, "generated_ideas", "GENIDEA")
                priority = self.calculate_priority(
                    priority_manual=0,
                    urgency=finding["urgency"],
                    impact=finding["impact"],
                    strategic_value=7,
                    effort=finding["effort"],
                    risk=finding["risk"],
                    confidence=0.72,
                    dependencies=[],
                    status="Ready",
                )
                markdown = self._render_generated_idea_markdown(idea_id, finding, priority["score"])
                target = self.agent_workspace / "ideas" / "ready" / f"{idea_id.lower()}-{self._slug(finding['title'])}.md"
                write_text(target, markdown)
                connection.execute(
                    """
                    INSERT INTO generated_ideas(id, title, file_path, fingerprint, status, created_at, imported_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (idea_id, finding["title"], str(target), fingerprint, "ready", utc_now(), ""),
                )
                self._record_event(connection, service="idea-worker", action="generate_markdown", result="ok", message=str(target))
                generated.append({"id": idea_id, "title": finding["title"], "path": str(target), "priority": priority["score"]})
        return {"generated": generated, "ready_dir": str(self.agent_workspace / "ideas" / "ready")}

    def import_ready_ideas(self) -> dict[str, Any]:
        self.initialize()
        imported: list[dict[str, Any]] = []
        ready_dir = self.agent_workspace / "ideas" / "ready"
        analyzed_dir = self.agent_workspace / "ideas" / "analyzed"
        analyzed_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(ready_dir.glob("*.md")):
            parsed = self._parse_generated_idea(path)
            if not parsed["valid"]:
                continue
            fingerprint = stable_hash(parsed["title"] + parsed["body"])
            with self.connect() as connection:
                existing = connection.execute(
                    "SELECT id FROM ideas WHERE title = ? OR original_text LIKE ?",
                    (parsed["title"], f"%{parsed['title']}%"),
                ).fetchone()
                if existing is not None:
                    duplicates = self.agent_workspace / "ideas" / "duplicates"
                    duplicates.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), duplicates / path.name)
                    continue
            idea = self.add_idea(
                parsed["body"],
                author="idea-synthesis-worker",
                source="agent-workspace",
                project=parsed["frontmatter"].get("project", "FractalOS"),
                module=parsed["frontmatter"].get("module", ""),
                category="generated",
                tags=parsed["frontmatter"].get("tags", []),
                priority_manual=int(parsed["frontmatter"].get("priority_manual", 0) or 0),
                urgency=int(parsed["frontmatter"].get("urgency", 5) or 5),
                impact=int(parsed["frontmatter"].get("impact", 6) or 6),
                effort=int(parsed["frontmatter"].get("effort", 5) or 5),
                risk=int(parsed["frontmatter"].get("risk", 4) or 4),
                confidence=float(parsed["frontmatter"].get("confidence", 0.72) or 0.72),
                dependencies=parsed["frontmatter"].get("dependencies", []),
                related=parsed["frontmatter"].get("related", []),
            )
            imported.append({"idea": idea["id"], "title": idea["title"], "source_file": str(path), "fingerprint": fingerprint})
            shutil.move(str(path), analyzed_dir / path.name)
            with self.connect() as connection:
                connection.execute(
                    "UPDATE generated_ideas SET status = ?, imported_at = ? WHERE file_path = ?",
                    ("imported", utc_now(), str(path)),
                )
                self._record_event(connection, service="idea-import", action="import_ready", result="ok", idea_id=idea["id"])
        return {"imported": imported}

    def interpret_message(self, message: str, *, author: str = "the owner", source: str = "openwebui") -> dict[str, Any]:
        text = message.strip()
        lower = text.lower()
        if not text:
            raise ValueError("Message is empty.")
        if lower.startswith("/studio status") or "creation studio status" in lower or "statut creation studio" in lower:
            return {"intent": "creation_studio_status", "response": self.creation_studio_status()}
        if lower.startswith("/studio scenario") or "scenario creation studio" in lower or "demo creation studio" in lower:
            return {"intent": "creation_studio_scenario", "response": self.run_creation_studio_scenario()}
        if lower.startswith("/tools status") or "statut des outils" in lower or "tool customization" in lower:
            return {"intent": "tool_customization_status", "response": self.tool_customization_status()}
        if lower.startswith("/runtime status") or lower in {"/health", "status", "statut"}:
            return {"intent": "consult", "response": self.mobile_summary()}
        if lower.startswith("/runtime pause") or "pause" in lower and "idee" not in lower:
            return {"intent": "suspend", "response": self.pause_runtime(reason="mobile command")}
        if lower.startswith("/runtime resume") or "reprend" in lower or "resume" in lower:
            return {"intent": "resume", "response": self.resume_runtime()}
        if lower.startswith("/runtime stop-after-current") or "après la tâche actuelle" in lower or "apres la tache actuelle" in lower:
            return {"intent": "stop-after-current", "response": self.stop_after_current()}
        if lower.startswith("/runtime emergency-stop") or "arrêt urgence" in lower or "arret urgence" in lower:
            return {"intent": "emergency-stop", "response": self.emergency_stop()}
        if lower.startswith("/queue") or "dix tâches" in lower or "10 tâches" in lower or "priorités" in lower or "priorites" in lower:
            return {"intent": "consult", "response": self.mobile_queue(limit=10)}
        if lower.startswith("/ideas") or "idées" in lower or "idees" in lower:
            return {"intent": "consult", "response": {"ideas": self.list_ideas(limit=20)}}
        if lower.startswith("/idea-worker"):
            return {"intent": "diagnose" if "pause" in lower else "planifier", "response": self.run_idea_worker()}
        if "commence" in lower and "tâche" in lower or lower.startswith("/coder resume"):
            return {"intent": "start", "response": self.run_cycle(max_steps=1)}
        if "urgent" in lower:
            idea_text = self._extract_idea_text(text)
            idea = self.add_idea(idea_text, author=author, source=source, urgency=9, impact=8, strategic_value=8, tags=["urgent"])
            return {"intent": "add_idea", "response": {"idea": idea, "mobile": self._mobile_idea_response(idea)}}
        if "ajoute" in lower and "idée" in lower or "ajoute" in lower and "idee" in lower:
            idea = self.add_idea(self._extract_idea_text(text), author=author, source=source)
            return {"intent": "add_idea", "response": {"idea": idea, "mobile": self._mobile_idea_response(idea)}}
        if "planifie" in lower or "planifier" in lower:
            idea = self.add_idea(self._extract_idea_text(text), author=author, source=source, urgency=6, impact=7, tags=["planning"])
            plan = self.plan_idea(idea["id"])
            return {"intent": "planifier", "response": {"idea": idea, "plan": plan}}
        idea = self.add_idea(text, author=author, source=source)
        return {"intent": "add_idea", "response": {"idea": idea, "mobile": self._mobile_idea_response(idea)}}

    def creation_studio(self) -> FractalCreationStudio:
        return FractalCreationStudio(StudioConfig.build(self.runtime_dir / "creation-studio"))

    def creation_studio_status(self) -> dict[str, Any]:
        studio = self.creation_studio()
        status = studio.initialize()
        tools = studio.load_tool_runtime()
        status["toolCounts"] = {
            "tools": len(tools.get("tools", {})),
            "presets": len(tools.get("presets", {})),
            "profiles": len(tools.get("profiles", {})),
            "toolbars": len(tools.get("toolbars", {})),
        }
        status["commands"] = ["/studio status", "/studio scenario", "/tools status"]
        return status

    def run_creation_studio_scenario(self) -> dict[str, Any]:
        studio = self.creation_studio()
        result = studio.run_acceptance_scenario()
        with self.connect() as connection:
            self._record_event(
                connection,
                service="creation-studio",
                action="acceptance_scenario",
                result="ok" if result["project"]["validation"]["valid"] else "error",
                message=result["project"]["path"],
            )
        return result

    def tool_customization_status(self) -> dict[str, Any]:
        studio = self.creation_studio()
        state = studio.load_tool_runtime()
        return {
            "schemaVersion": state.get("schemaVersion"),
            "tools": len(state.get("tools", {})),
            "presets": len(state.get("presets", {})),
            "profiles": len(state.get("profiles", {})),
            "toolbars": len(state.get("toolbars", {})),
            "favorites": len(state.get("favorites", [])),
            "usageSamples": len(state.get("usage", [])),
            "recoveryProfileId": state.get("recoveryProfileId"),
        }

    def pause_runtime(self, *, reason: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            self._set_setting(connection, "runtime.paused", "true")
            self._record_event(connection, service="supervisor", action="pause", result="ok", message=reason)
        return self.status()

    def resume_runtime(self) -> dict[str, Any]:
        with self.connect() as connection:
            self._set_setting(connection, "runtime.paused", "false")
            self._set_setting(connection, "runtime.emergency_stop", "false")
            self._set_setting(connection, "runtime.stop_after_current", "false")
            self._record_event(connection, service="supervisor", action="resume", result="ok")
        return self.status()

    def stop_after_current(self) -> dict[str, Any]:
        with self.connect() as connection:
            self._set_setting(connection, "runtime.stop_after_current", "true")
            self._record_event(connection, service="supervisor", action="stop_after_current", result="ok")
        return self.status()

    def emergency_stop(self) -> dict[str, Any]:
        with self.connect() as connection:
            self._set_setting(connection, "runtime.emergency_stop", "true")
            self._set_setting(connection, "runtime.paused", "true")
            connection.execute("UPDATE tasks SET status = 'Blocked', blocked_reason = 'Runtime emergency stop' WHERE status IN ('Ready','Queued','InProgress','Testing','Validation')")
            self._record_event(connection, service="supervisor", action="emergency_stop", result="ok")
        return self.status()

    def status(self) -> dict[str, Any]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            return {
                "initialized": False,
                "runtime_dir": str(self.runtime_dir),
                "database": str(self.db_path),
                "state": {"paused": True, "emergency_stop": False, "stop_after_current": False},
            }
        with self.connect() as connection:
            state = self._runtime_state(connection)
            current = connection.execute(
                "SELECT * FROM tasks WHERE status IN ('InProgress','Testing','Validation') ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            counts = {
                "ideas": connection.execute("SELECT COUNT(*) FROM ideas").fetchone()[0],
                "tasks": connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "ready_tasks": connection.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('Ready','Queued')").fetchone()[0],
                "blocked_tasks": connection.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Blocked'").fetchone()[0],
                "completed_tasks": connection.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Completed'").fetchone()[0],
                "pending_approvals": connection.execute("SELECT COUNT(*) FROM approvals WHERE status = 'Pending'").fetchone()[0],
                "memory_summaries": connection.execute("SELECT COUNT(*) FROM memory_summaries").fetchone()[0],
            }
            health = self.health(connection=connection)
            return {
                "initialized": True,
                "name": "Fractal Continuous Development Runtime",
                "runtime_dir": str(self.runtime_dir),
                "database": str(self.db_path),
                "agent_workspace": str(self.agent_workspace),
                "state": state,
                "counts": counts,
                "current_task": self._task_from_row(current) if current else None,
                "health": health,
                "urls": {
                    "api_local": f"http://127.0.0.1:{self.config.port}",
                    "openapi": f"http://127.0.0.1:{self.config.port}/openapi.json",
                    "openwebui_local": "http://127.0.0.1:3000",
                },
            }

    def mobile_summary(self) -> str:
        status = self.status()
        task = status.get("current_task") or {}
        queue = self.list_queue(limit=1)
        next_task = queue[0] if queue else None
        return "\n".join(
            [
                f"Tache actuelle: {task.get('title', '(aucune)')}",
                f"Etat: {'Paused' if status['state'].get('paused') else 'Running'}",
                f"Priorite: {task.get('queue', '(aucune)')} - {task.get('priority_score', 0)}",
                "Projet: FractalOS",
                f"Module: {task.get('module', '(non defini)')}",
                f"Progression: {status['counts'].get('completed_tasks', 0)} terminee(s)",
                f"Etape: {task.get('status', 'idle')}",
                f"Blocage: {task.get('blocked_reason', 'aucun') or 'aucun'}",
                f"Prochaine tache: {next_task['id'] if next_task else '(aucune)'}",
            ]
        )

    def mobile_queue(self, *, limit: int = 10) -> str:
        rows = self.list_queue(limit=limit)
        if not rows:
            return "Aucune tache prete."
        return "\n".join(
            f"{index}. {task['id']} - {task['title']} - {task['priority_score']} - {task['status']}"
            for index, task in enumerate(rows, start=1)
        )

    def health(self, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = connection is None
        conn = connection or self.connect()
        try:
            tools = {name: shutil.which(name) for name in ["git", "ollama", "opencode", "aider", "docker", "wsl", "tailscale", "python", "dotnet"]}
            gpus = self.detect_gpus()
            disk = shutil.disk_usage(self.runtime_dir if self.runtime_dir.exists() else self.config.workspace_root)
            ram = self._detect_ram()
            health = {
                "database": self.db_path.exists(),
                "openwebui": self._tcp_probe("127.0.0.1", 3000),
                "api": True,
                "tools": tools,
                "gpus": gpus,
                "ram": ram,
                "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "used_percent": round(disk.used * 100 / disk.total, 2)},
                "coding_agent_gpu": self.config.coding_agent_gpu,
                "idea_agent_gpu": self.config.idea_agent_gpu,
                "limits": {
                    "max_ram_percent": self.config.max_ram_percent,
                    "max_gpu0_vram_percent": self.config.max_gpu0_vram_percent,
                    "max_gpu1_vram_percent": self.config.max_gpu1_vram_percent,
                    "max_disk_usage_percent": self.config.max_disk_usage_percent,
                },
            }
            conn.execute(
                """
                INSERT INTO system_health(id, created_at, component, status, details_json)
                VALUES(?,?,?,?,?)
                """,
                (self._next_id(conn, "system_health", "HEALTH"), utc_now(), "runtime", "ok", json.dumps(health, ensure_ascii=False)),
            )
            return health
        finally:
            if owns_connection:
                conn.close()

    def detect_gpus(self) -> list[dict[str, Any]]:
        result = run_command(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
            cwd=self.config.workspace_root,
            timeout=8,
        )
        if not result["success"]:
            return []
        gpus: list[dict[str, Any]] = []
        for line in result["stdout"].splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 5:
                gpus.append(
                    {
                        "index": parts[0],
                        "name": parts[1],
                        "memory_total_mb": int(float(parts[2] or 0)),
                        "memory_used_mb": int(float(parts[3] or 0)),
                        "temperature_c": int(float(parts[4] or 0)),
                    }
                )
        return gpus

    def calculate_priority(
        self,
        *,
        priority_manual: int,
        urgency: int,
        impact: int,
        strategic_value: int,
        effort: int,
        risk: int,
        confidence: float,
        dependencies: list[str],
        status: str,
    ) -> dict[str, Any]:
        blocking_bug = 1 if any("bug" in dependency.lower() for dependency in dependencies) else 0
        security_impact = 1 if any("security" in dependency.lower() or "secur" in dependency.lower() for dependency in dependencies) else 0
        stability_impact = 1 if urgency >= 8 else 0
        user_impact = min(10, impact)
        architectural_impact = min(10, strategic_value)
        unlocked_tasks = 0
        age_bonus = 0
        uncertainty = max(0, int((1.0 - confidence) * 10))
        dependency_penalty = len(dependencies) * 3
        readiness_bonus = 6 if status in {"Approved", "Ready", "Queued"} and not dependencies else 0
        score = (
            priority_manual * 5
            + urgency * 4
            + blocking_bug * 8
            + security_impact * 6
            + stability_impact * 5
            + user_impact * 3
            + architectural_impact * 3
            + strategic_value * 3
            + unlocked_tasks * 2
            + age_bonus
            + readiness_bonus
            - effort
            - risk * 2
            - uncertainty
            - dependency_penalty
        )
        score = max(0, min(100, int(score)))
        detail = {
            "manual_weight": priority_manual * 5,
            "urgency": urgency * 4,
            "blocking_bug": blocking_bug * 8,
            "security_impact": security_impact * 6,
            "stability_impact": stability_impact * 5,
            "user_impact": user_impact * 3,
            "architectural_impact": architectural_impact * 3,
            "strategic_value": strategic_value * 3,
            "readiness_bonus": readiness_bonus,
            "effort_penalty": -effort,
            "risk_penalty": -risk * 2,
            "uncertainty_penalty": -uncertainty,
            "dependency_penalty": -dependency_penalty,
        }
        queue = self._queue_for(score, dependencies)
        reason = f"{queue}: score {score}, urgence {urgency}, impact {impact}, dependances {len(dependencies)}."
        return {"score": score, "detail": detail, "reason": reason, "queue": queue, "ready": not dependencies}

    def backup(self, target_zip: str | Path | None = None) -> dict[str, Any]:
        self.initialize()
        target = Path(target_zip).expanduser().resolve() if target_zip else self.runtime_dir.parent / f"continuous-dev-runtime-backup-{int(time.time())}"
        archive_base = target.with_suffix("")
        archive = shutil.make_archive(str(archive_base), "zip", root_dir=self.runtime_dir)
        return {"archive": archive}

    def restore(self, archive_zip: str | Path) -> dict[str, Any]:
        archive = Path(archive_zip).expanduser().resolve()
        if not archive.exists():
            raise FileNotFoundError(str(archive))
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(archive), str(self.runtime_dir), "zip")
        return self.status()

    def openapi_spec(self) -> dict[str, Any]:
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "Fractal Continuous Dev Commander",
                "version": "0.1.0",
                "description": "Local private API for OpenWebUI, FractalOS and Tailscale devices.",
            },
            "servers": [{"url": f"http://127.0.0.1:{self.config.port}"}],
            "paths": {
                "/api/v1/health": {"get": {"operationId": "health", "summary": "Runtime health"}},
                "/api/v1/runtime/status": {"get": {"operationId": "runtime_status", "summary": "Runtime status"}},
                "/api/v1/runtime/pause": {"post": {"operationId": "runtime_pause", "summary": "Pause runtime"}},
                "/api/v1/runtime/resume": {"post": {"operationId": "runtime_resume", "summary": "Resume runtime"}},
                "/api/v1/runtime/stop-after-current": {"post": {"operationId": "runtime_stop_after_current", "summary": "Stop after current task"}},
                "/api/v1/runtime/emergency-stop": {"post": {"operationId": "runtime_emergency_stop", "summary": "Emergency stop"}},
                "/api/v1/runtime/run-cycle": {"post": {"operationId": "runtime_run_cycle", "summary": "Run scheduler cycle"}},
                "/api/v1/creation/status": {"get": {"operationId": "creation_studio_status", "summary": "Fractal Creation Studio status"}},
                "/api/v1/creation/scenario": {"post": {"operationId": "creation_studio_scenario", "summary": "Run Fractal Creation Studio acceptance scenario"}},
                "/api/v1/tools/status": {"get": {"operationId": "tool_customization_status", "summary": "Fractal Tool Customization Runtime status"}},
                "/api/v1/message": {"post": {"operationId": "send_message", "summary": "Interpret a mobile/OpenWebUI command"}},
                "/api/v1/ideas": {"get": {"operationId": "list_ideas"}, "post": {"operationId": "add_idea"}},
                "/api/v1/queue": {"get": {"operationId": "queue"}},
                "/api/v1/idea-worker/run": {"post": {"operationId": "run_idea_worker"}},
                "/api/v1/ideas/import-ready": {"post": {"operationId": "import_ready_ideas"}},
                "/api/v1/memory/status": {"get": {"operationId": "memory_status"}},
                "/api/v1/memory/compact": {"post": {"operationId": "memory_compact"}},
            },
            "components": {
                "securitySchemes": {
                    "BearerAuth": {"type": "http", "scheme": "bearer"},
                    "TokenHeader": {"type": "apiKey", "in": "header", "name": "X-Fractal-Dev-Token"},
                }
            },
            "security": [{"BearerAuth": []}, {"TokenHeader": []}],
        }

    def diagnostics_report(self) -> str:
        status = self.status()
        queue = self.list_queue(limit=10)
        memory = self.memory_status()
        lines = [
            "# Fractal Continuous Development Runtime Diagnostics",
            "",
            f"Generated: {utc_now()}",
            f"Runtime: {status['runtime_dir']}",
            f"Database: {status['database']}",
            f"Agent workspace: {status['agent_workspace']}",
            "",
            "## State",
            "",
            json.dumps(status["state"], indent=2, ensure_ascii=False),
            "",
            "## Counts",
            "",
            json.dumps(status["counts"], indent=2, ensure_ascii=False),
            "",
            "## Queue",
        ]
        lines.extend(f"- {task['id']} {task['queue']} {task['priority_score']} {task['status']} {task['title']}" for task in queue)
        lines.extend(["", "## Memory", "", json.dumps(memory, indent=2, ensure_ascii=False)])
        report = "\n".join(lines)
        report_path = self.agent_workspace / "reports" / "runtime-diagnostics.md"
        write_text(report_path, report)
        return report

    def _ensure_agent_workspace(self) -> None:
        for relative in [
            "ideas/inbox",
            "ideas/analyzed",
            "ideas/ready",
            "ideas/rejected",
            "ideas/duplicates",
            "ideas/archived",
            "plans",
            "reports",
            "memory",
            "executions",
            "sandboxes",
            "openwebui",
        ]:
            (self.agent_workspace / relative).mkdir(parents=True, exist_ok=True)

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations(id TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS repositories(id TEXT PRIMARY KEY, project_id TEXT, path TEXT NOT NULL, branch TEXT, git_head TEXT, dirty INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS ideas(
                id TEXT PRIMARY KEY,
                original_text TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                author TEXT,
                source TEXT,
                conversation_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                project TEXT,
                module TEXT,
                category TEXT,
                tags_json TEXT,
                priority_manual INTEGER,
                priority_calculated INTEGER,
                urgency INTEGER,
                impact INTEGER,
                strategic_value INTEGER,
                effort INTEGER,
                risk INTEGER,
                confidence REAL,
                dependencies_json TEXT,
                related_json TEXT,
                plans_json TEXT,
                tasks_json TEXT,
                status TEXT,
                history_json TEXT
            );
            CREATE TABLE IF NOT EXISTS idea_relations(id TEXT PRIMARY KEY, source_idea_id TEXT, target_idea_id TEXT, relation_type TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS initiatives(id TEXT PRIMARY KEY, title TEXT, description TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS epics(id TEXT PRIMARY KEY, initiative_id TEXT, title TEXT, description TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS features(id TEXT PRIMARY KEY, epic_id TEXT, title TEXT, description TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS tasks(
                id TEXT PRIMARY KEY,
                idea_id TEXT,
                feature_id TEXT,
                title TEXT,
                description TEXT,
                hierarchy_level TEXT,
                queue TEXT,
                status TEXT,
                priority_score INTEGER,
                readiness TEXT,
                dependencies_json TEXT,
                acceptance_json TEXT,
                blocked_reason TEXT,
                module TEXT,
                worktree_path TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS task_dependencies(id TEXT PRIMARY KEY, task_id TEXT, depends_on_task_id TEXT, status TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS priority_scores(id TEXT PRIMARY KEY, target_type TEXT, target_id TEXT, score INTEGER, detail_json TEXT, reason TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, idea_id TEXT, task_id TEXT, title TEXT, body TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, target_type TEXT, target_id TEXT, status TEXT, title TEXT, description TEXT, risk TEXT, requested_at TEXT, decided_at TEXT, decided_by TEXT);
            CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, task_id TEXT, status TEXT, started_at TEXT, completed_at TEXT, result_summary TEXT, sandbox_path TEXT, context_package_id TEXT);
            CREATE TABLE IF NOT EXISTS execution_events(id TEXT PRIMARY KEY, execution_id TEXT, task_id TEXT, timestamp TEXT, service TEXT, action TEXT, result TEXT, duration_ms INTEGER, gpu TEXT, model TEXT, correlation_id TEXT, message TEXT, error TEXT, payload_json TEXT);
            CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, name TEXT, role TEXT, provider TEXT, model TEXT, gpu TEXT, status TEXT, capabilities_json TEXT, logs_json TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS context_packages(id TEXT PRIMARY KEY, task_id TEXT, created_at TEXT, token_budget INTEGER, char_budget INTEGER, file_budget INTEGER, content_json TEXT, provenance_json TEXT);
            CREATE TABLE IF NOT EXISTS memory_items(id TEXT PRIMARY KEY, level TEXT, title TEXT, body TEXT, source_type TEXT, source_id TEXT, provenance_json TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS memory_summaries(id TEXT PRIMARY KEY, memory_item_id TEXT, level TEXT, summary TEXT, provenance_json TEXT, confidence REAL, restorable INTEGER, created_at TEXT);
            CREATE TABLE IF NOT EXISTS memory_relations(id TEXT PRIMARY KEY, source_memory_id TEXT, target_memory_id TEXT, relation_type TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, path TEXT, title TEXT, kind TEXT, checksum TEXT, indexed_at TEXT, summary TEXT);
            CREATE TABLE IF NOT EXISTS generated_ideas(id TEXT PRIMARY KEY, title TEXT, file_path TEXT, fingerprint TEXT UNIQUE, status TEXT, created_at TEXT, imported_at TEXT);
            CREATE TABLE IF NOT EXISTS validation_reports(id TEXT PRIMARY KEY, task_id TEXT, execution_id TEXT, status TEXT, command TEXT, output TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS git_workspaces(id TEXT PRIMARY KEY, task_id TEXT, repository_path TEXT, branch TEXT, worktree_path TEXT, base_head TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS system_health(id TEXT PRIMARY KEY, created_at TEXT, component TEXT, status TEXT, details_json TEXT);
            CREATE TABLE IF NOT EXISTS audit_events(id TEXT PRIMARY KEY, timestamp TEXT, service TEXT, agent TEXT, project TEXT, task_id TEXT, execution_id TEXT, action TEXT, result TEXT, duration_ms INTEGER, gpu TEXT, model TEXT, correlation_id TEXT, message TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS idx_ideas_status_priority ON ideas(status, priority_calculated DESC);
            CREATE INDEX IF NOT EXISTS idx_tasks_status_queue_priority ON tasks(status, queue, priority_score DESC);
            CREATE INDEX IF NOT EXISTS idx_events_task ON execution_events(task_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_memory_level ON memory_items(level);
            """
        )
        connection.execute("INSERT OR IGNORE INTO schema_migrations(id, applied_at) VALUES(?,?)", (SCHEMA_VERSION, utc_now()))
        connection.execute(
            "INSERT OR IGNORE INTO projects(id, name, description, created_at, updated_at) VALUES(?,?,?,?,?)",
            ("PROJECT-FRACTALOS", "FractalOS", "AIONE / FractalOS HUD", utc_now(), utc_now()),
        )
        connection.execute(
            "INSERT OR IGNORE INTO repositories(id, project_id, path, branch, git_head, dirty, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
            ("REPO-MAIN", "PROJECT-FRACTALOS", str(self.config.workspace_root), self._git_branch(), self._git_head(), 0, utc_now(), utc_now()),
        )

    def _ensure_default_settings(self, connection: sqlite3.Connection) -> None:
        defaults = {
            "runtime.paused": "false",
            "runtime.emergency_stop": "false",
            "runtime.stop_after_current": "false",
            "runtime.autonomy_mode": "2",
            "security.allow_push": "false",
            "security.allow_public_bind": "false",
            "coding_agent.gpu": self.config.coding_agent_gpu,
            "idea_agent.gpu": self.config.idea_agent_gpu,
            "coding_agent.model": self.config.coding_model,
            "idea_agent.model": self.config.idea_model,
        }
        for key, value in defaults.items():
            connection.execute("INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?,?,?)", (key, value, utc_now()))
        connection.execute(
            "INSERT OR REPLACE INTO agents(id, name, role, provider, model, gpu, status, capabilities_json, logs_json, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "coding-agent",
                "Continuous Coding Agent",
                "coding",
                "manual-safe-demo",
                self.config.coding_model,
                self.config.coding_agent_gpu,
                "available",
                json.dumps(["context-package", "demo-repo", "tests", "memory-compaction"]),
                "[]",
                utc_now(),
            ),
        )
        connection.execute(
            "INSERT OR REPLACE INTO agents(id, name, role, provider, model, gpu, status, capabilities_json, logs_json, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "idea-worker",
                "Idea Synthesis Worker",
                "idea",
                "local-document-synthesis",
                self.config.idea_model,
                self.config.idea_agent_gpu,
                "available",
                json.dumps(["docs-scan", "todo-detection", "markdown-generation", "no-code-write"]),
                "[]",
                utc_now(),
            ),
        )

    def _next_id(self, connection: sqlite3.Connection, table: str, prefix: str) -> str:
        rows = connection.execute(f"SELECT id FROM {table} WHERE id LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}-%",)).fetchall()
        if not rows:
            return f"{prefix}-000001"
        match = re.search(r"-(\d+)$", rows[0]["id"])
        number = int(match.group(1)) + 1 if match else 1
        return f"{prefix}-{number:06d}"

    def _record_event(
        self,
        connection: sqlite3.Connection,
        *,
        service: str,
        action: str,
        result: str,
        message: str = "",
        task_id: str = "",
        idea_id: str = "",
        execution_id: str = "",
        error: str = "",
        duration_ms: int = 0,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events(id, timestamp, service, agent, project, task_id, execution_id, action, result, duration_ms, gpu, model, correlation_id, message, error)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                self._next_id(connection, "audit_events", "AUDIT"),
                utc_now(),
                service,
                "",
                "FractalOS",
                task_id,
                execution_id,
                action,
                result,
                duration_ms,
                "",
                "",
                idea_id or task_id or execution_id,
                message,
                error,
            ),
        )

    def _record_execution_event(
        self,
        connection: sqlite3.Connection,
        *,
        execution_id: str,
        task_id: str,
        action: str,
        result: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO execution_events(id, execution_id, task_id, timestamp, service, action, result, duration_ms, gpu, model, correlation_id, message, error, payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                self._next_id(connection, "execution_events", "EVT"),
                execution_id,
                task_id,
                utc_now(),
                "coding-agent",
                action,
                result,
                0,
                self.config.coding_agent_gpu,
                self.config.coding_model,
                execution_id,
                message,
                "" if result in {"ok", "passed", "Completed"} else message,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )

    def _store_priority_score(self, connection: sqlite3.Connection, *, target_type: str, target_id: str, score: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO priority_scores(id, target_type, target_id, score, detail_json, reason, created_at) VALUES(?,?,?,?,?,?,?)",
            (
                self._next_id(connection, "priority_scores", "PRI"),
                target_type,
                target_id,
                score["score"],
                json.dumps(score["detail"], ensure_ascii=False),
                score["reason"],
                utc_now(),
            ),
        )

    def _create_approval(
        self,
        connection: sqlite3.Connection,
        *,
        target_type: str,
        target_id: str,
        title: str,
        description: str,
        risk: str,
    ) -> dict[str, Any]:
        approval_id = self._next_id(connection, "approvals", "APPROVAL")
        connection.execute(
            """
            INSERT INTO approvals(id, target_type, target_id, status, title, description, risk, requested_at, decided_at, decided_by)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (approval_id, target_type, target_id, "Pending", title, description, risk, utc_now(), "", ""),
        )
        return {
            "id": approval_id,
            "target_type": target_type,
            "target_id": target_id,
            "status": "Pending",
            "title": title,
            "risk": risk,
        }

    def _create_task_from_idea(self, connection: sqlite3.Connection, idea: dict[str, Any]) -> dict[str, Any]:
        existing = connection.execute("SELECT * FROM tasks WHERE idea_id = ? LIMIT 1", (idea["id"],)).fetchone()
        if existing is not None:
            return self._task_from_row(existing)
        priority = self.calculate_priority(
            priority_manual=idea["priority_manual"],
            urgency=idea["urgency"],
            impact=idea["impact"],
            strategic_value=idea["strategic_value"],
            effort=idea["effort"],
            risk=idea["risk"],
            confidence=idea["confidence"],
            dependencies=idea["dependencies"],
            status="Ready",
        )
        task_id = self._next_id(connection, "tasks", "TASK")
        acceptance = [
            "La tache s'execute dans un depot de test isole.",
            "Les tests du depot de test passent.",
            "Un context package est cree.",
            "Une memoire compactee est produite.",
            "Aucun push, commit ou modification du depot utilisateur n'est realise.",
        ]
        status = "Ready" if priority["ready"] else "Blocked"
        blocked_reason = "" if priority["ready"] else "Dependances non satisfaites: " + ", ".join(idea["dependencies"])
        connection.execute(
            """
            INSERT INTO tasks(id, idea_id, feature_id, title, description, hierarchy_level, queue, status, priority_score, readiness, dependencies_json, acceptance_json, blocked_reason, module, worktree_path, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id,
                idea["id"],
                "",
                idea["title"],
                idea["description"],
                "Task",
                priority["queue"],
                status,
                priority["score"],
                "ready" if priority["ready"] else "blocked",
                json.dumps(idea["dependencies"], ensure_ascii=False),
                json.dumps(acceptance, ensure_ascii=False),
                blocked_reason,
                idea["module"],
                "",
                utc_now(),
                utc_now(),
            ),
        )
        self._store_priority_score(connection, target_type="task", target_id=task_id, score=priority)
        return self._get_task(connection, task_id)

    def _runtime_state(self, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = connection is None
        conn = connection or self.connect()
        try:
            settings = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM settings").fetchall()}
            return {
                "paused": settings.get("runtime.paused", "false") == "true",
                "emergency_stop": settings.get("runtime.emergency_stop", "false") == "true",
                "stop_after_current": settings.get("runtime.stop_after_current", "false") == "true",
                "autonomy_mode": int(settings.get("runtime.autonomy_mode", "2")),
            }
        finally:
            if owns_connection:
                conn.close()

    def _set_setting(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, utc_now()),
        )

    def _next_ready_task(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            rows = self.list_queue(limit=100)
            for task in rows:
                if task["status"] not in {"Ready", "Queued"}:
                    continue
                if self._dependencies_satisfied(connection, task):
                    return task
                connection.execute(
                    "UPDATE tasks SET status = ?, blocked_reason = ?, updated_at = ? WHERE id = ?",
                    ("Blocked", "Dependances non satisfaites.", utc_now(), task["id"]),
                )
            return None

    def _dependencies_satisfied(self, connection: sqlite3.Connection, task: dict[str, Any]) -> bool:
        dependencies = task["dependencies"]
        if not dependencies:
            return True
        for dependency in dependencies:
            row = connection.execute("SELECT status FROM tasks WHERE id = ?", (dependency,)).fetchone()
            if row is None or row["status"] != "Completed":
                return False
        return True

    def _prepare_demo_repository(self, task_id: str) -> Path:
        root = self.agent_workspace / "sandboxes" / "demo_repo"
        root.mkdir(parents=True, exist_ok=True)
        write_text(
            root / "fractal_runtime_demo.py",
            """
def implemented_feature_count() -> int:
    path = __import__('pathlib').Path(__file__).with_name('implemented_features.md')
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding='utf-8').splitlines() if line.startswith('- TASK-')])
""".strip()
            + "\n",
        )
        write_text(
            root / "tests" / "test_demo.py",
            """
import unittest
from fractal_runtime_demo import implemented_feature_count


class RuntimeDemoTests(unittest.TestCase):
    def test_feature_count_is_non_negative(self):
        self.assertGreaterEqual(implemented_feature_count(), 0)


if __name__ == "__main__":
    unittest.main()
""".strip()
            + "\n",
        )
        if not (root / ".git").exists() and shutil.which("git"):
            run_command(["git", "init"], cwd=root, timeout=15)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO git_workspaces(id, task_id, repository_path, branch, worktree_path, base_head, status, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"GW-{task_id}",
                    task_id,
                    str(root),
                    f"cdr/{task_id.lower()}",
                    str(root),
                    "",
                    "prepared",
                    utc_now(),
                    utc_now(),
                ),
            )
        return root

    def _apply_safe_demo_change(self, sandbox: Path, task_id: str) -> dict[str, Any]:
        feature_log = sandbox / "implemented_features.md"
        existing = feature_log.read_text(encoding="utf-8") if feature_log.exists() else "# Implemented Features\n\n"
        line = f"- {task_id}: executed by Fractal Continuous Development Runtime at {utc_now()}\n"
        if line not in existing:
            write_text(feature_log, existing.rstrip() + "\n" + line)
        return {"success": True, "changed_files": [str(feature_log)]}

    def _scan_for_idea_sources(self, *, max_documents: int) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        candidates = list(self.config.workspace_root.glob("*.md")) + list((self.config.workspace_root / "docs").rglob("*.md"))
        for path in candidates[:max_documents]:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            checksum = stable_hash(text)
            with self.connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO documents(id, path, title, kind, checksum, indexed_at, summary) VALUES(?,?,?,?,?,?,?)",
                    (stable_hash(str(path)), str(path), path.stem, "markdown", checksum, utc_now(), text[:500]),
                )
            for line in text.splitlines():
                if re.search(r"TODO|FIXME|incomplet|manquant|absent|bloque", line, flags=re.IGNORECASE):
                    title = self._title_from_text(line)
                    findings.append(
                        {
                            "title": title,
                            "source": str(path),
                            "problem": line.strip()[:500],
                            "urgency": 7 if "bloqu" in line.lower() else 5,
                            "impact": 7,
                            "effort": 5,
                            "risk": 4,
                            "tags": ["idea-worker", "todo-scan"],
                        }
                    )
                    break
        if not findings:
            findings.append(
                {
                    "title": "Inspecteur graphique de la memoire cyclique",
                    "source": "idea-worker-default",
                    "problem": "Le runtime a besoin d'un panneau de diagnostic pour inspecter focus, session active, projet chaud, compactage et archive.",
                    "urgency": 6,
                    "impact": 8,
                    "effort": 5,
                    "risk": 4,
                    "tags": ["memory", "runtime", "hud"],
                }
            )
        return findings

    def _render_generated_idea_markdown(self, idea_id: str, finding: dict[str, Any], priority: int) -> str:
        tags = finding.get("tags", ["runtime"])
        return "\n".join(
            [
                "---",
                f"id: {idea_id}",
                f"title: {finding['title']}",
                "status: ready",
                "project: FractalOS",
                "module: Runtime.Memory",
                f"created_at: {utc_now()}",
                "source: idea-synthesis-agent",
                "priority_manual: 0",
                f"priority_suggested: {priority}",
                f"urgency: {finding['urgency']}",
                f"impact: {finding['impact']}",
                f"effort: {finding['effort']}",
                f"risk: {finding['risk']}",
                "confidence: 0.72",
                "dependencies: []",
                "related: []",
                "tags:",
                *[f"  - {tag}" for tag in tags],
                "---",
                "",
                "# Resume",
                "",
                finding["title"],
                "",
                "# Probleme observe",
                "",
                finding["problem"],
                "",
                "# Objectif",
                "",
                "Transformer cette observation en tache executable, testable et documentee.",
                "",
                "# Perimetre",
                "",
                "- analyse du module concerne;",
                "- implementation minimale;",
                "- tests de validation;",
                "- documentation du comportement.",
                "",
                "# Non-objectifs",
                "",
                "- modification hors workspace;",
                "- push automatique;",
                "- suppression definitive de sources.",
                "",
                "# Plan propose",
                "",
                "1. Construire un contexte minimal.",
                "2. Identifier les fichiers cibles.",
                "3. Proposer le patch.",
                "4. Lancer les tests.",
                "5. Compacter le contexte.",
                "",
                "# Criteres d'acceptation",
                "",
                "- la tache est tracable;",
                "- les tests passent;",
                "- la provenance est conservee;",
                "- aucun secret n'est lu.",
                "",
                "# Risques",
                "",
                "- doublon avec une fonctionnalite existante;",
                "- effort sous-estime;",
                "- contexte trop large.",
                "",
                "# Tests requis",
                "",
                "- test API;",
                "- test de persistence;",
                "- test de priorite.",
                "",
            ]
        )

    def _parse_generated_idea(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {"valid": False, "reason": "missing frontmatter"}
        _, front, body = text.split("---", 2)
        frontmatter: dict[str, Any] = {}
        current_list: str | None = None
        for raw in front.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            if line.startswith("  - ") and current_list:
                frontmatter.setdefault(current_list, []).append(line[4:].strip())
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                current_list = None
                if value == "[]":
                    frontmatter[key] = []
                elif value == "":
                    frontmatter[key] = []
                    current_list = key
                else:
                    frontmatter[key] = value
        title = str(frontmatter.get("title") or path.stem)
        return {"valid": True, "frontmatter": frontmatter, "title": title, "body": body.strip()}

    def _select_relevant_documents(self, task: dict[str, Any]) -> list[dict[str, str]]:
        docs = []
        for path in [self.config.workspace_root / "README.md", self.config.workspace_root / "AGENTS.md", self.config.workspace_root / "PROJECT_MAP.md"]:
            if path.exists():
                docs.append({"path": str(path), "summary": path.read_text(encoding="utf-8", errors="ignore")[:1200]})
        return docs

    def _get_task(self, connection: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return self._task_from_row(row)

    def _idea_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["tags"] = read_json(item.pop("tags_json", "[]"), [])
        item["dependencies"] = read_json(item.pop("dependencies_json", "[]"), [])
        item["related"] = read_json(item.pop("related_json", "[]"), [])
        item["plans"] = read_json(item.pop("plans_json", "[]"), [])
        item["tasks"] = read_json(item.pop("tasks_json", "[]"), [])
        item["history"] = read_json(item.pop("history_json", "[]"), [])
        return item

    def _task_from_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        item = dict(row)
        item["dependencies"] = read_json(item.pop("dependencies_json", "[]"), [])
        item["acceptance"] = read_json(item.pop("acceptance_json", "[]"), [])
        return item

    def _plan_from_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        return dict(row) if row is not None else {}

    def _render_plan(self, idea: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# Plan - {idea['title']}",
                "",
                "## Hierarchie",
                "",
                "Vision: FractalOS autonome et persistant",
                "Initiative: Continuous Development Runtime",
                "Epic: Runtime local agentique",
                "Feature: " + idea["title"],
                "Task: " + idea["description"],
                "",
                "## Critères d'acceptation",
                "",
                "- idée persistée sans écraser le texte original;",
                "- priorité calculée et explicable;",
                "- tâche créée uniquement après approbation;",
                "- exécution sur dépôt de test isolé;",
                "- tests lancés et rapport enregistrés;",
                "- contexte compacté avec provenance.",
                "",
                "## Risques",
                "",
                "- doublon avec un module existant;",
                "- dépendances non satisfaites;",
                "- coût trop élevé pour une boucle continue.",
            ]
        )

    def _queue_for(self, score: int, dependencies: list[str]) -> str:
        if dependencies:
            return "Deferred"
        if score >= 90:
            return "Critical"
        if score >= 75:
            return "Urgent"
        if score >= 60:
            return "HighPriority"
        if score >= 35:
            return "Normal"
        return "Deferred"

    def _title_from_text(self, text: str) -> str:
        cleaned = re.sub(r"^\s*(ajoute|planifie|cette idee est urgente|cette idée est urgente)\s*:?", "", text, flags=re.IGNORECASE).strip()
        cleaned = cleaned.replace("à la liste", "").replace("a la liste", "").strip(" :.-")
        words = cleaned.split()
        title = " ".join(words[:10]) if words else "Idee FractalOS"
        return title[:90].strip().capitalize()

    def _description_from_text(self, text: str) -> str:
        return text.strip()

    def _tags_from_text(self, text: str) -> list[str]:
        lower = text.lower()
        tags = []
        for key in ["hud", "memoire", "memory", "runtime", "plugin", "console", "git", "openwebui", "ollama", "agent"]:
            if key in lower:
                tags.append(key)
        return tags or ["inbox"]

    def _extract_idea_text(self, text: str) -> str:
        if ":" in text:
            return text.split(":", 1)[1].strip()
        return text.strip()

    def _mobile_idea_response(self, idea: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"Idee: {idea['id']}",
                f"Titre: {idea['title']}",
                f"Score: {idea['priority_calculated']}",
                f"Statut: {idea['status']}",
                f"Urgence: {idea['urgency']}",
            ]
        )

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:60] or "idea"

    def _maybe_wait(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def _git_branch(self) -> str:
        result = run_command(["git", "branch", "--show-current"], cwd=self.config.workspace_root, timeout=8)
        return result["stdout"].strip() if result["success"] else ""

    def _git_head(self) -> str:
        result = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=self.config.workspace_root, timeout=8)
        return result["stdout"].strip() if result["success"] else ""

    def _tcp_probe(self, host: str, port: int) -> bool:
        import socket

        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def _detect_ram(self) -> dict[str, Any]:
        if os.name == "nt":
            result = run_command(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json"],
                cwd=self.config.workspace_root,
                timeout=8,
            )
            if result["success"]:
                try:
                    data = json.loads(result["stdout"])
                    total = int(data.get("TotalVisibleMemorySize", 0)) * 1024
                    free = int(data.get("FreePhysicalMemory", 0)) * 1024
                    return {"total": total, "free": free, "used_percent": round((total - free) * 100 / total, 2) if total else 0}
                except (ValueError, TypeError, json.JSONDecodeError):
                    pass
        return {"total": 0, "free": 0, "used_percent": 0}
