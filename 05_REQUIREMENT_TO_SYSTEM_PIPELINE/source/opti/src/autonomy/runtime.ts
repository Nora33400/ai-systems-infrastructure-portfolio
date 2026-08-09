import type { AutonomyConfig } from "./types.js";
import { ActionExecutor } from "./action-executor.js";
import { AgentProtocol } from "./agent-protocol.js";
import { CommandExecutor } from "./command-executor.js";
import { ContextBuilder } from "./context-builder.js";
import { EventLogger } from "./event-logger.js";
import { GitManager } from "./git-manager.js";
import { OllamaClient } from "./ollama-client.js";
import { Orchestrator } from "./orchestrator.js";
import { RecoveryManager } from "./recovery-manager.js";
import { Reviewer } from "./reviewer.js";
import { RuntimeLock, StopController } from "./runtime-control.js";
import { Scheduler } from "./scheduler.js";
import { SecurityPolicy } from "./security-policy.js";
import { StateStore } from "./state-store.js";
import { TaskImporter } from "./task-importer.js";
import { Validator } from "./validator.js";
import { WorkspaceWriter } from "./workspace-writer.js";
import { PolicyEngine } from "./policy-engine.js";
import { ReceiptEngine } from "./receipt-engine.js";
import { PlanningKernel } from "./planning-kernel.js";
import { join } from "node:path";
import { Phase2Planner } from "./phase2-planner.js";
import { NvidiaSmiObserver, ResourcePlanner } from "./resource-planner.js";
import { OllamaReadOnlyWorker } from "./ollama-readonly-worker.js";
import { IsolatedWorkspaceManager } from "./isolated-workspace-manager.js";

export interface RuntimeBundle {
  store: StateStore;
  stop: StopController;
  ollama: OllamaClient;
  orchestrator: Orchestrator;
  planning: PlanningKernel;
  receipts: ReceiptEngine;
  policy: PolicyEngine;
  phase2: Phase2Planner;
  resourcePlanner: ResourcePlanner;
  hardwareObserver: NvidiaSmiObserver;
  readonlyWorker: OllamaReadOnlyWorker;
  isolatedWorkspaces: IsolatedWorkspaceManager;
}

export function createRuntime(config: AutonomyConfig): RuntimeBundle {
  const logger = new EventLogger(config.runtime.event_log);
  const store = new StateStore(config.runtime.database);
  const policy = new SecurityPolicy(config);
  const writer = new WorkspaceWriter(config);
  const commands = new CommandExecutor(config, policy, logger);
  const git = new GitManager(config);
  const recovery = new RecoveryManager(config, writer);
  const stop = new StopController(config.runtime.stop_file);
  const ollama = new OllamaClient(config, logger);
  const importer = new TaskImporter(config, store, writer);
  const scheduler = new Scheduler(store);
  const contextBuilder = new ContextBuilder(config, git);
  const protocol = new AgentProtocol(config);
  const executor = new ActionExecutor(config, policy, commands, git, recovery, logger, writer);
  const validator = new Validator(config, policy, commands);
  const reviewer = new Reviewer(config, ollama);
  const lock = new RuntimeLock(config.runtime.lock_file);
  const isolatedWorkspaces = new IsolatedWorkspaceManager(config);
  const orchestrator = new Orchestrator(
    config, store, importer, scheduler, contextBuilder, protocol, ollama,
    executor, validator, reviewer, git, recovery, logger, lock, stop, isolatedWorkspaces,
  );
  const policyEngine = PolicyEngine.load(
    join(config.workspace, "config", "autonomy-policy.yaml"),
    join(config.workspace, "schemas", "autonomy-policy.schema.json"),
  );
  const receipts = new ReceiptEngine(store, join(config.workspace, "schemas", "autonomy-receipt.schema.json"));
  const planning = new PlanningKernel(
    config, store, importer, scheduler, validator, policyEngine, receipts, logger, lock, stop,
  );
  const phase2 = new Phase2Planner(store, importer, scheduler, policyEngine);
  const resourcePlanner = ResourcePlanner.load(
    join(config.workspace, "config", "resource-policy.yaml"),
    join(config.workspace, "schemas", "resource-policy.schema.json"),
  );
  const hardwareObserver = new NvidiaSmiObserver();
  const readonlyWorker = new OllamaReadOnlyWorker(
    config,
    store,
    receipts,
    logger,
    lock,
    stop,
    ollama,
    join(config.workspace, "schemas", "ollama-readonly-report.schema.json"),
  );
  return { store, stop, ollama, orchestrator, planning, receipts, policy: policyEngine, phase2, resourcePlanner, hardwareObserver, readonlyWorker, isolatedWorkspaces };
}
