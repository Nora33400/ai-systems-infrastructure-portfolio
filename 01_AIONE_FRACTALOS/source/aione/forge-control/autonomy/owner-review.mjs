import {
  appendFileSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { dirname, resolve } from "node:path";

export const OWNER_REVIEW_STATES = Object.freeze([
  "PROPOSED",
  "RESTRUCTURING",
  "REVIEW_READY",
  "VALIDATED",
  "REFUSED",
  "EXECUTING",
  "VERIFYING",
  "CORRECTING",
  "PUBLISH_READY",
  "PUBLISHED",
  "BLOCKED"
]);

const TERMINAL_STATES = new Set(["REFUSED", "PUBLISHED", "BLOCKED"]);
const ACTIVE_STATES = new Set(OWNER_REVIEW_STATES.filter((state) => !TERMINAL_STATES.has(state)));
const TRANSITIONS = Object.freeze({
  PROPOSED: new Set(["RESTRUCTURING", "BLOCKED"]),
  RESTRUCTURING: new Set(["REVIEW_READY", "BLOCKED"]),
  REVIEW_READY: new Set(["BLOCKED"]),
  VALIDATED: new Set(["EXECUTING", "BLOCKED"]),
  REFUSED: new Set(),
  EXECUTING: new Set(["VERIFYING", "BLOCKED"]),
  VERIFYING: new Set(["CORRECTING", "PUBLISH_READY", "BLOCKED"]),
  CORRECTING: new Set(["EXECUTING", "VERIFYING", "BLOCKED"]),
  PUBLISH_READY: new Set(["PUBLISHED", "CORRECTING", "BLOCKED"]),
  PUBLISHED: new Set(),
  BLOCKED: new Set()
});

const REQUIRED_REVIEW_FIELDS = Object.freeze([
  "reformulation",
  "architecture",
  "risks",
  "permissions",
  "tests",
  "rollback",
  "channels"
]);

function fail(code, message, details = undefined) {
  const error = new Error(message);
  error.code = code;
  if (details !== undefined) error.details = details;
  throw error;
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function hash(value) {
  return createHash("sha256").update(typeof value === "string" ? value : canonical(value)).digest("hex");
}

function plainClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function cleanText(value, field, { max = 8_000 } = {}) {
  if (typeof value !== "string" || !value.trim()) fail("INVALID_INPUT", `${field} doit être un texte non vide`);
  const text = value.replace(/\r\n/g, "\n").trim();
  if (text.length > max) fail("INVALID_INPUT", `${field} dépasse ${max} caractères`);
  return text;
}

function cleanShortText(value, field, max = 240) {
  return cleanText(value, field, { max });
}

function cleanStringArray(value, field, { min = 1, maxItems = 100 } = {}) {
  if (!Array.isArray(value) || value.length < min || value.length > maxItems) {
    fail("INVALID_INPUT", `${field} doit contenir entre ${min} et ${maxItems} éléments`);
  }
  return value.map((item, index) => cleanText(item, `${field}[${index}]`, { max: 2_000 }));
}

function normalizeRisk(value, index) {
  if (typeof value === "string") {
    return { risk: cleanText(value, `risks[${index}]`), mitigation: "À préciser avant validation" };
  }
  if (!value || typeof value !== "object") fail("INVALID_INPUT", `risks[${index}] est invalide`);
  return {
    risk: cleanText(value.risk, `risks[${index}].risk`, { max: 2_000 }),
    mitigation: cleanText(value.mitigation, `risks[${index}].mitigation`, { max: 2_000 })
  };
}

function normalizeReview(review) {
  if (!review || typeof review !== "object" || Array.isArray(review)) {
    fail("INVALID_INPUT", "Le dossier de revue doit être un objet");
  }
  for (const field of REQUIRED_REVIEW_FIELDS) {
    if (!(field in review)) fail("INVALID_INPUT", `Champ de revue manquant: ${field}`);
  }
  if (!Array.isArray(review.risks) || review.risks.length === 0) {
    fail("INVALID_INPUT", "risks doit contenir au moins un risque");
  }
  return {
    reformulation: cleanText(review.reformulation, "reformulation"),
    architecture: cleanStringArray(review.architecture, "architecture"),
    risks: review.risks.map(normalizeRisk),
    permissions: cleanStringArray(review.permissions, "permissions"),
    tests: cleanStringArray(review.tests, "tests"),
    rollback: Array.isArray(review.rollback)
      ? cleanStringArray(review.rollback, "rollback")
      : [cleanText(review.rollback, "rollback")],
    channels: cleanStringArray(review.channels, "channels"),
    documentation: review.documentation
      ? cleanStringArray(review.documentation, "documentation")
      : [],
    acceptanceCriteria: review.acceptanceCriteria
      ? cleanStringArray(review.acceptanceCriteria, "acceptanceCriteria")
      : []
  };
}

function normalizeSource(source) {
  const value = String(source || "").toUpperCase();
  if (!["OWNER", "AI"].includes(value)) fail("INVALID_INPUT", "source doit valoir OWNER ou AI");
  return value;
}

function normalizeProposal(input) {
  if (!input || typeof input !== "object") fail("INVALID_INPUT", "Proposition manquante");
  const source = normalizeSource(input.source);
  if (source === "OWNER" && input?.provenance?.verified !== true) {
    fail("OWNER_PROVENANCE_REQUIRED", "Une proposition Owner exige une provenance vérifiée par la frontière d'entrée.");
  }
  const ownerProvenance = source === "OWNER" ? {
    verified: input?.provenance?.verified === true,
    requestId: cleanShortText(input?.provenance?.requestId, "provenance.requestId", 160),
    payloadHash: cleanShortText(input?.provenance?.payloadHash, "provenance.payloadHash", 160),
    principalIdHash: cleanShortText(input?.provenance?.principalIdHash, "provenance.principalIdHash", 160),
    authMethod: cleanShortText(input?.provenance?.authMethod, "provenance.authMethod", 120),
    authEvidenceId: cleanShortText(input?.provenance?.authEvidenceId, "provenance.authEvidenceId", 160)
  } : null;
  return {
    source,
    ecosystem: cleanShortText(input.ecosystem || "general", "ecosystem", 120),
    title: cleanShortText(input.title, "title", 240),
    intent: cleanText(input.intent, "intent", { max: 8_000 }),
    requestedOutcomes: input.requestedOutcomes
      ? cleanStringArray(input.requestedOutcomes, "requestedOutcomes")
      : [],
    priority: source === "OWNER" ? "OWNER_P0" : cleanShortText(input.priority || "NORMAL", "priority", 40),
    provenance: ownerProvenance
  };
}

function proposalFingerprint(proposal) {
  const comparable = {
    ecosystem: proposal.ecosystem.toLocaleLowerCase("fr-FR").replace(/\s+/g, " ").trim(),
    title: proposal.title.toLocaleLowerCase("fr-FR").replace(/\s+/g, " ").trim(),
    intent: proposal.intent.toLocaleLowerCase("fr-FR").replace(/\s+/g, " ").trim()
  };
  return hash(comparable);
}

function dossierHash(dossier) {
  const copy = plainClone(dossier);
  delete copy.dossierHash;
  return hash(copy);
}

function eventHash(event) {
  const copy = plainClone(event);
  delete copy.eventHash;
  return hash(copy);
}

function parseJsonLines(path) {
  if (!existsSync(path)) return [];
  const text = readFileSync(path, "utf8");
  if (!text.trim()) return [];
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch {
        fail("INTEGRITY_ERROR", `JSONL invalide dans ${path}, ligne ${index + 1}`);
      }
    });
}

