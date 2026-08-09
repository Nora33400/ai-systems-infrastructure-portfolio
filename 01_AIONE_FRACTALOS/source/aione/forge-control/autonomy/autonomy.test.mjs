import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { FractalMemory } from "./memory.mjs";
import { LocalAutonomyRuntime } from "./runtime.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function fixedClock() {
  return new Date("2026-07-26T12:00:00.000Z");
}

function testConfig(root) {
  return {
    schema: "aione.forge-autonomy.v1",
    mode: "LOCAL_AUTONOMY_GUARDED",
    workspace: root,
    stateDir: join(root, "state"),
    schedule: {
      cycleMinutes: 15,
      horizonHours: 24,
      maxActionsPerCycle: 1,
      quietHours: { start: 23, end: 7 },
      dailyPlanningHour: 8,
      dailyPlanningEnabled: false
    },
    continuous: {
      enabled: true,
      neverIdle: {
        enabled: true,
        rotation: [
          {type: "health-audit", quietSafe: true},
          {type: "context-audit", quietSafe: true},
          {type: "memory-compact", quietSafe: true}
        ]
      },
      history: {maximumQueueEntries: 500, maximumEvents: 200}
    },
    resources: {
      minimumFreeRamGbForAgent: 0,
      minimumFreeDiskGb: 0,
      maximumConcurrentModels: 1
    },
    projects: [{
      id: "aione",
      name: "AIONE",
      path: root,
      enabled: true,
      validationCommands: [{ command: "fake-test", args: [], timeoutMs: 1000 }]
    }],
    models: {
      fast: "qwen2.5-coder:7b",
      balanced: "qwen2.5-coder:14b",
      deep: "qwen3-coder:30b"
    },
    services: [{
      id: "fake-health",
      label: "Fake health",
      kind: "http",
      url: "http://127.0.0.1/fake",
      critical: true,
      timeoutMs: 1000
    }],
    approvals: {
      standingLocalApproval: ["health-audit", "plan", "memory-compact", "test-existing-command"],
      alwaysRequireHuman: ["delete", "git-write", "dependency-install", "mail-send", "external-publication"],
      externalActionsDefault: "deny"
    },
    guardian: {
      maximumLocalRepairAttempts: 2,
      repairCooldownMinutes: 30,
      maximumCodexInvocationsPerIncident: 1,
      codex: {
        enabled: false,
        requiredEnvironmentFlag: "AIONE_CODEX_RECOVERY",
        sandbox: "workspace-write",
        ephemeral: true
      }
    }
  };
}

function prepareAgents(root) {
  const directory = join(root, ".opencode", "agents");
  mkdirSync(directory, { recursive: true });
  for (const id of [
    "aione-autonomous-forge",
    "aione-orchestrator",
    "aione-ingestor",
    "aione-structurator",
    "aione-architect",
    "aione-creative",
    "aione-planner",
    "aione-publisher",
    "aione-auditor"
  ]) {
    const mode = id === "aione-autonomous-forge" ? "primary" : "subagent";
    writeFileSync(join(directory, `${id}.md`), `---\nmode: ${mode}\n---\n# ${id}\n`, "utf8");
  }
}

