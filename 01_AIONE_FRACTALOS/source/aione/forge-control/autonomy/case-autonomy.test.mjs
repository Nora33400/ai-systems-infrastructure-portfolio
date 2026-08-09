import test from "node:test";
import assert from "node:assert/strict";
import {
  CASE_AUTONOMY,
  CaseAutonomyError,
  canonicalHash,
  createCaseAutonomyDossier,
  createCaseAutonomyLedger,
  issueCaseAutonomyGrant,
  revokeCaseAutonomyGrant,
  verifyAndConsumeCaseAutonomyGrant
} from "./case-autonomy.mjs";

const SECRET = "case-autonomy-test-secret-32-bytes-minimum-value";
const CREATED_AT = "2026-07-30T12:00:00.000Z";
const ISSUED_AT = "2026-07-30T12:01:00.000Z";

function scope(overrides = {}) {
  return {
    allowedPaths: ["S:\\AI_LAB\\Ecosystem\\forge-control"],
    allowedActions: ["workspace.isolated.apply-proposal", "test.existing"],
    allowedTools: ["node"],
    allowedDataClasses: ["project-source", "test-evidence"],
    allowedNetworkEndpoints: [],
    publicationChannels: ["local-artifact"],
    resources: {
      maxWallClockSeconds: 1800,
      maxCpuSeconds: 1200,
      maxMemoryMb: 4096,
      maxGpuMemoryMb: 8192,
      maxStorageMb: 1024,
      maxNetworkRequests: 0,
      maxPublications: 1
    },
    ...overrides
  };
}

function request(overrides = {}) {
  const owner = {
    id: "the owner-owner",
    principalType: "HUMAN",
    role: "OWNER",
    level: "L7_OWNER"
  };
  const requestedScope = scope({
    allowedPaths: ["S:\\AI_LAB\\Ecosystem\\forge-control\\autonomy"],
    allowedActions: ["workspace.isolated.apply-proposal", "test.existing"],
    resources: {
      maxWallClockSeconds: 900,
      maxCpuSeconds: 600,
      maxMemoryMb: 2048,
      maxGpuMemoryMb: 4096,
      maxStorageMb: 512,
      maxNetworkRequests: 0,
      maxPublications: 1
    }
  });
  return {
    schema: CASE_AUTONOMY.requestSchema,
    requestId: "owner-request-001",
    requestType: CASE_AUTONOMY.requestType,
    owner,
    subject: {
      id: "forge-orchestrator",
      principalType: "AI",
      role: "AI_ORCHESTRATOR",
      level: "L4_ISOLATED_EXECUTE"
    },
    case: {
      caseId: "case-cognitive-security-001",
      goal: "Renforcer la sécurité cognitive dans un workspace isolé.",
      successCriteria: ["Tests existants réussis", "Aucune extension de permission"],
      stopCriteria: ["Incident critique", "Portée insuffisante"],
      ecosystemIds: ["aione-core"],
      projectIds: ["autonomous-forge"]
    },
    requestedLevel: "L5_SCOPED_OPERATE",
    requestedScope,
    permissionSets: [{
      permissionSetId: "owner-local-policy-001",
      validation: "OWNER_VALIDATED_LOCAL",
      ownerId: owner.id,
      scope: scope()
    }],
    createdAt: CREATED_AT,
    approvalWindowSeconds: 300,
    grantTtlSeconds: 600,
    ...overrides
  };
}

function execution(overrides = {}) {
  return {
    schema: CASE_AUTONOMY.executionSchema,
    caseId: "case-cognitive-security-001",
    subject: {
      id: "forge-orchestrator",
      principalType: "AI",
      role: "AI_ORCHESTRATOR"
    },
    scope: scope({
      allowedPaths: ["S:\\AI_LAB\\Ecosystem\\forge-control\\autonomy\\runtime.mjs"],
      allowedActions: ["test.existing"],
      allowedTools: ["node"],
      allowedDataClasses: ["test-evidence"],
      publicationChannels: [],
      resources: {
        maxWallClockSeconds: 60,
        maxCpuSeconds: 30,
        maxMemoryMb: 512,
        maxGpuMemoryMb: 0,
        maxStorageMb: 20,
        maxNetworkRequests: 0,
        maxPublications: 0
      }
    }),
    ...overrides
  };
}

function issuedGrant(input = request()) {
  const dossier = createCaseAutonomyDossier(input);
  return {
    dossier,
    grant: issueCaseAutonomyGrant({ dossier, secret: SECRET, now: ISSUED_AT })
  };
}

