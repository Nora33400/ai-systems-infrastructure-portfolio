const DEFAULT_CAPABILITY_BUDGETS = Object.freeze({
  maxLogicalLanes: 4,
  maxLogicalLanesPerGpu: 2,
  hardStopTemperatureCelsius: 82,
  resumeBelowCelsius: 72,
  scaleUpBelowCelsius: 70,
  saturatedUtilizationPercent: 85,
  scaleUpMaxUtilizationPercent: 70,
  minimumFreeVramMbForBase: 768,
  minimumFreeVramMbForBurst: 2_560,
  reservedVramMb: 512,
  estimatedBurstVramMb: 2_048,
  minimumReadyTasksForBurst: 3,
  maximumDownstreamBacklog: 8,
  minimumHealthySamplesForBurst: 2,
  scaleCooldownSeconds: 300,
  thermalCooldownSeconds: 600,
  partitionMinutes: 60,
  maximumTasksInspected: 500,
  maximumRecentAssignments: 1_000
});

const PRIORITY = Object.freeze({ P0: 0, P1: 1, P2: 2, P3: 3, P4: 4 });
const TERMINAL = new Set(["DONE", "COMPLETED", "STABLE", "ARCHIVED", "CANCELLED", "FAILED"]);

function finite(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function integer(value, fallback, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, Math.trunc(finite(value, fallback))));
}

function date(value, fallback) {
  const parsed = new Date(value ?? "");
  return Number.isFinite(parsed.getTime()) ? parsed : new Date(fallback);
}

function text(value, fallback = "") {
  const normalized = String(value ?? fallback).replaceAll("\0", "").trim();
  return normalized.slice(0, 300);
}

function normalizeBudgets(input = {}) {
  const budgets = {
    maxLogicalLanes: integer(input.maxLogicalLanes, 4, 1, 4),
    maxLogicalLanesPerGpu: integer(input.maxLogicalLanesPerGpu, 2, 1, 2),
    hardStopTemperatureCelsius: finite(input.hardStopTemperatureCelsius, 82),
    resumeBelowCelsius: finite(input.resumeBelowCelsius, 72),
    scaleUpBelowCelsius: finite(input.scaleUpBelowCelsius, 70),
    saturatedUtilizationPercent: finite(input.saturatedUtilizationPercent, 85),
    scaleUpMaxUtilizationPercent: finite(input.scaleUpMaxUtilizationPercent, 70),
    minimumFreeVramMbForBase: integer(input.minimumFreeVramMbForBase, 768, 128, 32_768),
    minimumFreeVramMbForBurst: integer(input.minimumFreeVramMbForBurst, 2_560, 256, 32_768),
    reservedVramMb: integer(input.reservedVramMb, 512, 0, 16_384),
    estimatedBurstVramMb: integer(input.estimatedBurstVramMb, 2_048, 256, 32_768),
    minimumReadyTasksForBurst: integer(input.minimumReadyTasksForBurst, 3, 2, 100),
    maximumDownstreamBacklog: integer(input.maximumDownstreamBacklog, 8, 1, 10_000),
    minimumHealthySamplesForBurst: integer(input.minimumHealthySamplesForBurst, 2, 1, 100),
    scaleCooldownSeconds: integer(input.scaleCooldownSeconds, 300, 0, 86_400),
    thermalCooldownSeconds: integer(input.thermalCooldownSeconds, 600, 1, 86_400),
    partitionMinutes: integer(input.partitionMinutes, 60, 5, 240),
    maximumTasksInspected: integer(input.maximumTasksInspected, 500, 1, 10_000),
    maximumRecentAssignments: integer(input.maximumRecentAssignments, 1_000, 0, 10_000)
  };
  if (!(budgets.scaleUpBelowCelsius <= budgets.resumeBelowCelsius &&
    budgets.resumeBelowCelsius < budgets.hardStopTemperatureCelsius)) {
    throw new Error("THERMAL_THRESHOLDS_INVALID");
  }
  if (budgets.scaleUpMaxUtilizationPercent >= budgets.saturatedUtilizationPercent) {
    throw new Error("UTILIZATION_THRESHOLDS_INVALID");
  }
  return Object.freeze(budgets);
}

