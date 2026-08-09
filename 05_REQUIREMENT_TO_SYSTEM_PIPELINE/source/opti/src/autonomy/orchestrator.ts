import { randomUUID } from "node:crypto";
import type {
  AgentAction,
  AutonomyConfig,
  IsolatedPatchArtifact,
  IsolatedWorkspaceMetadata,
  TaskRecord,
} from "./types.js";
import { ActionExecutor } from "./action-executor.js";
import { AgentProtocol } from "./agent-protocol.js";
import { ContextBuilder } from "./context-builder.js";
import { EventLogger } from "./event-logger.js";
import { GitManager } from "./git-manager.js";
import { OllamaClient } from "./ollama-client.js";
import { RecoveryManager } from "./recovery-manager.js";
import { Reviewer } from "./reviewer.js";
import { RuntimeLock, StopController } from "./runtime-control.js";
import { Scheduler } from "./scheduler.js";
import { StateStore } from "./state-store.js";
import { TaskImporter } from "./task-importer.js";
import { Validator } from "./validator.js";
import { IsolatedWorkspaceManager } from "./isolated-workspace-manager.js";

const CODER_SYSTEM = [
  "You are the single controlled coding worker for AIONE / La Forge.",
  "Return exactly one JSON action matching the supplied schema on every turn.",
  "Use read/search actions to inspect evidence before modifying files.",
  "Stay within the active task and likely files. Preserve user changes.",
  "Do not invent requirements or promote proposed/hypothetical concepts.",
  "Run relevant tests and inspect the actual diff before finish_task.",
  "Never repeat an identical action after it has succeeded; use the observation and advance the task.",
  "If machine acceptance reports missing or forbidden text, correct the file with evidence from the supplied likely files.",
  "A finish_task request triggers independent validation and review; it does not guarantee completion.",
  "Never include Markdown around the JSON action.",
].join("\n");

type TaskOutcome = "completed" | "failed" | "blocked" | "stopped";

export class Orchestrator {
  private completedThisSession = 0;
  private consecutiveFailures = 0;

  constructor(
    private readonly config: AutonomyConfig,
    private readonly store: StateStore,
    private readonly importer: TaskImporter,
    private readonly scheduler: Scheduler,
    private readonly contextBuilder: ContextBuilder,
    private readonly protocol: AgentProtocol,
    private readonly ollama: OllamaClient,
    private readonly executor: ActionExecutor,
    private readonly validator: Validator,
    private readonly reviewer: Reviewer,
    private readonly git: GitManager,
    private readonly recovery: RecoveryManager,
    private readonly logger: EventLogger,
    private readonly lock: RuntimeLock,
    private readonly stop: StopController,
    private readonly isolatedWorkspaces?: IsolatedWorkspaceManager,
  ) {}

  bootstrap(): Record<string, unknown> {
    this.lock.acquire();
    try {
      this.stop.assertEnabled("legacy bootstrap");
      const tasks = this.importer.import();
      const recovered = this.store.recoverInterrupted();
      const summary = this.store.summary();
      this.store.setMeta("last_bootstrap", {
        timestamp: new Date().toISOString(),
        imported: tasks.length,
        recovered: recovered.map((task) => task.id),
      });
      this.logger.log("bootstrap_completed", { imported: tasks.length, recovered: recovered.map((task) => task.id), summary });
      return summary;
    } finally {
      this.lock.release();
    }
  }

