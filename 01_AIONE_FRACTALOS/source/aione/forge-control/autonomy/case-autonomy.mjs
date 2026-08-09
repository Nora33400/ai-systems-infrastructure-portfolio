import {
  createHash,
  createHmac,
  randomUUID,
  timingSafeEqual
} from "node:crypto";
import path from "node:path";

export const CASE_AUTONOMY = Object.freeze({
  requestSchema: "aione.case-autonomy-request.v1",
  dossierSchema: "aione.case-autonomy-dossier.v1",
  grantSchema: "aione.case-autonomy-grant.v1",
  executionSchema: "aione.case-autonomy-execution.v1",
  requestType: "EXPLICIT_OWNER_REQUEST_FOR_ONE_CASE",
  levels: Object.freeze([
    "L0_NONE",
    "L1_OBSERVE",
    "L2_PROPOSE",
    "L3_SIMULATE",
    "L4_ISOLATED_EXECUTE",
    "L5_SCOPED_OPERATE",
    "L6_ADMIN",
    "L7_OWNER"
  ]),
  principalTypes: Object.freeze(["HUMAN", "AI"]),
  humanRoles: Object.freeze(["PUBLIC_USER", "AUTHENTICATED_USER", "USER", "ADMIN", "OWNER"]),
  aiRoles: Object.freeze(["AI_AGENT", "AI_ORCHESTRATOR", "AI_GOVERNOR"]),
  nonDelegableInvariants: Object.freeze([
    "applicable-law",
    "human-consent-and-rights",
    "no-hidden-manipulation",
    "no-identity-spoofing",
    "no-ai-self-escalation",
    "no-fabricated-owner-validation",
    "no-undeclared-irreversible-action",
    "no-secret-or-out-of-scope-data-access",
    "revocation-audit-and-rollback"
  ])
});

const LEVEL_INDEX = new Map(CASE_AUTONOMY.levels.map((level, index) => [level, index]));
const RESOURCE_KEYS = Object.freeze([
  "maxWallClockSeconds",
  "maxCpuSeconds",
  "maxMemoryMb",
  "maxGpuMemoryMb",
  "maxStorageMb",
  "maxNetworkRequests",
  "maxPublications"
]);
const SCOPE_KEYS = Object.freeze([
  "allowedPaths",
  "allowedActions",
  "allowedTools",
  "allowedDataClasses",
  "allowedNetworkEndpoints",
  "publicationChannels",
  "resources"
]);
const MAX_GRANT_TTL_SECONDS = 7 * 24 * 60 * 60;
const MAX_APPROVAL_WINDOW_SECONDS = 60 * 60;
const CREATED_LEDGERS = new WeakSet();

export class CaseAutonomyError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "CaseAutonomyError";
    this.code = code;
  }
}

function fail(code, message) {
  throw new CaseAutonomyError(code, message);
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function assertObject(value, code, label) {
  if (!isPlainObject(value)) fail(code, `${label} doit être un objet simple.`);
}

function assertExactKeys(value, expected, code, label) {
  assertObject(value, code, label);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (
    actual.length !== wanted.length ||
    actual.some((key, index) => key !== wanted[index])
  ) {
    fail(code, `${label} ne respecte pas le schéma strict.`);
  }
}

function assertAllowedKeys(value, allowed, code, label) {
  assertObject(value, code, label);
  if (Object.keys(value).some((key) => !allowed.includes(key))) {
    fail(code, `${label} contient une propriété inconnue.`);
  }
}

function assertString(value, code, label, { max = 4096, pattern } = {}) {
  if (
    typeof value !== "string" ||
    value.trim() !== value ||
    value.length === 0 ||
    value.length > max ||
    value.includes("\0") ||
    (pattern && !pattern.test(value))
  ) {
    fail(code, `${label} est invalide.`);
  }
  return value;
}

function normalizeIdentifier(value, label) {
  return assertString(value, "INVALID_IDENTIFIER", label, {
    max: 160,
    pattern: /^[A-Za-z0-9][A-Za-z0-9._:-]*$/
  });
}

function normalizeTextArray(value, label, { identifiers = false } = {}) {
  if (!Array.isArray(value) || value.length === 0 || value.length > 128) {
    fail("INVALID_ARRAY", `${label} doit être une liste bornée non vide.`);
  }
  const normalized = value.map((item, index) =>
    identifiers
      ? normalizeIdentifier(item, `${label}[${index}]`)
      : assertString(item, "INVALID_TEXT", `${label}[${index}]`, { max: 2048 })
  );
  if (new Set(normalized).size !== normalized.length) {
    fail("DUPLICATE_SCOPE_VALUE", `${label} contient un doublon.`);
  }
  return normalized.sort();
}

function normalizeOptionalIdentifierArray(value, label) {
  if (!Array.isArray(value) || value.length > 256) {
    fail("INVALID_SCOPE", `${label} doit être une liste bornée.`);
  }
  const normalized = value.map((item, index) =>
    normalizeIdentifier(item, `${label}[${index}]`)
  );
  if (new Set(normalized).size !== normalized.length) {
    fail("DUPLICATE_SCOPE_VALUE", `${label} contient un doublon.`);
  }
  return normalized.sort();
}

function parseInstant(value, label) {
  assertString(value, "INVALID_TIME", label, { max: 64 });
  const time = Date.parse(value);
  if (!Number.isFinite(time) || new Date(time).toISOString() !== value) {
    fail("INVALID_TIME", `${label} doit être un instant ISO canonique.`);
  }
  return time;
}

function instant(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) fail("INVALID_TIME", "Instant invalide.");
  return date.toISOString();
}

