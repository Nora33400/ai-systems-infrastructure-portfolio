import assert from "node:assert/strict";
import test from "node:test";
import { planCapabilityLadder } from "./capability-ladder.mjs";

const AT = "2026-08-03T12:00:00.000Z";
const physicalLanes = [
  { id: "gpu-3060-development", gpuUuid: "GPU-3060", roles: ["code"] },
  { id: "gpu-4060-quality", gpuUuid: "GPU-4060", roles: ["test"] }
];
const healthyTelemetry = [
  { uuid: "GPU-3060", temperatureCelsius: 61, utilizationPercent: 38, memoryUsedMb: 8_000, memoryTotalMb: 12_288 },
  { uuid: "GPU-4060", temperatureCelsius: 59, utilizationPercent: 42, memoryUsedMb: 4_500, memoryTotalMb: 8_192 }
];
const readyTasks = [
  { id: "A-1", projectId: "alpha", priority: "P1", status: "READY" },
  { id: "A-2", projectId: "alpha", priority: "P2", status: "READY" },
  { id: "B-1", projectId: "beta", priority: "P0", status: "READY" },
  { id: "C-1", projectId: "gamma", priority: "P2", status: "READY" }
];

function healthyState(overrides = {}) {
  return {
    activeLogicalLaneCount: 2,
    healthySamplesByGpu: { "GPU-3060": 3, "GPU-4060": 3 },
    cooldowns: {},
    ...overrides
  };
}

test("healthy headroom admits four logical lanes without claiming double performance", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    state: healthyState(),
    at: AT
  });
  assert.equal(plan.level, "BURST_FOUR");
  assert.equal(plan.logicalLanes.length, 4);
  assert.equal(plan.logicalLanes.filter((lane) => lane.tier === "BURST").length, 2);
  assert.equal(plan.assignments.length, 4);
  assert.equal(plan.capacity.logicalLaneMultiplier, 2);
  assert.equal(plan.capacity.throughputMultiplierEstimate, null);
  assert.equal(plan.capacity.performanceClaim, "NOT_CLAIMED");
  assert.deepEqual(new Set(plan.assignments.map((task) => task.projectId)), new Set(["alpha", "beta", "gamma"]));
  assert.equal(plan.mutationPerformed, false);
  assert.equal(plan.schedulerActionPerformed, false);
});

test("GPU saturation and VRAM pressure keep the scheduler at the safe baseline", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: [
      { uuid: "GPU-3060", temperatureCelsius: 62, utilizationPercent: 91, memoryUsedMb: 9_000, memoryTotalMb: 12_288 },
      { uuid: "GPU-4060", temperatureCelsius: 62, utilizationPercent: 45, memoryUsedMb: 7_200, memoryTotalMb: 8_192 }
    ],
    readyTasks,
    state: healthyState(),
    at: AT
  });
  assert.equal(plan.level, "BASELINE_TWO");
  assert.equal(plan.logicalLanes.length, 2);
  assert.equal(plan.devices[0].burstEligible, false);
  assert(plan.devices[0].reasons.includes("GPU_SATURATED_NO_SCALE_UP"));
  assert.equal(plan.devices[1].burstEligible, false);
  assert(plan.devices[1].reasons.includes("BURST_VRAM_HEADROOM_INSUFFICIENT"));
  assert(plan.audit.reasons.includes("SATURATED_GPU_PREVENTS_CAPACITY_CLAIM"));
  assert.equal(plan.capacity.throughputMultiplierEstimate, null);
});

test("hard thermal stop removes the hot GPU and establishes a cooldown", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: [
      { uuid: "GPU-3060", temperatureCelsius: 82, utilizationPercent: 80, memoryUsedMb: 7_000, memoryTotalMb: 12_288 },
      healthyTelemetry[1]
    ],
    readyTasks,
    state: healthyState(),
    at: AT
  });
  assert.equal(plan.devices[0].state, "THERMAL_STOP");
  assert.equal(plan.logicalLanes.some((lane) => lane.gpuId === "GPU-3060"), false);
  assert.equal(plan.audit.thermalStopGpuIds.includes("GPU-3060"), true);
  assert.equal(plan.nextState.cooldowns["GPU-3060"], "2026-08-03T12:10:00.000Z");
});