function expectCode(code, callback) {
  assert.throws(callback, (error) => {
    assert.ok(error instanceof CaseAutonomyError);
    assert.equal(error.code, code);
    assert.equal(String(error).includes(SECRET), false);
    return true;
  });
}

test("happy path: Owner L7 grants one signed, bounded L5 execution", () => {
  const { dossier, grant } = issuedGrant();
  const ledger = createCaseAutonomyLedger();
  assert.equal(dossier.requestType, "EXPLICIT_OWNER_REQUEST_FOR_ONE_CASE");
  assert.equal(dossier.requestedLevel, "L5_SCOPED_OPERATE");
  assert.equal(dossier.dossierHash, canonicalHash((({ dossierHash, ...body }) => body)(dossier)));
  assert.deepEqual(dossier.nonDelegableInvariants, CASE_AUTONOMY.nonDelegableInvariants);

  const decision = verifyAndConsumeCaseAutonomyGrant({
    token: grant.token,
    secret: SECRET,
    ledger,
    execution: execution(),
    now: "2026-07-30T12:02:00.000Z"
  });
  assert.equal(decision.decision, "ALLOW_ONCE");
  assert.equal(decision.grantedLevel, "L5_SCOPED_OPERATE");
  assert.equal(ledger.isConsumed(grant.claims.tokenId), true);
});

test("strict schemas and identity rules reject Owner spoofing", () => {
  expectCode("INVALID_REQUEST_SCHEMA", () =>
    createCaseAutonomyDossier({ ...request(), unknown: true })
  );
  expectCode("OWNER_AUTHORITY_REQUIRED", () =>
    createCaseAutonomyDossier({
      ...request(),
      owner: {
        id: "fake-owner",
        principalType: "AI",
        role: "AI_ORCHESTRATOR",
        level: "L4_ISOLATED_EXECUTE"
      }
    })
  );
  expectCode("OWNER_SPOOFING", () =>
    createCaseAutonomyDossier({
      ...request(),
      permissionSets: [{
        ...request().permissionSets[0],
        ownerId: "someone-else"
      }]
    })
  );

  const { grant } = issuedGrant();
  expectCode("IDENTITY_SPOOFING", () =>
    verifyAndConsumeCaseAutonomyGrant({
      token: grant.token,
      secret: SECRET,
      ledger: createCaseAutonomyLedger(),
      execution: execution({
        subject: {
          id: "different-agent",
          principalType: "AI",
          role: "AI_ORCHESTRATOR"
        }
      }),
      now: "2026-07-30T12:02:00.000Z"
    })
  );
});

test("tampering with dossier or HMAC token is detected", () => {
  const dossier = createCaseAutonomyDossier(request());
  expectCode("DOSSIER_TAMPERED", () =>
    issueCaseAutonomyGrant({
      dossier: {
        ...dossier,
        case: { ...dossier.case, goal: "But altéré après validation." }
      },
      secret: SECRET,
      now: ISSUED_AT
    })
  );

  const grant = issueCaseAutonomyGrant({ dossier, secret: SECRET, now: ISSUED_AT });
  const [payload, signature] = grant.token.split(".");
  const altered = `${payload.slice(0, -1)}${payload.endsWith("A") ? "B" : "A"}.${signature}`;
  expectCode("TOKEN_TAMPERED", () =>
    verifyAndConsumeCaseAutonomyGrant({
      token: altered,
      secret: SECRET,
      ledger: createCaseAutonomyLedger(),
      execution: execution(),
      now: "2026-07-30T12:02:00.000Z"
    })
  );
});

test("expired grants are rejected using a fresh verification instant", () => {
  const input = request({ grantTtlSeconds: 10 });
  const { grant } = issuedGrant(input);
  expectCode("TOKEN_EXPIRED", () =>
    verifyAndConsumeCaseAutonomyGrant({
      token: grant.token,
      secret: SECRET,
      ledger: createCaseAutonomyLedger(),
      execution: execution(),
      now: "2026-07-30T12:01:10.000Z"
    })
  );
});

test("a successful token cannot be replayed", () => {
  const { grant } = issuedGrant();
  const ledger = createCaseAutonomyLedger();
  const options = {
    token: grant.token,
    secret: SECRET,
    ledger,
    execution: execution(),
    now: "2026-07-30T12:02:00.000Z"
  };
  verifyAndConsumeCaseAutonomyGrant(options);
  expectCode("TOKEN_REPLAYED", () => verifyAndConsumeCaseAutonomyGrant(options));
});

