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
import { fileURLToPath } from "node:url";

export const INTELLIGENCE_CLASSES = Object.freeze([
  "LOCAL_FACT",
  "AUTHORIZED_EXTERNAL_FACT",
  "INFERENCE",
  "OPPORTUNITY"
]);
export const INTELLIGENCE_STATUSES = Object.freeze(["ACCEPTED", "QUARANTINED", "ARCHIVED"]);

const MODULE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const DEFAULT_CONFIG_PATH = join(MODULE_ROOT, "config", "daily-intelligence-journal.json");
const MAX_TITLE_CHARS = 300;
const MAX_SUMMARY_CHARS = 5_000;
const MAX_DETAILS_CHARS = 20_000;
const MAX_ARRAY_ITEMS = 50;
const MAX_BATCH_ITEMS = 100;
const MAX_LEDGER_LINE_CHARS = 256_000;

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

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
}

function atomicText(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, content.endsWith("\n") ? content : `${content}\n`, "utf8");
  renameSync(temporary, path);
}

function textFileHash(content) {
  const normalized = String(content).replace(/\r\n/g, "\n");
  return hash(normalized.endsWith("\n") ? normalized : `${normalized}\n`);
}

function cleanText(value, field, max) {
  if (typeof value !== "string" || !value.trim()) fail("INVALID_INPUT", `${field} doit être un texte non vide`);
  const text = value.replace(/\r\n/g, "\n").trim();
  if (text.length > max) fail("LIMIT_EXCEEDED", `${field} dépasse ${max} caractères`);
  return text;
}

function cleanOptionalText(value, field, max) {
  if (value === undefined || value === null || value === "") return "";
  return cleanText(value, field, max);
}

function cleanArray(value, field, { required = false, maxItems = MAX_ARRAY_ITEMS } = {}) {
  if (value === undefined || value === null) {
    if (required) return [];
    return [];
  }
  if (!Array.isArray(value) || value.length > maxItems) {
    fail("LIMIT_EXCEEDED", `${field} doit être un tableau de ${maxItems} éléments au maximum`);
  }
  return value.map((entry, index) => cleanText(String(entry), `${field}[${index}]`, 500));
}

function clamp01(value, field, fallback = 0.5) {
  const candidate = value === undefined ? fallback : Number(value);
  if (!Number.isFinite(candidate) || candidate < 0 || candidate > 1) {
    fail("INVALID_INPUT", `${field} doit être compris entre 0 et 1`);
  }
  return candidate;
}

function validDate(value) {
  if (value === undefined || value === null || value === "") return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isoDate(value, field, { required = false } = {}) {
  if (value === undefined || value === null || value === "") {
    if (required) return null;
    return null;
  }
  const date = validDate(value);
  if (!date) return null;
  return date.toISOString();
}

function redactText(value) {
  let text = String(value ?? "");
  const markers = new Set();
  const replace = (pattern, replacement, marker) => {
    text = text.replace(pattern, (...args) => {
      markers.add(marker);
      return typeof replacement === "function" ? replacement(...args) : replacement;
    });
  };
  replace(/```[\s\S]*?```/g, "[SOURCE_CODE_REDACTED]", "SOURCE_CODE");
  replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b/gi, "Bearer [SECRET_REDACTED]", "SECRET");
  replace(/\b(?:sk|pk|api)[-_][A-Za-z0-9_-]{8,}\b/gi, "[SECRET_REDACTED]", "SECRET");
  replace(
    /\b(password|passwd|secret|token|api[_ -]?key|private[_ -]?key)\b\s*[:=]\s*[^\s,;]+/gi,
    (_match, name) => `${name}=[SECRET_REDACTED]`,
    "SECRET"
  );
  replace(/[A-Z]:\\Users\\[^\\\s]+/gi, "[PRIVATE_USER_PATH]", "PRIVATE_PATH");
  replace(
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
    "[PRIVATE_EMAIL]",
    "PRIVATE_IDENTIFIER"
  );
  replace(
    /(?<!\d)(?:\+33|0)[1-9](?:[ .-]?\d{2}){4}(?!\d)/g,
    "[PRIVATE_PHONE]",
    "PRIVATE_IDENTIFIER"
  );
  return { text, markers: [...markers].sort() };
}

