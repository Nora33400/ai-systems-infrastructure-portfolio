import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ReflectiveCognitiveEngine } from "../core/reflective-engine.mjs";
import { ReflectionMemory } from "../memory/reflection-memory.mjs";

const policy = JSON.parse(readFileSync(new URL("../../config/reflective-autonomy.json", import.meta.url), "utf8"));

function decision(id, utility, overrides = {}) {
  return {
    id,
    level: "E0",
    kind: "strategy",
    scope: "current-task",
    expectedEffect: "amélioration mesurable",
    reversible: true,
    rollback: "restaurer la stratégie précédente",
    confidence: 0.8,
    localOnly: true,
    external: false,
    utility,
    evidence: ["test-local"],
    ...overrides
  };
}

test("simple and complex scenarios self-select an evidence-linked decision", () => {
  const engine = new ReflectiveCognitiveEngine({ policy });
  assert.equal(engine.reflect({ decisions: [decision("simple", 1)] }).decision.id, "simple");
  const complex = engine.reflect({
    decisions: [decision("safe", 3), decision("fast", 8, { domains: ["permissions"] })],
    strategies: [
      { id: "baseline", utility: 2, confidence: 0.9, cost: 0.2, risk: 0.1 },
      { id: "candidate", utility: 5, confidence: 0.8, cost: 0.5, risk: 0.2 },
      { id: "uncertain", utility: 10, confidence: 0.1 }
    ]
  });
  assert.equal(complex.decision.id, "safe");
  assert.equal(complex.strategy.id, "candidate");
});

test("subgoals are created, prioritized, adopted and retired autonomously", () => {
  const engine = new ReflectiveCognitiveEngine({ policy });
  const low = engine.createSubgoal({ title: "documenter", utility: 1 });
  const high = engine.createSubgoal({ title: "réparer", utility: 9, acceptance: ["tests-pass"] });
  assert.equal(engine.prioritizeSubgoals()[0].id, high.id);
  assert.equal(engine.setSubgoalStatus(high.id, "ADOPTED").status, "ADOPTED");
  assert.equal(engine.setSubgoalStatus(low.id, "RETIRED").status, "RETIRED");
});

test("prediction errors are recorded and raw chains of thought are rejected", () => {
  const engine = new ReflectiveCognitiveEngine({ policy });
  assert.equal(engine.recordPrediction({ subject: "duration", predicted: 2, actual: 5 }).absoluteError, 3);
  const memory = new ReflectionMemory();
  assert.throws(() => memory.append({ rawChainOfThought: "secret reasoning" }), /refusée/u);
  assert.equal(JSON.stringify(engine.snapshot()).includes("chainOfThought"), false);
});
