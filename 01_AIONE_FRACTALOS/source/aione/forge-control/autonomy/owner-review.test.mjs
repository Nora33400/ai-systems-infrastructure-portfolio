import assert from "node:assert/strict";
import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import {
  createOwnerReviewStore,
  humanOwnerPrincipal,
  OWNER_REVIEW_STATES
} from "./owner-review.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const OWNER_ID = "portfolio@example.invalid";

function fixture(options = {}) {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-owner-review-"));
  const clock = { value: new Date("2026-07-30T10:00:00.000Z") };
  const store = createOwnerReviewStore({
    runtimeRoot: root,
    ownerPrincipalId: OWNER_ID,
    now: () => new Date(clock.value),
    ...options
  });
  return {
    root,
    clock,
    store,
    cleanup: () => rmSync(root, { recursive: true, force: true })
  };
}

function proposal(source = "OWNER", suffix = "") {
  return {
    source,
    ecosystem: `programmation${suffix}`,
    title: `Renforcer le flux${suffix}`,
    intent: `Rendre les interactions robustes et vérifiables${suffix}`,
    requestedOutcomes: ["flux fluide", "preuve locale"],
    ...(source === "OWNER" ? {
      provenance: {
        verified: true,
        requestId: `request${suffix || "-default"}`,
        payloadHash: `payload-hash${suffix || "-default"}`,
        principalIdHash: "owner-principal-hash",
        authMethod: "TEST_VERIFIED_OWNER",
        authEvidenceId: `auth-evidence${suffix || "-default"}`
      }
    } : {})
  };
}

function review(overrides = {}) {
  return {
    reformulation: "Construire un flux borné, observable et réversible.",
    architecture: ["entrée typée", "permission broker", "ledger append-only"],
    risks: [{ risk: "action hors portée", mitigation: "refus par défaut" }],
    permissions: ["lecture locale", "écriture isolée"],
    tests: ["test nominal", "test refus", "test concurrence"],
    rollback: ["désactiver le mandat", "restaurer le snapshot"],
    channels: ["outbox locale Owner"],
    documentation: ["dossier de décision"],
    acceptanceCriteria: ["aucune action externe implicite"],
    ...overrides
  };
}

function expectCode(code, operation) {
  assert.throws(operation, (error) => error?.code === code);
}

test("un texte ne peut pas s'auto-déclarer Owner sans provenance vérifiée", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  expectCode("OWNER_PROVENANCE_REQUIRED", () => fx.store.propose({
    ...proposal("AI", "-spoof"),
    source: "OWNER",
    actor: { id: "the owner", role: "owner" }
  }));
});

test("cycle Owner complet, hashé et append-only", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const created = fx.store.propose(proposal()).dossier;
  assert.equal(created.state, "PROPOSED");
  assert.equal(created.priority, "OWNER_P0");
  assert.match(created.dossierHash, /^[a-f0-9]{64}$/);

  const ready = fx.store.restructure(created.id, review(), {
    expectedRevision: 1,
    actor: { principalId: "local-orchestrator" }
  }).dossier;
  assert.equal(ready.state, "REVIEW_READY");
  assert.equal(ready.revision, 3);
  assert.match(ready.reviewHash, /^[a-f0-9]{64}$/);

  const validated = fx.store.decide(created.id, {
    decision: "VALIDATED",
    actor: humanOwnerPrincipal(OWNER_ID),
    reviewHash: ready.reviewHash,
    expectedRevision: ready.revision
  }).dossier;
  assert.equal(validated.state, "VALIDATED");

  let current = validated;
  for (const state of ["EXECUTING", "VERIFYING", "CORRECTING", "EXECUTING", "VERIFYING", "PUBLISH_READY", "PUBLISHED"]) {
    current = fx.store.advance(created.id, state, {
      expectedRevision: current.revision,
      actor: { principalType: "AI", role: "ORCHESTRATOR", principalId: "forge" },
      evidence: { check: state }
    }).dossier;
  }
  assert.equal(current.state, "PUBLISHED");
  assert.deepEqual(OWNER_REVIEW_STATES.includes(current.state), true);
  const integrity = fx.store.verifyIntegrity();
  assert.equal(integrity.ok, true);
  assert.equal(integrity.dossiers, 1);
  assert.equal(integrity.ledgerEvents, current.revision);
});

