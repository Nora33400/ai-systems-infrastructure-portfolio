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
import { dirname, join, resolve } from "node:path";

export const THERMAL_STATES = Object.freeze(["COLD", "WARM", "HOT", "BURNING"]);
export const TILE_LEVELS = Object.freeze(["tile", "unitile", "kilotile", "megatile", "gigatile"]);
export const TILE_FAMILIES = Object.freeze([
  "utile",
  "ntile",
  "itile",
  "unitile",
  "nutile",
  "iutile",
  "inutile",
  "uiutile",
  "iuitile"
]);
export const RECONSTRUCTION_MODES = Object.freeze([
  "QUICK",
  "OPERATIONAL",
  "DEEP_DOCUMENTATION",
  "REFLEXIVE"
]);

const DEFAULT_BUDGETS = Object.freeze({
  QUICK: Object.freeze({ maxTokens: 200, maxChars: 800 }),
  OPERATIONAL: Object.freeze({ maxTokens: 1_000, maxChars: 4_000 }),
  DEEP_DOCUMENTATION: Object.freeze({ maxTokens: 4_000, maxChars: 16_000 }),
  REFLEXIVE: Object.freeze({ maxTokens: 2_500, maxChars: 10_000 })
});

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

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function cleanText(value, field, max = 100_000) {
  if (typeof value !== "string" || !value.trim()) fail("INVALID_INPUT", `${field} doit être un texte non vide`);
  const text = value.replace(/\r\n/g, "\n").trim();
  if (text.length > max) fail("INVALID_INPUT", `${field} dépasse ${max} caractères`);
  return text;
}

function cleanOptionalText(value, field, max = 100_000) {
  if (value === undefined || value === null || value === "") return "";
  return cleanText(value, field, max);
}

function clamp01(value, field) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0 || number > 1) {
    fail("INVALID_INPUT", `${field} doit être compris entre 0 et 1`);
  }
  return number;
}

function safeSegment(value, field) {
  const text = cleanText(value, field, 120);
  const segment = text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  if (!segment || segment === "." || segment === "..") fail("INVALID_INPUT", `${field} ne produit pas un dossier sûr`);
  return segment;
}

function normalizeEnum(value, allowed, field) {
  const candidate = String(value || "").toLowerCase();
  const found = allowed.find((item) => item.toLowerCase() === candidate);
  if (!found) fail("INVALID_INPUT", `${field} invalide: ${value}`);
  return found;
}

function normalizeProvenance(value, timestamp) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail("INVALID_INPUT", "provenance doit être un objet");
  }
  return {
    sourceId: cleanText(value.sourceId, "provenance.sourceId", 500),
    sourceType: cleanText(value.sourceType, "provenance.sourceType", 120),
    capturedAt: value.capturedAt ? new Date(value.capturedAt).toISOString() : timestamp,
    sourceHash: value.sourceHash
      ? cleanText(value.sourceHash, "provenance.sourceHash", 256)
      : null,
    locator: cleanOptionalText(value.locator, "provenance.locator", 2_000),
    agentId: cleanOptionalText(value.agentId, "provenance.agentId", 240)
  };
}

function normalizeAnchor(value, index) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail("INVALID_INPUT", `anchors[${index}] doit être un objet`);
  }
  const tileId = cleanOptionalText(value.tileId, `anchors[${index}].tileId`, 100);
  const fractalKey = cleanOptionalText(value.fractalKey, `anchors[${index}].fractalKey`, 240);
  if (!tileId && !fractalKey) {
    fail("INVALID_INPUT", `anchors[${index}] doit référencer tileId ou fractalKey`);
  }
  return {
    tileId: tileId || null,
    fractalKey: fractalKey || null,
    relation: cleanText(value.relation || "related", `anchors[${index}].relation`, 120),
    weight: clamp01(value.weight ?? 0.5, `anchors[${index}].weight`)
  };
}

function uniqueAnchors(anchors) {
  const seen = new Set();
  return anchors.filter((anchor) => {
    const key = canonical(anchor);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function tileHash(tile) {
  const value = clone(tile);
  delete value.tileHash;
  return hash(value);
}

function eventHash(event) {
  const value = clone(event);
  delete value.eventHash;
  return hash(value);
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
        fail("INTEGRITY_ERROR", `JSONL invalide ligne ${index + 1}: ${path}`);
      }
    });
}

