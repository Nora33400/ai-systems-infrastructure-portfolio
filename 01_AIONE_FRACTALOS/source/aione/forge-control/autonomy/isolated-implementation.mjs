import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync
} from "node:fs";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { basename, dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_PATH = fileURLToPath(import.meta.url);
const DEFAULT_ROOT = resolve(dirname(MODULE_PATH), "..", "..");
const DEFAULT_RUNTIME_ROOT = "S:\\AI_LAB\\Runtime\\DualGpuDevelopment";
const PROPOSAL_SCHEMA = "aione.isolated-mutation-proposal.v1";
const ALLOWED_PREFIXES = [
  "aione_cognitive_engine/",
  "config/",
  "docs/",
  "forge-control/",
  "projects/",
  "schemas/",
  "scripts/",
  "src/",
  "tests/"
];
const ALLOWED_EXTENSIONS = new Set([
  ".cjs",
  ".css",
  ".html",
  ".js",
  ".json",
  ".md",
  ".mjs",
  ".ps1",
  ".py",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml"
]);
const DENIED_PATH_PATTERN = /(^|\/)(?:\.git|node_modules|dist|build|coverage|runtime|secrets?|credentials?|private|\.env(?:\.|$))|(?:^|\/)(?:package(?:-lock)?\.json|agents\.md)$/i;
const SECRET_PATTERN = /(?:api[_-]?key|authorization|bearer|password|private[_-]?key|secret|token)\s*[:=]\s*["'`]?[A-Za-z0-9+/_=-]{12,}/i;
const GUARDED_TRUE_KEYS = Object.freeze([
  "isolatedCodeRunnerRequiredForFileMutation",
  "requireHumanReviewBeforeCanonicalApply",
  "noDependencyInstall",
  "noModelDownload",
  "noGitCommitPushMerge",
  "noProtectedPathWrite",
  "respectThermals",
  "localOnly",
  "bindLoopbackOnly",
  "requireValidationAfterRepair",
  "publicationRequiresHuman"
]);
const GUARDED_FALSE_KEYS = Object.freeze([
  "allowCloudModels",
  "allowModelDownload",
  "allowDependencyInstall",
  "allowCanonicalMutation",
  "allowGitCommitPushMerge",
  "allowExternalPublication",
  "automaticPublication"
]);

function atomicJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  renameSync(temporary, path);
}

function atomicText(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, String(value), "utf8");
  renameSync(temporary, path);
}

