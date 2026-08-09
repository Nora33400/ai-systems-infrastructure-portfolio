import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { buildModelEvolutionBacklog, readModelEvolutionHandoffStatus, writeModelEvolutionHandoff } from "./model-evolution-handoff.mjs";

const config = {
  circuits: [{ id: "C1", stages: ["measure", "verify"], output: "proof", mutation: false }],
  roadmap: [
    { id: "P0-A", priority: "P0", status: "ACTIVE", objective: "Mesurer le baseline.", acceptance: ["three-runs"] },
    { id: "P9-DONE", priority: "P9", status: "DONE", objective: "Ne pas republier.", acceptance: [] }
  ]
};

test("build handoff includes active work and excludes terminal work", () => {
  const result = buildModelEvolutionBacklog(config);
  assert.equal(result.items.length, 1);
  assert.match(result.content, /P0-A/u);
  assert.doesNotMatch(result.content, /P9-DONE/u);
  assert.match(result.content, /aucun élargissement de permission/u);
});

test("write handoff is idempotent and stays inside the supplied runtime", () => {
  const root = mkdtempSync(join(tmpdir(), "aione-model-evolution-root-"));
  const runtimeRoot = mkdtempSync(join(tmpdir(), "aione-model-evolution-runtime-"));
  try {
    mkdirSync(join(root, "config"), { recursive: true });
    writeFileSync(join(root, "config", "autonomous-model-evolution.json"), JSON.stringify(config), "utf8");
    const first = writeModelEvolutionHandoff({ root, runtimeRoot });
    const second = writeModelEvolutionHandoff({ root, runtimeRoot });
    assert.equal(first.changed, true);
    assert.equal(second.changed, false);
    assert(first.outputPath.startsWith(runtimeRoot));
    assert.match(readFileSync(first.outputPath, "utf8"), /Mesurer le baseline/u);
    writeFileSync(join(runtimeRoot, "ModelEvolution", "handoff-state.json"), "{partial", "utf8");
    const recovered = readModelEvolutionHandoffStatus({ runtimeRoot });
    assert.equal(recovered.digest, first.digest);
    assert.equal(recovered.recoveredFromLastValid, true);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});