function assertBoundedInteger(value, label, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < 0 || value > max) {
    fail("INVALID_RESOURCE_LIMIT", `${label} doit être un entier borné positif ou nul.`);
  }
  return value;
}

function validatePrincipal(principal, label) {
  assertExactKeys(
    principal,
    ["id", "principalType", "role", "level"],
    "INVALID_PRINCIPAL",
    label
  );
  const id = normalizeIdentifier(principal.id, `${label}.id`);
  if (!CASE_AUTONOMY.principalTypes.includes(principal.principalType)) {
    fail("INVALID_PRINCIPAL_TYPE", `${label}.principalType est invalide.`);
  }
  if (!LEVEL_INDEX.has(principal.level)) {
    fail("INVALID_PERMISSION_LEVEL", `${label}.level est invalide.`);
  }
  const roles = principal.principalType === "HUMAN"
    ? CASE_AUTONOMY.humanRoles
    : CASE_AUTONOMY.aiRoles;
  if (!roles.includes(principal.role)) {
    fail("ROLE_TYPE_MISMATCH", `${label}.role ne correspond pas au type de principal.`);
  }
  const levelIndex = LEVEL_INDEX.get(principal.level);
  if (principal.principalType === "AI" && levelIndex > 4) {
    fail("AI_SELF_ESCALATION", "Une identité IA non mandatée est plafonnée à L4.");
  }
  if (principal.role === "OWNER" && principal.level !== "L7_OWNER") {
    fail("INVALID_OWNER", "Le rôle Owner requiert L7_OWNER.");
  }
  if (principal.role === "PUBLIC_USER" && levelIndex > 1) {
    fail("INVALID_PUBLIC_USER", "Un utilisateur public est plafonné à L1 observation.");
  }
  if (principal.role === "AUTHENTICATED_USER" && levelIndex > 5) {
    fail("INVALID_AUTHENTICATED_USER", "Un utilisateur authentifié est plafonné à L5 borné.");
  }
  if (principal.role === "ADMIN" && levelIndex > 6) {
    fail("INVALID_ADMIN", "Le rôle Admin ne peut pas revendiquer L7.");
  }
  if (principal.role === "USER" && levelIndex > 5) {
    fail("INVALID_USER", "Le rôle User est plafonné à L5.");
  }
  return Object.freeze({
    id,
    principalType: principal.principalType,
    role: principal.role,
    level: principal.level
  });
}

function assertOwner(owner) {
  const normalized = validatePrincipal(owner, "owner");
  if (
    normalized.principalType !== "HUMAN" ||
    normalized.role !== "OWNER" ||
    normalized.level !== "L7_OWNER"
  ) {
    fail("OWNER_AUTHORITY_REQUIRED", "Un Owner humain L7 est requis.");
  }
  return normalized;
}

function normalizeScopedPath(value, label) {
  const original = assertString(value, "INVALID_PATH_SCOPE", label, { max: 1024 });
  if (/[*?]/u.test(original)) {
    fail("WILDCARD_SCOPE_REFUSED", `${label} ne peut pas contenir de joker.`);
  }
  const windowsAbsolute = /^[A-Za-z]:[\\/]/u.test(original);
  const posixAbsolute = original.startsWith("/");
  if (!windowsAbsolute && !posixAbsolute) {
    fail("RELATIVE_SCOPE_REFUSED", `${label} doit être absolu.`);
  }
  const segments = original.replaceAll("\\", "/").split("/");
  if (segments.includes("..")) {
    fail("PATH_TRAVERSAL_REFUSED", `${label} contient une traversée.`);
  }
  if (windowsAbsolute) {
    const normalized = path.win32.normalize(original.replaceAll("/", "\\"));
    return normalized[0].toUpperCase() + normalized.slice(1);
  }
  return path.posix.normalize(original);
}