function readJson(path, fallback = null) {
  try {
    return JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
  } catch {
    return fallback;
  }
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function hashFile(path) {
  return existsSync(path) ? sha256(readFileSync(path)) : null;
}

function normalizeProposalPath(value) {
  const normalized = String(value || "").replaceAll("\\", "/").replace(/^\.\/+/, "");
  if (
    !normalized ||
    normalized.startsWith("/") ||
    /^[A-Za-z]:/.test(normalized) ||
    normalized.split("/").some((part) => !part || part === "." || part === "..")
  ) {
    throw new Error(`Chemin de proposition refusé: ${value}`);
  }
  if (!ALLOWED_PREFIXES.some((prefix) => normalized.startsWith(prefix))) {
    throw new Error(`Chemin hors allowlist: ${normalized}`);
  }
  if (DENIED_PATH_PATTERN.test(normalized)) {
    throw new Error(`Chemin protégé ou sensible: ${normalized}`);
  }
  if (!ALLOWED_EXTENSIONS.has(extname(normalized).toLowerCase())) {
    throw new Error(`Extension non autorisée: ${normalized}`);
  }
  return normalized;
}

function resolveInside(root, relativePath) {
  const target = resolve(root, relativePath);
  const boundary = `${resolve(root)}${sep}`;
  if (target !== resolve(root) && !target.startsWith(boundary)) {
    throw new Error(`Échappement de workspace refusé: ${relativePath}`);
  }
  return target;
}

function ensureNoSymlink(root, relativePath) {
  let current = resolve(root);
  for (const part of relativePath.replaceAll("\\", "/").split("/").slice(0, -1)) {
    current = join(current, part);
    if (existsSync(current) && lstatSync(current).isSymbolicLink()) {
      throw new Error(`Lien symbolique refusé dans le chemin: ${relativePath}`);
    }
  }
}

function extractMutationProposal(markdown) {
  const match = String(markdown || "").match(/```aione-mutation[^\r\n]*\r?\n([\s\S]*?)```/i);
  if (!match) {
    return { ok: false, status: "NO_CONTRACT", error: "Bloc aione-mutation absent." };
  }
  try {
    const body = match[1].trim();
    const firstBrace = body.indexOf("{");
    const lastBrace = body.lastIndexOf("}");
    if (firstBrace < 0 || lastBrace <= firstBrace) throw new Error("Objet JSON absent du bloc.");
    return { ok: true, status: "PARSED", proposal: JSON.parse(body.slice(firstBrace, lastBrace + 1)) };
  } catch (error) {
    return { ok: false, status: "INVALID_JSON", error: error.message };
  }
}

function assertFundamentalGuardsPreserved(oldText, newText) {
  for (const key of GUARDED_TRUE_KEYS) {
    const guarded = new RegExp(`(?:^|[\\r\\n{,])\\s*"${key}"\\s*:\\s*true`, "u");
    if (guarded.test(oldText) && !guarded.test(newText)) {
      throw new Error(`garde-fou fondamental non affaiblissable: ${key}=true`);
    }
  }
  for (const key of GUARDED_FALSE_KEYS) {
    const guarded = new RegExp(`(?:^|[\\r\\n{,])\\s*"${key}"\\s*:\\s*false`, "u");
    if (guarded.test(oldText) && !guarded.test(newText)) {
      throw new Error(`garde-fou fondamental non affaiblissable: ${key}=false`);
    }
  }
}

function validateMutationProposal(proposal, options = {}) {
  const maximumChanges = Number(options.maximumChanges || 3);
  const maximumTotalCharacters = Number(options.maximumTotalCharacters || 64 * 1024);
  const minimumConfidence = Number(options.minimumConfidence ?? 0.72);
  const tolerateInvalidTestFiles = options.tolerateInvalidTestFiles === true;
  const errors = [];
  const warnings = [];
  const normalized = {
    schema: proposal?.schema,
    goal: String(proposal?.goal || "").trim(),
    confidence: Number(proposal?.confidence),
    changes: [],
    testFiles: Array.isArray(proposal?.testFiles) ? proposal.testFiles : []
  };
  if (proposal?.schema !== PROPOSAL_SCHEMA) errors.push(`schema doit valoir ${PROPOSAL_SCHEMA}`);
  if (normalized.goal.length < 12 || normalized.goal.length > 500) errors.push("goal doit contenir 12 à 500 caractères");
  if (!Number.isFinite(normalized.confidence) || normalized.confidence < minimumConfidence || normalized.confidence > 1) {
    errors.push(`confidence doit être comprise entre ${minimumConfidence} et 1`);
  }
  if (!Array.isArray(proposal?.changes) || proposal.changes.length < 1 || proposal.changes.length > maximumChanges) {
    errors.push(`changes doit contenir 1 à ${maximumChanges} changements`);
  } else {
    for (const [index, raw] of proposal.changes.entries()) {
      try {
        const path = normalizeProposalPath(raw?.path);
        const operation = String(raw?.operation || "");
        if (!["create-file", "replace-fragment"].includes(operation)) {
          throw new Error(`opération inconnue: ${operation}`);
        }
        const change = { operation, path };
        if (operation === "create-file") {
          change.content = String(raw?.content ?? "");
          if (!change.content.trim()) throw new Error("contenu vide");
          if (SECRET_PATTERN.test(change.content)) throw new Error("secret ou jeton potentiel détecté");
        } else {
          change.oldText = String(raw?.oldText ?? "");
          change.newText = String(raw?.newText ?? "");
          if (!change.oldText || !change.newText) throw new Error("oldText et newText sont obligatoires et non vides");
          if (change.oldText === change.newText) throw new Error("remplacement sans changement");
          if (SECRET_PATTERN.test(change.newText)) throw new Error("secret ou jeton potentiel détecté");
          assertFundamentalGuardsPreserved(change.oldText, change.newText);
        }
        normalized.changes.push(change);
      } catch (error) {
        errors.push(`changes[${index}]: ${error.message}`);
      }
    }
  }
  let totalCharacters = 0;
  for (const change of normalized.changes) {
    totalCharacters += (change.content || "").length + (change.oldText || "").length + (change.newText || "").length;
  }
  if (totalCharacters > maximumTotalCharacters) errors.push(`taille totale supérieure à ${maximumTotalCharacters} caractères`);
  const changedPaths = new Set(normalized.changes.map((change) => change.path));
  if (changedPaths.size !== normalized.changes.length) errors.push("un fichier ne peut être modifié qu'une fois par proposition");
  const tests = [];
  for (const rawPath of normalized.testFiles.slice(0, 3)) {
    try {
      const path = normalizeProposalPath(rawPath);
      if (!/\.test\.mjs$/i.test(path)) throw new Error("seuls les tests Node .test.mjs sont exécutables automatiquement");
      if (changedPaths.has(path)) throw new Error("un test généré ou modifié ne peut pas être auto-exécuté");
      tests.push(path);
    } catch (error) {
      const message = `testFiles: ${error.message}`;
      if (tolerateInvalidTestFiles) warnings.push(`${message}; suggestion ignorée, tests Forge obligatoires conservés`);
      else errors.push(message);
    }
  }
  normalized.testFiles = [...new Set(tests)];
  return { ok: errors.length === 0, errors, warnings, proposal: normalized, totalCharacters };
}

function enqueueMutationProposal({
  runtimeRoot = DEFAULT_RUNTIME_ROOT,
  canonicalRoot,
  manifestPath,
  markdown,
  packageId,
  laneId,
  minimumConfidence = 0.72
}) {
  const extracted = extractMutationProposal(markdown);
  if (!extracted.ok) return extracted;
  const validation = validateMutationProposal(extracted.proposal, {
    minimumConfidence,
    tolerateInvalidTestFiles: true
  });
  if (!validation.ok) {
    return { ok: false, status: "INVALID_CONTRACT", errors: validation.errors };
  }
  const automaticRepairs = [];
  if (canonicalRoot) {
    const preflightErrors = [];
    validation.proposal.changes = validation.proposal.changes.map((change) => {
      const target = resolveInside(resolve(canonicalRoot), change.path);
      if (change.operation === "replace-fragment" && !existsSync(target)) {
        automaticRepairs.push(`replace-fragment→create-file:${change.path}`);
        return { operation: "create-file", path: change.path, content: change.newText };
      }
      return change;
    });
    for (const change of validation.proposal.changes) {
      const target = resolveInside(resolve(canonicalRoot), change.path);
      if (change.operation === "create-file" && existsSync(target)) {
        preflightErrors.push(`create-file refuse un fichier existant: ${change.path}`);
      } else if (change.operation === "replace-fragment") {
        if (!existsSync(target)) {
          preflightErrors.push(`fichier à remplacer absent: ${change.path}`);
        } else {
          const occurrences = countOccurrences(readFileSync(target, "utf8"), change.oldText);
          if (occurrences !== 1) preflightErrors.push(`oldText doit apparaître une fois dans ${change.path}; trouvé=${occurrences}`);
        }
      }
    }
    if (preflightErrors.length) {
      return { ok: false, status: "PREFLIGHT_REJECTED", errors: preflightErrors };
    }
  }
  const safeId = String(packageId || "").replace(/[^A-Za-z0-9._-]/g, "_");
  if (!safeId) return { ok: false, status: "INVALID_PACKAGE_ID", error: "packageId absent" };
  const targetSignature = validation.proposal.changes
    .map((change) => {
      const canonicalHash = canonicalRoot ? hashFile(resolveInside(resolve(canonicalRoot), change.path)) : null;
      return `${change.operation}:${change.path}:${canonicalHash || "ABSENT"}`;
    })
    .sort()
    .join("|");
  const targetKey = sha256(targetSignature).slice(0, 24);
  const indexPath = join(runtimeRoot, "implementation-contract-index", `${targetKey}.json`);
  mkdirSync(dirname(indexPath), { recursive: true });
  try {
    writeFileSync(indexPath, `${JSON.stringify({
      schema: "aione.isolated-contract-target-claim.v1",
      targetKey,
      targetSignature,
      packageId,
      laneId,
      claimedAt: new Date().toISOString()
    }, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
    const existing = readJson(indexPath, {});
    return {
      ok: false,
      status: "DUPLICATE_TARGET_CONTRACT",
      targetKey,
      existingPackageId: existing.packageId || null,
      existingLaneId: existing.laneId || null
    };
  }
  const proposalPath = join(runtimeRoot, "implementation-proposals", laneId || "unknown", `${safeId}.json`);
  const queuePath = join(runtimeRoot, "implementation-queue", `${safeId}.json`);
  atomicJson(proposalPath, {
    schema: "aione.isolated-mutation-envelope.v1",
    packageId,
    laneId,
    createdAt: new Date().toISOString(),
    manifestPath,
    proposal: validation.proposal
  });
  atomicJson(queuePath, {
    schema: "aione.isolated-implementation-queue-item.v1",
    packageId,
    laneId,
    createdAt: new Date().toISOString(),
    manifestPath,
    proposalPath
  });
  return {
    ok: true,
    status: "QUEUED_FOR_ISOLATED_IMPLEMENTATION",
    proposalPath,
    queuePath,
    changeCount: validation.proposal.changes.length,
    targetKey,
    warnings: validation.warnings,
    automaticRepairs
  };
}

function copySnapshot(canonicalRoot, workspace, targetPaths) {
  const copied = [];
  const roots = new Set(["forge-control", "config", "scripts", "schemas"]);
  for (const path of targetPaths) roots.add(path.split("/")[0]);
  for (const entry of ["package.json", "AGENTS.md"]) {
    if (existsSync(join(canonicalRoot, entry))) roots.add(entry);
  }
  const filter = (source) => {
    const name = basename(source);
    if (/^(?:\.git|node_modules|dist|build|coverage|runtime)$/i.test(name)) return false;
    if (/^(?:\.env|secrets?|credentials?|private)$/i.test(name)) return false;
    if (existsSync(source) && lstatSync(source).isSymbolicLink()) return false;
    return true;
  };
  for (const entry of roots) {
    const source = join(canonicalRoot, entry);
    if (!existsSync(source)) continue;
    const destination = join(workspace, entry);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, force: true, filter });
    copied.push(entry);
  }
  return copied.sort();
}

function countOccurrences(content, fragment) {
  let count = 0;
  let offset = 0;
  while (true) {
    const index = content.indexOf(fragment, offset);
    if (index < 0) return count;
    count += 1;
    offset = index + fragment.length;
  }
}

function applyChanges(workspace, changes, options = {}) {
  const prepared = [];
  for (const change of changes) {
    ensureNoSymlink(workspace, change.path);
    const target = resolveInside(workspace, change.path);
    if (change.operation === "create-file") {
      if (existsSync(target)) throw new Error(`create-file refuse d'écraser: ${change.path}`);
      prepared.push({ change, target, content: change.content, existed: false, original: null });
    } else {
      if (!existsSync(target)) throw new Error(`fichier à remplacer absent: ${change.path}`);
      const original = readFileSync(target, "utf8");
      const occurrences = countOccurrences(original, change.oldText);
      if (occurrences !== 1) throw new Error(`oldText doit apparaître exactement une fois dans ${change.path}; trouvé=${occurrences}`);
      prepared.push({ change, target, content: original.replace(change.oldText, change.newText), existed: true, original });
    }
  }

  // Aucune écriture n'est faite avant que l'ensemble du contrat ait passé le
  // préflight. Une erreur tardive ne peut donc plus laisser un workspace à
  // moitié muté et rendre la correction automatique incohérente.
  const changed = [];
  const applied = [];
  try {
    for (const item of prepared) {
      const { change, target, content } = item;
      atomicText(target, content);
      applied.push(item);
      changed.push({
        path: change.path,
        operation: change.operation,
        sha256: hashFile(target),
        bytes: readFileSync(target).length
      });
    }
    if (typeof options.validate === "function") {
      const validation = options.validate(changed);
      if (validation?.ok === false) {
        const error = new Error((validation.errors || ["validation statique refusée"]).join("; "));
        error.code = "STATIC_VALIDATION_REJECTED";
        error.validation = validation;
        throw error;
      }
    }
  } catch (error) {
    for (const item of applied.reverse()) {
      try {
        if (item.existed) atomicText(item.target, item.original);
        else if (existsSync(item.target)) unlinkSync(item.target);
      } catch {
        // Le workspace reste isolé; l'erreur initiale et le rollback incomplet
        // seront conservés comme incident, jamais promus au dépôt canonique.
      }
    }
    throw error;
  }
  return changed;
}

function commandResult(command, args, options = {}) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    encoding: "utf8",
    windowsHide: true,
    timeout: options.timeoutMs || 120000,
    maxBuffer: 4 * 1024 * 1024,
    env: options.env || {
      PATH: process.env.PATH,
      SystemRoot: process.env.SystemRoot,
      TEMP: process.env.TEMP,
      TMP: process.env.TMP
    },
    stdio: ["ignore", "pipe", "pipe"]
  });
  return {
    command: [command, ...args].join(" "),
    startedAt,
    completedAt: new Date().toISOString(),
    ok: result.status === 0 && !result.error,
    exitCode: result.status,
    signal: result.signal || null,
    stdout: String(result.stdout || "").slice(-12000),
    stderr: String(result.stderr || result.error?.message || "").slice(-12000)
  };
}

