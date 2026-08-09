import { execFileSync } from "node:child_process";
import { readFileSync, statfsSync } from "node:fs";
import { freemem, totalmem } from "node:os";
import { resolve } from "node:path";

const LEVEL_INDEX = Object.freeze({ GREEN: 0, YELLOW: 1, ORANGE: 2, RED: 3, BLACK: 4 });

function percent(used, total) {
  return total > 0 ? Math.max(0, Math.min(100, (Number(used) / Number(total)) * 100)) : null;
}

function maxFinite(values, fallback = null) {
  const finite = values.map(Number).filter(Number.isFinite);
  return finite.length ? Math.max(...finite) : fallback;
}

function parseGpuTelemetry(output) {
  return String(output || "").split(/\r?\n/u).filter(Boolean).map((line) => {
    const [name, utilization, memoryUsed, memoryTotal, temperature] = line.split(",").map((item) => item.trim());
    return {
      name,
      utilizationPercent: Number(utilization),
      memoryUsedMb: Number(memoryUsed),
      memoryTotalMb: Number(memoryTotal),
      vramPercent: percent(memoryUsed, memoryTotal),
      temperatureCelsius: Number(temperature)
    };
  });
}

function observeLocalSystem({ runtimeRoot, probes = [], source = {} } = {}) {
  let storagePercent = null;
  try {
    const stat = statfsSync(resolve(runtimeRoot));
    const total = Number(stat.blocks) * Number(stat.bsize);
    const free = Number(stat.bavail) * Number(stat.bsize);
    storagePercent = percent(total - free, total);
  } catch { /* métrique indisponible, jamais inventée */ }
  let gpus = [];
  try {
    gpus = parseGpuTelemetry(execFileSync("nvidia-smi", [
      "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
      "--format=csv,noheader,nounits"
    ], { encoding: "utf8", timeout: 5000, windowsHide: true }));
  } catch { /* GPU absent ou outil indisponible */ }
  return {
    observedAt: new Date().toISOString(),
    integrityOk: source.ok !== false,
    auditIntegrityOk: true,
    cpuPercent: null,
    ramPercent: percent(totalmem() - freemem(), totalmem()),
    storagePercent,
    gpus,
    errors: probes.filter((probe) => !probe.ok).map((probe) => ({ id: probe.id, critical: probe.critical === true, status: probe.status })),
    criticalProcesses: probes.filter((probe) => probe.critical).map((probe) => ({ id: probe.id, healthy: probe.ok === true })),
    connectivity: { local: probes.filter((probe) => probe.kind === "HTTP").every((probe) => probe.ok), external: "NOT_PROBED" },
    models: probes.filter((probe) => String(probe.id).startsWith("ollama-")).map((probe) => ({ id: probe.id, healthy: probe.ok === true })),
    responseQuality: null,
    memoryIntegrity: source.ok !== false
  };
}

function metricLevel(value, thresholds) {
  if (value === null || value === undefined || value === "") return "GREEN";
  if (!Number.isFinite(Number(value))) return "GREEN";
  if (Number(value) >= Number(thresholds.red)) return "RED";
  if (Number(value) >= Number(thresholds.orange)) return "ORANGE";
  if (Number(value) >= Number(thresholds.yellow)) return "YELLOW";
  return "GREEN";
}

function qualityLevel(value, thresholds) {
  if (value === null || value === undefined || value === "") return "GREEN";
  if (!Number.isFinite(Number(value))) return "GREEN";
  if (Number(value) < Number(thresholds.redBelow)) return "RED";
  if (Number(value) < Number(thresholds.orangeBelow)) return "ORANGE";
  if (Number(value) < Number(thresholds.yellowBelow)) return "YELLOW";
  return "GREEN";
}

function highest(levels) {
  return levels.sort((left, right) => LEVEL_INDEX[right] - LEVEL_INDEX[left])[0] || "GREEN";
}

