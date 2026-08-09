import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  writeFileSync
} from "node:fs";
import { dirname, join, resolve } from "node:path";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_MS = 7 * DAY_MS;
const DEFAULT_ROOT = "S:\\AI_LAB\\Runtime\\WeekSoak";
const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(authorization|cookie|password|secret|token|api.?key|private.?key|credential)/iu;
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/u;
const SEVERITIES = Object.freeze(["INFO", "WARNING", "ERROR", "CRITICAL"]);
const STATE_SCHEMA = "aione.week-soak-state.v1";
const SNAPSHOT_SCHEMA = "aione.week-soak-snapshot.v1";
const SAMPLE_SCHEMA = "aione.week-soak-sample.v1";
const REPORT_SCHEMA = "aione.week-soak-report.v1";
const LOCK_SCHEMA = "aione.week-soak-lock.v1";
const GENESIS_HASH = "GENESIS";

const DEFAULT_CONFIG = Object.freeze({
  sampleIntervalMs: 5 * 60 * 1000,
  lockLeaseMs: 5 * 60 * 1000,
  maxSamples: 2_500,
  maxSampleBytes: 48 * 1024,
  maxSnapshotBytes: 64 * 1024 * 1024,
  maxStateBytes: 4 * 1024 * 1024,
  maxAnomalyExamples: 512,
  maxLockHistory: 4_096,
  gpuTemperatureWarningC: 82,
  gpuTemperatureCriticalC: 88,
  queueStallSeconds: 2 * 60 * 60,
  criteria: Object.freeze({
    minCoverageRatio: 0.90,
    minForgeHealthyRatio: 0.99,
    minGpuWorkerActiveRatio: 0.95,
    maxCriticalErrors: 0,
    minTestsExecuted: 1,
    minTestPassRate: 0.98,
    minImplementationsCompleted: 1,
    minImplementationSuccessRate: 0.80,
    maxCanonicalMutations: 0,
    maxQueueStallSamples: 12,
    maxChainIssues: 0
  })
});

export const WEEK_SOAK = Object.freeze({
  durationMs: WEEK_MS,
  defaultRoot: DEFAULT_ROOT,
  sampleSchema: SAMPLE_SCHEMA,
  snapshotSchema: SNAPSHOT_SCHEMA,
  reportSchema: REPORT_SCHEMA,
  stateSchema: STATE_SCHEMA,
  severities: SEVERITIES
});

export class WeekSoakError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "WeekSoakError";
    this.code = code;
  }
}

function fail(code, message) {
  throw new WeekSoakError(code, message);
}

function plainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, keys, code, label) {
  if (!plainObject(value)) fail(code, `${label} doit être un objet simple.`);
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length ||
    actual.some((key, index) => key !== expected[index])
  ) {
    fail(code, `${label} ne respecte pas le schéma strict.`);
  }
}

function allowedKeys(value, keys, code, label) {
  if (!plainObject(value)) fail(code, `${label} doit être un objet simple.`);
  if (Object.keys(value).some((key) => !keys.includes(key))) {
    fail(code, `${label} contient une propriété inconnue.`);
  }
}

function boundedString(value, label, max = 512) {
  if (
    typeof value !== "string" ||
    value.trim() !== value ||
    value.length === 0 ||
    value.length > max ||
    value.includes("\0")
  ) {
    fail("INVALID_STRING", `${label} est invalide.`);
  }
  return value;
}

function identifier(value, label) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) {
    fail("INVALID_IDENTIFIER", `${label} est invalide.`);
  }
  if (/\bsk-[A-Za-z0-9_-]{8,}\b/gu.test(value)) {
    fail("SECRET_IN_IDENTIFIER", `${label} ressemble à un secret et est refusé.`);
  }
  return value;
}

function finiteNumber(value, label, { min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
  if (!Number.isFinite(value) || value < min || value > max) {
    fail("INVALID_METRIC", `${label} doit être un nombre borné.`);
  }
  return value;
}

function integer(value, label, bounds = {}) {
  finiteNumber(value, label, bounds);
  if (!Number.isSafeInteger(value)) fail("INVALID_METRIC", `${label} doit être un entier.`);
  return value;
}

function ratio(value, label) {
  return finiteNumber(value, label, { min: 0, max: 1 });
}

function parseInstant(value, label) {
  boundedString(value, label, 64);
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString() !== value) {
    fail("INVALID_TIME", `${label} doit être un instant ISO canonique.`);
  }
  return timestamp;
}

function nowIso(clock) {
  const value = clock();
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) fail("INVALID_CLOCK", "L'horloge est invalide.");
  return date.toISOString();
}

function canonicalize(value) {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  if (plainObject(value)) {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalize(value[key])])
    );
  }
  fail("NON_CANONICAL_VALUE", "Une valeur persistée n'est pas canonique.");
}

export function canonicalSoakJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function hashSoakValue(value) {
  return createHash("sha256").update(canonicalSoakJson(value), "utf8").digest("hex");
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
}

function sanitizeText(value) {
  return value
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/giu, `Bearer ${REDACTED}`)
    .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/gu, REDACTED)
    .replace(
      /\b(password|secret|token|api[_-]?key|credential)\s*[:=]\s*[^\s,;]+/giu,
      (_match, key) => `${key}=${REDACTED}`
    );
}

export function redactSoakSecrets(value) {
  if (typeof value === "string") return sanitizeText(value);
  if (Array.isArray(value)) return value.map(redactSoakSecrets);
  if (!plainObject(value)) return value;
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [
    key,
    SENSITIVE_KEY.test(key) ? REDACTED : redactSoakSecrets(child)
  ]));
}

function normalizeForge(value) {
  exactKeys(
    value,
    ["healthy", "status", "uptimeSeconds", "responseTimeMs"],
    "INVALID_FORGE_SAMPLE",
    "sample.forge"
  );
  if (typeof value.healthy !== "boolean") {
    fail("INVALID_FORGE_SAMPLE", "sample.forge.healthy doit être booléen.");
  }
  return {
    healthy: value.healthy,
    status: sanitizeText(boundedString(value.status, "sample.forge.status", 120)),
    uptimeSeconds: integer(value.uptimeSeconds, "sample.forge.uptimeSeconds"),
    responseTimeMs: finiteNumber(value.responseTimeMs, "sample.forge.responseTimeMs", {
      max: 60_000
    })
  };
}

