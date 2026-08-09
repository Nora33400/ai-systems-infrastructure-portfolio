import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { moduleForDate, nextSessionDate, runUserLearningPlanner } from "./user-learning-planner.mjs";

test("the curriculum rotates one module per week", () => {
  const config = {
    startDate: "2026-08-03",
    modules: [{ id: "A" }, { id: "B" }]
  };
  assert.equal(moduleForDate(config, new Date(2026, 7, 3, 10)).module.id, "A");
  assert.equal(moduleForDate(config, new Date(2026, 7, 10, 10)).module.id, "B");
  assert.equal(moduleForDate(config, new Date(2026, 7, 17, 10)).module.id, "A");
});

test("next session dates never point into the past", () => {
  const now = new Date(2026, 7, 4, 19, 0, 0);
  const next = nextSessionDate(now, { day: "TU", start: "18:00" });
  assert.ok(next > now);
  assert.equal(next.getDay(), 2);
});

test("planner creates current and weekly session kits only on S", () => {
  const base = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(base, { recursive: true });
  const runtimeRoot = mkdtempSync(join(base, "learning-coach-"));
  const root = mkdtempSync(join(base, "learning-config-"));
  try {
    mkdirSync(join(root, "config"), { recursive: true });
    const config = {
      schema: "aione.user-learning-plan.v1",
      enabled: true,
      timezone: "Europe/Paris",
      startDate: "2026-08-03",
      runtimeRoot,
      purpose: "Apprendre à utiliser la Forge.",
      sessionCadence: [{
        id: "tutor",
        calendarSeriesId: "CAL-TUTOR-TU",
        day: "TU",
        start: "18:00",
        durationMinutes: 45,
        structure: ["objectif", "pratique", "preuve"]
      }],
      modules: [{
        id: "FORGE-01",
        title: "Observer",
        outcomes: ["lire une preuve"],
        exercise: "Lire un manifeste.",
        evidence: "Une note vérifiée.",
        convention: "Pas de preuve, pas de terminé."
      }]
    };
    const configPath = join(root, "config", "user-learning-plan.json");
    writeFileSync(configPath, JSON.stringify(config), "utf8");
    const result = runUserLearningPlanner({
      root,
      configPath,
      now: new Date(2026, 7, 3, 12, 0, 0)
    });
    assert.equal(result.ok, true);
    assert.equal(result.moduleId, "FORGE-01");
    assert.equal(existsSync(join(runtimeRoot, "current-session.md")), true);
    assert.match(readFileSync(join(runtimeRoot, "current-session.md"), "utf8"), /État GPU/);
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});