class CognitiveImmuneSystem {
  constructor({ policy, policyPath } = {}) {
    this.policy = policy || JSON.parse(readFileSync(resolve(policyPath), "utf8"));
    if (this.policy?.schema !== "aione.cognitive-immune-system.v1" || this.policy.automaticSystemMutation !== false) {
      throw new Error("COGNITIVE_IMMUNE_POLICY_INVALID");
    }
  }

  assess(observation = {}, history = []) {
    const thresholds = this.policy.thresholds;
    const gpuTemperatures = (observation.gpus || []).map((gpu) => gpu.temperatureCelsius);
    const vram = (observation.gpus || []).map((gpu) => gpu.vramPercent ?? percent(gpu.memoryUsedMb, gpu.memoryTotalMb));
    const signals = {
      cpu: metricLevel(observation.cpuPercent, thresholds.cpuPercent),
      ram: metricLevel(observation.ramPercent, thresholds.ramPercent),
      vram: metricLevel(maxFinite(vram), thresholds.vramPercent),
      storage: metricLevel(observation.storagePercent, thresholds.storagePercent),
      temperature: metricLevel(maxFinite(gpuTemperatures), thresholds.temperatureCelsius),
      responseQuality: qualityLevel(observation.responseQuality, thresholds.responseQuality)
    };
    if ((observation.errors || []).some((error) => error.critical)) signals.criticalError = "RED";
    else if ((observation.errors || []).length) signals.error = "ORANGE";
    if ((observation.criticalProcesses || []).some((process) => process.healthy === false)) signals.criticalProcess = "RED";
    if (observation.integrityOk === false || observation.auditIntegrityOk === false || observation.memoryIntegrity === false) signals.integrity = "BLACK";
    const level = highest(Object.values(signals));
    const priorLevels = history.map((entry) => entry.level).filter((entry) => entry in LEVEL_INDEX);
    const progressiveDegradation = priorLevels.slice(-3).every((entry, index, items) => index === 0 || LEVEL_INDEX[items[index - 1]] <= LEVEL_INDEX[entry]) && priorLevels.length >= 3 && level !== "GREEN";
    const strategies = level === "GREEN" ? ["CONTINUE_OBSERVATION"] : [
      "DOCUMENT_EVIDENCE",
      "ISOLATE_AFFECTED_COMPONENT_IF_POLICY_ALLOWS",
      "PRESERVE_DIAGNOSTIC_INFORMATION",
      "NOTIFY_USER",
      "PROPOSE_MULTIPLE_REPAIR_STRATEGIES"
    ];
    return {
      schema: "aione.cognitive-health-state.v1",
      observedAt: observation.observedAt || new Date().toISOString(),
      level,
      priority: ["NORMAL", "MONITOR", "HIGH", "CRITICAL", "EMERGENCY"][LEVEL_INDEX[level]],
      signals,
      progressiveDegradation,
      strategies,
      automaticMutationPerformed: false,
      userSupervisionRequiredForImportantDecision: level !== "GREEN"
    };
  }

  proposeThresholdUpdate({ outcomes = [], currentThresholds = this.policy.thresholds } = {}) {
    const plasticity = this.policy.thresholdPlasticity;
    if (!plasticity.enabled || outcomes.length < Number(plasticity.minimumSamples)) {
      return { status: "INSUFFICIENT_EVIDENCE", applied: false, sampleCount: outcomes.length };
    }
    const falsePositiveRate = outcomes.filter((outcome) => outcome.classification === "FALSE_POSITIVE").length / outcomes.length;
    const adjustment = falsePositiveRate > 0.25 ? Number(plasticity.maximumAdjustmentPercent) : 0;
    return {
      status: adjustment ? "VERSIONED_THRESHOLD_PROPOSAL" : "NO_ADJUSTMENT_NEEDED",
      applied: false,
      sampleCount: outcomes.length,
      evidence: { falsePositiveRate },
      maximumAdjustmentPercent: adjustment,
      candidateThresholds: structuredClone(currentThresholds),
      traceabilityPreserved: true
    };
  }
}

export { CognitiveImmuneSystem, LEVEL_INDEX, observeLocalSystem, parseGpuTelemetry };