function normalizePhysicalLanes(lanes = []) {
  const seen = new Set();
  return (Array.isArray(lanes) ? lanes : []).map((lane, index) => {
    const id = text(lane?.id, `physical-lane-${index + 1}`);
    const gpuId = text(lane?.gpuUuid || lane?.gpuId || lane?.uuid, id);
    if (!id || !gpuId || seen.has(id)) throw new Error(`PHYSICAL_LANE_INVALID:${id || index}`);
    seen.add(id);
    return {
      id,
      label: text(lane.label, id),
      gpuId,
      endpoint: text(lane.endpoint),
      roles: [...new Set((Array.isArray(lane.roles) ? lane.roles : []).map((role) => text(role)).filter(Boolean))].slice(0, 30)
    };
  }).slice(0, 2);
}

function telemetryFor(lane, telemetry = []) {
  return (Array.isArray(telemetry) ? telemetry : []).find((device) =>
    text(device?.uuid || device?.gpuUuid || device?.gpuId || device?.id) === lane.gpuId
  ) ?? null;
}

function cooldownFor(state, gpuId) {
  const value = state?.cooldowns?.[gpuId];
  const until = date(value, 0);
  return Number.isFinite(until.getTime()) && until.getTime() > 0 ? until : null;
}

function assessDevice({ lane, telemetry, state = {}, budgets, at }) {
  const cooldownUntil = cooldownFor(state, lane.gpuId);
  if (!telemetry) {
    return {
      lane,
      state: "TELEMETRY_MISSING",
      baseEligible: false,
      burstEligible: false,
      reasons: ["GPU_TELEMETRY_MISSING"],
      cooldownUntil: cooldownUntil?.toISOString() ?? null
    };
  }

  const temperatureCelsius = finite(telemetry.temperatureCelsius ?? telemetry.temperature, Number.POSITIVE_INFINITY);
  const utilizationPercent = finite(telemetry.utilizationPercent ?? telemetry.utilization, 100);
  const memoryTotalMb = Math.max(0, finite(telemetry.memoryTotalMb ?? telemetry.vramTotalMb, 0));
  const memoryUsedMb = Math.max(0, finite(telemetry.memoryUsedMb ?? telemetry.vramUsedMb, memoryTotalMb));
  const freeVramMb = Math.max(0, memoryTotalMb - memoryUsedMb);
  const reasons = [];
  let deviceState = "READY_BASE";
  let baseEligible = true;
  let burstEligible = true;

  if (temperatureCelsius >= budgets.hardStopTemperatureCelsius) {
    deviceState = "THERMAL_STOP";
    baseEligible = false;
    burstEligible = false;
    reasons.push("THERMAL_HARD_STOP");
  } else if (cooldownUntil && at < cooldownUntil && temperatureCelsius > budgets.resumeBelowCelsius) {
    deviceState = "THERMAL_COOLDOWN";
    baseEligible = false;
    burstEligible = false;
    reasons.push("THERMAL_COOLDOWN_ACTIVE");
  } else if (freeVramMb < budgets.minimumFreeVramMbForBase) {
    deviceState = "VRAM_STOP";
    baseEligible = false;
    burstEligible = false;
    reasons.push("BASE_VRAM_HEADROOM_INSUFFICIENT");
  }

  const requiredBurstVramMb = Math.max(
    budgets.minimumFreeVramMbForBurst,
    budgets.estimatedBurstVramMb + budgets.reservedVramMb
  );
  if (baseEligible && temperatureCelsius > budgets.scaleUpBelowCelsius) {
    burstEligible = false;
    reasons.push("TEMPERATURE_TOO_HIGH_FOR_SCALE_UP");
  }
  if (baseEligible && utilizationPercent > budgets.scaleUpMaxUtilizationPercent) {
    burstEligible = false;
    reasons.push(utilizationPercent >= budgets.saturatedUtilizationPercent
      ? "GPU_SATURATED_NO_SCALE_UP"
      : "GPU_BUSY_NO_SCALE_UP");
  }
  if (baseEligible && freeVramMb < requiredBurstVramMb) {
    burstEligible = false;
    reasons.push("BURST_VRAM_HEADROOM_INSUFFICIENT");
  }
  const healthySamples = integer(state?.healthySamplesByGpu?.[lane.gpuId], 0, 0, 1_000_000);
  if (baseEligible && healthySamples < budgets.minimumHealthySamplesForBurst) {
    burstEligible = false;
    reasons.push("HEALTHY_SAMPLE_WINDOW_INCOMPLETE");
  }
  if (baseEligible && cooldownUntil && at < cooldownUntil) {
    burstEligible = false;
    reasons.push("SCALE_COOLDOWN_ACTIVE");
  }
  if (baseEligible && burstEligible) deviceState = "READY_BURST";

  return {
    lane,
    state: deviceState,
    baseEligible,
    burstEligible,
    reasons,
    telemetry: {
      temperatureCelsius,
      utilizationPercent,
      memoryUsedMb,
      memoryTotalMb,
      freeVramMb
    },
    requiredBurstVramMb,
    cooldownUntil: cooldownUntil?.toISOString() ?? null
  };
}

