import test from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { createHash } from "node:crypto";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parse } from "yaml";
import { CommandExecutor, parseCommand } from "../../src/autonomy/command-executor.js";
import { EventLogger } from "../../src/autonomy/event-logger.js";
import { PlanningKernel } from "../../src/autonomy/planning-kernel.js";
import { PolicyEngine } from "../../src/autonomy/policy-engine.js";
import { ReceiptEngine } from "../../src/autonomy/receipt-engine.js";
import { RuntimeLock, StopController } from "../../src/autonomy/runtime-control.js";
import { Scheduler } from "../../src/autonomy/scheduler.js";
import { SecurityPolicy } from "../../src/autonomy/security-policy.js";
import { StateStore } from "../../src/autonomy/state-store.js";
import { TaskImporter } from "../../src/autonomy/task-importer.js";
import { InvalidTaskTransition, TaskStateMachine } from "../../src/autonomy/task-state-machine.js";
import { Validator } from "../../src/autonomy/validator.js";
import { WorkspaceWriter } from "../../src/autonomy/workspace-writer.js";
import { task, testConfig } from "./test-helpers.js";

const repository = resolve(process.env.AIONE_WORKSPACE ?? process.cwd());

function installSchemas(workspace: string): void {
  copyFileSync(join(repository, "schemas", "autonomy-policy.schema.json"), join(workspace, "schemas", "autonomy-policy.schema.json"));
  copyFileSync(join(repository, "schemas", "autonomy-receipt.schema.json"), join(workspace, "schemas", "autonomy-receipt.schema.json"));
}

test("planning state machine allows the validated path and rejects invalid completion", () => {
  const machine = new TaskStateMachine();
  assert.equal(machine.canTransition("DISCOVERED", "READY_LOCAL_AI"), true);
  assert.equal(machine.canTransition("READY_LOCAL_AI", "COMPLETED"), false);
  assert.throws(() => machine.assertTransition("READY_LOCAL_AI", "COMPLETED"), InvalidTaskTransition);
});

test("state store enforces planning transitions and survives reopen", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-planning-state-"));
  const config = testConfig(workspace);
  let store = new StateStore(config.runtime.database);
  store.saveTask(task("WQ-9001", { status: "DISCOVERED" }));
  store.transition("WQ-9001", "READY_LOCAL_AI", "test_ready");
  assert.throws(() => store.transition("WQ-9001", "COMPLETED", "invalid"), InvalidTaskTransition);
  store.close();
  store = new StateStore(config.runtime.database);
  assert.equal(store.getTask("WQ-9001")?.status, "READY_LOCAL_AI");
  store.close();
});

test("policy validates from schema and blocks sensitive, deep and external tasks", () => {
  const engine = PolicyEngine.load(join(repository, "config", "autonomy-policy.yaml"), join(repository, "schemas", "autonomy-policy.schema.json"));
  assert.deepEqual(engine.decide(task("WQ-9002", { status: "READY_LOCAL_AI" })), { level: "LOCAL_SAFE", allowed: true, reason: "safe_local_system_task" });
  assert.equal(engine.decide(task("WQ-9003", { risk_level: "SENSITIVE" })).level, "OWNER_REQUIRED");
  assert.equal(engine.decide(task("WQ-9004", { subtask_depth: 5 })).level, "FORBIDDEN");
  assert.equal(engine.decide(task("WQ-9005", { assigned_agent: "OLLAMA" })).allowed, false);
});

test("receipt registry is immutable and detects database tampering", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-receipts-"));
  const config = testConfig(workspace);
  installSchemas(workspace);
  let store = new StateStore(config.runtime.database);
  const engine = new ReceiptEngine(store, join(workspace, "schemas", "autonomy-receipt.schema.json"));
  const receipt = engine.create({
    task_id: "WQ-9006", execution_id: "EXE-1", actor: "LOCAL_SYSTEM", action: "test",
    inputs: { a: 1 }, outputs: { b: 2 }, files_read: [], files_modified: [], commands: [], tests: [], decision: "COMPLETED", result: { ok: true },
  });
  assert.deepEqual(engine.verifyAll(), { valid: true, count: 1, issues: [] });
  assert.throws(() => store.insertReceipt(receipt, "0".repeat(64)), /UNIQUE/);
  store.close();

  const db = new DatabaseSync(config.runtime.database);
  db.prepare("UPDATE autonomy_receipts SET data_json = replace(data_json, 'COMPLETED', 'TAMPERED') WHERE receipt_id = ?").run(receipt.receipt_id);
  db.close();
  store = new StateStore(config.runtime.database);
  const verification = new ReceiptEngine(store, join(workspace, "schemas", "autonomy-receipt.schema.json")).verifyAll();
  assert.equal(verification.valid, false);
  assert.match(verification.issues.join("\n"), /content_hash_mismatch/);
  store.close();
});

