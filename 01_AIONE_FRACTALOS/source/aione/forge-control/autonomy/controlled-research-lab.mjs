import { createHash } from "node:crypto";
import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { renameWithRetry } from "./atomic-file.mjs";

const SCHEMA = "aione.controlled-research-lab.v1";
const PROVIDERS = new Set(["ARXIV_ATOM", "WIKIMEDIA_JSON", "OPENALEX_JSON"]);
const PROMPT_PATTERNS = Object.freeze([
  /ignore\s+(all\s+)?previous\s+(instructions?|prompts?)/iu,
  /disregard\s+(all\s+)?(prior|previous)\s+(instructions?|prompts?)/iu,
  /(?:system|developer)\s+(?:message|prompt)\s*:/iu,
  /(?:begin|end)\s+(?:system|developer|assistant)\s+(?:message|prompt)/iu,
  /you\s+are\s+(?:chatgpt|an?\s+assistant|an?\s+agent)/iu,
  /(?:execute|run|invoke|call)\s+(?:this\s+)?(?:command|shell|tool|function)/iu,
  /(?:reveal|print|return|exfiltrate)\s+(?:the\s+)?(?:secret|token|password|system\s+prompt)/iu,
  /prompt\s*injection|jailbreak/iu
]);
const STOP_WORDS = new Set([
  "about", "after", "ainsi", "avec", "based", "comme", "dans", "des", "elle", "elles", "entre",
  "from", "have", "leur", "leurs", "mais", "more", "nous", "pour", "sans", "that", "the", "this",
  "through", "une", "using", "vers", "with", "your", "aux", "and", "are", "les", "sur", "par", "qui",
  "que", "est", "être", "etre", "into", "than", "these", "those", "such", "also", "been", "when"
]);
const DEFAULT_BUDGETS = Object.freeze({
  maxSourcesPerRun: 3,
  maxRequestsPerRun: 3,
  maxItemsPerSource: 20,
  maxItemsPerRun: 50,
  maxBytesPerResponse: 1_000_000,
  maxBytesPerRun: 2_000_000,
  timeoutMs: 8_000,
  maxGraphNodes: 160,
  maxGraphEdges: 420,
  maxGraphDepth: 3,
  maxProposalsPerRun: 8
});

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function sha256(value) {
  return createHash("sha256").update(String(value), "utf8").digest("hex");
}

function boundedInteger(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, parsed));
}

function boundedText(value, maximum = 4_000) {
  return String(value ?? "").replaceAll("\0", "").replace(/\s+/gu, " ").trim().slice(0, maximum);
}

function uniqueStrings(values, maximum = 100) {
  return [...new Set((Array.isArray(values) ? values : [])
    .map((value) => boundedText(value, 300))
    .filter(Boolean))].slice(0, maximum);
}

function normalizeKey(value) {
  return boundedText(value, 1_000)
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, " ")
    .trim();
}

function decodeEntities(value) {
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
  return String(value ?? "").replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/giu, (match, entity) => {
    if (entity[0] === "#") {
      const hexadecimal = entity[1]?.toLowerCase() === "x";
      const code = Number.parseInt(entity.slice(hexadecimal ? 2 : 1), hexadecimal ? 16 : 10);
      return Number.isSafeInteger(code) ? String.fromCodePoint(code) : match;
    }
    return named[entity.toLowerCase()] ?? match;
  });
}

function stripMarkup(value) {
  return boundedText(decodeEntities(String(value ?? "").replace(/<[^>]*>/gu, " ")), 4_000);
}

function xmlValue(fragment, tag) {
  const match = fragment.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, "iu"));
  return match ? stripMarkup(match[1]) : "";
}

function xmlAttribute(fragment, tag, attribute, predicate = () => true) {
  const expression = new RegExp(`<${tag}\\b([^>]*)\\/?\\s*>`, "giu");
  for (const match of fragment.matchAll(expression)) {
    const attributes = Object.fromEntries([...match[1].matchAll(/([\w:-]+)\s*=\s*["']([^"']*)["']/gu)]
      .map((item) => [item[1], decodeEntities(item[2])]));
    if (predicate(attributes) && attributes[attribute]) return boundedText(attributes[attribute], 2_000);
  }
  return "";
}

function parseArxivAtom(text, maximum) {
  return [...String(text).matchAll(/<entry(?:\s[^>]*)?>([\s\S]*?)<\/entry>/giu)].slice(0, maximum).map((match) => {
    const entry = match[1];
    const authors = [...entry.matchAll(/<author(?:\s[^>]*)?>([\s\S]*?)<\/author>/giu)]
      .map((author) => xmlValue(author[1], "name"));
    const categories = [...entry.matchAll(/<category\b([^>]*)\/?\s*>/giu)]
      .map((category) => xmlAttribute(`<category ${category[1]}>`, "category", "term"));
    const id = xmlValue(entry, "id");
    return {
      externalId: id,
      title: xmlValue(entry, "title"),
      summary: xmlValue(entry, "summary"),
      publishedAt: xmlValue(entry, "published") || xmlValue(entry, "updated"),
      updatedAt: xmlValue(entry, "updated"),
      authors: uniqueStrings(authors, 30),
      categories: uniqueStrings(categories, 30),
      canonicalUrl: xmlAttribute(entry, "link", "href", (attributes) => attributes.rel === "alternate") || id,
      doi: xmlValue(entry, "arxiv:doi") || xmlValue(entry, "doi"),
      itemType: "paper"
    };
  });
}

