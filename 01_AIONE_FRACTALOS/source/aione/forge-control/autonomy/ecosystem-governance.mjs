import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync,
  writeSync
} from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const REQUIRED_SUBSYSTEMS = Object.freeze([
  "project-registry",
  "goal-and-dependency-graph",
  "task-queue-and-scheduler",
  "specialized-agent-pool",
  "workflow-registry",
  "tile-context-memory",
  "resource-budget",
  "permission-overlay",
  "health-and-incidents",
  "test-and-evidence-ledger",
  "backup-and-restore",
  "owner-review-inbox"
]);

export const EXCHANGE_REQUIRED_FIELDS = Object.freeze([
  "flowId",
  "sourceEcosystemId",
  "targetEcosystemId",
  "principalId",
  "purpose",
  "offeredValue",
  "requestedValue",
  "dataClass",
  "provenance",
  "license",
  "permissionDecisionId",
  "causalClock",
  "ttl",
  "compensation"
]);

const DATA_CLASSES = new Set(["PUBLIC", "INTERNAL", "SENSITIVE", "RESTRICTED"]);
const DECISION_AUTHORITIES = new Set(["HUMAN_OWNER", "PERMISSION_BROKER"]);
const NON_FINANCIAL_UNITS = new Set([
  "capability-unit",
  "compute-unit",
  "evidence-unit",
  "knowledge-unit",
  "review-slot",
  "service-unit",
  "storage-unit",
  "workflow-unit"
]);
const FINANCIAL_KEYS = /(?:amount|currency|eur|usd|price|payment|money|cash|invoice|billing|financial)/i;
const IDENTIFIER = /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,159}$/;
const EVENT_VERSION = 1;
const MAX_TEXT = 4_000;
const MAX_TTL_SECONDS = 31 * 24 * 60 * 60;

export class GovernanceError extends Error {
  constructor(code, message, details = undefined) {
    super(message);
    this.name = "GovernanceError";
    this.code = code;
    this.details = details;
  }
}

function fail(code, message, details) {
  throw new GovernanceError(code, message, details);
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
  return createHash("sha256").update(String(value)).digest("hex");
}

function copy(value) {
  return structuredClone(value);
}

function absolutePath(value) {
  return value instanceof URL ? fileURLToPath(value) : resolve(value);
}

function nowIso(clock) {
  const value = clock();
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) fail("INVALID_CLOCK", "L'horloge doit retourner une date valide.");
  return date.toISOString();
}

function isoDate(value, field) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) fail("INVALID_DATE", `${field} doit etre une date ISO valide.`);
  return date.toISOString();
}

function text(value, field, maximum = MAX_TEXT) {
  const normalized = String(value ?? "").trim();
  if (!normalized) fail("REQUIRED_FIELD", `${field} est requis.`);
  if (normalized.length > maximum) fail("FIELD_TOO_LONG", `${field} depasse ${maximum} caracteres.`);
  return normalized;
}

function identifier(value, field) {
  const normalized = text(value, field, 160);
  if (!IDENTIFIER.test(normalized)) fail("INVALID_IDENTIFIER", `${field} contient des caracteres interdits.`);
  return normalized;
}

function stringArray(value, field, { minimum = 0, maximum = 256 } = {}) {
  if (!Array.isArray(value)) fail("INVALID_ARRAY", `${field} doit etre un tableau.`);
  const result = [...new Set(value.map((item, index) => text(item, `${field}[${index}]`, 300)))];
  if (result.length < minimum || result.length > maximum) {
    fail("INVALID_ARRAY_SIZE", `${field} doit contenir entre ${minimum} et ${maximum} valeurs.`);
  }
  return result;
}

function finiteNonNegative(value, field) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) fail("INVALID_QUANTITY", `${field} doit etre un nombre positif ou nul.`);
  return number;
}

function assertPlainObject(value, field) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail("INVALID_OBJECT", `${field} doit etre un objet.`);
  }
  return value;
}

function rejectFinancialValue(value, field, seen = new Set()) {
  if (value === null || value === undefined) return;
  if (typeof value !== "object") return;
  if (seen.has(value)) fail("CYCLIC_VALUE", `${field} ne peut pas etre cyclique.`);
  seen.add(value);
  for (const [key, nested] of Object.entries(value)) {
    if (FINANCIAL_KEYS.test(key)) {
      fail("FINANCIAL_VALUE_DENIED", `${field}.${key} est interdit: les echanges sont non financiers.`);
    }
    rejectFinancialValue(nested, `${field}.${key}`, seen);
  }
  seen.delete(value);
}

function normalizeNonFinancialValue(value, field) {
  const candidate = assertPlainObject(value, field);
  rejectFinancialValue(candidate, field);
  const kind = text(candidate.kind, `${field}.kind`, 120);
  const quantity = finiteNonNegative(candidate.quantity, `${field}.quantity`);
  const unit = text(candidate.unit, `${field}.unit`, 80);
  if (!NON_FINANCIAL_UNITS.has(unit)) {
    fail("INVALID_VALUE_UNIT", `${field}.unit n'est pas une unite non financiere autorisee.`);
  }
  return {
    kind,
    quantity,
    unit,
    description: String(candidate.description ?? "").trim().slice(0, 1_000),
    constraints: copy(candidate.constraints ?? {})
  };
}

function normalizeResourceVector(value, field, knownResources, { requirePositive = false } = {}) {
  const input = assertPlainObject(value, field);
  const result = {};
  for (const [resource, quantity] of Object.entries(input)) {
    identifier(resource, `${field}.${resource}`);
    if (!knownResources.has(resource)) fail("UNKNOWN_RESOURCE", `${resource} n'est pas une ressource gouvernee.`);
    result[resource] = finiteNonNegative(quantity, `${field}.${resource}`);
  }
  if (requirePositive && !Object.values(result).some((quantity) => quantity > 0)) {
    fail("EMPTY_RESOURCE_REQUEST", `${field} doit demander au moins une ressource.`);
  }
  return result;
}

function priorityScore(priority) {
  if (Number.isFinite(Number(priority))) return Number(priority);
  const match = /^P([0-9])$/.exec(String(priority ?? "").toUpperCase());
  return match ? 1_000 - Number(match[1]) * 100 : 0;
}

function initialEcosystemState(definition) {
  return {
    id: definition.id,
    name: definition.name,
    mission: definition.mission,
    domains: copy(definition.domains),
    orchestratorRole: definition.orchestratorRole,
    exchangeOffers: copy(definition.exchangeOffers ?? []),
    projectRegistry: {},
    goalDependencyGraph: { goals: {}, dependencies: [] },
    taskQueueAndScheduler: [],
    specializedAgentPool: {},
    workflowRegistry: {},
    tileContextMemory: [],
    resourceBudget: { limits: {}, allocated: {} },
    permissionOverlay: { decisions: {} },
    healthAndIncidents: { status: "UNKNOWN", checkedAt: null, incidents: [] },
    testAndEvidenceLedger: [],
    backupAndRestore: { records: [] },
    ownerReviewInbox: [],
    valueExchange: { offers: [], demands: [], inbox: [], outbox: [], quarantine: [] }
  };
}

