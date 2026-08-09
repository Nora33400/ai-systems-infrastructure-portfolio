import { createHash } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

const NODE_KINDS = Object.freeze([
  "federation",
  "ecosystem",
  "organization",
  "domain",
  "project",
  "agent",
  "workflow",
  "resource",
  "knowledge"
]);

const LIFECYCLE_STATES = Object.freeze(["active", "dormant", "archived"]);
const CONTEXT_LEVELS = Object.freeze(["unitile", "tile", "kilotile", "megatile", "gigatile"]);
const CONTEXT_PERSPECTIVES = Object.freeze(["machine-subjective", "user-objective", "dual"]);
const CONTEXT_UTILITY = Object.freeze(["useful", "neutral", "irrelevant", "contradictory", "unknown"]);

const ALLOWED_PARENTS = Object.freeze({
  federation: [],
  ecosystem: ["federation"],
  organization: ["federation", "ecosystem"],
  domain: ["organization", "domain"],
  project: ["organization", "domain"],
  agent: ["organization", "domain", "project"],
  workflow: ["organization", "domain", "project", "agent"],
  resource: ["federation", "ecosystem", "organization", "domain", "project", "agent", "workflow"],
  knowledge: ["federation", "ecosystem", "organization", "domain", "project", "agent", "workflow"]
});

const DEFAULT_ROOT_POLICY = Object.freeze({
  permissions: {
    allow: ["read", "search", "inventory", "audit", "plan", "simulate", "test.existing", "memory.write", "evidence.write"],
    deny: ["delete.recursive", "permission.self-escalation", "publication.automatic"]
  },
  limits: {
    maxConcurrentAgents: 256,
    maxContextTokens: 1_000_000,
    maxStorageBytes: 1_000_000_000_000
  },
  externalActionsDefault: "DENY",
  crossOrganizationRead: false,
  destructiveMutation: false
});

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, canonicalize(value[key])])
  );
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function sha256(value) {
  return createHash("sha256").update(String(value)).digest("hex");
}

function boundedText(value, field, maximum = 200) {
  const text = String(value || "").trim();
  if (!text) throw new Error(`${field} requis.`);
  if (text.length > maximum) throw new Error(`${field} depasse ${maximum} caracteres.`);
  return text;
}

function finiteInteger(value, fallback) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : fallback;
}

function stringSet(value) {
  return [...new Set(
    (Array.isArray(value) ? value : [])
      .filter((item) => item !== undefined && item !== null)
      .map((item) => String(item).trim())
      .filter(Boolean)
  )].sort();
}

function parseJson(value, fallback = {}) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function normalizeDate(value, fallback) {
  const date = value ? new Date(value) : fallback;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) throw new Error(`Date invalide: ${value}`);
  return date.toISOString();
}

function deterministicId(kind, namespace, naturalKey) {
  const digest = sha256(`${namespace}\u001f${kind}\u001f${naturalKey}`);
  return `${kind.slice(0, 4)}_${digest.slice(0, 24)}`;
}

function partitionFor(identity, shardCount) {
  const value = Number.parseInt(sha256(identity).slice(0, 8), 16) % shardCount;
  return `p${value.toString(16).padStart(4, "0")}`;
}

function normalizeContext(context = {}) {
  const level = CONTEXT_LEVELS.includes(context.level) ? context.level : "unitile";
  const perspective = CONTEXT_PERSPECTIVES.includes(context.perspective) ? context.perspective : "dual";
  const utility = CONTEXT_UTILITY.includes(context.utility) ? context.utility : "unknown";
  const sourceRefs = stringSet(context.reconstruction?.sourceRefs || context.sourceRefs).slice(0, 256);
  const reconstruction = {
    type: String(context.reconstruction?.type || "structured-summary"),
    sourceRefs,
    sourceChecksum: context.reconstruction?.sourceChecksum || null,
    reversible: context.reconstruction?.reversible !== false
  };
  return {
    level,
    perspective,
    utility,
    machineSubjective: String(context.machineSubjective || "").slice(0, 4000),
    userObjective: String(context.userObjective || "").slice(0, 4000),
    confidence: Math.max(0, Math.min(1, Number(context.confidence ?? 1))),
    reconstruction
  };
}