test("fractal memory compacts atom -> tile -> kilo-tile -> mega-tile and audits checksums", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-memory-test-"));
  try {
    const memory = new FractalMemory({ rootDir: root, clock: fixedClock });
    for (let group = 0; group < 4; group += 1) {
      memory.captureAtom("test", { group, item: 1 });
      memory.captureAtom("test", { group, item: 2 });
      memory.compact({ atomsPerTile: 2, tilesPerKilo: 2, kilosPerMega: 2 });
    }
    const audit = memory.audit();
    assert.equal(audit.ok, true);
    assert.equal(audit.counts.atoms, 8);
    assert.equal(audit.counts.tiles, 4);
    assert.equal(audit.counts.kiloTiles, 2);
    assert.equal(audit.counts.megaTiles, 1);
    assert.equal(audit.counts.gigaTiles, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("fractal memory compacts through gigatile without losing reconstructable sources", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-memory-giga-test-"));
  try {
    const memory = new FractalMemory({ rootDir: root, clock: fixedClock });
    for (let group = 0; group < 8; group += 1) {
      memory.captureAtom("test", { group, item: 1 });
      memory.captureAtom("test", { group, item: 2 });
      memory.compact({ atomsPerTile: 2, tilesPerKilo: 2, kilosPerMega: 2, megasPerGiga: 2 });
    }
    const audit = memory.audit();
    assert.equal(audit.ok, true);
    assert.deepEqual(audit.counts, {
      atoms: 16,
      tiles: 8,
      kiloTiles: 4,
      megaTiles: 2,
      gigaTiles: 1
    });
    const index = memory.readIndex();
    const giga = JSON.parse(readFileSync(join(root, "giga-tiles", `${index.gigaTiles[0].id}.json`), "utf8"));
    assert.equal(giga.schema, "aione.memory-giga-tile.v1");
    assert.equal(giga.sourceIds.length, 2);
    assert.ok(giga.checksum);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("runtime audits agents, protects sensitive tasks, and completes an allowlisted cycle", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-autonomy-test-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    const commandRunner = async (command) => ({ stdout: command === "fake-test" ? "tests ok" : "tool ok", stderr: "" });
    const fetchImpl = async () => new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl,
      commandRunner
    });

    const audit = await runtime.audit();
    assert.equal(audit.ok, true);
    assert.equal(audit.agentRegistry.missing.length, 0);

    const blocked = runtime.enqueue({
      type: "plan",
      title: "Action sensible",
      payload: { capabilities: ["dependency-install"] }
    });
    assert.equal(blocked.status, "AWAITING_HUMAN_APPROVAL");

    const allowed = runtime.enqueue({ type: "health-audit", title: "Audit local" });
    assert.equal(allowed.status, "QUEUED");
    const cycle = await runtime.runCycle();
    assert.equal(cycle.ok, true);
    assert.equal(cycle.taskResult.status, "COMPLETED");
    assert.equal(cycle.backup.ok, true);
    const backupAudit = runtime.verifyBackup(cycle.backup.backupRoot);
    assert.equal(backupAudit.ok, true);
    const restore = runtime.testRestore(cycle.backup.backupRoot);
    assert.equal(restore.ok, true);
    assert.equal(restore.liveStateUntouched, true);
    assert.equal(runtime.status().queueDepth, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a failed optional service remains visible without blocking safe local work", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-optional-service-"));
  try {
    prepareAgents(root);
    const config = testConfig(root);
    config.services[0].critical = false;
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(config, null, 2), "utf8");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl: async () => {
        throw new Error("optional service offline");
      },
      commandRunner: async () => ({stdout: "ok", stderr: ""})
    });

    const cycle = await runtime.runCycle();

    assert.equal(cycle.ok, true);
    assert.equal(cycle.audit.ok, true);
    assert.equal(cycle.audit.services[0].ok, false);
    assert.equal(cycle.taskResult.ran, true);
    assert.equal(cycle.taskResult.status, "COMPLETED");
    assert.equal(cycle.incidents[0].critical, false);
    assert.equal(cycle.incidents[0].status, "OPEN");
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("an existing incident follows the current service criticality", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-incident-criticality-"));
  try {
    prepareAgents(root);
    const config = testConfig(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(config, null, 2), "utf8");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl: async () => {
        throw new Error("service remains offline");
      },
      commandRunner: async () => ({stdout: "ok", stderr: ""})
    });

    const blocked = await runtime.runCycle({executeTasks: false});
    assert.equal(blocked.ok, false);
    assert.equal(blocked.incidents[0].critical, true);

    runtime.config.services[0].critical = false;
    const allowed = await runtime.runCycle();
    assert.equal(allowed.ok, true);
    assert.equal(allowed.incidents[0].critical, false);
    assert.equal(allowed.taskResult.status, "COMPLETED");
    assert.ok(runtime.readState().events.some((event) => (
      event.type === "incident-reclassified"
      && event.previousCritical === true
      && event.critical === false
    )));
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("a recurring failure reopens a previously resolved incident", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-incident-reopen-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    let healthy = false;
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl: async () => {
        if (!healthy) throw new Error("same recurring failure");
        return new Response(JSON.stringify({ok: true}), {
          status: 200,
          headers: {"content-type": "application/json"}
        });
      },
      commandRunner: async () => ({stdout: "ok", stderr: ""})
    });

    await runtime.runCycle({executeTasks: false});
    let incident = Object.values(runtime.readState().incidents)[0];
    assert.equal(incident.status, "OPEN");
    assert.equal(incident.episodes, 1);

    healthy = true;
    await runtime.runCycle({executeTasks: false});
    incident = Object.values(runtime.readState().incidents)[0];
    assert.equal(incident.status, "RESOLVED");

    healthy = false;
    await runtime.runCycle({executeTasks: false});
    const state = runtime.readState();
    incident = Object.values(state.incidents)[0];
    assert.equal(incident.status, "OPEN");
    assert.equal(incident.episodes, 2);
    assert.ok(state.events.some((event) => event.type === "incident-reopened"));
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("healthy resources resolve prior pressure incidents and invalid legacy council tasks are cancelled", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-state-reconciliation-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl: async () => new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      }),
      commandRunner: async () => ({ stdout: "ok", stderr: "" })
    });
    const state = runtime.readState();
    state.queue.push({
      id: "legacy-council-task",
      type: "council-meeting",
      status: "AWAITING_HUMAN_REVIEW",
      attempts: 2,
      payload: {},
      error: "Réunion inconnue: undefined"
    });
    state.approvalsRequired.push({
      taskId: "legacy-council-task",
      capabilities: ["local-task-recovery"],
      reason: "Réunion inconnue: undefined"
    });
    runtime.writeState(state);

    const incident = await runtime.handleFailure({
      id: "resources",
      label: "Ressources système",
      critical: true,
      error: "low-ram-sample-a"
    }, "cycle-pressure");
    assert.equal(incident.status, "OPEN");
    const resolved = runtime.resolveHealthyIncidents([{ id: "resources" }], "cycle-healthy");
    assert.equal(resolved.length, 1);

    const reconciled = runtime.readState();
    assert.equal(reconciled.queue.find((task) => task.id === "legacy-council-task").status, "CANCELLED");
    assert.equal(reconciled.approvalsRequired.length, 0);
    assert.equal(Object.values(reconciled.incidents).find((item) => item.id === incident.id).status, "RESOLVED");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("orchestrator consumes dual-GPU backlog requests and creates a bounded non-canonical refill", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-backlog-refill-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    const configDir = join(root, "config");
    mkdirSync(configDir, { recursive: true });
    const dualRuntime = join(root, "dual-runtime");
    mkdirSync(join(dualRuntime, "requests"), { recursive: true });
    writeFileSync(join(configDir, "dual-gpu-development.json"), JSON.stringify({
      schema: "aione.dual-gpu-development.v1",
      enabled: true,
      runtimeDir: dualRuntime
    }, null, 2), "utf8");
    writeFileSync(join(configDir, "fractalos-hard-development.json"), JSON.stringify({
      schema: "aione.fractalos-hard-development.v1",
      enabled: true,
      cycle: { workstreamsPerGeneration: 1 },
      workstreams: [{
        id: "P0-FRACTALOS-RUNTIME-CORE",
        priority: "P0",
        status: "ACTIVE",
        objective: "construire le cœur FractalOS hébergé et non destructif",
        targetFiles: ["fractal_dev_runtime"],
        acceptance: ["crash-recovery", "no-canonical-mutation"]
      }]
    }, null, 2), "utf8");
    writeFileSync(join(configDir, "absolute-priority-program.json"), JSON.stringify({
      schema: "aione.absolute-priority-program.v1",
      enabled: true,
      mode: "CONTINUOUS_24_7_DUAL_GPU_ABSOLUTE_P0",
      priorityPolicy: { maximumWorkstreamsPerGeneration: 1 },
      prompts: Array.from({ length: 4 }, (_, index) => ({
        id: `PROMPT_${index + 1}`,
        name: `Prompt ${index + 1}`,
        source: `docs/prompts/prompt-${index + 1}.md`,
        status: "ACTIVE",
        functionalGate: "NOT_VERIFIED",
        workstreams: index === 0 ? [{
          id: "ABSOLUTE-PROMPT-1-CORE",
          priority: "P0",
          status: "ACTIVE",
          objective: "construire le cœur cognitif testable",
          targetFiles: ["forge-control/autonomy"],
          acceptance: ["real-test"]
        }] : []
      })),
      functionalGates: Array.from({ length: 4 }, (_, index) => ({
        id: `PROMPT_${index + 1}_FUNCTIONAL`,
        status: "NOT_VERIFIED",
        requires: ["real-test"]
      })),
      interfaceActivation: { targets: ["OPENWEBUI", "LOBEHUB"] }
    }, null, 2), "utf8");
    writeFileSync(join(dualRuntime, "requests", "request-backlog-refresh.json"), JSON.stringify({
      schema: "aione.backlog-refresh-request.v1",
      laneId: "gpu-test",
      partition: { id: "2026-07-29-P17" },
      focus: "security",
      createdAt: fixedClock().toISOString()
    }, null, 2), "utf8");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock
    });

    const result = runtime.runBacklogRefill();
    assert.equal(result.status, "GENERATED");
    assert.equal(result.generatedTasks, 68);
    assert.equal(result.canonicalMutation, false);
    assert.equal(existsSync(result.outputPath), true);
    const generated = readFileSync(result.outputPath, "utf8");
    assert.match(generated, /TASK-AUTOGEN-/);
    assert.match(generated, /Mutation canonique autorisée: NON/);
    assert.match(generated, /identités HUMAN et AI/);
    assert.match(generated, /validation Owner/);
    assert.match(generated, /P0-FRACTALOS-RUNTIME-CORE/);
    assert.match(generated, /Lots FractalOS 24\/7: 1/);
    assert.match(generated, /ABSOLUTE-PROMPT-1-CORE/);
    assert.match(generated, /Bases historiques 4 prompts: 1/);
    assert.match(generated, /Interfaces OpenWebUI\/LobeHub: BLOCKED_BY_FUNCTIONAL_GATES/);
    assert.equal(runtime.runBacklogRefill().status, "ALREADY_GENERATED");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("an orphaned cycle lock is recovered while a live lock remains exclusive", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-autonomy-lock-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    const stateDir = join(root, "runtime");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir,
      clock: fixedClock,
      fetchImpl: async () => new Response(JSON.stringify({ok: true}), {
        status: 200,
        headers: {"content-type": "application/json"}
      }),
      commandRunner: async () => ({stdout: "ok", stderr: ""})
    });

    const liveLock = runtime.acquireCycleLock();
    assert.equal(liveLock.ok, true);
    const concurrentRuntime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir,
      clock: fixedClock,
      fetchImpl: runtime.fetchImpl,
      commandRunner: runtime.commandRunner
    });
    const blocked = await concurrentRuntime.runCycle({executeTasks: false});
    assert.equal(blocked.status, "ALREADY_RUNNING");
    runtime.releaseCycleLock(liveLock);

    const lockPath = join(stateDir, "locks", "cycle.lock");
    writeFileSync(lockPath, JSON.stringify({
      pid: 2147483647,
      createdAt: fixedClock().toISOString()
    }), "utf8");
    const recovered = await concurrentRuntime.runCycle({executeTasks: false});
    assert.equal(recovered.ok, true);
    assert.equal(recovered.lockRecovery.reason, "owner-process-not-running");
    assert.equal(recovered.lockRecovery.previousPid, 2147483647);
    assert.equal(existsSync(lockPath), false);
    assert.ok(concurrentRuntime.readState().events.some((event) => event.type === "orphan-cycle-lock-recovered"));
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("editorial sync creates an idempotent redacted local-only publication package", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-editorial-sync-"));
  try {
    prepareAgents(root);
    const config = testConfig(root);
    config.continuous.neverIdle.rotation = [{
      type: "editorial-sync",
      quietSafe: true,
      minimumIntervalMinutes: 1440
    }];
    config.approvals.standingLocalApproval.push("editorial-sync");
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(config, null, 2), "utf8");
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: fixedClock,
      fetchImpl: async () => {
        throw new Error("editorial sync must not use the network");
      },
      commandRunner: async () => {
        throw new Error("editorial sync must not execute commands");
      }
    });
    const state = runtime.readState();
    state.lastCycle = {
      id: "cycle-editorial-test",
      status: "OK",
      completedAt: fixedClock().toISOString()
    };
    state.incidents["incident-editorial-test"] = {
      id: "incident-editorial-test",
      serviceId: "optional-service",
      label: "Optional service",
      critical: false,
      status: "OPEN",
      occurrences: 1,
      lastSeenAt: fixedClock().toISOString(),
      error: "Authorization: Bearer secret-token token=another-secret"
    };
    runtime.writeState(state);

    const task = runtime.ensureMaintenanceTask();
    assert.equal(task.type, "editorial-sync");
    const firstRun = await runtime.runNextSafeTask();
    assert.equal(firstRun.status, "COMPLETED");
    assert.equal(firstRun.result.status, "DRAFT_LOCAL_ONLY");
    assert.equal(firstRun.result.published, false);
    assert.equal(firstRun.result.networkUsed, false);
    assert.equal(runtime.ensureMaintenanceTask(), null);

    const expectedFiles = [
      "PROJECT_STATUS.md",
      "DEVLOG.md",
      "DEVBLOG_DRAFT.md",
      "FORUM_DRAFT.md",
      "site/index.html",
      "PUBLICATION_MANIFEST.json"
    ];
    const readPackage = () => Object.fromEntries(expectedFiles.map((relativePath) => {
      const path = join(firstRun.result.outputDir, ...relativePath.split("/"));
      assert.equal(existsSync(path), true);
      return [relativePath, readFileSync(path, "utf8")];
    }));
    const stableFirstRun = runtime.runEditorialSync();
    const firstPackage = readPackage();
    const secondRun = runtime.runEditorialSync();
    assert.equal(secondRun.snapshotSha256, stableFirstRun.snapshotSha256);
    const secondPackage = readPackage();
    assert.deepEqual(secondPackage, firstPackage);
    const allContent = Object.values(secondPackage).join("\n");
    assert.equal(allContent.includes("secret-token"), false);
    assert.equal(allContent.includes("another-secret"), false);
    assert.match(allContent, /\[REDACTED\]/);
    const manifest = JSON.parse(secondPackage["PUBLICATION_MANIFEST.json"]);
    assert.equal(manifest.status, "DRAFT_LOCAL_ONLY");
    assert.equal(manifest.published, false);
    assert.equal(manifest.networkUsed, false);
    assert.equal(manifest.humanValidationRequired, true);
    assert.ok(manifest.provenance.length >= 3);
    assert.equal(readdirSync(firstRun.result.outputDir).some((name) => name.endsWith(".tmp")), false);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("continuous autonomy simulates more than 24 hours without idle or queue growth", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-autonomy-soak-"));
  try {
    prepareAgents(root);
    const config = testConfig(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(config, null, 2), "utf8");
    let now = new Date(2026, 6, 26, 0, 0, 0, 0);
    const commandRunner = async () => ({stdout: "ok", stderr: ""});
    const fetchImpl = async () => new Response(JSON.stringify({ok: true}), {
      status: 200,
      headers: {"content-type": "application/json"}
    });
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: () => now,
      fetchImpl,
      commandRunner
    });

    for (let cycle = 0; cycle < 100; cycle += 1) {
      const result = await runtime.runCycle();
      assert.equal(result.ok, true);
      assert.equal(result.taskResult.ran, true);
      assert.equal(result.taskResult.status, "COMPLETED");
      now = new Date(now.getTime() + 15 * 60000);
    }

    const status = runtime.status();
    assert.equal(status.metrics.cycles, 100);
    assert.equal(status.metrics.successfulCycles, 100);
    assert.equal(status.metrics.maintenanceCompleted, 100);
    assert.equal(status.queueDepth, 0);
    assert.ok(runtime.readState().queue.length <= 100);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("agent council relays a meeting then the 96-hour broker schedules a guarded DEV package", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-council-capacity-"));
  try {
    prepareAgents(root);
    const configPath = join(root, "forge-autonomy.json");
    writeFileSync(configPath, JSON.stringify(testConfig(root), null, 2), "utf8");
    const configDir = join(root, "config");
    mkdirSync(configDir, { recursive: true });
    writeFileSync(join(configDir, "agent-council.json"), JSON.stringify({
      schema: "aione.agent-council.v1",
      enabled: true,
      outputDir: join(root, "council"),
      policy: {maximumContextCharactersPerUpstream: 1000},
      meetings: [{
        id: "council",
        name: "Conseil test",
        day: "MO",
        time: "08:30",
        model: "qwen2.5-coder:14b",
        role: "aione-orchestrator",
        purpose: "Distribuer un lot",
        inputs: ["PRIORITY.md"],
        outputs: ["lot"],
        recipients: ["development"]
      }],
      relay: []
    }, null, 2), "utf8");
    writeFileSync(join(configDir, "development-capacity.json"), JSON.stringify({
      schema: "aione.development-capacity.v1",
      enabled: true,
      weeklyTargetAgentHours: 96,
      measurement: {unit: "NOMINAL_AGENT_HOUR"},
      allocation: [{focus: "code", agentHours: 40}, {focus: "tests", agentHours: 16}],
      workPackages: {
        nominalHours: 2,
        minimumIntervalMinutes: 120,
        maximumPerDay: 8,
        oneAtATime: true,
        currentExecutionMode: "ANALYSIS_DIAGNOSTIC_TEST_AND_CODE_PREPARATION",
        isolatedCodeRunnerRequiredForFileMutation: true
      },
      backlogSources: ["PRIORITY.md"],
      antiEmptyQueue: ["test-gap-audit"],
      priorityProjects: ["aione"]
    }, null, 2), "utf8");
    const now = new Date(2026, 6, 27, 9, 0, 0, 0);
    const runtime = new LocalAutonomyRuntime({
      root,
      configPath,
      stateDir: join(root, "runtime"),
      clock: () => now,
      commandRunner: async () => ({stdout: "preuve locale et prochain lot", stderr: ""}),
      fetchImpl: async () => new Response(JSON.stringify({
        model: "qwen2.5-coder:7b",
        response: "preuve locale et prochain lot",
        total_duration: 1000,
        prompt_eval_count: 10,
        eval_count: 20
      }), {
        status: 200,
        headers: {"content-type": "application/json"}
      })
    });

    const councilTask = runtime.ensureCouncilTask({
      readiness: {allowed: true, reason: "LIGHT_RESOURCE_USE", gates: {userAbsent: false}, freeRamGb: 12}
    });
    assert.equal(councilTask.type, "council-meeting");
    assert.equal(councilTask.payload.selectedModel, "qwen2.5-coder:7b");
    assert.equal(runtime.ensureDevelopmentCapacityTask({readiness: {allowed: true}}), null);
    const councilResult = await runtime.runNextSafeTask();
    assert.equal(councilResult.status, "COMPLETED");
    assert.equal(runtime.status().council.completed, 1);

    const devTask = runtime.ensureDevelopmentCapacityTask({readiness: {allowed: true}});
    assert.equal(devTask.type, "development-work-package");
    const devResult = await runtime.runNextSafeTask();
    assert.equal(devResult.status, "COMPLETED");
    assert.equal(devResult.result.mutationPerformed, false);
    const capacity = runtime.developmentCapacityStatus();
    assert.equal(capacity.weeklyTargetAgentHours, 96);
    assert.equal(capacity.nominalAgentHoursCompleted, 2);
    assert.ok(capacity.actualWallClockMs >= 0);
    assert.equal(capacity.isolatedCodeRunnerRequiredForFileMutation, true);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
