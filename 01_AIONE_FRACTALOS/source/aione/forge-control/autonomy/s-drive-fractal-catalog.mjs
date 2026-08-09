import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  existsSync,
  fsyncSync,
  fstatSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readSync,
  readdirSync,
  realpathSync,
  renameSync,
  writeFileSync
} from "node:fs";
import { basename, dirname, extname, isAbsolute, join, relative, resolve } from "node:path";

const MAP_SCHEMA = "aione.s-drive-fractal-map.v1";
const SIMULATION_SCHEMA = "aione.s-drive-fractal-simulation.v1";
const STATE_SCHEMA = "aione.s-drive-fractal-state.v1";
const MAX_POLICY_ENTRIES = 10_000;

export const DEFAULT_CATALOG_POLICY = Object.freeze({
  maxDepth: 4,
  maxEntries: 20_000,
  maxEntriesPerDirectory: 2_000,
  maxContentFiles: 128,
  maxContentBytesPerFile: 64 * 1024,
  maxTotalContentBytes: 2 * 1024 * 1024,
  contentAllowlist: [],
  includeTopLevel: [],
  excludePatterns: [],
  excludedDirectoryNames: [
    ".git",
    ".svn",
    "node_modules",
    "__pycache__"
  ],
  protectedDirectoryNames: [
    "$RECYCLE.BIN",
    "System Volume Information",
    "Recovery",
    "Config.Msi",
    "EFI",
    "Boot"
  ],
  protectedFilePatterns: [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.pfx",
    "*.p12",
    "*credential*",
    "*password*",
    "*secret*",
    "*token*",
    "id_rsa*",
    "known_hosts"
  ]
});

export class FractalCatalogError extends Error {
  constructor(code, message, details = undefined) {
    super(message);
    this.name = "FractalCatalogError";
    this.code = code;
    this.details = details;
  }
}

function fail(code, message, details) {
  throw new FractalCatalogError(code, message, details);
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
}

function stableJson(value) {
  return JSON.stringify(canonicalize(value));
}

function hash(value) {
  return createHash("sha256").update(String(value)).digest("hex");
}

function clone(value) {
  return structuredClone(value);
}

function isoNow(clock) {
  const date = clock();
  const normalized = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(normalized.getTime())) fail("INVALID_CLOCK", "L'horloge du catalogue est invalide.");
  return normalized.toISOString();
}

function boundedInteger(value, field, minimum, maximum) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < minimum || number > maximum) {
    fail("INVALID_POLICY_LIMIT", `${field} doit etre un entier entre ${minimum} et ${maximum}.`);
  }
  return number;
}

function normalizeStringList(value, field, maximum = 1_000) {
  if (!Array.isArray(value)) fail("INVALID_POLICY_LIST", `${field} doit etre un tableau.`);
  if (value.length > maximum) fail("POLICY_LIST_TOO_LARGE", `${field} depasse ${maximum} entrees.`);
  return [...new Set(value.map((entry) => String(entry ?? "").trim()).filter(Boolean))].sort();
}

function normalizedPathKey(value) {
  return String(value).replaceAll("\\", "/").replace(/^\.\/+/, "").replace(/\/+/g, "/").toLocaleLowerCase("en-US");
}

function pathInside(parentPath, candidatePath, allowSame = true) {
  const delta = relative(resolve(parentPath), resolve(candidatePath));
  if (delta === "") return allowSame;
  return delta !== ".." && !delta.startsWith(`..\\`) && !delta.startsWith("../") && !isAbsolute(delta);
}

function wildcardRegex(pattern) {
  const escaped = String(pattern)
    .replaceAll("\\", "/")
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*\*/g, "\u0000")
    .replace(/\*/g, "[^/]*")
    .replace(/\?/g, "[^/]")
    .replace(/\u0000/g, ".*");
  return new RegExp(`^${escaped}$`, "i");
}

function matchesPattern(relativePath, patterns) {
  const candidate = String(relativePath).replaceAll("\\", "/");
  const fileName = basename(candidate);
  return patterns.some((pattern) => {
    const expression = wildcardRegex(pattern);
    return expression.test(candidate) || (!String(pattern).includes("/") && expression.test(fileName));
  });
}

function deterministicId(kind, rootIdentity, relativePath) {
  return `${kind}_${hash(`${rootIdentity}\u001f${normalizedPathKey(relativePath)}`).slice(0, 24)}`;
}

function anchorId(type, from, to) {
  return `anchor_${hash(`${type}\u001f${from}\u001f${to}`).slice(0, 24)}`;
}