function initialState(config, globalCapacity) {
  return {
    schema: "aione.ecosystem-governance-state.v1",
    federation: {
      id: config.federation.id,
      governor: config.federation.governor,
      globalCapacity: copy(globalCapacity),
      resourceRequests: [],
      allocations: [],
      exchangeFlowIndex: {},
      causalHeads: {},
      quarantine: []
    },
    ecosystems: Object.fromEntries(config.ecosystems.map((ecosystem) => [
      ecosystem.id,
      initialEcosystemState(ecosystem)
    ])),
    ledger: { sequence: 0, headHash: "GENESIS" }
  };
}

function eventBody(event) {
  const { hash: _hash, ...body } = event;
  return body;
}

function applyEvent(state, event) {
  const ecosystem = event.ecosystemId ? state.ecosystems[event.ecosystemId] : null;
  const payload = copy(event.payload);
  switch (event.type) {
    case "PROJECT_UPSERTED":
      ecosystem.projectRegistry[payload.id] = payload;
      break;
    case "GOAL_UPSERTED":
      ecosystem.goalDependencyGraph.goals[payload.id] = payload;
      break;
    case "DEPENDENCY_RECORDED":
      if (!ecosystem.goalDependencyGraph.dependencies.some((entry) => entry.id === payload.id)) {
        ecosystem.goalDependencyGraph.dependencies.push(payload);
      }
      break;
    case "TASK_ENQUEUED":
      if (!ecosystem.taskQueueAndScheduler.some((entry) => entry.id === payload.id)) {
        ecosystem.taskQueueAndScheduler.push(payload);
      }
      break;
    case "AGENT_REGISTERED":
      ecosystem.specializedAgentPool[payload.id] = payload;
      break;
    case "WORKFLOW_REGISTERED":
      ecosystem.workflowRegistry[payload.id] = payload;
      break;
    case "MEMORY_APPENDED":
      ecosystem.tileContextMemory.push(payload);
      break;
    case "RESOURCE_BUDGET_SET":
      ecosystem.resourceBudget.limits = payload.limits;
      break;
    case "PERMISSION_RECORDED":
      ecosystem.permissionOverlay.decisions[payload.permissionDecisionId] = payload;
      break;
    case "HEALTH_REPORTED":
      ecosystem.healthAndIncidents.status = payload.status;
      ecosystem.healthAndIncidents.checkedAt = payload.checkedAt;
      ecosystem.healthAndIncidents.details = payload.details;
      break;
    case "INCIDENT_RECORDED":
      ecosystem.healthAndIncidents.incidents.push(payload);
      break;
    case "EVIDENCE_RECORDED":
      ecosystem.testAndEvidenceLedger.push(payload);
      break;
    case "BACKUP_RECORDED":
      ecosystem.backupAndRestore.records.push(payload);
      break;
    case "OWNER_REVIEW_RECORDED":
      ecosystem.ownerReviewInbox.push(payload);
      break;
    case "VALUE_OFFERED":
      ecosystem.valueExchange.offers.push(payload);
      break;
    case "VALUE_DEMANDED":
      ecosystem.valueExchange.demands.push(payload);
      break;
    case "RESOURCE_REQUESTED":
      state.federation.resourceRequests.push(payload);
      break;
    case "RESOURCE_ARBITRATED":
      for (const decision of payload.decisions) {
        const request = state.federation.resourceRequests.find((entry) => entry.requestId === decision.requestId);
        if (request) {
          request.status = decision.status;
          request.decisionReason = decision.reason;
          request.decidedAt = payload.decidedAt;
        }
        if (decision.status === "GRANTED") {
          const allocation = {
            allocationId: decision.allocationId,
            requestId: decision.requestId,
            ecosystemId: decision.ecosystemId,
            resources: decision.resources,
            status: "ACTIVE",
            createdAt: payload.decidedAt
          };
          state.federation.allocations.push(allocation);
          const target = state.ecosystems[decision.ecosystemId];
          for (const [resource, quantity] of Object.entries(decision.resources)) {
            target.resourceBudget.allocated[resource] =
              Number(target.resourceBudget.allocated[resource] ?? 0) + quantity;
          }
        }
      }
      break;
    case "RESOURCES_RELEASED": {
      const allocation = state.federation.allocations.find((entry) => entry.allocationId === payload.allocationId);
      if (allocation && allocation.status === "ACTIVE") {
        allocation.status = "RELEASED";
        allocation.releasedAt = payload.releasedAt;
        const target = state.ecosystems[allocation.ecosystemId];
        for (const [resource, quantity] of Object.entries(allocation.resources)) {
          target.resourceBudget.allocated[resource] =
            Math.max(0, Number(target.resourceBudget.allocated[resource] ?? 0) - quantity);
        }
      }
      break;
    }
    case "EXCHANGE_ACCEPTED": {
      const { contract, receipt, contractHash } = payload;
      const source = state.ecosystems[contract.sourceEcosystemId];
      const target = state.ecosystems[contract.targetEcosystemId];
      source.valueExchange.outbox.push({ contract, receipt });
      target.valueExchange.inbox.push({ contract, receipt });
      state.federation.exchangeFlowIndex[contract.flowId] = { contractHash, receipt };
      state.federation.causalHeads[`${contract.sourceEcosystemId}->${contract.targetEcosystemId}`] =
        contract.causalClock.sourceCounter;
      break;
    }
    case "EXCHANGE_QUARANTINED": {
      state.federation.quarantine.push(payload);
      const source = state.ecosystems[payload.sourceEcosystemId];
      if (source) source.valueExchange.quarantine.push(payload);
      break;
    }
    default:
      fail("UNKNOWN_EVENT_TYPE", `Type d'evenement inconnu: ${event.type}`);
  }
  state.ledger.sequence = event.sequence;
  state.ledger.headHash = event.hash;
}

