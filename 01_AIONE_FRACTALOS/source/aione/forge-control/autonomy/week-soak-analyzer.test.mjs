import test from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync
} from "node:fs";
import { join } from "node:path";
import { testRuntimeRoot } from "./test-paths.mjs";
import {
  WEEK_SOAK,
  WeekSoakAnalyzer,
  WeekSoakError
} from "./week-soak-analyzer.mjs";

function fixture(config = {}) {
  const rootDir = mkdtempSync(join(testRuntimeRoot(), "aione-week-soak-"));
  const time = { current: new Date("2026-08-03T00:00:00.000Z") };
  const clock = () => new Date(time.current);
  const analyzer = new WeekSoakAnalyzer({
    rootDir,
    clock,
    config: {
      sampleIntervalMs: 6 * 60 * 60 * 1000,
      maxSamples: 64,
      ...config
    }
  });
  return {
    rootDir,
    time,
    clock,
    analyzer,
    cleanup: () => rmSync(rootDir, { recursive: true, force: true })
  };
}

function sample(at, index, overrides = {}) {
  const base = {
    schema: WEEK_SOAK.sampleSchema,
    sampleId: `sample-${String(index).padStart(3, "0")}`,
    observedAt: at.toISOString(),
    forge: {
      healthy: true,
      status: "READY",
      uptimeSeconds: index * 21_600,
      responseTimeMs: 12
    },
    gpus: [
      {
        id: "gpu-3060",
        model: "RTX 3060",
        workerActive: true,
        utilizationPercent: 78,
        temperatureC: 70,
        memoryUsedMb: 8_000,
        memoryTotalMb: 12_288,
        queueDepth: 4
      },
      {
        id: "gpu-4060",
        model: "RTX 4060",
        workerActive: true,
        utilizationPercent: 82,
        temperatureC: 72,
        memoryUsedMb: 6_000,
        memoryTotalMb: 8_192,
        queueDepth: 5
      }
    ],
    queues: {
      pending: 9,
      running: 2,
      completed: index * 4,
      failed: 0,
      oldestPendingAgeSeconds: 120
    },
    errors: [],
    throughput: {
      proposalsProduced: 4,
      artifactsProduced: 8,
      bytesProduced: 16_384
    },
    tests: {
      passed: 10,
      failed: 0,
      skipped: 0,
      durationMs: 2_000
    },
    implementations: {
      queued: 2,
      succeeded: 2,
      failed: 0,
      canonicalMutations: 0
    }
  };
  return {
    ...base,
    ...overrides
  };
}

function expectCode(code, callback) {
  assert.throws(callback, (error) => {
    assert.ok(error instanceof WeekSoakError);
    assert.equal(error.code, code);
    return true;
  });
}

test("a scheduler can advance a complete healthy seven-day soak without sleeping", () => {
  const fx = fixture();
  try {
    let result;
    for (let index = 0; index <= 28; index += 1) {
      fx.time.current = new Date(Date.parse("2026-08-03T00:00:00.000Z") + index * 6 * 60 * 60 * 1000);
      result = fx.analyzer.runCycle({ sample: sample(fx.time.current, index) });
    }
    assert.equal(result.status, "FINAL_SUCCESS");
    assert.equal(result.report.coverage.expectedSamples, 29);
    assert.equal(result.report.coverage.actualSamples, 29);
    assert.equal(result.report.coverage.ratio, 1);
    assert.equal(result.report.evidence.chainValid, true);
    assert.equal(result.report.hourly.length, 29);
    assert.equal(result.report.daily.length, 8);
    assert.equal(result.report.summary.proposalsProduced, 116);
    assert.equal(fx.analyzer.readFinalReport().reportHash, result.report.reportHash);
    assert.match(readFileSync(fx.analyzer.paths.reportMarkdown, "utf8"), /Résultat : \*\*SUCCESS\*\*/u);
  } finally {
    fx.cleanup();
  }
});

test("state is rebuilt from hash-chained snapshots after a crash or stale state", () => {
  const fx = fixture();
  try {
    fx.analyzer.runCycle({ sample: sample(fx.time.current, 0) });
    fx.time.current = new Date(fx.time.current.getTime() + 6 * 60 * 60 * 1000);
    fx.analyzer.runCycle({ sample: sample(fx.time.current, 1) });

    const stale = JSON.parse(readFileSync(fx.analyzer.paths.state, "utf8"));
    stale.snapshotCount = 0;
    writeFileSync(fx.analyzer.paths.state, `${JSON.stringify(stale)}\n`, "utf8");

    const resumed = new WeekSoakAnalyzer({
      rootDir: fx.rootDir,
      clock: fx.clock,
      config: { sampleIntervalMs: 6 * 60 * 60 * 1000, maxSamples: 64 }
    });
    fx.time.current = new Date(fx.time.current.getTime() + 6 * 60 * 60 * 1000);
    const result = resumed.runCycle({ sample: sample(fx.time.current, 2) });
    assert.equal(result.status, "RECORDED");
    assert.equal(result.state.snapshotCount, 3);
    assert.equal(result.state.recovery.previousStateValid, false);
    assert.equal(result.state.recovery.rebuiltFromSnapshots, true);
    assert.equal(resumed.auditChain().ok, true);
  } finally {
    fx.cleanup();
  }
});