function redactObject(value, path = "", markers = new Set()) {
  if (typeof value === "string") {
    const redacted = redactText(value);
    for (const marker of redacted.markers) markers.add(`${path || "value"}:${marker}`);
    return { value: redacted.text, markers };
  }
  if (Array.isArray(value)) {
    const result = value.map((entry, index) => redactObject(entry, `${path}[${index}]`, markers).value);
    return { value: result, markers };
  }
  if (value && typeof value === "object") {
    const result = {};
    for (const [key, entry] of Object.entries(value)) {
      result[key] = redactObject(entry, path ? `${path}.${key}` : key, markers).value;
    }
    return { value: result, markers };
  }
  return { value, markers };
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

function eventHash(event) {
  const value = clone(event);
  delete value.eventHash;
  return hash(value);
}

function itemHash(item) {
  const value = clone(item);
  delete value.itemHash;
  return hash(value);
}

function verifyEvents(events) {
  let previous = null;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (event.previousEventHash !== previous) {
      fail("INTEGRITY_ERROR", `Chaîne du journal rompue ligne ${index + 1}`);
    }
    if (eventHash(event) !== event.eventHash) {
      fail("INTEGRITY_ERROR", `Événement du journal altéré ligne ${index + 1}`);
    }
    if (event.type === "ITEM_INGESTED" && itemHash(event.data.item) !== event.data.item.itemHash) {
      fail("INTEGRITY_ERROR", `Item du journal altéré ligne ${index + 1}`);
    }
    previous = event.eventHash;
  }
  return { ok: true, count: events.length, head: previous };
}

function rebuild(events) {
  const items = new Map();
  const reviews = [];
  for (const event of events) {
    if (event.type === "ITEM_INGESTED") {
      const item = event.data.item;
      if (items.has(item.id)) fail("INTEGRITY_ERROR", `Identifiant d'item répété: ${item.id}`);
      items.set(item.id, item);
    } else if (event.type === "DAILY_REVIEWS_GENERATED") {
      reviews.push(event.data);
    }
  }
  return { items, reviews };
}

function normalizeClass(value) {
  const candidate = String(value || "").toUpperCase();
  if (!INTELLIGENCE_CLASSES.includes(candidate)) {
    fail("INVALID_INPUT", `sourceClass invalide: ${value}`);
  }
  return candidate;
}

function localDay(date, timezone) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