function normalizeGpu(value, index) {
  exactKeys(
    value,
    [
      "id",
      "model",
      "workerActive",
      "utilizationPercent",
      "temperatureC",
      "memoryUsedMb",
      "memoryTotalMb",
      "queueDepth"
    ],
    "INVALID_GPU_SAMPLE",
    `sample.gpus[${index}]`
  );
  if (typeof value.workerActive !== "boolean") {
    fail("INVALID_GPU_SAMPLE", `sample.gpus[${index}].workerActive doit être booléen.`);
  }
  const memoryTotalMb = integer(
    value.memoryTotalMb,
    `sample.gpus[${index}].memoryTotalMb`,
    { min: 1, max: 1_048_576 }
  );
  const memoryUsedMb = integer(
    value.memoryUsedMb,
    `sample.gpus[${index}].memoryUsedMb`,
    { max: memoryTotalMb }
  );
  return {
    id: identifier(value.id, `sample.gpus[${index}].id`),
    model: sanitizeText(boundedString(value.model, `sample.gpus[${index}].model`, 160)),
    workerActive: value.workerActive,
    utilizationPercent: finiteNumber(
      value.utilizationPercent,
      `sample.gpus[${index}].utilizationPercent`,
      { max: 100 }
    ),
    temperatureC: finiteNumber(value.temperatureC, `sample.gpus[${index}].temperatureC`, {
      min: -50,
      max: 150
    }),
    memoryUsedMb,
    memoryTotalMb,
    queueDepth: integer(value.queueDepth, `sample.gpus[${index}].queueDepth`)
  };
}

function normalizeQueues(value) {
  exactKeys(
    value,
    ["pending", "running", "completed", "failed", "oldestPendingAgeSeconds"],
    "INVALID_QUEUE_SAMPLE",
    "sample.queues"
  );
  return Object.fromEntries(Object.keys(value).map((key) => [
    key,
    integer(value[key], `sample.queues.${key}`)
  ]));
}

function normalizeErrors(value) {
  if (!Array.isArray(value) || value.length > 128) {
    fail("INVALID_ERROR_SAMPLE", "sample.errors doit être une liste bornée.");
  }
  return value.map((error, index) => {
    exactKeys(
      error,
      ["code", "severity", "count", "message"],
      "INVALID_ERROR_SAMPLE",
      `sample.errors[${index}]`
    );
    if (!SEVERITIES.includes(error.severity)) {
      fail("INVALID_ERROR_SAMPLE", `sample.errors[${index}].severity est invalide.`);
    }
    return {
      code: identifier(error.code, `sample.errors[${index}].code`),
      severity: error.severity,
      count: integer(error.count, `sample.errors[${index}].count`, { min: 1 }),
      message: sanitizeText(
        boundedString(error.message, `sample.errors[${index}].message`, 512)
      )
    };
  });
}

function normalizeCounters(value, keys, label) {
  exactKeys(value, keys, "INVALID_COUNTER_SAMPLE", label);
  return Object.fromEntries(keys.map((key) => [
    key,
    integer(value[key], `${label}.${key}`)
  ]));
}

export function normalizeWeekSoakSample(sample) {
  exactKeys(
    sample,
    [
      "schema",
      "sampleId",
      "observedAt",
      "forge",
      "gpus",
      "queues",
      "errors",
      "throughput",
      "tests",
      "implementations"
    ],
    "INVALID_SAMPLE",
    "sample"
  );
  if (sample.schema !== SAMPLE_SCHEMA) fail("INVALID_SAMPLE", "Schéma d'échantillon inconnu.");
  parseInstant(sample.observedAt, "sample.observedAt");
  if (!Array.isArray(sample.gpus) || sample.gpus.length !== 2) {
    fail("INVALID_GPU_SAMPLE", "Deux GPU exactement doivent être observés.");
  }
  const gpus = sample.gpus.map(normalizeGpu).sort((left, right) =>
    left.id.localeCompare(right.id)
  );
  if (gpus[0].id === gpus[1].id) {
    fail("INVALID_GPU_SAMPLE", "Les deux GPU doivent avoir des identités distinctes.");
  }
  const normalized = {
    schema: SAMPLE_SCHEMA,
    sampleId: identifier(sample.sampleId, "sample.sampleId"),
    observedAt: sample.observedAt,
    forge: normalizeForge(sample.forge),
    gpus,
    queues: normalizeQueues(sample.queues),
    errors: normalizeErrors(sample.errors),
    throughput: normalizeCounters(
      sample.throughput,
      ["proposalsProduced", "artifactsProduced", "bytesProduced"],
      "sample.throughput"
    ),
    tests: normalizeCounters(
      sample.tests,
      ["passed", "failed", "skipped", "durationMs"],
      "sample.tests"
    ),
    implementations: normalizeCounters(
      sample.implementations,
      ["queued", "succeeded", "failed", "canonicalMutations"],
      "sample.implementations"
    )
  };
  const redacted = redactSoakSecrets(normalized);
  return deepFreeze(redacted);
}

