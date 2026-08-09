import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function validateResiliencePolicy(policy) {
  const issues = [];
  if (policy?.schema !== "aione.resilience-manager.v1") issues.push("INVALID_SCHEMA");
  if (policy?.fundamentalRulesImmutable !== true) issues.push("FUNDAMENTAL_RULES_MUST_BE_IMMUTABLE");
  if (policy?.destructiveCleanupAutomatic !== false) issues.push("AUTOMATIC_DESTRUCTIVE_CLEANUP_FORBIDDEN");
  if (Number(policy?.generations?.minimumRetained || 0) < 2) issues.push("MULTIPLE_GENERATIONS_REQUIRED");
  return { ok: issues.length === 0, issues };
}

function compareVersions(current = {}, previous = {}) {
  const currentFiles = current.files || {};
  const previousFiles = previous.files || {};
  const paths = [...new Set([...Object.keys(currentFiles), ...Object.keys(previousFiles)])].sort();
  const changes = paths.map((path) => {
    if (!(path in currentFiles)) return { path, status: "MISSING_CURRENT", previousHash: previousFiles[path] };
    if (!(path in previousFiles)) return { path, status: "NEW_CURRENT", currentHash: currentFiles[path] };
    if (currentFiles[path] !== previousFiles[path]) return { path, status: "CHANGED", previousHash: previousFiles[path], currentHash: currentFiles[path] };
    return { path, status: "UNCHANGED", currentHash: currentFiles[path] };
  });
  const anomalies = changes.filter((entry) => ["MISSING_CURRENT", "CHANGED"].includes(entry.status));
  return {
    schema: "aione.resilience-comparison.v1",
    currentId: current.id || null,
    previousId: previous.id || null,
    changes,
    anomalies,
    corruptionSuspected: current.integrityVerified === false,
    dataLossSuspected: changes.some((entry) => entry.status === "MISSING_CURRENT")
  };
}

class ResilienceManager {
  constructor({ policy, policyPath, now = () => new Date() } = {}) {
    this.policy = policy || JSON.parse(readFileSync(resolve(policyPath), "utf8"));
    this.now = now;
    const validation = validateResiliencePolicy(this.policy);
    if (!validation.ok) throw new Error(validation.issues.join(","));
  }

  buildBackupPlan({ generations = [], domains = this.policy.monitoredDomains } = {}) {
    const verified = generations.filter((generation) => generation.integrityVerified === true);
    return {
      schema: "aione.resilience-backup-plan.v1",
      planId: randomUUID(),
      createdAt: this.now().toISOString(),
      provider: this.policy.backupProvider,
      periodic: this.policy.schedule.periodic === true,
      domains: [...domains],
      createNewGeneration: true,
      retainedVerifiedGenerations: verified.length,
      retentionHealthy: verified.length >= Number(this.policy.generations.minimumRetained),
      deleteGeneration: false,
      action: "CALL_EXISTING_VERIFIED_BACKUP_ENGINE"
    };
  }

  evaluateRestore({ backup, trigger, ownerAuthorization = null } = {}) {
    if (!backup?.id || backup.integrityVerified !== true || backup.restoreTestPassed !== true) {
      return { ok: false, status: "RESTORE_REFUSED_UNVERIFIED_BACKUP", restoreAllowed: false };
    }
    const ownerApproved = ownerAuthorization?.approved === true && ownerAuthorization.backupId === backup.id;
    const automatic = this.policy.restorePolicy.automaticEnabled === true &&
      (this.policy.restorePolicy.allowedAutomaticTriggers || []).includes(trigger);
    if (!ownerApproved && !automatic) {
      return { ok: true, status: "OWNER_AUTHORIZATION_REQUIRED", restoreAllowed: false, backupId: backup.id };
    }
    return {
      ok: true,
      status: ownerApproved ? "RESTORE_AUTHORIZED_BY_OWNER" : "RESTORE_AUTHORIZED_BY_PREDEFINED_POLICY",
      restoreAllowed: true,
      backupId: backup.id,
      trigger,
      authorizationHash: digest(ownerAuthorization || { automatic: true, trigger, backupId: backup.id }),
      rollbackRequired: true
    };
  }

  learnFromIncident({ incidentId, cause, evidence = [], proposedProcedure, touchesFundamentalRule = false }) {
    return {
      schema: "aione.resilience-incident-learning.v1",
      incidentId: String(incidentId),
      learnedAt: this.now().toISOString(),
      cause: String(cause),
      evidence: evidence.map(String),
      proposal: String(proposedProcedure || ""),
      decision: touchesFundamentalRule ? "REFUSED_FUNDAMENTAL_RULE" : "PROPOSE_VERSIONED_PROCEDURE_UPDATE",
      fundamentalRulesModified: false
    };
  }
}

export { ResilienceManager, compareVersions, validateResiliencePolicy };