function parseWikimediaJson(payload, maximum) {
  const search = Array.isArray(payload?.query?.search) ? payload.query.search : [];
  const pagesObject = payload?.query?.pages && typeof payload.query.pages === "object"
    ? Object.values(payload.query.pages)
    : [];
  const pages = Array.isArray(payload?.pages) ? payload.pages : pagesObject;
  return [...search, ...pages].slice(0, maximum).map((item) => ({
    externalId: String(item.pageid ?? item.id ?? item.key ?? item.title ?? ""),
    title: boundedText(item.title ?? item.displaytitle ?? item.name, 500),
    summary: stripMarkup(item.snippet ?? item.extract ?? item.description ?? ""),
    publishedAt: boundedText(item.timestamp ?? item.touched ?? "", 100),
    updatedAt: boundedText(item.timestamp ?? item.touched ?? "", 100),
    authors: [],
    categories: uniqueStrings(item.categories?.map((category) => category.title ?? category) ?? [], 30),
    canonicalUrl: boundedText(item.fullurl ?? item.content_urls?.desktop?.page ?? "", 2_000),
    doi: "",
    itemType: "encyclopedia-metadata"
  }));
}

function parseOpenAlexJson(payload, maximum) {
  const results = Array.isArray(payload?.results) ? payload.results : Array.isArray(payload) ? payload : [];
  return results.slice(0, maximum).map((item) => ({
    externalId: boundedText(item.id ?? item.ids?.openalex ?? "", 500),
    title: boundedText(item.display_name ?? item.title, 500),
    summary: boundedText([
      item.type ? `Type: ${item.type}.` : "",
      Number.isFinite(item.cited_by_count) ? `Cited by: ${item.cited_by_count}.` : ""
    ].filter(Boolean).join(" "), 1_000),
    publishedAt: boundedText(item.publication_date ?? item.created_date ?? "", 100),
    updatedAt: boundedText(item.updated_date ?? "", 100),
    authors: uniqueStrings((item.authorships ?? []).map((entry) => entry.author?.display_name), 30),
    categories: uniqueStrings([
      ...(item.concepts ?? []).map((concept) => concept.display_name),
      ...(item.topics ?? []).map((topic) => topic.display_name)
    ], 30),
    canonicalUrl: boundedText(item.primary_location?.landing_page_url ?? item.doi ?? item.id, 2_000),
    doi: boundedText(item.doi ?? item.ids?.doi ?? "", 500),
    itemType: boundedText(item.type ?? "research-work", 100)
  }));
}

function parseProvider(provider, text, maximum) {
  if (provider === "ARXIV_ATOM") return parseArxivAtom(text, maximum);
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`${provider}: réponse JSON invalide.`);
  }
  if (provider === "WIKIMEDIA_JSON") return parseWikimediaJson(payload, maximum);
  if (provider === "OPENALEX_JSON") return parseOpenAlexJson(payload, maximum);
  throw new Error(`Provider non supporté: ${provider}`);
}

function promptSignals(item) {
  const inspected = [item.title, item.summary, ...(item.authors ?? []), ...(item.categories ?? [])].join("\n");
  return PROMPT_PATTERNS.flatMap((pattern) => pattern.test(inspected) ? [pattern.source] : []);
}