function normalizeTasks(tasks, maximum) {
  const seen = new Set();
  return (Array.isArray(tasks) ? tasks : []).flatMap((task, index) => {
    const id = text(task?.id, `task-${index + 1}`);
    const status = text(task?.status, "READY").toUpperCase().replaceAll("_", "-");
    if (!id || seen.has(id) || TERMINAL.has(status) || task?.ready === false || task?.blocked === true) return [];
    seen.add(id);
    return [{
      id,
      projectId: text(task.projectId || task.project, "unassigned"),
      ecosystemId: text(task.ecosystemId, "unassigned"),
      priority: text(task.priority, "P2").toUpperCase(),
      stage: text(task.stage || task.kind, "DEVELOPMENT").toUpperCase(),
      enqueuedAt: date(task.enqueuedAt || task.createdAt, 8.64e15).toISOString()
    }];
  }).slice(0, maximum);
}

function recentCounts(assignments, maximum) {
  const counts = new Map();
  const recent = maximum > 0
    ? (Array.isArray(assignments) ? assignments : []).slice(-maximum)
    : [];
  for (const assignment of recent) {
    const projectId = text(assignment?.projectId, "unassigned");
    counts.set(projectId, (counts.get(projectId) || 0) + 1);
  }
  return counts;
}

function fairTaskOrder(tasks, recentAssignments, maximumRecentAssignments) {
  const counts = recentCounts(recentAssignments, maximumRecentAssignments);
  const projects = new Map();
  for (const task of tasks) {
    if (!projects.has(task.projectId)) projects.set(task.projectId, []);
    projects.get(task.projectId).push(task);
  }
  for (const queue of projects.values()) {
    queue.sort((left, right) =>
      (PRIORITY[left.priority] ?? 5) - (PRIORITY[right.priority] ?? 5) ||
      left.enqueuedAt.localeCompare(right.enqueuedAt) ||
      left.id.localeCompare(right.id));
  }
  const orderedProjects = [...projects.keys()].sort((left, right) =>
    (counts.get(left) || 0) - (counts.get(right) || 0) || left.localeCompare(right));
  const result = [];
  let remaining = tasks.length;
  while (remaining > 0) {
    for (const projectId of orderedProjects) {
      const task = projects.get(projectId).shift();
      if (!task) continue;
      result.push(task);
      remaining -= 1;
    }
  }
  return result;
}

function levelFor(count) {
  return ["STOPPED", "PROTECTED_ONE", "BASELINE_TWO", "BURST_THREE", "BURST_FOUR"][Math.max(0, Math.min(4, count))];
}

