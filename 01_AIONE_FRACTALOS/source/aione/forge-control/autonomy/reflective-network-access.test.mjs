import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { ReflectiveNetworkAccessManager, evaluateNetworkNeed } from "./reflective-network-access.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const basePolicy = JSON.parse(readFileSync(new URL("../../config/reflective-network-access.json", import.meta.url), "utf8"));
const request = {
  level: "N1",
  reason: "Vérifier une publication scientifique absente du corpus local.",
  expectedBenefit: 1,
  confidenceGain: 0.9,
  freshnessNeed: 0.8,
  urgency: 0.5,
  risk: 0.1,
  localAlternativeStrength: 0,
  sources: ["https://arxiv.org/abs/2601.00001"],
  dataCategories: []
};

test("local knowledge prevents a network request", () => {
  const result = evaluateNetworkNeed(basePolicy, request, { available: true, confidence: 0.95, reference: "tile:local" });
  assert.equal(result.status, "LOCAL_KNOWLEDGE_SUFFICIENT");
  assert.equal(result.networkAllowed, false);
});

test("necessary allowlisted access is proposed, then approved only by a bounded grant", () => {
  const proposed = evaluateNetworkNeed(basePolicy, request, { available: false });
  assert.equal(proposed.status, "PROPOSE_ACCESS");
  const approved = evaluateNetworkNeed(basePolicy, {
    ...request,
    authorization: { authorized: true, level: "N1", hosts: ["arxiv.org"], expiresAt: "2026-08-07T00:00:00Z" }
  }, { available: false }, { now: new Date("2026-08-06T20:00:00Z") });
  assert.equal(approved.status, "APPROVED_BOUNDED");
  assert.equal(approved.networkAllowed, true);
});

test("sensitive data and non-whitelisted sources are refused", () => {
  assert.equal(evaluateNetworkNeed(basePolicy, { ...request, dataCategories: ["secrets"] }, {}).status, "DENIED_SENSITIVE_DATA");
  assert.equal(evaluateNetworkNeed(basePolicy, { ...request, sources: ["https://example.com/data"] }, {}).status, "HOST_NOT_ALLOWLISTED");
});

test("approved access produces a hash-chained reflective record", (context) => {
  const root = mkdtempSync(join(testRuntimeRoot(), "network-access-"));
  context.after(() => rmSync(root, { recursive: true, force: true }));
  const policy = { ...basePolicy, ledgerPath: join(root, "ledger.jsonl") };
  const manager = new ReflectiveNetworkAccessManager({ policy, now: () => new Date("2026-08-06T20:00:00Z") });
  const decision = manager.decide({
    ...request,
    authorization: { authorized: true, level: "N1", hosts: ["arxiv.org"], expiresAt: "2026-08-07T00:00:00Z" }
  });
  const record = manager.recordAccess({ decision, durationMs: 120, result: "résumé local", confidence: 0.84, memoryImpact: "NEW_TILE", useful: true, localCopyReference: "tile:arxiv" });
  assert.match(record.hash, /^[a-f0-9]{64}$/u);
  assert.equal(record.futureRecommendation, "CACHE_LOCALLY_TO_REDUCE_FUTURE_DEPENDENCY");
});