  async run(maxTasksOverride?: number): Promise<Record<string, unknown>> {
    this.lock.acquire();
    try {
      this.stop.assertEnabled("legacy run");
      const maxTasks = maxTasksOverride && maxTasksOverride > 0
        ? maxTasksOverride
        : this.config.limits.max_tasks_per_session;
      this.logger.log("engine_started", { pid: process.pid, mode: this.config.mode, max_tasks: maxTasks });
      const recovered = this.store.recoverInterrupted();
      if (recovered.length > 0) {
        this.logger.log("tasks_recovered", { task_ids: recovered.map((task) => task.id) }, { level: "warn" });
      }
      this.importer.import();
      await this.ollama.waitUntilAvailable();

      while (this.completedThisSession < maxTasks) {
        const disabled = this.stop.disabledReason();
        if (disabled) {
          this.logger.log("engine_stop_observed", { phase: "between_tasks", reason: disabled });
          break;
        }
        const decision = this.scheduler.selectNext();
        this.logger.log("scheduler_decision", {
          selected: decision.task?.id ?? null,
          considered: decision.considered,
        });
        if (!decision.task) {
          this.logger.log("engine_idle", { reason: "no_realizable_tasks" });
          break;
        }

        const outcome = await this.runTask(decision.task);
        if (outcome === "stopped") break;
        if (outcome === "completed") {
          this.completedThisSession += 1;
          this.consecutiveFailures = 0;
        } else if (outcome === "failed") {
          this.consecutiveFailures += 1;
          if (this.consecutiveFailures >= this.config.limits.max_consecutive_failures) {
            this.logger.log("engine_stopped", { reason: "max_consecutive_failures", count: this.consecutiveFailures }, { level: "error" });
            break;
          }
        }
      }

      const summary = this.store.summary();
      this.store.setMeta("last_engine_stop", {
        timestamp: new Date().toISOString(),
        completed_this_session: this.completedThisSession,
        summary,
      });
      const disabled = this.stop.disabledReason();
      this.logger.log("engine_stopped", {
        reason: disabled ?? (this.completedThisSession >= maxTasks ? "task_budget" : "queue_state"),
        completed_this_session: this.completedThisSession,
        summary,
      });
      return summary;
    } finally {
      this.lock.release();
    }
  }

