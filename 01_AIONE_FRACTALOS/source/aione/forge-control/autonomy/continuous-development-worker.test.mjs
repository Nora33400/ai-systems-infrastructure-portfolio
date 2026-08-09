import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { testRuntimeRoot } from "./test-paths.mjs";
import {
  assertLocalEndpoint,
  assessOutputStructure,
  atomicJson,
  buildPrompt,
  completeOutputStructure,
  contentRevision,
  createDailyAgenda,
  chooseNovelWorkItem,
  extractBacklogCandidates,
  extractReferencedProjectPaths,
  getPartition,
  inspectForgePriorityQueue,
  isPathWithinAllowedRoot,
  isExpectedModelResident,
  isAbsolutePriorityWorkItem,
  loadSources,
  mutateAgenda,
  parseNvidiaCsv,
  resourceDecision,
  sanitizeText,
  shouldAbortGeneration,
  shouldYieldForPriorityQueue,
  shouldUseFallback,
  updateAgenda,
  workItemKey
} from "./continuous-development-worker.mjs";
import { buildPolicyContextResolution, readContextAuthorityPolicy } from "./context-authority.mjs";

test("backlog sources may read the explicit runtime root but reject unrelated paths", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-worker-source-root-"));
  const runtimeRoot = mkdtempSync(join(testRuntimeRoot(), "aione-worker-runtime-root-"));
  const modelEvolutionRoot = mkdtempSync(join(testRuntimeRoot(), "aione-worker-model-evolution-"));
  const unrelatedRoot = mkdtempSync(join(testRuntimeRoot(), "aione-worker-unrelated-"));
  try {
    assert.equal(isPathWithinAllowedRoot(runtimeRoot, runtimeRoot), true);
    assert.equal(isPathWithinAllowedRoot(join(runtimeRoot, "child", "item.md"), runtimeRoot), true);
    assert.equal(isPathWithinAllowedRoot(`${runtimeRoot}-sibling`, runtimeRoot), false);
    assert.equal(isPathWithinAllowedRoot(join(unrelatedRoot, "item.md"), runtimeRoot), false);
    mkdirSync(join(root, "docs"), { recursive: true });
    mkdirSync(join(root, "apps"), { recursive: true });
    writeFileSync(join(root, "docs", "backlog.md"), "P0 améliorer le projet local", "utf8");
    writeFileSync(join(runtimeRoot, "generated-backlog.md"), "P0 améliorer le runner isolé", "utf8");
    writeFileSync(join(modelEvolutionRoot, "generated-backlog.md"), "P0 améliorer le modèle local avec benchmark", "utf8");
    writeFileSync(join(unrelatedRoot, "secret.md"), "ne pas lire", "utf8");
    const sources = loadSources(root, [
      "docs/backlog.md",
      "apps",
      join(runtimeRoot, "generated-backlog.md"),
      join(modelEvolutionRoot, "generated-backlog.md"),
      join(unrelatedRoot, "secret.md")
    ], [runtimeRoot, modelEvolutionRoot]);
    assert.equal(sources.length, 3);
    assert.ok(sources.some((item) => item.content.includes("runner isolé")));
    assert.ok(sources.some((item) => item.content.includes("modèle local")));
    assert.equal(sources.some((item) => item.content.includes("ne pas lire")), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(runtimeRoot, { recursive: true, force: true });
    rmSync(modelEvolutionRoot, { recursive: true, force: true });
    rmSync(unrelatedRoot, { recursive: true, force: true });
  }
});

test("endpoints are restricted to explicit local HTTP ports", () => {
  assert.equal(assertLocalEndpoint("http://127.0.0.1:11435"), "http://127.0.0.1:11435");
  assert.throws(() => assertLocalEndpoint("https://example.com:443"), /non local/);
  assert.throws(() => assertLocalEndpoint("http://127.0.0.1"), /Port local explicite/);
});

test("hourly agenda covers the complete day and updates one lane slot", () => {
  const date = new Date(2026, 6, 28, 21, 15, 0);
  const lanes = [{
    id: "gpu-a",
    roles: ["code"],
    focusRotation: ["architecture", "code"]
  }];
  const agenda = createDailyAgenda(date, lanes, 60);
  assert.equal(agenda.partitions.length, 24);
  const partition = getPartition(date, 60);
  assert.equal(partition.id, "2026-07-28-P21");
  updateAgenda(agenda, partition.id, "gpu-a", date, true);
  const slot = agenda.partitions[21].lanes[0];
  assert.equal(slot.status, "ACTIVE");
  assert.equal(slot.packagesProduced, 1);
  updateAgenda(agenda, partition.id, "gpu-a", date, true, 20);
  assert.equal(slot.packagesProduced, 20);
});