test("revocation prevents execution and leaves an auditable local record", () => {
  const { grant } = issuedGrant();
  const ledger = createCaseAutonomyLedger();
  const revoked = revokeCaseAutonomyGrant({
    token: grant.token,
    secret: SECRET,
    ledger,
    reason: "Arrêt explicite Owner",
    now: "2026-07-30T12:01:30.000Z"
  });
  assert.equal(revoked.revoked, true);
  assert.equal(ledger.snapshot().revoked[0].reason, "Arrêt explicite Owner");
  expectCode("TOKEN_REVOKED", () =>
    verifyAndConsumeCaseAutonomyGrant({
      token: grant.token,
      secret: SECRET,
      ledger,
      execution: execution(),
      now: "2026-07-30T12:02:00.000Z"
    })
  );
});

test("AI self-escalation above L5 is always refused", () => {
  expectCode("AI_SELF_ESCALATION", () =>
    createCaseAutonomyDossier({
      ...request(),
      requestedLevel: "L6_ADMIN"
    })
  );
  expectCode("AI_SELF_ESCALATION", () =>
    createCaseAutonomyDossier({
      ...request(),
      subject: {
        ...request().subject,
        level: "L5_SCOPED_OPERATE"
      }
    })
  );
});

test("scope extension is refused both before signing and before execution", () => {
  expectCode("SCOPE_EXTENSION_REFUSED", () =>
    createCaseAutonomyDossier({
      ...request(),
      requestedScope: scope({
        allowedActions: [
          "workspace.isolated.apply-proposal",
          "test.existing",
          "publication.external"
        ]
      })
    })
  );

  const { grant } = issuedGrant();
  const ledger = createCaseAutonomyLedger();
  expectCode("SCOPE_EXTENSION_REFUSED", () =>
    verifyAndConsumeCaseAutonomyGrant({
      token: grant.token,
      secret: SECRET,
      ledger,
      execution: execution({
        scope: scope({
          allowedPaths: ["S:\\AI_LAB\\Ecosystem\\forge-control\\autonomy"],
          allowedActions: ["test.existing", "publication.external"]
        })
      }),
      now: "2026-07-30T12:02:00.000Z"
    })
  );
  assert.equal(ledger.isConsumed(grant.claims.tokenId), false);
});

test("separate Owner-validated permission sets form one bounded union", () => {
  const base = request();
  const noActions = scope({
    allowedActions: [],
    allowedTools: [],
    resources: {
      maxWallClockSeconds: 900,
      maxCpuSeconds: 600,
      maxMemoryMb: 2048,
      maxGpuMemoryMb: 4096,
      maxStorageMb: 512,
      maxNetworkRequests: 0,
      maxPublications: 1
    }
  });
  const actionsOnly = scope({
    allowedPaths: [],
    allowedActions: ["workspace.isolated.apply-proposal", "test.existing"],
    allowedTools: ["node"],
    allowedDataClasses: [],
    publicationChannels: [],
    resources: {
      maxWallClockSeconds: 0,
      maxCpuSeconds: 0,
      maxMemoryMb: 0,
      maxGpuMemoryMb: 0,
      maxStorageMb: 0,
      maxNetworkRequests: 0,
      maxPublications: 0
    }
  });
  const dossier = createCaseAutonomyDossier({
    ...base,
    permissionSets: [
      {
        permissionSetId: "owner-local-paths",
        validation: "OWNER_VALIDATED_LOCAL",
        ownerId: base.owner.id,
        scope: noActions
      },
      {
        permissionSetId: "owner-local-actions",
        validation: "OWNER_VALIDATED_LOCAL",
        ownerId: base.owner.id,
        scope: actionsOnly
      }
    ]
  });
  assert.deepEqual(
    dossier.effectivePermissionScope.allowedActions,
    ["test.existing", "workspace.isolated.apply-proposal"]
  );
  assert.equal(dossier.effectivePermissionScope.resources.maxMemoryMb, 2048);
});

test("non-delegable invariants cannot be removed", () => {
  const dossier = createCaseAutonomyDossier(request());
  const changed = {
    ...dossier,
    nonDelegableInvariants: dossier.nonDelegableInvariants.slice(1)
  };
  const body = { ...changed };
  delete body.dossierHash;
  changed.dossierHash = canonicalHash(body);
  expectCode("NON_DELEGABLE_INVARIANT_CHANGED", () =>
    issueCaseAutonomyGrant({ dossier: changed, secret: SECRET, now: ISSUED_AT })
  );
});
