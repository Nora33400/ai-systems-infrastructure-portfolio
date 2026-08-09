import test from "node:test";
import assert from "node:assert/strict";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync
} from "node:fs";
import { dirname, join } from "node:path";
import {
  CONTINUOUS_OBSERVATION,
  ContinuousObservationCycle,
  ContinuousObservationError,
  continuousObservationMain
} from "./continuous-observation-cycle.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function writeJson(target, value) {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function makeIdempotentEngines({
  failDailyOnce = false,
  predictiveWindowSize = null,
  predictiveMinimumEvidence = 2
} = {}) {
  const calls = {
    week: [],
    predictive: [],
    predictivePlans: [],
    thermal: [],
    daily: []
  };
  const seen = {
    week: new Set(),
    predictive: new Set(),
    thermal: new Map(),
    daily: new Map()
  };
  let shouldFailDaily = failDailyOnce;
  let currentPredictivePlan = null;
  const predictiveEvolution = {
    observe(input) {
      calls.predictive.push(input);
      const duplicate = seen.predictive.has(input.sampleId);
      seen.predictive.add(input.sampleId);
      return { status: duplicate ? "DUPLICATE" : "RECORDED" };
    }
  };
  if (predictiveWindowSize) {
    predictiveEvolution.config = {
      predictiveBottleneck: {
        observationWindowSamples: predictiveWindowSize,
        minimumEvidenceSamples: predictiveMinimumEvidence
      }
    };
    predictiveEvolution.status = () => ({
      observations: seen.predictive.size,
      plan: currentPredictivePlan
    });
    predictiveEvolution.plan = () => {
      currentPredictivePlan = {
        generatedAt: new Date(`2030-01-01T00:00:${String(calls.predictivePlans.length).padStart(2, "0")}.000Z`).toISOString(),
        observationCount: Math.min(seen.predictive.size, predictiveWindowSize)
      };
      const result = { status: "PLANNED", plan: currentPredictivePlan };
      calls.predictivePlans.push(result);
      return result;
    };
  }
  return {
    calls,
    engines: {
      weekSoak: {
        runCycle({ sample }) {
          calls.week.push(sample);
          const duplicate = seen.week.has(sample.sampleId);
          seen.week.add(sample.sampleId);
          return { ok: true, status: duplicate ? "DUPLICATE_SAMPLE" : "RECORDED" };
        }
      },
      predictiveEvolution,
      thermalContext: {
        ingest(input) {
          calls.thermal.push(input);
          const key = input.provenance.sourceId;
          const duplicate = seen.thermal.has(key);
          if (!duplicate) seen.thermal.set(key, `tile-${seen.thermal.size + 1}`);
          return {
            ok: true,
            idempotent: duplicate,
            duplicate,
            tile: { id: seen.thermal.get(key) }
          };
        }
      },
      dailyIntelligence: {
        ingest(input) {
          calls.daily.push(input);
          if (shouldFailDaily) {
            shouldFailDaily = false;
            throw Object.assign(new Error("crash simulé"), { code: "SIMULATED_CRASH" });
          }
          const key = input.idempotencyKey;
          const duplicate = seen.daily.has(key);
          if (!duplicate) seen.daily.set(key, `item-${seen.daily.size + 1}`);
          return {
            ok: true,
            idempotent: duplicate,
            duplicate,
            item: { id: seen.daily.get(key) }
          };
        }
      }
    }
  };
}