function normalizeCriteria(value) {
  exactKeys(
    value,
    [
      "minCoverageRatio",
      "minForgeHealthyRatio",
      "minGpuWorkerActiveRatio",
      "maxCriticalErrors",
      "minTestsExecuted",
      "minTestPassRate",
      "minImplementationsCompleted",
    "minImplementationSuccessRate",
    "maxCanonicalMutations",
    "maxQueueStallSamples",
      "maxChainIssues"
    ],
    "INVALID_CONFIG",
    "config.criteria"
  );
  return deepFreeze({
    minCoverageRatio: ratio(value.minCoverageRatio, "criteria.minCoverageRatio"),
    minForgeHealthyRatio: ratio(
      value.minForgeHealthyRatio,
      "criteria.minForgeHealthyRatio"
    ),
    minGpuWorkerActiveRatio: ratio(
      value.minGpuWorkerActiveRatio,
      "criteria.minGpuWorkerActiveRatio"
    ),
    maxCriticalErrors: integer(value.maxCriticalErrors, "criteria.maxCriticalErrors"),
    minTestsExecuted: integer(value.minTestsExecuted, "criteria.minTestsExecuted"),
    minTestPassRate: ratio(value.minTestPassRate, "criteria.minTestPassRate"),
    minImplementationsCompleted: integer(
      value.minImplementationsCompleted,
      "criteria.minImplementationsCompleted"
    ),
    minImplementationSuccessRate: ratio(
      value.minImplementationSuccessRate,
      "criteria.minImplementationSuccessRate"
    ),
    maxCanonicalMutations: integer(
      value.maxCanonicalMutations,
      "criteria.maxCanonicalMutations"
    ),
    maxQueueStallSamples: integer(
      value.maxQueueStallSamples,
      "criteria.maxQueueStallSamples"
    ),
    maxChainIssues: integer(value.maxChainIssues, "criteria.maxChainIssues")
  });
}

function normalizeConfig(candidate = {}) {
  allowedKeys(
    candidate,
    [
      "sampleIntervalMs",
      "lockLeaseMs",
      "maxSamples",
      "maxSampleBytes",
      "maxSnapshotBytes",
      "maxStateBytes",
      "maxAnomalyExamples",
      "maxLockHistory",
      "gpuTemperatureWarningC",
      "gpuTemperatureCriticalC",
      "queueStallSeconds",
      "criteria"
    ],
    "INVALID_CONFIG",
    "config"
  );
  const merged = {
    ...DEFAULT_CONFIG,
    ...candidate,
    criteria: { ...DEFAULT_CONFIG.criteria, ...(candidate.criteria || {}) }
  };
  const config = {
    sampleIntervalMs: integer(merged.sampleIntervalMs, "config.sampleIntervalMs", {
      min: 60_000,
      max: DAY_MS
    }),
    lockLeaseMs: integer(merged.lockLeaseMs, "config.lockLeaseMs", {
      min: 1_000,
      max: DAY_MS
    }),
    maxSamples: integer(merged.maxSamples, "config.maxSamples", {
      min: 8,
      max: 20_000
    }),
    maxSampleBytes: integer(merged.maxSampleBytes, "config.maxSampleBytes", {
      min: 1_024,
      max: 1024 * 1024
    }),
    maxSnapshotBytes: integer(merged.maxSnapshotBytes, "config.maxSnapshotBytes", {
      min: 1024 * 1024,
      max: 1024 * 1024 * 1024
    }),
    maxStateBytes: integer(merged.maxStateBytes, "config.maxStateBytes", {
      min: 64 * 1024,
      max: 64 * 1024 * 1024
    }),
    maxAnomalyExamples: integer(merged.maxAnomalyExamples, "config.maxAnomalyExamples", {
      min: 1,
      max: 10_000
    }),
    maxLockHistory: integer(merged.maxLockHistory, "config.maxLockHistory", {
      min: 8,
      max: 100_000
    }),
    gpuTemperatureWarningC: finiteNumber(
      merged.gpuTemperatureWarningC,
      "config.gpuTemperatureWarningC",
      { min: 0, max: 150 }
    ),
    gpuTemperatureCriticalC: finiteNumber(
      merged.gpuTemperatureCriticalC,
      "config.gpuTemperatureCriticalC",
      { min: 0, max: 150 }
    ),
    queueStallSeconds: integer(merged.queueStallSeconds, "config.queueStallSeconds", {
      min: 1,
      max: WEEK_MS / 1000
    }),
    criteria: normalizeCriteria(merged.criteria)
  };
  if (config.gpuTemperatureCriticalC <= config.gpuTemperatureWarningC) {
    fail("INVALID_CONFIG", "Le seuil GPU critique doit dépasser le seuil d'avertissement.");
  }
  const expectedSamples = Math.floor(WEEK_MS / config.sampleIntervalMs) + 1;
  if (config.maxSamples < expectedSamples) {
    fail("INVALID_CONFIG", "maxSamples est inférieur au nombre d'échantillons attendus.");
  }
  return deepFreeze(config);
}

function ensureDirectory(target) {
  mkdirSync(target, { recursive: true });
  return target;
}