test("seul le HUMAN OWNER principal décide, avec empreinte et idempotence", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const created = fx.store.propose(proposal()).dossier;
  const ready = fx.store.restructure(created.id, review(), { expectedRevision: 1 }).dossier;

  expectCode("OWNER_AUTHORITY_REQUIRED", () =>
    fx.store.decide(created.id, {
      decision: "VALIDATED",
      actor: { principalType: "AI", role: "OWNER", isPrimary: true, principalId: OWNER_ID },
      reviewHash: ready.reviewHash,
      expectedRevision: ready.revision
    })
  );
  expectCode("OWNER_AUTHORITY_REQUIRED", () =>
    fx.store.decide(created.id, {
      decision: "VALIDATED",
      actor: humanOwnerPrincipal("portfolio@example.invalid"),
      reviewHash: ready.reviewHash,
      expectedRevision: ready.revision
    })
  );
  expectCode("REVIEW_HASH_MISMATCH", () =>
    fx.store.decide(created.id, {
      decision: "VALIDATED",
      actor: humanOwnerPrincipal(OWNER_ID),
      reviewHash: "0".repeat(64),
      expectedRevision: ready.revision
    })
  );

  const first = fx.store.decide(created.id, {
    decision: "VALIDATED",
    actor: humanOwnerPrincipal(OWNER_ID),
    reviewHash: ready.reviewHash,
    expectedRevision: ready.revision
  });
  const repeated = fx.store.decide(created.id, {
    decision: "VALIDATED",
    actor: humanOwnerPrincipal(OWNER_ID),
    reviewHash: ready.reviewHash,
    expectedRevision: ready.revision
  });
  assert.equal(first.idempotent, false);
  assert.equal(repeated.idempotent, true);
  assert.equal(repeated.dossier.revision, first.dossier.revision);
  const executing = fx.store.advance(created.id, "EXECUTING", {
    expectedRevision: first.dossier.revision,
    actor: { principalType: "AI", role: "ORCHESTRATOR", principalId: "forge" }
  }).dossier;
  const delayedRetry = fx.store.decide(created.id, {
    decision: "VALIDATED",
    actor: humanOwnerPrincipal(OWNER_ID),
    reviewHash: ready.reviewHash,
    expectedRevision: ready.revision
  });
  assert.equal(delayedRetry.idempotent, true);
  assert.equal(delayedRetry.dossier.revision, executing.revision);
  expectCode("DECISION_CONFLICT", () =>
    fx.store.decide(created.id, {
      decision: "REFUSED",
      actor: humanOwnerPrincipal(OWNER_ID),
      reviewHash: ready.reviewHash,
      expectedRevision: ready.revision
    })
  );
});

test("déduplication, quota IA journalier, plafond actif et priorité Owner", (context) => {
  const fx = fixture({ dailyAiProposalLimit: 2, activeDossierLimit: 4 });
  context.after(fx.cleanup);
  const aiFirst = fx.store.propose(proposal("AI", "-a"));
  const duplicate = fx.store.propose(proposal("AI", "-a"));
  assert.equal(duplicate.idempotent, true);
  assert.equal(duplicate.dossier.id, aiFirst.dossier.id);
  fx.store.propose(proposal("AI", "-b"));
  expectCode("DAILY_AI_QUOTA_EXCEEDED", () => fx.store.propose(proposal("AI", "-c")));

  const owner = fx.store.propose(proposal("OWNER", "-owner")).dossier;
  assert.equal(fx.store.list()[0].id, owner.id);
  fx.store.propose(proposal("OWNER", "-owner-2"));
  expectCode("ACTIVE_QUOTA_EXCEEDED", () => fx.store.propose(proposal("OWNER", "-owner-3")));

  const digest = fx.store.getDigest();
  assert.equal(digest.active, 4);
  assert.equal(digest.ownerPriority, 2);
  assert.equal(digest.aiProposals, 2);
});

test("outbox locale en digest expurgé, sans secret ni bloc de code", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const created = fx.store.propose({
    source: "AI",
    ecosystem: "programmation",
    title: "Analyse `rm -rf`",
    intent: "token=supersecretvalue ```js\nconsole.log('code')\n``` Bearer abcdefghijklmnop"
  }).dossier;
  fx.store.restructure(
    created.id,
    review({
      reformulation: "Traiter api_key=abcdef123456 et `const secret = 1` sans les exposer."
    }),
    { expectedRevision: 1 }
  );
  const raw = readFileSync(fx.store.paths.outbox, "utf8");
  assert.doesNotMatch(raw, /supersecretvalue|console\.log|abcdefghijklmnop|abcdef123456|const secret/);
  assert.match(raw, /contentRedacted/);
  assert.match(raw, /registre local hashé/);
  assert.equal(fx.store.readOutbox().every((item) => !("review" in item)), true);
});

test("altération du ledger, concurrence et révision périmée sont refusées", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const created = fx.store.propose(proposal()).dossier;
  writeFileSync(fx.store.paths.lock, "occupied", "utf8");
  expectCode("CONCURRENT_WRITE", () => fx.store.propose(proposal("OWNER", "-other")));
  rmSync(fx.store.paths.lock);

  const ready = fx.store.restructure(created.id, review(), { expectedRevision: 1 }).dossier;
  expectCode("REVISION_CONFLICT", () =>
    fx.store.advance(created.id, "BLOCKED", { expectedRevision: 1 })
  );
  const lines = readFileSync(fx.store.paths.ledger, "utf8").trim().split(/\r?\n/);
  const first = JSON.parse(lines[0]);
  first.dossier.title = "ALTÉRÉ";
  lines[0] = JSON.stringify(first);
  writeFileSync(fx.store.paths.ledger, `${lines.join("\n")}\n`, "utf8");
  expectCode("INTEGRITY_ERROR", () => fx.store.get(ready.id));
});

test("refus est terminal et une proposition Owner n'est pas comptée dans le quota IA", (context) => {
  const fx = fixture({ dailyAiProposalLimit: 1 });
  context.after(fx.cleanup);
  fx.store.propose(proposal("AI", "-ai"));
  const created = fx.store.propose(proposal("OWNER", "-owner")).dossier;
  const ready = fx.store.restructure(created.id, review(), { expectedRevision: 1 }).dossier;
  const refused = fx.store.decide(created.id, {
    decision: "REFUSED",
    actor: humanOwnerPrincipal(OWNER_ID),
    reviewHash: ready.reviewHash,
    expectedRevision: ready.revision,
    reason: "Périmètre à revoir"
  }).dossier;
  assert.equal(refused.state, "REFUSED");
  expectCode("INVALID_TRANSITION", () =>
    fx.store.advance(created.id, "EXECUTING", { expectedRevision: refused.revision })
  );
});
