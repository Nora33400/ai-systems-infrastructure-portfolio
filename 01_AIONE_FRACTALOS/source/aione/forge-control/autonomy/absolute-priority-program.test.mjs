import assert from "node:assert/strict";
import test from "node:test";
import { buildAbsolutePriorityProgram } from "./absolute-priority-program.mjs";
import { buildPolicyContextResolution, readContextAuthorityPolicy } from "./context-authority.mjs";

function configuration(gateStatus = "NOT_VERIFIED", withEvidence = false) {
  const prompts = Array.from({ length: 4 }, (_, index) => ({
    id: `PROMPT_${index + 1}`,
    name: `Prompt ${index + 1}`,
    source: `docs/prompts/prompt-${index + 1}.md`,
    status: "ACTIVE",
    functionalGate: gateStatus,
    workstreams: [{
      id: `ABSOLUTE-PROMPT-${index + 1}-CORE`,
      priority: "P0",
      status: "ACTIVE",
      objective: "Construire une capacité testable.",
      targetFiles: ["forge-control/autonomy"],
      acceptance: ["proof"]
    }]
  }));
  const functionalGates = Array.from({ length: 4 }, (_, index) => ({
    id: `PROMPT_${index + 1}_FUNCTIONAL`,
    status: gateStatus,
    requires: ["real-test"],
    evidence: withEvidence ? [{ criterion: "real-test", ok: true, proof: "node --test: pass" }] : []
  }));
  return {
    enabled: true,
    mode: "CONTINUOUS_24_7_DUAL_GPU_ABSOLUTE_P0",
    prompts,
    functionalGates,
    interfaceActivation: { targets: ["OPENWEBUI", "LOBEHUB"] }
  };
}

test("four prompt workstreams are active while interfaces remain gated", () => {
  const program = buildAbsolutePriorityProgram(configuration());
  assert.equal(program.valid, true);
  assert.equal(program.activeWorkstreams.length, 4);
  assert.equal(program.allFunctional, false);
  assert.equal(program.interfaceActivation.effectiveStatus, "BLOCKED_BY_FUNCTIONAL_GATES");
  assert.deepEqual(program.interfaceActivation.targets, ["OPENWEBUI", "LOBEHUB"]);
});

test("a VERIFIED label without criterion-level proof never unlocks interfaces", () => {
  const program = buildAbsolutePriorityProgram(configuration("VERIFIED", false));
  assert.equal(program.gates.every((gate) => gate.verifiedWithRealEvidence), false);
  assert.equal(program.interfaceActivation.effectiveStatus, "BLOCKED_BY_FUNCTIONAL_GATES");
});

test("all four exact evidence sets make interface planning ready but never auto-activate it", () => {
  const program = buildAbsolutePriorityProgram(configuration("VERIFIED", true));
  assert.equal(program.allFunctional, true);
  assert.equal(program.interfaceActivation.effectiveStatus, "READY_FOR_INTERFACE_PLANNING");
  assert.equal(program.interfaceActivation.automaticActivation, false);
});

test("a contextual Owner revision adapts historical prompts without deleting their workstreams", () => {
  const { policy } = readContextAuthorityPolicy();
  const authorityResolution = buildPolicyContextResolution(policy);
  const program = buildAbsolutePriorityProgram(configuration(), { authorityResolution });
  assert.equal(program.contextualAuthority.applied, true);
  assert.equal(program.contextualAuthority.legacyPreemption, false);
  assert.equal(program.effectivePriorityClass, "CONTEXTUAL_P0_REVISABLE_BASE");
  assert.equal(program.activeWorkstreams.length, 4);
  assert.equal(program.activeWorkstreams.every((entry) => entry.contextStatus === "ADAPTED"), true);
});