function normalizeNetworkEndpoint(value, label) {
  const raw = assertString(value, "INVALID_NETWORK_ENDPOINT", label, { max: 1024 });
  if (raw.includes("*")) {
    fail("WILDCARD_SCOPE_REFUSED", `${label} ne peut pas contenir de joker.`);
  }
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    fail("INVALID_NETWORK_ENDPOINT", `${label} n'est pas une URL valide.`);
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.hash
  ) {
    fail("INVALID_NETWORK_ENDPOINT", `${label} contient une autorité réseau interdite.`);
  }
  return parsed.href;
}

function normalizeResources(resources) {
  assertExactKeys(
    resources,
    RESOURCE_KEYS,
    "INVALID_RESOURCES",
    "scope.resources"
  );
  return Object.freeze(Object.fromEntries(
    RESOURCE_KEYS.map((key) => [key, assertBoundedInteger(resources[key], key)])
  ));
}

function normalizeScope(scope) {
  assertExactKeys(scope, SCOPE_KEYS, "INVALID_SCOPE", "scope");
  if (!Array.isArray(scope.allowedPaths) || scope.allowedPaths.length > 256) {
    fail("INVALID_SCOPE", "scope.allowedPaths doit être une liste bornée.");
  }
  const allowedPaths = scope.allowedPaths.map((entry, index) =>
    normalizeScopedPath(entry, `scope.allowedPaths[${index}]`)
  ).sort();
  if (new Set(allowedPaths.map((entry) => entry.toLowerCase())).size !== allowedPaths.length) {
    fail("DUPLICATE_SCOPE_VALUE", "scope.allowedPaths contient un doublon.");
  }
  if (!Array.isArray(scope.allowedNetworkEndpoints) || scope.allowedNetworkEndpoints.length > 128) {
    fail("INVALID_SCOPE", "scope.allowedNetworkEndpoints doit être une liste bornée.");
  }
  const allowedNetworkEndpoints = scope.allowedNetworkEndpoints.map((entry, index) =>
    normalizeNetworkEndpoint(entry, `scope.allowedNetworkEndpoints[${index}]`)
  ).sort();
  if (new Set(allowedNetworkEndpoints).size !== allowedNetworkEndpoints.length) {
    fail("DUPLICATE_SCOPE_VALUE", "scope.allowedNetworkEndpoints contient un doublon.");
  }
  return deepFreeze({
    allowedPaths,
    allowedActions: normalizeOptionalIdentifierArray(scope.allowedActions, "scope.allowedActions"),
    allowedTools: normalizeOptionalIdentifierArray(scope.allowedTools, "scope.allowedTools"),
    allowedDataClasses: normalizeOptionalIdentifierArray(
      scope.allowedDataClasses,
      "scope.allowedDataClasses"
    ),
    allowedNetworkEndpoints,
    publicationChannels: normalizeOptionalIdentifierArray(
      scope.publicationChannels,
      "scope.publicationChannels"
    ),
    resources: normalizeResources(scope.resources)
  });
}

function isPathWithin(candidate, allowedRoot) {
  const windows = /^[A-Za-z]:\\/u.test(candidate) && /^[A-Za-z]:\\/u.test(allowedRoot);
  const pathApi = windows ? path.win32 : path.posix;
  const left = windows ? candidate.toLowerCase() : candidate;
  const right = windows ? allowedRoot.toLowerCase() : allowedRoot;
  const relative = pathApi.relative(right, left);
  return relative === "" || (!relative.startsWith("..") && !pathApi.isAbsolute(relative));
}

function scopeIsSubset(candidate, allowed) {
  const setContainsAll = (values, available) => {
    const allowedSet = new Set(available);
    return values.every((value) => allowedSet.has(value));
  };
  return (
    candidate.allowedPaths.every((candidatePath) =>
      allowed.allowedPaths.some((root) => isPathWithin(candidatePath, root))
    ) &&
    setContainsAll(candidate.allowedActions, allowed.allowedActions) &&
    setContainsAll(candidate.allowedTools, allowed.allowedTools) &&
    setContainsAll(candidate.allowedDataClasses, allowed.allowedDataClasses) &&
    setContainsAll(candidate.allowedNetworkEndpoints, allowed.allowedNetworkEndpoints) &&
    setContainsAll(candidate.publicationChannels, allowed.publicationChannels) &&
    RESOURCE_KEYS.every((key) => candidate.resources[key] <= allowed.resources[key])
  );
}