test("snapshot falsification stops the run and is reported with evidence", () => {
  const fx = fixture();
  try {
    fx.analyzer.runCycle({ sample: sample(fx.time.current, 0) });
    const target = join(
      fx.analyzer.paths.snapshots,
      readdirSync(fx.analyzer.paths.snapshots)[0]
    );
    const record = JSON.parse(readFileSync(target, "utf8"));
    record.sample.forge.status = "TAMPERED";
    writeFileSync(target, `${JSON.stringify(record, null, 2)}\n`, "utf8");

    fx.time.current = new Date(fx.time.current.getTime() + 6 * 60 * 60 * 1000);
    const result = fx.analyzer.runCycle({ sample: sample(fx.time.current, 1) });
    assert.equal(result.ok, false);
    assert.equal(result.status, "TAMPERED");
    assert.ok(result.audit.issues.some((issue) => issue.code === "SNAPSHOT_HASH_MISMATCH"));
    assert.equal(readdirSync(fx.analyzer.paths.snapshots).length, 1);
  } finally {
    fx.cleanup();
  }
});

test("duplicate samples are idempotent and do not extend the chain", () => {
  const fx = fixture();
  try {
    const first = sample(fx.time.current, 0);
    fx.analyzer.runCycle({ sample: first });
    const duplicate = fx.analyzer.runCycle({ sample: first });
    assert.equal(duplicate.status, "DUPLICATE_SAMPLE");
    assert.equal(duplicate.sequence, 1);
    assert.equal(fx.analyzer.auditChain().snapshotCount, 1);
  } finally {
    fx.cleanup();
  }
});

test("final failure report exposes anomalies and failed criteria", () => {
  const fx = fixture();
  try {
    let result;
    for (let index = 0; index <= 28; index += 1) {
      fx.time.current = new Date(Date.parse("2026-08-03T00:00:00.000Z") + index * 6 * 60 * 60 * 1000);
      const unhealthy = index === 5
        ? sample(fx.time.current, index, {
            forge: {
              healthy: false,
              status: "ERROR secret=should-not-leak",
              uptimeSeconds: 0,
              responseTimeMs: 5_000
            },
            errors: [{
              code: "FORGE_FAILURE",
              severity: "CRITICAL",
              count: 1,
              message: "Bearer abcdefghijklmnopqrstuvwxyz"
            }],
            tests: { passed: 0, failed: 2, skipped: 0, durationMs: 5_000 },
            implementations: {
              queued: 2,
              succeeded: 0,
              failed: 2,
              canonicalMutations: 0
            }
          })
        : sample(fx.time.current, index);
      result = fx.analyzer.runCycle({ sample: unhealthy });
    }
    assert.equal(result.status, "FINAL_FAILURE");
    assert.equal(result.report.result, "FAILURE");
    assert.ok(result.report.criteria.some((criterion) =>
      criterion.id === "critical-errors" && !criterion.passed
    ));
    assert.equal(result.report.anomalies.byCode.FORGE_UNHEALTHY, 1);
    const persisted = readFileSync(fx.analyzer.paths.reportJson, "utf8");
    assert.equal(persisted.includes("should-not-leak"), false);
    assert.equal(persisted.includes("abcdefghijklmnopqrstuvwxyz"), false);
    assert.match(persisted, /\[REDACTED\]/u);
  } finally {
    fx.cleanup();
  }
});

test("strict sample schema, two GPUs, quotas and lock exclusion are enforced", () => {
  const fx = fixture();
  try {
    expectCode("INVALID_SAMPLE", () =>
      fx.analyzer.runCycle({ sample: { ...sample(fx.time.current, 0), password: "no" } })
    );
    expectCode("INVALID_GPU_SAMPLE", () =>
      fx.analyzer.runCycle({
        sample: { ...sample(fx.time.current, 0), gpus: sample(fx.time.current, 0).gpus.slice(0, 1) }
      })
    );
    const activeLock = {
      schema: "aione.week-soak-lock.v1",
      token: "concurrent-lock",
      status: "ACTIVE",
      acquiredAt: fx.clock().toISOString(),
      pid: 999
    };
    writeFileSync(fx.analyzer.paths.activeLock, `${JSON.stringify(activeLock)}\n`, "utf8");
    const blocked = fx.analyzer.runCycle({ sample: sample(fx.time.current, 0) });
    assert.equal(blocked.status, "ALREADY_RUNNING");
  } finally {
    fx.cleanup();
  }
});