function verifyHashChain(events, kind) {
  let previous = null;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (event.previousEventHash !== previous) {
      fail("INTEGRITY_ERROR", `${kind}: chaîne rompue à la ligne ${index + 1}`);
    }
    if (eventHash(event) !== event.eventHash) {
      fail("INTEGRITY_ERROR", `${kind}: empreinte invalide à la ligne ${index + 1}`);
    }
    previous = event.eventHash;
  }
  return { ok: true, count: events.length, head: previous };
}

function rebuild(events) {
  const dossiers = new Map();
  for (const event of events) {
    const dossier = event.dossier;
    if (!dossier || dossierHash(dossier) !== dossier.dossierHash) {
      fail("INTEGRITY_ERROR", `Dossier altéré dans l'événement ${event.eventId || "inconnu"}`);
    }
    const before = dossiers.get(dossier.id);
    if (before && dossier.revision !== before.revision + 1) {
      fail("INTEGRITY_ERROR", `Révision non séquentielle pour ${dossier.id}`);
    }
    if (!before && dossier.revision !== 1) {
      fail("INTEGRITY_ERROR", `Première révision invalide pour ${dossier.id}`);
    }
    dossiers.set(dossier.id, dossier);
  }
  return dossiers;
}

function redactForOutbox(value) {
  let text = String(value ?? "");
  text = text.replace(/```[\s\S]*?```/g, "[CODE_REDACTED]");
  text = text.replace(/`[^`\n]+`/g, "[CODE_REDACTED]");
  text = text.replace(/\b(?:sk|pk|api)[-_][A-Za-z0-9_-]{8,}\b/gi, "[SECRET_REDACTED]");
  text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b/gi, "Bearer [SECRET_REDACTED]");
  text = text.replace(
    /\b(password|passwd|secret|token|api[_ -]?key|private[_ -]?key)\b\s*[:=]\s*[^\s,;]+/gi,
    "$1=[SECRET_REDACTED]"
  );
  return text.replace(/\s+/g, " ").trim().slice(0, 500);
}

function utcDay(isoString) {
  return isoString.slice(0, 10);
}

function assertExpectedRevision(dossier, expectedRevision) {
  if (!Number.isInteger(expectedRevision)) {
    fail("EXPECTED_REVISION_REQUIRED", "expectedRevision entier est obligatoire");
  }
  if (dossier.revision !== expectedRevision) {
    fail("REVISION_CONFLICT", `Révision attendue ${expectedRevision}, actuelle ${dossier.revision}`);
  }
}

function assertHumanOwner(actor, ownerPrincipalId) {
  const principalType = String(actor?.principalType || actor?.kind || actor?.type || "").toUpperCase();
  const role = String(actor?.role || "").toUpperCase();
  if (
    principalType !== "HUMAN" ||
    role !== "OWNER" ||
    actor?.isPrimary !== true ||
    actor?.principalId !== ownerPrincipalId
  ) {
    fail("OWNER_AUTHORITY_REQUIRED", "Seul le principal HUMAN OWNER principal peut décider");
  }
}

function assertDecision(decision) {
  const value = String(decision || "").toUpperCase();
  if (!["VALIDATED", "REFUSED"].includes(value)) {
    fail("INVALID_DECISION", "decision doit valoir VALIDATED ou REFUSED");
  }
  return value;
}

function defaultRuntimeRoot() {
  return "S:\\AI_LAB\\Runtime\\OwnerReview";
}

/**
 * Registre local append-only des dossiers Owner.
 *
 * Aucune méthode n'envoie de donnée sur le réseau. `outbox.jsonl` est une file
 * locale expurgée qu'un autre composant devra présenter au propriétaire.
 */
export function createOwnerReviewStore({
  runtimeRoot,
  ownerPrincipalId = "portfolio@example.invalid",
  now = () => new Date(),
  dailyAiProposalLimit = 12,
  activeDossierLimit = 25
} = {}) {
  const rootWasInjected = runtimeRoot !== undefined;
  const root = resolve(runtimeRoot || defaultRuntimeRoot());
  if (!rootWasInjected && !/^S:\\/i.test(root)) {
    fail("LOCAL_S_STORAGE_REQUIRED", `Le stockage par défaut doit rester sur S: ${root}`);
  }
  if (!Number.isInteger(dailyAiProposalLimit) || dailyAiProposalLimit < 1) {
    fail("INVALID_CONFIG", "dailyAiProposalLimit doit être un entier positif");
  }
  if (!Number.isInteger(activeDossierLimit) || activeDossierLimit < 1) {
    fail("INVALID_CONFIG", "activeDossierLimit doit être un entier positif");
  }

  const paths = Object.freeze({
    root,
    ledger: resolve(root, "owner-review-ledger.jsonl"),
    outbox: resolve(root, "owner-review-outbox.jsonl"),
    lock: resolve(root, ".owner-review.lock")
  });
  mkdirSync(root, { recursive: true });

  function withWriteLock(operation) {
    let descriptor;
    try {
      descriptor = openSync(paths.lock, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, acquiredAt: new Date().toISOString() }));
    } catch (error) {
      if (error?.code === "EEXIST") fail("CONCURRENT_WRITE", "Une autre écriture Owner est en cours");
      throw error;
    }
    try {
      return operation();
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(paths.lock)) unlinkSync(paths.lock);
    }
  }

  function loadVerified() {
    const events = parseJsonLines(paths.ledger);
    const chain = verifyHashChain(events, "owner-review-ledger");
    return { events, dossiers: rebuild(events), chain };
  }

  function appendOutbox(payload, timestamp) {
    const outbox = parseJsonLines(paths.outbox);
    verifyHashChain(outbox, "owner-review-outbox");
    const event = {
      eventId: randomUUID(),
      timestamp,
      previousEventHash: outbox.at(-1)?.eventHash || null,
      ...payload
    };
    event.eventHash = eventHash(event);
    appendFileSync(paths.outbox, `${JSON.stringify(event)}\n`, "utf8");
    return event;
  }

  function appendDossierEvent(events, action, dossier, timestamp, metadata = {}) {
    const event = {
      eventId: randomUUID(),
      timestamp,
      action,
      previousEventHash: events.at(-1)?.eventHash || null,
      dossier,
      metadata: plainClone(metadata)
    };
    event.eventHash = eventHash(event);
    appendFileSync(paths.ledger, `${JSON.stringify(event)}\n`, "utf8");
    return event;
  }

  function nextDossier(current, state, timestamp, changes = {}) {
    const dossier = {
      ...plainClone(current),
      ...plainClone(changes),
      state,
      revision: current.revision + 1,
      updatedAt: timestamp
    };
    dossier.dossierHash = dossierHash(dossier);
    return dossier;
  }

  function propose(input) {
    return withWriteLock(() => {
      const timestamp = now().toISOString();
      const proposal = normalizeProposal(input);
      const fingerprint = proposalFingerprint(proposal);
      const { events, dossiers } = loadVerified();
      const duplicate = [...dossiers.values()].find(
        (item) => item.fingerprint === fingerprint && !TERMINAL_STATES.has(item.state)
      );
      if (duplicate) {
        return { ok: true, idempotent: true, duplicate: true, dossier: plainClone(duplicate) };
      }
      const activeCount = [...dossiers.values()].filter((item) => ACTIVE_STATES.has(item.state)).length;
      if (activeCount >= activeDossierLimit) {
        fail("ACTIVE_QUOTA_EXCEEDED", `Quota de ${activeDossierLimit} dossiers actifs atteint`);
      }
      if (proposal.source === "AI") {
        const today = utcDay(timestamp);
        const aiToday = [...dossiers.values()].filter(
          (item) => item.source === "AI" && utcDay(item.createdAt) === today
        ).length;
        if (aiToday >= dailyAiProposalLimit) {
          fail("DAILY_AI_QUOTA_EXCEEDED", `Quota IA quotidien de ${dailyAiProposalLimit} atteint`);
        }
      }
      const dossier = {
        id: randomUUID(),
        fingerprint,
        source: proposal.source,
        ecosystem: proposal.ecosystem,
        title: proposal.title,
        intent: proposal.intent,
        requestedOutcomes: proposal.requestedOutcomes,
        priority: proposal.priority,
        provenance: proposal.provenance,
        state: "PROPOSED",
        revision: 1,
        createdAt: timestamp,
        updatedAt: timestamp,
        review: null,
        reviewHash: null,
        decision: null
      };
      dossier.dossierHash = dossierHash(dossier);
      appendDossierEvent(events, "PROPOSE", dossier, timestamp, {
        authority: proposal.source === "OWNER" ? "OWNER_REQUEST" : "AI_PROPOSAL"
      });
      if (proposal.source === "AI") {
        appendOutbox(
          {
            kind: "AI_PROPOSAL_DIGEST",
            dossierId: dossier.id,
            dossierHash: dossier.dossierHash,
            ecosystemHash: hash(dossier.ecosystem),
            titleHash: hash(dossier.title),
            title: "Proposition IA locale à restructurer",
            summary: "Ouvrir le dossier local avec son identifiant et vérifier son empreinte avant toute décision.",
            contentRedacted: true,
            priority: dossier.priority
          },
          timestamp
        );
      }
      return { ok: true, idempotent: false, duplicate: false, dossier: plainClone(dossier) };
    });
  }

  function advance(id, targetState, { expectedRevision, actor = {}, evidence = {} } = {}) {
    return withWriteLock(() => {
      const timestamp = now().toISOString();
      const { events, dossiers } = loadVerified();
      const current = dossiers.get(id);
      if (!current) fail("NOT_FOUND", `Dossier inconnu: ${id}`);
      const target = String(targetState || "").toUpperCase();
      if (!OWNER_REVIEW_STATES.includes(target)) fail("INVALID_STATE", `État inconnu: ${target}`);
      if (current.state === target) return { ok: true, idempotent: true, dossier: plainClone(current) };
      assertExpectedRevision(current, expectedRevision);
      if (!TRANSITIONS[current.state].has(target)) {
        fail("INVALID_TRANSITION", `Transition interdite: ${current.state} -> ${target}`);
      }
      const dossier = nextDossier(current, target, timestamp);
      appendDossierEvent(events, "ADVANCE", dossier, timestamp, {
        actor: {
          principalType: redactForOutbox(actor.principalType || actor.kind || actor.type || "AI"),
          role: redactForOutbox(actor.role || "ORCHESTRATOR"),
          principalId: hash(String(actor.principalId || "local-forge"))
        },
        evidenceHash: hash(evidence)
      });
      return { ok: true, idempotent: false, dossier: plainClone(dossier) };
    });
  }

  function restructure(id, review, { expectedRevision, actor = {} } = {}) {
    return withWriteLock(() => {
      const timestamp = now().toISOString();
      const normalized = normalizeReview(review);
      const { events, dossiers } = loadVerified();
      const current = dossiers.get(id);
      if (!current) fail("NOT_FOUND", `Dossier inconnu: ${id}`);

      if (current.state === "REVIEW_READY" && current.reviewHash === hash({ id, fingerprint: current.fingerprint, review: normalized })) {
        return { ok: true, idempotent: true, dossier: plainClone(current) };
      }
      assertExpectedRevision(current, expectedRevision);
      if (current.state === "PROPOSED") {
        const restructuring = nextDossier(current, "RESTRUCTURING", timestamp);
        appendDossierEvent(events, "BEGIN_RESTRUCTURING", restructuring, timestamp, {
          actorHash: hash(String(actor.principalId || "local-forge"))
        });
        events.push(parseJsonLines(paths.ledger).at(-1));
        const preparedReviewHash = hash({ id, fingerprint: current.fingerprint, review: normalized });
        const ready = nextDossier(restructuring, "REVIEW_READY", timestamp, {
          review: normalized,
          reviewHash: preparedReviewHash
        });
        appendDossierEvent(events, "REVIEW_READY", ready, timestamp, {
          reviewHash: preparedReviewHash
        });
        appendOutbox(
          {
            kind: current.source === "OWNER" ? "OWNER_REVIEW_READY" : "AI_REVIEW_DIGEST_READY",
            dossierId: ready.id,
            dossierHash: ready.dossierHash,
            reviewHash: ready.reviewHash,
            ecosystemHash: hash(ready.ecosystem),
            titleHash: hash(ready.title),
            title: current.source === "OWNER" ? "Demande Owner prête à relire" : "Proposition IA prête à relire",
            summary: "Le contenu détaillé reste dans le registre local hashé; cette outbox ne contient ni secret ni code.",
            contentRedacted: true,
            architectureItems: ready.review.architecture.length,
            riskItems: ready.review.risks.length,
            permissionItems: ready.review.permissions.length,
            testItems: ready.review.tests.length,
            requiresHumanOwnerDecision: true
          },
          timestamp
        );
        return { ok: true, idempotent: false, dossier: plainClone(ready) };
      }
      if (current.state !== "RESTRUCTURING") {
        fail("INVALID_TRANSITION", `Restructuration interdite depuis ${current.state}`);
      }
      const preparedReviewHash = hash({ id, fingerprint: current.fingerprint, review: normalized });
      const ready = nextDossier(current, "REVIEW_READY", timestamp, {
        review: normalized,
        reviewHash: preparedReviewHash
      });
      appendDossierEvent(events, "REVIEW_READY", ready, timestamp, { reviewHash: preparedReviewHash });
      return { ok: true, idempotent: false, dossier: plainClone(ready) };
    });
  }

  function decide(
    id,
    { decision, actor, reviewHash: expectedReviewHash, expectedRevision, reason = "" } = {}
  ) {
    return withWriteLock(() => {
      const timestamp = now().toISOString();
      const target = assertDecision(decision);
      assertHumanOwner(actor, ownerPrincipalId);
      const { events, dossiers } = loadVerified();
      const current = dossiers.get(id);
      if (!current) fail("NOT_FOUND", `Dossier inconnu: ${id}`);
      if (current.decision) {
        if (
          current.decision.value === target &&
          current.decision?.reviewHash === expectedReviewHash &&
          current.decision?.principalIdHash === hash(ownerPrincipalId)
        ) {
          return { ok: true, idempotent: true, dossier: plainClone(current) };
        }
        fail("DECISION_CONFLICT", `Une décision ${current.decision.value} existe déjà`);
      }
      assertExpectedRevision(current, expectedRevision);
      if (current.state !== "REVIEW_READY") {
        fail("INVALID_TRANSITION", `Décision interdite depuis ${current.state}`);
      }
      if (!expectedReviewHash || expectedReviewHash !== current.reviewHash) {
        fail("REVIEW_HASH_MISMATCH", "La décision ne correspond pas à l'empreinte du dossier relu");
      }
      const decisionRecord = {
        value: target,
        reviewHash: current.reviewHash,
        principalType: "HUMAN",
        role: "OWNER",
        principalIdHash: hash(ownerPrincipalId),
        decidedAt: timestamp,
        reason: cleanText(reason || (target === "VALIDATED" ? "Validé par Owner" : "Refusé par Owner"), "reason", {
          max: 2_000
        })
      };
      const dossier = nextDossier(current, target, timestamp, { decision: decisionRecord });
      appendDossierEvent(events, "OWNER_DECISION", dossier, timestamp, {
        decision: target,
        reviewHash: current.reviewHash,
        principalIdHash: hash(ownerPrincipalId)
      });
      appendOutbox(
        {
          kind: "OWNER_DECISION_RECEIPT",
          dossierId: dossier.id,
          dossierHash: dossier.dossierHash,
          reviewHash: current.reviewHash,
          decision: target
        },
        timestamp
      );
      return { ok: true, idempotent: false, dossier: plainClone(dossier) };
    });
  }

  function get(id) {
    const { dossiers } = loadVerified();
    const dossier = dossiers.get(id);
    if (!dossier) fail("NOT_FOUND", `Dossier inconnu: ${id}`);
    return plainClone(dossier);
  }

  function list({ activeOnly = false } = {}) {
    const { dossiers } = loadVerified();
    return [...dossiers.values()]
      .filter((dossier) => !activeOnly || ACTIVE_STATES.has(dossier.state))
      .sort((left, right) => {
        const sourceDelta = Number(right.source === "OWNER") - Number(left.source === "OWNER");
        if (sourceDelta) return sourceDelta;
        return left.createdAt.localeCompare(right.createdAt);
      })
      .map(plainClone);
  }

  function readOutbox() {
    const events = parseJsonLines(paths.outbox);
    verifyHashChain(events, "owner-review-outbox");
    return events.map(plainClone);
  }

  function verifyIntegrity() {
    const ledger = loadVerified();
    const outbox = readOutbox();
    return {
      ok: true,
      ledgerEvents: ledger.events.length,
      dossiers: ledger.dossiers.size,
      ledgerHead: ledger.chain.head,
      outboxEvents: outbox.length,
      outboxHead: outbox.at(-1)?.eventHash || null
    };
  }

  function getDigest() {
    const dossiers = list();
    const active = dossiers.filter((item) => ACTIVE_STATES.has(item.state));
    return {
      generatedAt: now().toISOString(),
      active: active.length,
      ownerPriority: active.filter((item) => item.source === "OWNER").length,
      aiProposals: active.filter((item) => item.source === "AI").length,
      reviewReady: active.filter((item) => item.state === "REVIEW_READY").length,
      items: active.map((item) => ({
        id: item.id,
        source: item.source,
        priority: item.priority,
        ecosystem: redactForOutbox(item.ecosystem),
        title: redactForOutbox(item.title),
        state: item.state,
        revision: item.revision,
        dossierHash: item.dossierHash,
        reviewHash: item.reviewHash
      }))
    };
  }

  return Object.freeze({
    paths,
    propose,
    restructure,
    decide,
    advance,
    get,
    list,
    getDigest,
    readOutbox,
    verifyIntegrity
  });
}

export function humanOwnerPrincipal(principalId = "portfolio@example.invalid") {
  return Object.freeze({
    principalType: "HUMAN",
    role: "OWNER",
    isPrimary: true,
    principalId
  });
}