function unionScopes(scopes) {
  if (!Array.isArray(scopes) || scopes.length === 0) {
    fail("PERMISSION_SET_REQUIRED", "Au moins un ensemble de permissions validé est requis.");
  }
  const normalized = scopes.map(normalizeScope);
  const union = {
    allowedPaths: [],
    allowedActions: [],
    allowedTools: [],
    allowedDataClasses: [],
    allowedNetworkEndpoints: [],
    publicationChannels: [],
    resources: Object.fromEntries(RESOURCE_KEYS.map((key) => [key, 0]))
  };
  for (const scope of normalized) {
    for (const key of SCOPE_KEYS.filter((entry) => entry !== "resources")) {
      union[key].push(...scope[key]);
    }
    for (const key of RESOURCE_KEYS) {
      union.resources[key] = Math.max(union.resources[key], scope.resources[key]);
    }
  }
  for (const key of SCOPE_KEYS.filter((entry) => entry !== "resources")) {
    const caseInsensitive = key === "allowedPaths";
    const seen = new Map();
    for (const value of union[key]) {
      seen.set(caseInsensitive ? value.toLowerCase() : value, value);
    }
    union[key] = [...seen.values()].sort();
  }
  return deepFreeze(union);
}

function validateCase(caseDefinition) {
  assertExactKeys(
    caseDefinition,
    [
      "caseId",
      "goal",
      "successCriteria",
      "stopCriteria",
      "ecosystemIds",
      "projectIds"
    ],
    "INVALID_CASE",
    "case"
  );
  return deepFreeze({
    caseId: normalizeIdentifier(caseDefinition.caseId, "case.caseId"),
    goal: assertString(caseDefinition.goal, "INVALID_GOAL", "case.goal", { max: 4096 }),
    successCriteria: normalizeTextArray(
      caseDefinition.successCriteria,
      "case.successCriteria"
    ),
    stopCriteria: normalizeTextArray(caseDefinition.stopCriteria, "case.stopCriteria"),
    ecosystemIds: normalizeTextArray(
      caseDefinition.ecosystemIds,
      "case.ecosystemIds",
      { identifiers: true }
    ),
    projectIds: normalizeTextArray(
      caseDefinition.projectIds,
      "case.projectIds",
      { identifiers: true }
    )
  });
}

function canonicalize(value) {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  if (isPlainObject(value)) {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalize(value[key])])
    );
  }
  fail("NON_CANONICAL_VALUE", "La valeur ne peut pas être canonisée.");
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function canonicalHash(value) {
  return createHash("sha256").update(canonicalJson(value), "utf8").digest("hex");
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const item of Object.values(value)) deepFreeze(item);
  }
  return value;
}

function validatePermissionSet(permissionSet, owner) {
  assertExactKeys(
    permissionSet,
    ["permissionSetId", "validation", "ownerId", "scope"],
    "INVALID_PERMISSION_SET",
    "permissionSet"
  );
  if (permissionSet.validation !== "OWNER_VALIDATED_LOCAL") {
    fail("UNVALIDATED_PERMISSION_SET", "L'ensemble de permissions n'est pas validé localement.");
  }
  if (permissionSet.ownerId !== owner.id) {
    fail("OWNER_SPOOFING", "L'autorité de l'ensemble de permissions ne correspond pas à l'Owner.");
  }
  return deepFreeze({
    permissionSetId: normalizeIdentifier(
      permissionSet.permissionSetId,
      "permissionSet.permissionSetId"
    ),
    validation: permissionSet.validation,
    ownerId: permissionSet.ownerId,
    scope: normalizeScope(permissionSet.scope)
  });
}