function atomicWrite(target, content, maxBytes = Number.MAX_SAFE_INTEGER) {
  ensureDirectory(dirname(target));
  if (Buffer.byteLength(content, "utf8") > maxBytes) {
    fail("PERSISTENCE_QUOTA_EXCEEDED", "La donnée persistée dépasse son quota.");
  }
  const temporary = `${target}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
  writeFileSync(temporary, content, { encoding: "utf8", flag: "wx" });
  renameSync(temporary, target);
}

function atomicJson(target, value, maxBytes = Number.MAX_SAFE_INTEGER) {
  const content = `${JSON.stringify(value, null, 2)}\n`;
  if (Buffer.byteLength(content, "utf8") > maxBytes) {
    fail("PERSISTENCE_QUOTA_EXCEEDED", "La donnée persistée dépasse son quota.");
  }
  atomicWrite(target, content, maxBytes);
}

function readJson(target, maxBytes = 64 * 1024 * 1024) {
  if (!existsSync(target)) return null;
  try {
    if (statSync(target).size > maxBytes) return null;
    return JSON.parse(readFileSync(target, "utf8"));
  } catch {
    return null;
  }
}

function compactStamp(iso) {
  return iso.replace(/[-:.TZ]/gu, "");
}

function lockHistoryName(lock) {
  return `lock-${compactStamp(lock.acquiredAt)}-${lock.token}.json`;
}

function validateLock(lock) {
  return (
    plainObject(lock) &&
    lock.schema === LOCK_SCHEMA &&
    typeof lock.token === "string" &&
    IDENTIFIER.test(lock.token) &&
    Number.isFinite(Date.parse(lock.acquiredAt))
  );
}

function snapshotBody(record) {
  const body = { ...record };
  delete body.hash;
  return body;
}

function validateStoredSnapshot(record) {
  exactKeys(
    record,
    [
      "schema",
      "runId",
      "sequence",
      "sampleId",
      "observedAt",
      "capturedAt",
      "previousHash",
      "sample",
      "hash"
    ],
    "INVALID_SNAPSHOT",
    "snapshot"
  );
  if (record.schema !== SNAPSHOT_SCHEMA) fail("INVALID_SNAPSHOT", "Schéma snapshot inconnu.");
  identifier(record.runId, "snapshot.runId");
  integer(record.sequence, "snapshot.sequence", { min: 1 });
  identifier(record.sampleId, "snapshot.sampleId");
  parseInstant(record.observedAt, "snapshot.observedAt");
  parseInstant(record.capturedAt, "snapshot.capturedAt");
  if (
    record.previousHash !== GENESIS_HASH &&
    !/^[a-f0-9]{64}$/u.test(record.previousHash)
  ) {
    fail("INVALID_SNAPSHOT", "Le précédent hash est invalide.");
  }
  if (!/^[a-f0-9]{64}$/u.test(record.hash)) {
    fail("INVALID_SNAPSHOT", "Le hash est invalide.");
  }
  const sample = normalizeWeekSoakSample(record.sample);
  if (
    record.sampleId !== sample.sampleId ||
    record.observedAt !== sample.observedAt ||
    canonicalSoakJson(record.sample) !== canonicalSoakJson(sample)
  ) {
    fail("INVALID_SNAPSHOT", "L'échantillon snapshot n'est pas canonique.");
  }
  return record;
}

function emptyTotals() {
  return {
    samples: 0,
    forgeHealthySamples: 0,
    gpuActiveObservations: 0,
    gpuObservations: 0,
    queuePendingSum: 0,
    queuePendingMax: 0,
    queueRunningSum: 0,
    queueRunningMax: 0,
    queueStallSamples: 0,
    errorCount: 0,
    criticalErrorCount: 0,
    proposalsProduced: 0,
    artifactsProduced: 0,
    bytesProduced: 0,
    testsPassed: 0,
    testsFailed: 0,
    testsSkipped: 0,
    testDurationMs: 0,
    implementationsQueued: 0,
    implementationsSucceeded: 0,
    implementationsFailed: 0,
    canonicalMutations: 0
  };
}

function addSample(totals, sample, config) {
  totals.samples += 1;
  totals.forgeHealthySamples += sample.forge.healthy ? 1 : 0;
  totals.gpuObservations += sample.gpus.length;
  totals.gpuActiveObservations += sample.gpus.filter((gpu) => gpu.workerActive).length;
  totals.queuePendingSum += sample.queues.pending;
  totals.queuePendingMax = Math.max(totals.queuePendingMax, sample.queues.pending);
  totals.queueRunningSum += sample.queues.running;
  totals.queueRunningMax = Math.max(totals.queueRunningMax, sample.queues.running);
  if (
    sample.queues.pending > 0 &&
    sample.queues.oldestPendingAgeSeconds >= config.queueStallSeconds
  ) totals.queueStallSamples += 1;
  for (const error of sample.errors) {
    totals.errorCount += error.count;
    if (error.severity === "CRITICAL") totals.criticalErrorCount += error.count;
  }
  totals.proposalsProduced += sample.throughput.proposalsProduced;
  totals.artifactsProduced += sample.throughput.artifactsProduced;
  totals.bytesProduced += sample.throughput.bytesProduced;
  totals.testsPassed += sample.tests.passed;
  totals.testsFailed += sample.tests.failed;
  totals.testsSkipped += sample.tests.skipped;
  totals.testDurationMs += sample.tests.durationMs;
  totals.implementationsQueued += sample.implementations.queued;
  totals.implementationsSucceeded += sample.implementations.succeeded;
  totals.implementationsFailed += sample.implementations.failed;
  totals.canonicalMutations += sample.implementations.canonicalMutations;
}

function rounded(value) {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function completeTotals(totals) {
  const testsExecuted = totals.testsPassed + totals.testsFailed;
  const implementationsCompleted =
    totals.implementationsSucceeded + totals.implementationsFailed;
  return {
    ...totals,
    forgeHealthyRatio: totals.samples
      ? rounded(totals.forgeHealthySamples / totals.samples)
      : 0,
    gpuWorkerActiveRatio: totals.gpuObservations
      ? rounded(totals.gpuActiveObservations / totals.gpuObservations)
      : 0,
    queuePendingAverage: totals.samples
      ? rounded(totals.queuePendingSum / totals.samples)
      : 0,
    queueRunningAverage: totals.samples
      ? rounded(totals.queueRunningSum / totals.samples)
      : 0,
    testsExecuted,
    testPassRate: testsExecuted ? rounded(totals.testsPassed / testsExecuted) : 0,
    implementationsCompleted,
    implementationSuccessRate: implementationsCompleted
      ? rounded(totals.implementationsSucceeded / implementationsCompleted)
      : 0
  };
}

function sampleAnomalies(record, config) {
  const anomalies = [];
  const push = (code, severity, message, details = {}) => anomalies.push({
    code,
    severity,
    sampleId: record.sampleId,
    observedAt: record.observedAt,
    message,
    details
  });
  const { sample } = record;
  if (!sample.forge.healthy) {
    push("FORGE_UNHEALTHY", "CRITICAL", "La Forge n'est pas saine.", {
      status: sample.forge.status
    });
  }
  for (const gpu of sample.gpus) {
    if (!gpu.workerActive) {
      push("GPU_WORKER_INACTIVE", "ERROR", "Un worker GPU est inactif.", { gpuId: gpu.id });
    }
    if (gpu.temperatureC >= config.gpuTemperatureCriticalC) {
      push("GPU_TEMPERATURE_CRITICAL", "CRITICAL", "Température GPU critique.", {
        gpuId: gpu.id,
        temperatureC: gpu.temperatureC
      });
    } else if (gpu.temperatureC >= config.gpuTemperatureWarningC) {
      push("GPU_TEMPERATURE_WARNING", "WARNING", "Température GPU élevée.", {
        gpuId: gpu.id,
        temperatureC: gpu.temperatureC
      });
    }
  }
  if (
    sample.queues.pending > 0 &&
    sample.queues.oldestPendingAgeSeconds >= config.queueStallSeconds
  ) {
    push("QUEUE_STALLED", "ERROR", "La plus ancienne tâche dépasse le seuil de blocage.", {
      pending: sample.queues.pending,
      oldestPendingAgeSeconds: sample.queues.oldestPendingAgeSeconds
    });
  }
  for (const error of sample.errors) {
    push(`REPORTED_${error.code}`, error.severity, error.message, { count: error.count });
  }
  if (sample.tests.failed > 0) {
    push("TEST_FAILURE", "ERROR", "Un ou plusieurs tests ont échoué.", {
      failed: sample.tests.failed
    });
  }
  if (sample.implementations.failed > 0) {
    push("IMPLEMENTATION_FAILURE", "ERROR", "Une implémentation a échoué.", {
      failed: sample.implementations.failed
    });
  }
  if (sample.implementations.canonicalMutations > 0) {
    push("CANONICAL_MUTATION_OBSERVED", "WARNING", "Une mutation canonique a été observée.", {
      count: sample.implementations.canonicalMutations
    });
  }
  return anomalies;
}

function aggregateRecords(records, config) {
  const totals = emptyTotals();
  const hourly = new Map();
  const daily = new Map();
  const anomalyCounts = {};
  const anomalyExamples = [];
  let anomalyTotal = 0;
  for (const record of records) {
    addSample(totals, record.sample, config);
    const hourKey = record.observedAt.slice(0, 13) + ":00:00.000Z";
    const dayKey = record.observedAt.slice(0, 10);
    if (!hourly.has(hourKey)) hourly.set(hourKey, emptyTotals());
    if (!daily.has(dayKey)) daily.set(dayKey, emptyTotals());
    addSample(hourly.get(hourKey), record.sample, config);
    addSample(daily.get(dayKey), record.sample, config);
    for (const anomaly of sampleAnomalies(record, config)) {
      anomalyTotal += 1;
      anomalyCounts[anomaly.code] = (anomalyCounts[anomaly.code] || 0) + 1;
      if (anomalyExamples.length < config.maxAnomalyExamples) {
        anomalyExamples.push(anomaly);
      }
    }
  }
  const serializeBuckets = (buckets) => [...buckets.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([period, values]) => ({ period, ...completeTotals(values) }));
  return deepFreeze({
    totals: completeTotals(totals),
    hourly: serializeBuckets(hourly),
    daily: serializeBuckets(daily),
    anomalies: {
      total: anomalyTotal,
      truncated: anomalyTotal > anomalyExamples.length,
      byCode: Object.fromEntries(Object.entries(anomalyCounts).sort(([a], [b]) =>
        a.localeCompare(b)
      )),
      examples: anomalyExamples
    }
  });
}

function stateBody(state) {
  const body = { ...state };
  delete body.stateHash;
  return body;
}

function reportBody(report) {
  const body = { ...report };
  delete body.reportHash;
  return body;
}

function criteriaResults({ summary, coverageRatio, chainIssues, config }) {
  const expected = config.criteria;
  const rows = [
    ["coverage", coverageRatio, ">=", expected.minCoverageRatio],
    ["forge-health", summary.forgeHealthyRatio, ">=", expected.minForgeHealthyRatio],
    [
      "gpu-workers-active",
      summary.gpuWorkerActiveRatio,
      ">=",
      expected.minGpuWorkerActiveRatio
    ],
    ["critical-errors", summary.criticalErrorCount, "<=", expected.maxCriticalErrors],
    ["tests-executed", summary.testsExecuted, ">=", expected.minTestsExecuted],
    ["test-pass-rate", summary.testPassRate, ">=", expected.minTestPassRate],
    [
      "implementations-completed",
      summary.implementationsCompleted,
      ">=",
      expected.minImplementationsCompleted
    ],
    [
      "implementation-success-rate",
      summary.implementationSuccessRate,
      ">=",
      expected.minImplementationSuccessRate
    ],
    [
      "canonical-mutations-without-owner",
      summary.canonicalMutations,
      "<=",
      expected.maxCanonicalMutations
    ],
    ["queue-stall-samples", summary.queueStallSamples, "<=", expected.maxQueueStallSamples],
    ["chain-issues", chainIssues, "<=", expected.maxChainIssues]
  ];
  return rows.map(([id, actual, operator, target]) => ({
    id,
    actual,
    operator,
    target,
    passed: operator === ">=" ? actual >= target : actual <= target
  }));
}

function markdownReport(report) {
  const lines = [
    "# AIONE — Analyse de robustesse continue sur 7 jours",
    "",
    `- Résultat : **${report.result}**`,
    `- Début : ${report.period.startedAt}`,
    `- Fin attendue : ${report.period.endedAt}`,
    `- Rapport généré : ${report.generatedAt}`,
    `- Échantillons : ${report.evidence.snapshotCount}/${report.coverage.expectedSamples}`,
    `- Couverture : ${(report.coverage.ratio * 100).toFixed(2)} %`,
    `- Chaîne de preuve : ${report.evidence.chainValid ? "valide" : "invalide"}`,
    `- Tête SHA-256 : \`${report.evidence.headHash}\``,
    "",
    "## Critères",
    "",
    "| Critère | Mesure | Attendu | État |",
    "|---|---:|---:|---|",
    ...report.criteria.map((criterion) =>
      `| ${criterion.id} | ${criterion.actual} | ${criterion.operator} ${criterion.target} | ${criterion.passed ? "OK" : "ÉCHEC"} |`
    ),
    "",
    "## Synthèse",
    "",
    `- Forge saine : ${(report.summary.forgeHealthyRatio * 100).toFixed(2)} %`,
    `- Workers GPU actifs : ${(report.summary.gpuWorkerActiveRatio * 100).toFixed(2)} %`,
    `- Propositions produites : ${report.summary.proposalsProduced}`,
    `- Artefacts produits : ${report.summary.artifactsProduced}`,
    `- Tests : ${report.summary.testsPassed} réussis, ${report.summary.testsFailed} échoués`,
    `- Implémentations : ${report.summary.implementationsSucceeded} réussies, ${report.summary.implementationsFailed} échouées`,
    `- Anomalies : ${report.anomalies.total}`,
    "",
    "## Anomalies par code",
    "",
    ...(Object.keys(report.anomalies.byCode).length
      ? Object.entries(report.anomalies.byCode).map(([code, count]) => `- ${code} : ${count}`)
      : ["- Aucune"]),
    "",
    "Les compteurs représentent les événements observés pendant chaque intervalle, pas des cumuls historiques.",
    ""
  ];
  return lines.join("\n");
}