function normalizeWords(value) {
  return String(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("fr-FR")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function preferenceFit(item, preferences) {
  const haystack = normalizeWords(
    [item.title, item.summary, item.details, ...item.topics, ...item.preferenceTags].join(" ")
  );
  let best = 0;
  for (const preference of preferences.priorities || []) {
    const words = normalizeWords(preference).split(" ").filter((word) => word.length >= 3);
    if (words.length === 0) continue;
    const hits = words.filter((word) => haystack.includes(word)).length;
    best = Math.max(best, hits / words.length);
  }
  return Number(best.toFixed(6));
}

function exclusionMatches(item, preferences) {
  const haystack = normalizeWords([item.title, item.summary, item.details, ...item.topics].join(" "));
  return (preferences.excludeByDefault || []).filter((rule) => {
    const words = normalizeWords(rule).split(" ").filter((word) => word.length >= 4);
    return words.length > 0 && words.every((word) => haystack.includes(word));
  });
}

function authorizedExternal(provenance, registry) {
  if (!Array.isArray(registry) || registry.length === 0) return false;
  return registry.some((entry) => {
    if (typeof entry === "string") {
      return provenance.authorizationId === entry || provenance.canonicalUrl?.startsWith(entry);
    }
    if (!entry || typeof entry !== "object" || entry.enabled === false) return false;
    if (entry.id && provenance.authorizationId === entry.id) return true;
    if (entry.canonicalUrlPrefix && provenance.canonicalUrl?.startsWith(entry.canonicalUrlPrefix)) return true;
    if (entry.publisher && provenance.publisher === entry.publisher) return true;
    return false;
  });
}

function localSourceAllowed(locator, localSources) {
  if (!locator || !Array.isArray(localSources)) return false;
  const normalized = String(locator).replace(/\//g, "\\").toLowerCase();
  return localSources.some((source) => {
    const allowed = String(source).replace(/\//g, "\\").replace(/\\+$/g, "").toLowerCase();
    return normalized === allowed || normalized.startsWith(`${allowed}\\`);
  });
}

function isMissing(value) {
  return (
    value === undefined ||
    value === null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

function evidenceReasons(sourceClass, provenance, sourceConfig, state, config, timestamp) {
  const reasons = [];
  for (const field of sourceConfig.minimumProvenance || []) {
    if (isMissing(provenance[field])) reasons.push(`MISSING_PROVENANCE:${field}`);
  }
  if (provenance.contentHash && !/^[a-f0-9]{32,128}$/i.test(String(provenance.contentHash))) {
    reasons.push("INVALID_PROVENANCE:contentHash");
  }
  const dateFields = ["observedAt", "publishedAt", "retrievedAt", "expiresAt", "nextVerification"];
  for (const field of dateFields) {
    if (provenance[field] && !validDate(provenance[field])) reasons.push(`INVALID_DATE:${field}`);
  }
  if (sourceClass === "LOCAL_FACT") {
    if (
      provenance.sourcePathOrEndpoint &&
      !localSourceAllowed(provenance.sourcePathOrEndpoint, config.localSources)
    ) {
      reasons.push("LOCAL_SOURCE_NOT_REGISTERED");
    }
  }
  if (sourceClass === "AUTHORIZED_EXTERNAL_FACT" && !authorizedExternal(provenance, config.externalSourceRegistry)) {
    reasons.push("EXTERNAL_SOURCE_NOT_AUTHORIZED");
  }
  if (sourceClass === "INFERENCE" || sourceClass === "OPPORTUNITY") {
    for (const supportingId of provenance.supportingItemIds || []) {
      const supporting = state.items.get(supportingId);
      if (!supporting) reasons.push(`SUPPORTING_ITEM_NOT_FOUND:${supportingId}`);
      else if (supporting.status !== "ACCEPTED") reasons.push(`SUPPORTING_ITEM_NOT_ACCEPTED:${supportingId}`);
    }
  }
  if (sourceClass === "INFERENCE") {
    if (provenance.confidence !== undefined) {
      const confidence = Number(provenance.confidence);
      if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
        reasons.push("INVALID_PROVENANCE:confidence");
      }
    }
    if (provenance.expiresAt && new Date(provenance.expiresAt) <= new Date(timestamp)) {
      reasons.push("EXPIRED");
    }
  }
  return [...new Set(reasons)].sort();
}

function effectiveDate(sourceClass, provenance, timestamp) {
  const value =
    provenance.observedAt ||
    provenance.publishedAt ||
    provenance.retrievedAt ||
    provenance.nextVerification ||
    timestamp;
  return validDate(value)?.toISOString() || timestamp;
}

function normalizeProvenance(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const result = clone(value);
  for (const field of [
    "observedAt",
    "publishedAt",
    "retrievedAt",
    "expiresAt",
    "nextVerification"
  ]) {
    if (result[field] && validDate(result[field])) result[field] = new Date(result[field]).toISOString();
  }
  if (result.supportingItemIds !== undefined) {
    result.supportingItemIds = cleanArray(result.supportingItemIds, "provenance.supportingItemIds");
  }
  if (result.confidence !== undefined && Number.isFinite(Number(result.confidence))) {
    result.confidence = Number(result.confidence);
  }
  return result;
}

function renderMarkdown(review) {
  const heading =
    review.audience === "USER"
      ? `# Revue quotidienne utilisateur — ${review.date}`
      : `# Revue quotidienne Owner — ${review.date}`;
  const lines = [
    heading,
    "",
    `Générée localement: ${review.generatedAt}`,
    `Fuseau: ${review.timezone}`,
    `Éléments: ${review.items.length}`,
    "",
    "> Les éléments INFERENCE et OPPORTUNITY sont des analyses, pas des faits. Leurs sources de soutien sont affichées.",
    ""
  ];
  if (review.items.length === 0) {
    lines.push("Aucun élément admissible aujourd'hui.", "");
  }
  for (const [index, item] of review.items.entries()) {
    const visibleLabel =
      item.sourceClass === "INFERENCE" || item.sourceClass === "OPPORTUNITY"
        ? `⚠ ${item.sourceClass}`
        : item.sourceClass;
    lines.push(
      `## ${index + 1}. [${visibleLabel}] ${item.title}`,
      "",
      `- Statut: ${item.status}`,
      `- Score: ${item.rankScore}`,
      `- Date de preuve: ${item.effectiveAt}`,
      `- Expiration: ${item.expiresAt || "non définie"}`
    );
    if (item.supportingItemIds?.length) {
      lines.push(`- Items sources: ${item.supportingItemIds.join(", ")}`);
    }
    if (item.quarantineReasons?.length) {
      lines.push(`- Quarantaine: ${item.quarantineReasons.join(", ")}`);
    }
    lines.push("", item.summary, "");
    if (review.audience === "OWNER") {
      lines.push(
        `- Projets: ${item.projectIds.join(", ") || "aucun"}`,
        `- Provenance: ${item.provenanceSummary}`,
        `- Empreinte: ${item.itemHash}`,
        ""
      );
    }
  }
  return lines.join("\n");
}

function renderSubsetMarkdown(title, date, generatedAt, items) {
  const lines = [`# ${title} — ${date}`, "", `Généré localement: ${generatedAt}`, ""];
  if (items.length === 0) lines.push("Aucun élément admissible.", "");
  for (const item of items) {
    lines.push(
      `## [${item.sourceClass}] ${item.title}`,
      "",
      `Score: ${item.rankScore}`,
      "",
      item.summary,
      ""
    );
    if (item.supportingItemIds?.length) lines.push(`Sources: ${item.supportingItemIds.join(", ")}`, "");
  }
  return lines.join("\n");
}

export function createDailyIntelligenceJournal({
  configPath = DEFAULT_CONFIG_PATH,
  config: injectedConfig,
  runtimeRoot,
  now = () => new Date()
} = {}) {
  const config = clone(injectedConfig || readJson(resolve(configPath)));
  if (config.enabled === false) fail("DISABLED", "Le journal quotidien est désactivé");
  const injectedRuntime = runtimeRoot !== undefined;
  const root = resolve(runtimeRoot || config.runtimeRoot);
  if (!injectedRuntime && !/^S:\\/i.test(root)) {
    fail("LOCAL_S_STORAGE_REQUIRED", `Le journal doit rester sur S: ${root}`);
  }
  if (!config.sourceClasses || !config.ranking || !config.preferences) {
    fail("INVALID_CONFIG", "Configuration du journal incomplète");
  }
  const weights = config.ranking.weights;
  const weightNames = [
    "preferenceFit",
    "projectImpact",
    "evidenceQuality",
    "urgency",
    "novelty",
    "actionability"
  ];
  for (const name of weightNames) clamp01(weights[name], `ranking.weights.${name}`);
  const weightTotal = weightNames.reduce((sum, name) => sum + weights[name], 0);
  if (Math.abs(weightTotal - 1) > 0.000001) fail("INVALID_CONFIG", "Les poids de ranking doivent totaliser 1");
  for (const field of [
    "maximumItemsUserReview",
    "maximumItemsOwnerReview",
    "deduplicateWindowDays"
  ]) {
    if (!Number.isInteger(config.ranking[field]) || config.ranking[field] < 1) {
      fail("INVALID_CONFIG", `ranking.${field} doit être un entier positif`);
    }
  }
  for (const sourceClass of INTELLIGENCE_CLASSES) {
    if (!config.sourceClasses[sourceClass]) {
      fail("INVALID_CONFIG", `sourceClasses.${sourceClass} est obligatoire`);
    }
  }

  const paths = Object.freeze({
    root,
    ledger: resolve(root, "daily-intelligence-ledger.jsonl"),
    reviews: resolve(root, "reviews"),
    lock: resolve(root, ".daily-intelligence.lock")
  });
  mkdirSync(paths.reviews, { recursive: true });

  function withLock(operation) {
    let descriptor;
    try {
      descriptor = openSync(paths.lock, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, at: new Date().toISOString() }));
    } catch (error) {
      if (error?.code === "EEXIST") fail("CONCURRENT_WRITE", "Une écriture du journal est déjà active");
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
    const integrity = verifyEvents(events);
    return { events, integrity, ...rebuild(events) };
  }

  function appendEvent(events, type, data, timestamp) {
    const event = {
      eventId: randomUUID(),
      timestamp,
      type,
      previousEventHash: events.at(-1)?.eventHash || null,
      data: clone(data)
    };
    event.eventHash = eventHash(event);
    const line = JSON.stringify(event);
    if (line.length > MAX_LEDGER_LINE_CHARS) {
      fail("LIMIT_EXCEEDED", `Événement supérieur à ${MAX_LEDGER_LINE_CHARS} caractères`);
    }
    appendFileSync(paths.ledger, `${line}\n`, "utf8");
    return event;
  }

  function ingest(input) {
    return withLock(() => {
      const timestamp = now().toISOString();
      const sourceClass = normalizeClass(input?.sourceClass);
      const state = load();
      const idempotencyKey = cleanOptionalText(input?.idempotencyKey, "idempotencyKey", 500);
      if (idempotencyKey) {
        const prior = [...state.items.values()].find((item) => item.idempotencyKeyHash === hash(idempotencyKey));
        if (prior) return { ok: true, idempotent: true, duplicate: true, item: clone(prior) };
      }
      const title = cleanText(input?.title, "title", MAX_TITLE_CHARS);
      const summary = cleanText(input?.summary, "summary", MAX_SUMMARY_CHARS);
      const details = cleanOptionalText(input?.details, "details", MAX_DETAILS_CHARS);
      const topics = cleanArray(input?.topics, "topics");
      const projectIds = cleanArray(input?.projectIds, "projectIds");
      const preferenceTags = cleanArray(input?.preferenceTags, "preferenceTags");
      const rawProvenance = normalizeProvenance(input?.provenance);
      const redacted = redactObject({
        title,
        summary,
        details,
        topics,
        projectIds,
        preferenceTags,
        provenance: rawProvenance
      });
      const content = redacted.value;
      const sourceConfig = config.sourceClasses[sourceClass];
      const reasons = evidenceReasons(
        sourceClass,
        content.provenance,
        sourceConfig,
        state,
        config,
        timestamp
      );
      const expiresAt =
        isoDate(input?.expiresAt, "expiresAt") ||
        isoDate(content.provenance.expiresAt, "provenance.expiresAt");
      if (input?.expiresAt && !expiresAt) reasons.push("INVALID_DATE:expiresAt");
      const expired = expiresAt && new Date(expiresAt) <= new Date(timestamp);
      const status = expired
        ? "ARCHIVED"
        : reasons.length > 0
          ? "QUARANTINED"
          : "ACCEPTED";
      const labels = [sourceClass];
      if (sourceClass === "INFERENCE" || sourceClass === "OPPORTUNITY") {
        labels.push("ANALYSIS_NOT_FACT", "SOURCE_REFERENCES_REQUIRED");
      }
      const rankSignals = {
        projectImpact: clamp01(input?.rankSignals?.projectImpact, "rankSignals.projectImpact"),
        evidenceQuality: clamp01(
          input?.rankSignals?.evidenceQuality,
          "rankSignals.evidenceQuality",
          reasons.length === 0 ? 1 : 0
        ),
        urgency: clamp01(input?.rankSignals?.urgency, "rankSignals.urgency"),
        novelty: clamp01(input?.rankSignals?.novelty, "rankSignals.novelty"),
        actionability: clamp01(input?.rankSignals?.actionability, "rankSignals.actionability")
      };
      const provisional = {
        id: randomUUID(),
        idempotencyKeyHash: idempotencyKey ? hash(idempotencyKey) : null,
        sourceClass,
        labels,
        title: content.title,
        summary: content.summary,
        details: content.details,
        topics: content.topics,
        projectIds: content.projectIds,
        preferenceTags: content.preferenceTags,
        provenance: content.provenance,
        effectiveAt: effectiveDate(sourceClass, content.provenance, timestamp),
        expiresAt,
        status,
        quarantineReasons: [...new Set(reasons)].sort(),
        redactions: [...redacted.markers],
        rankSignals,
        createdAt: timestamp
      };
      provisional.contentFingerprint = hash({
        sourceClass,
        title: normalizeWords(provisional.title),
        summary: normalizeWords(provisional.summary),
        supportingItemIds: provisional.provenance.supportingItemIds || []
      });
      const windowMs = config.ranking.deduplicateWindowDays * 86_400_000;
      const duplicate = [...state.items.values()].find(
        (item) =>
          item.contentFingerprint === provisional.contentFingerprint &&
          new Date(timestamp) - new Date(item.createdAt) <= windowMs
      );
      if (duplicate) return { ok: true, idempotent: true, duplicate: true, item: clone(duplicate) };
      provisional.itemHash = itemHash(provisional);
      appendEvent(state.events, "ITEM_INGESTED", { item: provisional }, timestamp);
      return {
        ok: true,
        idempotent: false,
        duplicate: false,
        quarantined: status === "QUARANTINED",
        item: clone(provisional)
      };
    });
  }

  function ingestMany(inputs) {
    if (!Array.isArray(inputs) || inputs.length > MAX_BATCH_ITEMS) {
      fail("LIMIT_EXCEEDED", `Un lot contient au maximum ${MAX_BATCH_ITEMS} items`);
    }
    return inputs.map((input) => ingest(input));
  }

  function listItems({ sourceClass, status } = {}) {
    const state = load();
    return [...state.items.values()]
      .filter((item) => !sourceClass || item.sourceClass === String(sourceClass).toUpperCase())
      .filter((item) => !status || item.status === String(status).toUpperCase())
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
      .map(clone);
  }

  function ranked({ audience = "USER", at = now() } = {}) {
    const targetAudience = String(audience).toUpperCase();
    if (!["USER", "OWNER"].includes(targetAudience)) {
      fail("INVALID_INPUT", "audience doit valoir USER ou OWNER");
    }
    const timestamp = new Date(at);
    const items = listItems();
    return items
      .map((item) => {
        const expired = item.expiresAt && new Date(item.expiresAt) <= timestamp;
        const exclusions = exclusionMatches(item, config.preferences);
        const fit = preferenceFit(item, config.preferences);
        const evidence = item.status === "QUARANTINED" ? 0 : item.rankSignals.evidenceQuality;
        const rankScore = Number(
          (
            weights.preferenceFit * fit +
            weights.projectImpact * item.rankSignals.projectImpact +
            weights.evidenceQuality * evidence +
            weights.urgency * item.rankSignals.urgency +
            weights.novelty * item.rankSignals.novelty +
            weights.actionability * item.rankSignals.actionability
          ).toFixed(6)
        );
        return {
          ...item,
          preferenceFit: fit,
          exclusionMatches: exclusions,
          rankScore,
          archivedFromView: item.status === "ARCHIVED" || Boolean(expired)
        };
      })
      .filter((item) => !item.archivedFromView)
      .filter((item) => targetAudience === "OWNER" || item.status === "ACCEPTED")
      .filter((item) => targetAudience === "OWNER" || item.exclusionMatches.length === 0)
      .sort((left, right) => {
        if (targetAudience === "OWNER" && left.status !== right.status) {
          return Number(left.status === "QUARANTINED") - Number(right.status === "QUARANTINED");
        }
        return right.rankScore - left.rankScore || right.effectiveAt.localeCompare(left.effectiveAt);
      })
      .map(clone);
  }

  function reviewItem(item, audience) {
    const base = {
      id: item.id,
      sourceClass: item.sourceClass,
      labels: item.labels,
      title: item.title,
      summary: item.summary,
      status: item.status,
      rankScore: item.rankScore,
      preferenceFit: item.preferenceFit,
      effectiveAt: item.effectiveAt,
      expiresAt: item.expiresAt,
      supportingItemIds: item.provenance.supportingItemIds || [],
      quarantineReasons: item.quarantineReasons
    };
    if (audience === "OWNER") {
      return {
        ...base,
        details: item.details,
        topics: item.topics,
        projectIds: item.projectIds,
        rankSignals: item.rankSignals,
        exclusionMatches: item.exclusionMatches,
        provenance: item.provenance,
        provenanceSummary: [
          item.provenance.sourceType || item.provenance.publisher || item.sourceClass,
          item.provenance.sourceId ||
            item.provenance.sourcePathOrEndpoint ||
            item.provenance.canonicalUrl ||
            "non prouvé"
        ].join(" — "),
        redactions: item.redactions,
        itemHash: item.itemHash
      };
    }
    return base;
  }

  function writeReviewFiles(directory, basename, review, markdown, contentKey) {
    const versionedBase = `${basename}-${contentKey.slice(0, 16)}`;
    const versionedJson = join(directory, `${versionedBase}.json`);
    const versionedMarkdown = join(directory, `${versionedBase}.md`);
    const currentJson = join(directory, `${basename}.json`);
    const currentMarkdown = join(directory, `${basename}.md`);
    if (!existsSync(versionedJson)) atomicText(versionedJson, JSON.stringify(review, null, 2));
    if (!existsSync(versionedMarkdown)) atomicText(versionedMarkdown, markdown);
    atomicText(currentJson, JSON.stringify(review, null, 2));
    atomicText(currentMarkdown, markdown);
    return { versionedJson, versionedMarkdown, currentJson, currentMarkdown };
  }

  function verifyReviewRecord(review) {
    for (const audience of ["user", "owner"]) {
      const jsonPath = review.files?.[audience]?.versionedJson;
      const markdownPath = review.files?.[audience]?.versionedMarkdown;
      if (!jsonPath || !existsSync(jsonPath)) fail("INTEGRITY_ERROR", `Revue ${audience} JSON manquante`);
      if (!markdownPath || !existsSync(markdownPath)) {
        fail("INTEGRITY_ERROR", `Revue ${audience} Markdown manquante`);
      }
      const jsonContent = readJson(jsonPath);
      const markdownContent = readFileSync(markdownPath, "utf8").replace(/\r\n/g, "\n");
      const expectedJson = audience === "user" ? review.userHash : review.ownerHash;
      const expectedMarkdown =
        audience === "user" ? review.userMarkdownHash : review.ownerMarkdownHash;
      if (hash(jsonContent) !== expectedJson) fail("INTEGRITY_ERROR", `Revue ${audience} JSON altérée`);
      if (textFileHash(markdownContent) !== expectedMarkdown) {
        fail("INTEGRITY_ERROR", `Revue ${audience} Markdown altérée`);
      }
    }
  }

  function generateDailyReviews({ at = now() } = {}) {
    return withLock(() => {
      const timestamp = new Date(at).toISOString();
      const date = localDay(new Date(at), config.timezone);
      const state = load();
      const userItems = ranked({ audience: "USER", at }).slice(
        0,
        config.ranking.maximumItemsUserReview
      );
      const ownerItems = ranked({ audience: "OWNER", at }).slice(
        0,
        config.ranking.maximumItemsOwnerReview
      );
      const selectionFingerprint = hash({
        date,
        rankingConfig: {
          preferences: config.preferences,
          weights: config.ranking.weights,
          maximumItemsUserReview: config.ranking.maximumItemsUserReview,
          maximumItemsOwnerReview: config.ranking.maximumItemsOwnerReview
        },
        user: userItems.map((item) => ({ itemHash: item.itemHash, rankScore: item.rankScore })),
        owner: ownerItems.map((item) => ({ itemHash: item.itemHash, rankScore: item.rankScore }))
      });
      const prior = [...state.reviews]
        .reverse()
        .find((review) => review.date === date && review.selectionFingerprint === selectionFingerprint);
      if (prior) {
        verifyReviewRecord(prior);
        return { ok: true, idempotent: true, ...clone(prior) };
      }
      const userReview = {
        schema: "aione.daily-user-review.v1",
        audience: "USER",
        date,
        generatedAt: timestamp,
        timezone: config.timezone,
        items: userItems.map((item) => reviewItem(item, "USER"))
      };
      const ownerReview = {
        schema: "aione.daily-owner-review.v1",
        audience: "OWNER",
        ownerId: config.preferences.ownerId,
        date,
        generatedAt: timestamp,
        timezone: config.timezone,
        items: ownerItems.map((item) => reviewItem(item, "OWNER"))
      };
      const userHash = hash(userReview);
      const ownerHash = hash(ownerReview);
      const userMarkdown = renderMarkdown(userReview);
      const ownerMarkdown = renderMarkdown(ownerReview);
      const userMarkdownHash = textFileHash(userMarkdown);
      const ownerMarkdownHash = textFileHash(ownerMarkdown);
      const outputDirectory = join(paths.reviews, date);
      mkdirSync(outputDirectory, { recursive: true });
      const files = {
        user: writeReviewFiles(
          outputDirectory,
          "daily-user-review",
          userReview,
          userMarkdown,
          userHash
        ),
        owner: writeReviewFiles(
          outputDirectory,
          "daily-owner-review",
          ownerReview,
          ownerMarkdown,
          ownerHash
        )
      };
      if ((config.outputs || []).includes("local-operations-news")) {
        const localItems = userReview.items.filter((item) => item.sourceClass === "LOCAL_FACT");
        const localOutput = {
          schema: "aione.local-operations-news.v1",
          date,
          generatedAt: timestamp,
          items: localItems
        };
        files.localOperations = writeReviewFiles(
          outputDirectory,
          "local-operations-news",
          localOutput,
          renderSubsetMarkdown("Actualités des opérations locales", date, timestamp, localItems),
          hash(localOutput)
        );
      }
      if ((config.outputs || []).includes("opportunity-watch")) {
        const opportunityItems = ownerReview.items.filter((item) =>
          ["OPPORTUNITY", "INFERENCE"].includes(item.sourceClass)
        );
        const opportunityOutput = {
          schema: "aione.opportunity-watch.v1",
          date,
          generatedAt: timestamp,
          warning: "INFERENCE et OPPORTUNITY ne sont pas des faits; vérifier les items sources.",
          items: opportunityItems
        };
        files.opportunityWatch = writeReviewFiles(
          outputDirectory,
          "opportunity-watch",
          opportunityOutput,
          renderSubsetMarkdown("Veille opportunités et inférences", date, timestamp, opportunityItems),
          hash(opportunityOutput)
        );
      }
      const record = {
        date,
        generatedAt: timestamp,
        selectionFingerprint,
        userHash,
        ownerHash,
        userMarkdownHash,
        ownerMarkdownHash,
        counts: {
          user: userReview.items.length,
          owner: ownerReview.items.length,
          quarantinedOwner: ownerReview.items.filter((item) => item.status === "QUARANTINED").length
        },
        files
      };
      appendEvent(state.events, "DAILY_REVIEWS_GENERATED", record, timestamp);
      return { ok: true, idempotent: false, ...clone(record), userReview, ownerReview };
    });
  }

  function verifyIntegrity() {
    const state = load();
    for (const review of state.reviews) verifyReviewRecord(review);
    return {
      ok: true,
      events: state.events.length,
      items: state.items.size,
      reviews: state.reviews.length,
      ledgerHead: state.integrity.head
    };
  }

  return Object.freeze({
    config: Object.freeze(config),
    paths,
    ingest,
    ingestMany,
    listItems,
    ranked,
    generateDailyReviews,
    verifyIntegrity
  });
}