export function createCaseAutonomyDossier(input) {
  assertExactKeys(
    input,
    [
      "schema",
      "requestId",
      "requestType",
      "owner",
      "subject",
      "case",
      "requestedLevel",
      "requestedScope",
      "permissionSets",
      "createdAt",
      "approvalWindowSeconds",
      "grantTtlSeconds"
    ],
    "INVALID_REQUEST_SCHEMA",
    "request"
  );
  if (input.schema !== CASE_AUTONOMY.requestSchema) {
    fail("INVALID_REQUEST_SCHEMA", "Schéma de demande inconnu.");
  }
  if (input.requestType !== CASE_AUTONOMY.requestType) {
    fail("EXPLICIT_OWNER_REQUEST_REQUIRED", "Une demande Owner explicite pour un cas est requise.");
  }
  const owner = assertOwner(input.owner);
  const subject = validatePrincipal(input.subject, "subject");
  if (subject.principalType !== "AI") {
    fail("AI_SUBJECT_REQUIRED", "Le mandat autonome cible une identité IA déclarée.");
  }
  const requestedLevelIndex = LEVEL_INDEX.get(input.requestedLevel);
  if (requestedLevelIndex === undefined) {
    fail("INVALID_PERMISSION_LEVEL", "Le niveau demandé est inconnu.");
  }
  if (requestedLevelIndex > 5) {
    fail("AI_SELF_ESCALATION", "Un mandat Owner borné ne peut pas accorder L6 ou L7 à une IA.");
  }
  if (requestedLevelIndex <= LEVEL_INDEX.get(subject.level)) {
    fail("GRANT_NOT_NEEDED", "Le mandat doit accorder un niveau supérieur au niveau IA courant.");
  }
  const createdAtMs = parseInstant(input.createdAt, "createdAt");
  const approvalWindowSeconds = assertBoundedInteger(
    input.approvalWindowSeconds,
    "approvalWindowSeconds",
    MAX_APPROVAL_WINDOW_SECONDS
  );
  if (approvalWindowSeconds < 1) {
    fail("INVALID_APPROVAL_WINDOW", "La fenêtre d'approbation doit être positive.");
  }
  const grantTtlSeconds = assertBoundedInteger(
    input.grantTtlSeconds,
    "grantTtlSeconds",
    MAX_GRANT_TTL_SECONDS
  );
  if (grantTtlSeconds < 1) fail("INVALID_TTL", "Le TTL du mandat doit être positif.");
  if (!Array.isArray(input.permissionSets) || input.permissionSets.length > 64) {
    fail("INVALID_PERMISSION_SET", "permissionSets doit être une liste bornée.");
  }
  const permissionSets = input.permissionSets.map((entry) =>
    validatePermissionSet(entry, owner)
  );
  const ids = permissionSets.map((entry) => entry.permissionSetId);
  if (new Set(ids).size !== ids.length) {
    fail("DUPLICATE_PERMISSION_SET", "Un ensemble de permissions est dupliqué.");
  }
  const effectivePermissionScope = unionScopes(permissionSets.map((entry) => entry.scope));
  const requestedScope = normalizeScope(input.requestedScope);
  if (!scopeIsSubset(requestedScope, effectivePermissionScope)) {
    fail("SCOPE_EXTENSION_REFUSED", "La demande dépasse l'union des permissions validées.");
  }
  const body = {
    schema: CASE_AUTONOMY.dossierSchema,
    requestId: normalizeIdentifier(input.requestId, "requestId"),
    requestType: input.requestType,
    owner,
    subject,
    case: validateCase(input.case),
    requestedLevel: input.requestedLevel,
    requestedScope,
    permissionSetIds: ids.sort(),
    effectivePermissionScope,
    createdAt: new Date(createdAtMs).toISOString(),
    approvalExpiresAt: new Date(createdAtMs + approvalWindowSeconds * 1000).toISOString(),
    grantTtlSeconds,
    singleUse: true,
    scopeExpansion: "REFUSED_REQUIRES_NEW_OWNER_GRANT",
    nonDelegableInvariants: [...CASE_AUTONOMY.nonDelegableInvariants]
  };
  return deepFreeze({ ...body, dossierHash: canonicalHash(body) });
}

