import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_PATH = fileURLToPath(import.meta.url);
const DEFAULT_ROOT = resolve(dirname(MODULE_PATH), "..", "..");
const LEVELS = Object.freeze(["E0", "E1", "E2", "E3", "E4"]);

function normalizeList(value) {
  return Array.isArray(value) ? [...new Set(value.map((item) => String(item || "").trim()).filter(Boolean))] : [];
}

function validateReflectiveAutonomyPolicy(policy) {
  const issues = [];
  if (policy?.schema !== "aione.reflective-autonomy.v1") issues.push("INVALID_SCHEMA");
  if (policy?.enabled !== true) issues.push("POLICY_DISABLED");
  for (const level of LEVELS) {
    if (!policy?.levels?.[level]) issues.push(`MISSING_LEVEL_${level}`);
  }
  if (policy?.levels?.E4?.decision !== "DENY_AUTONOMOUS") issues.push("E4_MUST_REMAIN_DENIED");
  if (normalizeList(policy?.immutableDomains).length === 0) issues.push("IMMUTABLE_DOMAINS_REQUIRED");
  return { ok: issues.length === 0, issues };
}

function readReflectiveAutonomyPolicy(root = DEFAULT_ROOT) {
  const path = join(resolve(root), "config", "reflective-autonomy.json");
  const policy = JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
  return { path, policy, validation: validateReflectiveAutonomyPolicy(policy) };
}

function decisionTouchesImmutable(policy, decision) {
  const immutable = new Set(normalizeList(policy?.immutableDomains).map((item) => item.toLowerCase()));
  return normalizeList(decision?.domains).some((item) => immutable.has(item.toLowerCase()));
}

function evaluateReflectiveDecision(policy, decision = {}) {
  const validation = validateReflectiveAutonomyPolicy(policy);
  if (!validation.ok) return { ok: false, status: "POLICY_INVALID", reasons: validation.issues };
  const level = String(decision.level || "").toUpperCase();
  const levelPolicy = policy.levels[level];
  if (!levelPolicy || !LEVELS.includes(level)) return { ok: false, status: "INVALID_LEVEL", reasons: ["UNKNOWN_EVOLUTION_LEVEL"] };
  const missingContract = normalizeList(policy.decisionContract?.required).filter((field) => {
    if (field === "reversible") return typeof decision.reversible !== "boolean";
    return decision[field] === undefined || decision[field] === null || decision[field] === "";
  });
  if (missingContract.length > 0) return { ok: false, status: "INCOMPLETE_DECISION", reasons: missingContract.map((field) => `MISSING_${field}`) };
  if (level === "E4" || decisionTouchesImmutable(policy, decision)) {
    return { ok: false, status: "DENIED_IMMUTABLE", reasons: [level === "E4" ? "E4_AUTONOMY_DENIED" : "IMMUTABLE_DOMAIN"] };
  }
  if (decision.localOnly !== true || decision.external === true) {
    return { ok: false, status: "OWNER_REQUIRED_EXTERNAL", reasons: ["OUTSIDE_LOCAL_ENVELOPE"] };
  }
  if (decision.reversible !== true || !String(decision.rollback || "").trim()) {
    return { ok: false, status: "OWNER_REQUIRED_IRREVERSIBLE", reasons: ["REVERSIBLE_ROLLBACK_REQUIRED"] };
  }
  if (level === "E3" && decision.deploymentTarget !== "isolated-runtime") {
    return { ok: false, status: "OWNER_REQUIRED_CANONICAL", reasons: ["E3_AUTONOMY_ISOLATED_ONLY"] };
  }
  const confidenceFloor = Number(policy.decisionContract?.minimumConfidence?.[level] ?? 1);
  if (!Number.isFinite(Number(decision.confidence)) || Number(decision.confidence) < confidenceFloor) {
    return { ok: false, status: "NEEDS_MORE_EVIDENCE", reasons: ["CONFIDENCE_BELOW_LEVEL_FLOOR"] };
  }
  const evidence = normalizeList(decision.evidence);
  const gateState = { ...decision.gates, evidencePresent: evidence.length > 0 };
  const missingGates = normalizeList(levelPolicy.requiredGates).filter((gate) => gateState[gate] !== true);
  if (missingGates.length > 0) {
    return { ok: false, status: "NEEDS_MORE_EVIDENCE", reasons: missingGates.map((gate) => `GATE_${gate}_REQUIRED`) };
  }
  return {
    ok: true,
    status: level === "E3" ? "AUTO_APPROVED_ISOLATED" : "AUTO_APPROVED",
    level,
    persistence: levelPolicy.persistence,
    humanApprovalRequired: false,
    explanation: `Choix ${decision.id} autorisé au niveau ${level}: local, réversible et conforme aux portes de preuve.`,
    audit: {
      id: decision.id,
      kind: decision.kind,
      scope: decision.scope,
      expectedEffect: decision.expectedEffect,
      evidence,
      confidence: Number(decision.confidence),
      rollback: decision.rollback
    }
  };
}

function chooseReflectiveAction(policy, candidates = []) {
  const evaluated = candidates.map((candidate) => ({ candidate, decision: evaluateReflectiveDecision(policy, candidate) }));
  const eligible = evaluated
    .filter((item) => item.decision.ok)
    .sort((left, right) => {
      const utilityDifference = Number(right.candidate.utility || 0) - Number(left.candidate.utility || 0);
      if (utilityDifference !== 0) return utilityDifference;
      return String(left.candidate.id).localeCompare(String(right.candidate.id));
    });
  return {
    status: eligible.length > 0 ? "SELF_SELECTED" : "NO_ELIGIBLE_CHOICE",
    selected: eligible[0] || null,
    evaluated
  };
}

function buildReflectiveAutonomyInstruction(policy) {
  if (!validateReflectiveAutonomyPolicy(policy).ok) return "";
  return [
    "AUTONOMIE RÉFLEXIVE ACTIVE:",
    "Tu choisis toi-même les sous-objectifs, stratégies, outils locaux autorisés, profondeur de réflexion, ordre et arrêt des pistes inefficaces.",
    "Aucune validation humaine n'est requise pour E0/E1 ni pour E2 après sandbox, tests, comparaison et rollback vérifié.",
    "E3 peut être adopté seul uniquement dans le runtime isolé versionné; le canonique et l'externe restent hors enveloppe.",
    "Justifie le choix par faits, critères, incertitude et rollback, sans exposer de chaîne de pensée brute. E4 reste interdit."
  ].join("\n");
}

export {
  buildReflectiveAutonomyInstruction,
  chooseReflectiveAction,
  evaluateReflectiveDecision,
  readReflectiveAutonomyPolicy,
  validateReflectiveAutonomyPolicy
};
