import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { spawnSync } from "node:child_process";
import { basename, dirname, join, relative, resolve } from "node:path";
import {
  applyIsolatedModelProposal,
  buildDocumentationFallbackContract,
  inspectQueueCapabilities
} from "./forge-queue-capabilities.mjs";

const [jobPath, resultPath, heartbeatPath] = process.argv.slice(2);
if (!jobPath || !resultPath || !heartbeatPath) {
  process.stderr.write("Usage: node forge-queue-worker.mjs <job.json> <result.json> <heartbeat.json>\n");
  process.exit(2);
}

const job = JSON.parse(readFileSync(resolve(jobPath), "utf8"));
const canonicalRoot = resolve(job.canonicalRoot);
const runRoot = resolve(job.runRoot);
const worktree = resolve(job.worktree);
const model = job.model || "qwen2.5-coder:7b";
const startedAt = new Date().toISOString();
const commands = [];
let lastStage = "STARTING";
let lastAction = "Worker enfant initialise.";
let heartbeatTimer;
let lastModelEvidence = null;
let lastImplementation = null;
let atomicWriteSequence = 0;

function shortSynchronousPause(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}

function atomicJson(path, value) {
  const target = resolve(path);
  mkdirSync(dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.${Date.now()}.${atomicWriteSequence += 1}.tmp`;
  writeFileSync(temporary, JSON.stringify(value, null, 2), "utf8");
  try {
    for (let attempt = 0; ; attempt += 1) {
      try {
        renameSync(temporary, target);
        return;
      } catch (error) {
        const retryable = ["EACCES", "EBUSY", "EPERM"].includes(error.code);
        if (!retryable || attempt >= 5) throw error;
        shortSynchronousPause(15 * (attempt + 1));
      }
    }
  } finally {
    // Un fichier temporaire orphelin n'est jamais une preuve de heartbeat et
    // ne doit pas s'accumuler après un verrou antivirus/indexeur Windows.
    if (existsSync(temporary)) {
      try { unlinkSync(temporary); } catch { /* incident principal conservé */ }
    }
  }
}

function heartbeat(stage, action, extra = {}) {
  lastStage = stage;
  lastAction = action;
  atomicJson(heartbeatPath, {
    schema: "aione.forge-queue-worker-heartbeat.v1",
    runId: job.runId,
    queueTaskId: job.task.id,
    pid: process.pid,
    model,
    stage,
    currentTask: job.task.title,
    lastAction: action,
    startedAt,
    lastHeartbeat: new Date().toISOString(),
    worktree,
    ...extra
  });
}

function run(command, args, { cwd = worktree, timeoutMs = 120000 } = {}) {
  heartbeat(lastStage, `Commande: ${command} ${args.join(" ")}`, { currentCommand: [command, ...args] });
  const started = Date.now();
  const result = spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    windowsHide: true,
    timeout: timeoutMs,
    maxBuffer: 8 * 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"]
  });
  const record = {
    command,
    args,
    cwd,
    startedAt: new Date(Date.now() - (Date.now() - started)).toISOString(),
    completedAt: new Date().toISOString(),
    durationMs: Date.now() - started,
    exitCode: result.status,
    signal: result.signal || null,
    stdout: String(result.stdout || "").slice(-20000),
    stderr: String(result.stderr || "").slice(-20000),
    error: result.error?.message || null
  };
  commands.push(record);
  if (record.exitCode !== 0 || record.error) {
    throw new Error(`${command} ${args.join(" ")} a echoue: ${record.error || record.stderr || `exit ${record.exitCode}`}`);
  }
  return record;
}

function walkFiles(root) {
  if (!existsSync(root)) return [];
  const output = [];
  const stack = [root];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const fullPath = join(current, entry.name);
      if (entry.isDirectory()) stack.push(fullPath);
      else if (entry.isFile()) output.push(fullPath);
    }
  }
  return output.sort();
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

function overlayCurrentForgeSources() {
  const entries = [
    "forge-control",
    "config",
    "package.json",
    "package-lock.json",
    "AGENTS.md"
  ];
  const copied = [];
  for (const entry of entries) {
    const source = join(canonicalRoot, entry);
    if (!existsSync(source)) continue;
    const destination = join(worktree, entry);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, force: true });
    if (statSync(source).isDirectory()) {
      copied.push(...walkFiles(destination).map((path) => relative(worktree, path).replaceAll("\\", "/")));
    } else {
      copied.push(relative(worktree, destination).replaceAll("\\", "/"));
    }
  }
  return [...new Set(copied)].sort();
}

async function askLocalModel(filesRead, mutationRequested) {
  heartbeat("RUNNING", `Analyse locale avec ${model}.`, { modelLoaded: false });
  const selectedSources = [
    "forge-control/server.mjs",
    "forge-control/autonomy/runtime.mjs",
    "forge-control/autonomy/agent-commons.mjs",
    "forge-control/web/agents-space.js",
    "forge-control/web/agents-space.html",
    "config/permission-broker.json",
    "config/development-capacity.json"
  ].filter((path) => existsSync(join(worktree, path)));
  const excerpts = selectedSources.map((path) => {
    const content = readFileSync(join(worktree, path), "utf8").slice(0, 6000);
    filesRead.add(path);
    return `\n## ${path}\n${content}`;
  }).join("\n");
  const prompt = [
    mutationRequested
      ? "Tu es le worker de développement local de la Forge AIONE. Tu peux proposer une petite mutation uniquement dans le workspace isolé fourni."
      : "Tu es le worker local, en lecture seule, de la Forge AIONE.",
    `Tache: ${job.task.title}`,
    `Description: ${job.task.description || ""}`,
    mutationRequested
      ? `Choisis une seule tranche verticale utile, bornée et testable. Termine obligatoirement par un bloc \`\`\`aione-mutation contenant un JSON strict: schema=aione.isolated-mutation-proposal.v1, goal, confidence >= 0.72, 1 à 3 changes, testFiles. Chaque change vaut create-file ou replace-fragment. ${job.task.requiredCapabilities?.includes("docs.write-approved") && !job.task.requiredCapabilities?.includes("write-approved") ? "Cette tâche a une permission DOCUMENTATION UNIQUEMENT: tous les chemins de changes doivent commencer par docs/. Toute modification config/, code ou script sera refusée mécaniquement." : "Les chemins doivent commencer par config/, docs/, forge-control/, projects/, schemas/, scripts/, src/ ou tests/."} Pour replace-fragment, oldText doit être recopié exactement depuis les extraits et n'apparaître qu'une fois. Ne touche jamais AGENTS.md, package.json, .git, secrets, runtime ou dépendances.`
      : "Produis un audit court et factuel: constat, preuves inspectees, risques, tests a lancer, prochaine action.",
    "N'invente aucune execution. Ne propose ni commit, ni push, ni merge, ni publication.",
    mutationRequested
      ? "La proposition sera validée mécaniquement puis appliquée uniquement au workspace isolé; la branche canonique restera inchangée."
      : "Tu n'as pas le droit de modifier les fichiers.",
    excerpts
  ].join("\n\n");
  const response = await fetch("http://127.0.0.1:11434/api/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      prompt,
      stream: false,
      options: {
        temperature: 0.15,
        num_ctx: 16384,
        num_predict: mutationRequested ? 2200 : 900
      }
    }),
    signal: AbortSignal.timeout(10 * 60 * 1000)
  });
  if (!response.ok) throw new Error(`Ollama HTTP ${response.status}: ${await response.text()}`);
  const body = await response.json();
  if (!body.response) throw new Error("Ollama n'a retourne aucune analyse.");
  heartbeat("RUNNING", `Analyse locale terminee avec ${body.model || model}.`, {
    model: body.model || model,
    modelLoaded: true
  });
  return {
    modelRequested: model,
    modelUsed: body.model || model,
    modelLoaded: true,
    response: body.response,
    totalDurationNs: Number(body.total_duration || 0),
    loadDurationNs: Number(body.load_duration || 0),
    evalCount: Number(body.eval_count || 0)
  };
}