function validateDossier(dossier) {
  assertExactKeys(
    dossier,
    [
      "schema",
      "requestId",
      "requestType",
      "owner",
      "subject",
      "case",
      "requestedLevel",
      "requestedScope",
      "permissionSetIds",
      "effectivePermissionScope",
      "createdAt",
      "approvalExpiresAt",
      "grantTtlSeconds",
      "singleUse",
      "scopeExpansion",
      "nonDelegableInvariants",
      "dossierHash"
    ],
    "INVALID_DOSSIER",
    "dossier"
  );
  if (dossier.schema !== CASE_AUTONOMY.dossierSchema) {
    fail("INVALID_DOSSIER", "Schéma de dossier inconnu.");
  }
  if (
    dossier.requestType !== CASE_AUTONOMY.requestType ||
    dossier.singleUse !== true ||
    dossier.scopeExpansion !== "REFUSED_REQUIRES_NEW_OWNER_GRANT"
  ) {
    fail("INVALID_DOSSIER", "Les invariants structurels du dossier sont invalides.");
  }
  assertOwner(dossier.owner);
  const subject = validatePrincipal(dossier.subject, "dossier.subject");
  if (subject.principalType !== "AI") fail("INVALID_DOSSIER", "Le sujet doit être une IA.");
  validateCase(dossier.case);
  normalizeScope(dossier.requestedScope);
  normalizeScope(dossier.effectivePermissionScope);
  if (!scopeIsSubset(dossier.requestedScope, dossier.effectivePermissionScope)) {
    fail("SCOPE_EXTENSION_REFUSED", "Le dossier contient une extension de portée.");
  }
  if (
    !Array.isArray(dossier.permissionSetIds) ||
    dossier.permissionSetIds.length === 0 ||
    dossier.permissionSetIds.some((id) => normalizeIdentifier(id, "permissionSetId") !== id) ||
    new Set(dossier.permissionSetIds).size !== dossier.permissionSetIds.length ||
    canonicalJson(dossier.permissionSetIds) !==
      canonicalJson([...dossier.permissionSetIds].sort())
  ) {
    fail("INVALID_DOSSIER", "Les références de permissions sont invalides.");
  }
  if (
    !Array.isArray(dossier.nonDelegableInvariants) ||
    canonicalJson(dossier.nonDelegableInvariants) !==
      canonicalJson(CASE_AUTONOMY.nonDelegableInvariants)
  ) {
    fail("NON_DELEGABLE_INVARIANT_CHANGED", "Les invariants non délégables ont été altérés.");
  }
  const level = LEVEL_INDEX.get(dossier.requestedLevel);
  if (level === undefined || level > 5 || level <= LEVEL_INDEX.get(subject.level)) {
    fail("AI_SELF_ESCALATION", "Le niveau du dossier est invalide.");
  }
  const createdAtMs = parseInstant(dossier.createdAt, "dossier.createdAt");
  const approvalExpiresAtMs = parseInstant(
    dossier.approvalExpiresAt,
    "dossier.approvalExpiresAt"
  );
  if (
    approvalExpiresAtMs <= createdAtMs ||
    approvalExpiresAtMs - createdAtMs > MAX_APPROVAL_WINDOW_SECONDS * 1000
  ) {
    fail("INVALID_APPROVAL_WINDOW", "La fenêtre d'approbation du dossier est invalide.");
  }
  assertBoundedInteger(
    dossier.grantTtlSeconds,
    "dossier.grantTtlSeconds",
    MAX_GRANT_TTL_SECONDS
  );
  if (dossier.grantTtlSeconds < 1) {
    fail("INVALID_TTL", "Le TTL du mandat doit être positif.");
  }
  const body = { ...dossier };
  delete body.dossierHash;
  if (
    typeof dossier.dossierHash !== "string" ||
    dossier.dossierHash.length !== 64 ||
    canonicalHash(body) !== dossier.dossierHash
  ) {
    fail("DOSSIER_TAMPERED", "Le hash canonique du dossier ne correspond pas.");
  }
  return dossier;
}

function secretBuffer(secret) {
  const buffer = typeof secret === "string"
    ? Buffer.from(secret, "utf8")
    : Buffer.isBuffer(secret) || secret instanceof Uint8Array
      ? Buffer.from(secret)
      : null;
  if (!buffer || buffer.byteLength < 32) {
    fail("INVALID_SIGNING_KEY", "Une clé locale injectée d'au moins 32 octets est requise.");
  }
  return buffer;
}

function signPayload(payload, secret) {
  return createHmac("sha256", secretBuffer(secret)).update(payload, "utf8").digest();
}

function validateGrantClaims(claims) {
  assertExactKeys(
    claims,
    [
      "schema",
      "tokenId",
      "dossierHash",
      "caseId",
      "ownerId",
      "subject",
      "grantedLevel",
      "scope",
      "issuedAt",
      "expiresAt",
      "revocationId",
      "singleUse",
      "nonDelegableInvariants"
    ],
    "INVALID_GRANT",
    "grant"
  );
  if (claims.schema !== CASE_AUTONOMY.grantSchema || claims.singleUse !== true) {
    fail("INVALID_GRANT", "Le contrat du jeton est invalide.");
  }
  normalizeIdentifier(claims.tokenId, "grant.tokenId");
  normalizeIdentifier(claims.caseId, "grant.caseId");
  normalizeIdentifier(claims.ownerId, "grant.ownerId");
  normalizeIdentifier(claims.revocationId, "grant.revocationId");
  if (!/^[a-f0-9]{64}$/u.test(claims.dossierHash)) {
    fail("INVALID_GRANT", "Le hash du dossier est invalide.");
  }
  assertExactKeys(
    claims.subject,
    ["id", "principalType", "role"],
    "INVALID_GRANT",
    "grant.subject"
  );
  normalizeIdentifier(claims.subject.id, "grant.subject.id");
  if (
    claims.subject.principalType !== "AI" ||
    !CASE_AUTONOMY.aiRoles.includes(claims.subject.role)
  ) {
    fail("INVALID_GRANT", "Le sujet signé n'est pas une identité IA valide.");
  }
  if (LEVEL_INDEX.get(claims.grantedLevel) > 5 || !LEVEL_INDEX.has(claims.grantedLevel)) {
    fail("AI_SELF_ESCALATION", "Le niveau signé dépasse le plafond Owner L5.");
  }
  normalizeScope(claims.scope);
  parseInstant(claims.issuedAt, "grant.issuedAt");
  parseInstant(claims.expiresAt, "grant.expiresAt");
  if (
    !Array.isArray(claims.nonDelegableInvariants) ||
    canonicalJson(claims.nonDelegableInvariants) !==
      canonicalJson(CASE_AUTONOMY.nonDelegableInvariants)
  ) {
    fail("NON_DELEGABLE_INVARIANT_CHANGED", "Les invariants signés ont été altérés.");
  }
  return claims;
}

