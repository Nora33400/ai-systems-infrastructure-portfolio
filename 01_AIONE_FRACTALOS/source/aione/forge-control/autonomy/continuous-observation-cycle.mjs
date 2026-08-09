import { createHash, randomUUID } from "node:crypto";
import { renameWithRetry } from "./atomic-file.mjs";
import {
  closeSync,
  existsSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  writeFileSync
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createDailyIntelligenceJournal } from "./daily-intelligence-journal.mjs";
import { PredictiveEvolution } from "./predictive-evolution.mjs";
import { createThermalContextStore } from "./thermal-context-tiles.mjs";
import {
  WEEK_SOAK,
  WeekSoakAnalyzer,
  hashSoakValue,
  normalizeWeekSoakSample,
  redactSoakSecrets
} from "./week-soak-analyzer.mjs";

const MODULE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CURSOR_SCHEMA = "aione.continuous-observation-cursor.v1";
const TRANSACTION_SCHEMA = "aione.continuous-observation-transaction.v1";
const LOCK_SCHEMA = "aione.continuous-observation-lock.v1";
const PREDICTIVE_WINDOW_SCHEMA = "aione.continuous-observation-predictive-window.v1";
const TILE_CYCLE_SCHEMA = "aione.continuous-observation-tile-cycle.v1";
const MAX_JSON_BYTES = 16 * 1024 * 1024;
const DEFAULT_RUNTIME_ROOT = "S:\\AI_LAB\\Runtime\\ContinuousObservation";
const DEFAULT_SOURCE_ROOT = "S:\\AI_LAB\\Runtime\\DualGpuDevelopment";
const COUNTER_KEYS = Object.freeze([
  "packages",
  "artifactFiles",
  "artifactBytes",
  "testsPassed",
  "testsFailed",
  "testsSkipped",
  "testDurationMs",
  "implementationsQueued",
  "implementationsSucceeded",
  "implementationsFailed",
  "canonicalMutations",
  "tasksCompleted",
  "failedCycles"
]);

export const CONTINUOUS_OBSERVATION = Object.freeze({
  cursorSchema: CURSOR_SCHEMA,
  transactionSchema: TRANSACTION_SCHEMA,
  defaultRuntimeRoot: DEFAULT_RUNTIME_ROOT,
  defaultSourceRoot: DEFAULT_SOURCE_ROOT,
  command: "node forge-control/autonomy/continuous-observation-cycle.mjs --once"
});

export class ContinuousObservationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ContinuousObservationError";
    this.code = code;
  }
}

function fail(code, message) {
  throw new ContinuousObservationError(code, message);
}

function plainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function allowedKeys(value, keys, label) {
  if (!plainObject(value)) fail("INVALID_OPTIONS", `${label} doit être un objet.`);
  if (Object.keys(value).some((key) => !keys.includes(key))) {
    fail("INVALID_OPTIONS", `${label} contient une propriété inconnue.`);
  }
}

function canonicalize(value) {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map((entry) =>
    entry === undefined ? null : canonicalize(entry)
  );
  if (plainObject(value)) {
    return Object.fromEntries(
      Object.keys(value)
        .filter((key) => value[key] !== undefined)
        .sort()
        .map((key) => [key, canonicalize(value[key])])
    );
  }
  fail("NON_CANONICAL_VALUE", "Une valeur du cycle n'est pas canonique.");
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function hash(value) {
  return createHash("sha256").update(stableJson(value), "utf8").digest("hex");
}

function nowIso(clock) {
  const candidate = clock();
  const date = candidate instanceof Date ? candidate : new Date(candidate);
  if (!Number.isFinite(date.getTime())) fail("INVALID_CLOCK", "Horloge invalide.");
  return date.toISOString();
}

function finite(value, fallback = 0, maximum = Number.MAX_SAFE_INTEGER) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0
    ? Math.min(number, maximum)
    : fallback;
}

function integer(value, fallback = 0, maximum = Number.MAX_SAFE_INTEGER) {
  return Math.floor(finite(value, fallback, maximum));
}

function clamp01(value) {
  return Math.max(0, Math.min(1, finite(value, 0, 1)));
}

function assertSPath(candidate, label) {
  if (typeof candidate !== "string" || !/^S:[\\/]/iu.test(candidate)) {
    fail("LOCAL_S_PATH_REQUIRED", `${label} doit rester sur S:.`);
  }
  return resolve(candidate);
}

function ensureLocalDirectory(candidate, label) {
  const target = assertSPath(candidate, label);
  mkdirSync(target, { recursive: true });
  if (lstatSync(target).isSymbolicLink()) {
    fail("SYMLINK_REFUSED", `${label} ne peut pas être un lien symbolique.`);
  }
  return target;
}

function assertReadableLocalPath(candidate, label) {
  const target = assertSPath(candidate, label);
  if (existsSync(target) && lstatSync(target).isSymbolicLink()) {
    fail("SYMLINK_REFUSED", `${label} ne peut pas être un lien symbolique.`);
  }
  return target;
}

function readBoundedJson(target, { fallback = null, maxBytes = MAX_JSON_BYTES } = {}) {
  if (!existsSync(target)) return fallback;
  const metadata = lstatSync(target);
  if (metadata.isSymbolicLink()) fail("SYMLINK_REFUSED", `Lien symbolique refusé: ${target}`);
  if (!metadata.isFile()) fail("INVALID_EVIDENCE", `La preuve n'est pas un fichier: ${target}`);
  if (metadata.size > maxBytes) fail("EVIDENCE_QUOTA_EXCEEDED", `Preuve trop grande: ${target}`);
  try {
    return JSON.parse(readFileSync(target, "utf8").replace(/^\uFEFF/u, ""));
  } catch {
    fail("INVALID_EVIDENCE_JSON", `Preuve JSON invalide: ${target}`);
  }
}