  private async runTask(initial: TaskRecord): Promise<TaskOutcome> {
    const task = this.store.getTask(initial.id) ?? initial;
    task.status = "running";
    task.attempts += 1;
    task.last_agent = this.config.ollama.coder_model;
    task.history.push({
      timestamp: new Date().toISOString(),
      event: "task_started",
      detail: { attempt: task.attempts, git_snapshot: this.git.snapshot() },
    });
    this.store.saveTask(task);
    this.logger.log("task_selected", { title: task.title, attempt: task.attempts }, { taskId: task.id });

    let isolatedWorkspace: IsolatedWorkspaceMetadata | null = null;
    let taskWorkspace = this.config.workspace;
    try {
      if (task.isolation.enabled) {
        if (!this.isolatedWorkspaces) {
          throw new Error("Isolated workspace support is not configured for this runtime.");
        }
        const executionId = `EXE-${randomUUID()}`;
        isolatedWorkspace = this.isolatedWorkspaces.create({
          task_id: task.id,
          execution_id: executionId,
          allowed_paths: task.allowed_paths,
          forbidden_paths: task.forbidden_paths,
          require_clean_baseline: true,
        });
        taskWorkspace = isolatedWorkspace.worktree_path;
        task.history.push({
          timestamp: new Date().toISOString(),
          event: "isolated_workspace_created",
          detail: {
            execution_id: executionId,
            base_head: isolatedWorkspace.base_head,
            worktree_path: isolatedWorkspace.worktree_path,
          },
        });
        this.store.saveTask(task);
      } else {
        this.recovery.begin(task);
      }
    } catch (error) {
      await this.failTask(task, error, isolatedWorkspace);
      return "failed";
    }

    let context = this.contextBuilder.build(task);
    this.logger.log("context_built", { chars: context.length, likely_files: task.likely_files }, { taskId: task.id });
    let transcript = [
      "## Execution protocol",
      "Choose one action. Read the operational files before modifying them. Continue until tests and diff inspection justify finish_task.",
    ].join("\n\n");
    const successfulActionCounts = new Map<string, number>();
    let correctionMode = false;

    try {
      for (let actionIndex = 0; actionIndex < this.config.limits.max_actions_per_task; actionIndex += 1) {
        const disabled = this.stop.disabledReason();
        if (disabled) {
          this.logger.log("task_interrupted_by_stop", { action_index: actionIndex, reason: disabled }, { taskId: task.id, level: "warn" });
          task.status = "retryable_failure";
          task.history.push({ timestamp: new Date().toISOString(), event: "task_paused_by_stop", detail: { action_index: actionIndex, reason: disabled } });
          this.store.saveTask(task);
          await this.importer.sync(task);
          return "stopped";
        }
        const requestContext = correctionMode ? this.contextBuilder.buildCorrection(task) : context;
        const action = await this.ollama.structured<AgentAction>({
          model: this.config.ollama.coder_model,
          schema: correctionMode ? this.protocol.correctionSchema : this.protocol.schema,
          system: correctionMode
            ? `${CODER_SYSTEM}\nCORRECTION MODE: validation or review failed. The next action must mutate a relevant file to correct the exact failure. Copy every missing literal reported by a file_contains failure exactly, remove every literal reported by a file_not_contains failure, and preserve already-passing requirements. Report a blocker only when evidence proves mutation is impossible.`
            : CODER_SYSTEM,
          user: [
            requestContext,
            "## Recent execution",
            transcript.slice(-Math.max(4000, this.config.limits.max_context_chars - requestContext.length - 1000)),
          ].join("\n\n"),
          taskId: task.id,
          validate: (value): value is AgentAction => this.protocol.validate(value),
          validationError: () => this.protocol.errors(),
        });
        this.logger.log("action_requested", { action: action.action, action_index: actionIndex }, { taskId: task.id });

        if (action.action === "report_blocker") {
          task.status = "blocked";
          task.blockers.push(action);
          task.history.push({ timestamp: new Date().toISOString(), event: "task_blocked", detail: action });
          this.store.saveTask(task);
          await this.importer.sync(task);
          this.logger.log("task_blocked", { blocker: action }, { taskId: task.id, level: "warn" });
          return "blocked";
        }

        if (action.action === "finish_task") {
          const validationOutcome = await this.validateAndReview(
            task,
            context,
            action.summary,
            taskWorkspace,
            isolatedWorkspace,
          );
          if (validationOutcome.completed) return "completed";
          transcript = "VALIDATION OR REVIEW REJECTED:\n" + validationOutcome.feedback + "\nUse the supplied likely-file evidence and mutate the relevant file now.";
          correctionMode = true;
          context = this.contextBuilder.build(task);
          task.status = "running";
          this.store.saveTask(task);
          continue;
        }

        const observation = await this.executor.execute(action, task.id, taskWorkspace);
        task.history.push({
          timestamp: new Date().toISOString(),
          event: "action_observed",
          detail: { action: action.action, ok: observation.ok, summary: observation.summary },
        });
        this.store.saveTask(task);
        transcript += "\n\nACTION:\n" + JSON.stringify(action) + "\n\nOBSERVATION:\n" + JSON.stringify(observation);
        if (observation.ok && ["apply_patch", "create_file", "delete_file"].includes(action.action)) {
          correctionMode = false;
          context = this.contextBuilder.build(task);
        }

        const signature = JSON.stringify(action);
        const count = (successfulActionCounts.get(signature) ?? 0) + 1;
        successfulActionCounts.set(signature, count);
        if (!observation.ok && count >= 2) {
          this.logger.log("refusal_loop_guard_triggered", { signature, repetitions: count, error: observation.summary }, { taskId: task.id, level: "warn" });
          transcript = `REPEATED ACTION REFUSED: ${observation.summary}\nThe repeated action cannot make progress. Mutate the relevant file now; if it is missing, create it from the supplied likely-file evidence.`;
          correctionMode = true;
          successfulActionCounts.clear();
          continue;
        }
        if (observation.ok) {
          const threshold = action.action === "run_tests" || action.action === "run_command" ? 2 : 3;
          if (count >= threshold) {
            this.logger.log("loop_guard_triggered", { signature, repetitions: count }, { taskId: task.id, level: "warn" });
            const validationOutcome = await this.validateAndReview(
              task,
              context,
              "Completion requested by the duplicate-success loop guard after repeated successful validation.",
              taskWorkspace,
              isolatedWorkspace,
            );
            if (validationOutcome.completed) return "completed";
            transcript = "AUTOMATIC VALIDATION OR REVIEW REJECTED:\n" + validationOutcome.feedback + "\nDo not repeat successful actions. Use the supplied likely-file evidence and mutate the relevant file now.";
            correctionMode = true;
            context = this.contextBuilder.build(task);
            task.status = "running";
            this.store.saveTask(task);
            successfulActionCounts.clear();
          }
        }
      }
      this.logger.log("action_budget_validation_started", { max_actions: this.config.limits.max_actions_per_task }, { taskId: task.id, level: "warn" });
      const finalOutcome = await this.validateAndReview(
        task,
        context,
        "Completion requested by the action-budget guard after final independent validation.",
        taskWorkspace,
        isolatedWorkspace,
      );
      if (finalOutcome.completed) return "completed";
      throw new Error(`Maximum actions reached and final validation/review rejected completion: ${finalOutcome.feedback}`);
    } catch (error) {
      await this.failTask(task, error, isolatedWorkspace);
      return "failed";
    }
  }