test("thermal guard requires cooling hysteresis and checks RAM and disk", () => {
  const guard = {
    maximumTemperatureCelsius: 78,
    resumeBelowCelsius: 72,
    minimumFreeRamGb: 4,
    minimumFreeRamGbWhenModelResident: 1,
    minimumFreeDiskGb: 12
  };
  const gpu = { temperatureCelsius: 78 };
  assert.deepEqual(resourceDecision({ gpu, freeRamGb: 8, freeDiskGb: 20, guard }), {
    ready: false,
    reason: "THERMAL_LIMIT",
    cooling: true
  });
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 73 }, freeRamGb: 8, freeDiskGb: 20, guard, cooling: true }).reason, "THERMAL_COOLDOWN");
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 71 }, freeRamGb: 8, freeDiskGb: 20, guard, cooling: true }).ready, true);
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 60 }, freeRamGb: 3, freeDiskGb: 20, guard }).reason, "LOW_RAM");
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 60 }, freeRamGb: 1.2, freeDiskGb: 20, guard, modelResident: true }).ready, true);
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 60 }, freeRamGb: 0.9, freeDiskGb: 20, guard, modelResident: true }).reason, "LOW_RAM");
  assert.equal(resourceDecision({ gpu: { temperatureCelsius: 60 }, freeRamGb: 8, freeDiskGb: 11, guard }).reason, "LOW_DISK");
  assert.equal(shouldAbortGeneration({ temperatureCelsius: 77 }, guard), false);
  assert.equal(shouldAbortGeneration({ temperatureCelsius: 78 }, guard), true);
  const lane = { model: "14b", fallbackModel: "7b" };
  assert.equal(shouldUseFallback(Object.assign(new Error("chaud"), { code: "THERMAL_LIMIT" }), lane), false);
  assert.equal(shouldUseFallback(new Error("modèle indisponible"), lane), true);
});

test("resident-model relief requires the exact configured model with real VRAM", () => {
  const payload = { models: [
    { model: "qwen2.5-coder:14b", size_vram: 8984691997 },
    { model: "other:7b", size_vram: 0 }
  ] };
  assert.equal(isExpectedModelResident(payload, "qwen2.5-coder:14b"), true);
  assert.equal(isExpectedModelResident(payload, "other:7b"), false);
  assert.equal(isExpectedModelResident(payload, "missing:latest"), false);
});

test("NVIDIA rows, backlog and secrets are normalized deterministically", () => {
  const rows = parseNvidiaCsv("GPU-one, 55, 92, 6000, 8192\nGPU-two, 60, 10, 5000, 12288\n");
  assert.equal(rows[0].uuid, "GPU-one");
  assert.equal(rows[1].memoryTotalMb, 12288);
  const candidates = extractBacklogCandidates([
    {
      path: "TASK.md",
      content: "# TASK.md — Tâche active\n## Objectif\nID: TASK-AUTONOMY-0001\nP0 améliorer les tests locaux\nCe fichier convertit PLAN en tâches vérifiables\n\"next\": \"TSK-P1-019 — Diagnostiquer Ollama\"\n\"path\": \"C:\\\\Users\\\\the-owner\\\\Documents\\\\AIONE\"\ntexte banal"
    }
  ]);
  assert.equal(candidates[0].text, "P0 améliorer les tests locaux");
  assert.equal(candidates.some((item) => item.text.startsWith("\"path\"")), false);
  assert.equal(candidates.some((item) => item.text.startsWith("ID:")), false);
  assert.equal(candidates.some((item) => item.text.startsWith("Ce fichier")), false);
  assert.ok(candidates.some((item) => item.text === "TSK-P1-019 — Diagnostiquer Ollama"));
  assert.match(sanitizeText("api_key=12345 authorization: Bearer abc"), /\[REDACTED\]/);
  assert.doesNotMatch(sanitizeText("api_key=12345"), /12345/);
});

test("candidate selection can exceed the legacy 80 item window without changing its default", () => {
  const source = {
    path: "S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\generated-backlog.md",
    content: Array.from({ length: 140 }, (_, index) => `- P0 TASK-AUTOGEN-${index} — améliorer robustesse et sécurité avec test ${index}.`).join("\n")
  };
  assert.equal(extractBacklogCandidates([source]).length, 80);
  assert.equal(extractBacklogCandidates([source], 320).length, 140);
});