function verifyChain(events) {
  let previous = null;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (event.previousEventHash !== previous) {
      fail("INTEGRITY_ERROR", `Chaîne fractale rompue à la ligne ${index + 1}`);
    }
    if (eventHash(event) !== event.eventHash) {
      fail("INTEGRITY_ERROR", `Événement fractal altéré à la ligne ${index + 1}`);
    }
    if (!event.tile || tileHash(event.tile) !== event.tile.tileHash) {
      fail("INTEGRITY_ERROR", `Tuile altérée à la ligne ${index + 1}`);
    }
    previous = event.eventHash;
  }
  return { ok: true, count: events.length, head: previous };
}

function rebuild(events) {
  const tiles = new Map();
  const history = new Map();
  for (const event of events) {
    const prior = tiles.get(event.tile.id);
    if (!prior && event.tile.revision !== 1) {
      fail("INTEGRITY_ERROR", `Première révision invalide: ${event.tile.id}`);
    }
    if (prior && event.tile.revision !== prior.revision + 1) {
      fail("INTEGRITY_ERROR", `Révision non séquentielle: ${event.tile.id}`);
    }
    tiles.set(event.tile.id, event.tile);
    if (!history.has(event.tile.id)) history.set(event.tile.id, []);
    history.get(event.tile.id).push(event.tile);
  }
  return { tiles, history };
}

function hoursBetween(now, then) {
  return Math.max(0, (now.getTime() - new Date(then).getTime()) / 3_600_000);
}

export function thermalScore(
  { usageCount = 0, lastUsedAt, createdAt, importance = 0.5, confidence = 0.5 },
  at = new Date()
) {
  const usage = 1 - Math.exp(-Math.max(0, usageCount) / 4);
  const recency = Math.exp(-hoursBetween(at, lastUsedAt || createdAt || at) / 72);
  // Un grand nombre d'usages est une mémoire de fréquence, pas une raison de
  // rester brûlant éternellement : sa contribution refroidit avec la récence.
  const activeUsage = usage * Math.sqrt(recency);
  return Math.max(
    0,
    Math.min(
      1,
      Number((0.3 * activeUsage + 0.25 * recency + 0.3 * importance + 0.15 * confidence).toFixed(6))
    )
  );
}

/**
 * Hystérésis :
 * - entrée WARM/HOT/BURNING : 0.38 / 0.62 / 0.82
 * - sortie vers le niveau inférieur : 0.30 / 0.54 / 0.74
 */
export function thermalStateForScore(score, previous = "COLD") {
  const value = clamp01(score, "score");
  const prior = normalizeEnum(previous, THERMAL_STATES, "previous").toUpperCase();
  if (prior === "BURNING") {
    if (value >= 0.74) return "BURNING";
    if (value >= 0.54) return "HOT";
    if (value >= 0.3) return "WARM";
    return "COLD";
  }
  if (prior === "HOT") {
    if (value >= 0.82) return "BURNING";
    if (value >= 0.54) return "HOT";
    if (value >= 0.3) return "WARM";
    return "COLD";
  }
  if (prior === "WARM") {
    if (value >= 0.82) return "BURNING";
    if (value >= 0.62) return "HOT";
    if (value >= 0.3) return "WARM";
    return "COLD";
  }
  if (value >= 0.82) return "BURNING";
  if (value >= 0.62) return "HOT";
  if (value >= 0.38) return "WARM";
  return "COLD";
}

