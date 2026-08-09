import assert from "node:assert/strict";
import test from "node:test";

import { PIPELINE_STAGES, buildLiveBlockerSnapshot } from "./live-blockers.mjs";

test("live blockers separates repairable local failures from deferred external dependencies", () => {
  const snapshot = buildLiveBlockerSnapshot({
    queue: [{
      id: "QUEUE-1",
      title: "Réparer le worker",
      status: "BLOCKED",
      evidence: [{ type: "failure", at: "2026-07-31T10:05:00.000Z", summary: "worker exit 1" }]
    }],
    cards: [{
      id: "CARD-1",
      queueTaskId: "QUEUE-1",
      title: "Réparer le worker",
      status: "80-blocked",
      history: [{ at: "2026-07-31T10:05:00.000Z", actor: "worker", action: "blocked", summary: "worker exit 1" }]
    }],
    workerRuns: [{
      id: "RUN-1",
      queueTaskId: "QUEUE-1",
      status: "FAILED",
      startedAt: "2026-07-31T10:00:00.000Z",
      completedAt: "2026-07-31T10:05:00.000Z",
      lastHeartbeat: "2026-07-31T10:04:59.000Z",
      lastAction: "tests failed"
    }],
    incidents: [{ id: "INCIDENT-1", status: "OPEN", critical: true, title: "Worker local arrêté", summary: "exit 1" }],
    commons: {
      posts: [{ id: "POST-1", channel: "HUMAN_REQUEST", state: "OPEN", importance: "IMPORTANT", title: "Autoriser la réparation" }]
    },
    eligibility: {
      queued: 1,
      eligible: 0,
      selected: null,
      inspected: [{ queueTaskId: "QUEUE-1", cardId: "CARD-1", eligible: false, reason: "capability-not-supported" }]
    },
    resilience: {
      mode: "LOCAL_LOCAL",
      developmentAutonomy: "AVAILABLE_WITHOUT_EXTERNAL_CONNECTIONS",
      sourceOfTruth: "S:\\AI_LAB\\Runtime",
      externalConnections: [
        { id: "trello", connected: false, state: "DEFERRED_LOCAL", localFallback: "LOCAL_OUTBOX_AND_LEDGER" },
        { id: "google-calendar", connected: false, state: "DEFERRED_LOCAL", localFallback: "LOCAL_OUTBOX_AND_LEDGER" }
      ]
    },
    now: () => new Date("2026-07-31T11:00:00.000Z")
  });

  assert.equal(snapshot.schema, "aione.live-blockers.v1");
  assert.equal(snapshot.generatedAt, "2026-07-31T11:00:00.000Z");
  assert.equal(snapshot.mode, "LOCAL_LOCAL");
  assert.equal(snapshot.state, "CRITICAL_LOCAL_BLOCKER");
  assert.equal(snapshot.counts.localBlocking, 2);
  assert.equal(snapshot.counts.localRepairable, 2);
  assert.equal(snapshot.counts.externalDeferred, 2);
  assert.equal(snapshot.counts.openHumanRequests, 1);
  assert.ok(snapshot.localRepairable.every((item) => item.quickActions.includes("AI_LOCAL_REPAIR")));
  assert.ok(snapshot.externalDeferred.every((item) => item.blocking === false && item.repairable === false));
  assert.equal(snapshot.currentContext.externalDependenciesBlocking, 0);
  assert.equal(snapshot.currentContext.localSourceOfTruth, "S:\\AI_LAB\\Runtime");
  assert.equal(snapshot.pipelines[0].status, "BLOCKED");
  assert.equal(snapshot.pipelines[0].stages.length, PIPELINE_STAGES.length);
  assert.ok(snapshot.pipelines[0].history.some((entry) => entry.summary === "worker exit 1"));
});

test("live blockers exposes current stages and keeps resolved incidents out of the snapshot", () => {
  const snapshot = buildLiveBlockerSnapshot({
    queue: [
      { id: "QUEUE-RUN", title: "Implémentation", status: "EXECUTING", lastHeartbeat: "2026-07-31T12:00:00.000Z" },
      { id: "QUEUE-WAIT", title: "Tests suivants", status: "QUEUED" }
    ],
    cards: [
      { id: "CARD-RUN", queueTaskId: "QUEUE-RUN", status: "40-dev", history: [] },
      { id: "CARD-WAIT", queueTaskId: "QUEUE-WAIT", status: "24-queue", history: [] }
    ],
    workerRuns: [{
      id: "RUN-ACTIVE",
      queueTaskId: "QUEUE-RUN",
      status: "RUNNING",
      startedAt: "2026-07-31T11:50:00.000Z",
      lastHeartbeat: "2026-07-31T12:00:00.000Z",
      lastAction: "rédaction du patch"
    }],
    incidents: {
      old: { id: "INCIDENT-OLD", status: "RESOLVED", summary: "ancien incident" }
    },
    eligibility: {
      selected: { queueTaskId: "QUEUE-WAIT" },
      inspected: [{ queueTaskId: "QUEUE-WAIT", eligible: true }]
    },
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] },
    commons: { openHumanRequests: 0 },
    now: "2026-07-31T12:01:00.000Z"
  });

  assert.equal(snapshot.state, "RUNNING_LOCAL");
  assert.equal(snapshot.counts.localBlocking, 0);
  assert.equal(snapshot.blockers.length, 0);
  assert.deepEqual(snapshot.currentContext.activePipelineIds, ["QUEUE-RUN"]);
  assert.equal(snapshot.currentContext.currentPipelineId, "QUEUE-RUN");
  assert.equal(snapshot.currentContext.selectedQueueTaskId, "QUEUE-WAIT");
  assert.equal(snapshot.currentContext.latestWorkerRun.status, "EXECUTING");
  assert.equal(snapshot.pipelines[0].stages.find((stage) => stage.id === "EXECUTING").state, "CURRENT");
  assert.equal(snapshot.pipelines[1].stages.find((stage) => stage.id === "QUEUED").state, "CURRENT");
});

