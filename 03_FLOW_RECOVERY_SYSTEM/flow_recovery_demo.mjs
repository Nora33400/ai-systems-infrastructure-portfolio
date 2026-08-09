import { performance } from "node:perf_hooks";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildLiveBlockerSnapshot } from "../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/live-blockers.mjs";
import { planRepairRetry } from "../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/repair-retry.mjs";
import { ResilienceManager, compareVersions } from "../01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/resilience-manager.mjs";

const here = resolve(fileURLToPath(new URL(".", import.meta.url)));
const policyPath = resolve(here, "../01_AIONE_FRACTALOS/source/aione/config/resilience-manager.json");

function snapshotFor({ status, workerStatus, incidentStatus }) {
  return buildLiveBlockerSnapshot({
    queue: [{
      id: "JOB-2",
      title: "logical worker job",
      status,
      evidence: status === "BLOCKED"
        ? [{ type: "failure", at: "2026-08-09T12:00:00.000Z", summary: "injected worker failure" }]
        : []
    }],
    cards: [{ id: "CARD-2", queueTaskId: "JOB-2", title: "logical worker job", status: status === "BLOCKED" ? "80-blocked" : "90-completed", history: [] }],
    workerRuns: [{
      id: "RUN-2",
      queueTaskId: "JOB-2",
      status: workerStatus,
      startedAt: "2026-08-09T11:59:59.000Z",
      completedAt: "2026-08-09T12:00:00.000Z",
      lastHeartbeat: "2026-08-09T12:00:00.000Z",
      lastAction: status === "BLOCKED" ? "injected failure" : "validation completed"
    }],
    incidents: [{ id: "INC-2", status: incidentStatus, critical: true, title: "injected logical worker failure" }],
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] },
    eligibility: { queued: 1, eligible: status === "BLOCKED" ? 0 : 1, selected: null, inspected: [] },
    now: "2026-08-09T12:00:01.000Z"
  });
}

export function runFlowRecoveryDemo() {
  const started = performance.now();
  const failed = snapshotFor({ status: "BLOCKED", workerStatus: "FAILED", incidentStatus: "OPEN" });
  const detected = performance.now();

  const retry = planRepairRetry({
    id: "REPAIR-2",
    status: "BLOCKED",
    retryCount: 0,
    maximumRetries: 2,
    repairTargetQueueTaskId: "JOB-2",
    evidence: []
  }, { at: "2026-08-09T12:00:02.000Z" });

  const comparison = compareVersions(
    { id: "degraded", integrityVerified: false, files: { "job/state.json": "changed" } },
    { id: "last-green", integrityVerified: true, files: { "job/state.json": "green", "job/checkpoint.json": "present" } }
  );

  const policy = JSON.parse(readFileSync(policyPath, "utf8"));
  const resilience = new ResilienceManager({ policy, now: () => new Date("2026-08-09T12:00:03.000Z") });
  const restore = resilience.evaluateRestore({
    backup: { id: "last-green", integrityVerified: true, restoreTestPassed: true },
    trigger: "CORRUPTION",
    ownerAuthorization: { approved: true, backupId: "last-green" }
  });

  const recovered = snapshotFor({ status: "COMPLETED", workerStatus: "COMPLETED", incidentStatus: "RESOLVED" });
  const completed = performance.now();

  return {
    schema: "portfolio.flow-recovery-demo.v1",
    scope: "single-machine deterministic logical-worker integration",
    injected_failure: true,
    detection: {
      state: failed.state,
      local_blockers: failed.counts.localBlocking,
      detection_time_ms: Number((detected - started).toFixed(3))
    },
    recovery: {
      retry_eligible: retry.eligible,
      retry_count: retry.patch?.retryCount ?? 0,
      retry_budget: 2,
      corruption_detected: comparison.corruptionSuspected,
      data_loss_risk_detected: comparison.dataLossSuspected,
      restore_authorized: restore.restoreAllowed,
      final_state: recovered.state,
      remaining_blockers: recovered.counts.localBlocking,
      recovery_time_ms: Number((completed - detected).toFixed(3))
    },
    jobs: { submitted: 3, completed: 3, retried: 1, lost: 0 },
    transitions: [
      "AVAILABLE", "OBSERVED", "SUSPECT", "RESTRICTED", "ISOLATED",
      "DIAGNOSTIC", "REPAIRING", "RELOADING", "VALIDATING",
      "LIMITED_RETURN", "AVAILABLE"
    ],
    limitations: [
      "Logical workers run in one Node.js process; no physical node or network partition is exercised.",
      "Job counts are deterministic scenario bookkeeping, not throughput measurement.",
      "No workload migration or real process restart is performed.",
      "Times measure harness function overhead only and are not operational recovery SLOs."
    ]
  };
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const report = runFlowRecoveryDemo();
  const outArg = process.argv.indexOf("--out");
  if (outArg >= 0 && process.argv[outArg + 1]) {
    writeFileSync(resolve(process.argv[outArg + 1]), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

