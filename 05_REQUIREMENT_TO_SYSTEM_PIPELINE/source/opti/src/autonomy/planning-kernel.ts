import { randomUUID } from "node:crypto";
import type { AutonomyConfig, TaskRecord, TestResult } from "./types.js";
import { EventLogger } from "./event-logger.js";
import { PolicyEngine } from "./policy-engine.js";
import { ReceiptEngine } from "./receipt-engine.js";
import { RuntimeLock, StopController } from "./runtime-control.js";
import { Scheduler } from "./scheduler.js";
import { StateStore } from "./state-store.js";
import { TaskImporter } from "./task-importer.js";
import { Validator } from "./validator.js";
import { taskResourceKeys } from "./resource-locks.js";

export interface RunOnceResult {
  selected_task: string | null;
  execution_id: string | null;
  status: string;
  reason: string;
  receipt_id: string | null;
  validation: TestResult[];
}

export class PlanningKernel {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly store: StateStore,
    private readonly importer: TaskImporter,
    private readonly scheduler: Scheduler,
    private readonly validator: Validator,
    private readonly policy: PolicyEngine,
    private readonly receipts: ReceiptEngine,
    private readonly logger: EventLogger,
    private readonly lock: RuntimeLock,
    private readonly stop: StopController,
  ) {}

  async runOnce(): Promise<RunOnceResult> {
    this.lock.acquire();
    try {
      this.stop.assertEnabled("planning run-once");
      const recoveredTasks = this.store.recoverInterrupted();
      const recoveredExecutions = this.store.recoverInterruptedExecutions();
      this.importer.import();
      this.logger.log("planning_run_once_started", {
        recovered_tasks: recoveredTasks.map((task) => task.id),
        recovered_executions: recoveredExecutions.map((execution) => execution.execution_id),
      });

      const schedule = this.scheduler.selectNext();
      const task = schedule.task;
      if (!task) {
        return { selected_task: null, execution_id: null, status: "IDLE", reason: "no_ready_local_task", receipt_id: null, validation: [] };
      }

      const policyDecision = this.policy.decide(task);
      if (!policyDecision.allowed || policyDecision.level !== "LOCAL_SAFE") {
        this.logger.log("planning_task_deferred", { task_id: task.id, policy: policyDecision }, { taskId: task.id, level: "warn" });
        return { selected_task: task.id, execution_id: null, status: "DEFERRED", reason: policyDecision.reason, receipt_id: null, validation: [] };
      }

      const executionId = `EXE-${randomUUID()}`;
      if (!this.store.acquireResourceLocks(taskResourceKeys(task), executionId)) {
        return { selected_task: task.id, execution_id: null, status: "BLOCKED", reason: "task_resources_locked", receipt_id: null, validation: [] };
      }

      try {
        const running = this.store.transition(task.id, "RUNNING_LOCAL_AI", "planning_execution_started", { execution_id: executionId });
        running.attempts += 1;
        running.last_agent = "LOCAL_SYSTEM";
        this.store.saveTask(running);
        const now = new Date().toISOString();
        this.store.startExecution({
          execution_id: executionId,
          task_id: running.id,
          status: "RUNNING",
          actor: "LOCAL_SYSTEM",
          started_at: now,
          updated_at: now,
          finished_at: null,
          attempt: running.attempts,
          checkpoint: { phase: "before_validation", task_status: running.status },
          result: null,
        });
        this.store.saveCheckpoint(`CHK-${randomUUID()}`, running.id, executionId, {
          objective: running.objective,
          status: running.status,
          dependencies: running.dependencies,
          acceptance: running.acceptance,
        });

        const validation = await this.validator.validateTask(running, false);
        const failures = validation.filter((result) => !result.passed);
        if (failures.length > 0) {
          return await this.finishFailure(running, executionId, validation, failures);
        }

        this.store.transition(running.id, "VALIDATED", "local_validation_passed", { execution_id: executionId });
        const completed = this.store.transition(running.id, "COMPLETED", "planning_execution_completed", { execution_id: executionId });
        completed.test_results.push(...validation);
        completed.result = {
          summary: "Local planning validation task completed without an external supervisor or worker.",
          modified_files: [],
          validation,
          commit: null,
        };
        this.store.saveTask(completed);
        await this.importer.sync(completed);
        const receipt = this.receipts.create({
          task_id: completed.id,
          execution_id: executionId,
          actor: "LOCAL_SYSTEM",
          action: "planning_run_once_validation",
          inputs: { objective: completed.objective, dependencies: completed.dependencies, acceptance: completed.acceptance },
          outputs: { status: completed.status, validation },
          files_read: completed.likely_files,
          files_modified: ["WORK_QUEUE.yaml"],
          commands: validation.flatMap((result) => "command" in result.criterion ? [result.criterion.command] : []),
          tests: validation.map((result) => ({ passed: result.passed, detail: result.detail, criterion: result.criterion })),
          decision: "COMPLETED",
          result: completed.result,
        });
        this.store.updateExecution(executionId, {
          status: "COMPLETED",
          finished_at: new Date().toISOString(),
          result: { receipt_id: receipt.receipt_id, validation_passed: true },
        });
        this.logger.log("planning_run_once_completed", { execution_id: executionId, receipt_id: receipt.receipt_id }, { taskId: completed.id });
        return { selected_task: completed.id, execution_id: executionId, status: completed.status, reason: "validated_and_completed", receipt_id: receipt.receipt_id, validation };
      } finally {
        this.store.releaseResourceLocks(executionId);
      }
    } finally {
      this.lock.release();
    }
  }

  private async finishFailure(task: TaskRecord, executionId: string, validation: TestResult[], failures: TestResult[]): Promise<RunOnceResult> {
    const retryable = task.attempts < task.retry_policy.max_retries;
    const status = retryable ? "FAILED_RETRYABLE" : "FAILED_FINAL";
    const failed = this.store.transition(task.id, status, "local_validation_failed", { execution_id: executionId, failures });
    failed.next_retry_at = retryable
      ? new Date(Date.now() + failed.retry_policy.retry_delay_seconds * 1_000).toISOString()
      : null;
    failed.test_results.push(...validation);
    failed.blockers.push({ reason: "local_validation_failed", failures });
    this.store.saveTask(failed);
    await this.importer.sync(failed);
    const receipt = this.receipts.create({
      task_id: failed.id,
      execution_id: executionId,
      actor: "LOCAL_SYSTEM",
      action: "planning_run_once_validation",
      inputs: { objective: failed.objective, acceptance: failed.acceptance },
      outputs: { status: failed.status, failures },
      files_read: failed.likely_files,
      files_modified: ["WORK_QUEUE.yaml"],
      commands: validation.flatMap((result) => "command" in result.criterion ? [result.criterion.command] : []),
      tests: validation.map((result) => ({ passed: result.passed, detail: result.detail, criterion: result.criterion })),
      decision: status,
      result: { failures },
    });
    this.store.updateExecution(executionId, {
      status: "FAILED",
      finished_at: new Date().toISOString(),
      result: { receipt_id: receipt.receipt_id, validation_passed: false },
    });
    return { selected_task: failed.id, execution_id: executionId, status: failed.status, reason: "validation_failed", receipt_id: receipt.receipt_id, validation };
  }
}