test("current task context outranks a historical ABSOLUTE marker and always yields to the real queue", () => {
  const { policy } = readContextAuthorityPolicy();
  const authorityResolution = buildPolicyContextResolution(policy);
  const candidates = extractBacklogCandidates([
    { path: "TASK.md", content: "- P0 CURRENT-OWNER-CONTEXT améliorer le planning actuel avec tests." },
    {
      path: "S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\generated-backlog.md",
      content: "- P0 TASK-AUTOGEN-999 — ABSOLUTE-PROMPT-1-CORE construire le moteur cognitif avec tests."
    }
  ], 80, authorityResolution);
  assert.match(candidates[0].text, /CURRENT-OWNER-CONTEXT/u);
  const historical = candidates.find((item) => isAbsolutePriorityWorkItem(item));
  assert.equal(historical.sourceKind, "INHERITED_ARTIFACT");
  assert.equal(shouldYieldForPriorityQueue(historical, { shouldYield: true }), true);
  assert.equal(shouldYieldForPriorityQueue(candidates[0], { shouldYield: true }), true);
});

test("historical prompt generation excludes peer output and applies contextual authority once", () => {
  const workItem = {
    source: "generated-backlog.md",
    text: "P0 ABSOLUTE-PROMPT-1-COGNITION implémenter la boucle cognitive bornée"
  };
  const prompt = buildPrompt({
    lane: { label: "lane test", roles: ["architecture"], maximumOutputTokens: 900 },
    partition: { id: "P01", start: "00:00", end: "01:00" },
    focus: "architecture",
    workItem,
    sources: [],
    peerArtifact: "ANCIEN DOSSIER OWNER À RECOPIER",
    packageId: "W000001",
    reflectiveAutonomy: JSON.parse(readFileSync(join(process.cwd(), "config", "reflective-autonomy.json"), "utf8")),
    authorityResolution: buildPolicyContextResolution(readContextAuthorityPolicy().policy)
  });
  assert.equal(prompt.includes("ANCIEN DOSSIER OWNER À RECOPIER"), false);
  assert.equal(prompt.includes("CONTRAT ABSOLU ACTIF À TRAITER"), false);
  assert.equal(prompt.includes("AUTORITÉ CONTEXTUELLE ACTIVE"), true);
  assert.match(prompt, /base historique contextuellement révisable/u);
  assert.equal(prompt.includes("AUTONOMIE RÉFLEXIVE ACTIVE"), true);
  assert.equal(prompt.split(workItem.text).length - 1, 1);
  assert.ok(prompt.indexOf("## Contrat de mutation isolée") < prompt.indexOf("## Code ou patch proposé"));
  assert.match(prompt, /petit prototype exécutable autonome/u);
  assert.match(prompt, /RAPPEL FINAL NON NÉGOCIABLE/u);
});

test("detailed generated contracts remain visible without widening ordinary source lines", () => {
  const detailed = `P0 TASK-AUTOGEN-LONG — améliorer et tester la robustesse locale ${"avec preuves bornées ".repeat(20)}`.trim();
  assert.ok(detailed.length > 300 && detailed.length < 900);
  assert.equal(extractBacklogCandidates([{
    path: "S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\generated-backlog.md",
    content: detailed
  }]).length, 1);
  assert.equal(extractBacklogCandidates([{ path: "TASK.md", content: detailed }]).length, 0);
});

test("continuous lanes yield to the local Forge priority queue and ignore outages", async () => {
  const config = {
    enabled: true,
    endpoint: "http://127.0.0.1:4310/api/blockers/live",
    yieldForStates: ["QUEUED", "EXECUTING"]
  };
  const queued = await inspectForgePriorityQueue(config, async () => ({
    ok: true,
    json: async () => ({ blockers: { pipelines: [{ queueTaskId: "TASK-P0", status: "QUEUED" }, { queueTaskId: "OLD", status: "BLOCKED" }] } })
  }));
  assert.equal(queued.shouldYield, true);
  assert.deepEqual(queued.queueTaskIds, ["TASK-P0"]);
  const outage = await inspectForgePriorityQueue(config, async () => { throw new Error("offline"); });
  assert.equal(outage.shouldYield, false);
  assert.equal(outage.reason, "PRIORITY_PROBE_DEFERRED");
});

test("output structure reports every missing section honestly", () => {
  const incomplete = assessOutputStructure("# Résultat\n## Documentation\nTexte");
  assert.equal(incomplete.complete, false);
  assert.ok(incomplete.missingSections.includes("## Tests, validation et vérification"));
  const complete = assessOutputStructure([
    "## Compréhension et contexte objectif utilisateur",
    "## Contexte subjectif machine et hypothèses",
    "## Possibilités distinguées",
    "## Amélioration sélectionnée et justification",
    "## Architecture ou structure",
    "## Code ou patch proposé",
    "## Contrat de mutation isolée",
    "## Documentation",
    "## Diagnostic et corrections",
    "## Tests, validation et vérification",
    "## Risques, limites et prochaine tâche"
  ].join("\n"));
  assert.equal(complete.complete, true);
  const reconstructed = completeOutputStructure("# Résultat\n## Documentation\nTexte", { text: "corriger le test" });
  assert.equal(reconstructed.structure.complete, true);
  assert.equal(reconstructed.completedByOrchestrator, true);
  assert.ok(reconstructed.originalMissingSections.includes("## Tests, validation et vérification"));
  assert.ok(reconstructed.originalMissingSections.includes("## Contrat de mutation isolée"));
  assert.match(reconstructed.output, /NON EXÉCUTÉ/);
});

