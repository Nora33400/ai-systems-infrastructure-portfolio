import { resolve } from "node:path";
import { loadConfig } from "./config.js";
import { validateDocumentation } from "./document-validator.js";
import { GitManager } from "./git-manager.js";

function option(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function flag(name: string): boolean {
  return process.argv.includes(name);
}

async function main(): Promise<void> {
  const command = process.argv[2] ?? "status";
  const configPath = resolve(option("--config") ?? "config/autonomy.yaml");
  const config = loadConfig(configPath);
  if (command === "validate-docs") {
    const result = validateDocumentation(config.workspace);
    console.log(JSON.stringify(result, null, 2));
    if (result.issues.length > 0) process.exitCode = 1;
    return;
  }
  const { createRuntime } = await import("./runtime.js");
  const runtime = createRuntime(config);

  try {
    if (command === "bootstrap") {
      const docs = validateDocumentation(config.workspace);
      if (docs.issues.length > 0) throw new Error("Documentation validation failed before bootstrap: " + docs.issues.join("; "));
      const summary = runtime.orchestrator.bootstrap();
      console.log(JSON.stringify({ command, database: config.runtime.database, event_log: config.runtime.event_log, summary }, null, 2));
    } else if (command === "run") {
      const maxTasksRaw = option("--max-tasks");
      const maxTasks = maxTasksRaw ? Number(maxTasksRaw) : undefined;
      const summary = await runtime.orchestrator.run(maxTasks);
      console.log(JSON.stringify({ command, summary }, null, 2));
    } else if (command === "run-once") {
      const result = await runtime.planning.runOnce();
      console.log(JSON.stringify({ command, result }, null, 2));
      if (["FAILED_RETRYABLE", "FAILED_FINAL", "BLOCKED"].includes(result.status)) process.exitCode = 1;
    } else if (command === "plan-once") {
      const result = runtime.phase2.plan();
      console.log(JSON.stringify({ command, result }, null, 2));
    } else if (command === "resources") {
      const userActivity = flag("--user-active") ? "ACTIVE" : flag("--user-idle") ? "IDLE" : "UNKNOWN";
      const snapshot = await runtime.hardwareObserver.observe({
        user_activity: userActivity,
        fullscreen: flag("--fullscreen"),
        game_detected: flag("--game"),
      });
      const requestedWorkersRaw = option("--requested-workers");
      const requestedWorkers = requestedWorkersRaw ? Number(requestedWorkersRaw) : 0;
      if (!Number.isInteger(requestedWorkers) || requestedWorkers < 0) throw new Error("--requested-workers must be a non-negative integer.");
      const recommendation = runtime.resourcePlanner.recommend(snapshot, {
        requested_workers: requestedWorkers,
        heavy_reasoning: flag("--heavy"),
        gpu_required: requestedWorkers > 0 || flag("--heavy"),
      });
      console.log(JSON.stringify({ command, snapshot, recommendation }, null, 2));
    } else if (command === "doctor") {
      const docs = validateDocumentation(config.workspace);
      const git = new GitManager(config);
      const disabled = runtime.stop.disabledReason();
      const external = runtime.policy.document.external;
      console.log(JSON.stringify({
        command,
        healthy: docs.issues.length === 0 && disabled === null,
        autonomy_disabled: disabled,
        documentation: docs,
        git: git.snapshot(),
        state: runtime.store.summary(),
        receipts: runtime.receipts.verifyAll(),
        readonly_reports: runtime.store.verifyReadOnlyReports(),
        external: {
          trello: external.trello_enabled ? "CONFIGURED_NOT_TESTED" : "DISABLED",
          codex: external.codex_adapter,
          chatgpt: external.chatgpt_adapter,
          trello_environment_present: ["TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"].every((name) => Boolean(process.env[name])),
        },
        resource_planning: {
          activation: runtime.resourcePlanner.document.activation,
          user_activity_priority: runtime.resourcePlanner.document.user_activity_priority,
          hardware_observer: "nvidia-smi_read_only",
        },
      }, null, 2));
      if (docs.issues.length > 0 || disabled !== null) process.exitCode = 1;
    } else if (command === "tasks") {
      console.log(JSON.stringify({ command, tasks: runtime.store.listTasks().map((task) => ({ id: task.id, title: task.title, status: task.status, priority: task.priority, assigned_agent: task.assigned_agent, risk_level: task.risk_level })) }, null, 2));
    } else if (command === "task-show") {
      const taskId = option("--task");
      if (!taskId) throw new Error("task-show requires --task <id>.");
      const task = runtime.store.getTask(taskId);
      if (!task) throw new Error(`Unknown task: ${taskId}`);
      console.log(JSON.stringify({ command, task, executions: runtime.store.listExecutions(taskId) }, null, 2));
    } else if (command === "receipts-verify") {
      const verification = runtime.receipts.verifyAll();
      const readonlyReports = runtime.store.verifyReadOnlyReports();
      console.log(JSON.stringify({ command, verification, readonly_reports: readonlyReports }, null, 2));
      if (!verification.valid || !readonlyReports.valid) process.exitCode = 1;
    } else if (command === "ollama-readonly") {
      const taskId = option("--task");
      if (!taskId) throw new Error("ollama-readonly requires --task <id>.");
      runtime.orchestrator.bootstrap();
      const before = runtime.store.getTask(taskId);
      if (!before) throw new Error(`Unknown task: ${taskId}`);
      const result = await runtime.readonlyWorker.run(taskId);
      const after = runtime.store.getTask(taskId);
      console.log(JSON.stringify({
        command,
        task_id: taskId,
        task_status_before: before.status,
        task_status_after: after?.status ?? null,
        attempted_models: result.attempted_models,
        report: result.report,
        receipt_id: result.receipt.receipt_id,
      }, null, 2));
    } else if (command === "status") {
      console.log(JSON.stringify({
        command,
        database: config.runtime.database,
        event_log: config.runtime.event_log,
        stop_requested: runtime.stop.isRequested(),
        summary: runtime.store.summary(),
        last_stop: runtime.store.getMeta("last_engine_stop"),
      }, null, 2));
    } else if (command === "stop") {
      runtime.stop.request();
      console.log(JSON.stringify({ command, requested: true, stop_file: config.runtime.stop_file }, null, 2));
    } else if (command === "retry-task") {
      const taskId = option("--task");
      if (!taskId) throw new Error("retry-task requires --task <id>.");
      const task = await runtime.orchestrator.retryTask(taskId);
      console.log(JSON.stringify({ command, task_id: task.id, status: task.status, attempts: task.attempts }, null, 2));
    } else if (command === "check-ollama") {
      const models = await runtime.ollama.waitUntilAvailable();
      console.log(JSON.stringify({
        command,
        coder_model: config.ollama.coder_model,
        reviewer_model: config.ollama.reviewer_model,
        readonly_model: config.ollama.readonly_model,
        fallback_models: config.ollama.fallback_models,
        models,
      }, null, 2));
    } else {
      throw new Error("Unknown command: " + command);
    }
  } finally {
    runtime.store.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