function compressedReconstruction(subjectiveMachine, objectiveUser, maxChars = 1_200) {
  const text = [
    `Machine: ${subjectiveMachine.replace(/\s+/g, " ").trim()}`,
    `Utilisateur: ${objectiveUser.replace(/\s+/g, " ").trim()}`
  ].join(" | ");
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`;
}

function fingerprint(input) {
  return hash({
    category: input.category.toLowerCase(),
    title: input.title.toLowerCase().replace(/\s+/g, " ").trim(),
    subjectiveMachine: input.subjectiveMachine.replace(/\s+/g, " ").trim(),
    objectiveUser: input.objectiveUser.replace(/\s+/g, " ").trim()
  });
}

function assertExpectedRevision(tile, expectedRevision) {
  if (!Number.isInteger(expectedRevision)) {
    fail("EXPECTED_REVISION_REQUIRED", "expectedRevision entier est obligatoire");
  }
  if (tile.revision !== expectedRevision) {
    fail("REVISION_CONFLICT", `Révision attendue ${expectedRevision}, actuelle ${tile.revision}`);
  }
}

function estimateTokens(text) {
  return Math.ceil(text.length / 4);
}

function bounded(text, maxChars, maxTokens) {
  const hardLimit = Math.max(0, Math.min(maxChars, maxTokens * 4));
  if (text.length <= hardLimit) {
    return { text, truncated: false, usedChars: text.length, estimatedTokens: estimateTokens(text) };
  }
  const suffix = hardLimit > 1 ? "…" : "";
  const result = `${text.slice(0, Math.max(0, hardLimit - suffix.length)).trimEnd()}${suffix}`;
  return {
    text: result,
    truncated: true,
    usedChars: result.length,
    estimatedTokens: estimateTokens(result)
  };
}

function normalizeBudgets(defaultBudgets, mode, maxChars, maxTokens) {
  const defaults = defaultBudgets[mode];
  const chars = maxChars ?? defaults.maxChars;
  const tokens = maxTokens ?? defaults.maxTokens;
  if (!Number.isInteger(chars) || chars < 1 || !Number.isInteger(tokens) || tokens < 1) {
    fail("INVALID_BUDGET", "Les budgets caractères et tokens doivent être des entiers positifs");
  }
  return { maxChars: chars, maxTokens: tokens };
}

function defaultRoot() {
  return "S:\\AI_LAB\\Runtime\\FractalContext";
}

/**
 * Mémoire fractale latente, locale et append-only.
 *
 * `compact` produit une représentation logique réversible : les révisions
 * sources restent dans le ledger et dans leurs snapshots. Aucun fichier source
 * n'est supprimé et aucune archive système n'est créée.
 */
export function createThermalContextStore({
  runtimeRoot,
  now = () => new Date(),
  budgets = DEFAULT_BUDGETS
} = {}) {
  const injected = runtimeRoot !== undefined;
  const root = resolve(runtimeRoot || defaultRoot());
  if (!injected && !/^S:\\/i.test(root)) {
    fail("LOCAL_S_STORAGE_REQUIRED", `Le stockage par défaut doit rester sur S: ${root}`);
  }
  const normalizedBudgets = {};
  for (const mode of RECONSTRUCTION_MODES) {
    const override = budgets?.[mode] || {};
    normalizedBudgets[mode] = normalizeBudgets(
      DEFAULT_BUDGETS,
      mode,
      override.maxChars,
      override.maxTokens
    );
  }

  const paths = Object.freeze({
    root,
    ledger: resolve(root, "thermal-context-ledger.jsonl"),
    tiles: resolve(root, "tiles"),
    lock: resolve(root, ".thermal-context.lock")
  });
  mkdirSync(paths.tiles, { recursive: true });

  function withLock(operation) {
    let descriptor;
    try {
      descriptor = openSync(paths.lock, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, at: new Date().toISOString() }));
    } catch (error) {
      if (error?.code === "EEXIST") fail("CONCURRENT_WRITE", "Une autre écriture de contexte est active");
      throw error;
    }
    try {
      return operation();
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(paths.lock)) unlinkSync(paths.lock);
    }
  }

  function load() {
    const events = parseJsonLines(paths.ledger);
    const chain = verifyChain(events);
    const state = rebuild(events);
    return { events, chain, ...state };
  }

  function snapshotPath(tile) {
    return join(
      paths.tiles,
      safeSegment(tile.category, "category"),
      tile.temperature,
      tile.id,
      `${String(tile.revision).padStart(6, "0")}-${tile.tileHash}.json`
    );
  }

  function persist(events, action, tile, metadata = {}) {
    const timestamp = tile.updatedAt;
    const event = {
      eventId: randomUUID(),
      timestamp,
      action,
      previousEventHash: events.at(-1)?.eventHash || null,
      tile,
      metadata: clone(metadata)
    };
    event.eventHash = eventHash(event);
    appendFileSync(paths.ledger, `${JSON.stringify(event)}\n`, "utf8");
    const target = snapshotPath(tile);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, `${JSON.stringify({ eventHash: event.eventHash, tile }, null, 2)}\n`, {
      encoding: "utf8",
      flag: "wx"
    });
    return event;
  }

  function nextTile(current, changes, timestamp) {
    const tile = {
      ...clone(current),
      ...clone(changes),
      revision: current.revision + 1,
      updatedAt: timestamp
    };
    tile.tileHash = tileHash(tile);
    return tile;
  }

  function ingest(input) {
    return withLock(() => {
      const timestamp = now().toISOString();
      const subjectiveMachine = cleanText(input?.subjectiveMachine, "subjectiveMachine");
      const objectiveUser = cleanText(input?.objectiveUser, "objectiveUser");
      const normalized = {
        category: cleanText(input?.category, "category", 120),
        title: cleanText(input?.title, "title", 500),
        subjectiveMachine,
        objectiveUser,
        level: normalizeEnum(input?.level || "tile", TILE_LEVELS, "level"),
        family: normalizeEnum(input?.family || "utile", TILE_FAMILIES, "family"),
        importance: clamp01(input?.importance ?? 0.5, "importance"),
        confidence: clamp01(input?.confidence ?? 0.5, "confidence"),
        provenance: normalizeProvenance(input?.provenance, timestamp),
        anchors: uniqueAnchors((input?.anchors || []).map(normalizeAnchor))
      };
      const contentFingerprint = fingerprint(normalized);
      const { events, tiles } = load();
      const duplicate = [...tiles.values()].find((tile) => tile.fingerprint === contentFingerprint);
      if (duplicate) {
        return { ok: true, idempotent: true, duplicate: true, tile: clone(duplicate) };
      }
      const initial = {
        id: randomUUID(),
        fingerprint: contentFingerprint,
        category: normalized.category,
        title: normalized.title,
        level: normalized.level,
        family: normalized.family,
        contentMode: "FULL",
        subjectiveMachine,
        objectiveUser,
        reconstructionCompressed: cleanOptionalText(
          input?.reconstructionCompressed,
          "reconstructionCompressed",
          10_000
        ) || compressedReconstruction(subjectiveMachine, objectiveUser),
        sourceRevision: null,
        sourceContentHash: hash({ subjectiveMachine, objectiveUser }),
        anchors: normalized.anchors,
        provenance: normalized.provenance,
        importance: normalized.importance,
        confidence: normalized.confidence,
        usageCount: 0,
        lastUsedAt: timestamp,
        createdAt: timestamp,
        updatedAt: timestamp,
        revision: 1
      };
      initial.heatScore = thermalScore(initial, new Date(timestamp));
      initial.temperature = thermalStateForScore(initial.heatScore, "COLD");
      initial.tileHash = tileHash(initial);
      persist(events, "INGEST", initial, {
        sourceContentHash: initial.sourceContentHash,
        noSourceDeletion: true
      });
      return { ok: true, idempotent: false, duplicate: false, tile: clone(initial) };
    });
  }

  function get(id) {
    const { tiles } = load();
    const tile = tiles.get(id);
    if (!tile) fail("NOT_FOUND", `Tuile inconnue: ${id}`);
    return clone(tile);
  }

  function list({ category, temperature, level, family } = {}) {
    const { tiles } = load();
    return [...tiles.values()]
      .filter((tile) => !category || tile.category === category)
      .filter((tile) => !temperature || tile.temperature === String(temperature).toUpperCase())
      .filter((tile) => !level || tile.level === level)
      .filter((tile) => !family || tile.family === family)
      .sort((left, right) => right.heatScore - left.heatScore || left.createdAt.localeCompare(right.createdAt))
      .map(clone);
  }

  function touch(
    id,
    { weight = 1, importance, confidence, expectedRevision, at = now() } = {}
  ) {
    return withLock(() => {
      const timestamp = new Date(at).toISOString();
      const { events, tiles } = load();
      const current = tiles.get(id);
      if (!current) fail("NOT_FOUND", `Tuile inconnue: ${id}`);
      assertExpectedRevision(current, expectedRevision);
      const usageWeight = Number(weight);
      if (!Number.isFinite(usageWeight) || usageWeight <= 0 || usageWeight > 100) {
        fail("INVALID_INPUT", "weight doit être supérieur à 0 et inférieur ou égal à 100");
      }
      const candidate = {
        ...current,
        usageCount: current.usageCount + usageWeight,
        lastUsedAt: timestamp,
        importance: importance === undefined ? current.importance : clamp01(importance, "importance"),
        confidence: confidence === undefined ? current.confidence : clamp01(confidence, "confidence")
      };
      const score = thermalScore(candidate, new Date(timestamp));
      const temperature = thermalStateForScore(score, current.temperature);
      const tile = nextTile(current, {
        usageCount: candidate.usageCount,
        lastUsedAt: timestamp,
        importance: candidate.importance,
        confidence: candidate.confidence,
        heatScore: score,
        temperature
      }, timestamp);
      persist(events, "TOUCH", tile, {
        priorTemperature: current.temperature,
        transition: current.temperature === temperature ? null : `${current.temperature}->${temperature}`
      });
      return { ok: true, tile: clone(tile) };
    });
  }

  function refreshTemperatures({ at = now() } = {}) {
    return withLock(() => {
      const timestamp = new Date(at).toISOString();
      const state = load();
      const refreshed = [];
      for (const current of state.tiles.values()) {
        const score = thermalScore(current, new Date(timestamp));
        const temperature = thermalStateForScore(score, current.temperature);
        const tile = nextTile(current, { heatScore: score, temperature }, timestamp);
        persist(state.events, "THERMAL_REFRESH", tile, {
          priorTemperature: current.temperature,
          transition: current.temperature === temperature ? null : `${current.temperature}->${temperature}`
        });
        state.events.push(parseJsonLines(paths.ledger).at(-1));
        refreshed.push(clone(tile));
      }
      return { ok: true, count: refreshed.length, tiles: refreshed };
    });
  }

  function link(
    fromId,
    toId,
    { relation = "related", weight = 0.5, bidirectional = false, expectedRevision, targetExpectedRevision } = {}
  ) {
    return withLock(() => {
      const timestamp = now().toISOString();
      const state = load();
      const from = state.tiles.get(fromId);
      const to = state.tiles.get(toId);
      if (!from || !to) fail("NOT_FOUND", "Les deux tuiles doivent exister avant le lien");
      assertExpectedRevision(from, expectedRevision);
      const forward = normalizeAnchor({ tileId: toId, relation, weight }, 0);
      const existingForward = from.anchors.some((anchor) => canonical(anchor) === canonical(forward));
      if (existingForward && !bidirectional) {
        return { ok: true, idempotent: true, from: clone(from), to: clone(to) };
      }
      let updatedFrom = from;
      if (!existingForward) {
        updatedFrom = nextTile(from, { anchors: uniqueAnchors([...from.anchors, forward]) }, timestamp);
        persist(state.events, "LINK", updatedFrom, { targetId: toId, bidirectional });
        state.events.push(parseJsonLines(paths.ledger).at(-1));
      }
      let updatedTo = to;
      if (bidirectional) {
        const reverse = normalizeAnchor({ tileId: fromId, relation, weight }, 0);
        if (!to.anchors.some((anchor) => canonical(anchor) === canonical(reverse))) {
          assertExpectedRevision(to, targetExpectedRevision);
          updatedTo = nextTile(to, { anchors: uniqueAnchors([...to.anchors, reverse]) }, timestamp);
          persist(state.events, "LINK_REVERSE", updatedTo, { targetId: fromId, bidirectional: true });
        }
      }
      return {
        ok: true,
        idempotent: existingForward && updatedTo === to,
        from: clone(updatedFrom),
        to: clone(updatedTo)
      };
    });
  }

  function originalContent(tileId, history) {
    const revisions = history.get(tileId) || [];
    const full = revisions.find((revision) => revision.contentMode === "FULL");
    if (!full) fail("INTEGRITY_ERROR", `Source pleine introuvable pour ${tileId}`);
    const content = {
      subjectiveMachine: full.subjectiveMachine,
      objectiveUser: full.objectiveUser
    };
    if (hash(content) !== full.sourceContentHash) {
      fail("INTEGRITY_ERROR", `Contenu source altéré pour ${tileId}`);
    }
    return { ...content, revision: full.revision, tileHash: full.tileHash };
  }

  function compact(id, { reconstruction, expectedRevision, maxChars = 1_200 } = {}) {
    return withLock(() => {
      const timestamp = now().toISOString();
      const { events, tiles, history } = load();
      const current = tiles.get(id);
      if (!current) fail("NOT_FOUND", `Tuile inconnue: ${id}`);
      if (current.contentMode === "LOGICALLY_ZIPPED") {
        return { ok: true, idempotent: true, tile: clone(current) };
      }
      assertExpectedRevision(current, expectedRevision);
      if (!Number.isInteger(maxChars) || maxChars < 80) {
        fail("INVALID_BUDGET", "maxChars de compaction doit être un entier >= 80");
      }
      const source = originalContent(id, history);
      const compressed = cleanOptionalText(reconstruction, "reconstruction", 20_000)
        || compressedReconstruction(source.subjectiveMachine, source.objectiveUser, maxChars);
      const packed = bounded(compressed, maxChars, Math.ceil(maxChars / 4));
      const tile = nextTile(current, {
        contentMode: "LOGICALLY_ZIPPED",
        subjectiveMachine: null,
        objectiveUser: null,
        reconstructionCompressed: packed.text,
        sourceRevision: source.revision,
        sourceContentHash: hash({
          subjectiveMachine: source.subjectiveMachine,
          objectiveUser: source.objectiveUser
        })
      }, timestamp);
      persist(events, "LOGICAL_ZIP", tile, {
        reversibleSourceRevision: source.revision,
        reversibleSourceTileHash: source.tileHash,
        realArchiveCreated: false,
        sourceDeleted: false
      });
      return { ok: true, idempotent: false, tile: clone(tile) };
    });
  }

  function expand(id, { expectedRevision } = {}) {
    return withLock(() => {
      const timestamp = now().toISOString();
      const { events, tiles, history } = load();
      const current = tiles.get(id);
      if (!current) fail("NOT_FOUND", `Tuile inconnue: ${id}`);
      if (current.contentMode === "FULL") {
        return { ok: true, idempotent: true, tile: clone(current) };
      }
      assertExpectedRevision(current, expectedRevision);
      const source = originalContent(id, history);
      const tile = nextTile(current, {
        contentMode: "FULL",
        subjectiveMachine: source.subjectiveMachine,
        objectiveUser: source.objectiveUser,
        sourceRevision: null
      }, timestamp);
      persist(events, "LOGICAL_UNZIP", tile, {
        restoredFromRevision: source.revision,
        sourceDeleted: false
      });
      return { ok: true, idempotent: false, tile: clone(tile) };
    });
  }

  function reconstruct({
    tileIds = [],
    fractalKeys = [],
    includeAnchors = true,
    mode = "QUICK",
    maxChars,
    maxTokens
  } = {}) {
    const normalizedMode = normalizeEnum(mode, RECONSTRUCTION_MODES, "mode").toUpperCase();
    const budget = normalizeBudgets(normalizedBudgets, normalizedMode, maxChars, maxTokens);
    const { tiles, history } = load();
    const selected = new Set(tileIds);
    const keySet = new Set(fractalKeys);
    for (const tile of tiles.values()) {
      if (tile.anchors.some((anchor) => anchor.fractalKey && keySet.has(anchor.fractalKey))) {
        selected.add(tile.id);
      }
    }
    if (includeAnchors) {
      for (const id of [...selected]) {
        const tile = tiles.get(id);
        for (const anchor of tile?.anchors || []) {
          if (anchor.tileId && tiles.has(anchor.tileId)) selected.add(anchor.tileId);
        }
      }
    }
    const layers = [...selected]
      .map((id) => tiles.get(id))
      .filter(Boolean)
      .sort((left, right) => right.heatScore - left.heatScore || right.importance - left.importance);
    if (layers.length === 0) fail("NO_CONTEXT", "Aucune tuile ne correspond à la reconstruction");

    const sections = layers.map((tile) => {
      const source = originalContent(tile.id, history);
      if (normalizedMode === "QUICK") {
        return `[${tile.temperature}] ${tile.reconstructionCompressed}`;
      }
      if (normalizedMode === "OPERATIONAL") {
        return [
          `## ${tile.title} [${tile.temperature}/${tile.level}/${tile.family}]`,
          `Objectif utilisateur: ${source.objectiveUser}`,
          `Reconstruction: ${tile.reconstructionCompressed}`
        ].join("\n");
      }
      if (normalizedMode === "REFLEXIVE") {
        return [
          `## Réflexion — ${tile.title}`,
          `Subjectivité machine: ${source.subjectiveMachine}`,
          `Objectif utilisateur depuis cette subjectivité: ${source.objectiveUser}`,
          `Confiance: ${tile.confidence}; importance: ${tile.importance}; chaleur: ${tile.heatScore}`,
          `Question réflexive: où l'interprétation machine peut-elle diverger de l'intention utilisateur ?`
        ].join("\n");
      }
      return [
        `## ${tile.title}`,
        `Identifiant: ${tile.id}`,
        `Catégorie: ${tile.category}; niveau: ${tile.level}; famille: ${tile.family}`,
        `Température: ${tile.temperature}; score: ${tile.heatScore}`,
        `Subjectivité machine: ${source.subjectiveMachine}`,
        `Objectif utilisateur: ${source.objectiveUser}`,
        `Reconstruction compressée: ${tile.reconstructionCompressed}`,
        `Provenance: ${tile.provenance.sourceType}/${tile.provenance.sourceId} @ ${tile.provenance.capturedAt}`,
        `Empreinte source: ${tile.sourceContentHash}`,
        `Ancres: ${tile.anchors.map((anchor) => anchor.tileId || anchor.fractalKey).join(", ") || "aucune"}`
      ].join("\n");
    });
    const header = [
      `# Reconstruction ${normalizedMode}`,
      `Superposition: ${layers.length} couche(s)`,
      ""
    ].join("\n");
    const result = bounded(`${header}${sections.join("\n\n")}`, budget.maxChars, budget.maxTokens);
    return {
      ok: true,
      mode: normalizedMode,
      text: result.text,
      usedChars: result.usedChars,
      estimatedTokens: result.estimatedTokens,
      maxChars: budget.maxChars,
      maxTokens: budget.maxTokens,
      truncated: result.truncated,
      tileIds: layers.map((tile) => tile.id),
      temperatures: layers.map((tile) => tile.temperature),
      provenance: layers.map((tile) => ({
        tileId: tile.id,
        sourceId: tile.provenance.sourceId,
        sourceType: tile.provenance.sourceType,
        sourceContentHash: tile.sourceContentHash,
        tileHash: tile.tileHash
      })),
      reconstructionHash: hash(result.text)
    };
  }

  function verifyIntegrity({ verifySnapshots = true } = {}) {
    const state = load();
    let snapshotCount = 0;
    if (verifySnapshots) {
      for (const event of state.events) {
        const path = snapshotPath(event.tile);
        if (!existsSync(path)) fail("INTEGRITY_ERROR", `Snapshot manquant: ${path}`);
        let snapshot;
        try {
          snapshot = JSON.parse(readFileSync(path, "utf8"));
        } catch {
          fail("INTEGRITY_ERROR", `Snapshot JSON invalide: ${path}`);
        }
        if (
          snapshot.eventHash !== event.eventHash ||
          tileHash(snapshot.tile) !== snapshot.tile.tileHash ||
          snapshot.tile.tileHash !== event.tile.tileHash
        ) {
          fail("INTEGRITY_ERROR", `Snapshot altéré: ${path}`);
        }
        snapshotCount += 1;
      }
    }
    return {
      ok: true,
      events: state.events.length,
      tiles: state.tiles.size,
      snapshots: snapshotCount,
      ledgerHead: state.chain.head
    };
  }

  return Object.freeze({
    paths,
    ingest,
    get,
    list,
    touch,
    refreshTemperatures,
    link,
    compact,
    expand,
    reconstruct,
    verifyIntegrity
  });
}