function fixture(options = {}) {
  const root = mkdtempSync(join(testRuntimeRoot(), "continuous-observation-"));
  const source = join(root, "source");
  const runtimeRoot = join(root, "runtime");
  const artifacts = join(source, "artifacts");
  const implementationQueue = join(source, "implementation-queue");
  mkdirSync(artifacts, { recursive: true });
  mkdirSync(implementationQueue, { recursive: true });
  const time = { current: new Date("2026-08-03T00:00:00.000Z") };
  const engineFixture = options.engineFixture || makeIdempotentEngines();
  const paths = {
    forgeState: join(source, "forge-state.json"),
    laneStates: [
      join(source, "gpu-3060-state.json"),
      join(source, "gpu-4060-state.json")
    ],
    laneHeartbeats: [
      join(source, "gpu-3060-heartbeat.json"),
      join(source, "gpu-4060-heartbeat.json")
    ],
    implementationState: join(source, "implementation-state.json"),
    implementationQueue,
    artifacts,
    testTotals: join(source, "test-totals.json"),
    systemMetrics: join(source, "system-metrics.json")
  };

  function seed({
    packages3060 = 10,
    packages4060 = 20,
    tasksCompleted = 5,
    failedCycles = 0,
    implementationsSucceeded = 2,
    implementationsFailed = 0,
    testsPassed = 10,
    testsFailed = 0
  } = {}) {
    const at = time.current.toISOString();
    writeJson(paths.forgeState, {
      paused: false,
      createdAt: "2026-08-02T00:00:00.000Z",
      updatedAt: at,
      lastCycle: { status: "OK" },
      queue: [],
      incidents: {},
      metrics: { tasksCompleted, failedCycles }
    });
    [
      ["gpu-3060-development", packages3060, 70, 6_000, 12_288],
      ["gpu-4060-quality", packages4060, 72, 5_000, 8_192]
    ].forEach(([laneId, totalPackages, temperatureCelsius, memoryUsedMb, memoryTotalMb], index) => {
      writeJson(paths.laneStates[index], {
        laneId,
        totalPackages,
        consecutiveFailures: 0,
        cooling: false,
        startedAt: "2026-08-02T00:00:00.000Z",
        lastPackageAt: at,
        lastThermalReading: {
          temperatureCelsius,
          utilizationPercent: 80,
          memoryUsedMb,
          memoryTotalMb
        }
      });
      writeJson(paths.laneHeartbeats[index], {
        laneId,
        at,
        status: "GENERATING",
        model: index === 0 ? "qwen2.5-coder:14b" : "qwen2.5-coder:7b"
      });
    });
    writeJson(paths.implementationState, {
      totals: {
        queued: implementationsSucceeded + implementationsFailed,
        succeeded: implementationsSucceeded,
        failed: implementationsFailed,
        canonicalMutations: 0
      },
      updatedAt: at
    });
    writeJson(paths.testTotals, {
      passed: testsPassed,
      failed: testsFailed,
      skipped: 0,
      durationMs: testsPassed * 100,
      updatedAt: at
    });
    writeJson(paths.systemMetrics, {
      ramHeadroom: 0.7,
      diskHeadroom: 0.8,
      contextLatencyMs: 30,
      ownerReviewWaitMinutes: 5
    });
  }
  seed();
  const cycle = new ContinuousObservationCycle({
    runtimeRoot,
    paths,
    engines: engineFixture.engines,
    clock: () => new Date(time.current),
    loopback: options.loopback
  });
  return {
    root,
    source,
    runtimeRoot,
    paths,
    time,
    seed,
    cycle,
    engineFixture,
    cleanup: () => rmSync(root, { recursive: true, force: true })
  };
}

test("local evidence becomes one strict WEEK_SOAK baseline then bounded deltas", async () => {
  const fx = fixture();
  try {
    const first = await fx.cycle.runOnce();
    assert.equal(first.status, "RECORDED");
    assert.equal(first.sample.schema, "aione.week-soak-sample.v1");
    assert.equal(first.sample.gpus.length, 2);
    assert.equal(first.sample.throughput.proposalsProduced, 0);
    assert.equal(first.sample.tests.passed, 0);

    fx.time.current = new Date(fx.time.current.getTime() + 5 * 60 * 1000);
    fx.seed({
      packages3060: 12,
      packages4060: 23,
      tasksCompleted: 7,
      implementationsSucceeded: 4,
      testsPassed: 14
    });
    writeFileSync(join(fx.paths.artifacts, "new.md"), "preuve\n", "utf8");
    writeJson(join(fx.paths.implementationQueue, "queued.json"), { id: "queued" });
    const second = await fx.cycle.runOnce();
    assert.equal(second.status, "RECORDED");
    assert.equal(second.sample.throughput.proposalsProduced, 5);
    assert.equal(second.sample.throughput.artifactsProduced, 1);
    assert.equal(second.sample.tests.passed, 4);
    assert.equal(second.sample.implementations.succeeded, 2);
    assert.equal(second.sample.queues.completed, 4);
    assert.equal(fx.engineFixture.calls.week.length, 2);
    assert.equal(fx.engineFixture.calls.predictive[1].metrics.queueServiceRate, 2);
    assert.equal(
      fx.engineFixture.calls.thermal.filter((entry) =>
        entry.provenance.sourceType === "WEEK_SOAK_LOCAL_OBSERVATION"
      ).length,
      2
    );
    assert.equal(fx.engineFixture.calls.daily.length, 2);
    const cursor = JSON.parse(readFileSync(fx.cycle.paths.cursor, "utf8"));
    assert.equal(cursor.sampleId, second.sample.sampleId);
  } finally {
    fx.cleanup();
  }
});

test("unchanged evidence is idempotent and does not feed engines twice", async () => {
  const fx = fixture();
  try {
    const first = await fx.cycle.runOnce();
    const second = await fx.cycle.runOnce();
    assert.equal(first.status, "RECORDED");
    assert.equal(second.status, "NO_NEW_EVIDENCE");
    assert.equal(fx.engineFixture.calls.week.length, 1);
    assert.equal(fx.engineFixture.calls.daily.length, 1);
  } finally {
    fx.cleanup();
  }
});

