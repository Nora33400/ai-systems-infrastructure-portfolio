import { readFileSync } from "node:fs";
import { parse, parseDocument } from "yaml";
import type { AcceptanceCriterion, AutonomyConfig, TaskRecord, TaskStatus } from "./types.js";
import { StateStore } from "./state-store.js";
import { WorkspaceWriter } from "./workspace-writer.js";

interface RawQueueTask {
  id?: string;
  title?: string;
  module?: string;
  description?: string;
  reason?: string;
  dependencies?: string[];
  depends_on?: string[];
  priority?: string | number;
  status?: string;
  acceptance?: unknown[];
  acceptance_criteria?: unknown[];
  likely_files?: string[];
  files?: string[];
  source_refs?: string[];
  autonomy_eligible?: boolean;
  objective?: string;
  project?: string;
  risk_level?: string;
  parent_task?: string | null;
  subtask_depth?: number;
  assigned_agent?: string;
  required_supervisor?: string | null;
  required_validator?: string | null;
  allowed_paths?: string[];
  forbidden_paths?: string[];
  allowed_commands?: string[];
  context_requirements?: string[];
  resource_budget?: TaskRecord["resource_budget"];
  retry_policy?: Partial<TaskRecord["retry_policy"]>;
  next_retry_at?: string | null;
  trello?: Partial<TaskRecord["trello"]>;
  isolation?: Partial<TaskRecord["isolation"]>;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

interface RawQueue {
  schema_version?: number;
  tasks?: RawQueueTask[];
  [key: string]: unknown;
}

const ACCEPTANCE_TYPES = new Set([
  "file_exists", "file_contains", "file_not_contains",
  "command_succeeds", "docs_validate", "tests_pass",
]);

function priorityValue(value: string | number | undefined): number {
  if (typeof value === "number") return value;
  const match = /^P(\d+)$/i.exec(value ?? "P9");
  return match ? Math.max(0, 100 - Number(match[1]) * 20) : 0;
}

function statusValue(value: string | undefined, eligible: boolean, planningFormat: boolean): TaskStatus {
  const normalized = (value ?? "").toUpperCase();
  const planningStatuses = new Set([
    "DISCOVERED", "NEEDS_CONTEXT", "READY_LOCAL_AI", "RUNNING_LOCAL_AI",
    "READY_CODEX_REVIEW", "RUNNING_CODEX_REVIEW", "NEEDS_CHATGPT_REVIEW",
    "NEEDS_OWNER_DECISION", "BLOCKED", "FAILED_RETRYABLE", "FAILED_FINAL",
    "VALIDATED", "COMPLETED", "ARCHIVED", "CANCELLED",
  ]);
  if (planningFormat && planningStatuses.has(normalized)) return normalized as TaskStatus;
  if (normalized === "COMPLETED") return "completed";
  if (normalized === "CANCELLED") return "cancelled";
  if (normalized === "QUARANTINED") return "quarantined";
  if (normalized === "READY" && eligible) return "ready";
  if (normalized === "BLOCKED") return "blocked";
  return eligible ? "pending" : "blocked";
}

function acceptanceValue(value: unknown[] | undefined): AcceptanceCriterion[] {
  if (!value) return [];
  return value.filter((entry): entry is AcceptanceCriterion => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return false;
    const type = (entry as { type?: unknown }).type;
    return typeof type === "string" && ACCEPTANCE_TYPES.has(type);
  });
}

