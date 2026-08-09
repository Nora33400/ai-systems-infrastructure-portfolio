import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { createHash } from "node:crypto";
import { PLANNING_TASK_STATUSES, type AutonomyReceipt, type ExecutionRecord, type ReadOnlyReportRecord, type TaskRecord, type TaskStatus } from "./types.js";
import { TaskStateMachine } from "./task-state-machine.js";
import { normalizeResourceKey, resourceKeysConflict } from "./resource-locks.js";
import { DirectionsRegistry, type DirectionRecord, type DirectionStatus } from "./directions-registry.js";

interface TaskRow {
  data_json: string;
}

interface ReceiptRow extends TaskRow {
  receipt_id: string;
  content_hash: string;
}

interface ReadOnlyReportRow extends TaskRow {
  report_id: string;
  input_hash: string;
  output_hash: string;
  content_hash: string;
}

export interface ResourceLockRecord {
  resource_key: string;
  execution_id: string;
  acquired_at: string;
}

export class StateStore {
  private readonly db: DatabaseSync;
  private readonly stateMachine = new TaskStateMachine();
  private readonly directionsRegistry: DirectionsRegistry;

  constructor(databasePath: string) {
    mkdirSync(dirname(databasePath), { recursive: true });
    this.db = new DatabaseSync(databasePath);
    this.directionsRegistry = new DirectionsRegistry(this.db);
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA synchronous = FULL;
      CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        priority INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS tasks_status_priority ON tasks(status, priority DESC);
      CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_executions (
        execution_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        status TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS autonomy_executions_task_status ON autonomy_executions(task_id, status);
      CREATE TABLE IF NOT EXISTS autonomy_resource_locks (
        resource_key TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL,
        acquired_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_decisions (
        decision_id TEXT PRIMARY KEY,
        task_id TEXT,
        created_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_authorizations (
        authorization_id TEXT PRIMARY KEY,
        task_id TEXT,
        created_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_external_sync_changes (
        change_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS autonomy_receipts (
        receipt_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        parent_receipt TEXT,
        data_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS autonomy_receipts_task_timestamp ON autonomy_receipts(task_id, timestamp);
      CREATE TABLE IF NOT EXISTS autonomy_readonly_reports (
        report_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        model TEXT NOT NULL,
        input_hash TEXT NOT NULL,
        output_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        data_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS autonomy_readonly_reports_task_created ON autonomy_readonly_reports(task_id, created_at);
    `);
  }

  close(): void {
    this.db.close();
  }

  getTask(id: string): TaskRecord | null {
    const row = this.db.prepare("SELECT data_json FROM tasks WHERE id = ?").get(id) as TaskRow | undefined;
    return row ? (JSON.parse(row.data_json) as TaskRecord) : null;
  }

  listTasks(): TaskRecord[] {
    const rows = this.db.prepare("SELECT data_json FROM tasks ORDER BY priority DESC, id").all() as unknown as TaskRow[];
    return rows.map((row) => JSON.parse(row.data_json) as TaskRecord);
  }

  saveTask(task: TaskRecord, options: { bypassTransition?: boolean } = {}): void {
    const existing = this.getTask(task.id);
    if (existing && existing.status !== task.status && !options.bypassTransition) {
      this.stateMachine.assertTransition(existing.status, task.status);
    }
    task.updated_at = new Date().toISOString();
    this.db.prepare(`
      INSERT INTO tasks(id, status, priority, updated_at, data_json)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        status = excluded.status,
        priority = excluded.priority,
        updated_at = excluded.updated_at,
        data_json = excluded.data_json
    `).run(task.id, task.status, task.priority, task.updated_at, JSON.stringify(task));
  }

  importTask(definition: TaskRecord): TaskRecord {
    const existing = this.getTask(definition.id);
    if (!existing) {
      this.saveTask(definition);
      return definition;
    }
    const externalTerminal = ["completed", "cancelled", "COMPLETED", "CANCELLED", "ARCHIVED", "FAILED_FINAL"].includes(definition.status);
    const externalPlanningStatus = (PLANNING_TASK_STATUSES as readonly string[]).includes(definition.status);
    const runtimeActive = ["running", "testing", "reviewing", "RUNNING_LOCAL_AI", "RUNNING_CODEX_REVIEW"].includes(existing.status);
    const externalAuthoritative = externalTerminal || (externalPlanningStatus && !runtimeActive);
    const merged: TaskRecord = {
      ...definition,
      status: externalAuthoritative ? definition.status : existing.status,
      attempts: existing.attempts,
      history: existing.status !== definition.status && externalAuthoritative
        ? [...existing.history, { timestamp: new Date().toISOString(), event: "canonical_work_queue_status_imported", detail: { previous_status: existing.status, imported_status: definition.status } }]
        : existing.history,
      blockers: externalAuthoritative ? [] : existing.blockers,
      test_results: existing.test_results,
      last_agent: existing.last_agent,
      updated_at: existing.updated_at,
      ...(existing.result ? { result: existing.result } : {}),
    };
    this.saveTask(merged, { bypassTransition: externalAuthoritative });
    return merged;
  }

  transition(id: string, status: TaskStatus, event: string, detail?: unknown): TaskRecord {
    const task = this.getTask(id);
    if (!task) throw new Error(`Unknown task: ${id}`);
    this.stateMachine.assertTransition(task.status, status);
    task.status = status;
    task.history.push({
      timestamp: new Date().toISOString(),
      event,
      ...(detail === undefined ? {} : { detail }),
    });
    this.saveTask(task);
    return task;
  }

  recoverInterrupted(): TaskRecord[] {
    const interrupted = this.listTasks().filter((task) =>
      ["running", "testing", "reviewing", "RUNNING_LOCAL_AI", "RUNNING_CODEX_REVIEW"].includes(task.status),
    );
    for (const task of interrupted) {
      const previousStatus = task.status;
      task.status = previousStatus === "RUNNING_LOCAL_AI" || previousStatus === "RUNNING_CODEX_REVIEW"
        ? "FAILED_RETRYABLE"
        : "retryable_failure";
      task.history.push({
        timestamp: new Date().toISOString(),
        event: "recovered_after_interruption",
        detail: { previous_status: previousStatus },
      });
      task.next_retry_at = new Date(Date.now() + task.retry_policy.retry_delay_seconds * 1_000).toISOString();
      this.saveTask(task);
    }
    return interrupted;
  }

  startExecution(execution: ExecutionRecord): void {
    this.db.prepare(`
      INSERT INTO autonomy_executions(execution_id, task_id, status, updated_at, data_json)
      VALUES (?, ?, ?, ?, ?)
    `).run(execution.execution_id, execution.task_id, execution.status, execution.updated_at, JSON.stringify(execution));
  }

  getExecution(executionId: string): ExecutionRecord | null {
    const row = this.db.prepare("SELECT data_json FROM autonomy_executions WHERE execution_id = ?").get(executionId) as TaskRow | undefined;
    return row ? JSON.parse(row.data_json) as ExecutionRecord : null;
  }

  listExecutions(taskId?: string): ExecutionRecord[] {
    const rows = taskId
      ? this.db.prepare("SELECT data_json FROM autonomy_executions WHERE task_id = ? ORDER BY updated_at").all(taskId) as unknown as TaskRow[]
      : this.db.prepare("SELECT data_json FROM autonomy_executions ORDER BY updated_at").all() as unknown as TaskRow[];
    return rows.map((row) => JSON.parse(row.data_json) as ExecutionRecord);
  }

  updateExecution(executionId: string, update: Partial<Pick<ExecutionRecord, "status" | "finished_at" | "checkpoint" | "result">>): ExecutionRecord {
    const execution = this.getExecution(executionId);
    if (!execution) throw new Error(`Unknown execution: ${executionId}`);
    const updated: ExecutionRecord = { ...execution, ...update, updated_at: new Date().toISOString() };
    this.db.prepare("UPDATE autonomy_executions SET status = ?, updated_at = ?, data_json = ? WHERE execution_id = ?")
      .run(updated.status, updated.updated_at, JSON.stringify(updated), executionId);
    return updated;
  }

  recoverInterruptedExecutions(): ExecutionRecord[] {
    const running = this.listExecutions().filter((execution) => execution.status === "RUNNING");
    for (const execution of running) {
      this.updateExecution(execution.execution_id, {
        status: "ABANDONED",
        finished_at: new Date().toISOString(),
        result: { reason: "recovered_after_interruption" },
      });
      this.releaseResourceLocks(execution.execution_id);
    }
    return running;
  }

  acquireResourceLock(resourceKey: string, executionId: string): boolean {
    return this.acquireResourceLocks([resourceKey], executionId);
  }

  acquireResourceLocks(resourceKeys: string[], executionId: string): boolean {
    const requested = [...new Set(resourceKeys.map(normalizeResourceKey))].sort();
    if (requested.length === 0) return true;
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const existing = this.listResourceLocks().filter((lock) => lock.execution_id !== executionId);
      const conflict = requested.some((key) => existing.some((lock) => resourceKeysConflict(key, lock.resource_key)));
      if (conflict) {
        this.db.exec("ROLLBACK");
        return false;
      }
      const insert = this.db.prepare("INSERT OR IGNORE INTO autonomy_resource_locks(resource_key, execution_id, acquired_at) VALUES (?, ?, ?)");
      const acquiredAt = new Date().toISOString();
      for (const key of requested) insert.run(key, executionId, acquiredAt);
      this.db.exec("COMMIT");
      return true;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  listResourceLocks(): ResourceLockRecord[] {
    return this.db.prepare("SELECT resource_key, execution_id, acquired_at FROM autonomy_resource_locks ORDER BY resource_key")
      .all() as unknown as ResourceLockRecord[];
  }

  conflictingResourceLocks(resourceKeys: string[]): ResourceLockRecord[] {
    const requested = resourceKeys.map(normalizeResourceKey);
    return this.listResourceLocks().filter((lock) => requested.some((key) => resourceKeysConflict(key, lock.resource_key)));
  }

  releaseResourceLocks(executionId: string): void {
    this.db.prepare("DELETE FROM autonomy_resource_locks WHERE execution_id = ?").run(executionId);
  }

  saveCheckpoint(checkpointId: string, taskId: string, executionId: string, data: Record<string, unknown>): void {
    this.db.prepare(`
      INSERT INTO autonomy_checkpoints(checkpoint_id, task_id, execution_id, created_at, data_json)
      VALUES (?, ?, ?, ?, ?)
    `).run(checkpointId, taskId, executionId, new Date().toISOString(), JSON.stringify(data));
  }

  insertReceipt(receipt: AutonomyReceipt, contentHash: string): void {
    this.db.prepare(`
      INSERT INTO autonomy_receipts(receipt_id, task_id, execution_id, timestamp, content_hash, parent_receipt, data_json)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(receipt.receipt_id, receipt.task_id, receipt.execution_id, receipt.timestamp, contentHash, receipt.parent_receipt, JSON.stringify(receipt));
  }

  listReceiptRows(): Array<{ receipt: AutonomyReceipt; content_hash: string; data_json: string }> {
    const rows = this.db.prepare("SELECT receipt_id, content_hash, data_json FROM autonomy_receipts ORDER BY timestamp, receipt_id").all() as unknown as ReceiptRow[];
    return rows.map((row) => ({ receipt: JSON.parse(row.data_json) as AutonomyReceipt, content_hash: row.content_hash, data_json: row.data_json }));
  }

  lastReceiptForTask(taskId: string): AutonomyReceipt | null {
    const row = this.db.prepare("SELECT data_json FROM autonomy_receipts WHERE task_id = ? ORDER BY timestamp DESC, receipt_id DESC LIMIT 1").get(taskId) as TaskRow | undefined;
    return row ? JSON.parse(row.data_json) as AutonomyReceipt : null;
  }

  insertReadOnlyReport(report: ReadOnlyReportRecord, contentHash: string): void {
    this.db.prepare(`
      INSERT INTO autonomy_readonly_reports(
        report_id, task_id, execution_id, created_at, model,
        input_hash, output_hash, content_hash, data_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      report.report_id,
      report.task_id,
      report.execution_id,
      report.created_at,
      report.model,
      report.input_hash,
      report.output_hash,
      contentHash,
      JSON.stringify(report),
    );
  }

  listReadOnlyReports(taskId?: string): ReadOnlyReportRecord[] {
    const rows = taskId
      ? this.db.prepare("SELECT data_json FROM autonomy_readonly_reports WHERE task_id = ? ORDER BY created_at, report_id").all(taskId) as unknown as TaskRow[]
      : this.db.prepare("SELECT data_json FROM autonomy_readonly_reports ORDER BY created_at, report_id").all() as unknown as TaskRow[];
    return rows.map((row) => JSON.parse(row.data_json) as ReadOnlyReportRecord);
  }

  verifyReadOnlyReports(): { valid: boolean; count: number; issues: string[] } {
    const rows = this.db.prepare(`
      SELECT report_id, input_hash, output_hash, content_hash, data_json
      FROM autonomy_readonly_reports ORDER BY created_at, report_id
    `).all() as unknown as ReadOnlyReportRow[];
    const issues: string[] = [];
    for (const row of rows) {
      const record = JSON.parse(row.data_json) as ReadOnlyReportRecord;
      const hash = (value: string): string => createHash("sha256").update(value).digest("hex");
      if (hash(row.data_json) !== row.content_hash) issues.push(`${row.report_id}:content_hash_mismatch`);
      if (hash(JSON.stringify(record.task_package)) !== row.input_hash) issues.push(`${row.report_id}:input_hash_mismatch`);
      if (hash(JSON.stringify(record.report)) !== row.output_hash) issues.push(`${row.report_id}:output_hash_mismatch`);
      if (record.input_hash !== row.input_hash || record.output_hash !== row.output_hash) {
        issues.push(`${row.report_id}:record_hash_columns_mismatch`);
      }
    }
    return { valid: issues.length === 0, count: rows.length, issues };
  }

  setMeta(key: string, value: unknown): void {
    this.db.prepare(`
      INSERT INTO metadata(key, value) VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value = excluded.value
    `).run(key, JSON.stringify(value));
  }

  getMeta<T>(key: string): T | null {
    const row = this.db.prepare("SELECT value FROM metadata WHERE key = ?").get(key) as { value: string } | undefined;
    return row ? (JSON.parse(row.value) as T) : null;
  }

  summary(): Record<string, unknown> {
    const tasks = this.listTasks();
    const counts = Object.fromEntries(
      [...new Set(tasks.map((task) => task.status))].map((status) => [
        status,
        tasks.filter((task) => task.status === status).length,
      ]),
    );
    return {
      total: tasks.length,
      counts,
      current: tasks.find((task) => ["running", "testing", "reviewing", "RUNNING_LOCAL_AI", "RUNNING_CODEX_REVIEW"].includes(task.status))?.id ?? null,
      next_candidates: tasks
        .filter((task) => task.autonomy_eligible && ["ready", "pending", "retryable_failure", "DISCOVERED", "READY_LOCAL_AI", "FAILED_RETRYABLE"].includes(task.status))
        .sort((a, b) => b.priority - a.priority)
        .slice(0, 5)
        .map((task) => task.id),
    };
  }

  // Directions Registry wrapper methods
  createDirection(direction: Omit<DirectionRecord, 'id' | 'created_at' | 'updated_at'>): DirectionRecord {
    return this.directionsRegistry.create(direction);
  }

  getDirection(id: string): DirectionRecord | null {
    return this.directionsRegistry.get(id);
  }

  listActiveDirections(taskId?: string): DirectionRecord[] {
    return this.directionsRegistry.listActive(taskId);
  }

  updateDirectionPriority(id: string, priority: number): DirectionRecord | null {
    return this.directionsRegistry.updatePriority(id, priority);
  }

  pauseDirection(id: string): DirectionRecord | null {
    return this.directionsRegistry.pause(id);
  }

  cancelDirection(id: string): DirectionRecord | null {
    return this.directionsRegistry.cancel(id);
  }

  checkAndExpireDirections(): DirectionRecord[] {
    return this.directionsRegistry.checkAndExpire();
  }

  isDirectionUsable(id: string): boolean {
    return this.directionsRegistry.isDirectionUsable(id);
  }
}