test("thermal cooldown requires both elapsed time and resume temperature", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: [
      { ...healthyTelemetry[0], temperatureCelsius: 75 },
      healthyTelemetry[1]
    ],
    readyTasks,
    state: healthyState({ cooldowns: { "GPU-3060": "2026-08-03T12:05:00.000Z" } }),
    at: AT
  });
  assert.equal(plan.devices[0].state, "THERMAL_COOLDOWN");
  assert.equal(plan.devices[0].baseEligible, false);
  assert.equal(plan.logicalLanes.some((lane) => lane.gpuId === "GPU-3060"), false);
});

test("downstream backpressure refuses burst lanes even with healthy GPUs", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    downstreamBacklog: 8,
    state: healthyState(),
    at: AT
  });
  assert.equal(plan.level, "BASELINE_TWO");
  assert.equal(plan.backpressure.active, true);
  assert.equal(plan.backpressure.scaleUpPermitted, false);
  assert(plan.audit.reasons.includes("DOWNSTREAM_BACKPRESSURE"));
});

test("healthy sample window and queue depth prevent premature scale-up", () => {
  const samplePlan = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    state: healthyState({ healthySamplesByGpu: { "GPU-3060": 1, "GPU-4060": 1 } }),
    at: AT
  });
  assert.equal(samplePlan.logicalLanes.length, 2);
  assert(samplePlan.devices.every((device) => device.reasons.includes("HEALTHY_SAMPLE_WINDOW_INCOMPLETE")));

  const shallowPlan = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks: readyTasks.slice(0, 2),
    state: healthyState(),
    at: AT
  });
  assert.equal(shallowPlan.logicalLanes.length, 2);
  assert(shallowPlan.audit.reasons.includes("QUEUE_TOO_SHALLOW_FOR_BURST"));
});

test("fair ordering starts with the project least served recently and does not mutate inputs", () => {
  const inputs = {
    physicalLanes: structuredClone(physicalLanes),
    telemetry: structuredClone(healthyTelemetry),
    readyTasks: structuredClone(readyTasks),
    recentAssignments: [
      { projectId: "alpha" },
      { projectId: "alpha" },
      { projectId: "beta" }
    ],
    state: healthyState(),
    at: AT
  };
  const before = structuredClone(inputs);
  const plan = planCapabilityLadder(inputs);
  assert.equal(plan.assignments[0].projectId, "gamma");
  assert.equal(plan.assignments[1].projectId, "beta");
  assert.deepEqual(inputs, before);
  assert.equal(plan.fairness.starvationProtection, "ROUND_ROBIN_WHEN_SLOTS_ARE_AVAILABLE");
  assert.equal(plan.fairness.boundedByAvailableSlots, true);
});

test("global cooldown holds an admitted burst but blocks a fresh scale-up", () => {
  const hold = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    state: healthyState({
      activeLogicalLaneCount: 4,
      cooldownUntil: "2026-08-03T12:05:00.000Z"
    }),
    at: AT
  });
  assert.equal(hold.logicalLanes.length, 4);
  assert.equal(hold.backpressure.scaleUpPermitted, false);

  const block = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    state: healthyState({
      activeLogicalLaneCount: 2,
      cooldownUntil: "2026-08-03T12:05:00.000Z"
    }),
    at: AT
  });
  assert.equal(block.logicalLanes.length, 2);
  assert(block.audit.reasons.includes("GLOBAL_SCALE_COOLDOWN_ACTIVE"));
});

test("per-GPU lane budget can disable burst admission", () => {
  const plan = planCapabilityLadder({
    physicalLanes,
    telemetry: healthyTelemetry,
    readyTasks,
    state: healthyState(),
    budgets: { maxLogicalLanesPerGpu: 1 },
    at: AT
  });
  assert.equal(plan.logicalLanes.length, 2);
  assert.equal(plan.logicalLanes.some((lane) => lane.tier === "BURST"), false);
});

test("invalid thermal or utilization budgets fail closed", () => {
  assert.throws(() => planCapabilityLadder({ budgets: {
    resumeBelowCelsius: 72,
    scaleUpBelowCelsius: 75,
    hardStopTemperatureCelsius: 82
  } }), /THERMAL_THRESHOLDS_INVALID/u);
  assert.throws(() => planCapabilityLadder({ budgets: {
    scaleUpMaxUtilizationPercent: 90,
    saturatedUtilizationPercent: 85
  } }), /UTILIZATION_THRESHOLDS_INVALID/u);
});