function atomicJson(target, value, maxBytes = 2 * 1024 * 1024) {
  const content = `${JSON.stringify(value, null, 2)}\n`;
  if (Buffer.byteLength(content, "utf8") > maxBytes) {
    fail("PERSISTENCE_QUOTA_EXCEEDED", "État du cycle trop volumineux.");
  }
  mkdirSync(dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
  writeFileSync(temporary, content, { encoding: "utf8", flag: "wx" });
  renameWithRetry(temporary, target);
}

function hashBody(value, hashKey) {
  const body = { ...value };
  delete body[hashKey];
  return hash(body);
}

function safeTimestamp(value) {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function fresh(value, now, maximumAgeMs) {
  const timestamp = safeTimestamp(value);
  if (timestamp === null) return false;
  const age = Date.parse(now) - timestamp;
  return age >= 0 && age <= maximumAgeMs;
}

function boundedTreeStats(root, { maximumEntries = 30_000 } = {}) {
  if (!existsSync(root)) return { files: 0, bytes: 0, latestMtimeMs: 0, entries: 0 };
  if (lstatSync(root).isSymbolicLink()) fail("SYMLINK_REFUSED", `Racine liée refusée: ${root}`);
  const pending = [root];
  let files = 0;
  let bytes = 0;
  let latestMtimeMs = 0;
  let entries = 0;
  while (pending.length > 0) {
    const directory = pending.pop();
    const children = readdirSync(directory, { withFileTypes: true });
    for (const child of children) {
      entries += 1;
      if (entries > maximumEntries) {
        fail("EVIDENCE_ENTRY_QUOTA_EXCEEDED", `Trop d'entrées sous ${root}.`);
      }
      const target = join(directory, child.name);
      if (child.isSymbolicLink()) continue;
      if (child.isDirectory()) {
        pending.push(target);
      } else if (child.isFile()) {
        const metadata = statSync(target);
        files += 1;
        bytes += metadata.size;
        latestMtimeMs = Math.max(latestMtimeMs, metadata.mtimeMs);
      }
    }
  }
  return { files, bytes, latestMtimeMs, entries };
}

function countJsonFiles(root, maximumEntries = 5_000) {
  if (!existsSync(root)) return 0;
  if (lstatSync(root).isSymbolicLink()) fail("SYMLINK_REFUSED", `Racine liée refusée: ${root}`);
  const entries = readdirSync(root, { withFileTypes: true });
  if (entries.length > maximumEntries) {
    fail("EVIDENCE_ENTRY_QUOTA_EXCEEDED", `Trop d'entrées sous ${root}.`);
  }
  return entries.filter((entry) => entry.isFile() && entry.name.endsWith(".json")).length;
}

function normalizePaths(candidate = {}) {
  allowedKeys(
    candidate,
    [
      "forgeState",
      "laneStates",
      "laneHeartbeats",
      "implementationState",
      "implementationQueue",
      "artifacts",
      "testTotals",
      "systemMetrics"
    ],
    "paths"
  );
  const sourceRoot = DEFAULT_SOURCE_ROOT;
  const laneIds = ["gpu-3060-development", "gpu-4060-quality"];
  const laneStates = candidate.laneStates || laneIds.map((laneId) =>
    join(sourceRoot, "lanes", laneId, "state.json")
  );
  const laneHeartbeats = candidate.laneHeartbeats || laneIds.map((laneId) =>
    join(sourceRoot, "lanes", laneId, "heartbeat.json")
  );
  if (
    !Array.isArray(laneStates) ||
    !Array.isArray(laneHeartbeats) ||
    laneStates.length !== 2 ||
    laneHeartbeats.length !== 2
  ) fail("TWO_GPU_EVIDENCE_REQUIRED", "Deux états et deux heartbeats GPU sont requis.");
  return Object.freeze({
    forgeState: assertReadableLocalPath(
      candidate.forgeState || "S:\\AI_LAB\\Runtime\\ForgeAutonomy\\state.json",
      "paths.forgeState"
    ),
    laneStates: laneStates.map((entry, index) =>
      assertReadableLocalPath(entry, `paths.laneStates[${index}]`)
    ),
    laneHeartbeats: laneHeartbeats.map((entry, index) =>
      assertReadableLocalPath(entry, `paths.laneHeartbeats[${index}]`)
    ),
    implementationState: assertReadableLocalPath(
      candidate.implementationState || join(sourceRoot, "isolated-implementation-state.json"),
      "paths.implementationState"
    ),
    implementationQueue: assertReadableLocalPath(
      candidate.implementationQueue || join(sourceRoot, "implementation-queue"),
      "paths.implementationQueue"
    ),
    artifacts: assertReadableLocalPath(
      candidate.artifacts || join(sourceRoot, "artifacts"),
      "paths.artifacts"
    ),
    testTotals: assertReadableLocalPath(
      candidate.testTotals || join(DEFAULT_RUNTIME_ROOT, "test-totals.json"),
      "paths.testTotals"
    ),
    systemMetrics: assertReadableLocalPath(
      candidate.systemMetrics || join(DEFAULT_RUNTIME_ROOT, "system-metrics.json"),
      "paths.systemMetrics"
    )
  });
}

function normalizeLoopback(candidate) {
  if (candidate === undefined || candidate === null || candidate.enabled === false) {
    return Object.freeze({ enabled: false });
  }
  allowedKeys(
    candidate,
    ["enabled", "url", "timeoutMs", "maxResponseBytes", "fetchImpl"],
    "loopback"
  );
  if (candidate.enabled !== true) fail("INVALID_LOOPBACK", "loopback.enabled est invalide.");
  let url;
  try {
    url = new URL(candidate.url);
  } catch {
    fail("INVALID_LOOPBACK", "URL loopback invalide.");
  }
  const host = url.hostname.toLowerCase();
  if (
    url.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(host) ||
    url.username ||
    url.password ||
    url.hash
  ) {
    fail("LOOPBACK_ONLY", "Seul HTTP loopback sans identifiants est autorisé.");
  }
  const timeoutMs = integer(candidate.timeoutMs, 2_000, 10_000);
  if (timeoutMs < 100) fail("INVALID_LOOPBACK", "Timeout loopback trop court.");
  const maxResponseBytes = integer(candidate.maxResponseBytes, 256 * 1024, 1024 * 1024);
  if (maxResponseBytes < 1_024) fail("INVALID_LOOPBACK", "Quota réponse loopback trop faible.");
  const fetchImpl = candidate.fetchImpl || globalThis.fetch;
  if (typeof fetchImpl !== "function") fail("FETCH_UNAVAILABLE", "Fetch loopback indisponible.");
  return Object.freeze({
    enabled: true,
    url: url.href,
    timeoutMs,
    maxResponseBytes,
    fetchImpl
  });
}

async function queryLoopback(config) {
  if (!config.enabled) return null;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.timeoutMs);
  const startedAt = performance.now();
  try {
    const response = await config.fetchImpl(config.url, {
      method: "GET",
      redirect: "error",
      credentials: "omit",
      cache: "no-store",
      signal: controller.signal,
      headers: { accept: "application/json" }
    });
    if (!response?.ok) {
      fail("LOOPBACK_UNHEALTHY", `La sonde loopback répond ${response?.status || "sans statut"}.`);
    }
    const declaredLength = Number(response.headers?.get?.("content-length") || 0);
    if (declaredLength > config.maxResponseBytes) {
      fail("LOOPBACK_RESPONSE_TOO_LARGE", "Réponse loopback trop grande.");
    }
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > config.maxResponseBytes) {
      fail("LOOPBACK_RESPONSE_TOO_LARGE", "Réponse loopback trop grande.");
    }
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      fail("LOOPBACK_INVALID_JSON", "Réponse loopback JSON invalide.");
    }
    return {
      body: redactSoakSecrets(body),
      responseTimeMs: Math.max(0, performance.now() - startedAt)
    };
  } finally {
    clearTimeout(timeout);
  }
}