test("atomic JSON never leaves a partial destination", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-continuous-dev-"));
  try {
    const path = join(root, "state", "value.json");
    atomicJson(path, { ok: true, count: 2 });
    assert.deepEqual(JSON.parse(readFileSync(path, "utf8")), { ok: true, count: 2 });
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("two lanes cannot overwrite each other's agenda update", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-agenda-lock-"));
  try {
    const path = join(root, "agenda.json");
    await Promise.all(Array.from({ length: 20 }, () => mutateAgenda(
      path,
      () => ({ count: 0 }),
      (agenda) => {
        agenda.count += 1;
      }
    )));
    assert.equal(JSON.parse(readFileSync(path, "utf8")).count, 20);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("work items are not repeated until their source revision changes", () => {
  const firstRevision = contentRevision("version 1");
  const changedRevision = contentRevision("version 2");
  const first = { source: "TASK.md", text: "P0 corriger le test", sourceRevision: firstRevision };
  const changed = { ...first, sourceRevision: changedRevision };
  const focus = "code";
  const history = {
    entries: {
      [workItemKey(first, focus)]: { completedAt: "2026-07-29T00:00:00.000Z" }
    }
  };
  assert.equal(chooseNovelWorkItem([first], history, 0, focus), null);
  assert.deepEqual(chooseNovelWorkItem([changed], history, 0, focus), changed);
  const p0 = { source: "PRIORITY.md", text: "P0 sécurité", sourceRevision: firstRevision };
  const p3 = { source: "PRIORITY.md", text: "P3 polish", sourceRevision: firstRevision };
  assert.deepEqual(chooseNovelWorkItem([p0, p3], { entries: {} }, 999, focus), p0);
  assert.deepEqual(chooseNovelWorkItem([p0, p3], { entries: {} }, 999, focus, new Set([p0.text])), p3);
  assert.deepEqual(chooseNovelWorkItem([p0, p3], { entries: {} }, 999, focus, new Set(), 1), p3);
});

test("historical prompt wording no longer grants an internal scoring bonus", () => {
  const candidates = extractBacklogCandidates([{
    path: "S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\generated-backlog.md",
    content: [
      "- P0 TASK-AUTOGEN-001 — ABSOLUTE-PROMPT-1-FOUNDATION construire les schémas et tests.",
      "- P0 TASK-AUTOGEN-002 — ABSOLUTE-PROMPT-1-REFLECTION autonomie réflexive et plasticité self-directed avec tests.",
      "- P0 TASK-AUTOGEN-003 — ABSOLUTE-PROMPT-4-INTERFACE-GATEKEEPER vérifier les portes dans `forge-control/autonomy/absolute-priority-program.mjs`."
    ].join("\n")
  }]);
  assert.equal(candidates.every((entry) => entry.sourceKind === "INHERITED_ARTIFACT"), true);
  assert.match(candidates[0].text, /FOUNDATION/);
  assert.match(candidates[1].text, /REFLECTION/);
  assert.match(candidates.at(-1).text, /INTERFACE-GATEKEEPER/);
});

test("explicit project paths in generated tasks become bounded prompt sources", () => {
  assert.deepEqual(
    extractReferencedProjectPaths("Corriger `forge-control/autonomy/isolated-implementation.mjs` puis `docs/forge/RUNBOOK.md`."),
    ["forge-control/autonomy/isolated-implementation.mjs", "docs/forge/RUNBOOK.md"]
  );
  assert.deepEqual(
    extractReferencedProjectPaths("Implémenter `aione_cognitive_engine/core/cognitive_loop.py`."),
    ["aione_cognitive_engine/core/cognitive_loop.py"]
  );
  assert.deepEqual(extractReferencedProjectPaths("Ne pas lire `C:\\secret.txt`."), []);
});

test("implementation sources outrank policy and documentation paths in model context", () => {
  assert.deepEqual(extractReferencedProjectPaths([
    "`docs/prompts/source.md`",
    "`config/reflective-autonomy.json`",
    "`aione_cognitive_engine/core/reflective-engine.mjs`",
    "`aione_cognitive_engine/tests/reflective-engine.test.mjs`"
  ].join(" ")).slice(0, 4), [
    "aione_cognitive_engine/core/reflective-engine.mjs",
    "aione_cognitive_engine/tests/reflective-engine.test.mjs",
    "config/reflective-autonomy.json",
    "docs/prompts/source.md"
  ]);
});