function inheritPolicy(parentPolicy = DEFAULT_ROOT_POLICY, requested = {}) {
  const parentAllow = stringSet(parentPolicy.permissions?.allow);
  const requestedAllow = requested.permissions?.allow === undefined
    ? parentAllow
    : stringSet(requested.permissions.allow);
  const denied = stringSet([
    ...stringSet(parentPolicy.permissions?.deny),
    ...stringSet(requested.permissions?.deny)
  ]);
  const effectiveAllow = requestedAllow.filter((item) => parentAllow.includes(item) && !denied.includes(item));
  const clamps = [];
  for (const permission of requestedAllow) {
    if (!parentAllow.includes(permission)) clamps.push({ field: `permissions.allow.${permission}`, reason: "parent-ceiling" });
    else if (denied.includes(permission)) clamps.push({ field: `permissions.allow.${permission}`, reason: "explicit-deny" });
  }

  const limits = {};
  for (const field of ["maxConcurrentAgents", "maxContextTokens", "maxStorageBytes"]) {
    const ceiling = finiteInteger(parentPolicy.limits?.[field], DEFAULT_ROOT_POLICY.limits[field]);
    const requestedValue = finiteInteger(requested.limits?.[field], ceiling);
    limits[field] = Math.min(ceiling, requestedValue);
    if (requestedValue > ceiling) clamps.push({ field: `limits.${field}`, reason: "parent-ceiling", requested: requestedValue, effective: ceiling });
  }

  const booleanCeiling = (field) => {
    const ceiling = parentPolicy[field] === true;
    const requestedValue = requested[field] === undefined ? ceiling : requested[field] === true;
    if (requestedValue && !ceiling) clamps.push({ field, reason: "parent-ceiling", requested: true, effective: false });
    return ceiling && requestedValue;
  };

  const parentExternal = parentPolicy.externalActionsDefault === "ALLOW" ? "ALLOW" : "DENY";
  const requestedExternal = requested.externalActionsDefault === "ALLOW" ? "ALLOW" : "DENY";
  if (requestedExternal === "ALLOW" && parentExternal !== "ALLOW") {
    clamps.push({ field: "externalActionsDefault", reason: "parent-ceiling", requested: "ALLOW", effective: "DENY" });
  }

  return {
    policy: {
      permissions: { allow: effectiveAllow, deny: denied },
      limits,
      externalActionsDefault: parentExternal === "ALLOW" && requestedExternal === "ALLOW" ? "ALLOW" : "DENY",
      crossOrganizationRead: booleanCeiling("crossOrganizationRead"),
      destructiveMutation: booleanCeiling("destructiveMutation")
    },
    clamps
  };
}

function decodeNode(row) {
  if (!row) return null;
  return {
    id: row.id,
    namespace: row.namespace,
    kind: row.kind,
    naturalKey: row.natural_key,
    name: row.name,
    parentId: row.parent_id,
    organizationId: row.organization_id,
    partitionKey: row.partition_key,
    lifecycle: row.lifecycle,
    policy: parseJson(row.policy_json),
    context: parseJson(row.context_json),
    metadata: parseJson(row.metadata_json),
    revision: row.revision,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    headHash: row.head_hash
  };
}

function decodeEvent(row) {
  if (!row) return null;
  return {
    id: row.id,
    scopeId: row.scope_id,
    organizationId: row.organization_id,
    partitionKey: row.partition_key,
    sequence: row.sequence,
    logicalTime: row.logical_time,
    observedAt: row.observed_at,
    effectiveAt: row.effective_at,
    actorId: row.actor_id,
    type: row.type,
    payload: parseJson(row.payload_json),
    previousHash: row.previous_hash,
    hash: row.hash
  };
}