export class WeekSoakAnalyzer {
  constructor({
    rootDir = DEFAULT_ROOT,
    clock = () => new Date(),
    config = {}
  } = {}) {
    if (typeof rootDir !== "string" || rootDir.length === 0) {
      fail("INVALID_ROOT", "rootDir doit être un chemin injecté valide.");
    }
    if (typeof clock !== "function") fail("INVALID_CLOCK", "clock doit être injectable.");
    this.rootDir = resolve(rootDir);
    this.clock = clock;
    this.config = normalizeConfig(config);
    this.paths = deepFreeze({
      root: ensureDirectory(this.rootDir),
      snapshots: ensureDirectory(join(this.rootDir, "snapshots")),
      locks: ensureDirectory(join(this.rootDir, "locks")),
      lockHistory: ensureDirectory(join(this.rootDir, "locks", "history")),
      activeLock: join(this.rootDir, "locks", "active.lock"),
      state: join(this.rootDir, "state.json"),
      reportJson: join(this.rootDir, "final-report.json"),
      reportMarkdown: join(this.rootDir, "final-report.md")
    });
  }

  acquireLock() {
    const now = nowIso(this.clock);
    if (existsSync(this.paths.activeLock)) {
      const previous = readJson(this.paths.activeLock, 16 * 1024);
      if (validateLock(previous)) {
        const age = Date.parse(now) - Date.parse(previous.acquiredAt);
        if (previous.status === "ACTIVE" && age >= 0 && age < this.config.lockLeaseMs) {
          return { ok: false, status: "ALREADY_RUNNING", lock: previous };
        }
      }
      const history = readdirSync(this.paths.lockHistory).filter((name) =>
        name.endsWith(".json")
      );
      if (history.length >= this.config.maxLockHistory) {
        fail("LOCK_HISTORY_QUOTA_EXCEEDED", "Le quota de preuves de verrou est atteint.");
      }
      const archive = validateLock(previous)
        ? lockHistoryName(previous)
        : `lock-invalid-${compactStamp(now)}-${randomUUID()}.json`;
      try {
        renameSync(this.paths.activeLock, join(this.paths.lockHistory, archive));
      } catch {
        return { ok: false, status: "ALREADY_RUNNING", lock: null };
      }
    }
    const lock = {
      schema: LOCK_SCHEMA,
      token: randomUUID(),
      status: "ACTIVE",
      acquiredAt: now,
      pid: process.pid
    };
    let descriptor;
    try {
      descriptor = openSync(this.paths.activeLock, "wx");
      writeFileSync(descriptor, `${JSON.stringify(lock)}\n`, "utf8");
      closeSync(descriptor);
    } catch (error) {
      if (descriptor !== undefined) {
        try {
          closeSync(descriptor);
        } catch {
          // Le descripteur est déjà fermé ou invalide.
        }
      }
      if (error?.code === "EEXIST") {
        return { ok: false, status: "ALREADY_RUNNING", lock: null };
      }
      throw error;
    }
    return { ok: true, lock };
  }