function normalizePolicy(overrides = {}) {
  const merged = { ...DEFAULT_CATALOG_POLICY, ...clone(overrides) };
  const policy = {
    maxDepth: boundedInteger(merged.maxDepth, "maxDepth", 1, 32),
    maxEntries: boundedInteger(merged.maxEntries, "maxEntries", 1, 1_000_000),
    maxEntriesPerDirectory: boundedInteger(
      merged.maxEntriesPerDirectory,
      "maxEntriesPerDirectory",
      1,
      100_000
    ),
    maxContentFiles: boundedInteger(merged.maxContentFiles, "maxContentFiles", 0, 10_000),
    maxContentBytesPerFile: boundedInteger(
      merged.maxContentBytesPerFile,
      "maxContentBytesPerFile",
      0,
      4 * 1024 * 1024
    ),
    maxTotalContentBytes: boundedInteger(
      merged.maxTotalContentBytes,
      "maxTotalContentBytes",
      0,
      64 * 1024 * 1024
    ),
    contentAllowlist: normalizeStringList(merged.contentAllowlist, "contentAllowlist", MAX_POLICY_ENTRIES),
    includeTopLevel: normalizeStringList(merged.includeTopLevel, "includeTopLevel", MAX_POLICY_ENTRIES),
    excludePatterns: normalizeStringList(merged.excludePatterns, "excludePatterns", MAX_POLICY_ENTRIES),
    excludedDirectoryNames: normalizeStringList(
      merged.excludedDirectoryNames,
      "excludedDirectoryNames",
      MAX_POLICY_ENTRIES
    ),
    protectedDirectoryNames: normalizeStringList(
      merged.protectedDirectoryNames,
      "protectedDirectoryNames",
      MAX_POLICY_ENTRIES
    ),
    protectedFilePatterns: normalizeStringList(
      merged.protectedFilePatterns,
      "protectedFilePatterns",
      MAX_POLICY_ENTRIES
    )
  };
  return Object.freeze(policy);
}

function classifyPath(relativePath, directory, depth, policy, runtimePath, absolutePath) {
  const name = basename(relativePath);
  if (pathInside(runtimePath, absolutePath) || pathInside(absolutePath, runtimePath)) {
    if (pathInside(runtimePath, absolutePath)) {
      return { action: "EXCLUDE", reason: "RUNTIME_SELF_EXCLUSION" };
    }
  }
  if (matchesPattern(relativePath, policy.excludePatterns)) {
    return { action: "EXCLUDE", reason: "POLICY_PATTERN_EXCLUSION" };
  }
  if (directory && policy.protectedDirectoryNames.some((entry) => entry.toLowerCase() === name.toLowerCase())) {
    return { action: "METADATA_ONLY", reason: "PROTECTED_SYSTEM_DIRECTORY" };
  }
  if (directory && depth > 1 &&
      policy.excludedDirectoryNames.some((entry) => entry.toLowerCase() === name.toLowerCase())) {
    return { action: "METADATA_ONLY", reason: "POLICY_DIRECTORY_EXCLUSION" };
  }
  if (!directory && matchesPattern(relativePath, policy.protectedFilePatterns)) {
    return { action: "METADATA_ONLY", reason: "PROTECTED_SECRET_NAME" };
  }
  if (depth === 1 && policy.includeTopLevel.length > 0 &&
      !policy.includeTopLevel.some((entry) => entry.toLowerCase() === name.toLowerCase())) {
    return { action: "METADATA_ONLY", reason: "TOP_LEVEL_NOT_ALLOWLISTED" };
  }
  return { action: "INCLUDE", reason: null };
}

function checksumDocument(document) {
  const { documentChecksum: _checksum, ...body } = document;
  return hash(stableJson(body));
}

