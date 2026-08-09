import {
  appendFileSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import {
  CASE_AUTONOMY,
  createCaseAutonomyDossier,
  createCaseAutonomyLedger,
  issueCaseAutonomyGrant,
  revokeCaseAutonomyGrant,
  verifyAndConsumeCaseAutonomyGrant
} from "./case-autonomy.mjs";
import { EcosystemGovernance } from "./ecosystem-governance.mjs";
import { createOwnerReviewStore, humanOwnerPrincipal } from "./owner-review.mjs";

export class GovernanceServiceError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = "GovernanceServiceError";
    this.code = code;
    this.status = status;
  }
}

function fail(code, message, status = 400) {
  throw new GovernanceServiceError(code, message, status);
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function sha256(value) {
  return createHash("sha256").update(typeof value === "string" ? value : stableJson(value)).digest("hex");
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function parseJsonLines(path) {
  if (!existsSync(path)) return [];
  const content = readFileSync(path, "utf8");
  if (!content.trim()) return [];
  return content.split(/\r?\n/).filter(Boolean).map((line, index) => {
    try {
      return JSON.parse(line);
    } catch {
      fail("GRANT_LEDGER_CORRUPT", `Journal de mandat invalide à la ligne ${index + 1}.`, 503);
    }
  });
}

function eventHash(event) {
  const body = { ...event };
  delete body.hash;
  return sha256(body);
}

function verifyEvents(events) {
  let previousHash = null;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (event.sequence !== index + 1 || event.previousHash !== previousHash || event.hash !== eventHash(event)) {
      fail("GRANT_LEDGER_CORRUPT", `Chaîne des mandats rompue à l'événement ${index + 1}.`, 503);
    }
    previousHash = event.hash;
  }
  return { ok: true, events: events.length, head: previousHash };
}

function tokenState(events, tokenHash) {
  const relevant = events.filter((event) => event.tokenHash === tokenHash);
  return {
    issued: relevant.some((event) => event.type === "GRANT_ISSUED"),
    claimed: relevant.some((event) => event.type === "GRANT_CONSUME_CLAIMED"),
    consumed: relevant.some((event) => event.type === "GRANT_CONSUMED"),
    revoked: relevant.some((event) => event.type === "GRANT_REVOKED"),
    rejected: relevant.some((event) => event.type === "GRANT_REJECTED"),
    events: relevant
  };
}

function safeGrantMetadata(value) {
  if (!value || typeof value !== "object") return {};
  const allowed = [
    "reviewId",
    "reviewHash",
    "tokenHash",
    "tokenId",
    "dossierHash",
    "caseId",
    "subjectId",
    "expiresAt",
    "decision",
    "reason",
    "errorCode"
  ];
  return Object.fromEntries(allowed.filter((key) => value[key] !== undefined).map((key) => [key, value[key]]));
}

function ownerConfirmation(decision, dossier) {
  return `${decision}:${dossier.id}:${dossier.reviewHash}`;
}

export class GovernanceService {
  constructor({
    root,
    runtimeRoot = "S:\\AI_LAB\\Runtime",
    ownerPolicyPath = join(root, "config", "owner-review-policy.json"),
    ecosystemDomainsPath = join(root, "config", "ecosystem-domains.json"),
    caseSecret,
    clock = () => new Date(),
    globalCapacity
  } = {}) {
    if (!root) fail("ROOT_REQUIRED", "La racine AIONE est requise.");
    if (!(typeof caseSecret === "string" || Buffer.isBuffer(caseSecret) || caseSecret instanceof Uint8Array)) {
      fail("CASE_SECRET_REQUIRED", "La clé locale des mandats est requise.", 503);
    }
    if (Buffer.from(caseSecret).byteLength < 32) {
      fail("CASE_SECRET_TOO_SHORT", "La clé locale des mandats doit contenir au moins 32 octets.", 503);
    }
    this.root = resolve(root);
    this.runtimeRoot = resolve(runtimeRoot);
    this.clock = clock;
    this.caseSecret = Buffer.from(caseSecret);
    this.ownerPolicy = readJson(resolve(ownerPolicyPath), null);
    if (!this.ownerPolicy?.owner?.id || !this.ownerPolicy?.owner?.reviewEmail) {
      fail("OWNER_POLICY_INVALID", "La politique Owner est absente ou invalide.", 503);
    }
    this.paths = Object.freeze({
      root: this.runtimeRoot,
      ownerReview: join(this.runtimeRoot, "OwnerReview"),
      caseAutonomy: join(this.runtimeRoot, "CaseAutonomy"),
      ecosystemGovernance: join(this.runtimeRoot, "EcosystemGovernance"),
      approvedBacklog: join(this.runtimeRoot, "OwnerReview", "approved-backlog.md"),
      grantLedger: join(this.runtimeRoot, "CaseAutonomy", "grant-events.jsonl"),
      grantLock: join(this.runtimeRoot, "CaseAutonomy", ".grant-events.lock")
    });
    [
      this.paths.root,
      this.paths.ownerReview,
      this.paths.caseAutonomy,
      this.paths.ecosystemGovernance
    ].forEach((path) => mkdirSync(path, { recursive: true }));
    this.ownerReviews = createOwnerReviewStore({
      runtimeRoot: this.paths.ownerReview,
      ownerPrincipalId: this.ownerPolicy.owner.reviewEmail,
      now: this.clock,
      dailyAiProposalLimit: Number(this.ownerPolicy.continuousAiProposals?.maximumNewProposalsPerDay || 12),
      activeDossierLimit: Number(this.ownerPolicy.continuousAiProposals?.maximumActiveReviewDossiers || 25)
    });
    this.caseLedger = createCaseAutonomyLedger();
    this.ecosystems = new EcosystemGovernance({
      configPath: resolve(ecosystemDomainsPath),
      storageDirectory: this.paths.ecosystemGovernance,
      clock: this.clock,
      ...(globalCapacity ? { globalCapacity } : {})
    });
    verifyEvents(parseJsonLines(this.paths.grantLedger));
    this.syncApprovedBacklog();
  }

  #withGrantLock(operation) {
    mkdirSync(dirname(this.paths.grantLock), { recursive: true });
    let descriptor;
    try {
      descriptor = openSync(this.paths.grantLock, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, acquiredAt: this.clock().toISOString() }));
    } catch (error) {
      if (error?.code === "EEXIST") fail("GRANT_LEDGER_BUSY", "Le journal des mandats est déjà utilisé.", 409);
      throw error;
    }
    try {
      return operation();
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(this.paths.grantLock)) unlinkSync(this.paths.grantLock);
    }
  }

  #appendGrantEvent(type, metadata) {
    return this.#withGrantLock(() => {
      const events = parseJsonLines(this.paths.grantLedger);
      verifyEvents(events);
      const event = {
        schema: "aione.case-autonomy-ledger-event.v1",
        sequence: events.length + 1,
        eventId: randomUUID(),
        at: this.clock().toISOString(),
        type,
        previousHash: events.at(-1)?.hash || null,
        ...safeGrantMetadata(metadata)
      };
      event.hash = eventHash(event);
      appendFileSync(this.paths.grantLedger, `${JSON.stringify(event)}\n`, "utf8");
      return event;
    });
  }

  #grantEvents() {
    const events = parseJsonLines(this.paths.grantLedger);
    verifyEvents(events);
    return events;
  }

  status() {
    const grantEvents = this.#grantEvents();
    return {
      schema: "aione.governance-service-status.v1",
      ok: true,
      ownerReview: {
        digest: this.ownerReviews.getDigest(),
        integrity: this.ownerReviews.verifyIntegrity()
      },
      caseAutonomy: {
        requestSchema: CASE_AUTONOMY.requestSchema,
        grantSchema: CASE_AUTONOMY.grantSchema,
        persistentLedger: verifyEvents(grantEvents),
        issued: grantEvents.filter((event) => event.type === "GRANT_ISSUED").length,
        consumed: grantEvents.filter((event) => event.type === "GRANT_CONSUMED").length,
        revoked: grantEvents.filter((event) => event.type === "GRANT_REVOKED").length
      },
      federation: {
        map: this.ecosystems.getFederationMap(),
        integrity: this.ecosystems.verifyIntegrity()
      }
    };
  }

  propose(input) {
    return this.ownerReviews.propose(input);
  }

  prepareReview(id, review, options) {
    return this.ownerReviews.restructure(id, review, options);
  }

  decideReview(id, {
    decision,
    actor,
    reviewHash,
    expectedRevision,
    confirmation,
    reason,
    caseRequest = null
  } = {}) {
    const dossier = this.ownerReviews.get(id);
    const normalizedDecision = String(decision || "").toUpperCase();
    if (!["VALIDATED", "REFUSED"].includes(normalizedDecision)) {
      fail("INVALID_DECISION", "La décision doit être VALIDATED ou REFUSED.");
    }
    const verb = normalizedDecision === "VALIDATED" ? "VALIDATE" : "REFUSE";
    if (confirmation !== ownerConfirmation(verb, dossier)) {
      fail("OWNER_CONFIRMATION_MISMATCH", "La confirmation locale ne correspond pas au dossier relu.", 403);
    }
    const result = this.ownerReviews.decide(id, {
      decision: normalizedDecision,
      actor,
      reviewHash,
      expectedRevision,
      reason
    });
    const activation = normalizedDecision === "VALIDATED"
      ? this.activateValidatedReview(id)
      : this.syncApprovedBacklog();
    if (normalizedDecision !== "VALIDATED" || !caseRequest) {
      return { review: result, grant: null, activation };
    }
    if (caseRequest.requestId !== id) {
      fail("GRANT_REVIEW_MISMATCH", "Le mandat doit utiliser l'identifiant du dossier Owner.");
    }
    const caseDossier = createCaseAutonomyDossier(caseRequest);
    const issued = issueCaseAutonomyGrant({
      dossier: caseDossier,
      secret: this.caseSecret,
      now: this.clock()
    });
    const tokenHash = sha256(issued.token);
    this.#appendGrantEvent("GRANT_ISSUED", {
      reviewId: id,
      reviewHash: dossier.reviewHash,
      tokenHash,
      tokenId: issued.claims.tokenId,
      dossierHash: issued.claims.dossierHash,
      caseId: issued.claims.caseId,
      subjectId: issued.claims.subject.id,
      expiresAt: issued.claims.expiresAt,
      decision: "ISSUED"
    });
    return {
      review: result,
      grant: {
        token: issued.token,
        claims: issued.claims,
        reviewId: id,
        reviewHash: dossier.reviewHash
      },
      activation
    };
  }

  activateValidatedReview(id) {
    const dossier = this.ownerReviews.get(id);
    if (!["VALIDATED", "EXECUTING", "VERIFYING", "CORRECTING", "PUBLISH_READY", "PUBLISHED"].includes(dossier.state)) {
      fail("OWNER_VALIDATION_REQUIRED", "Le dossier doit être validé avant sa mise en file.", 409);
    }
    const projectId = `owner-approved:${dossier.id}`;
    const project = this.ecosystems.upsertProject(dossier.ecosystem, {
      id: projectId,
      name: dossier.title,
      status: dossier.state === "PUBLISHED" ? "PUBLISHED" : "ACTIVE",
      objective: dossier.review?.reformulation || dossier.intent,
      ownerPrincipalId: "human-owner:the owner",
      updatedAt: dossier.updatedAt,
      metadata: {
        ownerReviewId: dossier.id,
        reviewHash: dossier.reviewHash,
        source: dossier.source
      }
    });
    const task = this.ecosystems.enqueueTask(dossier.ecosystem, {
      id: `owner-p0:${dossier.id}`,
      projectId,
      title: dossier.title,
      priority: "P0",
      workflowId: null
    });
    const backlog = this.syncApprovedBacklog();
    return {
      status: "OWNER_VALIDATED_PRIORITY_QUEUED",
      project,
      task,
      backlog
    };
  }

  syncApprovedBacklog() {
    const activeStates = new Set(["VALIDATED", "EXECUTING", "VERIFYING", "CORRECTING", "PUBLISH_READY"]);
    const dossiers = this.ownerReviews.list().filter((item) => activeStates.has(item.state));
    const lines = [
      "# Backlog P0 validé par l’Owner",
      "",
      "Source canonique: registre local Owner Review hashé.",
      "Les agents peuvent analyser, concevoir, coder en espace isolé, documenter, tester, corriger et vérifier.",
      "La promotion canonique et la publication restent limitées aux permissions et canaux validés.",
      "",
      ...dossiers.flatMap((dossier) => [
        `- P0 OWNER-VALIDATED-${dossier.id} — ${dossier.title} — ${dossier.review?.reformulation || dossier.intent}`,
        `  - Écosystème: ${dossier.ecosystem}`,
        `  - État: ${dossier.state}`,
        `  - Empreinte de revue: ${dossier.reviewHash}`,
        `  - Tests: ${(dossier.review?.tests || []).join("; ") || "preuves locales obligatoires"}`,
        `  - Acceptation: ${(dossier.review?.acceptanceCriteria || []).join("; ") || "aucune extension silencieuse"}`,
        ""
      ])
    ];
    const temporary = `${this.paths.approvedBacklog}.${process.pid}.${Date.now()}.tmp`;
    const content = `${lines.join("\n").trim()}\n`;
    writeFileSync(temporary, content, "utf8");
    if (existsSync(this.paths.approvedBacklog)) {
      writeFileSync(this.paths.approvedBacklog, content, "utf8");
      unlinkSync(temporary);
    } else {
      renameSync(temporary, this.paths.approvedBacklog);
    }
    return {
      path: this.paths.approvedBacklog,
      activeValidatedProjects: dossiers.length,
      sha256: sha256(lines.join("\n"))
    };
  }

  consumeGrant({ token, execution } = {}) {
    const tokenHash = sha256(String(token || ""));
    const before = tokenState(this.#grantEvents(), tokenHash);
    if (!before.issued) fail("UNKNOWN_GRANT", "Le mandat n'a pas été émis par ce service.", 403);
    if (before.revoked) fail("TOKEN_REVOKED", "Le mandat a été révoqué.", 403);
    if (before.claimed || before.consumed) fail("TOKEN_REPLAYED", "Le mandat a déjà été réclamé.", 409);
    this.#appendGrantEvent("GRANT_CONSUME_CLAIMED", { tokenHash, decision: "CLAIMED" });
    try {
      const receipt = verifyAndConsumeCaseAutonomyGrant({
        token,
        secret: this.caseSecret,
        ledger: this.caseLedger,
        execution,
        now: this.clock()
      });
      this.#appendGrantEvent("GRANT_CONSUMED", {
        tokenHash,
        tokenId: receipt.tokenId,
        dossierHash: receipt.dossierHash,
        caseId: receipt.caseId,
        subjectId: receipt.subjectId,
        decision: receipt.decision
      });
      return receipt;
    } catch (error) {
      this.#appendGrantEvent("GRANT_REJECTED", {
        tokenHash,
        decision: "DENY",
        errorCode: error?.code || "GRANT_VERIFICATION_FAILED"
      });
      throw error;
    }
  }

  revokeGrant({ token, reason } = {}) {
    const tokenHash = sha256(String(token || ""));
    const current = tokenState(this.#grantEvents(), tokenHash);
    if (!current.issued) fail("UNKNOWN_GRANT", "Le mandat n'a pas été émis par ce service.", 403);
    if (current.revoked) return { revoked: true, idempotent: true };
    const result = revokeCaseAutonomyGrant({
      token,
      secret: this.caseSecret,
      ledger: this.caseLedger,
      reason,
      now: this.clock()
    });
    this.#appendGrantEvent("GRANT_REVOKED", {
      tokenHash,
      tokenId: result.tokenId,
      reason: result.reason,
      decision: "REVOKED"
    });
    return { ...result, idempotent: false };
  }

  ownerPrincipal() {
    return humanOwnerPrincipal(this.ownerPolicy.owner.reviewEmail);
  }
}