export function validateEcosystemDomains(value) {
  const config = assertPlainObject(value, "configuration");
  if (config.schema !== "aione.ecosystem-domains.v1") {
    fail("INVALID_CONFIG_SCHEMA", "Le schema ecosystem-domains doit etre aione.ecosystem-domains.v1.");
  }
  assertPlainObject(config.federation, "federation");
  identifier(config.federation.id, "federation.id");
  text(config.federation.governor, "federation.governor", 160);
  const mustNot = new Set(stringArray(config.federation.mustNot, "federation.mustNot", { minimum: 1 }));
  for (const invariant of [
    "implicit-cross-ecosystem-read",
    "implicit-permission-transfer",
    "routine-project-micromanagement",
    "ai-self-escalation"
  ]) {
    if (!mustNot.has(invariant)) fail("MISSING_GOVERNANCE_INVARIANT", `Invariant manquant: ${invariant}`);
  }

  const subsystems = new Set(stringArray(
    config.requiredSubsystemsPerEcosystem,
    "requiredSubsystemsPerEcosystem",
    { minimum: REQUIRED_SUBSYSTEMS.length }
  ));
  for (const subsystem of REQUIRED_SUBSYSTEMS) {
    if (!subsystems.has(subsystem)) fail("MISSING_SUBSYSTEM", `Sous-systeme requis manquant: ${subsystem}`);
  }

  if (!Array.isArray(config.ecosystems) || config.ecosystems.length < 1) {
    fail("MISSING_ECOSYSTEMS", "Au moins un ecosysteme est requis.");
  }
  const ids = new Set();
  const ecosystems = config.ecosystems.map((candidate, index) => {
    const ecosystem = assertPlainObject(candidate, `ecosystems[${index}]`);
    const id = identifier(ecosystem.id, `ecosystems[${index}].id`);
    if (ids.has(id)) fail("DUPLICATE_ECOSYSTEM", `Ecosysteme duplique: ${id}`);
    ids.add(id);
    return {
      id,
      name: text(ecosystem.name, `ecosystems[${index}].name`, 300),
      orchestratorRole: text(ecosystem.orchestratorRole, `ecosystems[${index}].orchestratorRole`, 160),
      mission: text(ecosystem.mission, `ecosystems[${index}].mission`, 2_000),
      domains: stringArray(ecosystem.domains, `ecosystems[${index}].domains`, { minimum: 1 }),
      exchangeOffers: stringArray(ecosystem.exchangeOffers ?? [], `ecosystems[${index}].exchangeOffers`),
      safetyNote: String(ecosystem.safetyNote ?? "").slice(0, 1_000)
    };
  });

  const exchange = assertPlainObject(config.exchangeContract, "exchangeContract");
  if (exchange.defaultDecision !== "DENY") fail("UNSAFE_EXCHANGE_DEFAULT", "exchangeContract.defaultDecision doit rester DENY.");
  if (exchange.missingOrInvalid !== "QUARANTINE") {
    fail("UNSAFE_INVALID_EXCHANGE_POLICY", "Les contrats manquants ou invalides doivent aller en QUARANTINE.");
  }
  const requiredFields = new Set(stringArray(exchange.requiredFields, "exchangeContract.requiredFields"));
  for (const field of EXCHANGE_REQUIRED_FIELDS) {
    if (!requiredFields.has(field)) fail("MISSING_EXCHANGE_FIELD", `Champ d'echange requis manquant: ${field}`);
  }

  return {
    schema: config.schema,
    updatedAt: config.updatedAt ? isoDate(config.updatedAt, "updatedAt") : null,
    status: String(config.status ?? "UNKNOWN"),
    federation: {
      id: config.federation.id,
      governor: config.federation.governor,
      responsibilities: stringArray(config.federation.responsibilities ?? [], "federation.responsibilities"),
      mustNot: [...mustNot]
    },
    requiredSubsystemsPerEcosystem: [...subsystems],
    ecosystems,
    exchangeContract: {
      defaultDecision: "DENY",
      requiredFields: [...requiredFields],
      missingOrInvalid: "QUARANTINE"
    }
  };
}

export function loadEcosystemDomains(configPath) {
  const resolvedPath = absolutePath(configPath);
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(resolvedPath, "utf8"));
  } catch (error) {
    fail("CONFIG_READ_FAILED", `Impossible de charger ${resolvedPath}: ${error.message}`);
  }
  return validateEcosystemDomains(parsed);
}

export class EcosystemGovernance {
  constructor({
    configPath,
    storageDirectory,
    globalCapacity = {
      cpuUnits: 100,
      gpuUnits: 100,
      ramUnits: 100,
      storageUnits: 100
    },
    clock = () => new Date(),
    faultInjector = null
  } = {}) {
    if (!configPath) fail("CONFIG_PATH_REQUIRED", "configPath est requis.");
    if (!storageDirectory) fail("STORAGE_PATH_REQUIRED", "storageDirectory est requis.");
    this.configPath = absolutePath(configPath);
    this.storageDirectory = absolutePath(storageDirectory);
    this.eventsDirectory = join(this.storageDirectory, "events");
    this.stagingDirectory = join(this.storageDirectory, ".staging");
    this.snapshotPath = join(this.storageDirectory, "state.snapshot.json");
    this.clock = clock;
    this.faultInjector = typeof faultInjector === "function" ? faultInjector : null;
    this.config = loadEcosystemDomains(this.configPath);
    this.governorId = this.config.federation.governor;
    const resources = assertPlainObject(globalCapacity, "globalCapacity");
    this.globalCapacity = Object.fromEntries(Object.entries(resources).map(([resource, quantity]) => [
      identifier(resource, `globalCapacity.${resource}`),
      finiteNonNegative(quantity, `globalCapacity.${resource}`)
    ]));
    if (Object.keys(this.globalCapacity).length < 1) fail("EMPTY_GLOBAL_CAPACITY", "globalCapacity ne peut pas etre vide.");
    this.knownResources = new Set(Object.keys(this.globalCapacity));
    mkdirSync(this.eventsDirectory, { recursive: true });
    mkdirSync(this.stagingDirectory, { recursive: true });
    this.state = initialState(this.config, this.globalCapacity);
    this.#replayEvents();
    this.#writeSnapshot();
  }