test("predictive planning follows the deterministic sliding window instead of its stable count", async () => {
  const engineFixture = makeIdempotentEngines({
    predictiveWindowSize: 3,
    predictiveMinimumEvidence: 2
  });
  const fx = fixture({ engineFixture });
  try {
    await fx.cycle.runOnce();
    for (let index = 1; index <= 3; index += 1) {
      fx.time.current = new Date(fx.time.current.getTime() + 5 * 60 * 1000);
      fx.seed({
        packages3060: 10 + index,
        packages4060: 20 + index,
        tasksCompleted: 5 + index
      });
      await fx.cycle.runOnce();
    }

    assert.equal(engineFixture.calls.predictivePlans.length, 3);
    assert.deepEqual(
      engineFixture.calls.predictivePlans.map((entry) => entry.plan.observationCount),
      [2, 3, 3]
    );
    const window = JSON.parse(readFileSync(fx.cycle.paths.predictiveWindow, "utf8"));
    assert.equal(window.samples.length, 3);
    assert.equal(new Set(window.samples.map((entry) => entry.sampleId)).size, 3);
    assert.equal(window.lastPlannedWindowKey, window.windowKey);
    assert.equal(window.stateHash.length, 64);

    const unchanged = await fx.cycle.runOnce();
    assert.equal(unchanged.status, "NO_NEW_EVIDENCE");
    assert.equal(engineFixture.calls.predictivePlans.length, 3);
  } finally {
    fx.cleanup();
  }
});

test("tile cadence creates at most one honest hourly and daily checkpoint per bucket", async () => {
  const fx = fixture();
  try {
    const first = await fx.cycle.runOnce();
    assert.equal(first.engines.thermalContext.cycle.mode, "BOUNDED_CHECKPOINTS_ONLY");
    assert.equal(first.engines.thermalContext.cycle.refreshPerformed, false);
    assert.equal(first.engines.thermalContext.cycle.compactionPerformed, false);

    fx.time.current = new Date("2026-08-03T00:05:00.000Z");
    fx.seed({ packages3060: 11 });
    await fx.cycle.runOnce();

    fx.time.current = new Date("2026-08-03T01:00:00.000Z");
    fx.seed({ packages3060: 12 });
    await fx.cycle.runOnce();

    fx.time.current = new Date("2026-08-04T00:00:00.000Z");
    fx.seed({ packages3060: 13 });
    await fx.cycle.runOnce();

    // Une horloge locale qui recule ne doit pas rouvrir un ancien bucket.
    fx.time.current = new Date("2026-08-03T00:30:00.000Z");
    fx.seed({ packages3060: 14 });
    await fx.cycle.runOnce();

    const byType = (sourceType) => fx.engineFixture.calls.thermal.filter((entry) =>
      entry.provenance.sourceType === sourceType
    );
    assert.equal(byType("WEEK_SOAK_LOCAL_OBSERVATION").length, 5);
    assert.equal(byType("BOUNDED_HOURLY_CHECKPOINT").length, 3);
    assert.equal(byType("BOUNDED_DAILY_CHECKPOINT").length, 2);
    assert.ok(byType("BOUNDED_HOURLY_CHECKPOINT").every((entry) => entry.level === "unitile"));
    assert.ok(byType("BOUNDED_DAILY_CHECKPOINT").every((entry) => entry.level === "kilotile"));
    assert.ok(byType("BOUNDED_HOURLY_CHECKPOINT").every((entry) =>
      entry.subjectiveMachine.includes("ne prétend pas synthétiser toute l'heure")
    ));
    const tileCycle = JSON.parse(readFileSync(fx.cycle.paths.tileCycle, "utf8"));
    assert.equal(tileCycle.lastHourlyBucket, "2026-08-04T00:00:00.000Z");
    assert.equal(tileCycle.lastDailyBucket, "2026-08-04");
  } finally {
    fx.cleanup();
  }
});

test("persistent incidents count as current signals rather than cumulative failures", async () => {
  const fx = fixture();
  try {
    const state = JSON.parse(readFileSync(fx.paths.forgeState, "utf8"));
    state.incidents = {
      docker: {
        serviceId: "docker",
        status: "OPEN",
        critical: false,
        occurrences: 235,
        error: "daemon indisponible"
      },
      openwebui: {
        serviceId: "openwebui",
        status: "OPEN",
        critical: false,
        occurrences: 41,
        error: "fetch failed"
      }
    };
    writeJson(fx.paths.forgeState, state);
    const result = await fx.cycle.runOnce();
    assert.equal(result.sample.errors.length, 2);
    assert.equal(result.sample.errors.reduce((sum, item) => sum + item.count, 0), 2);
    assert.match(result.sample.errors[0].message, /occurrences cumulées/u);
  } finally {
    fx.cleanup();
  }
});

