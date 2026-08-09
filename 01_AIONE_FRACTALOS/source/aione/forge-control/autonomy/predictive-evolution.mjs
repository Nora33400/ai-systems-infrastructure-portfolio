import {
  appendFileSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const TEMPLATES = new Set([
  "observer",
  "analyzer",
  "planner",
  "isolated-prototyper",
  "tester",
  "reviewer",
  "context-reconstructor",
  "incident-reproducer"
]);
const FORBIDDEN_KEYS = /authorization|cookie|password|secret|token|api.?key|private.?key|credential/i;

export class PredictiveEvolutionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "PredictiveEvolutionError";
    this.code = code;
  }
}

function fail(code, message) {
  throw new PredictiveEvolutionError(code, message);
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function hash(value) {
  return createHash("sha256").update(typeof value === "string" ? value : stableJson(value)).digest("hex");
}

function finite(value, field, { minimum = 0, maximum = Number.MAX_SAFE_INTEGER } = {}) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < minimum || number > maximum) {
    fail("INVALID_METRIC", `${field} doit être compris entre ${minimum} et ${maximum}.`);
  }
  return number;
}

function text(value, field, maximum = 500) {
  const normalized = String(value ?? "").trim();
  if (!normalized || normalized.length > maximum) fail("INVALID_TEXT", `${field} est absent ou trop long.`);
  return normalized;
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") {
    return typeof value === "string"
      ? value
          .replace(/(Bearer\s+)[^\s]+/gi, "$1[REDACTED]")
          .replace(/((?:password|secret|token|api.?key)\s*[:=]\s*)[^\s,;]+/gi, "$1[REDACTED]")
          .slice(0, 4_000)
      : value;
  }
  return Object.fromEntries(Object.entries(value).map(([key, nested]) => [
    key,
    FORBIDDEN_KEYS.test(key) ? "[REDACTED]" : redact(nested)
  ]));
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function readEvents(path) {
  if (!existsSync(path)) return [];
  const raw = readFileSync(path, "utf8").trim();
  if (!raw) return [];
  return raw.split(/\r?\n/).map((line, index) => {
    try {
      return JSON.parse(line);
    } catch {
      fail("LEDGER_CORRUPT", `Journal prédictif invalide à la ligne ${index + 1}.`);
    }
  });
}

function eventHash(event) {
  const body = { ...event };
  delete body.hash;
  return hash(body);
}

function verifyEvents(events) {
  let previousHash = null;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (
      event.sequence !== index + 1 ||
      event.previousHash !== previousHash ||
      event.hash !== eventHash(event)
    ) fail("LEDGER_CORRUPT", `Chaîne prédictive rompue à l’événement ${index + 1}.`);
    previousHash = event.hash;
  }
  return { ok: true, eventCount: events.length, head: previousHash };
}

function atomicJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  if (existsSync(path)) {
    writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
    unlinkSync(temporary);
  } else {
    renameSync(temporary, path);
  }
}

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function clamp(value) {
  return Math.max(0, Math.min(1, value));
}

function normalizeSample(sample, observedAt) {
  const metrics = sample?.metrics || {};
  return {
    sampleId: text(sample?.sampleId || `sample-${randomUUID()}`, "sampleId", 180),
    observedAt,
    metrics: {
      queueArrivalRate: finite(metrics.queueArrivalRate ?? 0, "queueArrivalRate"),
      queueServiceRate: finite(metrics.queueServiceRate ?? 0, "queueServiceRate"),
      queueAgeMinutes: finite(metrics.queueAgeMinutes ?? 0, "queueAgeMinutes"),
      gpuThermalHeadroom: finite(metrics.gpuThermalHeadroom ?? 1, "gpuThermalHeadroom", { maximum: 1 }),
      ramHeadroom: finite(metrics.ramHeadroom ?? 1, "ramHeadroom", { maximum: 1 }),
      diskHeadroom: finite(metrics.diskHeadroom ?? 1, "diskHeadroom", { maximum: 1 }),
      contextLatencyMs: finite(metrics.contextLatencyMs ?? 0, "contextLatencyMs"),
      testFailureRate: finite(metrics.testFailureRate ?? 0, "testFailureRate", { maximum: 1 }),
      implementationRejectionRate: finite(metrics.implementationRejectionRate ?? 0, "implementationRejectionRate", { maximum: 1 }),
      ownerReviewWaitMinutes: finite(metrics.ownerReviewWaitMinutes ?? 0, "ownerReviewWaitMinutes")
    },
    evidence: redact(sample?.evidence || {})
  };
}