function validateChangedFiles(workspace, changedFiles) {
  const results = [];
  for (const file of changedFiles) {
    const target = resolveInside(workspace, file.path);
    const extension = extname(target).toLowerCase();
    if (extension === ".json") {
      try {
        JSON.parse(readFileSync(target, "utf8"));
        results.push({ type: "static", path: file.path, ok: true, detail: "JSON valide" });
      } catch (error) {
        results.push({ type: "static", path: file.path, ok: false, detail: error.message });
      }
    } else if ([".js", ".mjs", ".cjs", ".ts"].includes(extension)) {
      const result = commandResult(process.execPath, ["--check", target], { cwd: workspace, timeoutMs: 30000 });
      results.push({ type: "syntax", path: file.path, ...result });
    } else if (extension === ".py") {
      const parser = "import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))";
      const result = commandResult("python", ["-c", parser, target], { cwd: workspace, timeoutMs: 30000 });
      results.push({ type: "syntax", path: file.path, ...result });
    } else if (extension === ".ps1") {
      const parser = "& { param($Path) $tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors) | Out-Null; if($errors.Count){$errors | ForEach-Object { $_.Message }; exit 1} }";
      const result = commandResult("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", parser, target], {
        cwd: workspace,
        timeoutMs: 30000
      });
      results.push({ type: "syntax", path: file.path, ...result });
    } else {
      const content = readFileSync(target, "utf8");
      results.push({
        type: "static",
        path: file.path,
        ok: content.trim().length > 0,
        detail: content.trim().length > 0 ? "contenu texte non vide" : "contenu vide"
      });
    }
  }
  return results;
}