export class EcosystemFabric {
  constructor({
    databasePath,
    namespace = "aione",
    shardCount = 256,
    actorId = "aione-autonomous-forge",
    rootPolicy = DEFAULT_ROOT_POLICY,
    clock = () => new Date()
  } = {}) {
    if (!databasePath) throw new Error("databasePath requis.");
    this.databasePath = resolve(databasePath);
    this.namespace = boundedText(namespace, "namespace", 120);
    this.shardCount = Math.max(16, Math.min(65_536, finiteInteger(shardCount, 256)));
    this.actorId = actorId;
    this.clock = clock;
    this.rootPolicy = inheritPolicy(DEFAULT_ROOT_POLICY, rootPolicy).policy;
    mkdirSync(dirname(this.databasePath), { recursive: true });
    this.db = new DatabaseSync(this.databasePath);
    this.initialize();
  }

  initialize() {
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA synchronous = NORMAL;
      PRAGMA foreign_keys = ON;
      PRAGMA busy_timeout = 5000;
      CREATE TABLE IF NOT EXISTS fabric_nodes (
        id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        kind TEXT NOT NULL,
        natural_key TEXT NOT NULL,
        name TEXT NOT NULL,
        parent_id TEXT REFERENCES fabric_nodes(id),
        organization_id TEXT,
        partition_key TEXT NOT NULL,
        lifecycle TEXT NOT NULL,
        policy_json TEXT NOT NULL,
        context_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        revision INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        head_hash TEXT,
        UNIQUE(namespace, kind, natural_key)
      );
      CREATE INDEX IF NOT EXISTS fabric_nodes_parent ON fabric_nodes(parent_id, kind, id);
      CREATE INDEX IF NOT EXISTS fabric_nodes_organization ON fabric_nodes(organization_id, kind, id);
      CREATE INDEX IF NOT EXISTS fabric_nodes_partition ON fabric_nodes(partition_key, id);
      CREATE TABLE IF NOT EXISTS fabric_events (
        id TEXT PRIMARY KEY,
        scope_id TEXT NOT NULL,
        organization_id TEXT,
        partition_key TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        logical_time INTEGER NOT NULL,
        observed_at TEXT NOT NULL,
        effective_at TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        previous_hash TEXT,
        hash TEXT NOT NULL,
        UNIQUE(scope_id, sequence)
      );
      CREATE INDEX IF NOT EXISTS fabric_events_scope ON fabric_events(scope_id, sequence);
      CREATE INDEX IF NOT EXISTS fabric_events_organization ON fabric_events(organization_id, logical_time);
      CREATE INDEX IF NOT EXISTS fabric_events_partition ON fabric_events(partition_key, logical_time);
      CREATE TABLE IF NOT EXISTS fabric_edges (
        source_id TEXT NOT NULL REFERENCES fabric_nodes(id),
        target_id TEXT NOT NULL REFERENCES fabric_nodes(id),
        relation TEXT NOT NULL,
        organization_id TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY(source_id, target_id, relation)
      );
      CREATE INDEX IF NOT EXISTS fabric_edges_target ON fabric_edges(target_id, relation);
    `);
  }

  close() {
    this.db.close();
  }

  getNode(id) {
    return decodeNode(this.db.prepare("SELECT * FROM fabric_nodes WHERE id = ?").get(String(id)));
  }

  listNodes({ parentId, organizationId, kind, partitionKey, lifecycle, cursor = "", limit = 100 } = {}) {
    const clauses = ["id > ?"];
    const values = [String(cursor || "")];
    for (const [field, value] of [
      ["parent_id", parentId],
      ["organization_id", organizationId],
      ["kind", kind],
      ["partition_key", partitionKey],
      ["lifecycle", lifecycle]
    ]) {
      if (value !== undefined && value !== null && value !== "") {
        clauses.push(`${field} = ?`);
        values.push(String(value));
      }
    }
    const boundedLimit = Math.max(1, Math.min(500, finiteInteger(limit, 100)));
    values.push(boundedLimit + 1);
    const rows = this.db.prepare(
      `SELECT * FROM fabric_nodes WHERE ${clauses.join(" AND ")} ORDER BY id LIMIT ?`
    ).all(...values);
    const hasMore = rows.length > boundedLimit;
    const items = rows.slice(0, boundedLimit).map(decodeNode);
    return {
      items,
      nextCursor: hasMore ? items.at(-1)?.id || null : null,
      hasMore
    };
  }

  simulateNode(input = {}) {
    const issues = [];
    const kind = String(input.kind || "").toLowerCase();
    if (!NODE_KINDS.includes(kind)) issues.push({ code: "invalid-kind", allowed: NODE_KINDS });
    let naturalKey = "";
    let name = "";
    try {
      naturalKey = boundedText(input.naturalKey, "naturalKey", 300);
      name = boundedText(input.name, "name", 300);
    } catch (error) {
      issues.push({ code: "invalid-identity", message: error.message });
    }
    const namespace = String(input.namespace || this.namespace);
    const id = kind && naturalKey ? deterministicId(kind, namespace, naturalKey) : null;
    const existing = id ? this.getNode(id) : null;
    const parent = input.parentId ? this.getNode(input.parentId) : null;
    if (input.parentId && !parent) issues.push({ code: "parent-not-found", parentId: input.parentId });
    if (kind && parent && !(ALLOWED_PARENTS[kind] || []).includes(parent.kind)) {
      issues.push({ code: "invalid-parent-kind", kind, parentKind: parent.kind });
    }
    if (kind && !input.parentId && !["federation", "ecosystem"].includes(kind)) {
      issues.push({ code: "parent-required", kind });
    }
    if (existing && (existing.parentId !== (input.parentId || null) || existing.name !== name)) {
      issues.push({ code: "identity-conflict", id, existingName: existing.name, existingParentId: existing.parentId });
    }

    const inheritedFrom = parent?.policy || this.rootPolicy;
    const { policy, clamps } = inheritPolicy(inheritedFrom, input.policy || {});
    const organizationId = kind === "organization" ? id : parent?.organizationId || null;
    const partitionKey = partitionFor(organizationId || id || `${namespace}:invalid`, this.shardCount);
    const now = this.clock();
    const observedAt = normalizeDate(input.time?.observedAt, now);
    const effectiveAt = normalizeDate(input.time?.effectiveAt, new Date(observedAt));
    const node = id ? {
      id,
      namespace,
      kind,
      naturalKey,
      name,
      parentId: input.parentId || null,
      organizationId,
      partitionKey,
      lifecycle: LIFECYCLE_STATES.includes(input.lifecycle) ? input.lifecycle : "active",
      policy,
      context: normalizeContext(input.context),
      metadata: input.metadata && typeof input.metadata === "object" ? input.metadata : {},
      revision: 1,
      createdAt: observedAt,
      updatedAt: observedAt,
      headHash: null
    } : null;
    return {
      schema: "aione.ecosystem-simulation.v1",
      scenarioId: `scenario_${sha256(stableJson({ action: "register-node", input })).slice(0, 20)}`,
      action: "register-node",
      allowed: issues.length === 0,
      wouldMutate: issues.length === 0 && !existing,
      alreadyExists: Boolean(existing),
      issues,
      policyClamps: clamps,
      node: existing || node,
      impact: {
        nodesCreated: issues.length === 0 && !existing ? 1 : 0,
        organizationsAffected: organizationId ? [organizationId] : [],
        partitionsAffected: node ? [partitionKey] : []
      },
      explanation: issues.length > 0
        ? "Proposition refusee par les contraintes de topologie ou d'identite."
        : existing
          ? "Identite deja presente; aucune mutation necessaire."
          : clamps.length > 0
            ? "Creation possible avec permissions et ressources bornees par le parent."
            : "Creation possible dans les limites heritees."
    };
  }

  registerNode(input = {}) {
    const simulation = this.simulateNode(input);
    if (!simulation.allowed) {
      const error = new Error(simulation.explanation);
      error.simulation = simulation;
      throw error;
    }
    if (!simulation.wouldMutate) return { created: false, node: simulation.node, simulation, event: null };
    const node = simulation.node;
    const event = this.createEvent({
      scopeId: node.id,
      organizationId: node.organizationId,
      partitionKey: node.partitionKey,
      type: "node.registered",
      payload: {
        nodeId: node.id,
        kind: node.kind,
        parentId: node.parentId,
        policyClamps: simulation.policyClamps
      },
      actorId: input.actorId,
      time: input.time
    });
    node.headHash = event.hash;
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare(`
        INSERT INTO fabric_nodes (
          id, namespace, kind, natural_key, name, parent_id, organization_id, partition_key,
          lifecycle, policy_json, context_json, metadata_json, revision, created_at, updated_at, head_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        node.id, node.namespace, node.kind, node.naturalKey, node.name, node.parentId,
        node.organizationId, node.partitionKey, node.lifecycle, stableJson(node.policy),
        stableJson(node.context), stableJson(node.metadata), node.revision, node.createdAt,
        node.updatedAt, node.headHash
      );
      this.insertEvent(event);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return { created: true, node, simulation, event };
  }