function bottleneckSignals(samples) {
  const metrics = samples.map((sample) => sample.metrics);
  const arrival = average(metrics.map((item) => item.queueArrivalRate));
  const service = average(metrics.map((item) => item.queueServiceRate));
  return [
    {
      id: "queue-capacity",
      severity: clamp(service > 0 ? (arrival - service) / Math.max(arrival, 1) : arrival > 0 ? 1 : 0),
      observed: { arrival, service }
    },
    {
      id: "thermal-headroom",
      severity: clamp(1 - average(metrics.map((item) => item.gpuThermalHeadroom))),
      observed: { headroom: average(metrics.map((item) => item.gpuThermalHeadroom)) }
    },
    {
      id: "context-latency",
      severity: clamp(average(metrics.map((item) => item.contextLatencyMs)) / 10_000),
      observed: { milliseconds: average(metrics.map((item) => item.contextLatencyMs)) }
    },
    {
      id: "quality-rejection",
      severity: clamp(average(metrics.map((item) =>
        (item.testFailureRate + item.implementationRejectionRate) / 2
      ))),
      observed: {
        testFailureRate: average(metrics.map((item) => item.testFailureRate)),
        implementationRejectionRate: average(metrics.map((item) => item.implementationRejectionRate))
      }
    },
    {
      id: "owner-review-wait",
      severity: clamp(average(metrics.map((item) => item.ownerReviewWaitMinutes)) / 1440),
      observed: { minutes: average(metrics.map((item) => item.ownerReviewWaitMinutes)) }
    }
  ].sort((left, right) => right.severity - left.severity);
}

function scenarioFor(signal, index) {
  const map = {
    "queue-capacity": ["observer", "planner", "isolated-prototyper"],
    "thermal-headroom": ["observer", "planner", "tester"],
    "context-latency": ["context-reconstructor", "tester", "reviewer"],
    "quality-rejection": ["incident-reproducer", "tester", "reviewer"],
    "owner-review-wait": ["analyzer", "planner", "reviewer"]
  };
  const templates = map[signal.id] || ["analyzer"];
  const template = templates[index % templates.length];
  return {
    scenarioId: `scenario:${signal.id}:${index + 1}`,
    bottleneckId: signal.id,
    hypothesis: `Réduire ${signal.id} avec le processus ${template}.`,
    template,
    permissionCeiling: "L4_ISOLATED_EXECUTE",
    canonicalMutation: false,
    resourceBudget: {
      maxWallClockSeconds: 900,
      maxCpuSeconds: 300,
      maxMemoryMb: 2048,
      maxGpuMemoryMb: template === "isolated-prototyper" ? 4096 : 0,
      maxStorageMb: 256,
      maxNetworkRequests: 0
    },
    stopCriteria: ["budget-exceeded", "no-measured-benefit", "permission-needed", "critical-incident"],
    tests: ["baseline-comparison", "no-regression", "permission-monotonicity"],
    rollback: ["discard-isolated-experiment", "restore-previous-process-parameters"]
  };
}

export class PredictiveEvolution {
  constructor({ configPath, runtimeRoot, clock = () => new Date() } = {}) {
    if (!configPath) fail("CONFIG_REQUIRED", "La configuration d’évolution est requise.");
    const resolvedConfigPath = configPath instanceof URL ? fileURLToPath(configPath) : resolve(configPath);
    this.config = readJson(resolvedConfigPath, null);
    if (this.config?.schema !== "aione.bounded-adaptive-evolution.v1" || !this.config.enabled) {
      fail("CONFIG_INVALID", "Configuration d’évolution absente, invalide ou désactivée.");
    }
    if (this.config.autonomousCeiling?.level !== "L4_ISOLATED_EXECUTE") {
      fail("UNSAFE_CEILING", "L’auto-évolution doit rester plafonnée à L4.");
    }
    this.clock = clock;
    this.runtimeRoot = resolve(runtimeRoot || this.config.runtimeRoot);
    this.paths = Object.freeze({
      ledger: join(this.runtimeRoot, "evolution-events.jsonl"),
      lock: join(this.runtimeRoot, ".evolution.lock"),
      plan: join(this.runtimeRoot, "current-plan.json")
    });
    mkdirSync(this.runtimeRoot, { recursive: true });
    verifyEvents(readEvents(this.paths.ledger));
  }