export class TaskImporter {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly store: StateStore,
    private readonly writer: WorkspaceWriter,
  ) {}

  import(): TaskRecord[] {
    const queue = parse(readFileSync(this.config.runtime.work_queue, "utf8")) as RawQueue;
    const imported: TaskRecord[] = [];
    for (const raw of queue.tasks ?? []) {
      if (!raw.id || !raw.title) continue;
      const eligible = raw.autonomy_eligible === true;
      const planningFormat = raw.objective !== undefined || raw.risk_level !== undefined || raw.assigned_agent !== undefined;
      const importedStatus = statusValue(raw.status, eligible, planningFormat);
      const now = new Date().toISOString();
      const task: TaskRecord = {
        id: raw.id,
        title: raw.title,
        module: raw.module ?? "project-documentation",
        description: raw.description ?? raw.reason ?? raw.title,
        dependencies: [...(raw.dependencies ?? raw.depends_on ?? [])],
        priority: priorityValue(raw.priority),
        status: importedStatus,
        acceptance: acceptanceValue(raw.acceptance),
        acceptance_criteria: [...(raw.acceptance_criteria ?? raw.acceptance ?? [])],
        likely_files: [...(raw.likely_files ?? raw.files ?? [])],
        source_refs: [...(raw.source_refs ?? [])],
        attempts: 0,
        history: [{ timestamp: now, event: "imported_from_work_queue" }],
        blockers: eligible || importedStatus === "completed" || importedStatus === "cancelled"
          ? []
          : [{ reason: "not_explicitly_autonomy_eligible" }],
        test_results: [],
        last_agent: null,
        updated_at: now,
        autonomy_eligible: eligible,
        objective: raw.objective ?? raw.description ?? raw.reason ?? raw.title,
        project: raw.project ?? "opti",
        risk_level: (["SAFE", "CONTROLLED", "SENSITIVE", "CRITICAL"].includes(raw.risk_level ?? "") ? raw.risk_level : "CONTROLLED") as TaskRecord["risk_level"],
        parent_task: raw.parent_task ?? null,
        subtask_depth: raw.subtask_depth ?? 0,
        assigned_agent: raw.assigned_agent ?? (eligible ? "LOCAL_AI" : "UNASSIGNED"),
        required_supervisor: raw.required_supervisor ?? null,
        required_validator: raw.required_validator ?? null,
        allowed_paths: [...(raw.allowed_paths ?? raw.likely_files ?? raw.files ?? [])],
        forbidden_paths: [...(raw.forbidden_paths ?? [])],
        allowed_commands: [...(raw.allowed_commands ?? [])],
        context_requirements: [...(raw.context_requirements ?? [])],
        resource_budget: { ...(raw.resource_budget ?? {}) },
        retry_policy: {
          max_retries: raw.retry_policy?.max_retries ?? this.config.limits.max_task_retries,
          retry_delay_seconds: raw.retry_policy?.retry_delay_seconds ?? 0,
          retryable_errors: [...(raw.retry_policy?.retryable_errors ?? [])],
        },
        next_retry_at: raw.next_retry_at ?? null,
        trello: {
          card_id: raw.trello?.card_id ?? null,
          sync_enabled: raw.trello?.sync_enabled ?? false,
        },
        isolation: {
          enabled: raw.isolation?.enabled ?? false,
          cleanup_on_success: raw.isolation?.cleanup_on_success ?? true,
        },
        created_at: raw.created_at ?? now,
      };
      imported.push(this.store.importTask(task));
    }
    return imported;
  }

  async sync(task: TaskRecord): Promise<void> {
    const source = readFileSync(this.config.runtime.work_queue, "utf8");
    const document = parseDocument(source);
    const tasks = document.get("tasks") as { items?: Array<{ get(key: string): unknown; set(key: string, value: unknown): void }> } | undefined;
    const raw = tasks?.items?.find((entry) => entry.get("id") === task.id);
    if (!raw) return;
    raw.set("status", task.status.toUpperCase());
    raw.set("execution_result", task.result ? {
      attempts: task.attempts,
      summary: task.result.summary,
      modified_files: task.result.modified_files,
      validation_passed: task.result.validation.every((result) => result.passed),
      validation_count: task.result.validation.length,
      commit: task.result.commit,
      updated_at: task.updated_at,
    } : {
      attempts: task.attempts,
      blockers: task.blockers,
      validation_count: task.test_results.length,
      updated_at: task.updated_at,
    });
    for (const entry of tasks?.items ?? []) {
      const queuedId = entry.get("id");
      if (typeof queuedId !== "string" || queuedId === task.id) continue;
      const stored = this.store.getTask(queuedId);
      if (!stored?.result) continue;
      entry.set("execution_result", {
        attempts: stored.attempts,
        summary: stored.result.summary,
        modified_files: stored.result.modified_files,
        validation_passed: stored.result.validation.every((result) => result.passed),
        validation_count: stored.result.validation.length,
        commit: stored.result.commit,
        updated_at: stored.updated_at,
      });
    }
    document.set("updated_at", new Date().toISOString().slice(0, 10));
    await this.writer.writeFile(this.config.runtime.work_queue, document.toString({ lineWidth: 0 }));
  }
}
