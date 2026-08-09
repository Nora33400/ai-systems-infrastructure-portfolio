import assert from "node:assert/strict";
import test from "node:test";
import { buildMultiEcosystemPlan, PROVIDER_POLICY } from "./multi-ecosystem-planner.mjs";

const AT = new Date("2026-08-03T12:34:00.000Z");
const domains = {
  ecosystems: [
    { id: "digital-programming", name: "Programmation", domains: ["software", "automation"] },
    { id: "scientific-extension", name: "Science", domains: ["research", "corpus"] },
    { id: "social-mediation", name: "Social", domains: ["mediation", "accessibility"] },
    { id: "local-creation", name: "Creation", domains: ["image", "video", "audio", "writing"] }
  ]
};
const gpuConfig = {
  schedule: { partitionMinutes: 60 },
  lanes: [
    { id: "gpu-dev", label: "GPU dev", focusRotation: ["code", "debug"] },
    { id: "gpu-qa", label: "GPU QA", focusRotation: ["tests", "validation"] }
  ]
};

function sample() {
  return buildMultiEcosystemPlan({
    at: AT,
    ecosystemDomains: domains,
    gpuConfig,
    portfolio: {
      generatedAt: "2026-08-01T00:00:00.000Z",
      projects: [
        {
          id: "forge",
          name: "Forge software runtime",
          status: "IN_PROGRESS",
          ecosystemId: "digital-programming",
          category: "CURRENT",
          planning: { durationDays: 30 },
          dependencies: []
        },
        {
          id: "media-lab",
          name: "Image video audio studio",
          category: "IDEA",
          planning: { durationDays: 90 },
          dependencies: ["forge"]
        },
        {
          id: "formula-corpus",
          name: "Scientific formula corpus research",
          category: "SPECULATIVE",
          planning: { durationDays: 365 }
        }
      ]
    },
    tasks: [
      { id: "code-1", projectId: "forge", title: "Coder", status: "24-queue", priority: "P1" },
      { id: "code-2", projectId: "forge", title: "Intégrer", status: "QUEUED", priority: "P2", dependencies: ["code-1"] },
      { id: "code-3", projectId: "forge", title: "Inconnu", status: "QUEUED", dependencies: ["missing-task"] },
      { id: "review-1", projectId: "forge", title: "Revue humaine", status: "60-review", priority: "P0" },
      { id: "media-1", projectId: "media-lab", title: "Storyboard", status: "QUEUED", priority: "P1", dueAt: "2026-08-09T00:00:00.000Z" },
      { id: "science-1", projectId: "formula-corpus", title: "Indexer", status: "90-done", priority: "P1" }
    ]
  });
}

test("regroupe les projets, rend les inférences visibles et calcule les jalons", () => {
  const plan = sample();
  const digital = plan.ecosystems.find((entry) => entry.id === "digital-programming");
  const creation = plan.ecosystems.find((entry) => entry.id === "local-creation");
  const science = plan.ecosystems.find((entry) => entry.id === "scientific-extension");

  assert.equal(digital.projects[0].ecosystemAssignment.source, "DECLARED");
  assert.equal(creation.projects[0].id, "media-lab");
  assert.equal(creation.projects[0].ecosystemAssignment.source, "INFERRED_KEYWORDS");
  assert.equal(science.projects[0].id, "formula-corpus");
  assert.deepEqual(creation.dependencies, [{ fromProjectId: "media-lab", toProjectId: "forge", state: "KNOWN" }]);
  assert.deepEqual(creation.milestones.find((item) => item.horizonDays === 7).taskIds, ["media-1"]);
  assert.ok(creation.milestones.find((item) => item.horizonDays === 90).projectIds.includes("media-lab"));
  assert.equal(plan.totals.projects, 3);
  assert.equal(plan.externalActionsPerformed, false);
});

test("sépare tâches prêtes, bloquées et terminées avec preuves de dépendance", () => {
  const plan = sample();
  const digital = plan.ecosystems.find((entry) => entry.id === "digital-programming");
  const science = plan.ecosystems.find((entry) => entry.id === "scientific-extension");

  assert.deepEqual(digital.readyTasks.map((task) => task.id), ["code-1"]);
  assert.deepEqual(digital.blockedTasks.map((task) => task.id), ["code-2", "code-3"]);
  assert.deepEqual(digital.waitingTasks.map((task) => task.id), ["review-1"]);
  assert.deepEqual(digital.blockedTasks[0].reasons, ["INCOMPLETE_DEPENDENCY"]);
  assert.deepEqual(digital.blockedTasks[1].reasons, ["MISSING_DEPENDENCY"]);
  assert.deepEqual(science.completedTasks.map((task) => task.id), ["science-1"]);
  assert.equal(plan.totals.ready, 1);
  assert.equal(plan.totals.blocked, 3);
  assert.equal(plan.totals.waiting, 1);
  assert.equal(plan.totals.completed, 1);
});

test("distribue équitablement les tâches prêtes sur deux lanes pendant 24 heures", () => {
  const plan = sample();
  assert.equal(plan.schedule.mode, "CONTINUOUS_24_7_LOCAL_PLAN");
  assert.equal(plan.schedule.lanes.length, 2);
  assert.equal(plan.schedule.slots.length, 48);
  assert.equal(plan.schedule.startAt, "2026-08-03T13:00:00.000Z");
  assert.equal(plan.schedule.endAt, "2026-08-04T13:00:00.000Z");

  const assigned = plan.schedule.slots.filter((slot) => slot.assignmentKind === "PROJECT_TASK");
  assert.deepEqual(assigned.map((slot) => slot.taskId), ["code-1"]);
  assert.deepEqual(assigned.map((slot) => slot.ecosystemId), ["digital-programming"]);
  assert.ok(plan.schedule.slots.every((slot) => slot.providerMode === "LOCAL_FREE"));
  assert.ok(plan.schedule.slots.every((slot) => slot.externalActionAllowed === false));
});

test("la politique gratuite est stable et la route payante ne peut jamais être auto-sélectionnée", () => {
  const first = sample();
  const second = sample();
  const futurePaid = first.providerPolicy.modes.find((mode) => mode.id === "FUTURE_PAID");
  const connector = first.providerPolicy.modes.find((mode) => mode.id === "OPTIONAL_FREE_CONNECTOR");

  assert.equal(first.providerPolicy.selectedMode, "LOCAL_FREE");
  assert.equal(connector.degradable, true);
  assert.equal(connector.fallbackMode, "LOCAL_FREE");
  assert.equal(futurePaid.enabled, false);
  assert.equal(futurePaid.autoSelectable, false);
  assert.equal(first.planHash, second.planHash);
  assert.deepEqual(PROVIDER_POLICY, first.providerPolicy);
});

test("refuse les identifiants d'écosystème dupliqués", () => {
  assert.throws(() => buildMultiEcosystemPlan({
    at: AT,
    ecosystemDomains: { ecosystems: [{ id: "same" }, { id: "same" }] },
    gpuConfig,
    portfolio: { projects: [] },
    tasks: []
  }), /duplique ou vide/u);
});