function selectTrustedTests(workspace, proposal) {
  const changed = new Set(proposal.changes.map((change) => change.path));
  const candidates = [...proposal.testFiles];
  for (const change of proposal.changes) {
    if (!change.path.endsWith(".mjs") || change.path.endsWith(".test.mjs")) continue;
    const sibling = change.path.replace(/\.mjs$/i, ".test.mjs");
    if (existsSync(resolveInside(workspace, sibling)) && !changed.has(sibling)) candidates.push(sibling);
  }
  return [...new Set(candidates)].filter((path) => existsSync(resolveInside(workspace, path)) && !changed.has(path));
}

function runPermissionedTests(workspace, tests, tempRoot) {
  if (tests.length === 0) return [];
  mkdirSync(tempRoot, { recursive: true });
  const args = [
    "--permission",
    `--allow-fs-read=${workspace}`,
    `--allow-fs-write=${tempRoot}`,
    "--test-isolation=none",
    "--test",
    ...tests
  ];
  return [commandResult(process.execPath, args, {
    cwd: workspace,
    timeoutMs: 180000,
    env: {
      PATH: process.env.PATH,
      SystemRoot: process.env.SystemRoot,
      TEMP: tempRoot,
      TMP: tempRoot,
      NODE_NO_WARNINGS: "1"
    }
  })];
}