function defaultCounters() {
  return Object.fromEntries(COUNTER_KEYS.map((key) => [key, 0]));
}

function deltas(current, previous) {
  const values = {};
  const resets = [];
  for (const key of COUNTER_KEYS) {
    const before = previous?.[key];
    if (before === undefined) {
      values[key] = 0;
    } else if (current[key] < before) {
      values[key] = 0;
      resets.push(key);
    } else {
      values[key] = current[key] - before;
    }
  }
  return { values, resets };
}

function validateStoredEnvelope(value, schema, hashKey) {
  if (!plainObject(value) || value.schema !== schema || value[hashKey] !== hashBody(value, hashKey)) {
    fail("PERSISTED_STATE_TAMPERED", `État persistant ${schema} invalide.`);
  }
  return value;
}

function activeIncidents(forgeState) {
  const incidents = plainObject(forgeState?.incidents)
    ? Object.values(forgeState.incidents)
    : [];
  return incidents
    .filter((incident) => incident?.status === "OPEN")
    .slice(0, 32)
    .map((incident) => ({
      code: String(incident.serviceId || "FORGE_INCIDENT")
        .replace(/[^A-Za-z0-9._:-]+/gu, "-")
        .slice(0, 120) || "FORGE_INCIDENT",
      severity: incident.critical ? "CRITICAL" : "ERROR",
      // WEEK_SOAK.count means signals observed in this sample, not the lifetime
      // occurrence counter of the incident. Reusing occurrences here made two
      // persistent incidents appear as hundreds of simultaneous errors.
      count: 1,
      message: `${String(incident.error || incident.label || "Incident local ouvert")
        .replaceAll("\0", "")
        .trim()
        .slice(0, 430) || "Incident local ouvert"} (occurrences cumulées: ${Math.max(1, integer(incident.occurrences, 1, 1_000_000))})`
        .slice(0, 500)
    }));
}

function queueSnapshot(forgeState, implementationQueueCount, deltaValues, observedAt) {
  const queue = Array.isArray(forgeState?.queue) ? forgeState.queue : [];
  const pendingItems = queue.filter((item) =>
    ["PENDING", "QUEUED", "READY", "AWAITING"].some((status) =>
      String(item?.status || "").toUpperCase().includes(status)
    )
  );
  const running = queue.filter((item) =>
    ["RUNNING", "EXECUTING"].includes(String(item?.status || "").toUpperCase())
  ).length;
  const now = Date.parse(observedAt);
  const ages = pendingItems.map((item) => {
    const timestamp = safeTimestamp(item.createdAt || item.queuedAt || item.updatedAt);
    return timestamp === null ? 0 : Math.max(0, Math.floor((now - timestamp) / 1000));
  });
  return {
    pending: pendingItems.length + implementationQueueCount,
    running,
    completed: deltaValues.tasksCompleted +
      deltaValues.implementationsSucceeded +
      deltaValues.implementationsFailed,
    failed: deltaValues.failedCycles + deltaValues.implementationsFailed,
    oldestPendingAgeSeconds: ages.length ? Math.max(...ages) : 0
  };
}

function engineDefaults(clock) {
  const production = JSON.parse(
    readFileSync(join(MODULE_ROOT, "config", "week-soak-production.json"), "utf8")
  );
  return Object.freeze({
    weekSoak: new WeekSoakAnalyzer({
      rootDir: production.runtimeRoot || "S:\\AI_LAB\\Runtime\\WeekSoak",
      clock,
      config: {
        sampleIntervalMs: Number(production.sampleIntervalMinutes || 5) * 60 * 1000,
        maxSamples: Number(production.maximumSamples || 2_304),
        criteria: {
          minCoverageRatio: Number(production.successGates?.minimumSampleCoverage ?? 0.95),
          minForgeHealthyRatio: Number(production.successGates?.minimumForgeAvailability ?? 0.99),
          maxCriticalErrors: Number(production.successGates?.maximumCriticalIncidentsOpenAtEnd ?? 0),
          maxCanonicalMutations: Number(production.successGates?.maximumCanonicalMutationsWithoutOwner ?? 0)
        }
      }
    }),
    predictiveEvolution: new PredictiveEvolution({
      configPath: join(MODULE_ROOT, "config", "bounded-adaptive-evolution.json"),
      runtimeRoot: "S:\\AI_LAB\\Runtime\\AdaptiveEvolution",
      clock
    }),
    thermalContext: createThermalContextStore({
      runtimeRoot: "S:\\AI_LAB\\Runtime\\FractalContext",
      now: clock
    }),
    dailyIntelligence: createDailyIntelligenceJournal({
      configPath: join(MODULE_ROOT, "config", "daily-intelligence-journal.json"),
      runtimeRoot: "S:\\AI_LAB\\Runtime\\DailyIntelligence",
      now: clock
    })
  });
}

function assertEngines(engines) {
  if (
    !engines ||
    typeof engines.weekSoak?.runCycle !== "function" ||
    typeof engines.predictiveEvolution?.observe !== "function" ||
    typeof engines.thermalContext?.ingest !== "function" ||
    typeof engines.dailyIntelligence?.ingest !== "function"
  ) fail("INVALID_ENGINES", "Les quatre moteurs d'observation sont requis.");
  return engines;
}