  createEvent({ scopeId, organizationId, partitionKey, type, payload = {}, actorId, time = {} }) {
    const head = this.db.prepare(
      "SELECT sequence, logical_time, hash FROM fabric_events WHERE scope_id = ? ORDER BY sequence DESC LIMIT 1"
    ).get(scopeId);
    const sequence = Number(head?.sequence || 0) + 1;
    const logicalTime = Math.max(Number(head?.logical_time || 0), finiteInteger(time.remoteLogicalTime, 0)) + 1;
    const observedAt = normalizeDate(time.observedAt, this.clock());
    const effectiveAt = normalizeDate(time.effectiveAt, new Date(observedAt));
    const unsigned = {
      scopeId,
      organizationId: organizationId || null,
      partitionKey,
      sequence,
      logicalTime,
      observedAt,
      effectiveAt,
      actorId: actorId || this.actorId,
      type,
      payload: canonicalize(payload),
      previousHash: head?.hash || null
    };
    const hash = sha256(stableJson(unsigned));
    return {
      id: `evt_${hash.slice(0, 24)}`,
      ...unsigned,
      hash
    };
  }

  insertEvent(event) {
    this.db.prepare(`
      INSERT INTO fabric_events (
        id, scope_id, organization_id, partition_key, sequence, logical_time,
        observed_at, effective_at, actor_id, type, payload_json, previous_hash, hash
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      event.id, event.scopeId, event.organizationId, event.partitionKey, event.sequence,
      event.logicalTime, event.observedAt, event.effectiveAt, event.actorId, event.type,
      stableJson(event.payload), event.previousHash, event.hash
    );
  }

  transitionLifecycle(id, lifecycle, { actorId, time } = {}) {
    if (!LIFECYCLE_STATES.includes(lifecycle)) throw new Error(`Cycle de vie invalide: ${lifecycle}`);
    const node = this.getNode(id);
    if (!node) throw new Error(`Noeud introuvable: ${id}`);
    if (node.lifecycle === lifecycle) return { changed: false, node, event: null };
    const event = this.createEvent({
      scopeId: node.id,
      organizationId: node.organizationId,
      partitionKey: node.partitionKey,
      type: "node.lifecycle-transitioned",
      payload: { from: node.lifecycle, to: lifecycle },
      actorId,
      time
    });
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.insertEvent(event);
      this.db.prepare(
        "UPDATE fabric_nodes SET lifecycle = ?, revision = revision + 1, updated_at = ?, head_hash = ? WHERE id = ?"
      ).run(lifecycle, event.observedAt, event.hash, id);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return { changed: true, node: this.getNode(id), event };
  }

  updateContext(id, context, { actorId, time } = {}) {
    const node = this.getNode(id);
    if (!node) throw new Error(`Noeud introuvable: ${id}`);
    const nextContext = normalizeContext(context);
    if (stableJson(node.context) === stableJson(nextContext)) {
      return { changed: false, node, event: null };
    }
    const event = this.createEvent({
      scopeId: node.id,
      organizationId: node.organizationId,
      partitionKey: node.partitionKey,
      type: "node.context-updated",
      payload: {
        previousChecksum: sha256(stableJson(node.context)),
        nextChecksum: sha256(stableJson(nextContext)),
        level: nextContext.level,
        perspective: nextContext.perspective,
        utility: nextContext.utility
      },
      actorId,
      time
    });
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.insertEvent(event);
      this.db.prepare(
        "UPDATE fabric_nodes SET context_json = ?, revision = revision + 1, updated_at = ?, head_hash = ? WHERE id = ?"
      ).run(stableJson(nextContext), event.observedAt, event.hash, id);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return { changed: true, node: this.getNode(id), event };
  }

  narrowPolicy(id, requestedPolicy, { actorId, time } = {}) {
    const node = this.getNode(id);
    if (!node) throw new Error(`Noeud introuvable: ${id}`);
    const { policy, clamps } = inheritPolicy(node.policy, requestedPolicy || {});
    if (stableJson(node.policy) === stableJson(policy)) {
      return { changed: false, node, clamps, event: null };
    }
    const event = this.createEvent({
      scopeId: node.id,
      organizationId: node.organizationId,
      partitionKey: node.partitionKey,
      type: "node.policy-narrowed",
      payload: {
        previousChecksum: sha256(stableJson(node.policy)),
        nextChecksum: sha256(stableJson(policy)),
        clamps
      },
      actorId,
      time
    });
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.insertEvent(event);
      this.db.prepare(
        "UPDATE fabric_nodes SET policy_json = ?, revision = revision + 1, updated_at = ?, head_hash = ? WHERE id = ?"
      ).run(stableJson(policy), event.observedAt, event.hash, id);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return { changed: true, node: this.getNode(id), clamps, event };
  }

  simulateLink({ sourceId, targetId, relation = "depends-on" } = {}) {
    const source = this.getNode(sourceId);
    const target = this.getNode(targetId);
    const issues = [];
    if (!source) issues.push({ code: "source-not-found", sourceId });
    if (!target) issues.push({ code: "target-not-found", targetId });
    if (sourceId === targetId) issues.push({ code: "self-link-forbidden" });
    const crossOrganization = Boolean(
      source?.organizationId
      && target?.organizationId
      && source.organizationId !== target.organizationId
    );
    if (crossOrganization && source?.policy.crossOrganizationRead !== true) {
      issues.push({ code: "cross-organization-link-denied", sourceOrganizationId: source.organizationId, targetOrganizationId: target.organizationId });
    }
    return {
      schema: "aione.ecosystem-simulation.v1",
      scenarioId: `scenario_${sha256(stableJson({ action: "link", sourceId, targetId, relation })).slice(0, 20)}`,
      action: "link",
      allowed: issues.length === 0,
      wouldMutate: issues.length === 0,
      issues,
      impact: {
        nodesCreated: 0,
        organizationsAffected: stringSet([source?.organizationId, target?.organizationId]),
        partitionsAffected: stringSet([source?.partitionKey, target?.partitionKey])
      },
      explanation: issues.length === 0
        ? "Lien simulable dans la frontiere de gouvernance."
        : "Lien refuse; aucune mutation n'a ete appliquee."
    };
  }

  linkNodes(input = {}) {
    const simulation = this.simulateLink(input);
    if (!simulation.allowed) {
      const error = new Error(simulation.explanation);
      error.simulation = simulation;
      throw error;
    }
    const source = this.getNode(input.sourceId);
    const target = this.getNode(input.targetId);
    const relation = boundedText(input.relation || "depends-on", "relation", 120);
    const result = this.db.prepare(`
      INSERT OR IGNORE INTO fabric_edges (source_id, target_id, relation, organization_id, created_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(source.id, target.id, relation, source.organizationId, this.clock().toISOString());
    return { created: Number(result.changes || 0) === 1, source, target, relation, simulation };
  }

  events({ scopeId, organizationId, afterLogicalTime = 0, limit = 100 } = {}) {
    const clauses = ["logical_time > ?"];
    const values = [finiteInteger(afterLogicalTime, 0)];
    if (scopeId) {
      clauses.push("scope_id = ?");
      values.push(String(scopeId));
    }
    if (organizationId) {
      clauses.push("organization_id = ?");
      values.push(String(organizationId));
    }
    values.push(Math.max(1, Math.min(1000, finiteInteger(limit, 100))));
    return this.db.prepare(
      `SELECT * FROM fabric_events WHERE ${clauses.join(" AND ")} ORDER BY logical_time, scope_id, sequence LIMIT ?`
    ).all(...values).map(decodeEvent);
  }

  verifyEventChains({ maximumEvents = 100_000 } = {}) {
    const total = Number(this.db.prepare("SELECT COUNT(*) AS count FROM fabric_events").get().count);
    const limit = Math.max(1, finiteInteger(maximumEvents, 100_000));
    const rows = this.db.prepare(
      "SELECT * FROM fabric_events ORDER BY scope_id, sequence LIMIT ?"
    ).all(limit);
    const issues = [];
    const heads = new Map();
    for (const row of rows) {
      const event = decodeEvent(row);
      const previous = heads.get(event.scopeId) || { sequence: 0, logicalTime: 0, hash: null };
      const unsigned = {
        scopeId: event.scopeId,
        organizationId: event.organizationId,
        partitionKey: event.partitionKey,
        sequence: event.sequence,
        logicalTime: event.logicalTime,
        observedAt: event.observedAt,
        effectiveAt: event.effectiveAt,
        actorId: event.actorId,
        type: event.type,
        payload: canonicalize(event.payload),
        previousHash: event.previousHash
      };
      if (event.sequence !== previous.sequence + 1) issues.push({ code: "sequence-gap", eventId: event.id });
      if (event.logicalTime <= previous.logicalTime) issues.push({ code: "logical-time-regression", eventId: event.id });
      if (event.previousHash !== previous.hash) issues.push({ code: "chain-mismatch", eventId: event.id });
      if (sha256(stableJson(unsigned)) !== event.hash) issues.push({ code: "hash-mismatch", eventId: event.id });
      heads.set(event.scopeId, { sequence: event.sequence, logicalTime: event.logicalTime, hash: event.hash });
    }
    return {
      ok: issues.length === 0,
      status: total > limit ? "BOUNDED" : "COMPLETE",
      checkedEvents: rows.length,
      totalEvents: total,
      scopeCount: heads.size,
      issues
    };
  }

  summary() {
    const total = Number(this.db.prepare("SELECT COUNT(*) AS count FROM fabric_nodes").get().count);
    const byKind = Object.fromEntries(
      this.db.prepare("SELECT kind, COUNT(*) AS count FROM fabric_nodes GROUP BY kind ORDER BY kind")
        .all().map((row) => [row.kind, Number(row.count)])
    );
    const byLifecycle = Object.fromEntries(
      this.db.prepare("SELECT lifecycle, COUNT(*) AS count FROM fabric_nodes GROUP BY lifecycle ORDER BY lifecycle")
        .all().map((row) => [row.lifecycle, Number(row.count)])
    );
    const partitions = Number(this.db.prepare("SELECT COUNT(DISTINCT partition_key) AS count FROM fabric_nodes").get().count);
    return {
      schema: "aione.ecosystem-fabric-status.v1",
      namespace: this.namespace,
      controllerTopology: "SINGLE_CONTROL_PLANE",
      databasePath: this.databasePath,
      totalNodes: total,
      organizations: byKind.organization || 0,
      ecosystems: byKind.ecosystem || 0,
      federations: byKind.federation || 0,
      activePartitions: partitions,
      configuredPartitions: this.shardCount,
      byKind,
      byLifecycle,
      contextLevels: CONTEXT_LEVELS,
      timeModel: {
        observedAt: "machine-subjective",
        effectiveAt: "user-objective",
        logicalTime: "causal-order"
      },
      eventIntegrity: this.verifyEventChains()
    };
  }
}

export {
  CONTEXT_LEVELS,
  CONTEXT_PERSPECTIVES,
  CONTEXT_UTILITY,
  DEFAULT_ROOT_POLICY,
  LIFECYCLE_STATES,
  NODE_KINDS,
  deterministicId,
  inheritPolicy,
  partitionFor,
  stableJson
};
