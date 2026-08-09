import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ResilienceManager, compareVersions } from "./resilience-manager.mjs";

const policy = JSON.parse(readFileSync(new URL("../../config/resilience-manager.json", import.meta.url), "utf8"));

test("backup planning keeps multiple generations and never deletes automatically", () => {
  const manager = new ResilienceManager({ policy, now: () => new Date("2026-08-06T20:00:00Z") });
  const plan = manager.buildBackupPlan({ generations: Array.from({ length: 7 }, (_, index) => ({ id: `B${index}`, integrityVerified: true })) });
  assert.equal(plan.retentionHealthy, true);
  assert.equal(plan.deleteGeneration, false);
  assert.equal(plan.action, "CALL_EXISTING_VERIFIED_BACKUP_ENGINE");
});

test("version comparison detects corruption, incoherence and possible loss", () => {
  const report = compareVersions(
    { id: "current", integrityVerified: false, files: { "config/a.json": "new" } },
    { id: "previous", files: { "config/a.json": "old", "memory/tile.json": "kept" } }
  );
  assert.equal(report.corruptionSuspected, true);
  assert.equal(report.dataLossSuspected, true);
  assert.ok(report.anomalies.some((entry) => entry.path === "memory/tile.json"));
});

test("restore requires a verified backup and owner approval by default", () => {
  const manager = new ResilienceManager({ policy });
  const backup = { id: "B7", integrityVerified: true, restoreTestPassed: true };
  assert.equal(manager.evaluateRestore({ backup, trigger: "CORRUPTION" }).status, "OWNER_AUTHORIZATION_REQUIRED");
  assert.equal(manager.evaluateRestore({ backup, trigger: "CORRUPTION", ownerAuthorization: { approved: true, backupId: "B7" } }).restoreAllowed, true);
  assert.equal(manager.evaluateRestore({ backup: { ...backup, integrityVerified: false } }).restoreAllowed, false);
});

test("incident learning never rewrites fundamental rules", () => {
  const manager = new ResilienceManager({ policy });
  assert.equal(manager.learnFromIncident({ incidentId: "I1", cause: "drift", proposedProcedure: "change permission", touchesFundamentalRule: true }).decision, "REFUSED_FUNDAMENTAL_RULE");
});
