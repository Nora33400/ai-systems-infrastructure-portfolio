import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { PredictiveEvolution } from "./predictive-evolution.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const CONFIG = new URL("../../config/bounded-adaptive-evolution.json", import.meta.url);

function metrics(index) {
  return {
    queueArrivalRate: 20 + index,
    queueServiceRate: 10,
    queueAgeMinutes: 30 + index,
    gpuThermalHeadroom: 0.2,
    ramHeadroom: 0.7,
    diskHeadroom: 0.8,
    contextLatencyMs: 2_000 + index * 100,
    testFailureRate: 0.1,
    implementationRejectionRate: 0.2,
    ownerReviewWaitMinutes: 60
  };
}

test("predicts bottlenecks and creates only L4 isolated process contracts", () => {
  const runtimeRoot = mkdtempSync(join(testRuntimeRoot(), "aione-predictive-"));
  let now = new Date("2026-07-30T20:00:00.000Z");
  try {
    const engine = new PredictiveEvolution({ configPath: CONFIG, runtimeRoot, clock: () => new Date(now) });
    for (let index = 0; index < 8; index += 1) {
      engine.observe({ sampleId: `sample-${index}`, metrics: metrics(index), evidence: { token: "secret-value" } });
      now = new Date(now.getTime() + 5 * 60_000);
    }
    assert.equal(engine.observe({ sampleId: "sample-7", metrics: metrics(7) }).status, "DUPLICATE");
    const result = engine.plan();
    assert.equal(result.status, "PLANNED");
    assert.equal(result.plan.permissionCeiling, "L4_ISOLATED_EXECUTE");
    assert.equal(result.plan.canonicalPromotion, "OWNER_REQUIRED");
    assert.ok(result.plan.scenarios.length > 0);
    assert.ok(result.plan.scenarios.every((item) =>
      item.permissionCeiling === "L4_ISOLATED_EXECUTE" &&
      item.resourceBudget.maxNetworkRequests === 0 &&
      item.canonicalMutation === false
    ));
    const experiment = engine.recordExperiment({
      scenarioId: result.plan.scenarios[0].scenarioId,
      baseline: 100,
      candidate: 70,
      testsPassed: true,
      permissionsUnchanged: true,
      rollbackReady: true
    });
    assert.equal(experiment.decision, "PROPOSE_OWNER_REVIEW");
    assert.equal(engine.status().integrity.ok, true);
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});

test("refuses to plan without evidence and rolls back regressions", () => {
  const runtimeRoot = mkdtempSync(join(testRuntimeRoot(), "aione-predictive-low-evidence-"));
  try {
    const engine = new PredictiveEvolution({ configPath: CONFIG, runtimeRoot });
    assert.equal(engine.plan().status, "INSUFFICIENT_EVIDENCE");
    for (let index = 0; index < 6; index += 1) {
      engine.observe({ sampleId: `s-${index}`, metrics: metrics(index) });
    }
    const plan = engine.plan().plan;
    const result = engine.recordExperiment({
      scenarioId: plan.scenarios[0].scenarioId,
      baseline: 50,
      candidate: 60,
      testsPassed: true,
      permissionsUnchanged: true,
      rollbackReady: true
    });
    assert.equal(result.decision, "ROLLBACK_ISOLATED");
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});