function atomicJson(path, value, { exclusive = false } = {}) {
  mkdirSync(dirname(path), { recursive: true });
  if (exclusive && existsSync(path)) return false;
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  const descriptor = openSync(temporary, "wx");
  try {
    const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8");
    writeFileSync(descriptor, bytes);
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
  renameSync(temporary, path);
  return true;
}

function readValidState(path) {
  try {
    const document = JSON.parse(readFileSync(path, "utf8"));
    if (document.schema !== STATE_SCHEMA || document.documentChecksum !== checksumDocument(document)) return null;
    return document;
  } catch {
    return null;
  }
}

function diffMaps(previousMap, nextMap) {
  const previous = new Map();
  const next = new Map();
  for (const item of [
    ...(previousMap?.categories ?? []),
    ...(previousMap?.nodes ?? [])
  ]) previous.set(item.id, item.fingerprint);
  for (const item of [...nextMap.categories, ...nextMap.nodes]) next.set(item.id, item.fingerprint);
  const added = [];
  const modified = [];
  const removed = [];
  let unchanged = 0;
  for (const [id, fingerprint] of next) {
    if (!previous.has(id)) added.push(id);
    else if (previous.get(id) !== fingerprint) modified.push(id);
    else unchanged += 1;
  }
  for (const id of previous.keys()) {
    if (!next.has(id)) removed.push(id);
  }
  return {
    added: added.sort(),
    modified: modified.sort(),
    removed: removed.sort(),
    unchanged,
    changed: added.length + modified.length + removed.length
  };
}

function detectCycles(nodeIds, anchors) {
  const graph = new Map([...nodeIds].map((id) => [id, []]));
  for (const anchor of anchors) {
    if (graph.has(anchor.from) && graph.has(anchor.to)) graph.get(anchor.from).push(anchor.to);
  }
  const color = new Map();
  const stack = [];
  const cycles = [];
  const seenCycles = new Set();
  function visit(node) {
    color.set(node, 1);
    stack.push(node);
    for (const next of graph.get(node) ?? []) {
      if (!color.has(next)) visit(next);
      else if (color.get(next) === 1) {
        const start = stack.lastIndexOf(next);
        const cycle = [...stack.slice(start), next];
        const signature = [...new Set(cycle)].sort().join("|");
        if (!seenCycles.has(signature)) {
          seenCycles.add(signature);
          cycles.push(cycle);
        }
      }
    }
    stack.pop();
    color.set(node, 2);
  }
  for (const node of [...nodeIds].sort()) {
    if (!color.has(node)) visit(node);
  }
  return cycles;
}

export class SDriveFractalCatalog {
  constructor({
    rootPath = "S:\\",
    runtimePath = "S:\\AI_LAB\\Runtime\\FractalCatalog",
    policy = {},
    clock = () => new Date(),
    faultInjector = null
  } = {}) {
    const requestedRoot = resolve(rootPath);
    if (!existsSync(requestedRoot)) fail("ROOT_NOT_FOUND", `Racine absente: ${requestedRoot}`);
    let rootStat;
    try {
      rootStat = lstatSync(requestedRoot);
    } catch (error) {
      fail("ROOT_UNREADABLE", `Racine illisible: ${error.message}`);
    }
    if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) {
      fail("INVALID_ROOT", "La racine doit etre un repertoire reel, jamais un lien.");
    }
    this.rootPath = realpathSync(requestedRoot);
    this.runtimePath = resolve(runtimePath);
    if (resolve(this.runtimePath) === resolve(this.rootPath)) {
      fail("RUNTIME_EQUALS_ROOT", "Le runtime ne peut pas etre la racine cataloguee.");
    }
    if (pathInside(this.rootPath, this.runtimePath) && !existsSync(dirname(this.runtimePath))) {
      fail(
        "RUNTIME_PARENT_NOT_FOUND",
        "Le parent du runtime doit deja exister afin de ne creer aucun dossier source implicite."
      );
    }
    this.policy = normalizePolicy(policy);
    this.clock = clock;
    this.faultInjector = typeof faultInjector === "function" ? faultInjector : null;
    this.rootIdentity = `root_${hash(normalizedPathKey(this.rootPath)).slice(0, 24)}`;
    if (existsSync(this.runtimePath) && lstatSync(this.runtimePath).isSymbolicLink()) {
      fail("SYMLINK_RUNTIME_DENIED", "Le runtime du catalogue ne peut pas etre un lien.");
    }
    this.paths = {
      history: join(this.runtimePath, "history"),
      exports: join(this.runtimePath, "exports"),
      staging: join(this.runtimePath, ".staging"),
      current: join(this.runtimePath, "current.json")
    };
    mkdirSync(this.paths.history, { recursive: true });
    mkdirSync(this.paths.exports, { recursive: true });
    mkdirSync(this.paths.staging, { recursive: true });
    this.runtimeRealPath = realpathSync(this.runtimePath);
    this.current = this.#loadLatestState();
  }

  #assertSourcePath(candidatePath) {
    const absolute = isAbsolute(candidatePath)
      ? resolve(candidatePath)
      : resolve(this.rootPath, candidatePath);
    if (!pathInside(this.rootPath, absolute)) {
      fail("PATH_OUTSIDE_ROOT", `Chemin hors racine refuse: ${absolute}`);
    }
    if (existsSync(absolute)) {
      const actual = realpathSync(absolute);
      if (!pathInside(this.rootPath, actual)) {
        fail("PATH_ESCAPES_ROOT", `Lien ou jonction sortant de la racine refuse: ${absolute}`);
      }
    }
    return absolute;
  }

  #assertRuntimePath(candidatePath) {
    const absolute = resolve(candidatePath);
    if (!pathInside(this.runtimePath, absolute)) {
      fail("OUTPUT_OUTSIDE_RUNTIME", `Ecriture hors runtime refusee: ${absolute}`);
    }
    if (existsSync(absolute) && lstatSync(absolute).isSymbolicLink()) {
      fail("SYMLINK_OUTPUT_DENIED", `Sortie symbolique refusee: ${absolute}`);
    }
    let existingAncestor = dirname(absolute);
    while (!existsSync(existingAncestor)) {
      const parent = dirname(existingAncestor);
      if (parent === existingAncestor) fail("OUTPUT_PARENT_UNRESOLVED", "Parent de sortie introuvable.");
      existingAncestor = parent;
    }
    if (!pathInside(this.runtimeRealPath, realpathSync(existingAncestor))) {
      fail("OUTPUT_ESCAPES_RUNTIME", `Le parent reel de la sortie quitte le runtime: ${absolute}`);
    }
    return absolute;
  }

  #loadLatestState() {
    const candidates = [];
    if (existsSync(this.paths.current)) {
      const current = readValidState(this.paths.current);
      if (current) candidates.push({ ...current, recoveredFrom: "current" });
    }
    if (existsSync(this.paths.history)) {
      for (const name of readdirSync(this.paths.history).filter((entry) => entry.endsWith(".json")).sort()) {
        const state = readValidState(join(this.paths.history, name));
        if (state) candidates.push({ ...state, recoveredFrom: `history/${name}` });
      }
    }
    candidates.sort((left, right) =>
      Number(right.revision) - Number(left.revision) ||
      String(right.committedAt).localeCompare(String(left.committedAt)));
    return candidates[0] ?? null;
  }

  inspectPath(candidatePath) {
    const absolute = this.#assertSourcePath(candidatePath);
    let info;
    try {
      info = lstatSync(absolute);
    } catch (error) {
      fail("PATH_UNREADABLE", `Chemin illisible: ${error.message}`);
    }
    const relativePath = relative(this.rootPath, absolute) || ".";
    return {
      relativePath,
      kind: info.isSymbolicLink() ? "link" : info.isDirectory() ? "directory" : info.isFile() ? "file" : "other",
      size: info.isFile() ? info.size : null,
      modifiedAt: new Date(info.mtimeMs).toISOString()
    };
  }

  #readAllowedContent(absolutePath, relativePath, expectedInfo, contentBudget) {
    if (!matchesPattern(relativePath, this.policy.contentAllowlist)) return null;
    if (matchesPattern(relativePath, this.policy.protectedFilePatterns)) return null;
    if (contentBudget.files >= this.policy.maxContentFiles) return { denied: "CONTENT_FILE_LIMIT" };
    const remaining = this.policy.maxTotalContentBytes - contentBudget.bytes;
    if (remaining <= 0) return { denied: "CONTENT_TOTAL_BYTE_LIMIT" };
    const fileSize = expectedInfo.size;
    const byteLimit = Math.min(fileSize, this.policy.maxContentBytesPerFile, remaining);
    if (byteLimit <= 0) return { denied: "CONTENT_BYTE_LIMIT" };
    const descriptor = openSync(absolutePath, "r");
    const buffer = Buffer.alloc(byteLimit);
    let bytesRead;
    try {
      const openedInfo = fstatSync(descriptor);
      if (!openedInfo.isFile() ||
          (expectedInfo.ino && openedInfo.ino && expectedInfo.ino !== openedInfo.ino) ||
          (expectedInfo.dev && openedInfo.dev && expectedInfo.dev !== openedInfo.dev)) {
        fail("CONTENT_PATH_CHANGED", `Le fichier ${relativePath} a change entre inventaire et lecture.`);
      }
      bytesRead = readSync(descriptor, buffer, 0, byteLimit, 0);
    } finally {
      closeSync(descriptor);
    }
    contentBudget.files += 1;
    contentBudget.bytes += bytesRead;
    return {
      bytesRead,
      truncated: bytesRead < fileSize,
      digest: hash(buffer.subarray(0, bytesRead))
    };
  }

  #scanSource() {
    const issues = [];
    const categories = [];
    const nodes = [];
    const anchors = [];
    const identityPaths = new Map();
    const contentBudget = { files: 0, bytes: 0 };
    let entryCount = 0;
    let limitReached = false;
    const rootNode = {
      id: this.rootIdentity,
      kind: "root",
      structuralRole: "CURRENT_ROOT_BRANCH",
      name: basename(this.rootPath) || this.rootPath,
      relativePath: ".",
      parentId: null,
      categoryId: null,
      policyStatus: "ROOT",
      fingerprint: hash(`root\u001f${normalizedPathKey(this.rootPath)}`)
    };

    const registerIdentity = (item) => {
      const existing = identityPaths.get(item.id);
      if (existing && existing !== item.relativePath) {
        issues.push({
          severity: "ERROR",
          code: "DETERMINISTIC_ID_COLLISION",
          id: item.id,
          paths: [existing, item.relativePath].sort()
        });
        return false;
      }
      identityPaths.set(item.id, item.relativePath);
      return true;
    };
    registerIdentity(rootNode);

    const sortedEntries = (directoryPath, relativeDirectory) => {
      try {
        const entries = readdirSync(directoryPath, { withFileTypes: true })
          .sort((left, right) =>
            left.name.localeCompare(right.name, "en", { sensitivity: "base" }) ||
            left.name.localeCompare(right.name, "en", { sensitivity: "variant" }));
        if (entries.length > this.policy.maxEntriesPerDirectory) {
          issues.push({
            severity: "WARNING",
            code: "DIRECTORY_ENTRY_LIMIT",
            path: relativeDirectory,
            observed: entries.length,
            inspected: this.policy.maxEntriesPerDirectory
          });
        }
        return entries.slice(0, this.policy.maxEntriesPerDirectory);
      } catch (error) {
        issues.push({
          severity: "WARNING",
          code: "DIRECTORY_UNREADABLE",
          path: relativeDirectory,
          message: String(error.code ?? error.message)
        });
        return [];
      }
    };

    const scanEntry = ({ absolutePath, relativePath, depth, parentId, categoryId, topLevel = false }) => {
      if (entryCount >= this.policy.maxEntries) {
        if (!limitReached) {
          limitReached = true;
          issues.push({
            severity: "WARNING",
            code: "GLOBAL_ENTRY_LIMIT",
            observed: entryCount,
            maximum: this.policy.maxEntries
          });
        }
        return null;
      }
      entryCount += 1;
      let info;
      try {
        info = lstatSync(absolutePath);
      } catch (error) {
        issues.push({
          severity: "WARNING",
          code: "ENTRY_UNREADABLE",
          path: relativePath,
          message: String(error.code ?? error.message)
        });
        return null;
      }
      const symbolic = info.isSymbolicLink();
      const directory = info.isDirectory();
      let classification = symbolic
        ? { action: "METADATA_ONLY", reason: "SYMBOLIC_LINK_BLOCKED" }
        : classifyPath(relativePath, directory, depth, this.policy, this.runtimePath, absolutePath);
      if (topLevel && directory && classification.action === "EXCLUDE" &&
          classification.reason !== "RUNTIME_SELF_EXCLUSION") {
        classification = { action: "METADATA_ONLY", reason: classification.reason };
      }
      if (classification.action === "EXCLUDE") return null;

      const kind = topLevel && directory ? "category" : symbolic ? "link" : directory ? "directory" : info.isFile() ? "file" : "other";
      const id = deterministicId(kind === "category" ? "category" : "node", this.rootIdentity, relativePath);
      const effectiveCategoryId = kind === "category" ? id : categoryId;
      const item = {
        id,
        kind,
        structuralRole: kind === "category" ? "CATEGORY_DEFINITION" : "CATEGORY_MEMBER",
        name: basename(relativePath),
        relativePath: relativePath.replaceAll("\\", "/"),
        parentId,
        categoryId: effectiveCategoryId,
        depth,
        policyStatus: classification.action,
        policyReason: classification.reason,
        size: info.isFile() ? info.size : null,
        extension: info.isFile() ? extname(relativePath).toLowerCase() : null,
        modifiedAt: info.isFile() ? new Date(info.mtimeMs).toISOString() : null,
        contentEvidence: null,
        fingerprint: ""
      };
      if (!registerIdentity(item)) return item;

      if (info.isFile() && classification.action === "INCLUDE") {
        try {
          item.contentEvidence = this.#readAllowedContent(absolutePath, relativePath, info, contentBudget);
        } catch (error) {
          issues.push({
            severity: "WARNING",
            code: "ALLOWLISTED_CONTENT_UNREADABLE",
            path: relativePath,
            message: String(error.code ?? error.message)
          });
        }
      }
      item.fingerprint = hash(stableJson({
        kind: item.kind,
        path: normalizedPathKey(item.relativePath),
        policyStatus: item.policyStatus,
        policyReason: item.policyReason,
        size: item.size,
        modifiedAt: item.modifiedAt,
        contentEvidence: item.contentEvidence
      }));
      if (kind === "category") categories.push(item);
      else nodes.push(item);
      anchors.push({
        id: anchorId("PARENT_OF", parentId, id),
        type: "PARENT_OF",
        from: parentId,
        to: id,
        source: "structural"
      });

      if (directory && !symbolic && classification.action === "INCLUDE" && depth < this.policy.maxDepth) {
        for (const entry of sortedEntries(absolutePath, relativePath)) {
          const childRelative = join(relativePath, entry.name);
          scanEntry({
            absolutePath: join(absolutePath, entry.name),
            relativePath: childRelative,
            depth: depth + 1,
            parentId: id,
            categoryId: effectiveCategoryId,
            topLevel: false
          });
          if (limitReached) break;
        }
      }
      return item;
    };

    for (const entry of sortedEntries(this.rootPath, ".")) {
      const relativePath = entry.name;
      const absolutePath = join(this.rootPath, entry.name);
      if (entry.isDirectory() || entry.isSymbolicLink()) {
        scanEntry({
          absolutePath,
          relativePath,
          depth: 1,
          parentId: rootNode.id,
          categoryId: null,
          topLevel: true
        });
      } else {
        scanEntry({
          absolutePath,
          relativePath,
          depth: 1,
          parentId: rootNode.id,
          categoryId: null,
          topLevel: false
        });
      }
      if (limitReached) break;
    }

    return { rootNode, categories, nodes, anchors, issues, contentBudget };
  }

  #addCrossAnchors(scan, crossAnchors) {
    if (!Array.isArray(crossAnchors)) fail("INVALID_CROSS_ANCHORS", "crossAnchors doit etre un tableau.");
    if (crossAnchors.length > 10_000) fail("TOO_MANY_CROSS_ANCHORS", "Trop d'ancres croisees.");
    const allItems = [scan.rootNode, ...scan.categories, ...scan.nodes];
    const byId = new Map(allItems.map((item) => [item.id, item]));
    const byPath = new Map(allItems.map((item) => [normalizedPathKey(item.relativePath), item]));
    const byAnchorId = new Map(scan.anchors.map((anchor) => [anchor.id, anchor]));
    const resolveEndpoint = (candidate, side, index) => {
      const explicitId = candidate[side];
      const explicitPath = candidate[`${side}Path`];
      const item = explicitId ? byId.get(String(explicitId)) : byPath.get(normalizedPathKey(explicitPath));
      if (!item) {
        scan.issues.push({
          severity: "ERROR",
          code: "CROSS_ANCHOR_ENDPOINT_MISSING",
          anchorIndex: index,
          side,
          value: explicitId ?? explicitPath ?? null
        });
      }
      return item;
    };
    crossAnchors.forEach((candidate, index) => {
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
        scan.issues.push({ severity: "ERROR", code: "INVALID_CROSS_ANCHOR", anchorIndex: index });
        return;
      }
      const from = resolveEndpoint(candidate, "from", index);
      const to = resolveEndpoint(candidate, "to", index);
      if (!from || !to) return;
      const type = String(candidate.type ?? "RELATES_TO").trim().toUpperCase();
      if (!/^[A-Z][A-Z0-9_]{0,79}$/.test(type)) {
        scan.issues.push({ severity: "ERROR", code: "INVALID_CROSS_ANCHOR_TYPE", anchorIndex: index });
        return;
      }
      const id = candidate.id ? String(candidate.id) : anchorId(type, from.id, to.id);
      const anchor = { id, type, from: from.id, to: to.id, source: "declared" };
      const existing = byAnchorId.get(id);
      if (existing && stableJson(existing) !== stableJson(anchor)) {
        scan.issues.push({
          severity: "ERROR",
          code: "ANCHOR_ID_COLLISION",
          id,
          existing,
          candidate: anchor
        });
        return;
      }
      if (!existing) {
        byAnchorId.set(id, anchor);
        scan.anchors.push(anchor);
      }
    });
  }

  #auditCoherence(scan) {
    const allItems = [scan.rootNode, ...scan.categories, ...scan.nodes];
    const byId = new Map();
    for (const item of allItems) {
      if (byId.has(item.id) && byId.get(item.id).relativePath !== item.relativePath) {
        scan.issues.push({ severity: "ERROR", code: "DUPLICATE_NODE_ID", id: item.id });
      }
      byId.set(item.id, item);
    }
    for (const category of scan.categories) {
      if (category.parentId !== scan.rootNode.id || category.depth !== 1 || category.categoryId !== category.id) {
        scan.issues.push({
          severity: "ERROR",
          code: "INCOHERENT_CATEGORY_DEFINITION",
          id: category.id
        });
      }
    }
    for (const node of scan.nodes) {
      if (!node.parentId || !byId.has(node.parentId)) {
        scan.issues.push({ severity: "ERROR", code: "ORPHAN_NODE", id: node.id });
      }
      if (node.categoryId && !byId.has(node.categoryId)) {
        scan.issues.push({ severity: "ERROR", code: "UNKNOWN_NODE_CATEGORY", id: node.id });
      }
    }
    const anchorIds = new Set();
    for (const anchor of scan.anchors) {
      if (anchorIds.has(anchor.id)) scan.issues.push({ severity: "ERROR", code: "DUPLICATE_ANCHOR_ID", id: anchor.id });
      anchorIds.add(anchor.id);
      if (!byId.has(anchor.from) || !byId.has(anchor.to)) {
        scan.issues.push({ severity: "ERROR", code: "ORPHAN_ANCHOR", id: anchor.id });
      }
      if (anchor.from === anchor.to) {
        scan.issues.push({ severity: "ERROR", code: "SELF_REFERENTIAL_ANCHOR", id: anchor.id });
      }
    }
    const cycles = detectCycles(new Set(byId.keys()), scan.anchors);
    for (const cycle of cycles) {
      scan.issues.push({ severity: "ERROR", code: "LOGICAL_CYCLE", cycle });
    }
  }

  simulateScan({ crossAnchors = [] } = {}) {
    const scan = this.#scanSource();
    this.#addCrossAnchors(scan, crossAnchors);
    this.#auditCoherence(scan);
    for (const category of scan.categories) {
      const members = scan.nodes
        .filter((node) => node.categoryId === category.id)
        .map(({ id, parentId, fingerprint }) => ({ id, parentId, fingerprint }))
        .sort((left, right) => left.id.localeCompare(right.id));
      const memberIds = new Set([category.id, ...members.map((member) => member.id)]);
      const internalAnchors = scan.anchors
        .filter((anchor) => memberIds.has(anchor.from) && memberIds.has(anchor.to))
        .map(({ id, type, from, to }) => ({ id, type, from, to }))
        .sort((left, right) => left.id.localeCompare(right.id));
      const relatedIssues = scan.issues.filter((issue) => stableJson(issue).includes(category.id));
      category.memberCount = members.length;
      category.localCoherenceFingerprint = hash(stableJson({ members, internalAnchors }));
      category.coherenceStatus = relatedIssues.some((issue) => issue.severity === "ERROR")
        ? "BLOCKED"
        : "COHERENT";
      category.fingerprint = hash(stableJson({
        ownFingerprint: category.fingerprint,
        localCoherenceFingerprint: category.localCoherenceFingerprint,
        coherenceStatus: category.coherenceStatus
      }));
    }
    const generatedAt = isoNow(this.clock);
    const sortedCategories = scan.categories.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
    const sortedNodes = scan.nodes.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
    const sortedAnchors = scan.anchors.sort((left, right) => left.id.localeCompare(right.id));
    const sortedIssues = scan.issues.sort((left, right) =>
      String(left.severity).localeCompare(String(right.severity)) ||
      String(left.code).localeCompare(String(right.code)) ||
      stableJson(left).localeCompare(stableJson(right)));
    const sourceFingerprint = hash(stableJson({
      root: scan.rootNode.fingerprint,
      categories: sortedCategories.map(({ id, fingerprint }) => ({ id, fingerprint })),
      nodes: sortedNodes.map(({ id, fingerprint }) => ({ id, fingerprint })),
      anchors: sortedAnchors
    }));
    const globalCoherenceFingerprint = hash(stableJson({
      rootId: scan.rootNode.id,
      categories: sortedCategories.map((category) => ({
        id: category.id,
        localCoherenceFingerprint: category.localCoherenceFingerprint,
        coherenceStatus: category.coherenceStatus
      })),
      crossAnchors: sortedAnchors.filter((anchor) => anchor.source === "declared"),
      errors: sortedIssues.filter((issue) => issue.severity === "ERROR")
    }));
    const mapBody = {
      schema: MAP_SCHEMA,
      root: scan.rootNode,
      categories: sortedCategories,
      nodes: sortedNodes,
      anchors: sortedAnchors,
      policy: clone(this.policy),
      policyFingerprint: hash(stableJson(this.policy)),
      sourceFingerprint,
      coherence: {
        status: sortedIssues.some((issue) => issue.severity === "ERROR") ? "BLOCKED" : "COHERENT",
        globalCoherenceFingerprint
      },
      issues: sortedIssues,
      statistics: {
        categoryCount: sortedCategories.length,
        nodeCount: sortedNodes.length,
        anchorCount: sortedAnchors.length,
        contentFilesRead: scan.contentBudget.files,
        contentBytesRead: scan.contentBudget.bytes,
        protectedOrExcludedCount: [...sortedCategories, ...sortedNodes]
          .filter((item) => item.policyStatus !== "INCLUDE").length
      }
    };
    const mapFingerprint = hash(stableJson(mapBody));
    const map = { ...mapBody, generatedAt, mapFingerprint };
    const changes = diffMaps(this.current?.map ?? null, map);
    const status = sortedIssues.some((issue) => issue.severity === "ERROR") ? "BLOCKED" : "READY";
    const simulationBody = {
      schema: SIMULATION_SCHEMA,
      generatedAt,
      status,
      proposedRevision: changes.changed === 0 && this.current ? this.current.revision : Number(this.current?.revision ?? 0) + 1,
      previousMapFingerprint: this.current?.map?.mapFingerprint ?? null,
      sourceFingerprint,
      mapFingerprint,
      changes,
      crossAnchors: clone(crossAnchors),
      map
    };
    return { ...simulationBody, simulationHash: hash(stableJson(simulationBody)) };
  }

  commitSimulation(simulation) {
    if (!simulation || simulation.schema !== SIMULATION_SCHEMA) {
      fail("INVALID_SIMULATION", "Simulation absente ou schema invalide.");
    }
    const { simulationHash, ...body } = simulation;
    if (simulationHash !== hash(stableJson(body))) fail("SIMULATION_TAMPERED", "La simulation a ete modifiee.");
    if (simulation.status !== "READY") {
      fail("SIMULATION_BLOCKED", "Une carte incoherente ne peut pas etre persistee.", simulation.map?.issues);
    }
    const fresh = this.simulateScan({ crossAnchors: simulation.crossAnchors });
    if (fresh.sourceFingerprint !== simulation.sourceFingerprint ||
        fresh.mapFingerprint !== simulation.mapFingerprint) {
      fail("SOURCE_CHANGED_AFTER_SIMULATION", "La racine a change depuis la simulation.");
    }
    if (this.current?.map?.mapFingerprint === simulation.mapFingerprint) {
      return {
        status: "UNCHANGED",
        revision: this.current.revision,
        mapFingerprint: simulation.mapFingerprint,
        state: clone(this.current)
      };
    }
    const revision = Number(this.current?.revision ?? 0) + 1;
    const document = {
      schema: STATE_SCHEMA,
      revision,
      committedAt: isoNow(this.clock),
      simulationHash,
      map: clone(simulation.map),
      previousDocumentChecksum: this.current?.documentChecksum ?? null,
      documentChecksum: ""
    };
    document.documentChecksum = checksumDocument(document);
    const historyPath = join(
      this.paths.history,
      `${String(revision).padStart(8, "0")}-${document.documentChecksum.slice(0, 16)}.json`
    );
    atomicJson(historyPath, document, { exclusive: true });
    this.faultInjector?.("history-written", clone(document));
    atomicJson(this.paths.current, document);
    this.faultInjector?.("current-written", clone(document));
    this.current = { ...clone(document), recoveredFrom: "current" };
    return {
      status: "COMMITTED",
      revision,
      mapFingerprint: simulation.mapFingerprint,
      state: clone(this.current)
    };
  }

  run(options = {}) {
    const simulation = this.simulateScan(options);
    if (simulation.status !== "READY") return { status: "BLOCKED", simulation };
    return { status: "READY", simulation, commit: this.commitSimulation(simulation) };
  }

  getCurrentState() {
    return this.current ? clone(this.current) : null;
  }

  exportMapJson(outputPath = join(this.paths.exports, "fractal-map.json")) {
    if (!this.current) fail("NO_COMMITTED_MAP", "Aucune carte simulee et validee n'est disponible.");
    const absolute = this.#assertRuntimePath(outputPath);
    atomicJson(absolute, this.current.map);
    return {
      status: "EXPORTED",
      outputPath: absolute,
      mapFingerprint: this.current.map.mapFingerprint
    };
  }
}