  #eventFiles() {
    return readdirSync(this.eventsDirectory)
      .filter((name) => /^\d{12}-[a-f0-9]{16}\.json$/.test(name))
      .sort();
  }

  #replayEvents() {
    let expectedSequence = 1;
    let previousHash = "GENESIS";
    for (const fileName of this.#eventFiles()) {
      let event;
      try {
        event = JSON.parse(readFileSync(join(this.eventsDirectory, fileName), "utf8"));
      } catch (error) {
        fail("CORRUPT_EVENT", `Evenement illisible ${fileName}: ${error.message}`);
      }
      if (event.version !== EVENT_VERSION) fail("EVENT_VERSION_MISMATCH", `Version d'evenement invalide dans ${fileName}.`);
      if (event.sequence !== expectedSequence) fail("EVENT_SEQUENCE_GAP", `Sequence attendue ${expectedSequence}, recue ${event.sequence}.`);
      if (event.previousHash !== previousHash) fail("EVENT_CHAIN_BROKEN", `Chaine de preuve rompue a ${fileName}.`);
      const calculated = sha256(stableJson(eventBody(event)));
      if (calculated !== event.hash) fail("EVENT_HASH_MISMATCH", `Empreinte invalide dans ${fileName}.`);
      if (event.ecosystemId && !this.state.ecosystems[event.ecosystemId]) {
        fail("ORPHAN_EVENT", `L'evenement ${fileName} vise un ecosysteme absent de la configuration.`);
      }
      applyEvent(this.state, event);
      expectedSequence += 1;
      previousHash = event.hash;
    }
  }

  #writeSnapshot() {
    const temporary = join(this.stagingDirectory, `snapshot-${process.pid}-${randomUUID()}.tmp`);
    writeFileSync(temporary, `${JSON.stringify(this.state, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
    renameSync(temporary, this.snapshotPath);
  }

  #commit(type, ecosystemId, payload) {
    if (ecosystemId) this.#ecosystem(ecosystemId);
    const diskFiles = this.#eventFiles();
    if (diskFiles.length !== this.state.ledger.sequence) {
      fail("CONCURRENT_MODIFICATION", "Le journal a change. Rouvrir le gouverneur avant de continuer.");
    }
    const body = {
      version: EVENT_VERSION,
      sequence: this.state.ledger.sequence + 1,
      eventId: randomUUID(),
      timestamp: nowIso(this.clock),
      type,
      ecosystemId: ecosystemId ?? null,
      payload: copy(payload),
      previousHash: this.state.ledger.headHash
    };
    const event = { ...body, hash: sha256(stableJson(body)) };
    const fileName = `${String(event.sequence).padStart(12, "0")}-${event.hash.slice(0, 16)}.json`;
    const temporary = join(this.stagingDirectory, `${fileName}.${process.pid}.${randomUUID()}.tmp`);
    const descriptor = openSync(temporary, "wx");
    try {
      writeSync(descriptor, `${JSON.stringify(event)}\n`, null, "utf8");
      fsyncSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
    renameSync(temporary, join(this.eventsDirectory, fileName));
    this.faultInjector?.("event-written", copy(event));
    applyEvent(this.state, event);
    this.faultInjector?.("state-applied", copy(event));
    this.#writeSnapshot();
    return copy(event);
  }

  #ecosystem(ecosystemId) {
    const id = identifier(ecosystemId, "ecosystemId");
    const ecosystem = this.state.ecosystems[id];
    if (!ecosystem) fail("UNKNOWN_ECOSYSTEM", `Ecosysteme inconnu: ${id}`);
    return ecosystem;
  }

  #existingById(collection, id, field = "id") {
    return Array.isArray(collection)
      ? collection.find((entry) => entry[field] === id)
      : collection[id];
  }

  #upsertMapEvent(type, ecosystemId, collection, item, field = "id") {
    const existing = this.#existingById(collection, item[field], field);
    if (existing && stableJson(existing) === stableJson(item)) return { status: "UNCHANGED", value: copy(existing) };
    this.#commit(type, ecosystemId, item);
    return { status: existing ? "UPDATED" : "CREATED", value: copy(item) };
  }

  getFederationMap() {
    return {
      federationId: this.state.federation.id,
      governor: this.state.federation.governor,
      globalCapacity: copy(this.state.federation.globalCapacity),
      activeAllocations: this.state.federation.allocations
        .filter((entry) => entry.status === "ACTIVE")
        .map(({ ecosystemId, resources }) => ({ ecosystemId, resources: copy(resources) })),
      ecosystems: Object.values(this.state.ecosystems).map((ecosystem) => ({
        id: ecosystem.id,
        name: ecosystem.name,
        orchestratorRole: ecosystem.orchestratorRole,
        health: ecosystem.healthAndIncidents.status,
        projectCount: Object.keys(ecosystem.projectRegistry).length,
        queuedTaskCount: ecosystem.taskQueueAndScheduler.filter((entry) => entry.status === "QUEUED").length,
        agentCount: Object.keys(ecosystem.specializedAgentPool).length,
        workflowCount: Object.keys(ecosystem.workflowRegistry).length,
        activeIncidentCount: ecosystem.healthAndIncidents.incidents.filter((entry) => entry.status !== "RESOLVED").length,
        resourceBudget: copy(ecosystem.resourceBudget)
      })),
      ledger: copy(this.state.ledger)
    };
  }

  readEcosystem(requesterEcosystemId, targetEcosystemId, access = {}) {
    const requester = this.#ecosystem(requesterEcosystemId);
    const target = this.#ecosystem(targetEcosystemId);
    if (requester.id === target.id) return copy(target);
    const permissionDecisionId = String(access.permissionDecisionId ?? "").trim();
    const principalId = String(access.principalId ?? "").trim();
    if (!permissionDecisionId || !principalId) {
      fail("IMPLICIT_CROSS_READ_DENIED", "Toute lecture inter-ecosysteme exige une decision de permission explicite.");
    }
    const decision = target.permissionOverlay.decisions[permissionDecisionId];
    if (!this.#permissionAllows(decision, {
      principalId,
      action: "ecosystem.read",
      sourceEcosystemId: target.id,
      targetEcosystemId: requester.id
    })) {
      fail("CROSS_READ_DENIED", "La decision ne permet pas cette lecture inter-ecosysteme.");
    }
    return copy(target);
  }

  upsertProject(ecosystemId, project) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(project, "project");
    const normalized = {
      id: identifier(candidate.id, "project.id"),
      name: text(candidate.name, "project.name", 300),
      status: text(candidate.status ?? "ACTIVE", "project.status", 80),
      objective: text(candidate.objective, "project.objective", 2_000),
      ownerPrincipalId: identifier(candidate.ownerPrincipalId, "project.ownerPrincipalId"),
      updatedAt: candidate.updatedAt ? isoDate(candidate.updatedAt, "project.updatedAt") : nowIso(this.clock),
      metadata: copy(candidate.metadata ?? {})
    };
    return this.#upsertMapEvent("PROJECT_UPSERTED", ecosystemId, ecosystem.projectRegistry, normalized);
  }

  upsertGoal(ecosystemId, goal) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(goal, "goal");
    const normalized = {
      id: identifier(candidate.id, "goal.id"),
      projectId: identifier(candidate.projectId, "goal.projectId"),
      objective: text(candidate.objective, "goal.objective", 2_000),
      status: text(candidate.status ?? "PLANNED", "goal.status", 80)
    };
    if (!ecosystem.projectRegistry[normalized.projectId]) fail("UNKNOWN_PROJECT", "Le but doit viser un projet enregistre.");
    return this.#upsertMapEvent("GOAL_UPSERTED", ecosystemId, ecosystem.goalDependencyGraph.goals, normalized);
  }

  recordDependency(ecosystemId, dependency) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(dependency, "dependency");
    const normalized = {
      id: identifier(candidate.id, "dependency.id"),
      fromGoalId: identifier(candidate.fromGoalId, "dependency.fromGoalId"),
      toGoalId: identifier(candidate.toGoalId, "dependency.toGoalId"),
      kind: text(candidate.kind ?? "REQUIRES", "dependency.kind", 80)
    };
    if (!ecosystem.goalDependencyGraph.goals[normalized.fromGoalId] ||
        !ecosystem.goalDependencyGraph.goals[normalized.toGoalId]) {
      fail("UNKNOWN_GOAL", "Les deux buts de la dependance doivent exister.");
    }
    if (normalized.fromGoalId === normalized.toGoalId) fail("SELF_DEPENDENCY", "Un but ne peut pas dependre de lui-meme.");
    const existing = this.#existingById(ecosystem.goalDependencyGraph.dependencies, normalized.id);
    if (existing) {
      if (stableJson(existing) === stableJson(normalized)) return { status: "UNCHANGED", value: copy(existing) };
      fail("IMMUTABLE_ID_CONFLICT", `La dependance ${normalized.id} existe avec un autre contenu.`);
    }
    this.#commit("DEPENDENCY_RECORDED", ecosystemId, normalized);
    return { status: "CREATED", value: normalized };
  }

  enqueueTask(ecosystemId, task) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(task, "task");
    const normalized = {
      id: identifier(candidate.id, "task.id"),
      projectId: identifier(candidate.projectId, "task.projectId"),
      title: text(candidate.title, "task.title", 500),
      priority: text(candidate.priority ?? "P2", "task.priority", 20),
      status: "QUEUED",
      workflowId: candidate.workflowId ? identifier(candidate.workflowId, "task.workflowId") : null,
      notBefore: candidate.notBefore ? isoDate(candidate.notBefore, "task.notBefore") : nowIso(this.clock),
      createdAt: nowIso(this.clock)
    };
    if (!ecosystem.projectRegistry[normalized.projectId]) fail("UNKNOWN_PROJECT", "La tache doit viser un projet enregistre.");
    const existing = this.#existingById(ecosystem.taskQueueAndScheduler, normalized.id);
    if (existing) return { status: "DUPLICATE", value: copy(existing) };
    this.#commit("TASK_ENQUEUED", ecosystemId, normalized);
    return { status: "QUEUED", value: normalized };
  }

  registerAgent(ecosystemId, agent) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(agent, "agent");
    const normalized = {
      id: identifier(candidate.id, "agent.id"),
      role: text(candidate.role, "agent.role", 160),
      capabilities: stringArray(candidate.capabilities ?? [], "agent.capabilities"),
      status: text(candidate.status ?? "AVAILABLE", "agent.status", 80),
      permissionCeiling: stringArray(candidate.permissionCeiling ?? [], "agent.permissionCeiling")
    };
    return this.#upsertMapEvent("AGENT_REGISTERED", ecosystemId, ecosystem.specializedAgentPool, normalized);
  }

  registerWorkflow(ecosystemId, workflow) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(workflow, "workflow");
    const normalized = {
      id: identifier(candidate.id, "workflow.id"),
      name: text(candidate.name, "workflow.name", 300),
      steps: stringArray(candidate.steps, "workflow.steps", { minimum: 1 }),
      version: text(candidate.version ?? "1", "workflow.version", 40),
      status: text(candidate.status ?? "ACTIVE", "workflow.status", 80)
    };
    return this.#upsertMapEvent("WORKFLOW_REGISTERED", ecosystemId, ecosystem.workflowRegistry, normalized);
  }

  appendMemory(ecosystemId, memory) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(memory, "memory");
    const normalized = {
      id: identifier(candidate.id, "memory.id"),
      level: text(candidate.level, "memory.level", 40),
      perspective: text(candidate.perspective, "memory.perspective", 80),
      subject: text(candidate.subject, "memory.subject", 300),
      reconstruction: text(candidate.reconstruction, "memory.reconstruction", MAX_TEXT),
      sourceRefs: stringArray(candidate.sourceRefs ?? [], "memory.sourceRefs"),
      recordedAt: candidate.recordedAt ? isoDate(candidate.recordedAt, "memory.recordedAt") : nowIso(this.clock)
    };
    const existing = this.#existingById(ecosystem.tileContextMemory, normalized.id);
    if (existing) {
      if (stableJson(existing) === stableJson(normalized)) return { status: "UNCHANGED", value: copy(existing) };
      fail("IMMUTABLE_ID_CONFLICT", `La memoire ${normalized.id} est append-only.`);
    }
    this.#commit("MEMORY_APPENDED", ecosystemId, normalized);
    return { status: "APPENDED", value: normalized };
  }

  setResourceBudget(ecosystemId, limits) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const normalized = normalizeResourceVector(limits, "limits", this.knownResources);
    for (const resource of this.knownResources) {
      const allocated = Number(ecosystem.resourceBudget.allocated[resource] ?? 0);
      if (Number(normalized[resource] ?? 0) < allocated) {
        fail("BUDGET_BELOW_ALLOCATION", `Le budget ${resource} ne peut pas passer sous l'allocation active.`);
      }
    }
    if (stableJson(ecosystem.resourceBudget.limits) === stableJson(normalized)) {
      return { status: "UNCHANGED", limits: copy(normalized) };
    }
    this.#commit("RESOURCE_BUDGET_SET", ecosystemId, { limits: normalized });
    return { status: "UPDATED", limits: copy(normalized) };
  }

  recordPermissionDecision(ecosystemId, decision) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(decision, "decision");
    const normalized = {
      permissionDecisionId: identifier(candidate.permissionDecisionId, "decision.permissionDecisionId"),
      principalId: identifier(candidate.principalId, "decision.principalId"),
      authority: text(candidate.authority, "decision.authority", 80),
      issuedBy: identifier(candidate.issuedBy, "decision.issuedBy"),
      decision: text(candidate.decision, "decision.decision", 20).toUpperCase(),
      actions: stringArray(candidate.actions, "decision.actions", { minimum: 1 }),
      sourceEcosystemId: identifier(candidate.sourceEcosystemId ?? ecosystemId, "decision.sourceEcosystemId"),
      targetEcosystemIds: stringArray(candidate.targetEcosystemIds, "decision.targetEcosystemIds", { minimum: 1 }),
      allowedDataClasses: stringArray(candidate.allowedDataClasses ?? [], "decision.allowedDataClasses"),
      allowedLicenses: stringArray(candidate.allowedLicenses ?? [], "decision.allowedLicenses"),
      validFrom: candidate.validFrom ? isoDate(candidate.validFrom, "decision.validFrom") : nowIso(this.clock),
      expiresAt: isoDate(candidate.expiresAt, "decision.expiresAt"),
      reason: text(candidate.reason, "decision.reason", 1_000)
    };
    if (!DECISION_AUTHORITIES.has(normalized.authority)) {
      fail("UNTRUSTED_PERMISSION_AUTHORITY", "Une IA ou un agent ne peut pas emettre sa propre permission.");
    }
    if (!["ALLOW", "DENY"].includes(normalized.decision)) fail("INVALID_PERMISSION_DECISION", "decision doit valoir ALLOW ou DENY.");
    if (normalized.sourceEcosystemId !== ecosystemId) {
      fail("PERMISSION_SCOPE_MISMATCH", "La decision doit etre conservee dans son ecosysteme source.");
    }
    for (const target of normalized.targetEcosystemIds) this.#ecosystem(target);
    if (new Date(normalized.expiresAt) <= new Date(normalized.validFrom)) {
      fail("INVALID_PERMISSION_WINDOW", "expiresAt doit etre posterieur a validFrom.");
    }
    const existing = ecosystem.permissionOverlay.decisions[normalized.permissionDecisionId];
    if (existing) {
      if (stableJson(existing) === stableJson(normalized)) return { status: "UNCHANGED", decision: copy(existing) };
      fail("IMMUTABLE_PERMISSION_CONFLICT", "Une decision de permission existante ne peut pas etre remplacee.");
    }
    this.#commit("PERMISSION_RECORDED", ecosystemId, normalized);
    return { status: "RECORDED", decision: normalized };
  }

  #permissionAllows(decision, { principalId, action, sourceEcosystemId, targetEcosystemId, dataClass, license }) {
    if (!decision || decision.decision !== "ALLOW") return false;
    if (decision.principalId !== principalId) return false;
    if (decision.sourceEcosystemId !== sourceEcosystemId) return false;
    if (!decision.targetEcosystemIds.includes(targetEcosystemId)) return false;
    if (!decision.actions.includes(action)) return false;
    const current = new Date(nowIso(this.clock)).getTime();
    if (current < new Date(decision.validFrom).getTime() || current >= new Date(decision.expiresAt).getTime()) return false;
    if (dataClass && !decision.allowedDataClasses.includes(dataClass) && !decision.allowedDataClasses.includes("*")) return false;
    if (license && !decision.allowedLicenses.includes(license) && !decision.allowedLicenses.includes("*")) return false;
    return true;
  }

  reportHealth(ecosystemId, health) {
    this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(health, "health");
    const normalized = {
      status: text(candidate.status, "health.status", 80),
      checkedAt: candidate.checkedAt ? isoDate(candidate.checkedAt, "health.checkedAt") : nowIso(this.clock),
      details: copy(candidate.details ?? {})
    };
    this.#commit("HEALTH_REPORTED", ecosystemId, normalized);
    return normalized;
  }

  recordIncident(ecosystemId, incident) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(incident, "incident");
    const normalized = {
      id: identifier(candidate.id, "incident.id"),
      signature: text(candidate.signature, "incident.signature", 300),
      severity: text(candidate.severity, "incident.severity", 40),
      status: text(candidate.status ?? "OPEN", "incident.status", 40),
      summary: text(candidate.summary, "incident.summary", 2_000),
      evidenceRefs: stringArray(candidate.evidenceRefs ?? [], "incident.evidenceRefs"),
      recordedAt: nowIso(this.clock)
    };
    const existing = this.#existingById(ecosystem.healthAndIncidents.incidents, normalized.id);
    if (existing) return { status: "DUPLICATE", incident: copy(existing) };
    this.#commit("INCIDENT_RECORDED", ecosystemId, normalized);
    return { status: "RECORDED", incident: normalized };
  }

  recordEvidence(ecosystemId, evidence) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(evidence, "evidence");
    const normalized = {
      id: identifier(candidate.id, "evidence.id"),
      kind: text(candidate.kind, "evidence.kind", 120),
      result: text(candidate.result, "evidence.result", 80),
      checksum: text(candidate.checksum, "evidence.checksum", 160),
      sourceRefs: stringArray(candidate.sourceRefs ?? [], "evidence.sourceRefs"),
      recordedAt: nowIso(this.clock)
    };
    const existing = this.#existingById(ecosystem.testAndEvidenceLedger, normalized.id);
    if (existing) return { status: "DUPLICATE", evidence: copy(existing) };
    this.#commit("EVIDENCE_RECORDED", ecosystemId, normalized);
    return { status: "RECORDED", evidence: normalized };
  }

  recordBackup(ecosystemId, backup) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(backup, "backup");
    const normalized = {
      id: identifier(candidate.id, "backup.id"),
      locationRef: text(candidate.locationRef, "backup.locationRef", 1_000),
      checksum: text(candidate.checksum, "backup.checksum", 160),
      restoreTest: text(candidate.restoreTest ?? "NOT_TESTED", "backup.restoreTest", 80),
      createdAt: nowIso(this.clock)
    };
    const existing = this.#existingById(ecosystem.backupAndRestore.records, normalized.id);
    if (existing) return { status: "DUPLICATE", backup: copy(existing) };
    this.#commit("BACKUP_RECORDED", ecosystemId, normalized);
    return { status: "RECORDED", backup: normalized };
  }

  submitOwnerReview(ecosystemId, review) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(review, "review");
    const normalized = {
      id: identifier(candidate.id, "review.id"),
      projectId: identifier(candidate.projectId, "review.projectId"),
      title: text(candidate.title, "review.title", 500),
      status: text(candidate.status ?? "AWAITING_OWNER", "review.status", 80),
      dossierRef: text(candidate.dossierRef, "review.dossierRef", 1_000),
      evidenceRefs: stringArray(candidate.evidenceRefs ?? [], "review.evidenceRefs"),
      createdAt: nowIso(this.clock)
    };
    if (!ecosystem.projectRegistry[normalized.projectId]) fail("UNKNOWN_PROJECT", "La revue doit viser un projet enregistre.");
    const existing = this.#existingById(ecosystem.ownerReviewInbox, normalized.id);
    if (existing) return { status: "DUPLICATE", review: copy(existing) };
    this.#commit("OWNER_REVIEW_RECORDED", ecosystemId, normalized);
    return { status: "RECORDED", review: normalized };
  }

  publishValueOffer(ecosystemId, offer) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(offer, "offer");
    const normalized = {
      id: identifier(candidate.id, "offer.id"),
      value: normalizeNonFinancialValue(candidate.value, "offer.value"),
      availableUntil: isoDate(candidate.availableUntil, "offer.availableUntil"),
      constraints: copy(candidate.constraints ?? {}),
      createdAt: nowIso(this.clock)
    };
    rejectFinancialValue(normalized.constraints, "offer.constraints");
    const existing = this.#existingById(ecosystem.valueExchange.offers, normalized.id);
    if (existing) return { status: "DUPLICATE", offer: copy(existing) };
    this.#commit("VALUE_OFFERED", ecosystemId, normalized);
    return { status: "PUBLISHED", offer: normalized };
  }

  publishValueDemand(ecosystemId, demand) {
    const ecosystem = this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(demand, "demand");
    const normalized = {
      id: identifier(candidate.id, "demand.id"),
      value: normalizeNonFinancialValue(candidate.value, "demand.value"),
      neededBy: isoDate(candidate.neededBy, "demand.neededBy"),
      purpose: text(candidate.purpose, "demand.purpose", 1_000),
      createdAt: nowIso(this.clock)
    };
    const existing = this.#existingById(ecosystem.valueExchange.demands, normalized.id);
    if (existing) return { status: "DUPLICATE", demand: copy(existing) };
    this.#commit("VALUE_DEMANDED", ecosystemId, normalized);
    return { status: "PUBLISHED", demand: normalized };
  }

  requestResources(ecosystemId, request) {
    this.#ecosystem(ecosystemId);
    const candidate = assertPlainObject(request, "request");
    const normalized = {
      requestId: identifier(candidate.requestId, "request.requestId"),
      ecosystemId,
      resources: normalizeResourceVector(candidate.resources, "request.resources", this.knownResources, { requirePositive: true }),
      priority: text(candidate.priority ?? "P2", "request.priority", 20),
      reason: text(candidate.reason, "request.reason", 1_000),
      status: "PENDING",
      createdAt: nowIso(this.clock)
    };
    const existing = this.#existingById(this.state.federation.resourceRequests, normalized.requestId, "requestId");
    if (existing) {
      if (stableJson(existing.resources) === stableJson(normalized.resources) && existing.ecosystemId === ecosystemId) {
        return { status: "DUPLICATE", request: copy(existing) };
      }
      fail("RESOURCE_REQUEST_ID_CONFLICT", "requestId existe avec un autre contenu.");
    }
    this.#commit("RESOURCE_REQUESTED", ecosystemId, normalized);
    return { status: "PENDING", request: normalized };
  }

  arbitrateResources() {
    const pending = this.state.federation.resourceRequests
      .filter((request) => request.status === "PENDING")
      .sort((left, right) =>
        priorityScore(right.priority) - priorityScore(left.priority) ||
        left.createdAt.localeCompare(right.createdAt) ||
        left.requestId.localeCompare(right.requestId));
    if (pending.length === 0) return { status: "NO_PENDING_REQUESTS", decisions: [] };

    const globalUsed = Object.fromEntries([...this.knownResources].map((resource) => [resource, 0]));
    for (const allocation of this.state.federation.allocations.filter((entry) => entry.status === "ACTIVE")) {
      for (const [resource, quantity] of Object.entries(allocation.resources)) globalUsed[resource] += quantity;
    }
    const provisionalByEcosystem = Object.fromEntries(Object.keys(this.state.ecosystems).map((id) => [
      id,
      copy(this.state.ecosystems[id].resourceBudget.allocated)
    ]));
    const decisions = [];
    for (const request of pending) {
      const ecosystem = this.state.ecosystems[request.ecosystemId];
      let reason = "GRANTED_WITHIN_ENVELOPES";
      for (const [resource, quantity] of Object.entries(request.resources)) {
        const ecosystemAvailable =
          Number(ecosystem.resourceBudget.limits[resource] ?? 0) -
          Number(provisionalByEcosystem[ecosystem.id][resource] ?? 0);
        if (quantity > ecosystemAvailable) {
          reason = "ECOSYSTEM_BUDGET_EXCEEDED";
          break;
        }
        const globalAvailable = Number(this.globalCapacity[resource]) - Number(globalUsed[resource]);
        if (quantity > globalAvailable) {
          reason = "GLOBAL_RESOURCE_CONFLICT";
          break;
        }
      }
      if (reason === "GRANTED_WITHIN_ENVELOPES") {
        for (const [resource, quantity] of Object.entries(request.resources)) {
          globalUsed[resource] += quantity;
          provisionalByEcosystem[ecosystem.id][resource] =
            Number(provisionalByEcosystem[ecosystem.id][resource] ?? 0) + quantity;
        }
        decisions.push({
          requestId: request.requestId,
          ecosystemId: ecosystem.id,
          resources: request.resources,
          status: "GRANTED",
          reason,
          allocationId: `alloc:${request.requestId}`
        });
      } else {
        decisions.push({
          requestId: request.requestId,
          ecosystemId: ecosystem.id,
          resources: request.resources,
          status: "DENIED",
          reason,
          allocationId: null
        });
      }
    }
    const decidedAt = nowIso(this.clock);
    this.#commit("RESOURCE_ARBITRATED", null, { decidedAt, decisions });
    return { status: "ARBITRATED", decidedAt, decisions: copy(decisions) };
  }

  releaseResources(allocationId) {
    const id = identifier(allocationId, "allocationId");
    const allocation = this.state.federation.allocations.find((entry) => entry.allocationId === id);
    if (!allocation) fail("UNKNOWN_ALLOCATION", `Allocation inconnue: ${id}`);
    if (allocation.status !== "ACTIVE") return { status: "ALREADY_RELEASED", allocation: copy(allocation) };
    this.#commit("RESOURCES_RELEASED", allocation.ecosystemId, {
      allocationId: id,
      releasedAt: nowIso(this.clock)
    });
    return { status: "RELEASED", allocationId: id };
  }

  #normalizeContract(raw) {
    const candidate = assertPlainObject(raw, "contract");
    for (const field of EXCHANGE_REQUIRED_FIELDS) {
      if (candidate[field] === undefined || candidate[field] === null || candidate[field] === "") {
        fail("MISSING_CONTRACT_FIELD", `Champ de contrat manquant: ${field}`);
      }
    }
    const dataClass = text(candidate.dataClass, "contract.dataClass", 40).toUpperCase();
    if (!DATA_CLASSES.has(dataClass)) fail("INVALID_DATA_CLASS", "dataClass est invalide.");
    const provenance = assertPlainObject(candidate.provenance, "contract.provenance");
    const checksum = text(provenance.checksum, "contract.provenance.checksum", 160);
    if (!/^(?:sha256:)?[a-f0-9]{64}$/i.test(checksum)) {
      fail("INVALID_PROVENANCE_CHECKSUM", "Le checksum de provenance doit etre un SHA-256.");
    }
    const causalClock = assertPlainObject(candidate.causalClock, "contract.causalClock");
    const sourceCounter = Number(causalClock.sourceCounter);
    if (!Number.isSafeInteger(sourceCounter) || sourceCounter < 1) {
      fail("INVALID_CAUSAL_CLOCK", "causalClock.sourceCounter doit etre un entier positif.");
    }
    const wallTime = isoDate(causalClock.wallTime, "contract.causalClock.wallTime");
    const observed = causalClock.observed === undefined
      ? {}
      : Object.fromEntries(Object.entries(assertPlainObject(causalClock.observed, "contract.causalClock.observed"))
        .map(([key, value]) => {
          identifier(key, `contract.causalClock.observed.${key}`);
          if (!Number.isSafeInteger(Number(value)) || Number(value) < 0) {
            fail("INVALID_CAUSAL_CLOCK", `Compteur causal invalide pour ${key}.`);
          }
          return [key, Number(value)];
        }));
    const ttl = Number(candidate.ttl);
    if (!Number.isSafeInteger(ttl) || ttl < 1 || ttl > MAX_TTL_SECONDS) {
      fail("INVALID_TTL", `ttl doit etre un nombre de secondes entre 1 et ${MAX_TTL_SECONDS}.`);
    }
    const sourceEcosystemId = identifier(candidate.sourceEcosystemId, "contract.sourceEcosystemId");
    const targetEcosystemId = identifier(candidate.targetEcosystemId, "contract.targetEcosystemId");
    if (sourceEcosystemId === targetEcosystemId) fail("SAME_ECOSYSTEM_EXCHANGE", "Un contrat federe doit relier deux ecosystemes distincts.");
    this.#ecosystem(sourceEcosystemId);
    this.#ecosystem(targetEcosystemId);
    const normalized = {
      flowId: identifier(candidate.flowId, "contract.flowId"),
      sourceEcosystemId,
      targetEcosystemId,
      principalId: identifier(candidate.principalId, "contract.principalId"),
      purpose: text(candidate.purpose, "contract.purpose", 1_000),
      offeredValue: normalizeNonFinancialValue(candidate.offeredValue, "contract.offeredValue"),
      requestedValue: normalizeNonFinancialValue(candidate.requestedValue, "contract.requestedValue"),
      dataClass,
      provenance: {
        sourceRefs: stringArray(provenance.sourceRefs, "contract.provenance.sourceRefs", { minimum: 1 }),
        checksum: checksum.toLowerCase().replace(/^sha256:/, ""),
        transformation: String(provenance.transformation ?? "none").slice(0, 500)
      },
      license: text(candidate.license, "contract.license", 160),
      permissionDecisionId: identifier(candidate.permissionDecisionId, "contract.permissionDecisionId"),
      causalClock: { sourceCounter, wallTime, observed },
      ttl,
      compensation: normalizeNonFinancialValue(candidate.compensation, "contract.compensation"),
      payload: copy(candidate.payload ?? null)
    };
    rejectFinancialValue(normalized.payload, "contract.payload");
    return normalized;
  }

  #quarantine(raw, reasons, contractHash = null) {
    const sourceEcosystemId = raw && typeof raw === "object" ? String(raw.sourceEcosystemId ?? "") : "";
    const payload = {
      quarantineId: `quarantine:${randomUUID()}`,
      flowId: raw && typeof raw === "object" ? String(raw.flowId ?? "") : "",
      sourceEcosystemId: this.state.ecosystems[sourceEcosystemId] ? sourceEcosystemId : null,
      targetEcosystemId: raw && typeof raw === "object" ? String(raw.targetEcosystemId ?? "") : "",
      contractHash: contractHash ?? sha256(stableJson(raw ?? null)),
      reasons: Array.isArray(reasons) ? reasons : [String(reasons)],
      quarantinedAt: nowIso(this.clock),
      contract: copy(raw ?? null)
    };
    this.#commit("EXCHANGE_QUARANTINED", null, payload);
    return { status: "QUARANTINED", ...copy(payload) };
  }

  submitExchange(rawContract) {
    let contract;
    try {
      contract = this.#normalizeContract(rawContract);
    } catch (error) {
      if (error instanceof GovernanceError) {
        return this.#quarantine(rawContract, [error.code]);
      }
      throw error;
    }
    const contractHash = sha256(stableJson(contract));
    const existing = this.state.federation.exchangeFlowIndex[contract.flowId];
    if (existing) {
      if (existing.contractHash === contractHash) {
        return { ...copy(existing.receipt), status: "ACCEPTED", replayed: true };
      }
      return this.#quarantine(contract, ["IDEMPOTENCY_CONFLICT"], contractHash);
    }

    const expiration = new Date(contract.causalClock.wallTime).getTime() + contract.ttl * 1_000;
    if (new Date(nowIso(this.clock)).getTime() >= expiration) {
      return this.#quarantine(contract, ["EXPIRED_TTL"], contractHash);
    }
    const causalKey = `${contract.sourceEcosystemId}->${contract.targetEcosystemId}`;
    const causalHead = Number(this.state.federation.causalHeads[causalKey] ?? 0);
    if (contract.causalClock.sourceCounter <= causalHead) {
      return this.#quarantine(contract, ["CAUSAL_REPLAY_OR_REORDER"], contractHash);
    }
    const source = this.state.ecosystems[contract.sourceEcosystemId];
    const decision = source.permissionOverlay.decisions[contract.permissionDecisionId];
    if (!this.#permissionAllows(decision, {
      principalId: contract.principalId,
      action: "exchange.send",
      sourceEcosystemId: contract.sourceEcosystemId,
      targetEcosystemId: contract.targetEcosystemId,
      dataClass: contract.dataClass,
      license: contract.license
    })) {
      return this.#quarantine(contract, ["PERMISSION_DENIED_OR_EXPIRED"], contractHash);
    }
    const receipt = {
      status: "ACCEPTED",
      flowId: contract.flowId,
      contractHash,
      permissionDecisionId: contract.permissionDecisionId,
      acceptedAt: nowIso(this.clock),
      expiresAt: new Date(expiration).toISOString(),
      replayed: false
    };
    this.#commit("EXCHANGE_ACCEPTED", null, { contract, contractHash, receipt });
    return copy(receipt);
  }

  getQuarantine() {
    return copy(this.state.federation.quarantine);
  }

  verifyIntegrity() {
    const before = copy(this.state.ledger);
    const verificationState = initialState(this.config, this.globalCapacity);
    let expectedSequence = 1;
    let previousHash = "GENESIS";
    for (const fileName of this.#eventFiles()) {
      const event = JSON.parse(readFileSync(join(this.eventsDirectory, fileName), "utf8"));
      if (event.sequence !== expectedSequence || event.previousHash !== previousHash) {
        return { ok: false, reason: "CHAIN_OR_SEQUENCE", fileName };
      }
      if (sha256(stableJson(eventBody(event))) !== event.hash) {
        return { ok: false, reason: "HASH_MISMATCH", fileName };
      }
      applyEvent(verificationState, event);
      expectedSequence += 1;
      previousHash = event.hash;
    }
    return {
      ok: verificationState.ledger.sequence === before.sequence &&
        verificationState.ledger.headHash === before.headHash &&
        stableJson(verificationState) === stableJson(this.state),
      eventCount: before.sequence,
      headHash: before.headHash
    };
  }
}