  releaseLock(acquired) {
    if (!acquired?.ok || !acquired.lock || !existsSync(this.paths.activeLock)) return;
    const current = readJson(this.paths.activeLock, 16 * 1024);
    if (!validateLock(current) || current.token !== acquired.lock.token) return;
    const released = {
      ...current,
      status: "RELEASED",
      releasedAt: nowIso(this.clock)
    };
    atomicJson(this.paths.activeLock, released, 16 * 1024);
    const target = join(this.paths.lockHistory, lockHistoryName(released));
    try {
      renameSync(this.paths.activeLock, target);
    } catch {
      // Le prochain cycle archivera ce verrou RELEASED sans détruire de preuve.
    }
  }

  listSnapshotFiles() {
    return readdirSync(this.paths.snapshots)
      .filter((name) => /^\d{6}-[A-Fa-f0-9]{16}\.json$/u.test(name))
      .sort()
      .map((name) => join(this.paths.snapshots, name));
  }

  auditChain() {
    const files = this.listSnapshotFiles();
    const records = [];
    const issues = [];
    let previousHash = GENESIS_HASH;
    let runId = null;
    let totalBytes = 0;
    const sampleIds = new Set();
    const observedTimes = new Set();
    let previousObservedAt = null;
    for (let index = 0; index < files.length; index += 1) {
      const target = files[index];
      const snapshotBytes = statSync(target).size;
      totalBytes += snapshotBytes;
      if (snapshotBytes > this.config.maxSampleBytes) {
        issues.push({
          sequence: index + 1,
          code: "SAMPLE_QUOTA_EXCEEDED",
          file: target
        });
        continue;
      }
      let record;
      try {
        record = JSON.parse(readFileSync(target, "utf8"));
        validateStoredSnapshot(record);
      } catch (error) {
        issues.push({
          sequence: index + 1,
          code: error instanceof WeekSoakError ? error.code : "INVALID_SNAPSHOT_JSON",
          file: target
        });
        continue;
      }
      if (record.sequence !== index + 1) {
        issues.push({ sequence: record.sequence, code: "SEQUENCE_MISMATCH", file: target });
      }
      if (runId === null) runId = record.runId;
      if (record.runId !== runId) {
        issues.push({ sequence: record.sequence, code: "RUN_ID_MISMATCH", file: target });
      }
      if (record.previousHash !== previousHash) {
        issues.push({ sequence: record.sequence, code: "CHAIN_LINK_MISMATCH", file: target });
      }
      const expectedHash = hashSoakValue(snapshotBody(record));
      if (record.hash !== expectedHash) {
        issues.push({ sequence: record.sequence, code: "SNAPSHOT_HASH_MISMATCH", file: target });
      }
      if (sampleIds.has(record.sampleId)) {
        issues.push({ sequence: record.sequence, code: "DUPLICATE_SAMPLE_ID", file: target });
      }
      if (observedTimes.has(record.observedAt)) {
        issues.push({ sequence: record.sequence, code: "DUPLICATE_OBSERVED_AT", file: target });
      }
      if (
        previousObservedAt !== null &&
        Date.parse(record.observedAt) <= Date.parse(previousObservedAt)
      ) {
        issues.push({ sequence: record.sequence, code: "OUT_OF_ORDER_OBSERVED_AT", file: target });
      }
      sampleIds.add(record.sampleId);
      observedTimes.add(record.observedAt);
      previousObservedAt = record.observedAt;
      records.push(record);
      previousHash = record.hash;
    }
    if (totalBytes > this.config.maxSnapshotBytes) {
      issues.push({ code: "SNAPSHOT_STORAGE_QUOTA_EXCEEDED" });
    }
    const persistedState = readJson(this.paths.state, this.config.maxStateBytes);
    const persistedStateValid = persistedState &&
      persistedState.schema === STATE_SCHEMA &&
      persistedState.stateHash === hashSoakValue(stateBody(persistedState));
    if (persistedStateValid) {
      if (persistedState.snapshotCount > records.length) {
        issues.push({ code: "SNAPSHOT_MISSING_FROM_CHAIN" });
      } else if (persistedState.snapshotCount > 0) {
        const persistedHead = records[persistedState.snapshotCount - 1]?.hash;
        if (persistedState.headHash !== persistedHead) {
          issues.push({ code: "PERSISTED_HEAD_MISMATCH" });
        }
      }
    }
    return deepFreeze({
      ok: issues.length === 0,
      issues,
      records,
      snapshotCount: records.length,
      headHash: records.length ? previousHash : GENESIS_HASH,
      runId,
      totalBytes
    });
  }