export function issueCaseAutonomyGrant(options) {
  assertAllowedKeys(options, ["dossier", "secret", "now"], "INVALID_OPTIONS", "options");
  const dossier = validateDossier(options.dossier);
  const nowIso = instant(options.now);
  const nowMs = Date.parse(nowIso);
  const createdAtMs = parseInstant(dossier.createdAt, "dossier.createdAt");
  if (createdAtMs > nowMs + 5_000) {
    fail("FUTURE_APPROVAL", "Le dossier provient du futur.");
  }
  if (nowMs >= parseInstant(dossier.approvalExpiresAt, "dossier.approvalExpiresAt")) {
    fail("STALE_OWNER_APPROVAL", "La validation Owner n'est plus fraîche.");
  }
  const claims = deepFreeze({
    schema: CASE_AUTONOMY.grantSchema,
    tokenId: randomUUID(),
    dossierHash: dossier.dossierHash,
    caseId: dossier.case.caseId,
    ownerId: dossier.owner.id,
    subject: {
      id: dossier.subject.id,
      principalType: dossier.subject.principalType,
      role: dossier.subject.role
    },
    grantedLevel: dossier.requestedLevel,
    scope: dossier.requestedScope,
    issuedAt: nowIso,
    expiresAt: new Date(nowMs + dossier.grantTtlSeconds * 1000).toISOString(),
    revocationId: randomUUID(),
    singleUse: true,
    nonDelegableInvariants: [...CASE_AUTONOMY.nonDelegableInvariants]
  });
  validateGrantClaims(claims);
  const payload = canonicalJson(claims);
  const signature = signPayload(payload, options.secret);
  const token = `${Buffer.from(payload, "utf8").toString("base64url")}.${signature.toString("base64url")}`;
  return deepFreeze({ token, claims });
}

function authenticateToken(token, secret) {
  if (typeof token !== "string" || token.length > 128_000) {
    fail("INVALID_TOKEN", "Jeton invalide.");
  }
  const parts = token.split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) fail("INVALID_TOKEN", "Jeton invalide.");
  let payload;
  let provided;
  try {
    payload = Buffer.from(parts[0], "base64url").toString("utf8");
    provided = Buffer.from(parts[1], "base64url");
  } catch {
    fail("INVALID_TOKEN", "Jeton invalide.");
  }
  const expected = signPayload(payload, secret);
  if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
    fail("TOKEN_TAMPERED", "La signature locale du jeton est invalide.");
  }
  let claims;
  try {
    claims = JSON.parse(payload);
  } catch {
    fail("INVALID_TOKEN", "La charge du jeton est invalide.");
  }
  validateGrantClaims(claims);
  if (payload !== canonicalJson(claims)) {
    fail("NON_CANONICAL_TOKEN", "La charge du jeton n'est pas canonique.");
  }
  return claims;
}

export function createCaseAutonomyLedger() {
  const revoked = new Map();
  const consumed = new Map();
  const ledger = Object.freeze({
    revoke(revocationId, metadata) {
      normalizeIdentifier(revocationId, "revocationId");
      assertExactKeys(metadata, ["reason", "at"], "INVALID_REVOCATION", "revocation");
      const reason = assertString(metadata.reason, "INVALID_REVOCATION", "revocation.reason", {
        max: 1024
      });
      const at = instant(metadata.at);
      if (!revoked.has(revocationId)) revoked.set(revocationId, Object.freeze({ reason, at }));
      return revoked.get(revocationId);
    },
    isRevoked(revocationId) {
      return revoked.has(revocationId);
    },
    isConsumed(tokenId) {
      return consumed.has(tokenId);
    },
    consume(tokenId, at) {
      normalizeIdentifier(tokenId, "tokenId");
      if (consumed.has(tokenId)) return false;
      consumed.set(tokenId, instant(at));
      return true;
    },
    snapshot() {
      return deepFreeze({
        revoked: [...revoked.entries()].map(([revocationId, metadata]) => ({
          revocationId,
          ...metadata
        })),
        consumed: [...consumed.entries()].map(([tokenId, at]) => ({ tokenId, at }))
      });
    }
  });
  CREATED_LEDGERS.add(ledger);
  return ledger;
}

