import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { CASE_AUTONOMY } from "./case-autonomy.mjs";
import { GovernanceService } from "./governance-service.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const SECRET = "governance-service-test-secret-at-least-32-bytes";

function review() {
  return {
    reformulation: "Créer un mandat local borné pour tester la gouvernance.",
    architecture: ["Dossier Owner", "Mandat HMAC", "Exécution isolée"],
    risks: [{ risk: "Extension de portée", mitigation: "Subset strict" }],
    permissions: ["test.existing", "workspace.isolated.apply-proposal"],
    tests: ["anti-rejeu", "révocation"],
    rollback: ["Restaurer le workspace isolé"],
    channels: ["local-artifact"],
    acceptanceCriteria: ["Aucun accès externe"]
  };
}

function scope(path) {
  return {
    allowedPaths: [path],
    allowedActions: ["test.existing"],
    allowedTools: ["node"],
    allowedDataClasses: ["test-evidence"],
    allowedNetworkEndpoints: [],
    publicationChannels: ["local-artifact"],
    resources: {
      maxWallClockSeconds: 120,
      maxCpuSeconds: 60,
      maxMemoryMb: 512,
      maxGpuMemoryMb: 0,
      maxStorageMb: 50,
      maxNetworkRequests: 0,
      maxPublications: 1
    }
  };
}

function caseRequest(reviewId, createdAt, path) {
  return {
    schema: CASE_AUTONOMY.requestSchema,
    requestId: reviewId,
    requestType: CASE_AUTONOMY.requestType,
    owner: { id: "the owner-owner", principalType: "HUMAN", role: "OWNER", level: "L7_OWNER" },
    subject: { id: "forge-orchestrator", principalType: "AI", role: "AI_ORCHESTRATOR", level: "L4_ISOLATED_EXECUTE" },
    case: {
      caseId: `case-${reviewId.slice(0, 8)}`,
      goal: "Tester le service de gouvernance.",
      successCriteria: ["Tests réussis"],
      stopCriteria: ["Incident critique"],
      ecosystemIds: ["digital-programming"],
      projectIds: ["aione-forge"]
    },
    requestedLevel: "L5_SCOPED_OPERATE",
    requestedScope: scope(path),
    permissionSets: [{
      permissionSetId: "owner-local-test",
      validation: "OWNER_VALIDATED_LOCAL",
      ownerId: "the owner-owner",
      scope: scope(path)
    }],
    createdAt,
    approvalWindowSeconds: 600,
    grantTtlSeconds: 600
  };
}

test("Owner review issues one persistent, bounded grant and rejects replay after reopening", () => {
  const runtimeRoot = mkdtempSync(join(testRuntimeRoot(), "aione-governance-service-"));
  const clockValue = { current: new Date("2026-07-30T13:00:00.000Z") };
  const clock = () => new Date(clockValue.current);
  try {
    const service = new GovernanceService({ root: ROOT, runtimeRoot, caseSecret: SECRET, clock });
    const proposed = service.propose({
      source: "OWNER",
      ecosystem: "digital-programming",
      title: "Mandat test",
      intent: "Valider le chemin complet sans réseau.",
      requestedOutcomes: ["Preuve"],
      priority: "P0",
      provenance: {
        verified: true,
        requestId: "governance-owner-request",
        payloadHash: "governance-owner-payload",
        principalIdHash: "governance-owner-principal",
        authMethod: "TEST_VERIFIED_OWNER",
        authEvidenceId: "governance-owner-evidence"
      }
    }).dossier;
    const ready = service.prepareReview(proposed.id, review(), {
      expectedRevision: proposed.revision,
      actor: { principalType: "AI", role: "AI_ORCHESTRATOR", principalId: "forge" }
    }).dossier;
    const decision = service.decideReview(ready.id, {
      decision: "VALIDATED",
      actor: service.ownerPrincipal(),
      reviewHash: ready.reviewHash,
      expectedRevision: ready.revision,
      confirmation: `VALIDATE:${ready.id}:${ready.reviewHash}`,
      caseRequest: caseRequest(ready.id, clock().toISOString(), join(runtimeRoot, "workspace"))
    });
    assert.equal(decision.review.dossier.state, "VALIDATED");
    assert.equal(decision.grant.claims.grantedLevel, "L5_SCOPED_OPERATE");
    assert.equal(decision.activation.status, "OWNER_VALIDATED_PRIORITY_QUEUED");
    assert.equal(decision.activation.task.value.priority, "P0");
    assert.match(readFileSync(service.paths.approvedBacklog, "utf8"), /P0 OWNER-VALIDATED/);

    const execution = {
      schema: CASE_AUTONOMY.executionSchema,
      caseId: decision.grant.claims.caseId,
      subject: { id: "forge-orchestrator", principalType: "AI", role: "AI_ORCHESTRATOR" },
      scope: scope(join(runtimeRoot, "workspace"))
    };
    const receipt = service.consumeGrant({ token: decision.grant.token, execution });
    assert.equal(receipt.decision, "ALLOW_ONCE");
    const reopened = new GovernanceService({ root: ROOT, runtimeRoot, caseSecret: SECRET, clock });
    assert.throws(
      () => reopened.consumeGrant({ token: decision.grant.token, execution }),
      (error) => error.code === "TOKEN_REPLAYED"
    );
    assert.equal(reopened.status().caseAutonomy.consumed, 1);
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});

test("review confirmation and refusal are exact and never issue a grant", () => {
  const runtimeRoot = mkdtempSync(join(testRuntimeRoot(), "aione-governance-refuse-"));
  try {
    const service = new GovernanceService({ root: ROOT, runtimeRoot, caseSecret: SECRET });
    const proposed = service.propose({
      source: "AI",
      ecosystem: "local-creation",
      title: "Proposition à refuser",
      intent: "Tester la décision terminale.",
      priority: "P1"
    }).dossier;
    const ready = service.prepareReview(proposed.id, review(), {
      expectedRevision: proposed.revision,
      actor: { principalType: "AI", role: "AI_AGENT", principalId: "agent" }
    }).dossier;
    assert.throws(
      () => service.decideReview(ready.id, {
        decision: "REFUSED",
        actor: service.ownerPrincipal(),
        reviewHash: ready.reviewHash,
        expectedRevision: ready.revision,
        confirmation: "REFUSE:wrong"
      }),
      (error) => error.code === "OWNER_CONFIRMATION_MISMATCH"
    );
    const refused = service.decideReview(ready.id, {
      decision: "REFUSED",
      actor: service.ownerPrincipal(),
      reviewHash: ready.reviewHash,
      expectedRevision: ready.revision,
      confirmation: `REFUSE:${ready.id}:${ready.reviewHash}`,
      reason: "Non prioritaire"
    });
    assert.equal(refused.review.dossier.state, "REFUSED");
    assert.equal(refused.grant, null);
    assert.equal(service.status().ownerReview.integrity.ok, true);
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});
