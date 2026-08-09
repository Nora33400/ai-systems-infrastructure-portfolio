import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { buildProjectPlanning, createTrelloPlanningOutbox } from "./project-planning.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

test("week and month planning expose durations without pretending estimates are commitments", () => {
  const planning = buildProjectPlanning({
    at: new Date("2026-07-31T12:00:00.000Z"),
    portfolio: {
      generatedAt: "2026-07-26T10:30:00.000Z",
      projects: [{ id: "aione", name: "AIONE", category: "CURRENT", status: "ACTIVE", authority: "LOCAL" }]
    },
    tasks: [{ id: "T1", project: "AIONE", status: "40-dev" }]
  });
  assert.equal(planning.projects[0].durationDays, 90);
  assert.equal(planning.projects[0].scheduleSource, "SYSTEM_ESTIMATE");
  assert.equal(planning.projects[0].taskCount, 1);
  assert.deepEqual(planning.week.projectIds, ["aione"]);
  assert.match(planning.warning, /pas des promesses/u);
});

test("portfolio aliases attach Forge cards to one declared ecosystem", () => {
  const planning = buildProjectPlanning({
    portfolio: {
      generatedAt: "2026-07-31T00:00:00.000Z",
      projects: [{ id: "aione-fractalos", name: "AIONE / FractalOS", aliases: ["AIONE Forge"], category: "CURRENT" }]
    },
    tasks: [{ id: "TASK-1", project: "AIONE Forge", status: "40-dev" }],
    at: new Date("2026-07-31T12:00:00.000Z")
  });
  assert.equal(planning.projects[0].taskCount, 1);
  assert.equal(planning.projects[0].activeTaskCount, 1);
});

test("Trello outbox is bounded, idempotent and hash chained", (context) => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-planning-"));
  context.after(() => rmSync(root, { recursive: true, force: true }));
  const outbox = createTrelloPlanningOutbox({ runtimeRoot: root, now: () => new Date("2026-07-31T12:00:00.000Z") });
  const tasks = Array.from({ length: 5 }, (_, index) => ({
    id: `T${index}`,
    project: "AIONE",
    title: `Tâche ${index}`,
    description: "preuve locale",
    priority: "P0",
    status: "40-dev"
  }));
  assert.equal(outbox.prepare(tasks).prepared, 3);
  assert.equal(outbox.prepare(tasks).prepared, 2);
  assert.equal(outbox.prepare(tasks).prepared, 0);
  assert.equal(outbox.status().pending, 5);
  assert.equal(outbox.verify().ok, true);
});