function assertLedger(ledger) {
  if (
    !CREATED_LEDGERS.has(ledger) ||
    !ledger ||
    typeof ledger.isRevoked !== "function" ||
    typeof ledger.isConsumed !== "function" ||
    typeof ledger.consume !== "function" ||
    typeof ledger.revoke !== "function"
  ) {
    fail("LEDGER_REQUIRED", "Un registre local de révocation et d'usage est requis.");
  }
}

function normalizeExecution(execution) {
  assertExactKeys(
    execution,
    ["schema", "caseId", "subject", "scope"],
    "INVALID_EXECUTION",
    "execution"
  );
  if (execution.schema !== CASE_AUTONOMY.executionSchema) {
    fail("INVALID_EXECUTION", "Schéma d'exécution inconnu.");
  }
  assertExactKeys(
    execution.subject,
    ["id", "principalType", "role"],
    "INVALID_EXECUTION",
    "execution.subject"
  );
  const subject = {
    id: normalizeIdentifier(execution.subject.id, "execution.subject.id"),
    principalType: execution.subject.principalType,
    role: execution.subject.role
  };
  if (
    subject.principalType !== "AI" ||
    !CASE_AUTONOMY.aiRoles.includes(subject.role)
  ) {
    fail("IDENTITY_SPOOFING", "L'identité d'exécution n'est pas une IA reconnue.");
  }
  return deepFreeze({
    schema: execution.schema,
    caseId: normalizeIdentifier(execution.caseId, "execution.caseId"),
    subject,
    scope: normalizeScope(execution.scope)
  });
}

export function verifyAndConsumeCaseAutonomyGrant(options) {
  assertAllowedKeys(
    options,
    ["token", "secret", "ledger", "execution", "now"],
    "INVALID_OPTIONS",
    "options"
  );
  assertLedger(options.ledger);
  const claims = authenticateToken(options.token, options.secret);
  const execution = normalizeExecution(options.execution);
  const nowIso = instant(options.now);
  const nowMs = Date.parse(nowIso);
  if (parseInstant(claims.issuedAt, "grant.issuedAt") > nowMs + 5_000) {
    fail("TOKEN_FROM_FUTURE", "Le jeton provient du futur.");
  }
  if (nowMs >= parseInstant(claims.expiresAt, "grant.expiresAt")) {
    fail("TOKEN_EXPIRED", "Le jeton est expiré.");
  }
  if (options.ledger.isRevoked(claims.revocationId)) {
    fail("TOKEN_REVOKED", "Le mandat a été révoqué.");
  }
  if (options.ledger.isConsumed(claims.tokenId)) {
    fail("TOKEN_REPLAYED", "Le jeton à usage unique a déjà été consommé.");
  }
  if (
    execution.caseId !== claims.caseId ||
    execution.subject.id !== claims.subject.id ||
    execution.subject.principalType !== claims.subject.principalType ||
    execution.subject.role !== claims.subject.role
  ) {
    fail("IDENTITY_SPOOFING", "Le cas ou le sujet ne correspond pas au mandat signé.");
  }
  if (!scopeIsSubset(execution.scope, normalizeScope(claims.scope))) {
    fail("SCOPE_EXTENSION_REFUSED", "L'exécution étend la portée du mandat.");
  }
  if (!options.ledger.consume(claims.tokenId, nowIso)) {
    fail("TOKEN_REPLAYED", "Le jeton à usage unique a déjà été consommé.");
  }
  return deepFreeze({
    decision: "ALLOW_ONCE",
    verifiedAt: nowIso,
    tokenId: claims.tokenId,
    dossierHash: claims.dossierHash,
    caseId: claims.caseId,
    subjectId: claims.subject.id,
    grantedLevel: claims.grantedLevel,
    effectiveExecutionScope: execution.scope,
    nonDelegableInvariants: [...CASE_AUTONOMY.nonDelegableInvariants]
  });
}

export function revokeCaseAutonomyGrant(options) {
  assertAllowedKeys(
    options,
    ["token", "secret", "ledger", "reason", "now"],
    "INVALID_OPTIONS",
    "options"
  );
  assertLedger(options.ledger);
  const claims = authenticateToken(options.token, options.secret);
  const at = instant(options.now);
  const record = options.ledger.revoke(claims.revocationId, {
    reason: options.reason,
    at
  });
  return deepFreeze({
    revoked: true,
    revocationId: claims.revocationId,
    tokenId: claims.tokenId,
    ...record
  });
}