export class ContinuousObservationCycle {
  constructor({
    runtimeRoot = DEFAULT_RUNTIME_ROOT,
    paths = {},
    loopback,
    engines,
    clock = () => new Date(),
    maximumArtifactEntries = 30_000,
    maximumQueueEntries = 5_000,
    heartbeatFreshnessMs = 15 * 60 * 1000,
    forgeFreshnessMs = 30 * 60 * 1000
  } = {}) {
    if (typeof clock !== "function") fail("INVALID_CLOCK", "clock doit être injectable.");
    this.clock = clock;
    this.runtimeRoot = ensureLocalDirectory(runtimeRoot, "runtimeRoot");
    this.sourcePaths = normalizePaths(paths);
    this.loopback = normalizeLoopback(loopback);
    this.maximumArtifactEntries = integer(maximumArtifactEntries, 30_000, 100_000);
    this.maximumQueueEntries = integer(maximumQueueEntries, 5_000, 20_000);
    this.heartbeatFreshnessMs = integer(heartbeatFreshnessMs, 15 * 60 * 1000, 24 * 60 * 60 * 1000);
    this.forgeFreshnessMs = integer(forgeFreshnessMs, 30 * 60 * 1000, 24 * 60 * 60 * 1000);
    this.paths = Object.freeze({
      cursor: join(this.runtimeRoot, "cursor.json"),
      transaction: join(this.runtimeRoot, "inflight.json"),
      predictiveWindow: join(this.runtimeRoot, "predictive-window.json"),
      tileCycle: join(this.runtimeRoot, "tile-cycle.json"),
      lock: join(this.runtimeRoot, "cycle.lock"),
      lockHistory: ensureLocalDirectory(join(this.runtimeRoot, "lock-history"), "lockHistory")
    });
    this.engines = assertEngines(engines || engineDefaults(clock));
  }