test("a crash between engines resumes the same transaction without duplicate effects", async () => {
  const engineFixture = makeIdempotentEngines({
    failDailyOnce: true,
    predictiveWindowSize: 3,
    predictiveMinimumEvidence: 1
  });
  const fx = fixture({ engineFixture });
  try {
    await assert.rejects(() => fx.cycle.runOnce(), /crash simulé/u);
    assert.equal(exists(fx.cycle.paths.cursor), false);
    const retried = await fx.cycle.runOnce();
    assert.equal(retried.status, "RECORDED");
    assert.equal(engineFixture.calls.week.length, 2);
    assert.equal(engineFixture.calls.week[0].sampleId, engineFixture.calls.week[1].sampleId);
    assert.equal(retried.engines.weekSoak.status, "DUPLICATE_SAMPLE");
    assert.equal(retried.engines.predictiveEvolution.status, "DUPLICATE");
    assert.equal(retried.engines.thermalContext.duplicate, true);
    assert.equal(engineFixture.calls.predictivePlans.length, 1);
    assert.equal(engineFixture.calls.thermal.filter((entry) =>
      entry.provenance.sourceType === "BOUNDED_HOURLY_CHECKPOINT"
    ).length, 1);
    assert.equal(engineFixture.calls.thermal.filter((entry) =>
      entry.provenance.sourceType === "BOUNDED_DAILY_CHECKPOINT"
    ).length, 1);
  } finally {
    fx.cleanup();
  }
});

test("configured HTTP is strictly loopback and response data stays bounded", async () => {
  let request;
  const loopback = {
    enabled: true,
    url: "http://127.0.0.1:4173/api/status",
    fetchImpl: async (url, options) => {
      request = { url, options };
      return {
        ok: true,
        status: 200,
        headers: { get: () => null },
        text: async () => JSON.stringify({ ok: true, status: "READY", token: "secret-value" })
      };
    }
  };
  const fx = fixture({ loopback });
  try {
    const result = await fx.cycle.runOnce();
    assert.equal(result.sample.forge.status, "READY");
    assert.equal(request.url, loopback.url);
    assert.equal(request.options.redirect, "error");
    assert.equal(JSON.stringify(result).includes("secret-value"), false);
    assert.throws(
      () => new ContinuousObservationCycle({
        runtimeRoot: join(fx.root, "external-denied"),
        paths: fx.paths,
        engines: fx.engineFixture.engines,
        clock: () => new Date(fx.time.current),
        loopback: {
          enabled: true,
          url: "https://example.com/status",
          fetchImpl: async () => null
        }
      }),
      (error) => error instanceof ContinuousObservationError && error.code === "LOOPBACK_ONLY"
    );
  } finally {
    fx.cleanup();
  }
});

test("loopback outage is recorded as a critical sample instead of stopping observation", async () => {
  const fx = fixture({
    loopback: {
      enabled: true,
      url: "http://127.0.0.1:4310/api/health",
      fetchImpl: async () => ({
        ok: false,
        status: 503,
        headers: { get: () => null },
        text: async () => JSON.stringify({ ok: false })
      })
    }
  });
  try {
    const result = await fx.cycle.runOnce();
    assert.equal(result.status, "RECORDED");
    assert.equal(result.sample.forge.healthy, false);
    assert.ok(result.sample.errors.some((error) =>
      error.severity === "CRITICAL" && error.code === "LOOPBACK_UNHEALTHY"
    ));
  } finally {
    fx.cleanup();
  }
});

test("CLI contract accepts only --once and exposes the exact scheduler command", async () => {
  const fx = fixture();
  try {
    const result = await continuousObservationMain(["--once"], {
      runtimeRoot: fx.runtimeRoot,
      paths: fx.paths,
      engines: fx.engineFixture.engines,
      clock: () => new Date(fx.time.current)
    });
    assert.equal(result.status, "RECORDED");
    assert.equal(
      CONTINUOUS_OBSERVATION.command,
      "node forge-control/autonomy/continuous-observation-cycle.mjs --once"
    );
    await assert.rejects(
      () => continuousObservationMain(["--watch"], {
        runtimeRoot: fx.runtimeRoot,
        paths: fx.paths,
        engines: fx.engineFixture.engines
      }),
      (error) => error instanceof ContinuousObservationError && error.code === "CLI_USAGE"
    );
  } finally {
    fx.cleanup();
  }
});

function exists(target) {
  try {
    return Boolean(readFileSync(target));
  } catch {
    return false;
  }
}