function itemIdentity(item) {
  const doi = normalizeKey(String(item.doi ?? "").replace(/^https?:\/\/(?:dx\.)?doi\.org\//iu, ""));
  if (doi) return `doi:${doi}`;
  const title = normalizeKey(item.title);
  const year = String(item.publishedAt ?? "").match(/\b(?:19|20)\d{2}\b/u)?.[0] ?? "";
  if (title) return `title:${title}:${year}`;
  return `external:${normalizeKey(item.externalId || item.canonicalUrl)}`;
}

function conceptTerms(item) {
  const explicit = uniqueStrings(item.categories ?? [], 30).map(normalizeKey).filter(Boolean);
  const words = normalizeKey(item.title).split(" ")
    .filter((word) => word.length >= 4 && !STOP_WORDS.has(word) && !/^\d+$/u.test(word));
  const pairs = words.slice(0, 12).flatMap((word, index) => index < words.length - 1 ? [`${word} ${words[index + 1]}`] : []);
  return uniqueStrings([...explicit, ...words, ...pairs], 40);
}

function graphCoordinates(id) {
  const digest = sha256(id);
  const angle = (Number.parseInt(digest.slice(0, 8), 16) / 0xffffffff) * Math.PI * 2;
  const radius = 0.28 + (Number.parseInt(digest.slice(8, 16), 16) / 0xffffffff) * 0.68;
  return {
    x: Number((Math.cos(angle) * radius).toFixed(6)),
    y: Number((Math.sin(angle) * radius).toFixed(6))
  };
}

function defaultState() {
  return {
    schema: SCHEMA,
    revision: 0,
    items: [],
    quarantine: [],
    proposals: [],
    tiles: [],
    runs: [],
    sourceHealth: {},
    ledgerHead: null
  };
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function atomicWriteJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  renameWithRetry(temporary, path);
}

function loadState(path) {
  if (!existsSync(path)) return defaultState();
  let loaded;
  try {
    loaded = JSON.parse(readFileSync(path, "utf8"));
  } catch {
    throw new Error("RESEARCH_STATE_CORRUPTED");
  }
  const base = defaultState();
  return {
    ...base,
    ...loaded,
    items: Array.isArray(loaded.items) ? loaded.items : [],
    quarantine: Array.isArray(loaded.quarantine) ? loaded.quarantine : [],
    proposals: Array.isArray(loaded.proposals) ? loaded.proposals : [],
    tiles: Array.isArray(loaded.tiles) ? loaded.tiles : [],
    runs: Array.isArray(loaded.runs) ? loaded.runs : [],
    sourceHealth: loaded.sourceHealth && typeof loaded.sourceHealth === "object" ? loaded.sourceHealth : {}
  };
}

function normalizedBudgets(input = {}) {
  return Object.freeze({
    maxSourcesPerRun: boundedInteger(input.maxSourcesPerRun, DEFAULT_BUDGETS.maxSourcesPerRun, 1, 20),
    maxRequestsPerRun: boundedInteger(input.maxRequestsPerRun, DEFAULT_BUDGETS.maxRequestsPerRun, 1, 20),
    maxItemsPerSource: boundedInteger(input.maxItemsPerSource, DEFAULT_BUDGETS.maxItemsPerSource, 1, 200),
    maxItemsPerRun: boundedInteger(input.maxItemsPerRun, DEFAULT_BUDGETS.maxItemsPerRun, 1, 500),
    maxBytesPerResponse: boundedInteger(input.maxBytesPerResponse, DEFAULT_BUDGETS.maxBytesPerResponse, 1_024, 10_000_000),
    maxBytesPerRun: boundedInteger(input.maxBytesPerRun, DEFAULT_BUDGETS.maxBytesPerRun, 1_024, 30_000_000),
    timeoutMs: boundedInteger(input.timeoutMs, DEFAULT_BUDGETS.timeoutMs, 50, 120_000),
    maxGraphNodes: boundedInteger(input.maxGraphNodes, DEFAULT_BUDGETS.maxGraphNodes, 1, 2_000),
    maxGraphEdges: boundedInteger(input.maxGraphEdges, DEFAULT_BUDGETS.maxGraphEdges, 0, 10_000),
    maxGraphDepth: boundedInteger(input.maxGraphDepth, DEFAULT_BUDGETS.maxGraphDepth, 0, 8),
    maxProposalsPerRun: boundedInteger(input.maxProposalsPerRun, DEFAULT_BUDGETS.maxProposalsPerRun, 0, 100)
  });
}

function normalizeSource(source) {
  const provider = String(source.provider ?? "").toUpperCase();
  if (!PROVIDERS.has(provider)) throw new Error(`Provider interdit: ${provider || "absent"}`);
  const id = boundedText(source.id, 120);
  if (!id) throw new Error("Identifiant de source requis.");
  const baseUrl = new URL(source.baseUrl);
  const allowedHosts = uniqueStrings(source.allowedHosts?.length ? source.allowedHosts : [baseUrl.hostname], 20)
    .map((host) => host.toLowerCase());
  validateHttpsUrl(baseUrl, allowedHosts);
  return Object.freeze({
    id,
    provider,
    baseUrl: baseUrl.href,
    allowedHosts,
    enabled: source.enabled !== false,
    optional: source.optional !== false,
    ecosystemId: boundedText(source.ecosystemId || "aione-core", 200),
    minimumDelayMs: boundedInteger(source.minimumDelayMs, provider === "ARXIV_ATOM" ? 3_000 : 0, 0, 60_000),
    cacheTtlMs: boundedInteger(source.cacheTtlMs, 86_400_000, 60_000, 604_800_000)
  });
}

function validateHttpsUrl(input, allowedHosts) {
  const url = input instanceof URL ? new URL(input.href) : new URL(String(input));
  if (url.protocol !== "https:") throw new Error("SOURCE_URL_HTTPS_REQUIRED");
  if (url.username || url.password) throw new Error("SOURCE_URL_CREDENTIALS_FORBIDDEN");
  if (url.port && url.port !== "443") throw new Error("SOURCE_URL_PORT_FORBIDDEN");
  if (url.hash) throw new Error("SOURCE_URL_FRAGMENT_FORBIDDEN");
  const hostname = url.hostname.toLowerCase();
  if (
    hostname === "localhost" ||
    hostname.endsWith(".localhost") ||
    hostname.endsWith(".local") ||
    /^\d+(?:\.\d+){3}$/u.test(hostname) ||
    hostname.includes(":")
  ) {
    throw new Error("SOURCE_HOST_LITERAL_OR_LOCAL_FORBIDDEN");
  }
  if (!allowedHosts.map((host) => host.toLowerCase()).includes(hostname)) {
    throw new Error(`SOURCE_HOST_NOT_ALLOWLISTED:${url.hostname}`);
  }
  return url;
}

async function readBoundedBody(response, maximumBytes) {
  const declaredLength = Number(response.headers?.get?.("content-length") || 0);
  if (declaredLength > maximumBytes) throw new Error("RESPONSE_SIZE_BUDGET_EXCEEDED");
  if (response.body?.getReader) {
    const reader = response.body.getReader();
    const chunks = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maximumBytes) {
        await reader.cancel("response-size-budget").catch(() => {});
        throw new Error("RESPONSE_SIZE_BUDGET_EXCEEDED");
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return { text: new TextDecoder().decode(bytes), bytes: total };
  }
  const buffer = new Uint8Array(await response.arrayBuffer());
  if (buffer.byteLength > maximumBytes) throw new Error("RESPONSE_SIZE_BUDGET_EXCEEDED");
  return { text: new TextDecoder().decode(buffer), bytes: buffer.byteLength };
}

function accessProviders(sourceHealth) {
  const connectorStates = Object.values(sourceHealth ?? {});
  const anyHealthy = connectorStates.some((entry) => ["HEALTHY", "HEALTHY_CACHE_FRESH"].includes(entry.state));
  return [
    {
      id: "FREE_LOCAL",
      price: "FREE",
      state: "ACTIVE",
      executable: true,
      scope: ["cache", "graph", "tiles", "proposals", "roadmaps"]
    },
    {
      id: "OPTIONAL_FREE_CONNECTOR",
      price: "FREE",
      state: anyHealthy ? "ACTIVE" : "DEGRADABLE",
      executable: true,
      scope: ["allowlisted-metadata-fetch"],
      fallback: "FREE_LOCAL"
    },
    {
      id: "FUTURE_PAID",
      price: "UNDEFINED",
      state: "DISABLED",
      executable: false,
      routesEnabled: false,
      scope: []
    }
  ];
}

export class ControlledResearchLab {
  constructor({
    config = {},
    runtimeRoot,
    fetch: injectedFetch,
    fetchImpl,
    clock = () => new Date(),
    nowMs = () => Date.now(),
    sleep = (milliseconds) => new Promise((resolveSleep) => setTimeout(resolveSleep, milliseconds))
  } = {}) {
    if (!runtimeRoot) throw new Error("runtimeRoot requis.");
    this.runtimeRoot = resolve(runtimeRoot);
    this.fetch = injectedFetch || fetchImpl || globalThis.fetch;
    if (typeof this.fetch !== "function") throw new Error("fetch injecté requis.");
    this.clock = clock;
    this.nowMs = nowMs;
    this.sleep = sleep;
    this.userAgent = boundedText(
      config.userAgent || "AIONE-ControlledResearchLab/1.0 (local-first; contact=portfolio@example.invalid)",
      300
    );
    if (!/^AIONE[-/]/u.test(this.userAgent) || !/(?:https?:\/\/|mailto:|contact=)/iu.test(this.userAgent)) {
      throw new Error("RESEARCH_USER_AGENT_IDENTITY_REQUIRED");
    }
    this.budgets = normalizedBudgets(config.budgets);
    this.sources = (config.sources ?? []).map(normalizeSource);
    this.paths = Object.freeze({
      state: join(this.runtimeRoot, "state.json"),
      ledger: join(this.runtimeRoot, "ledger.jsonl"),
      cache: join(this.runtimeRoot, "cache")
    });
    mkdirSync(this.paths.cache, { recursive: true });
    this.state = loadState(this.paths.state);
    this.running = false;
    this.hostLastRequestAt = new Map();
  }

  status() {
    const integrity = this.#persistenceIntegrity();
    return {
      schema: "aione.controlled-research-lab-status.v1",
      mode: "CONTROLLED_METADATA_ONLY",
      enabled: true,
      sources: this.sources.map((source) => ({
        id: source.id,
        provider: source.provider,
        host: new URL(source.baseUrl).hostname,
        enabled: source.enabled,
        optional: source.optional,
        minimumDelayMs: source.minimumDelayMs,
        cacheTtlMs: source.cacheTtlMs,
        health: this.state.sourceHealth[source.id] ?? { state: "NOT_RUN" }
      })),
      budgets: this.budgets,
      counts: {
        items: this.state.items.length,
        quarantined: this.state.quarantine.length,
        proposals: this.state.proposals.length,
        tiles: this.state.tiles.length,
        runs: this.state.runs.length
      },
      accessProviders: accessProviders(this.state.sourceHealth),
      integrity,
      invariants: {
        metadataOnly: true,
        publicationAllowed: false,
        installationAllowed: false,
        integrationAllowed: false,
        automaticExecutionAllowed: false
      }
    };
  }

  simulate(request = {}) {
    const queries = this.#queries(request);
    return {
      schema: "aione.controlled-research-simulation.v1",
      valid: queries.length > 0,
      mutationPerformed: false,
      networkPerformed: false,
      queries: queries.map(({ source, url, ecosystemId }) => ({
        sourceId: source.id,
        provider: source.provider,
        host: url.hostname,
        ecosystemId
      })),
      budgets: this.budgets,
      accessProviders: accessProviders(this.state.sourceHealth),
      expectedArtifacts: ["metadata", "unitile", "tile", "kilotile", "concept-graph", "non-executable-proposal", "roadmaps"],
      forbiddenArtifacts: ["downloaded-code", "installed-package", "publication", "automatic-integration"]
    };
  }

  async run(request = {}) {
    if (this.running) throw new Error("RESEARCH_CYCLE_ALREADY_RUNNING");
    const ledger = this.#persistenceIntegrity();
    if (!ledger.ok) throw new Error("LEDGER_INTEGRITY_ERROR");
    this.running = true;
    const runId = `research-run-${sha256(`${this.clock().toISOString()}|${this.state.revision + 1}`).slice(0, 20)}`;
    const queries = this.#queries(request);
    const run = {
      id: runId,
      startedAt: this.clock().toISOString(),
      completedAt: null,
      state: "RUNNING",
      offlineRequested: request.offline === true,
      sourceResults: [],
      accepted: 0,
      duplicates: 0,
      quarantined: 0,
      bytes: 0,
      proposalIds: [],
      tileIds: []
    };
    this.#appendLedger("RUN_STARTED", { runId, queries: queries.map((entry) => entry.source.id), offline: run.offlineRequested });
    try {
      for (const query of queries) {
        if (run.bytes >= this.budgets.maxBytesPerRun || run.accepted >= this.budgets.maxItemsPerRun) break;
        const result = await this.#ingestQuery(query, run, request.offline === true);
        run.sourceResults.push(result);
      }
      const created = this.#createRunArtifacts(run);
      run.proposalIds = created.proposalIds;
      run.tileIds = created.tileIds;
      run.completedAt = this.clock().toISOString();
      run.state = run.sourceResults.some((entry) => entry.state === "FETCHED")
        ? "COMPLETED"
        : run.sourceResults.some((entry) => entry.state.startsWith("CACHE_HIT"))
          ? run.offlineRequested ? "COMPLETED_OFFLINE" : "COMPLETED_CACHED"
          : "DEGRADED_NO_DATA";
      this.#appendLedger("RUN_COMPLETED", {
        runId,
        state: run.state,
        accepted: run.accepted,
        duplicates: run.duplicates,
        quarantined: run.quarantined,
        proposalIds: run.proposalIds
      });
      this.state.runs.push(run);
      this.state.runs = this.state.runs.slice(-200);
      this.state.revision += 1;
      this.state.ledgerHead = this.verifyLedger().head;
      atomicWriteJson(this.paths.state, this.state);
      return {
        schema: "aione.controlled-research-run.v1",
        run,
        graph: this.graph({ ecosystemId: request.ecosystemId }),
        proposals: this.proposals({ ecosystemId: request.ecosystemId }),
        mutationPerformed: true,
        externalMutationPerformed: false,
        publicationPerformed: false,
        installationPerformed: false,
        integrationPerformed: false
      };
    } catch (error) {
      run.completedAt = this.clock().toISOString();
      run.state = "FAILED";
      run.error = boundedText(error instanceof Error ? error.message : error, 1_000);
      this.#appendLedger("RUN_FAILED", { runId, error: run.error });
      this.state.runs.push(run);
      this.state.runs = this.state.runs.slice(-200);
      this.state.revision += 1;
      this.state.ledgerHead = this.verifyLedger().head;
      atomicWriteJson(this.paths.state, this.state);
      throw error;
    } finally {
      this.running = false;
    }
  }

  graph({ ecosystemId, query = "", depth = this.budgets.maxGraphDepth, limit = this.budgets.maxGraphNodes } = {}) {
    const items = this.state.items.filter((item) => !ecosystemId || item.ecosystemId === ecosystemId);
    const nodeMap = new Map();
    const edgeMap = new Map();
    for (const item of items) {
      const concepts = conceptTerms(item).slice(0, 25);
      for (const concept of concepts) {
        const id = `concept-${sha256(concept).slice(0, 20)}`;
        const node = nodeMap.get(id) ?? { id, label: concept, kind: "concept", weight: 0, itemIds: [], ...graphCoordinates(id) };
        node.weight += 1;
        if (node.itemIds.length < 20) node.itemIds.push(item.id);
        nodeMap.set(id, node);
      }
      for (let left = 0; left < concepts.length; left += 1) {
        for (let right = left + 1; right < Math.min(concepts.length, left + 6); right += 1) {
          const source = `concept-${sha256(concepts[left]).slice(0, 20)}`;
          const target = `concept-${sha256(concepts[right]).slice(0, 20)}`;
          const [first, second] = [source, target].sort();
          const id = `${first}|${second}`;
          const edge = edgeMap.get(id) ?? { id: `edge-${sha256(id).slice(0, 20)}`, source: first, target: second, relation: "co-occurs", weight: 0 };
          edge.weight += 1;
          edgeMap.set(id, edge);
        }
      }
    }
    const requestedLimit = boundedInteger(limit, this.budgets.maxGraphNodes, 1, this.budgets.maxGraphNodes);
    let nodes = [...nodeMap.values()].sort((a, b) => b.weight - a.weight || a.id.localeCompare(b.id)).slice(0, requestedLimit);
    let edges = [...edgeMap.values()].sort((a, b) => b.weight - a.weight || a.id.localeCompare(b.id));
    const normalizedQuery = normalizeKey(query);
    if (normalizedQuery) {
      const allowedDepth = boundedInteger(depth, this.budgets.maxGraphDepth, 0, this.budgets.maxGraphDepth);
      const selected = new Set(nodes.filter((node) => normalizeKey(node.label).includes(normalizedQuery)).map((node) => node.id));
      let frontier = new Set(selected);
      for (let level = 0; level < allowedDepth && frontier.size; level += 1) {
        const next = new Set();
        for (const edge of edges) {
          if (frontier.has(edge.source) && !selected.has(edge.target)) next.add(edge.target);
          if (frontier.has(edge.target) && !selected.has(edge.source)) next.add(edge.source);
        }
        for (const id of next) selected.add(id);
        frontier = next;
      }
      nodes = nodes.filter((node) => selected.has(node.id));
    }
    const nodeIds = new Set(nodes.map((node) => node.id));
    edges = edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)).slice(0, this.budgets.maxGraphEdges);
    return {
      schema: "aione.deterministic-concept-graph.v1",
      ecosystemId: ecosystemId || null,
      query: normalizedQuery,
      coordinateSystem: "DETERMINISTIC_HASH_RADIAL_2D",
      nodes,
      edges,
      bounds: {
        maxNodes: this.budgets.maxGraphNodes,
        maxEdges: this.budgets.maxGraphEdges,
        maxDepth: this.budgets.maxGraphDepth
      }
    };
  }

  proposals({ ecosystemId, status, limit = 100 } = {}) {
    const boundedLimit = boundedInteger(limit, 100, 1, 500);
    const items = this.state.proposals
      .filter((proposal) => !ecosystemId || proposal.ecosystemId === ecosystemId)
      .filter((proposal) => !status || proposal.status === status)
      .slice(-boundedLimit)
      .reverse();
    return {
      schema: "aione.controlled-research-proposals.v1",
      items,
      roadmaps: this.#roadmaps(items),
      executionAllowed: false,
      ownerReviewRequired: true
    };
  }

  verifyLedger() {
    if (!existsSync(this.paths.ledger)) return { ok: true, entries: 0, head: null, issues: [] };
    const lines = readFileSync(this.paths.ledger, "utf8").split(/\r?\n/u).filter(Boolean);
    const issues = [];
    let previousHash = null;
    lines.forEach((line, index) => {
      let entry;
      try {
        entry = JSON.parse(line);
      } catch {
        issues.push({ index, code: "INVALID_JSON" });
        return;
      }
      const unsigned = { ...entry };
      delete unsigned.hash;
      if (entry.sequence !== index + 1) issues.push({ index, code: "SEQUENCE_MISMATCH" });
      if (entry.previousHash !== previousHash) issues.push({ index, code: "CHAIN_MISMATCH" });
      if (sha256(stableJson(unsigned)) !== entry.hash) issues.push({ index, code: "HASH_MISMATCH" });
      previousHash = entry.hash;
    });
    return { ok: issues.length === 0, entries: lines.length, head: previousHash, issues };
  }

  #queries(request) {
    const requested = Array.isArray(request.queries) && request.queries.length
      ? request.queries
      : this.sources.filter((source) => source.enabled).map((source) => ({ sourceId: source.id, url: source.baseUrl }));
    const unique = new Set();
    const queries = [];
    for (const query of requested) {
      if (queries.length >= Math.min(this.budgets.maxSourcesPerRun, this.budgets.maxRequestsPerRun)) break;
      const source = this.sources.find((candidate) => candidate.id === query.sourceId && candidate.enabled);
      if (!source) throw new Error(`SOURCE_NOT_ENABLED:${boundedText(query.sourceId, 120)}`);
      const url = validateHttpsUrl(query.url || source.baseUrl, source.allowedHosts);
      const key = `${source.id}|${url.href}`;
      if (unique.has(key)) continue;
      unique.add(key);
      queries.push({ source, url, ecosystemId: boundedText(query.ecosystemId || request.ecosystemId || source.ecosystemId, 200) });
    }
    return queries;
  }

  async #ingestQuery(query, run, offline) {
    const cachePath = join(this.paths.cache, `${query.source.id}-${sha256(query.url.href).slice(0, 24)}.json`);
    const cached = readJson(cachePath, null);
    const cacheValid = cached?.body &&
      cached.url === query.url.href &&
      cached.provider === query.source.provider &&
      sha256(cached.body) === cached.digest;
    const cacheAgeMs = cacheValid ? Math.max(0, this.clock().getTime() - new Date(cached.fetchedAt).getTime()) : Number.POSITIVE_INFINITY;
    let body;
    let bytes = 0;
    let state = "FETCHED";
    let fetchError = null;
    if (!offline && cacheValid && cacheAgeMs <= query.source.cacheTtlMs) {
      body = cached.body;
      bytes = Number(cached.bytes || Buffer.byteLength(body, "utf8"));
      state = "CACHE_HIT_FRESH";
    } else if (!offline) {
      try {
        const response = await this.#fetchResponse(query);
        const bounded = await readBoundedBody(response, Math.min(this.budgets.maxBytesPerResponse, this.budgets.maxBytesPerRun - run.bytes));
        body = bounded.text;
        bytes = bounded.bytes;
        atomicWriteJson(cachePath, {
          schema: "aione.controlled-research-cache.v1",
          sourceId: query.source.id,
          provider: query.source.provider,
          url: query.url.href,
          fetchedAt: this.clock().toISOString(),
          bytes,
          digest: sha256(body),
          body
        });
      } catch (error) {
        fetchError = boundedText(error instanceof Error ? error.message : error, 1_000);
      }
    }
    if (body === undefined) {
      if (cacheValid) {
        body = cached.body;
        bytes = Number(cached.bytes || Buffer.byteLength(body, "utf8"));
        state = "CACHE_HIT";
      } else {
        state = "UNAVAILABLE";
        this.state.sourceHealth[query.source.id] = { state: "DEGRADED", checkedAt: this.clock().toISOString(), error: fetchError || "CACHE_MISS" };
        return { sourceId: query.source.id, state, accepted: 0, duplicates: 0, quarantined: 0, bytes: 0, error: fetchError || "CACHE_MISS" };
      }
    }
    const parsed = parseProvider(query.source.provider, body, this.budgets.maxItemsPerSource);
    const existing = new Set(this.state.items.map((item) => item.identity));
    const quarantined = new Set(this.state.quarantine.map((item) => item.identity));
    let acceptedCount = 0;
    let duplicateCount = 0;
    let quarantineCount = 0;
    const itemIds = [];
    for (const raw of parsed) {
      if (run.accepted >= this.budgets.maxItemsPerRun) break;
      const normalized = {
        ...raw,
        title: boundedText(raw.title, 500),
        summary: boundedText(raw.summary, 4_000),
        authors: uniqueStrings(raw.authors, 30),
        categories: uniqueStrings(raw.categories, 30),
        sourceId: query.source.id,
        provider: query.source.provider,
        ecosystemId: query.ecosystemId,
        observedAt: this.clock().toISOString()
      };
      if (!normalized.title || !normalized.externalId) continue;
      normalized.identity = itemIdentity(normalized);
      normalized.id = `research-item-${sha256(normalized.identity).slice(0, 24)}`;
      const signals = promptSignals(normalized);
      if (signals.length) {
        if (!quarantined.has(normalized.identity)) {
          const quarantine = {
            id: `quarantine-${sha256(normalized.identity).slice(0, 24)}`,
            identity: normalized.identity,
            sourceId: normalized.sourceId,
            provider: normalized.provider,
            titleDigest: sha256(normalized.title),
            detectedAt: this.clock().toISOString(),
            reason: "PROMPT_INSTRUCTION_DETECTED",
            signals,
            usableForPrompt: false,
            usableForGraph: false
          };
          this.state.quarantine.push(quarantine);
          quarantined.add(normalized.identity);
          this.#appendLedger("ITEM_QUARANTINED", { id: quarantine.id, identity: quarantine.identity, sourceId: quarantine.sourceId, signals });
        }
        quarantineCount += 1;
        run.quarantined += 1;
        continue;
      }
      if (existing.has(normalized.identity)) {
        duplicateCount += 1;
        run.duplicates += 1;
        continue;
      }
      normalized.provenance = {
        sourceUrl: query.url.href,
        canonicalUrl: boundedText(normalized.canonicalUrl, 2_000),
        metadataDigest: sha256(stableJson(raw)),
        fetchedFromCache: state.startsWith("CACHE_HIT")
      };
      this.state.items.push(normalized);
      existing.add(normalized.identity);
      itemIds.push(normalized.id);
      acceptedCount += 1;
      run.accepted += 1;
      this.#appendLedger("ITEM_ACCEPTED", { id: normalized.id, identity: normalized.identity, sourceId: normalized.sourceId, digest: normalized.provenance.metadataDigest });
    }
    run.bytes += bytes;
    this.state.sourceHealth[query.source.id] = {
      state: state === "FETCHED" ? "HEALTHY" : state === "CACHE_HIT_FRESH" ? "HEALTHY_CACHE_FRESH" : "DEGRADED_CACHE_ONLY",
      checkedAt: this.clock().toISOString(),
      bytes,
      accepted: acceptedCount,
      error: fetchError
    };
    return { sourceId: query.source.id, state, accepted: acceptedCount, duplicates: duplicateCount, quarantined: quarantineCount, itemIds, bytes, error: fetchError };
  }

  async #fetchResponse(query) {
    await this.#respectHostDelay(query);
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        reject(new Error("SOURCE_TIMEOUT"));
      }, this.budgets.timeoutMs);
    });
    try {
      const response = await Promise.race([
        this.fetch(query.url.href, {
          method: "GET",
          redirect: "manual",
          signal: controller.signal,
          headers: {
            accept: query.source.provider === "ARXIV_ATOM" ? "application/atom+xml, application/xml;q=0.9" : "application/json",
            "user-agent": this.userAgent,
            "api-user-agent": this.userAgent
          }
        }),
        timeout
      ]);
      if (!response || typeof response.status !== "number") throw new Error("SOURCE_INVALID_RESPONSE");
      if (response.status >= 300 && response.status < 400) throw new Error("SOURCE_REDIRECT_FORBIDDEN");
      if (!response.ok) throw new Error(`SOURCE_HTTP_${response.status}`);
      if (response.redirected) throw new Error("SOURCE_REDIRECT_FORBIDDEN");
      if (response.url) {
        const finalUrl = validateHttpsUrl(response.url, query.source.allowedHosts);
        if (finalUrl.href !== query.url.href) throw new Error("SOURCE_URL_CHANGED");
      }
      const contentType = String(response.headers?.get?.("content-type") || "").toLowerCase();
      if (query.source.provider === "ARXIV_ATOM") {
        if (!/(?:atom|xml)/u.test(contentType)) throw new Error("SOURCE_CONTENT_TYPE_INVALID");
      } else if (!contentType.includes("json")) {
        throw new Error("SOURCE_CONTENT_TYPE_INVALID");
      }
      return response;
    } finally {
      clearTimeout(timer);
    }
  }

  async #respectHostDelay(query) {
    const host = query.url.hostname.toLowerCase();
    const previous = this.hostLastRequestAt.get(host);
    if (previous) {
      const minimumDelayMs = Math.max(previous.minimumDelayMs, query.source.minimumDelayMs);
      const remaining = minimumDelayMs - (this.nowMs() - previous.at);
      if (remaining > 0) await this.sleep(remaining);
    }
    this.hostLastRequestAt.set(host, { at: this.nowMs(), minimumDelayMs: query.source.minimumDelayMs });
  }

  #createRunArtifacts(run) {
    const acceptedIds = new Set(run.sourceResults.flatMap((result) => result.itemIds ?? []));
    const accepted = this.state.items.filter((item) => acceptedIds.has(item.id));
    const tileIds = [];
    for (const item of accepted) {
      const tile = {
        id: `unitile-${sha256(item.id).slice(0, 24)}`,
        level: "unitile",
        ecosystemId: item.ecosystemId,
        sourceIds: [item.id],
        perspectives: {
          "machine-subjective": `Métadonnée observée par la machine via ${item.provider}; confiance limitée à la provenance et au schéma.`,
          "user-objective": `L’utilisateur peut examiner « ${item.title} » comme piste documentée, sans exécution ni intégration automatique.`
        },
        reconstruction: { type: "metadata-reference", reversible: true, sourceDigests: [item.provenance.metadataDigest] }
      };
      if (!this.state.tiles.some((candidate) => candidate.id === tile.id)) this.state.tiles.push(tile);
      tileIds.push(tile.id);
    }
    const conceptsByEcosystem = new Map();
    for (const item of accepted) {
      const concepts = conceptsByEcosystem.get(item.ecosystemId) ?? [];
      concepts.push(...conceptTerms(item));
      conceptsByEcosystem.set(item.ecosystemId, concepts);
    }
    for (const [ecosystemId, concepts] of conceptsByEcosystem) {
      const terms = uniqueStrings(concepts, 80);
      const tile = {
        id: `tile-${sha256(`${run.id}|${ecosystemId}|${terms.join("|")}`).slice(0, 24)}`,
        level: "tile",
        ecosystemId,
        sourceIds: accepted.filter((item) => item.ecosystemId === ecosystemId).map((item) => item.id),
        concepts: terms,
        perspectives: {
          "machine-subjective": `Regroupement déterministe de ${terms.length} concepts co-présents dans les métadonnées du cycle.`,
          "user-objective": "Carte de pistes à comparer; elle ne constitue ni une vérité, ni une permission, ni une décision de projet."
        },
        reconstruction: { type: "deterministic-concept-cluster", reversible: true }
      };
      this.state.tiles.push(tile);
      tileIds.push(tile.id);
    }
    const kilotile = {
      id: `kilotile-${sha256(run.id).slice(0, 24)}`,
      level: "kilotile",
      ecosystemId: "federation",
      sourceIds: accepted.map((item) => item.id),
      perspectives: {
        "machine-subjective": `Cycle ${run.id}: ${run.accepted} acceptée(s), ${run.duplicates} doublon(s), ${run.quarantined} quarantaine(s).`,
        "user-objective": "Vue consolidée du cycle contrôlé; toute proposition reste à relire et à valider avant planification."
      },
      reconstruction: { type: "run-ledger-summary", reversible: true, ledgerHead: this.verifyLedger().head }
    };
    this.state.tiles.push(kilotile);
    tileIds.push(kilotile.id);
    const proposalIds = [];
    for (const item of accepted.slice(0, this.budgets.maxProposalsPerRun)) {
      const id = `research-proposal-${sha256(item.identity).slice(0, 24)}`;
      if (this.state.proposals.some((proposal) => proposal.id === id)) continue;
      const proposal = {
        id,
        status: "PROPOSED",
        executable: false,
        ownerReviewRequired: true,
        ecosystemId: item.ecosystemId,
        title: `Évaluer localement : ${item.title}`,
        objective: "Comparer cette piste aux besoins et preuves de l’écosystème dans une simulation locale, sans télécharger de code ni modifier un projet principal.",
        sourceItemIds: [item.id],
        concepts: conceptTerms(item).slice(0, 12),
        benefits: ["Nouvelle piste documentée", "Comparaison reproductible dans le jumeau local"],
        costs: ["Temps de lecture et de simulation", "Validation humaine avant toute planification"],
        risks: ["Métadonnées incomplètes", "Résultat externe non reproduit localement"],
        permissions: [],
        forbiddenActions: ["publish", "install", "integrate", "execute-external-code"],
        createdAt: this.clock().toISOString()
      };
      this.state.proposals.push(proposal);
      proposalIds.push(id);
      this.#appendLedger("PROPOSAL_CREATED", { id, ecosystemId: proposal.ecosystemId, sourceItemIds: proposal.sourceItemIds });
    }
    this.state.tiles = this.state.tiles.slice(-5_000);
    this.state.proposals = this.state.proposals.slice(-2_000);
    return { proposalIds, tileIds };
  }

  #roadmaps(proposals) {
    const sorted = [...proposals].sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id));
    const phase = (horizon, label, offset, maximum, intent) => ({
      horizon,
      label,
      status: "PROPOSED_NON_EXECUTABLE",
      intent,
      proposalIds: sorted.slice(offset, offset + maximum).map((proposal) => proposal.id),
      ownerReviewRequired: true
    });
    return [
      phase("6m", "6 mois", 0, 8, "Stabiliser l’ingestion contrôlée, la provenance, les comparaisons et les prototypes isolés."),
      phase("1y", "1 an", 8, 16, "Relier les concepts éprouvés aux portefeuilles multi-écosystèmes et mesurer leurs effets."),
      phase("5y", "5 ans", 24, 32, "Étudier les architectures durables, interopérables et réversibles sans présumer des technologies futures.")
    ];
  }

  #appendLedger(type, payload) {
    const integrity = this.verifyLedger();
    if (!integrity.ok) throw new Error("LEDGER_INTEGRITY_ERROR");
    const entry = {
      schema: "aione.controlled-research-ledger-entry.v1",
      sequence: integrity.entries + 1,
      at: this.clock().toISOString(),
      type,
      payload,
      previousHash: integrity.head
    };
    entry.hash = sha256(stableJson(entry));
    appendFileSync(this.paths.ledger, `${JSON.stringify(entry)}\n`, "utf8");
    return entry;
  }

  #persistenceIntegrity() {
    const ledger = this.verifyLedger();
    const issues = [...ledger.issues];
    if (ledger.ok && this.state.ledgerHead !== ledger.head) {
      issues.push({ code: "STATE_LEDGER_HEAD_MISMATCH", stateHead: this.state.ledgerHead, ledgerHead: ledger.head });
    }
    return { ...ledger, ok: issues.length === 0, issues };
  }
}

export function createControlledResearchLab(options) {
  return new ControlledResearchLab(options);
}