export function planCapabilityLadder({
  physicalLanes = [],
  telemetry = [],
  readyTasks = [],
  downstreamBacklog = 0,
  recentAssignments = [],
  state = {},
  budgets: budgetOverrides = {},
  at = new Date()
} = {}) {
  const now = date(at, new Date());
  const budgets = normalizeBudgets(budgetOverrides);
  const lanes = normalizePhysicalLanes(physicalLanes);
  const tasks = normalizeTasks(readyTasks, budgets.maximumTasksInspected);
  const orderedTasks = fairTaskOrder(tasks, recentAssignments, budgets.maximumRecentAssignments);
  const deviceAssessments = lanes.map((lane) => assessDevice({
    lane,
    telemetry: telemetryFor(lane, telemetry),
    state,
    budgets,
    at: now
  }));

  const baseDevices = deviceAssessments.filter((device) => device.baseEligible);
  const burstDevices = deviceAssessments.filter((device) => device.burstEligible);
  const backpressureActive = finite(downstreamBacklog, 0) >= budgets.maximumDownstreamBacklog;
  const globalCooldownUntil = date(state.cooldownUntil, 0);
  const globalCooldownActive = globalCooldownUntil > now;
  const previousCount = integer(state.activeLogicalLaneCount, 0, 0, 4);
  const queueAllowsBurst = tasks.length >= budgets.minimumReadyTasksForBurst;
  const scaleUpPermitted = !backpressureActive && !globalCooldownActive && queueAllowsBurst;
  const maintainedBurstLimit = globalCooldownActive
    ? Math.max(0, previousCount - baseDevices.length)
    : Number.POSITIVE_INFINITY;

  const logicalLanes = [];
  for (const device of baseDevices) {
    logicalLanes.push({
      id: `${device.lane.id}::primary`,
      physicalLaneId: device.lane.id,
      gpuId: device.lane.gpuId,
      tier: "PRIMARY",
      executionClass: "LOCAL_GPU_WORK",
      vramAdmission: "BASE_HEADROOM_CONFIRMED"
    });
  }
  let admittedBurstCount = 0;
  if (!backpressureActive && queueAllowsBurst && budgets.maxLogicalLanesPerGpu > 1) {
    for (const device of burstDevices) {
      if (logicalLanes.length >= budgets.maxLogicalLanes) break;
      if (logicalLanes.length >= tasks.length) break;
      if (admittedBurstCount >= maintainedBurstLimit) break;
      logicalLanes.push({
        id: `${device.lane.id}::burst`,
        physicalLaneId: device.lane.id,
        gpuId: device.lane.gpuId,
        tier: "BURST",
        executionClass: "LOGICAL_PIPELINED_WORK",
        vramAdmission: "BURST_HEADROOM_CONFIRMED"
      });
      admittedBurstCount += 1;
    }
  }
  const admittedLanes = logicalLanes.slice(0, Math.min(
    budgets.maxLogicalLanes,
    tasks.length || baseDevices.length
  ));
  const assignments = admittedLanes.flatMap((lane, index) => orderedTasks[index]
    ? [{ ...orderedTasks[index], logicalLaneId: lane.id, physicalLaneId: lane.physicalLaneId, gpuId: lane.gpuId }]
    : []);

  const thermalStops = deviceAssessments.filter((device) => device.state === "THERMAL_STOP");
  const nextCooldowns = { ...(state.cooldowns || {}) };
  for (const device of thermalStops) {
    nextCooldowns[device.lane.gpuId] = new Date(now.getTime() + budgets.thermalCooldownSeconds * 1_000).toISOString();
  }
  const scaled = previousCount !== admittedLanes.length;
  const nextGlobalCooldown = scaled
    ? new Date(now.getTime() + budgets.scaleCooldownSeconds * 1_000).toISOString()
    : (globalCooldownUntil > now ? globalCooldownUntil.toISOString() : null);
  const nominalLogicalLaneMinutes = assignments.length * budgets.partitionMinutes;
  const reasons = [];
  if (tasks.length === 0) reasons.push("NO_READY_TASK");
  if (backpressureActive) reasons.push("DOWNSTREAM_BACKPRESSURE");
  if (globalCooldownActive) reasons.push("GLOBAL_SCALE_COOLDOWN_ACTIVE");
  if (tasks.length > 0 && tasks.length < budgets.minimumReadyTasksForBurst) reasons.push("QUEUE_TOO_SHALLOW_FOR_BURST");
  if (deviceAssessments.some((device) => device.reasons.includes("GPU_SATURATED_NO_SCALE_UP"))) {
    reasons.push("SATURATED_GPU_PREVENTS_CAPACITY_CLAIM");
  }

  return {
    schema: "aione.capability-ladder-plan.v1",
    generatedAt: now.toISOString(),
    planningOnly: true,
    mutationPerformed: false,
    schedulerActionPerformed: false,
    level: levelFor(admittedLanes.length),
    capacity: {
      physicalGpuCount: lanes.length,
      configuredMaximumLogicalLanes: budgets.maxLogicalLanes,
      admittedLogicalLanes: admittedLanes.length,
      logicalLaneMultiplier: lanes.length ? Number((admittedLanes.length / lanes.length).toFixed(2)) : 0,
      throughputMultiplierEstimate: null,
      performanceClaim: "NOT_CLAIMED",
      explanation: "Les lanes logiques représentent des créneaux planifiés; elles ne garantissent ni calcul parallèle physique ni doublement de performance."
    },
    usefulTime: {
      assignedTasks: assignments.length,
      readyTasks: tasks.length,
      nominalLogicalLaneMinutes,
      wallClockMinutes: budgets.partitionMinutes,
      occupancyRatio: admittedLanes.length ? Number((assignments.length / admittedLanes.length).toFixed(4)) : 0,
      interpretation: "Mesure nominale de créneaux-lanes, distincte du temps humain, du temps mural et du débit GPU."
    },
    backpressure: {
      active: backpressureActive,
      downstreamBacklog: Math.max(0, finite(downstreamBacklog, 0)),
      maximumDownstreamBacklog: budgets.maximumDownstreamBacklog,
      scaleUpPermitted
    },
    budgets,
    devices: deviceAssessments,
    logicalLanes: admittedLanes,
    assignments,
    fairness: {
      strategy: "RECENTLY_LEAST_SERVED_PROJECT_ROUND_ROBIN",
      projectOrder: [...new Set(orderedTasks.map((task) => task.projectId))],
      starvationProtection: "ROUND_ROBIN_WHEN_SLOTS_ARE_AVAILABLE",
      boundedByAvailableSlots: true
    },
    audit: {
      configuredPhysicalWorkers: lanes.length,
      telemetryMatchedWorkers: deviceAssessments.filter((device) => device.telemetry).length,
      baseEligibleWorkers: baseDevices.length,
      burstEligibleWorkers: burstDevices.length,
      thermalStopGpuIds: thermalStops.map((device) => device.lane.gpuId),
      reasons
    },
    nextState: {
      activeLogicalLaneCount: admittedLanes.length,
      lastScaleAt: scaled ? now.toISOString() : state.lastScaleAt || null,
      cooldownUntil: nextGlobalCooldown,
      cooldowns: nextCooldowns,
      healthySamplesByGpu: Object.fromEntries(deviceAssessments.map((device) => [
        device.lane.gpuId,
        device.baseEligible && device.telemetry?.temperatureCelsius <= budgets.scaleUpBelowCelsius
          ? integer(state?.healthySamplesByGpu?.[device.lane.gpuId], 0, 0, 1_000_000) + 1
          : 0
      ]))
    },
    guardrails: {
      localFreeOnly: true,
      noDownload: true,
      noSchedulerMutation: true,
      hardThermalStop: true,
      cooldownRequired: true,
      backpressureRequired: true
    }
  };
}

export { DEFAULT_CAPABILITY_BUDGETS, assessDevice, normalizeBudgets };
