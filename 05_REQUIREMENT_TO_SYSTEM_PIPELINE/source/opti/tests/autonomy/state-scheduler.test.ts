import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { StateStore } from "../../src/autonomy/state-store.js";
import { Scheduler } from "../../src/autonomy/scheduler.js";
import { task, testConfig } from "./test-helpers.js";

test("state survives reopen and interrupted tasks are recovered", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-state-"));
  const config = testConfig(workspace);
  let store = new StateStore(config.runtime.database);
  store.saveTask(task("T-1", { status: "running" }));
  store.close();

  store = new StateStore(config.runtime.database);
  assert.equal(store.getTask("T-1")?.status, "running");
  assert.deepEqual(store.recoverInterrupted().map((entry) => entry.id), ["T-1"]);
  assert.equal(store.getTask("T-1")?.status, "retryable_failure");
  store.close();
});

test("scheduler enforces completed dependencies and deterministic priority", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-scheduler-"));
  const config = testConfig(workspace);
  const store = new StateStore(config.runtime.database);
  store.saveTask(task("dependency", { status: "ready", priority: 20 }));
  store.saveTask(task("blocked-high", { dependencies: ["dependency"], priority: 100 }));
  store.saveTask(task("ready-low", { priority: 40 }));
  const scheduler = new Scheduler(store);
  assert.equal(scheduler.selectNext().task?.id, "ready-low");
  store.transition("dependency", "completed", "test_completion");
  assert.equal(scheduler.selectNext().task?.id, "blocked-high");
  store.close();
});

test("terminal status imported from the work queue overrides stale runtime state", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-import-terminal-"));
  const config = testConfig(workspace);
  const store = new StateStore(config.runtime.database);
  store.saveTask(task("manual-task", {
    status: "blocked",
    blockers: [{ reason: "not_explicitly_autonomy_eligible" }],
  }));

  const imported = store.importTask(task("manual-task", {
    status: "completed",
    autonomy_eligible: false,
    blockers: [],
  }));

  assert.equal(imported.status, "completed");
  assert.deepEqual(imported.blockers, []);
  assert.equal(store.getTask("manual-task")?.status, "completed");
  store.close();
});

test("a non-running planning task follows the canonical WORK_QUEUE status", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-import-planning-"));
  const config = testConfig(workspace);
  const store = new StateStore(config.runtime.database);
  store.saveTask(task("WQ-9007", { status: "BLOCKED", assigned_agent: "CODEX_LOCAL" }));

  const imported = store.importTask(task("WQ-9007", {
    status: "READY_CODEX_REVIEW",
    assigned_agent: "CODEX_LOCAL",
    autonomy_eligible: false,
  }));

  assert.equal(imported.status, "READY_CODEX_REVIEW");
  assert.equal(imported.history.at(-1)?.event, "canonical_work_queue_status_imported");
  store.close();
});