// The public copy redacts profile paths inside this historical receipt. Schema
// validation remains useful, but its original content hash cannot remain equal.
test.skip("the canonical WQ-0042 receipt projection keeps its pre-redaction runtime hash", () => {
  const receipt = JSON.parse(readFileSync(join(repository, "receipts", "autonomy-planning", "WQ-0042.json"), "utf8")) as Record<string, unknown>;
  const schema = JSON.parse(readFileSync(join(repository, "schemas", "autonomy-receipt.schema.json"), "utf8")) as Record<string, unknown>;
  const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema);
  assert.equal(validate(receipt), true);
  assert.equal(createHash("sha256").update(JSON.stringify(receipt)).digest("hex"), "2ea650d5c7002cb575c5232a2cf89263d09c4317c06487093f2e6147d27c3adb");
});

test("command parser preserves arguments and executor runs without a shell", async () => {
  assert.deepEqual(parseCommand('node -e "console.log(42)"'), { executable: "node", args: ["-e", "console.log(42)"] });
  const workspace = mkdtempSync(join(tmpdir(), "opti-command-"));
  const config = testConfig(workspace);
  const logger = new EventLogger(config.runtime.event_log);
  const executor = new CommandExecutor(config, new SecurityPolicy(config), logger);
  const result = await executor.execute('node -e "console.log(42)"');
  assert.equal(result.exit_code, 0);
  assert.equal(result.stdout.trim(), "42");
});

test("phase 1 run-once completes a safe local task without external services", async () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-run-once-"));
  const config = testConfig(workspace);
  installSchemas(workspace);
  writeFileSync(join(workspace, "docs", "result.md"), "ready", "utf8");
  writeFileSync(join(workspace, "WORK_QUEUE.yaml"), [
    "schema_version: 1",
    "tasks:",
    "  - id: WQ-9100",
    "    title: Local smoke",
    "    objective: Validate a local file",
    "    project: opti-test",
    "    module: autonomy-engine",
    "    status: DISCOVERED",
    "    priority: P0",
    "    risk_level: SAFE",
    "    dependencies: []",
    "    subtask_depth: 0",
    "    assigned_agent: LOCAL_SYSTEM",
    "    required_supervisor: null",
    "    required_validator: LOCAL_SYSTEM",
    "    allowed_paths: [docs/result.md]",
    "    forbidden_paths: [.git, .env]",
    "    allowed_commands: []",
    "    context_requirements: []",
    "    autonomy_eligible: true",
    "    acceptance:",
    "      - {type: file_exists, path: docs/result.md}",
    "    created_at: 2026-07-18",
    "    updated_at: 2026-07-18",
  ].join("\n") + "\n", "utf8");

  const store = new StateStore(config.runtime.database);
  const policy = new SecurityPolicy(config);
  const writer = new WorkspaceWriter(config);
  const logger = new EventLogger(config.runtime.event_log);
  const commands = new CommandExecutor(config, policy, logger);
  const importer = new TaskImporter(config, store, writer);
  const receipts = new ReceiptEngine(store, join(workspace, "schemas", "autonomy-receipt.schema.json"));
  const kernel = new PlanningKernel(
    config, store, importer, new Scheduler(store), new Validator(config, policy, commands),
    PolicyEngine.load(join(repository, "config", "autonomy-policy.yaml"), join(repository, "schemas", "autonomy-policy.schema.json")),
    receipts, logger, new RuntimeLock(config.runtime.lock_file), new StopController(config.runtime.stop_file),
  );

  const result = await kernel.runOnce();
  assert.equal(result.status, "COMPLETED");
  assert.ok(result.receipt_id);
  assert.equal(store.getTask("WQ-9100")?.status, "COMPLETED");
  assert.equal(store.listExecutions("WQ-9100")[0]?.status, "COMPLETED");
  assert.equal(receipts.verifyAll().valid, true);
  const queue = parse(readFileSync(join(workspace, "WORK_QUEUE.yaml"), "utf8")) as { tasks: Array<{ status: string }> };
  assert.equal(queue.tasks[0]?.status, "COMPLETED");
  store.close();
});
