import { createHash, randomUUID } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const LEVELS = Object.freeze(["N0", "N1", "N2", "N3", "N4", "N5"]);

function clamp(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function hash(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function hostMatches(host, allowed) {
  return host === allowed || host.endsWith(`.${allowed}`);
}

function safePublicUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password || url.port) throw new Error("SOURCE_URL_REFUSED");
  if (["localhost", "0.0.0.0", "::1"].includes(url.hostname) || /^127\./u.test(url.hostname) || /^10\./u.test(url.hostname) || /^192\.168\./u.test(url.hostname)) {
    throw new Error("PRIVATE_NETWORK_SOURCE_REFUSED");
  }
  return url;
}

function validatePolicy(policy) {
  const issues = [];
  if (policy?.schema !== "aione.reflective-network-access.v1") issues.push("INVALID_SCHEMA");
  if (policy?.offlineComplete !== true) issues.push("OFFLINE_COMPLETENESS_REQUIRED");
  for (const level of LEVELS) if (!policy?.levels?.[level]?.reversible) issues.push(`LEVEL_${level}_MUST_BE_REVERSIBLE`);
  return { ok: issues.length === 0, issues };
}

function authorizationAllows(authorization, request, urls, now) {
  if (authorization?.authorized !== true) return false;
  const ceiling = LEVELS.indexOf(String(authorization.level || "N0"));
  if (ceiling < LEVELS.indexOf(request.level)) return false;
  if (authorization.expiresAt && new Date(authorization.expiresAt) <= now) return false;
  const allowedHosts = Array.isArray(authorization.hosts) ? authorization.hosts : [];
  return urls.every((url) => allowedHosts.some((host) => hostMatches(url.hostname, host)));
}

function evaluateNetworkNeed(policy, request = {}, localKnowledge = {}, { now = new Date() } = {}) {
  const validation = validatePolicy(policy);
  if (!validation.ok) return { ok: false, status: "POLICY_INVALID", reasons: validation.issues };
  const level = String(request.level || policy.defaultLevel || "N0").toUpperCase();
  if (!LEVELS.includes(level)) return { ok: false, status: "INVALID_LEVEL", reasons: ["UNKNOWN_NETWORK_LEVEL"] };
  const reason = String(request.reason || "").trim();
  if (!reason) return { ok: false, status: "INCOMPLETE_REQUEST", reasons: ["REASON_REQUIRED"] };
  const dataCategories = (request.dataCategories || []).map((item) => String(item).toLowerCase());
  const forbidden = dataCategories.filter((item) => (policy.neverSend || []).includes(item));
  if (forbidden.length) return { ok: false, status: "DENIED_SENSITIVE_DATA", reasons: forbidden };
  if (localKnowledge.available === true && localKnowledge.confidence >= Number(request.minimumConfidence || 0.7)) {
    return { ok: true, status: "LOCAL_KNOWLEDGE_SUFFICIENT", networkAllowed: false, score: 0, localAlternative: localKnowledge.reference || null };
  }
  if (level === "N0") return { ok: true, status: "NETWORK_DISABLED", networkAllowed: false, score: 0 };

  let urls;
  try {
    urls = (request.sources || []).map(safePublicUrl);
  } catch (error) {
    return { ok: false, status: "SOURCE_REFUSED", networkAllowed: false, reasons: [error.message] };
  }
  if (urls.length === 0) return { ok: false, status: "INCOMPLETE_REQUEST", reasons: ["SOURCE_REQUIRED"] };
  const allowlist = policy.allowlistedHosts || [];
  if (level === "N1" && !urls.every((url) => allowlist.some((host) => hostMatches(url.hostname, host)))) {
    return { ok: false, status: "HOST_NOT_ALLOWLISTED", networkAllowed: false };
  }
  if (level === "N3" && !urls.every((url) => (policy.approvedApiHosts || []).some((host) => hostMatches(url.hostname, host)))) {
    return { ok: false, status: "API_NOT_APPROVED", networkAllowed: false };
  }

  const weights = policy.weights || {};
  const factors = {
    benefit: clamp(request.expectedBenefit),
    confidenceGain: clamp(request.confidenceGain),
    freshness: clamp(request.freshnessNeed),
    urgency: clamp(request.urgency),
    risk: clamp(request.risk),
    localAlternative: clamp(request.localAlternativeStrength)
  };
  const score = Math.max(0, Math.min(1, Object.entries(factors).reduce((sum, [key, value]) => sum + value * Number(weights[key] || 0), 0)));
  if (score < Number(policy.necessityThreshold || 0.68)) {
    return { ok: true, status: "LOCAL_ALTERNATIVE_PREFERRED", networkAllowed: false, score, factors };
  }
  const requestWithLevel = { ...request, level };
  const authorized = authorizationAllows(request.authorization, requestWithLevel, urls, now) || (policy.automaticLevels || []).includes(level);
  const decision = {
    ok: true,
    decisionId: randomUUID(),
    status: authorized ? "APPROVED_BOUNDED" : "PROPOSE_ACCESS",
    networkAllowed: authorized,
    humanAuthorizationRequired: !authorized,
    level,
    reason,
    score,
    factors,
    sources: urls.map((url) => url.toString()),
    alternatives: request.localAlternatives || [],
    expiresAt: request.authorization?.expiresAt || null
  };
  return decision;
}

class ReflectiveNetworkAccessManager {
  constructor({ policy, policyPath, now = () => new Date() } = {}) {
    this.policy = policy || JSON.parse(readFileSync(resolve(policyPath), "utf8"));
    this.now = now;
    const validation = validatePolicy(this.policy);
    if (!validation.ok) throw new Error(validation.issues.join(","));
  }

  decide(request, localKnowledge = {}) {
    return evaluateNetworkNeed(this.policy, request, localKnowledge, { now: this.now() });
  }

  recordAccess({ decision, durationMs, result, confidence, memoryImpact = "NONE", useful, localCopyReference = null }) {
    if (decision?.status !== "APPROVED_BOUNDED" || decision.networkAllowed !== true) throw new Error("UNAPPROVED_ACCESS_CANNOT_BE_RECORDED");
    const path = resolve(this.policy.ledgerPath);
    mkdirSync(dirname(path), { recursive: true });
    const lines = existsSync(path) ? readFileSync(path, "utf8").split(/\r?\n/u).filter(Boolean) : [];
    const previous = lines.length ? JSON.parse(lines.at(-1)) : null;
    const entry = {
      schema: "aione.network-access-record.v1",
      accessId: randomUUID(),
      at: this.now().toISOString(),
      decisionId: decision.decisionId,
      level: decision.level,
      reason: decision.reason,
      durationMs: Math.max(0, Number(durationMs) || 0),
      sources: decision.sources,
      result: String(result || "").slice(0, 2000),
      confidence: clamp(confidence),
      memoryImpact: String(memoryImpact),
      useful: useful === true,
      localCopyReference,
      futureRecommendation: useful && this.policy.copyUsefulKnowledgeLocally
        ? "CACHE_LOCALLY_TO_REDUCE_FUTURE_DEPENDENCY"
        : "DO_NOT_INCREASE_NETWORK_DEPENDENCY",
      previousHash: previous?.hash || null
    };
    entry.hash = hash(entry);
    appendFileSync(path, `${JSON.stringify(entry)}\n`, "utf8");
    return entry;
  }
}

export { LEVELS, ReflectiveNetworkAccessManager, evaluateNetworkNeed, validatePolicy };
