import assert from "node:assert/strict";
import test from "node:test";
import {
  buildReflectiveAutonomyInstruction,
  chooseReflectiveAction,
  evaluateReflectiveDecision,
  readReflectiveAutonomyPolicy
} from "./reflective-autonomy.mjs";

const { policy, validation } = readReflectiveAutonomyPolicy();

function decision(level, overrides = {}) {
  return {
    id: `choice-${level.toLowerCase()}`,
    level,
    kind: "strategy-adaptation",
    scope: "local-cognitive-runtime",
    expectedEffect: "Réduire les erreurs sans augmenter le risque.",
    reversible: true,
    rollback: "Restaurer le profil précédent.",
    confidence: 0.9,
    evidence: ["benchmark-local-001"],
    localOnly: true,
    external: false,
    domains: ["cognition"],
    gates: {
      sandboxPassed: true,
      testsPassed: true,
      baselineCompared: true,
      canaryPassed: true,
      rollbackVerified: true,
      noCriticalRegression: true
    },
    utility: 0.8,
    ...overrides
  };
}

test("policy enables self-directed local reflection without human presence", () => {
  assert.equal(validation.ok, true);
  assert.equal(policy.independentFromHumanPresence, true);
  assert.match(buildReflectiveAutonomyInstruction(policy), /choisis toi-même/i);
});

test("E0 and proven E2 decisions are autonomously approved", () => {
  assert.equal(evaluateReflectiveDecision(policy, decision("E0", { evidence: [] })).status, "AUTO_APPROVED");
  const result = evaluateReflectiveDecision(policy, decision("E2"));
  assert.equal(result.ok, true);
  assert.equal(result.humanApprovalRequired, false);
  assert.equal(result.status, "AUTO_APPROVED");
});

test("E2 gathers evidence instead of asking the human when a proof gate is missing", () => {
  const result = evaluateReflectiveDecision(policy, decision("E2", { gates: { sandboxPassed: true } }));
  assert.equal(result.status, "NEEDS_MORE_EVIDENCE");
  assert.equal(result.reasons.includes("GATE_testsPassed_REQUIRED"), true);
});

test("E3 is independent in isolation but canonical promotion still needs the owner", () => {
  assert.equal(evaluateReflectiveDecision(policy, decision("E3", { deploymentTarget: "isolated-runtime" })).status, "AUTO_APPROVED_ISOLATED");
  assert.equal(evaluateReflectiveDecision(policy, decision("E3", { deploymentTarget: "canonical" })).status, "OWNER_REQUIRED_CANONICAL");
});

test("E4, immutable domains and external action remain denied or owner-gated", () => {
  assert.equal(evaluateReflectiveDecision(policy, decision("E4")).status, "DENIED_IMMUTABLE");
  assert.equal(evaluateReflectiveDecision(policy, decision("E2", { domains: ["permissions"] })).status, "DENIED_IMMUTABLE");
  assert.equal(evaluateReflectiveDecision(policy, decision("E2", { localOnly: false, external: true })).status, "OWNER_REQUIRED_EXTERNAL");
});

test("the system selects its own best eligible reflective choice", () => {
  const choice = chooseReflectiveAction(policy, [
    decision("E2", { id: "safe-low", utility: 0.4 }),
    decision("E4", { id: "unsafe-high", utility: 1 }),
    decision("E2", { id: "safe-high", utility: 0.9 })
  ]);
  assert.equal(choice.status, "SELF_SELECTED");
  assert.equal(choice.selected.candidate.id, "safe-high");
});