test("a refused standalone card is visible history but does not paralyse local autonomy", () => {
  const snapshot = buildLiveBlockerSnapshot({
    cards: [{
      id: "CARD-REFUSED",
      title: "Publication externe",
      status: "80-blocked",
      finalDecision: "Refuse: ne pas publier",
      history: [{ at: "2026-07-31T09:00:00.000Z", actor: "the owner", action: "idea-rejected", summary: "ne pas publier" }]
    }],
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] },
    now: "2026-07-31T12:01:00.000Z"
  });

  assert.equal(snapshot.state, "LOCAL_READY");
  assert.equal(snapshot.counts.localBlocking, 0);
  assert.equal(snapshot.blockers[0].kind, "HUMAN_DECISION");
  assert.equal(snapshot.blockers[0].blocking, false);
  assert.deepEqual(snapshot.blockers[0].quickActions, []);
});

test("a queued retry is not masked by its historical failed worker", () => {
  const snapshot = buildLiveBlockerSnapshot({
    queue: [{
      id: "QUEUE-RETRY",
      title: "Reprise bornée",
      status: "QUEUED",
      evidence: [{ type: "local-safe-repair", at: "2026-08-02T08:00:00.000Z", summary: "correctif testé" }]
    }],
    cards: [{
      id: "CARD-RETRY",
      queueTaskId: "QUEUE-RETRY",
      status: "24-queue",
      history: [{ at: "2026-08-02T08:00:00.000Z", action: "safe-local-retry", summary: "reprise 1/3" }]
    }],
    workerRuns: [{
      id: "RUN-FAILED",
      queueTaskId: "QUEUE-RETRY",
      status: "FAILED",
      completedAt: "2026-07-31T10:05:00.000Z",
      lastHeartbeat: "2026-07-31T10:05:00.000Z",
      lastAction: "ancien échec"
    }],
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] },
    now: "2026-08-02T08:01:00.000Z"
  });

  assert.equal(snapshot.state, "LOCAL_READY");
  assert.equal(snapshot.counts.localBlocking, 0);
  assert.equal(snapshot.pipelines[0].status, "QUEUED");
  assert.equal(snapshot.pipelines[0].worker.historical, true);
  assert.equal(snapshot.pipelines[0].updatedAt, "2026-08-02T08:00:00.000Z");
});

test("a blocked repair is folded into its root blocker and never becomes recursive", () => {
  const snapshot = buildLiveBlockerSnapshot({
    queue: [
      { id: "ROOT-1", title: "Cause racine", status: "BLOCKED" },
      { id: "REPAIR-1", title: "Réparation", status: "BLOCKED", repairTargetQueueTaskId: "ROOT-1", retryCount: 1, maximumRetries: 3 }
    ],
    cards: [],
    workerRuns: [],
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] }
  });

  assert.equal(snapshot.counts.localBlocking, 1);
  assert.equal(snapshot.localRepairable.length, 1);
  assert.equal(snapshot.localRepairable[0].queueTaskId, "ROOT-1");
  assert.equal(snapshot.localRepairable[0].repairTaskId, "REPAIR-1");
  assert.equal(snapshot.localRepairable[0].repairStatus, "BLOCKED");
  assert.equal(snapshot.localRepairable[0].retryCount, 1);
  assert.ok(snapshot.pipelines.some((pipeline) => pipeline.id === "REPAIR-1"));
  assert.ok(!snapshot.blockers.some((blocker) => blocker.queueTaskId === "REPAIR-1"));
});

test("an exhausted repair disables recursive local repair on the root", () => {
  const snapshot = buildLiveBlockerSnapshot({
    queue: [
      { id: "ROOT-X", title: "Cause racine", status: "BLOCKED" },
      { id: "REPAIR-X", title: "Réparation", status: "FAILED", repairTargetQueueTaskId: "ROOT-X", retryCount: 3, maximumRetries: 3 }
    ],
    resilience: { mode: "LOCAL_LOCAL", externalConnections: [] }
  });

  assert.equal(snapshot.counts.localBlocking, 1);
  assert.equal(snapshot.counts.localRepairable, 0);
  assert.equal(snapshot.blockers[0].repairExhausted, true);
  assert.deepEqual(snapshot.blockers[0].quickActions, ["IMMUNE_DOCTOR"]);
});
