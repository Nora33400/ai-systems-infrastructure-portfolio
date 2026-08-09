import assert from "node:assert/strict";
import test from "node:test";
import { routeLocalModelTask } from "./model-quality-router.mjs";

const inventory = [
  { id: "qwen2.5-coder:7b", roles: ["fast-code", "code", "function-calling"], licenseClass: "APACHE-2.0", requiredVramMb: 5_000 },
  { id: "qwen2.5-coder:14b", roles: ["code", "reasoning", "planning"], licenseClass: "APACHE-2.0", requiredVramMb: 9_000 },
  { id: "unknown:8b", roles: ["reasoning"], licenseClass: "UNKNOWN", requiredVramMb: 5_000 }
];
const benchmarks = [
  { modelId: "qwen2.5-coder:7b", stableRuns: 3, compositeScore: 70, latencyMs: 1000, contractValidityRate: 1, criticalSafetyFailures: 0, baseline: true },
  { modelId: "qwen2.5-coder:14b", stableRuns: 3, compositeScore: 84, latencyMs: 2200, contractValidityRate: 1, criticalSafetyFailures: 0, baseline: true },
  { modelId: "unknown:8b", stableRuns: 3, compositeScore: 99, latencyMs: 500, contractValidityRate: 1, criticalSafetyFailures: 0 }
];

test("simple task uses one fast bounded stage", () => {
  const route = routeLocalModelTask({ task: { kind: "code", complexity: "simple", risk: "low" }, inventory, benchmarks });
  assert.equal(route.decision, "ROUTE_LOCAL");
  assert.equal(route.mode, "FAST");
  assert.equal(route.stages, 1);
  assert.equal(route.executionBudgetMultiplier, 1);
});

test("complex task creates four logical roles over no more than two physical models", () => {
  const route = routeLocalModelTask({ task: { kind: "code", complexity: "complex", risk: "high" }, inventory, benchmarks });
  assert.equal(route.mode, "DELIBERATIVE");
  assert.equal(route.roles.length, 4);
  assert(route.physicalConcurrentModels <= 2);
  assert.equal(route.executionBudgetMultiplier, 2);
  assert.equal(route.qualityGate.externalTestsRequired, true);
  assert.equal(route.performanceClaim, "NOT_CLAIMED_UNTIL_LIVE_BENCHMARK");
});

test("unknown license is rejected even with the highest synthetic score", () => {
  const route = routeLocalModelTask({ task: { complexity: "complex" }, inventory, benchmarks });
  assert.equal(route.roles.some((role) => role.modelId === "unknown:8b"), false);
});

test("critical safety failure makes a candidate ineligible", () => {
  const failed = benchmarks.map((item) => item.modelId === "qwen2.5-coder:14b" ? { ...item, criticalSafetyFailures: 1 } : item);
  const route = routeLocalModelTask({ task: { kind: "code", complexity: "complex" }, inventory, benchmarks: failed });
  assert.equal(route.roles.some((role) => role.modelId === "qwen2.5-coder:14b"), false);
});

test("VRAM budget excludes a model that does not fit", () => {
  const route = routeLocalModelTask({ task: { kind: "code", complexity: "complex" }, inventory, benchmarks, resources: { maximumAdmissibleVramMb: 6_000 } });
  assert.equal(route.roles.every((role) => role.modelId === "qwen2.5-coder:7b"), true);
});

test("fails closed when no installed model is licensed and benchmarked", () => {
  const route = routeLocalModelTask({
    task: { complexity: "deep" },
    inventory: [{ id: "mystery", roles: ["reasoning"], licenseClass: "UNKNOWN", requiredVramMb: 1000 }],
    benchmarks: []
  });
  assert.equal(route.decision, "NO_SAFE_MODEL");
  assert.equal(route.executable, false);
});

test("configured baseline bypass is disabled unless explicitly enabled", () => {
  const route = routeLocalModelTask({
    task: { complexity: "simple" },
    inventory: [{ id: "qwen2.5-coder:7b", roles: ["code"], licenseClass: "APACHE-2.0", requiredVramMb: 5_000 }],
    benchmarks: []
  });
  assert.equal(route.decision, "NO_SAFE_MODEL");
});