  async retryTask(taskId: string): Promise<TaskRecord> {
    this.lock.acquire();
    try {
      this.stop.assertEnabled("legacy retry-task");
      const task = this.store.getTask(taskId);
      if (!task) throw new Error(`Unknown task: ${taskId}`);
      if (!task.autonomy_eligible) throw new Error(`Task is not autonomy eligible: ${taskId}`);
      if (!["quarantined", "blocked", "retryable_failure"].includes(task.status)) {
        throw new Error(`Task is not retryable from status ${task.status}: ${taskId}`);
      }
      const previousStatus = task.status;
      task.status = "ready";
      task.history.push({ timestamp: new Date().toISOString(), event: "task_manually_requeued", detail: { previous_status: previousStatus } });
      this.store.saveTask(task);
      await this.importer.sync(task);
      this.logger.log("task_requeued", { previous_status: previousStatus }, { taskId });
      return task;
    } finally {
      this.lock.release();
    }
  }

  private async validateAndReview(
    task: TaskRecord,
    context: string,
    summary: string,
    taskWorkspace: string,
    isolatedWorkspace: IsolatedWorkspaceMetadata | null,
  ): Promise<{ completed: boolean; feedback: string }> {
    task.status = "testing";
    this.store.saveTask(task);
    this.logger.log("validation_started", {}, { taskId: task.id });
    const full = (this.completedThisSession + 1) % this.config.limits.full_validation_every_tasks === 0;
    const validation = await this.validator.validateTask(task, full, taskWorkspace);
    task.test_results.push(...validation);
    this.store.saveTask(task);
    const failures = validation.filter((result) => !result.passed);
    this.logger.log("validation_finished", { passed: failures.length === 0, results: validation }, { taskId: task.id, level: failures.length === 0 ? "info" : "warn" });
    if (failures.length > 0) {
      return { completed: false, feedback: JSON.stringify(failures, null, 2) };
    }

    task.status = "reviewing";
    this.store.saveTask(task);
    let artifact: IsolatedPatchArtifact | null = null;
    if (isolatedWorkspace && !this.isolatedWorkspaces) {
      throw new Error("Isolated workspace support disappeared during task validation.");
    }
    const diff = isolatedWorkspace
      ? this.isolatedWorkspaces!.readPatch(
          artifact = this.isolatedWorkspaces!.extractPatch(isolatedWorkspace.workspace_id),
        ).toString("utf8")
      : this.recovery.diff(this.config.limits.max_context_chars);
    const review = await this.reviewer.review(task, context, diff, validation);
    this.logger.log("review_finished", review as unknown as Record<string, unknown>, { taskId: task.id, level: review.approved ? "info" : "warn" });
    if (!review.approved) {
      return { completed: false, feedback: JSON.stringify(review, null, 2) };
    }

    let cleanupResult = "NOT_APPLICABLE";
    if (isolatedWorkspace && artifact && task.isolation.cleanup_on_success) {
      cleanupResult = this.isolatedWorkspaces!.cleanup(isolatedWorkspace.workspace_id).cleanup_result ?? "UNKNOWN";
    }
    const modified = artifact
      ? [...artifact.touched_files]
      : [...new Set([...this.recovery.changedFiles(), "WORK_QUEUE.yaml"])];
    task.status = isolatedWorkspace ? "READY_CODEX_REVIEW" : "completed";
    const result: NonNullable<TaskRecord["result"]> = {
      summary,
      modified_files: modified,
      validation,
      commit: null,
    };
    if (isolatedWorkspace && artifact) {
      result.isolation = {
        execution_id: isolatedWorkspace.execution_id,
        base_head: artifact.base_head,
        worktree_path: isolatedWorkspace.worktree_path,
        patch_path: artifact.patch_path,
        patch_sha256: artifact.patch_sha256,
        cleanup_result: cleanupResult,
      };
    }
    task.result = result;
    task.history.push({
      timestamp: new Date().toISOString(),
      event: "task_completed",
      detail: {
        summary,
        modified_files: modified,
        review,
        isolated_patch: artifact,
        cleanup_result: cleanupResult,
      },
    });
    this.store.saveTask(task);
    await this.importer.sync(task);
    this.logger.log("task_completed", { summary, modified_files: modified, validation_count: validation.length }, { taskId: task.id });
    return { completed: true, feedback: "" };
  }