  #withLock(operation) {
    let descriptor;
    try {
      descriptor = openSync(this.paths.lock, "wx");
    } catch (error) {
      if (error?.code === "EEXIST") fail("CONCURRENT_WRITE", "Une évolution est déjà en cours d’écriture.");
      throw error;
    }
    try {
      return operation();
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(this.paths.lock)) unlinkSync(this.paths.lock);
    }
  }

  #append(type, payload) {
    return this.#withLock(() => {
      const events = readEvents(this.paths.ledger);
      verifyEvents(events);
      const event = {
        schema: "aione.predictive-evolution-event.v1",
        sequence: events.length + 1,
        eventId: randomUUID(),
        type,
        at: this.clock().toISOString(),
        previousHash: events.at(-1)?.hash || null,
        payload: redact(payload)
      };
      event.hash = eventHash(event);
      appendFileSync(this.paths.ledger, `${JSON.stringify(event)}\n`, "utf8");
      return event;
    });
  }

  observe(sample) {
    const events = readEvents(this.paths.ledger);
    verifyEvents(events);
    const observedAt = this.clock().toISOString();
    const normalized = normalizeSample(sample, observedAt);
    const duplicate = events.find((event) =>
      event.type === "OBSERVATION" && event.payload.sampleId === normalized.sampleId
    );
    if (duplicate) return { status: "DUPLICATE", observation: duplicate.payload };
    this.#append("OBSERVATION", normalized);
    return { status: "RECORDED", observation: normalized };
  }

  plan() {
    const events = readEvents(this.paths.ledger);
    verifyEvents(events);
    const windowSize = Number(this.config.predictiveBottleneck.observationWindowSamples || 24);
    const observations = events
      .filter((event) => event.type === "OBSERVATION")
      .slice(-windowSize)
      .map((event) => event.payload);
    const minimum = Number(this.config.predictiveBottleneck.minimumEvidenceSamples || 6);
    if (observations.length < minimum) {
      return { status: "INSUFFICIENT_EVIDENCE", samples: observations.length, minimum };
    }
    const signals = bottleneckSignals(observations);
    const scenarioLimit = Number(this.config.predictiveBottleneck.speculation.maximumConcurrentScenarios || 5);
    const scenarios = signals.slice(0, scenarioLimit).map((signal, index) => {
      const scenario = scenarioFor(signal, index);
      if (!TEMPLATES.has(scenario.template)) fail("TEMPLATE_DENIED", `Template interdit: ${scenario.template}`);
      const vision = clamp(0.55 + signal.severity * 0.35);
      const timewarp = clamp(0.5 + signal.severity * 0.4);
      const coherental = clamp(0.9 - signal.severity * 0.1);
      return {
        ...scenario,
        score: {
          vision,
          timewarp,
          coherental,
          total: Number(((vision + timewarp + coherental) / 3).toFixed(4))
        },
        confidence: Number(Math.min(0.95, observations.length / windowSize * 0.8 + signal.severity * 0.2).toFixed(4))
      };
    });
    const plan = {
      schema: "aione.predictive-evolution-plan.v1",
      generatedAt: this.clock().toISOString(),
      observationCount: observations.length,
      horizonsMinutes: this.config.predictiveBottleneck.forecastHorizonsMinutes,
      bottlenecks: signals,
      scenarios,
      execution: "ISOLATED_EXPERIMENT_ONLY",
      permissionCeiling: "L4_ISOLATED_EXECUTE",
      canonicalPromotion: "OWNER_REQUIRED"
    };
    atomicJson(this.paths.plan, plan);
    this.#append("PLAN_GENERATED", { planHash: hash(plan), observationCount: observations.length, scenarios });
    return { status: "PLANNED", plan };
  }

  recordExperiment({ scenarioId, baseline, candidate, testsPassed, permissionsUnchanged, rollbackReady } = {}) {
    const plan = readJson(this.paths.plan, null);
    const scenario = plan?.scenarios?.find((item) => item.scenarioId === scenarioId);
    if (!scenario) fail("UNKNOWN_SCENARIO", `Scénario inconnu: ${scenarioId}`);
    const baselineValue = finite(baseline, "baseline");
    const candidateValue = finite(candidate, "candidate");
    const improved = candidateValue < baselineValue;
    const accepted = Boolean(improved && testsPassed && permissionsUnchanged && rollbackReady);
    const result = {
      scenarioId,
      baseline: baselineValue,
      candidate: candidateValue,
      improvementRatio: baselineValue > 0 ? (baselineValue - candidateValue) / baselineValue : 0,
      testsPassed: Boolean(testsPassed),
      permissionsUnchanged: Boolean(permissionsUnchanged),
      rollbackReady: Boolean(rollbackReady),
      decision: accepted ? "PROPOSE_OWNER_REVIEW" : "ROLLBACK_ISOLATED",
      canonicalMutation: false
    };
    this.#append("EXPERIMENT_EVALUATED", result);
    return result;
  }

  status() {
    const events = readEvents(this.paths.ledger);
    const integrity = verifyEvents(events);
    const plan = readJson(this.paths.plan, null);
    return {
      schema: "aione.predictive-evolution-status.v1",
      ok: true,
      mode: this.config.mode,
      permissionCeiling: this.config.autonomousCeiling.level,
      observations: events.filter((event) => event.type === "OBSERVATION").length,
      experiments: events.filter((event) => event.type === "EXPERIMENT_EVALUATED").length,
      plan,
      integrity
    };
  }
}