  deriveState(
    audit,
    now,
    existing = readJson(this.paths.state, this.config.maxStateBytes)
  ) {
    const records = audit.records;
    if (records.length === 0) return null;
    const startedAt = records[0].observedAt;
    const endAt = new Date(Date.parse(startedAt) + WEEK_MS).toISOString();
    const aggregates = aggregateRecords(records, this.config);
    const report = readJson(this.paths.reportJson, this.config.maxStateBytes);
    const validReport = report &&
      report.schema === REPORT_SCHEMA &&
      report.reportHash === hashSoakValue(reportBody(report));
    const status = validReport && report.runId === audit.runId
      ? `FINAL_${report.result}`
      : "RUNNING";
    const previousStateValid = existing &&
      existing.schema === STATE_SCHEMA &&
      existing.stateHash === hashSoakValue(stateBody(existing));
    const state = {
      schema: STATE_SCHEMA,
      runId: audit.runId,
      startedAt,
      endAt,
      durationMs: WEEK_MS,
      status,
      updatedAt: now,
      snapshotCount: audit.snapshotCount,
      snapshotBytes: audit.totalBytes,
      headHash: audit.headHash,
      hourly: aggregates.hourly,
      daily: aggregates.daily,
      totals: aggregates.totals,
      anomalies: aggregates.anomalies,
      recovery: {
        previousStatePresent: Boolean(existing),
        previousStateValid: Boolean(previousStateValid),
        rebuiltFromSnapshots: !previousStateValid ||
          existing.snapshotCount !== audit.snapshotCount ||
          existing.headHash !== audit.headHash
      },
      finalReportHash: validReport ? report.reportHash : null
    };
    state.stateHash = hashSoakValue(stateBody(state));
    const bytes = Buffer.byteLength(JSON.stringify(state), "utf8");
    if (bytes > this.config.maxStateBytes) {
      fail("STATE_QUOTA_EXCEEDED", "L'état agrégé dépasse son quota.");
    }
    return deepFreeze(state);
  }

  persistState(state) {
    atomicJson(this.paths.state, state, this.config.maxStateBytes);
  }

  createSnapshot(sample, audit, runId, capturedAt) {
    const body = {
      schema: SNAPSHOT_SCHEMA,
      runId,
      sequence: audit.snapshotCount + 1,
      sampleId: sample.sampleId,
      observedAt: sample.observedAt,
      capturedAt,
      previousHash: audit.headHash,
      sample
    };
    const record = deepFreeze({ ...body, hash: hashSoakValue(body) });
    const content = `${JSON.stringify(record, null, 2)}\n`;
    const bytes = Buffer.byteLength(content, "utf8");
    if (bytes > this.config.maxSampleBytes) {
      fail("SAMPLE_QUOTA_EXCEEDED", "L'échantillon dépasse son quota.");
    }
    if (audit.totalBytes + bytes > this.config.maxSnapshotBytes) {
      fail("SNAPSHOT_STORAGE_QUOTA_EXCEEDED", "Le stockage snapshot dépasse son quota.");
    }
    const projectedAggregates = aggregateRecords([...audit.records, record], this.config);
    const projectedStateBytes = Buffer.byteLength(JSON.stringify({
      hourly: projectedAggregates.hourly,
      daily: projectedAggregates.daily,
      totals: projectedAggregates.totals,
      anomalies: projectedAggregates.anomalies
    }), "utf8");
    if (projectedStateBytes > this.config.maxStateBytes) {
      fail("STATE_QUOTA_EXCEEDED", "L'échantillon ferait dépasser le quota d'état.");
    }
    const name = `${String(record.sequence).padStart(6, "0")}-${record.hash.slice(0, 16)}.json`;
    const target = join(this.paths.snapshots, name);
    atomicWrite(target, content, this.config.maxSampleBytes);
    return record;
  }