function processQueueItem({ canonicalRoot, runtimeRoot, queueItem }) {
  const envelope = readJson(queueItem.proposalPath);
  if (!envelope?.proposal) throw new Error(`Proposition introuvable: ${queueItem.proposalPath}`);
  const validation = validateMutationProposal(envelope.proposal);
  if (!validation.ok) throw new Error(`Contrat refusé: ${validation.errors.join("; ")}`);
  const safeId = String(queueItem.packageId).replace(/[^A-Za-z0-9._-]/g, "_");
  const runRoot = join(runtimeRoot, "isolated-implementations", safeId);
  const workspace = join(runRoot, "workspace");
  const resultPath = join(runRoot, "result.json");
  if (existsSync(resultPath)) return readJson(resultPath);
  if (existsSync(workspace)) throw new Error(`Workspace incomplet déjà présent: ${workspace}`);
  mkdirSync(workspace, { recursive: true });
  const canonicalBefore = Object.fromEntries(validation.proposal.changes.map((change) => [
    change.path,
    hashFile(resolveInside(canonicalRoot, change.path))
  ]));
  const snapshotEntries = copySnapshot(canonicalRoot, workspace, validation.proposal.changes.map((change) => change.path));
  const changedFiles = applyChanges(workspace, validation.proposal.changes);
  const staticValidation = validateChangedFiles(workspace, changedFiles);
  const trustedTests = selectTrustedTests(workspace, validation.proposal);
  const testValidation = staticValidation.every((item) => item.ok)
    ? runPermissionedTests(workspace, trustedTests, join(runRoot, "temp"))
    : [];
  const canonicalAfter = Object.fromEntries(validation.proposal.changes.map((change) => [
    change.path,
    hashFile(resolveInside(canonicalRoot, change.path))
  ]));
  const canonicalUnchanged = Object.keys(canonicalBefore).every((path) => canonicalBefore[path] === canonicalAfter[path]);
  const validationOk = staticValidation.every((item) => item.ok) && testValidation.every((item) => item.ok);
  const status = !canonicalUnchanged
    ? "CANONICAL_DRIFT_DETECTED"
    : !validationOk
      ? "FAILED_ISOLATED_VALIDATION"
      : testValidation.length > 0
        ? "TESTED_ISOLATED"
        : "STATIC_VALIDATED_ISOLATED";
  const result = {
    schema: "aione.isolated-implementation-result.v1",
    packageId: queueItem.packageId,
    laneId: queueItem.laneId,
    status,
    ok: canonicalUnchanged && validationOk,
    createdAt: queueItem.createdAt,
    completedAt: new Date().toISOString(),
    canonicalRoot,
    canonicalMutationPerformed: false,
    canonicalUnchanged,
    canonicalHashesBefore: canonicalBefore,
    canonicalHashesAfter: canonicalAfter,
    isolatedMutationPerformed: changedFiles.length > 0,
    workspace,
    snapshotEntries,
    changedFiles,
    staticValidation,
    trustedTests,
    testValidation,
    permissionSandbox: {
      enabledForTests: testValidation.length > 0,
      network: "DENY",
      childProcess: "DENY",
      workerThreads: "DENY",
      filesystemRead: workspace,
      filesystemWrite: join(runRoot, "temp")
    },
    humanReviewRequired: false,
    isolatedRetentionDecision: "AUTO_KEEP_IF_VALIDATED",
    autonomousContinuation: true,
    canonicalPromotionDecision: "ASK_OWNER"
  };
  atomicJson(resultPath, result);
  return result;
}