  acquireLock() {
    const now = nowIso(this.clock);
    if (existsSync(this.paths.lock)) {
      const old = readBoundedJson(this.paths.lock, { fallback: null, maxBytes: 16 * 1024 });
      const acquiredAt = safeTimestamp(old?.acquiredAt);
      const age = acquiredAt === null ? Number.POSITIVE_INFINITY : Date.parse(now) - acquiredAt;
      if (old?.schema === LOCK_SCHEMA && old.status === "ACTIVE" && age < 10 * 60 * 1000) {
        return null;
      }
      const archive = join(
        this.paths.lockHistory,
        `lock-${String(old?.token || randomUUID()).replace(/[^A-Za-z0-9._-]/gu, "-")}.json`
      );
      try {
        renameSync(this.paths.lock, archive);
      } catch {
        return null;
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
      descriptor = openSync(this.paths.lock, "wx");
      writeFileSync(descriptor, `${JSON.stringify(lock)}\n`, "utf8");
      closeSync(descriptor);
    } catch (error) {
      if (descriptor !== undefined) {
        try {
          closeSync(descriptor);
        } catch {
          // Descripteur déjà fermé.
        }
      }
      if (error?.code === "EEXIST") return null;
      throw error;
    }
    return lock;
  }

  releaseLock(lock) {
    if (!lock || !existsSync(this.paths.lock)) return;
    const current = readBoundedJson(this.paths.lock, { fallback: null, maxBytes: 16 * 1024 });
    if (current?.token !== lock.token) return;
    const released = { ...current, status: "RELEASED", releasedAt: nowIso(this.clock) };
    atomicJson(this.paths.lock, released, 16 * 1024);
    try {
      renameSync(
        this.paths.lock,
        join(this.paths.lockHistory, `lock-${released.token}.json`)
      );
    } catch {
      // Le prochain cycle archivera la preuve du verrou.
    }
  }

  readCursor() {
    const cursor = readBoundedJson(this.paths.cursor, { fallback: null, maxBytes: 2 * 1024 * 1024 });
    return cursor ? validateStoredEnvelope(cursor, CURSOR_SCHEMA, "cursorHash") : null;
  }

  readTransaction() {
    const transaction = readBoundedJson(this.paths.transaction, {
      fallback: null,
      maxBytes: 2 * 1024 * 1024
    });
    return transaction
      ? validateStoredEnvelope(transaction, TRANSACTION_SCHEMA, "transactionHash")
      : null;
  }

  readPredictiveWindow() {
    const state = readBoundedJson(this.paths.predictiveWindow, {
      fallback: null,
      maxBytes: 256 * 1024
    });
    return state
      ? validateStoredEnvelope(state, PREDICTIVE_WINDOW_SCHEMA, "stateHash")
      : null;
  }

  writePredictiveWindow(value) {
    const body = {
      schema: PREDICTIVE_WINDOW_SCHEMA,
      ...value,
      updatedAt: nowIso(this.clock)
    };
    atomicJson(this.paths.predictiveWindow, { ...body, stateHash: hash(body) }, 256 * 1024);
  }

  readTileCycle() {
    const state = readBoundedJson(this.paths.tileCycle, {
      fallback: null,
      maxBytes: 128 * 1024
    });
    return state
      ? validateStoredEnvelope(state, TILE_CYCLE_SCHEMA, "stateHash")
      : null;
  }

  writeTileCycle(value) {
    const body = {
      schema: TILE_CYCLE_SCHEMA,
      ...value,
      updatedAt: nowIso(this.clock)
    };
    atomicJson(this.paths.tileCycle, { ...body, stateHash: hash(body) }, 128 * 1024);
  }

  async collectEvidence() {
    const observedAt = nowIso(this.clock);
    const forgeState = readBoundedJson(this.sourcePaths.forgeState, {
      fallback: null,
      maxBytes: MAX_JSON_BYTES
    });
    const laneStates = this.sourcePaths.laneStates.map((target) =>
      readBoundedJson(target, { fallback: null, maxBytes: 512 * 1024 })
    );
    const laneHeartbeats = this.sourcePaths.laneHeartbeats.map((target) =>
      readBoundedJson(target, { fallback: null, maxBytes: 512 * 1024 })
    );
    const implementationState = readBoundedJson(this.sourcePaths.implementationState, {
      fallback: null,
      maxBytes: 4 * 1024 * 1024
    });
    const testTotals = readBoundedJson(this.sourcePaths.testTotals, {
      fallback: null,
      maxBytes: 256 * 1024
    });
    const systemMetrics = readBoundedJson(this.sourcePaths.systemMetrics, {
      fallback: null,
      maxBytes: 256 * 1024
    });
    const artifacts = boundedTreeStats(this.sourcePaths.artifacts, {
      maximumEntries: this.maximumArtifactEntries
    });
    const implementationQueueCount = countJsonFiles(
      this.sourcePaths.implementationQueue,
      this.maximumQueueEntries
    );
    let loopback;
    try {
      loopback = await queryLoopback(this.loopback);
    } catch (error) {
      loopback = {
        body: {
          ok: false,
          status: "LOOPBACK_UNAVAILABLE"
        },
        responseTimeMs: 0,
        error: {
          code: String(error?.code || "LOOPBACK_PROBE_FAILED")
            .replace(/[^A-Za-z0-9._:-]+/gu, "-")
            .slice(0, 120),
          message: String(error?.message || "Sonde Forge loopback indisponible.")
            .replaceAll("\0", "")
            .trim()
            .slice(0, 500)
        }
      };
    }

    const currentCounters = {
      ...defaultCounters(),
      packages: laneStates.reduce((sum, state) => sum + integer(state?.totalPackages), 0),
      artifactFiles: artifacts.files,
      artifactBytes: artifacts.bytes,
      testsPassed: integer(testTotals?.passed),
      testsFailed: integer(testTotals?.failed),
      testsSkipped: integer(testTotals?.skipped),
      testDurationMs: integer(testTotals?.durationMs),
      implementationsQueued: Math.max(
        implementationQueueCount,
        integer(implementationState?.totals?.queued)
      ),
      implementationsSucceeded: integer(implementationState?.totals?.succeeded),
      implementationsFailed: integer(implementationState?.totals?.failed),
      canonicalMutations: integer(implementationState?.totals?.canonicalMutations),
      tasksCompleted: integer(forgeState?.metrics?.tasksCompleted),
      failedCycles: integer(forgeState?.metrics?.failedCycles)
    };
    const evidence = redactSoakSecrets({
      forgeState: forgeState
        ? {
            paused: Boolean(forgeState.paused),
            createdAt: forgeState.createdAt || null,
            updatedAt: forgeState.updatedAt || null,
            lastCycleStatus: forgeState.lastCycle?.status || null,
            queueSize: Array.isArray(forgeState.queue) ? forgeState.queue.length : 0,
            openIncidents: activeIncidents(forgeState),
            metrics: forgeState.metrics || {}
          }
        : null,
      lanes: laneStates.map((state, index) => ({
        laneId: state?.laneId || laneHeartbeats[index]?.laneId || `gpu-${index}`,
        state: state
          ? {
              totalPackages: state.totalPackages,
              consecutiveFailures: state.consecutiveFailures,
              cooling: state.cooling,
              startedAt: state.startedAt,
              lastPackageAt: state.lastPackageAt,
              lastThermalReading: state.lastThermalReading
            }
          : null,
        heartbeat: laneHeartbeats[index]
          ? {
              at: laneHeartbeats[index].at,
              status: laneHeartbeats[index].status,
              model: laneHeartbeats[index].model,
              totalPackages: laneHeartbeats[index].totalPackages
            }
          : null
      })),
      implementationState: implementationState
        ? { totals: implementationState.totals, updatedAt: implementationState.updatedAt }
        : null,
      testTotals,
      systemMetrics,
      artifacts,
      implementationQueueCount,
      loopback: loopback ? { body: loopback.body } : null,
      currentCounters
    });
    return { observedAt, evidence, currentCounters, raw: {
      forgeState,
      laneStates,
      laneHeartbeats,
      implementationState,
      testTotals,
      systemMetrics,
      artifacts,
      implementationQueueCount,
      loopback
    } };
  }

  buildSample(collected, cursor) {
    const delta = deltas(collected.currentCounters, cursor?.counters);
    if (!cursor && collected.raw.testTotals) {
      delta.values.testsPassed = integer(collected.raw.testTotals.lastRunPassed);
      delta.values.testsFailed = integer(collected.raw.testTotals.lastRunFailed);
      delta.values.testsSkipped = integer(collected.raw.testTotals.lastRunSkipped);
      delta.values.testDurationMs = integer(collected.raw.testTotals.lastRunDurationMs);
    }
    const errors = [];
    const pushError = (code, severity, message, count = 1) => {
      if (errors.length >= 128) return;
      errors.push({ code, severity, count: Math.max(1, count), message });
    };
    if (!collected.raw.forgeState) {
      pushError("FORGE_EVIDENCE_MISSING", "CRITICAL", "État local de la Forge absent.");
    }
    if (!collected.raw.testTotals) {
      pushError("TEST_EVIDENCE_MISSING", "INFO", "Aucun compteur de test local n'est disponible.");
    }
    if (collected.raw.loopback?.error) {
      pushError(
        collected.raw.loopback.error.code || "LOOPBACK_PROBE_FAILED",
        "CRITICAL",
        collected.raw.loopback.error.message || "Sonde Forge loopback indisponible."
      );
    }
    for (const key of delta.resets) {
      pushError("COUNTER_RESET", "WARNING", `Compteur monotone réinitialisé: ${key}.`);
    }
    for (const incident of activeIncidents(collected.raw.forgeState)) errors.push(incident);

    const forgeFresh = fresh(
      collected.raw.forgeState?.updatedAt,
      collected.observedAt,
      this.forgeFreshnessMs
    );
    const localHealthy = Boolean(
      collected.raw.forgeState &&
      !collected.raw.forgeState.paused &&
      collected.raw.forgeState.lastCycle?.status === "OK" &&
      forgeFresh
    );
    const loopbackBody = collected.raw.loopback?.body;
    const loopbackHealthy = loopbackBody
      ? Boolean(loopbackBody.ok ?? ["READY", "OK", "HEALTHY"].includes(
          String(loopbackBody.status || "").toUpperCase()
        ))
      : true;
    const forgeHealthy = localHealthy && loopbackHealthy;
    const forgeCreatedAt = safeTimestamp(collected.raw.forgeState?.createdAt);
    const uptimeSeconds = forgeCreatedAt === null
      ? 0
      : Math.max(0, Math.floor((Date.parse(collected.observedAt) - forgeCreatedAt) / 1000));

    const gpus = collected.raw.laneStates.map((state, index) => {
      const heartbeat = collected.raw.laneHeartbeats[index];
      const thermal = state?.lastThermalReading || {};
      const workerActive = Boolean(
        heartbeat &&
        fresh(heartbeat.at, collected.observedAt, this.heartbeatFreshnessMs) &&
        !["FAILED", "STOPPED", "CRASHED"].includes(String(heartbeat.status || "").toUpperCase())
      );
      if (!state || !heartbeat) {
        pushError(
          `GPU_${index + 1}_EVIDENCE_MISSING`,
          "ERROR",
          `Preuve locale incomplète pour le GPU ${index + 1}.`
        );
      } else if (!workerActive) {
        pushError(
          `GPU_${index + 1}_HEARTBEAT_STALE`,
          "ERROR",
          `Heartbeat GPU ${index + 1} absent ou périmé.`
        );
      }
      if (integer(state?.consecutiveFailures) > 0) {
        pushError(
          `GPU_${index + 1}_WORKER_FAILURE`,
          "ERROR",
          `Le worker GPU ${index + 1} signale des échecs consécutifs.`,
          integer(state.consecutiveFailures)
        );
      }
      const normalizedId = String(state?.laneId || heartbeat?.laneId || `gpu-${index + 1}`)
        .replace(/[^A-Za-z0-9._:-]+/gu, "-")
        .slice(0, 160);
      const memoryTotalMb = Math.max(1, integer(thermal.memoryTotalMb, 1, 1_048_576));
      return {
        id: normalizedId || `gpu-${index + 1}`,
        model: String(heartbeat?.model || `GPU ${index + 1}`).slice(0, 160),
        workerActive,
        utilizationPercent: finite(thermal.utilizationPercent, 0, 100),
        temperatureC: finite(thermal.temperatureCelsius, 0, 150),
        memoryUsedMb: Math.min(
          memoryTotalMb,
          integer(thermal.memoryUsedMb, 0, 1_048_576)
        ),
        memoryTotalMb,
        queueDepth: 0
      };
    });
    const queue = queueSnapshot(
      collected.raw.forgeState,
      collected.raw.implementationQueueCount,
      delta.values,
      collected.observedAt
    );
    const evidenceHash = hash(collected.evidence);
    const transaction = this.readTransaction();
    const reuse = transaction?.status === "INFLIGHT" &&
      transaction.evidenceHash === evidenceHash;
    const sampleId = reuse
      ? transaction.sample.sampleId
      : `observation-${evidenceHash.slice(0, 24)}`;
    const sampleObservedAt = reuse ? transaction.sample.observedAt : collected.observedAt;
    const sample = normalizeWeekSoakSample({
      schema: WEEK_SOAK.sampleSchema,
      sampleId,
      observedAt: sampleObservedAt,
      forge: {
        healthy: forgeHealthy,
        status: String(
          loopbackBody?.status ||
          collected.raw.forgeState?.lastCycle?.status ||
          "LOCAL_EVIDENCE_MISSING"
        ).slice(0, 120),
        uptimeSeconds,
        responseTimeMs: finite(collected.raw.loopback?.responseTimeMs, 0, 60_000)
      },
      gpus,
      queues: queue,
      errors,
      throughput: {
        proposalsProduced: delta.values.packages,
        artifactsProduced: delta.values.artifactFiles,
        bytesProduced: delta.values.artifactBytes
      },
      tests: {
        passed: delta.values.testsPassed,
        failed: delta.values.testsFailed,
        skipped: delta.values.testsSkipped,
        durationMs: delta.values.testDurationMs
      },
      implementations: {
        queued: delta.values.implementationsQueued,
        succeeded: delta.values.implementationsSucceeded,
        failed: delta.values.implementationsFailed,
        canonicalMutations: delta.values.canonicalMutations
      }
    });
    return { sample, evidenceHash, counters: collected.currentCounters, delta };
  }

  writeInflight(built) {
    const body = {
      schema: TRANSACTION_SCHEMA,
      status: "INFLIGHT",
      evidenceHash: built.evidenceHash,
      sample: built.sample,
      counters: built.counters,
      createdAt: nowIso(this.clock)
    };
    const transaction = { ...body, transactionHash: hash(body) };
    atomicJson(this.paths.transaction, transaction);
    return transaction;
  }

  updatePredictiveWindow(transaction, predictiveObservation) {
    const engine = this.engines.predictiveEvolution;
    if (typeof engine.status !== "function" || typeof engine.plan !== "function") {
      return { plan: null, window: null };
    }
    const status = engine.status();
    const windowSize = Math.max(1, integer(
      engine.config?.predictiveBottleneck?.observationWindowSamples,
      24,
      10_000
    ));
    const minimumEvidence = Math.max(1, integer(
      engine.config?.predictiveBottleneck?.minimumEvidenceSamples,
      6,
      windowSize
    ));
    const previous = this.readPredictiveWindow();
    const currentIdentity = {
      sampleId: transaction.sample.sampleId,
      evidenceHash: transaction.evidenceHash
    };
    const samples = [
      ...((previous?.samples || []).filter((entry) => entry.sampleId !== currentIdentity.sampleId)),
      currentIdentity
    ].slice(-windowSize);
    const windowKey = hash(samples);
    let lastPlannedWindowKey = previous?.lastPlannedWindowKey || null;
    let planAttempt = previous?.planAttempt || null;
    const effectiveObservationCount = Math.min(Number(status.observations || 0), windowSize);

    // Reprise après crash : si le plan courant est postérieur au début de la
    // tentative pour cette fenêtre, l'appel a déjà abouti. On ne le rejoue pas.
    if (planAttempt?.windowKey === windowKey && status.plan?.generatedAt) {
      const generatedAt = Date.parse(status.plan.generatedAt);
      const startedAt = Date.parse(planAttempt.startedAt);
      if (
        Number.isFinite(generatedAt) &&
        Number.isFinite(startedAt) &&
        generatedAt >= startedAt &&
        Number(status.plan.observationCount) === effectiveObservationCount
      ) {
        lastPlannedWindowKey = windowKey;
        planAttempt = null;
      }
    }

    const eligible = Number(status.observations || 0) >= minimumEvidence;
    const shouldPlan = eligible && lastPlannedWindowKey !== windowKey;
    let plan = null;
    if (shouldPlan) {
      planAttempt = { windowKey, startedAt: nowIso(this.clock) };
      this.writePredictiveWindow({
        windowSize,
        minimumEvidence,
        samples,
        windowKey,
        lastPlannedWindowKey,
        planAttempt
      });
      plan = engine.plan();
      lastPlannedWindowKey = windowKey;
      planAttempt = null;
    }
    this.writePredictiveWindow({
      windowSize,
      minimumEvidence,
      samples,
      windowKey,
      lastPlannedWindowKey,
      planAttempt
    });
    return {
      plan,
      window: {
        key: windowKey,
        trackedSamples: samples.length,
        complete: samples.length === windowSize,
        planned: shouldPlan,
        observationStatus: predictiveObservation.status
      }
    };
  }

  runBoundedTileCycle(transaction, baseTile) {
    const engine = this.engines.thermalContext;
    const sample = transaction.sample;
    const previous = this.readTileCycle();
    const hourlyBucket = `${sample.observedAt.slice(0, 13)}:00:00.000Z`;
    const dailyBucket = sample.observedAt.slice(0, 10);
    let hourly = null;
    let daily = null;
    let lastHourlyBucket = previous?.lastHourlyBucket || null;
    let lastHourlyTileId = previous?.lastHourlyTileId || null;
    let lastDailyBucket = previous?.lastDailyBucket || null;
    let lastDailyTileId = previous?.lastDailyTileId || null;

    if (!lastHourlyBucket || hourlyBucket > lastHourlyBucket) {
      hourly = engine.ingest({
        category: "forge-observation-cycle",
        title: `Jalon horaire borné ${hourlyBucket}`,
        subjectiveMachine: [
          `Jalon de cadence ${hourlyBucket}.`,
          `Dernière observation locale: Forge ${sample.forge.healthy ? "saine" : "dégradée"},`,
          `${sample.gpus.filter((gpu) => gpu.workerActive).length}/2 GPU actifs et ${sample.queues.pending} élément(s) en attente.`,
          "Ce jalon référence une observation; il ne prétend pas synthétiser toute l'heure."
        ].join(" "),
        objectiveUser: "Fournir un point de reprise horaire traçable sans relire ni réécrire toutes les tuiles de la période.",
        level: "unitile",
        family: "unitile",
        importance: sample.forge.healthy ? 0.55 : 0.9,
        confidence: 0.95,
        provenance: {
          sourceId: `continuous-observation-hour:${hourlyBucket}`,
          sourceType: "BOUNDED_HOURLY_CHECKPOINT",
          capturedAt: sample.observedAt,
          sourceHash: transaction.evidenceHash,
          locator: this.paths.transaction,
          agentId: "aione-continuous-observer"
        },
        anchors: baseTile?.id ? [{ tileId: baseTile.id, relation: "checkpoint-of", weight: 1 }] : []
      });
      lastHourlyBucket = hourlyBucket;
      lastHourlyTileId = hourly.tile?.id || null;
      this.writeTileCycle({
        lastHourlyBucket,
        lastHourlyTileId,
        lastDailyBucket,
        lastDailyTileId
      });
    }

    if (!lastDailyBucket || dailyBucket > lastDailyBucket) {
      daily = engine.ingest({
        category: "forge-observation-cycle",
        title: `Jalon journalier borné ${dailyBucket}`,
        subjectiveMachine: [
          `Jalon de cadence du ${dailyBucket}.`,
          "Il ancre le premier point de reprise observé ce jour et ne prétend pas être un agrégat exhaustif des 24 heures."
        ].join(" "),
        objectiveUser: "Fournir un point de reprise journalier traçable, local et à croissance bornée.",
        level: "kilotile",
        family: "utile",
        importance: sample.forge.healthy ? 0.6 : 0.95,
        confidence: 0.95,
        provenance: {
          sourceId: `continuous-observation-day:${dailyBucket}`,
          sourceType: "BOUNDED_DAILY_CHECKPOINT",
          capturedAt: sample.observedAt,
          sourceHash: transaction.evidenceHash,
          locator: this.paths.transaction,
          agentId: "aione-continuous-observer"
        },
        anchors: lastHourlyTileId ? [{ tileId: lastHourlyTileId, relation: "checkpoint-of", weight: 1 }] : []
      });
      lastDailyBucket = dailyBucket;
      lastDailyTileId = daily.tile?.id || null;
      this.writeTileCycle({
        lastHourlyBucket,
        lastHourlyTileId,
        lastDailyBucket,
        lastDailyTileId
      });
    }

    return {
      mode: "BOUNDED_CHECKPOINTS_ONLY",
      hourly: hourly ? { bucket: hourlyBucket, tileId: hourly.tile?.id || null, duplicate: hourly.duplicate } : null,
      daily: daily ? { bucket: dailyBucket, tileId: daily.tile?.id || null, duplicate: daily.duplicate } : null,
      refreshPerformed: false,
      compactionPerformed: false,
      limitation: "Le magasin actuel révise chaque tuile lors d'un refresh global et ne sait pas agréger un intervalle sans le relire; ces opérations restent désactivées pour éviter une croissance non bornée."
    };
  }

  feedEngines(transaction, collected) {
    const { sample } = transaction;
    const weekSoak = this.engines.weekSoak.runCycle({ sample });
    const testTotal = sample.tests.passed + sample.tests.failed;
    const implementationTotal =
      sample.implementations.succeeded + sample.implementations.failed;
    const maxTemperature = Math.max(...sample.gpus.map((gpu) => gpu.temperatureC));
    const predictiveObservation = this.engines.predictiveEvolution.observe({
      sampleId: sample.sampleId,
      metrics: {
        queueArrivalRate: sample.implementations.queued,
        queueServiceRate: implementationTotal,
        queueAgeMinutes: sample.queues.oldestPendingAgeSeconds / 60,
        gpuThermalHeadroom: clamp01((90 - maxTemperature) / 40),
        ramHeadroom: clamp01(collected.raw.systemMetrics?.ramHeadroom ?? 0.5),
        diskHeadroom: clamp01(collected.raw.systemMetrics?.diskHeadroom ?? 0.5),
        contextLatencyMs: finite(
          collected.raw.systemMetrics?.contextLatencyMs,
          sample.forge.responseTimeMs,
          60_000
        ),
        testFailureRate: testTotal ? sample.tests.failed / testTotal : 0,
        implementationRejectionRate: implementationTotal
          ? sample.implementations.failed / implementationTotal
          : 0,
        ownerReviewWaitMinutes: finite(
          collected.raw.systemMetrics?.ownerReviewWaitMinutes,
          0,
          365 * 24 * 60
        )
      },
      evidence: {
        weekSoakSampleId: sample.sampleId,
        evidenceHash: transaction.evidenceHash,
        localOnly: true
      }
    });
    const predictiveWindow = this.updatePredictiveWindow(transaction, predictiveObservation);
    const predictivePlan = predictiveWindow.plan;
    const anomalyCount = sample.errors.reduce((sum, error) => sum + error.count, 0);
    const subjectiveMachine = [
      `Observation ${sample.sampleId}: Forge ${sample.forge.healthy ? "saine" : "dégradée"}.`,
      `GPU actifs ${sample.gpus.filter((gpu) => gpu.workerActive).length}/2.`,
      `File ${sample.queues.pending} en attente, ${sample.queues.running} en cours.`,
      `Deltas: ${sample.throughput.proposalsProduced} propositions, ${sample.tests.failed} tests échoués,`,
      `${sample.implementations.succeeded} implémentations réussies et ${anomalyCount} signaux d'erreur.`
    ].join(" ");
    const objectiveUser = [
      "Donner à l'utilisateur une preuve locale, bornée et temporelle de la continuité réelle de la Forge,",
      "sans mutation canonique ni action externe."
    ].join(" ");
    const thermalContext = this.engines.thermalContext.ingest({
      category: "forge-observation",
      title: `Observation continue ${sample.sampleId}`,
      subjectiveMachine,
      objectiveUser,
      level: "tile",
      family: "utile",
      importance: sample.forge.healthy ? 0.6 : 0.95,
      confidence: 0.95,
      reconstructionCompressed: `${subjectiveMachine} ${objectiveUser}`,
      provenance: {
        sourceId: sample.sampleId,
        sourceType: "WEEK_SOAK_LOCAL_OBSERVATION",
        capturedAt: sample.observedAt,
        sourceHash: transaction.evidenceHash,
        locator: this.paths.transaction,
        agentId: "aione-continuous-observer"
      },
      anchors: [{
        fractalKey: "aione:continuous-observation",
        relation: "measures",
        weight: 1
      }]
    });
    const tileCycle = this.runBoundedTileCycle(transaction, thermalContext.tile);
    const observationHour = sample.observedAt.slice(0, 13);
    const dailyIntelligence = this.engines.dailyIntelligence.ingest({
      sourceClass: "LOCAL_FACT",
      // The 5-minute soak remains exhaustive, while the human journal keeps one
      // idempotent state per UTC hour instead of flooding the Owner review.
      idempotencyKey: `continuous-observation-hour:${observationHour}`,
      title: `État horaire local de la Forge — ${observationHour}:00Z`,
      summary: subjectiveMachine,
      details: objectiveUser,
      topics: ["IA locale gratuite", "sécurité et robustesse", "orchestration autonome"],
      projectIds: ["aione-autonomous-forge"],
      preferenceTags: ["sécurité et robustesse", "apprentissage de la Forge"],
      provenance: {
        sourcePathOrEndpoint: "S:\\AI_LAB\\Runtime\\WeekSoak",
        observedAt: sample.observedAt,
        contentHash: hashSoakValue(sample)
      },
      rankSignals: {
        projectImpact: 0.9,
        evidenceQuality: 1,
        urgency: sample.forge.healthy ? 0.4 : 1,
        novelty: 0.5,
        actionability: 0.8
      }
    });
    const dailyReviews = typeof this.engines.dailyIntelligence.generateDailyReviews === "function"
      ? this.engines.dailyIntelligence.generateDailyReviews({
          at: new Date(sample.observedAt)
        })
      : null;
    return redactSoakSecrets({
      weekSoak,
      predictiveEvolution: {
        ...predictiveObservation,
        observation: predictiveObservation,
        plan: predictivePlan,
        window: predictiveWindow.window
      },
      thermalContext: {
        ok: thermalContext.ok,
        idempotent: thermalContext.idempotent,
        duplicate: thermalContext.duplicate,
        tileId: thermalContext.tile?.id,
        cycle: tileCycle
      },
      dailyIntelligence: {
        ok: dailyIntelligence.ok,
        idempotent: dailyIntelligence.idempotent,
        duplicate: dailyIntelligence.duplicate,
        itemId: dailyIntelligence.item?.id,
        reviewsGenerated: Boolean(dailyReviews),
        reviewDate: dailyReviews?.date || sample.observedAt.slice(0, 10)
      }
    });
  }

  async runOnce() {
    const lock = this.acquireLock();
    if (!lock) return { ok: false, status: "ALREADY_RUNNING" };
    try {
      const cursor = this.readCursor();
      const collected = await this.collectEvidence();
      const currentEvidenceHash = hash(collected.evidence);
      if (cursor?.evidenceHash === currentEvidenceHash) {
        return {
          ok: true,
          status: "NO_NEW_EVIDENCE",
          sampleId: cursor.sampleId,
          cursorHash: cursor.cursorHash
        };
      }
      const built = this.buildSample(collected, cursor);
      const transaction = this.writeInflight(built);
      const engines = this.feedEngines(transaction, collected);
      const cursorBody = {
        schema: CURSOR_SCHEMA,
        evidenceHash: transaction.evidenceHash,
        sampleId: transaction.sample.sampleId,
        observedAt: transaction.sample.observedAt,
        counters: transaction.counters,
        committedAt: nowIso(this.clock),
        engineEvidence: {
          weekSoakStatus: engines.weekSoak?.status || null,
          predictiveStatus: engines.predictiveEvolution?.status || null,
          thermalTileId: engines.thermalContext.tileId || null,
          intelligenceItemId: engines.dailyIntelligence.itemId || null
        }
      };
      const nextCursor = { ...cursorBody, cursorHash: hash(cursorBody) };
      atomicJson(this.paths.cursor, nextCursor);
      const committedTransactionBody = {
        ...transaction,
        status: "COMMITTED",
        committedAt: nextCursor.committedAt
      };
      delete committedTransactionBody.transactionHash;
      const committedTransaction = {
        ...committedTransactionBody,
        transactionHash: hash(committedTransactionBody)
      };
      atomicJson(this.paths.transaction, committedTransaction);
      return redactSoakSecrets({
        ok: true,
        status: "RECORDED",
        sample: transaction.sample,
        delta: built.delta,
        cursorHash: nextCursor.cursorHash,
        engines
      });
    } finally {
      this.releaseLock(lock);
    }
  }
}

export function createContinuousObservationCycle(options = {}) {
  return new ContinuousObservationCycle(options);
}

export async function runContinuousObservationOnce(options = {}) {
  return createContinuousObservationCycle(options).runOnce();
}

export async function continuousObservationMain(
  argv = process.argv.slice(2),
  options = {}
) {
  if (!Array.isArray(argv) || argv.length !== 1 || argv[0] !== "--once") {
    fail("CLI_USAGE", `Usage: ${CONTINUOUS_OBSERVATION.command}`);
  }
  const loopbackUrl = process.env.AIONE_OBSERVATION_LOOPBACK_URL;
  const result = await runContinuousObservationOnce({
    ...options,
    loopback: options.loopback || (loopbackUrl
      ? { enabled: true, url: loopbackUrl }
      : undefined)
  });
  return result;
}

const entryUrl = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : null;
if (entryUrl === import.meta.url) {
  continuousObservationMain()
    .then((result) => {
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      process.exitCode = result.ok ? 0 : 2;
    })
    .catch((error) => {
      process.stderr.write(`${JSON.stringify({
        ok: false,
        error: error?.code || "OBSERVATION_FAILED",
        message: error?.message || String(error)
      })}\n`);
      process.exitCode = 1;
    });
}
