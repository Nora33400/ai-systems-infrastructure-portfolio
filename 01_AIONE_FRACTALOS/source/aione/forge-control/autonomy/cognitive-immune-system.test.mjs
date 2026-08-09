import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CognitiveImmuneSystem, parseGpuTelemetry } from "./cognitive-immune-system.mjs";

const policy = JSON.parse(readFileSync(new URL("../../config/cognitive-immune-system.json", import.meta.url), "utf8"));

test("health classification spans green through black without mutating the system", () => {
  const immune = new CognitiveImmuneSystem({ policy });
  assert.equal(immune.assess({ integrityOk: true, auditIntegrityOk: true, memoryIntegrity: true, ramPercent: 30, gpus: [] }).level, "GREEN");
  assert.equal(immune.assess({ integrityOk: true, auditIntegrityOk: true, memoryIntegrity: true, responseQuality: null, gpus: [] }).signals.responseQuality, "GREEN");
  assert.equal(immune.assess({ integrityOk: true, auditIntegrityOk: true, memoryIntegrity: true, ramPercent: 92, gpus: [] }).level, "ORANGE");
  const black = immune.assess({ integrityOk: false, auditIntegrityOk: true, memoryIntegrity: true, gpus: [] });
  assert.equal(black.level, "BLACK");
  assert.equal(black.automaticMutationPerformed, false);
});

test("GPU telemetry covers utilization, VRAM and temperature", () => {
  const [gpu] = parseGpuTelemetry("RTX 4060, 91, 7000, 8188, 76\n");
  assert.equal(gpu.utilizationPercent, 91);
  assert.ok(gpu.vramPercent > 85);
  assert.equal(gpu.temperatureCelsius, 76);
});

test("critical processes and progressive degradation raise visible state", () => {
  const immune = new CognitiveImmuneSystem({ policy });
  const state = immune.assess({ integrityOk: true, auditIntegrityOk: true, memoryIntegrity: true, gpus: [], criticalProcesses: [{ id: "forge", healthy: false }] }, [
    { level: "GREEN" }, { level: "YELLOW" }, { level: "ORANGE" }
  ]);
  assert.equal(state.level, "RED");
  assert.equal(state.progressiveDegradation, true);
  assert.ok(state.strategies.includes("NOTIFY_USER"));
});

test("threshold plasticity proposes a bounded version instead of applying it", () => {
  const immune = new CognitiveImmuneSystem({ policy });
  const outcomes = Array.from({ length: 20 }, (_, index) => ({ classification: index < 8 ? "FALSE_POSITIVE" : "CORRECT" }));
  const proposal = immune.proposeThresholdUpdate({ outcomes });
  assert.equal(proposal.status, "VERSIONED_THRESHOLD_PROPOSAL");
  assert.equal(proposal.applied, false);
  assert.equal(proposal.maximumAdjustmentPercent, 5);
});