function runNextIsolatedImplementation({
  canonicalRoot = DEFAULT_ROOT,
  runtimeRoot = DEFAULT_RUNTIME_ROOT
} = {}) {
  canonicalRoot = resolve(canonicalRoot);
  runtimeRoot = resolve(runtimeRoot);
  if (!/^S:\\/i.test(runtimeRoot)) throw new Error(`Runtime isolé hors S refusé: ${runtimeRoot}`);
  const queueRoot = join(runtimeRoot, "implementation-queue");
  mkdirSync(queueRoot, { recursive: true });
  const statePath = join(runtimeRoot, "isolated-implementation-state.json");
  const state = readJson(statePath, {
    schema: "aione.isolated-implementation-state.v1",
    processed: {},
    totals: { processed: 0, succeeded: 0, failed: 0 }
  });
  const candidates = readdirSync(queueRoot)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => readJson(join(queueRoot, name)))
    .filter((item) => item?.packageId && !state.processed[item.packageId]);
  if (candidates.length === 0) {
    return { ok: true, status: "QUEUE_EMPTY", pending: 0, totals: state.totals };
  }
  const queueItem = candidates[0];
  let result;
  try {
    result = processQueueItem({ canonicalRoot, runtimeRoot, queueItem });
  } catch (error) {
    result = {
      schema: "aione.isolated-implementation-result.v1",
      packageId: queueItem.packageId,
      laneId: queueItem.laneId,
      status: "FAILED_PROCESSING",
      ok: false,
      completedAt: new Date().toISOString(),
      canonicalMutationPerformed: false,
      isolatedMutationPerformed: false,
      humanReviewRequired: false,
      autonomousContinuation: true,
      automaticNextAction: "RETRY_OR_REPLAN",
      error: error.stack || error.message
    };
    const safeId = String(queueItem.packageId).replace(/[^A-Za-z0-9._-]/g, "_");
    atomicJson(join(runtimeRoot, "isolated-implementations", safeId, "result.json"), result);
  }
  state.processed[queueItem.packageId] = {
    at: result.completedAt,
    status: result.status,
    ok: result.ok
  };
  state.totals.processed += 1;
  if (result.ok) state.totals.succeeded += 1;
  else state.totals.failed += 1;
  state.updatedAt = new Date().toISOString();
  atomicJson(statePath, state);
  return {
    ...result,
    pending: Math.max(0, candidates.length - 1),
    totals: state.totals
  };
}

function parseArguments(values) {
  const options = {};
  for (let index = 0; index < values.length; index += 1) {
    if (values[index] === "--root") options.canonicalRoot = values[++index];
    else if (values[index] === "--runtime") options.runtimeRoot = values[++index];
  }
  return options;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(MODULE_PATH)) {
  try {
    process.stdout.write(`${JSON.stringify(runNextIsolatedImplementation(parseArguments(process.argv.slice(2))), null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  }
}

export {
  PROPOSAL_SCHEMA,
  applyChanges,
  enqueueMutationProposal,
  extractMutationProposal,
  normalizeProposalPath,
  runNextIsolatedImplementation,
  runPermissionedTests,
  validateChangedFiles,
  validateMutationProposal
};