function mutationRepairContext(proposal) {
  const excerpts = [];
  const seen = new Set();
  for (const change of proposal?.changes || []) {
    const path = String(change?.path || "").replaceAll("\\", "/");
    if (!path || seen.has(path)) continue;
    seen.add(path);
    const target = resolve(worktree, path);
    const relativeTarget = relative(worktree, target);
    if (relativeTarget.startsWith("..") || resolve(target) === resolve(worktree)) continue;
    if (!existsSync(target)) {
      excerpts.push(`## ${path}\nFICHIER ABSENT DANS LE WORKSPACE ISOLE`);
      continue;
    }
    const content = readFileSync(target, "utf8");
    const head = content.slice(0, 8000);
    const tail = content.length > 12000 ? content.slice(-4000) : "";
    excerpts.push(`## ${path} (contenu actuel exact)\n${head}${tail ? `\n...[milieu omis]...\n${tail}` : ""}`);
  }
  return excerpts.join("\n\n").slice(0, 28000);
}

async function repairMutationContract(invalidResponse, validationErrors, failingProposal = null) {
  heartbeat("RUNNING", `Correction bornée du contrat de mutation avec ${model}.`, { modelLoaded: true });
  const currentContext = mutationRepairContext(failingProposal);
  const prompt = [
    "Tu corriges uniquement un contrat JSON de mutation locale AIONE refusé. Réponds avec UN objet JSON strict, sans Markdown, sans explication et sans clé supplémentaire.",
    `Tâche à traiter réellement: ${job.task.title}\n${job.task.description || ""}`,
    "Structure exacte attendue (les valeurs TASK_SPECIFIC_* sont des marqueurs interdits à remplacer par du contenu réellement lié à la tâche):",
    JSON.stringify({
      schema: "aione.isolated-mutation-proposal.v1",
      goal: "TASK_SPECIFIC_GOAL",
      confidence: 0.9,
      changes: [{
        operation: "create-file",
        path: "docs/TASK_SPECIFIC_NAME.md",
        content: "TASK_SPECIFIC_CONTENT"
      }],
      testFiles: []
    }),
    `Règles: operation vaut seulement create-file ou replace-fragment. Un même path ne peut apparaître qu'une fois dans changes. Pour replace-fragment, fournir path, oldText recopié exactement depuis le contenu actuel ci-dessous et présent une seule fois, puis newText. N'invente jamais un oldText absent. testFiles est un tableau de chemins texte vers des fichiers .test.mjs existants, jamais des objets. Si aucun test existant ne convient, utiliser []. 1 à 3 changements. ${job.task.requiredCapabilities?.includes("docs.write-approved") && !job.task.requiredCapabilities?.includes("write-approved") ? "PERMISSION DOCUMENTATION UNIQUEMENT: tous les changes doivent cibler docs/." : "Chemins autorisés: config/, docs/, forge-control/, projects/, schemas/, scripts/, src/, tests/."} Ne touche pas AGENTS.md, package.json, .git, secrets, runtime ou dépendances.`,
    `Erreurs mécaniques à corriger: ${(validationErrors || []).join("; ").slice(0, 4000)}`,
    `Contrat refusé à restructurer: ${String(invalidResponse || "").slice(0, 12000)}`,
    currentContext ? `Contenu actuel du workspace isolé faisant autorité:\n${currentContext}` : ""
  ].join("\n\n");
  const response = await fetch("http://127.0.0.1:11434/api/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      prompt,
      stream: false,
      format: "json",
      options: { temperature: 0.05, num_ctx: 16384, num_predict: 1800 }
    }),
    signal: AbortSignal.timeout(10 * 60 * 1000)
  });
  if (!response.ok) throw new Error(`Ollama correction contrat HTTP ${response.status}: ${await response.text()}`);
  const body = await response.json();
  if (!body.response) throw new Error("Ollama n'a retourné aucun contrat corrigé.");
  return {
    modelUsed: body.model || model,
    response: `\`\`\`aione-mutation\n${String(body.response).trim()}\n\`\`\``,
    totalDurationNs: Number(body.total_duration || 0),
    evalCount: Number(body.eval_count || 0)
  };
}

