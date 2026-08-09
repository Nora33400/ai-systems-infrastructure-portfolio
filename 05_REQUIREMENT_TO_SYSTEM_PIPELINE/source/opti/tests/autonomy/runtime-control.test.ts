import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Orchestrator } from "../../src/autonomy/orchestrator.js";
import { PlanningKernel } from "../../src/autonomy/planning-kernel.js";
import { RuntimeLock, StopController } from "../../src/autonomy/runtime-control.js";
import { testConfig } from "./test-helpers.js";

function stoppedRuntime() {
  const workspace = mkdtempSync(join(tmpdir(), "opti-global-stop-"));
  const config = testConfig(workspace);
  const stop = new StopController(config.runtime.stop_file);
  stop.request("negative_test");
  return { workspace, config, stop };
}

test("the stop sentinel is persistent until an explicit clear", () => {
  const { config, stop } = stoppedRuntime();
  assert.equal(stop.isRequested(), true);
  assert.match(stop.disabledReason() ?? "", /stop sentinel/);
  assert.throws(() => stop.assertEnabled("test"), /Autonomy is disabled for test/);

  const reopened = new StopController(config.runtime.stop_file);
  assert.equal(reopened.isRequested(), true);
  reopened.clear();
  assert.equal(reopened.isRequested(), false);
});

test("AUTONOMY_DISABLED uses the same fail-closed guard", { concurrency: false }, () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-global-env-stop-"));
  const config = testConfig(workspace);
  const previous = process.env.AUTONOMY_DISABLED;
  process.env.AUTONOMY_DISABLED = "1";
  try {
    const stop = new StopController(config.runtime.stop_file);
    assert.equal(stop.disabledReason(), "AUTONOMY_DISABLED environment variable");
    assert.throws(() => stop.assertEnabled("test"), /AUTONOMY_DISABLED environment variable/);
  } finally {
    if (previous === undefined) delete process.env.AUTONOMY_DISABLED;
    else process.env.AUTONOMY_DISABLED = previous;
  }
});

test("planning run-once fails closed before importing or mutating tasks", async () => {
  const { config, stop } = stoppedRuntime();
  const kernel = new PlanningKernel(
    config,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    new RuntimeLock(config.runtime.lock_file),
    stop,
  );

  await assert.rejects(kernel.runOnce(), /Autonomy is disabled for planning run-once/);
  assert.equal(stop.isRequested(), true);
  assert.equal(existsSync(config.runtime.lock_file), false);
  assert.equal(existsSync(config.runtime.database), false);
});

test("legacy execution entrypoints fail closed without clearing the sentinel", async () => {
  const { config, stop } = stoppedRuntime();
  const orchestrator = new Orchestrator(
    config,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    undefined as never,
    new RuntimeLock(config.runtime.lock_file),
    stop,
  );

  assert.throws(() => orchestrator.bootstrap(), /Autonomy is disabled for legacy bootstrap/);
  await assert.rejects(orchestrator.run(1), /Autonomy is disabled for legacy run/);
  await assert.rejects(orchestrator.retryTask("WQ-TEST"), /Autonomy is disabled for legacy retry-task/);
  assert.equal(stop.isRequested(), true);
  assert.equal(existsSync(config.runtime.lock_file), false);
});