  finalize(state, audit, now) {
    const expectedSamples = Math.floor(WEEK_MS / this.config.sampleIntervalMs) + 1;
    const coverageRatio = rounded(Math.min(1, audit.snapshotCount / expectedSamples));
    const criteria = criteriaResults({
      summary: state.totals,
      coverageRatio,
      chainIssues: audit.issues.length,
      config: this.config
    });
    const result = criteria.every((criterion) => criterion.passed) ? "SUCCESS" : "FAILURE";
    const body = {
      schema: REPORT_SCHEMA,
      runId: state.runId,
      generatedAt: now,
      result,
      period: {
        startedAt: state.startedAt,
        endedAt: state.endAt,
        durationMs: WEEK_MS
      },
      coverage: {
        expectedSamples,
        actualSamples: audit.snapshotCount,
        ratio: coverageRatio,
        sampleIntervalMs: this.config.sampleIntervalMs
      },
      criteria,
      summary: state.totals,
      hourly: state.hourly,
      daily: state.daily,
      anomalies: state.anomalies,
      evidence: {
        chainValid: audit.ok,
        chainIssueCount: audit.issues.length,
        snapshotCount: audit.snapshotCount,
        snapshotBytes: audit.totalBytes,
        headHash: audit.headHash
      }
    };
    const report = deepFreeze({ ...body, reportHash: hashSoakValue(body) });
    atomicJson(this.paths.reportJson, report, this.config.maxStateBytes);
    atomicWrite(
      this.paths.reportMarkdown,
      markdownReport(report),
      this.config.maxStateBytes
    );
    const finalState = {
      ...state,
      status: `FINAL_${result}`,
      updatedAt: now,
      finalReportHash: report.reportHash
    };
    finalState.stateHash = hashSoakValue(stateBody(finalState));
    this.persistState(finalState);
    return deepFreeze({ report, state: finalState });
  }

  runCycle(options = {}) {
    allowedKeys(options, ["sample"], "INVALID_OPTIONS", "options");
    const acquired = this.acquireLock();
    if (!acquired.ok) return deepFreeze(acquired);
    try {
      const capturedAt = nowIso(this.clock);
      const persistedBeforeCycle = readJson(this.paths.state, this.config.maxStateBytes);
      let audit = this.auditChain();
      if (!audit.ok) {
        return deepFreeze({
          ok: false,
          status: "TAMPERED",
          audit
        });
      }
      let state = this.deriveState(audit, capturedAt, persistedBeforeCycle);
      const existingReport = readJson(this.paths.reportJson, this.config.maxStateBytes);
      if (
        state?.status?.startsWith("FINAL_") &&
        existingReport?.reportHash === state.finalReportHash
      ) {
        this.persistState(state);
        return deepFreeze({
          ok: true,
          status: "ALREADY_FINALIZED",
          state,
          report: existingReport
        });
      }

      let sample = null;
      if (options.sample !== undefined && options.sample !== null) {
        sample = normalizeWeekSoakSample(options.sample);
        const observedAtMs = parseInstant(sample.observedAt, "sample.observedAt");
        const capturedAtMs = parseInstant(capturedAt, "capturedAt");
        if (observedAtMs > capturedAtMs + 5_000) {
          fail("SAMPLE_FROM_FUTURE", "L'échantillon provient du futur.");
        }
        const duplicate = audit.records.find((record) =>
          record.sampleId === sample.sampleId || record.observedAt === sample.observedAt
        );
        if (duplicate) {
          if (state) this.persistState(state);
          return deepFreeze({
            ok: true,
            status: "DUPLICATE_SAMPLE",
            sampleId: duplicate.sampleId,
            sequence: duplicate.sequence,
            state
          });
        }
        if (audit.snapshotCount >= this.config.maxSamples) {
          fail("SAMPLE_COUNT_QUOTA_EXCEEDED", "Le quota d'échantillons est atteint.");
        }
        if (audit.records.length > 0) {
          const lastObservedAt = Date.parse(audit.records.at(-1).observedAt);
          if (observedAtMs <= lastObservedAt) {
            fail("OUT_OF_ORDER_SAMPLE", "L'échantillon est antérieur au dernier snapshot.");
          }
        }
        const startedAtMs = state
          ? Date.parse(state.startedAt)
          : observedAtMs;
        const endAtMs = startedAtMs + WEEK_MS;
        if (observedAtMs <= endAtMs) {
          const runId = state?.runId || `soak-${randomUUID()}`;
          this.createSnapshot(sample, audit, runId, capturedAt);
          audit = this.auditChain();
          if (!audit.ok) {
            return deepFreeze({ ok: false, status: "TAMPERED", audit });
          }
          state = this.deriveState(audit, capturedAt, persistedBeforeCycle);
          this.persistState(state);
        }
      }

      if (!state) {
        return deepFreeze({
          ok: true,
          status: "AWAITING_FIRST_SAMPLE",
          state: null
        });
      }
      if (Date.parse(capturedAt) >= Date.parse(state.endAt)) {
        const finalized = this.finalize(state, audit, capturedAt);
        return deepFreeze({
          ok: finalized.report.result === "SUCCESS",
          status: `FINAL_${finalized.report.result}`,
          ...finalized
        });
      }
      return deepFreeze({
        ok: true,
        status: sample ? "RECORDED" : "RUNNING",
        state
      });
    } finally {
      this.releaseLock(acquired);
    }
  }

  getStatus() {
    const audit = this.auditChain();
    const now = nowIso(this.clock);
    if (!audit.ok) return deepFreeze({ ok: false, status: "TAMPERED", audit });
    const state = this.deriveState(audit, now);
    if (!state) return deepFreeze({ ok: true, status: "NOT_STARTED", audit, state: null });
    return deepFreeze({ ok: true, status: state.status, audit, state });
  }

  readFinalReport() {
    const report = readJson(this.paths.reportJson, this.config.maxStateBytes);
    if (!report) return null;
    if (
      report.schema !== REPORT_SCHEMA ||
      report.reportHash !== hashSoakValue(reportBody(report))
    ) {
      fail("REPORT_TAMPERED", "Le rapport final a été altéré.");
    }
    return deepFreeze(report);
  }
}