  private async failTask(
    task: TaskRecord,
    error: unknown,
    isolatedWorkspace: IsolatedWorkspaceMetadata | null,
  ): Promise<void> {
    const message = error instanceof Error ? error.message : String(error);
    let rollbackError: string | null = null;
    try {
      if (isolatedWorkspace) {
        if (!this.isolatedWorkspaces) {
          throw new Error("Isolated workspace recovery is unavailable.");
        }
        const recovered = this.isolatedWorkspaces.recover(isolatedWorkspace.workspace_id);
        this.logger.log("isolated_workspace_recovered", {
          workspace_id: recovered.workspace_id,
          state: recovered.state,
          patch_path: recovered.patch_path,
        }, { taskId: task.id, level: "warn" });
      } else {
        this.recovery.restore();
        this.logger.log("rollback_completed", { manifest: this.recovery.currentManifestPath() }, { taskId: task.id, level: "warn" });
      }
    } catch (restoreError) {
      rollbackError = restoreError instanceof Error ? restoreError.message : String(restoreError);
      this.logger.log("rollback_failed", { error: rollbackError }, { taskId: task.id, level: "error" });
    }
    task.status = task.attempts >= this.config.limits.max_task_retries ? "quarantined" : "retryable_failure";
    task.blockers.push({
      facts: ["Autonomous attempt failed."],
      files: task.likely_files,
      commands: [],
      errors: [message, ...(rollbackError ? [rollbackError] : [])],
      attempts: ["attempt " + task.attempts],
      human_information_needed: task.status === "quarantined" ? "Review the exact errors and decide whether to change constraints or retry." : "",
      independent_tasks_can_continue: true,
    });
    task.history.push({ timestamp: new Date().toISOString(), event: "task_attempt_failed", detail: { message, rollback_error: rollbackError } });
    this.store.saveTask(task);
    await this.importer.sync(task);
    this.logger.log("task_failed", { error: message, status: task.status, rollback_error: rollbackError }, { taskId: task.id, level: "error" });
  }
}