function rejectPlaceholderContract(implementation) {
  if (!implementation?.ok) return implementation;
  const serialized = JSON.stringify(implementation.proposal || {});
  if (/TASK_SPECIFIC_|docs\/exemple-borne\.md|Contenu utile sans secret\./u.test(serialized)) {
    return {
      ok: false,
      status: "PLACEHOLDER_CONTRACT_REFUSED",
      errors: ["Le modèle a recopié un exemple ou un marqueur au lieu de produire une modification liée à la tâche."],
      proposal: implementation.proposal,
      changedFiles: implementation.changedFiles || []
    };
  }
  return implementation;
}

async function main() {
  mkdirSync(runRoot, { recursive: true });
  heartbeatTimer = setInterval(() => heartbeat(lastStage, lastAction), 2000);
  heartbeatTimer.unref();
  heartbeat("PREPARING", "Creation de l'environnement Git isole local.");

  if (existsSync(worktree)) {
    throw new Error(`L'environnement isole cible existe deja: ${worktree}`);
  }
  mkdirSync(dirname(worktree), { recursive: true });
  run("git", ["clone", "--shared", "--no-checkout", canonicalRoot, worktree], {
    cwd: canonicalRoot,
    timeoutMs: 120000
  });
  run("git", ["checkout", "--detach", "HEAD"], {
    cwd: worktree,
    timeoutMs: 120000
  });
  heartbeat("WORKTREE_READY", "Clone partage isole en HEAD detache; aucun branchement ni commit.");
  await delay(700);

  const overlayFiles = overlayCurrentForgeSources();
  const manifestPath = join(runRoot, "overlay-manifest.json");
  atomicJson(manifestPath, {
    schema: "aione.forge-worker-overlay.v1",
    canonicalRoot,
    worktree,
    copiedAt: new Date().toISOString(),
    files: overlayFiles
  });

  const filesRead = new Set([
    "AGENTS.md",
    "package.json",
    "config/permission-broker.json",
    "config/development-capacity.json"
  ].filter((path) => existsSync(join(worktree, path))));

  heartbeat("RUNNING", "Verification du depot isole.");
  run("git", ["rev-parse", "HEAD"]);
  run("git", ["status", "--short", "--branch"]);
  const capabilities = inspectQueueCapabilities(job.task);
  if (!capabilities.eligible) throw new Error(`Capacités worker refusées: ${capabilities.unsupportedCapabilities.join(",")}`);
  const modelEvidence = await askLocalModel(filesRead, capabilities.mutationRequested);
  lastModelEvidence = modelEvidence;
  const allowedPathPrefixes = capabilities.documentationOnly ? ["docs/"] : null;
  let implementation = capabilities.mutationRequested
    ? applyIsolatedModelProposal({ markdown: modelEvidence.response, workspace: worktree, allowedPathPrefixes })
    : { ok: true, status: "READ_ONLY_TASK", changedFiles: [], proposal: null };
  implementation = rejectPlaceholderContract(implementation);
  if (!implementation.ok && capabilities.mutationRequested) {
    modelEvidence.initialResponse = modelEvidence.response;
    const attempts = [];
    for (let attempt = 1; attempt <= 2 && !implementation.ok; attempt += 1) {
      const correction = await repairMutationContract(
        modelEvidence.response,
        implementation.errors || [implementation.error],
        implementation.proposal
      );
      modelEvidence.response = correction.response;
      attempts.push({
        attempt,
        modelUsed: correction.modelUsed,
        totalDurationNs: correction.totalDurationNs,
        evalCount: correction.evalCount
      });
      implementation = rejectPlaceholderContract(applyIsolatedModelProposal({ markdown: correction.response, workspace: worktree, allowedPathPrefixes }));
    }
    modelEvidence.contractCorrection = {
      attempted: true,
      maximumAttempts: 2,
      attempts
    };
  }
  if (!implementation.ok && capabilities.documentationOnly) {
    const rejectedImplementation = implementation;
    const fallbackContract = buildDocumentationFallbackContract(job.task, rejectedImplementation);
    implementation = applyIsolatedModelProposal({
      markdown: fallbackContract,
      workspace: worktree,
      allowedPathPrefixes
    });
    modelEvidence.deterministicDocumentationFallback = {
      attempted: true,
      accepted: implementation.ok,
      rejectedModelStatus: rejectedImplementation.status,
      rejectedModelErrors: rejectedImplementation.errors || [],
      reason: "Le modèle local n'a pas respecté la portée après correction; aucun garde-fou n'a été affaibli."
    };
  }
  lastImplementation = implementation;
  if (!implementation.ok) {
    throw new Error(`Contrat de mutation isolée refusé: ${implementation.status} ${(implementation.errors || [implementation.error]).filter(Boolean).join("; ")}`);
  }

  heartbeat("TESTING", "Execution des validations dans le worktree.");
  await delay(700);
  const syntax = run("node", ["--check", "forge-control/server.mjs"]);
  const tests = run("node", [
    "--test",
    "forge-control/autonomy/control-plane.test.mjs",
    "forge-control/autonomy/digital-life.test.mjs"
  ], { timeoutMs: 240000 });
  const proposalTests = [];
  for (const testFile of implementation.proposal?.testFiles || []) {
    proposalTests.push(run("node", ["--test", testFile], { timeoutMs: 240000 }));
  }

  heartbeat("REVIEWING", "Relecture des preuves et verification de l'absence de mutation canonique.");
  await delay(700);
  const isolatedStatus = run("git", ["status", "--short", "--branch"]);
  const result = {
    schema: "aione.forge-queue-worker-result.v1",
    ok: true,
    runId: job.runId,
    queueTaskId: job.task.id,
    cardId: job.card?.id || null,
    pid: process.pid,
    model: modelEvidence,
    startedAt,
    completedAt: new Date().toISOString(),
    durationMs: Date.now() - Date.parse(startedAt),
    canonicalRoot,
    canonicalMutationPerformed: false,
    worktree,
    detached: true,
    isolationMode: "detached-shared-clone",
    registeredGitWorktree: false,
    branchCreated: false,
    commitCreated: false,
    pushed: false,
    merged: false,
    published: false,
    overlayManifest: manifestPath,
    filesRead: [...filesRead].sort(),
    filesCopiedToIsolatedWorktree: overlayFiles,
    filesModifiedInCanonicalRepository: [],
    filesModifiedInIsolatedWorktree: implementation.changedFiles || [],
    commands,
    tests: [
      { name: "node syntax", commandIndex: commands.indexOf(syntax), passed: syntax.exitCode === 0 },
      { name: "control-plane and digital-life", commandIndex: commands.indexOf(tests), passed: tests.exitCode === 0 },
      ...proposalTests.map((testResult) => ({
        name: `proposal test ${testResult.args.at(-1)}`,
        commandIndex: commands.indexOf(testResult),
        passed: testResult.exitCode === 0
      }))
    ],
    analysis: modelEvidence.response,
    implementation,
    isolatedGitStatus: isolatedStatus.stdout
  };
  atomicJson(resultPath, result);
  heartbeat("COMPLETED", "Worker termine; resultat en attente de revue humaine.", {
    model: modelEvidence.modelUsed,
    modelLoaded: true,
    resultPath
  });
}

main().catch((error) => {
  const failure = {
    schema: "aione.forge-queue-worker-result.v1",
    ok: false,
    runId: job.runId,
    queueTaskId: job.task?.id,
    pid: process.pid,
    model: lastModelEvidence || { modelRequested: model, modelUsed: null, modelLoaded: false },
    implementation: lastImplementation,
    startedAt,
    completedAt: new Date().toISOString(),
    durationMs: Date.now() - Date.parse(startedAt),
    canonicalRoot,
    worktree,
    commands,
    error: error instanceof Error ? error.stack || error.message : String(error)
  };
  try {
    atomicJson(resultPath, failure);
    heartbeat("FAILED", failure.error, { resultPath });
  } catch {
    // The process exit code remains the final failure signal.
  }
  process.stderr.write(`${failure.error}\n`);
  process.exitCode = 1;
}).finally(() => {
  if (heartbeatTimer) clearInterval(heartbeatTimer);
});
