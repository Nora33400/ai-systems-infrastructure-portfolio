import {
  existsSync,
  closeSync,
  copyFileSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  statfsSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { execFile, execFileSync, spawn } from "node:child_process";
import { promisify } from "node:util";
import { basename, dirname, join, resolve, sep } from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";
import { renameWithRetry } from "./atomic-file.mjs";
import { createHash, randomUUID } from "node:crypto";
import { FractalMemory, atomicJson, readJson } from "./memory.mjs";
import { buildAbsolutePriorityProgram } from "./absolute-priority-program.mjs";
import { buildPolicyContextResolution } from "./context-authority.mjs";

const execFileAsync = promisify(execFile);
const MODULE_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = resolve(MODULE_DIR, "..", "..");

function expandEnvironmentPath(value) {
  const expanded = String(value || "").replace(/%([^%]+)%/g, (_, name) => process.env[name] || `%${name}%`);
  return resolve(expanded);
}

function iso(clock) {
  return clock().toISOString();
}

function atomicText(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.${randomUUID().slice(0, 8)}.tmp`;
  writeFileSync(temporary, String(content), "utf8");
  renameWithRetry(temporary, path);
}

function redactEditorialText(value) {
  return String(value ?? "")
    .replace(/(authorization\s*:\s*bearer\s+)[^\s"'<>]+/gi, "$1[REDACTED]")
    .replace(/\b(api[_ -]?key|token|password|secret)\b\s*[:=]\s*([^\s,;]+)/gi, "$1=[REDACTED]");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function stableId(prefix, value) {
  return `${prefix}-${createHash("sha256").update(String(value)).digest("hex").slice(0, 12)}`;
}

function localDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function mondayWeekKey(date) {
  const monday = new Date(date);
  const day = monday.getDay();
  const distance = day === 0 ? -6 : 1 - day;
  monday.setDate(monday.getDate() + distance);
  return localDateKey(monday);
}

function minuteOfDay(value) {
  const [hour, minute] = String(value || "00:00").split(":").map(Number);
  return (Number.isFinite(hour) ? hour : 0) * 60 + (Number.isFinite(minute) ? minute : 0);
}

function readOptionalJson(path) {
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : null;
}

function executableCandidates(command) {
  if (process.platform !== "win32") return [command];
  if (existsSync(String(command))) return [String(command)];
  try {
    return execFileSync("where.exe", [command], { encoding: "utf8", windowsHide: true })
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .sort((left, right) => {
        const score = (path) => path.endsWith(".exe") ? 0 : path.endsWith(".ps1") ? 1 : path.endsWith(".cmd") ? 2 : 3;
        return score(left.toLowerCase()) - score(right.toLowerCase());
      });
  } catch {
    return [command];
  }
}

function resolveNativeExecutable(command, candidate) {
  if (process.platform !== "win32") return candidate;
  if (String(command).toLowerCase() === "opencode") {
    const npmRoot = dirname(candidate);
    const native = join(npmRoot, "node_modules", "opencode-ai", "bin", "opencode.exe");
    if (existsSync(native)) return native;
  }
  return candidate;
}

function quoteCmdArgument(value) {
  const text = String(value);
  if (!/[\s"&|<>^()]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

async function defaultCommandRunner(command, args = [], options = {}) {
  const discovered = executableCandidates(command)[0] || command;
  const candidate = resolveNativeExecutable(command, discovered);
  const timeout = options.timeoutMs || 30000;
  const cwd = options.cwd || process.cwd();
  const common = { cwd, timeout, windowsHide: true, maxBuffer: 8 * 1024 * 1024, env: { ...process.env, ...(options.env || {}) } };
  if (process.platform === "win32" && candidate.toLowerCase().endsWith(".ps1")) {
    return execFileAsync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", candidate, ...args], common);
  }
  if (process.platform === "win32" && candidate.toLowerCase().endsWith(".cmd")) {
    const commandLine = [candidate, ...args].map(quoteCmdArgument).join(" ");
    return execFileAsync(process.env.ComSpec || "cmd.exe", ["/d", "/s", "/c", commandLine], common);
  }
  return execFileAsync(candidate, args, common);
}

async function fetchJson(url, timeoutMs, fetchImpl) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs || 10000);
  try {
    const response = await fetchImpl(url, { signal: controller.signal, cache: "no-store" });
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = text;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${String(text).slice(0, 300)}`);
    return body;
  } finally {
    clearTimeout(timer);
  }
}

function defaultState(clock) {
  return {
    schema: "aione.forge-autonomy-state.v1",
    mode: "LOCAL_AUTONOMY_GUARDED",
    paused: false,
    createdAt: iso(clock),
    updatedAt: iso(clock),
    lastCycle: null,
    nextCycle: null,
    lastDailyPlanDate: null,
    nextMaintenanceIndex: 0,
    maintenanceLastRun: {},
    lastCouncilRuns: {},
    backlogRefill: {
      lastRequestKey: null,
      lastGeneratedAt: null,
      outputPath: null,
      generatedTasks: 0
    },
    developmentCapacity: {
      weekKey: mondayWeekKey(clock()),
      nominalAgentHours: 0,
      actualWallClockMs: 0,
      packagesCompleted: 0,
      lastRunAt: null,
      dailyPackages: {}
    },
    events: [],
    incidents: {},
    queue: [],
    approvalsRequired: [],
    metrics: {
      cycles: 0,
      successfulCycles: 0,
      failedCycles: 0,
      tasksCompleted: 0,
      maintenanceCompleted: 0,
      councilMeetingsCompleted: 0,
      developmentWorkPackagesCompleted: 0,
      nominalDevelopmentAgentHours: 0,
      actualDevelopmentWallClockMs: 0,
      repairsAttempted: 0,
      codexInvocations: 0
    }
  };
}

export class LocalAutonomyRuntime {
  constructor({
    root = DEFAULT_ROOT,
    configPath = join(root, "config", "forge-autonomy.json"),
    stateDir,
    clock = () => new Date(),
    fetchImpl = globalThis.fetch,
    commandRunner = defaultCommandRunner
  } = {}) {
    this.root = resolve(root);
    this.configPath = resolve(configPath);
    this.clock = clock;
    this.fetchImpl = fetchImpl;
    this.commandRunner = commandRunner;
    this.config = JSON.parse(readFileSync(this.configPath, "utf8"));
    this.councilConfig = readOptionalJson(join(this.root, "config", "agent-council.json"));
    this.developmentCapacityConfig = readOptionalJson(join(this.root, "config", "development-capacity.json"));
    this.dualGpuConfig = readOptionalJson(join(this.root, "config", "dual-gpu-development.json"));
    this.developmentContinuityConfig = readOptionalJson(join(this.root, "config", "agentic-development-continuity.json"));
    this.fractalOsHardDevelopmentConfig = readOptionalJson(join(this.root, "config", "fractalos-hard-development.json"));
    this.contextAuthorityConfig = readOptionalJson(join(this.root, "config", "context-authority.json"));
    this.contextAuthorityResolution = this.contextAuthorityConfig
      ? buildPolicyContextResolution(this.contextAuthorityConfig)
      : null;
    this.absolutePriorityConfig = readOptionalJson(join(this.root, "config", "absolute-priority-program.json"));
    this.absolutePriorityProgram = buildAbsolutePriorityProgram(this.absolutePriorityConfig || {}, {
      authorityResolution: this.contextAuthorityResolution
    });
    this.stateDir = stateDir ? resolve(stateDir) : expandEnvironmentPath(this.config.stateDir);
    const configuredCouncilDir = this.councilConfig?.outputDir
      ? expandEnvironmentPath(this.councilConfig.outputDir)
      : join(this.stateDir, "council");
    this.paths = {
      state: join(this.stateDir, "state.json"),
      incidents: join(this.stateDir, "incidents"),
      reports: join(this.stateDir, "reports"),
      memory: join(this.stateDir, "memory"),
      locks: join(this.stateDir, "locks"),
      recovery: join(this.stateDir, "recovery"),
      backups: join(this.stateDir, "backups"),
      restoreTests: join(this.stateDir, "restore-tests"),
      council: configuredCouncilDir,
      editorial: this.config.editorial?.outputDir
        ? expandEnvironmentPath(this.config.editorial.outputDir)
        : join(this.stateDir, "editorial")
    };
    Object.values(this.paths).filter((path) => path !== this.paths.state).forEach((path) => mkdirSync(path, { recursive: true }));
    mkdirSync(this.stateDir, { recursive: true });
    if (!existsSync(this.paths.state)) atomicJson(this.paths.state, defaultState(this.clock));
    this.memory = new FractalMemory({ rootDir: this.paths.memory, clock: this.clock });
  }

  readState() {
    const defaults = defaultState(this.clock);
    const state = readJson(this.paths.state, defaults);
    state.metrics = { ...defaults.metrics, ...(state.metrics || {}) };
    state.nextMaintenanceIndex = Number(state.nextMaintenanceIndex || 0);
    state.maintenanceLastRun ||= {};
    state.lastCouncilRuns ||= {};
    state.backlogRefill = {
      ...defaults.backlogRefill,
      ...(state.backlogRefill || {})
    };
    state.developmentCapacity = {
      ...defaults.developmentCapacity,
      ...(state.developmentCapacity || {}),
      dailyPackages: { ...(state.developmentCapacity?.dailyPackages || {}) }
    };
    state.queue ||= [];
    state.events ||= [];
    state.incidents ||= {};
    state.approvalsRequired ||= [];
    const cancelledLegacyTaskIds = new Set();
    for (const task of state.queue) {
      const invalidLegacyCouncilTask = task.type === "council-meeting"
        && !task.payload?.meetingId
        && ["AWAITING_HUMAN_REVIEW", "QUEUED"].includes(task.status)
        && /Réunion inconnue: undefined/.test(String(task.error || ""));
      if (!invalidLegacyCouncilTask) continue;
      task.status = "CANCELLED";
      task.cancelledAt ||= iso(this.clock);
      task.cancellationReason = "INVALID_LEGACY_COUNCIL_TASK_WITHOUT_MEETING_ID";
      cancelledLegacyTaskIds.add(task.id);
    }
    const actionableApprovalTaskIds = new Set(
      state.queue
        .filter((task) => ["AWAITING_HUMAN_APPROVAL", "AWAITING_HUMAN_REVIEW"].includes(task.status))
        .map((task) => task.id)
    );
    state.approvalsRequired = state.approvalsRequired.filter((approval, index, approvals) => (
      !cancelledLegacyTaskIds.has(approval.taskId)
      && actionableApprovalTaskIds.has(approval.taskId)
      && approvals.findIndex((candidate) => candidate.taskId === approval.taskId) === index
    ));
    return state;
  }

  writeState(state) {
    state.updatedAt = iso(this.clock);
    state.events = (state.events || []).slice(-Number(this.config.continuous?.history?.maximumEvents || 200));
    const maximumQueueEntries = Number(this.config.continuous?.history?.maximumQueueEntries || 500);
    if ((state.queue || []).length > maximumQueueEntries) {
      const active = state.queue.filter((task) => !["COMPLETED", "CANCELLED"].includes(task.status));
      const completed = state.queue.filter((task) => ["COMPLETED", "CANCELLED"].includes(task.status));
      state.queue = [...active, ...completed.slice(-(Math.max(0, maximumQueueEntries - active.length)))];
    }
    atomicJson(this.paths.state, state);
  }

  status() {
    const state = this.readState();
    return {
      ok: !state.paused,
      mode: state.mode,
      paused: state.paused,
      lastCycle: state.lastCycle,
      nextCycle: state.nextCycle,
      queueDepth: state.queue.filter((task) => task.status === "QUEUED").length,
      openIncidents: Object.values(state.incidents).filter((incident) => incident.status !== "RESOLVED").length,
      approvalsRequired: state.approvalsRequired,
      metrics: state.metrics,
      stateDir: this.stateDir,
      memory: this.memory.audit(),
      activeTasks: state.queue
        .filter((task) => task.status === "RUNNING")
        .map((task) => ({
          id: task.id,
          type: task.type,
          title: task.title,
          projectId: task.projectId,
          startedAt: task.startedAt,
          model: task.payload?.selectedModel || null
        })),
      council: this.councilStatus(state),
      developmentCapacity: this.developmentCapacityStatus(state)
    };
  }

  readWorkspaceContext(relativePaths, { maximumTotalCharacters = 30000, maximumPerFileCharacters = 6000 } = {}) {
    const sections = [];
    let remaining = maximumTotalCharacters;
    for (const relativePath of relativePaths || []) {
      if (remaining <= 0 || typeof relativePath !== "string") break;
      const candidate = resolve(this.root, relativePath);
      const insideRoot = candidate === this.root || candidate.startsWith(`${this.root}${sep}`);
      if (!insideRoot || !existsSync(candidate) || !statSync(candidate).isFile()) continue;
      const content = readFileSync(candidate, "utf8").slice(0, Math.min(maximumPerFileCharacters, remaining));
      remaining -= content.length;
      sections.push(`## Source ${relativePath}\n${content}`);
    }
    return sections.join("\n\n");
  }

  async runLocalAgentPrompt({ model, prompt, timeoutMs = 20 * 60 * 1000, numPredict = 4096, format, signal }) {
    let routedModel = model;
    let endpoint = "http://127.0.0.1:11434";
    let contextLength = 16384;
    if (this.dualGpuConfig?.enabled === true) {
      let lane = this.dualGpuConfig.lanes.find((item) => item.model === routedModel);
      if (!lane && routedModel === this.config.models?.deep) {
        routedModel = this.config.models?.balanced || routedModel;
        lane = this.dualGpuConfig.lanes.find((item) => item.model === routedModel);
      }
      if (lane) {
        endpoint = String(lane.endpoint);
        contextLength = Number(lane.contextLength || 8192);
      }
    }
    const controller = new AbortController();
    const abortFromCaller = () => controller.abort(signal?.reason);
    if (signal?.aborted) abortFromCaller();
    else signal?.addEventListener?.("abort", abortFromCaller, { once: true });
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const startedAt = Date.now();
    try {
      const response = await this.fetchImpl(`${endpoint}/api/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          model: routedModel,
          prompt,
          stream: false,
          keep_alive: "10m",
          ...(format ? { format } : {}),
          options: {
            temperature: 0.2,
            num_ctx: contextLength,
            num_predict: Math.max(256, Math.min(8192, Number(numPredict) || 4096))
          }
        }),
        signal: controller.signal,
        cache: "no-store"
      });
      const text = await response.text();
      if (!response.ok) throw new Error(`Ollama HTTP ${response.status}: ${text.slice(0, 500)}`);
      const body = JSON.parse(text);
      const output = String(body.response || "").trim().slice(0, 240000);
      if (!output) throw new Error("Ollama n'a produit aucune réponse.");
      return {
        output,
        model: body.model || routedModel,
        actualWallClockMs: Date.now() - startedAt,
        totalDurationNs: Number(body.total_duration || 0),
        loadDurationNs: Number(body.load_duration || 0),
        promptEvalCount: Number(body.prompt_eval_count || 0),
        evalCount: Number(body.eval_count || 0)
      };
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener?.("abort", abortFromCaller);
    }
  }

  councilStatus(state = this.readState()) {
    return {
      enabled: Boolean(this.councilConfig?.enabled),
      meetingCount: this.councilConfig?.meetings?.length || 0,
      completed: state.metrics.councilMeetingsCompleted,
      lastRuns: state.lastCouncilRuns,
      outputDir: this.paths.council
    };
  }

  developmentCapacityStatus(state = this.readState()) {
    const config = this.developmentCapacityConfig;
    const weekKey = mondayWeekKey(this.clock());
    const current = state.developmentCapacity?.weekKey === weekKey
      ? state.developmentCapacity
      : {
          weekKey,
          nominalAgentHours: 0,
          actualWallClockMs: 0,
          packagesCompleted: 0,
          lastRunAt: null,
          dailyPackages: {}
        };
    const target = Number(config?.weeklyTargetAgentHours || 0);
    return {
      enabled: Boolean(config?.enabled),
      weekKey,
      unit: config?.measurement?.unit || "NOMINAL_AGENT_HOUR",
      weeklyTargetAgentHours: target,
      nominalAgentHoursCompleted: Number(current.nominalAgentHours || 0),
      nominalAgentHoursRemaining: Math.max(0, target - Number(current.nominalAgentHours || 0)),
      actualWallClockMs: Number(current.actualWallClockMs || 0),
      packagesCompleted: Number(current.packagesCompleted || 0),
      currentExecutionMode: config?.workPackages?.currentExecutionMode || null,
      isolatedCodeRunnerRequiredForFileMutation: Boolean(config?.workPackages?.isolatedCodeRunnerRequiredForFileMutation)
    };
  }

  listIncidents() {
    return readdirSync(this.paths.incidents)
      .filter((name) => name.endsWith(".json"))
      .sort()
      .reverse()
      .map((name) => readJson(join(this.paths.incidents, name), null))
      .filter(Boolean);
  }

  createBackup() {
    const stamp = this.clock().toISOString().replace(/[-:.TZ]/g, "");
    const backupRoot = join(this.paths.backups, `backup-${stamp}-${randomUUID().slice(0, 8)}`);
    mkdirSync(backupRoot, { recursive: true });
    const sources = [
      { source: this.paths.state, relative: "state.json" },
      { source: this.configPath, relative: "config/forge-autonomy.json" },
      { source: this.paths.memory, relative: "memory" },
      { source: this.paths.incidents, relative: "incidents" },
      { source: this.paths.reports, relative: "reports" },
      { source: this.paths.council, relative: "council" },
      { source: this.paths.editorial, relative: "editorial" },
      { source: join(dirname(this.stateDir), "ControlPlane"), relative: "control-plane" },
      { source: join(this.root, "AGENTS.md"), relative: "workspace/AGENTS.md" },
      { source: join(this.root, "AUTONOMY_STATE.md"), relative: "workspace/AUTONOMY_STATE.md" },
      { source: join(this.root, "AIONE_CODEX_AUTONOMY_RESULT.md"), relative: "workspace/AIONE_CODEX_AUTONOMY_RESULT.md" },
      { source: join(this.root, "AIONE_CONTROL_PLANE_INTEGRATION_RESULT.md"), relative: "workspace/AIONE_CONTROL_PLANE_INTEGRATION_RESULT.md" },
      { source: join(this.root, "package.json"), relative: "workspace/package.json" },
      { source: join(this.root, "opencode.json"), relative: "workspace/opencode.json" },
      { source: join(this.root, "config"), relative: "workspace/config" },
      { source: join(this.root, ".opencode", "agents"), relative: "workspace/.opencode/agents" },
      { source: join(this.root, "forge-control", "autonomy"), relative: "workspace/forge-control/autonomy" },
      { source: join(this.root, "forge-control", "server.mjs"), relative: "workspace/forge-control/server.mjs" },
      { source: join(this.root, "automation", "n8n"), relative: "workspace/automation/n8n" },
      { source: join(this.root, "docs", "forge"), relative: "workspace/docs/forge" },
      { source: join(this.root, "projects", "fractal-formula-corpus"), relative: "workspace/projects/fractal-formula-corpus" },
      { source: join(this.root, "scripts", "aione-automate.ps1"), relative: "workspace/scripts/aione-automate.ps1" },
      { source: join(this.root, "scripts", "build-aione-guarded.ps1"), relative: "workspace/scripts/build-aione-guarded.ps1" },
      { source: join(this.root, "scripts", "deliver-lobehub-morning-brief.ps1"), relative: "workspace/scripts/deliver-lobehub-morning-brief.ps1" },
      { source: join(this.root, "scripts", "ensure-lobehub-digital-life-agents.ps1"), relative: "workspace/scripts/ensure-lobehub-digital-life-agents.ps1" },
      { source: join(this.root, "scripts", "install-aione-secretary.ps1"), relative: "workspace/scripts/install-aione-secretary.ps1" },
      { source: join(this.root, "scripts", "install-forge-autonomy.ps1"), relative: "workspace/scripts/install-forge-autonomy.ps1" },
      { source: join(this.root, "scripts", "install-lobehub-cloud-gateway.ps1"), relative: "workspace/scripts/install-lobehub-cloud-gateway.ps1" },
      { source: join(this.root, "scripts", "install-lobehub-morning-brief.ps1"), relative: "workspace/scripts/install-lobehub-morning-brief.ps1" },
      { source: join(this.root, "scripts", "run-aione-secretary.ps1"), relative: "workspace/scripts/run-aione-secretary.ps1" },
      { source: join(this.root, "scripts", "run-forge-autonomy.ps1"), relative: "workspace/scripts/run-forge-autonomy.ps1" },
      { source: join(this.root, "scripts", "run-lobehub-cloud-gateway.ps1"), relative: "workspace/scripts/run-lobehub-cloud-gateway.ps1" },
      { source: join(this.root, "scripts", "show-aione-notification.ps1"), relative: "workspace/scripts/show-aione-notification.ps1" },
      { source: join(this.root, "scripts", "get-forge-readiness.ps1"), relative: "workspace/scripts/get-forge-readiness.ps1" },
      { source: join(this.root, "scripts", "sync-lobehub-aione-agents.ps1"), relative: "workspace/scripts/sync-lobehub-aione-agents.ps1" }
    ];
    const files = [];
    for (const item of sources) {
      this.copyBackupSource(item.source, join(backupRoot, item.relative), backupRoot, files);
    }
    const manifest = {
      schema: "aione.forge-autonomy-backup.v1",
      createdAt: iso(this.clock),
      workspace: this.root,
      sourceStateDir: this.stateDir,
      files
    };
    atomicJson(join(backupRoot, "manifest.json"), manifest);
    return { ok: true, backupRoot, fileCount: files.length, manifest };
  }

  copyBackupSource(source, target, backupRoot, files) {
    if (!existsSync(source)) return;
    const stats = statSync(source);
    if (stats.isDirectory()) {
      mkdirSync(target, { recursive: true });
      for (const name of readdirSync(source)) {
        this.copyBackupSource(join(source, name), join(target, name), backupRoot, files);
      }
      return;
    }
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(source, target);
    const content = readFileSync(target);
    files.push({
      path: target.slice(backupRoot.length + 1).replace(/\\/g, "/"),
      bytes: content.byteLength,
      sha256: createHash("sha256").update(content).digest("hex")
    });
  }

  verifyBackup(backupRoot) {
    const manifestPath = join(resolve(backupRoot), "manifest.json");
    const manifest = readJson(manifestPath, null);
    if (!manifest || manifest.schema !== "aione.forge-autonomy-backup.v1") {
      return { ok: false, backupRoot: resolve(backupRoot), issues: [{ code: "invalid-or-missing-manifest" }] };
    }
    const issues = [];
    for (const entry of manifest.files || []) {
      const path = join(resolve(backupRoot), entry.path);
      if (!existsSync(path)) {
        issues.push({ code: "missing-file", path: entry.path });
        continue;
      }
      const content = readFileSync(path);
      const checksum = createHash("sha256").update(content).digest("hex");
      if (checksum !== entry.sha256) issues.push({ code: "checksum-mismatch", path: entry.path });
    }
    return { ok: issues.length === 0, backupRoot: resolve(backupRoot), fileCount: manifest.files.length, issues };
  }

  testRestore(backupRoot) {
    const verification = this.verifyBackup(backupRoot);
    if (!verification.ok) return { ...verification, restored: false };
    const target = join(this.paths.restoreTests, `restore-${this.clock().toISOString().replace(/[-:.TZ]/g, "")}-${randomUUID().slice(0, 8)}`);
    mkdirSync(target, { recursive: true });
    const manifest = readJson(join(resolve(backupRoot), "manifest.json"), null);
    for (const entry of manifest.files) {
      const source = join(resolve(backupRoot), entry.path);
      const destination = join(target, entry.path);
      mkdirSync(dirname(destination), { recursive: true });
      copyFileSync(source, destination);
    }
    const restoredState = readJson(join(target, "state.json"), null);
    const restoredMemory = readJson(join(target, "memory", "index.json"), null);
    const ok = Boolean(restoredState?.schema && restoredMemory?.schema);
    return {
      ok,
      restored: ok,
      target,
      liveStateUntouched: true,
      stateSchema: restoredState?.schema || null,
      memorySchema: restoredMemory?.schema || null
    };
  }

  enqueue(task) {
    const state = this.readState();
    const item = {
      id: task.id || `local-task-${randomUUID()}`,
      type: task.type || "plan",
      title: task.title || "Tâche locale",
      projectId: task.projectId || "aione",
      risk: task.risk || "low",
      status: "QUEUED",
      createdAt: iso(this.clock),
      attempts: 0,
      payload: task.payload || {}
    };
    const alwaysAsk = new Set(this.config.approvals.alwaysRequireHuman);
    const requestedCapabilities = item.payload.capabilities || [];
    const sensitive = requestedCapabilities.filter((capability) => alwaysAsk.has(capability));
    if (sensitive.length > 0) {
      item.status = "AWAITING_HUMAN_APPROVAL";
      state.approvalsRequired.push({
        taskId: item.id,
        capabilities: sensitive,
        reason: "Action hors autonomie locale permanente.",
        createdAt: item.createdAt
      });
    }
    state.queue.push(item);
    state.events.push({ at: item.createdAt, type: "task-enqueued", taskId: item.id, status: item.status });
    this.writeState(state);
    this.memory.captureAtom("task-enqueued", { id: item.id, type: item.type, status: item.status });
    return item;
  }

  async audit() {
    const serviceResults = [];
    for (const service of this.config.services) {
      if (service.enabled === false) {
        serviceResults.push({
          id: service.id,
          label: service.label,
          ok: true,
          critical: false,
          disabled: true,
          status: "DISABLED",
          reason: service.disabledReason || "disabled-by-configuration"
        });
        continue;
      }
      serviceResults.push(await this.checkService(service));
    }
    const memory = this.memory.audit();
    const resource = this.checkResources();
    const agentRegistry = this.checkAgentRegistry();
    const ok = serviceResults.filter((item) => item.critical).every((item) => item.ok) && memory.ok && resource.ok && agentRegistry.ok;
    return {
      schema: "aione.forge-audit.v1",
      ok,
      generatedAt: iso(this.clock),
      services: serviceResults,
      resources: resource,
      memory,
      agentRegistry
    };
  }

  async developmentReadiness() {
    const script = join(this.root, "scripts", "get-forge-readiness.ps1");
    if (!existsSync(script)) throw new Error("Sonde de disponibilité Forge absente.");
    const result = await this.commandRunner(script, ["-Json"], {
      cwd: this.root,
      timeoutMs: 15000
    });
    const parsed = JSON.parse(String(result.stdout || "").trim());
    if (parsed.schema !== "aione.forge-readiness.v1" || typeof parsed.allowed !== "boolean") {
      throw new Error("Résultat de disponibilité Forge invalide.");
    }
    return parsed;
  }

  async checkService(service) {
    const startedAt = Date.now();
    try {
      let details = null;
      if (service.kind === "http") {
        details = await fetchJson(service.url, service.timeoutMs, this.fetchImpl);
      } else if (service.kind === "ollama") {
        details = await fetchJson(service.url, service.timeoutMs, this.fetchImpl);
        const models = (details?.models || []).map((item) => item.name || item.model).filter(Boolean);
        const missingModels = (service.requiredModels || []).filter((name) => !models.includes(name));
        if (missingModels.length > 0) throw new Error(`Modèles absents: ${missingModels.join(", ")}`);
        details = { models, missingModels };
      } else if (service.kind === "command") {
        const result = await this.commandRunner(service.command, service.args || [], {
          cwd: this.root,
          timeoutMs: service.timeoutMs
        });
        details = String(result.stdout || "").trim().slice(0, 1000);
      } else if (service.kind === "lobehub-device") {
        const result = await this.commandRunner("lh", ["device", "status", "--json"], {
          cwd: this.root,
          timeoutMs: service.timeoutMs
        });
        details = JSON.parse(String(result.stdout || "{}").trim());
        const minimumDevices = Number(service.minimumOnlineDevices || 1);
        if (!details.online || Number(details.deviceCount || 0) < minimumDevices) {
          throw new Error(`Passerelle LobeHub hors ligne (${Number(details.deviceCount || 0)} appareil connecté).`);
        }
      } else if (service.kind === "docker-container") {
        const result = await this.commandRunner("docker", [
          "inspect",
          service.container,
          "--format",
          "{{json .State}}"
        ], { cwd: this.root, timeoutMs: service.timeoutMs });
        details = JSON.parse(String(result.stdout || "{}").trim());
        if (details.Status !== service.expectedState) {
          throw new Error(`État ${details.Status || "inconnu"}, attendu ${service.expectedState}`);
        }
      } else {
        throw new Error(`Type de service inconnu: ${service.kind}`);
      }
      return {
        id: service.id,
        label: service.label,
        ok: true,
        critical: Boolean(service.critical),
        latencyMs: Date.now() - startedAt,
        details
      };
    } catch (error) {
      return {
        id: service.id,
        label: service.label,
        ok: false,
        critical: Boolean(service.critical),
        latencyMs: Date.now() - startedAt,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  checkResources() {
    const freeRamGb = os.freemem() / (1024 ** 3);
    let freeDiskGb = null;
    try {
      const stats = statfsSync(this.root);
      freeDiskGb = Number(stats.bavail) * Number(stats.bsize) / (1024 ** 3);
    } catch {
      freeDiskGb = null;
    }
    const ramOk = freeRamGb >= Number(this.config.resources.minimumFreeRamGbForAgent || 0);
    const diskOk = freeDiskGb === null || freeDiskGb >= Number(this.config.resources.minimumFreeDiskGb || 0);
    return {
      ok: ramOk && diskOk,
      freeRamGb: Number(freeRamGb.toFixed(2)),
      totalRamGb: Number((os.totalmem() / (1024 ** 3)).toFixed(2)),
      freeDiskGb: freeDiskGb === null ? null : Number(freeDiskGb.toFixed(2)),
      gates: { ramOk, diskOk }
    };
  }

  checkAgentRegistry() {
    const expected = ["aione-autonomous-forge"];
    const directory = join(this.root, ".opencode", "agents");
    const present = existsSync(directory)
      ? readdirSync(directory).filter((name) => name.endsWith(".md")).map((name) => basename(name, ".md"))
      : [];
    const missing = expected.filter((id) => !present.includes(id));
    const profiles = present.map((id) => {
      const content = readFileSync(join(directory, `${id}.md`), "utf8");
      return {
        id,
        mode: content.match(/^mode:\s*(\S+)/m)?.[1] || "unspecified"
      };
    });
    const primaryAioneProfiles = profiles.filter((item) => item.mode === "primary").map((item) => item.id);
    const internalRoleProfiles = profiles.filter((item) => item.id !== "aione-autonomous-forge").map((item) => item.id);
    return {
      ok: missing.length === 0 &&
        primaryAioneProfiles.length === 1 &&
        primaryAioneProfiles[0] === "aione-autonomous-forge",
      authorityModel: "SINGLE_CONTROL_PLANE",
      expected,
      present,
      missing,
      internalRoleProfiles,
      primaryAioneProfiles,
      profiles
    };
  }

  acquireCycleLock() {
    const path = join(this.paths.locks, "cycle.lock");
    const tryOpen = () => {
      const descriptor = openSync(path, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, createdAt: iso(this.clock) }), "utf8");
      return { ok: true, descriptor, path };
    };
    try {
      return tryOpen();
    } catch (error) {
      if (error?.code !== "EEXIST") {
        return { ok: false, path, error: error instanceof Error ? error.message : String(error) };
      }
      try {
        const lockMetadata = JSON.parse(readFileSync(path, "utf8"));
        const ageMs = this.clock().getTime() - statSync(path).mtimeMs;
        const ownerPid = Number(lockMetadata?.pid);
        let ownerAlive = null;
        if (Number.isInteger(ownerPid) && ownerPid > 0) {
          try {
            process.kill(ownerPid, 0);
            ownerAlive = true;
          } catch (processError) {
            ownerAlive = processError?.code === "ESRCH" ? false : null;
          }
        }
        const staleReason = ownerAlive === false
          ? "owner-process-not-running"
          : ageMs > 2 * 60 * 60 * 1000
            ? "lock-older-than-two-hours"
            : null;
        if (staleReason) {
          unlinkSync(path);
          return {
            ...tryOpen(),
            recovered: {
              reason: staleReason,
              previousPid: Number.isInteger(ownerPid) ? ownerPid : null,
              previousCreatedAt: lockMetadata?.createdAt || null,
              ageMs
            }
          };
        }
      } catch {
        // Le verrou reste considéré actif si son état ne peut pas être prouvé.
      }
      return { ok: false, path, error: error instanceof Error ? error.message : String(error) };
    }
  }

  releaseCycleLock(lock) {
    if (!lock?.ok) return;
    try {
      closeSync(lock.descriptor);
    } finally {
      try {
        unlinkSync(lock.path);
      } catch {
        // Un prochain cycle pourra récupérer un verrou ancien après deux heures.
      }
    }
  }

  async runCycle(options = {}) {
    const lock = this.acquireCycleLock();
    if (!lock.ok) {
      return { ok: false, status: "ALREADY_RUNNING", lockPath: lock.path };
    }
    try {
      return await this.runCycleUnlocked({ ...options, recoveredLock: lock.recovered || null });
    } finally {
      this.releaseCycleLock(lock);
    }
  }

  async runCycleUnlocked({ executeTasks = true, recoveredLock = null } = {}) {
    const state = this.readState();
    const cycleId = `cycle-${this.clock().toISOString().replace(/[-:.TZ]/g, "")}-${randomUUID().slice(0, 8)}`;
    if (state.paused) return { ok: false, cycleId, status: "PAUSED", audit: await this.audit() };

    const audit = await this.audit();
    state.metrics.cycles += 1;
    state.lastCycle = { id: cycleId, startedAt: iso(this.clock), status: "RUNNING" };
    if (recoveredLock) {
      state.events.push({
        at: state.lastCycle.startedAt,
        type: "orphan-cycle-lock-recovered",
        cycleId,
        ...recoveredLock
      });
    }
    state.events.push({ at: state.lastCycle.startedAt, type: "cycle-started", cycleId });
    this.writeState(state);
    this.memory.captureAtom("health-audit", { cycleId, ok: audit.ok, services: audit.services.map(({ id, ok }) => ({ id, ok })) });
    const healthySubjects = audit.services.filter((service) => service.ok);
    if (audit.memory.ok) healthySubjects.push({ id: "memory-index" });
    if (audit.resources.ok) healthySubjects.push({ id: "resources" });
    this.resolveHealthyIncidents(healthySubjects, cycleId);

    const failures = audit.services.filter((service) => !service.ok);
    const incidents = [];
    for (const failure of failures) {
      incidents.push(await this.handleFailure(failure, cycleId));
    }
    if (!audit.memory.ok) {
      incidents.push(await this.handleFailure({
        id: "memory-index",
        label: "Mémoire fractale",
        ok: false,
        critical: true,
        error: JSON.stringify(audit.memory.issues)
      }, cycleId));
    }
    if (!audit.resources.ok) {
      incidents.push(await this.handleFailure({
        id: "resources",
        label: "Ressources système",
        ok: false,
        critical: true,
        error: JSON.stringify(audit.resources)
      }, cycleId));
    }

    let taskResult = null;
    const inQuietHours = this.isQuietHours();
    if (executeTasks && audit.resources.ok && audit.services.filter((service) => service.critical).every((service) => service.ok)) {
      if (!inQuietHours) this.ensureDailyPlanningTask();
      let developmentReadiness = null;
      if (this.developmentCapacityConfig?.enabled) {
        try {
          developmentReadiness = await this.developmentReadiness();
        } catch (error) {
          developmentReadiness = {
            allowed: false,
            reason: "readiness-probe-failed",
            error: error instanceof Error ? error.message : String(error)
          };
        }
        if (!inQuietHours) this.ensureCouncilTask({ readiness: developmentReadiness });
        this.ensureDevelopmentCapacityTask({ readiness: developmentReadiness, quietHours: inQuietHours });
      } else if (!inQuietHours) {
        this.ensureCouncilTask();
      }
      this.ensureMaintenanceTask({ quietHours: inQuietHours });
      const quietSafeTypes = new Set(
        (this.config.continuous?.neverIdle?.rotation || [])
          .filter((entry) => entry.quietSafe)
          .map((entry) => entry.type)
      );
      if (developmentReadiness?.allowed) quietSafeTypes.add("development-work-package");
      taskResult = await this.runNextSafeTask({
        allowedTypes: inQuietHours ? quietSafeTypes : null
      });
    }

    const finalState = this.readState();
    const criticalOpen = incidents.some((incident) => incident?.critical && incident.status !== "RESOLVED");
    finalState.lastCycle = {
      id: cycleId,
      startedAt: state.lastCycle.startedAt,
      completedAt: iso(this.clock),
      status: criticalOpen ? "DEGRADED" : "OK",
      quietHours: inQuietHours,
      taskResult
    };
    const next = new Date(this.clock().getTime() + Number(this.config.schedule.cycleMinutes || 15) * 60000);
    finalState.nextCycle = next.toISOString();
    if (criticalOpen) finalState.metrics.failedCycles += 1;
    else finalState.metrics.successfulCycles += 1;
    finalState.events.push({ at: finalState.lastCycle.completedAt, type: "cycle-completed", cycleId, status: finalState.lastCycle.status });
    const backupDay = this.clock().toISOString().slice(0, 10);
    const shouldBackup = finalState.lastBackupDate !== backupDay;
    if (shouldBackup) finalState.lastBackupDate = backupDay;
    this.writeState(finalState);
    this.memory.captureAtom("cycle-completed", finalState.lastCycle);
    this.memory.compact();
    const backup = shouldBackup ? this.createBackup() : null;

    const report = {
      ok: !criticalOpen,
      cycleId,
      audit,
      incidents,
      taskResult,
      quietHours: inQuietHours,
      backup,
      lockRecovery: recoveredLock
    };
    atomicJson(join(this.paths.reports, `${cycleId}.json`), report);
    return report;
  }

  isQuietHours() {
    const hour = this.clock().getHours();
    const start = Number(this.config.schedule.quietHours?.start ?? 23);
    const end = Number(this.config.schedule.quietHours?.end ?? 7);
    return start > end ? hour >= start || hour < end : hour >= start && hour < end;
  }

  ensureDailyPlanningTask() {
    if (!this.config.schedule.dailyPlanningEnabled) return null;
    const now = this.clock();
    if (now.getHours() < Number(this.config.schedule.dailyPlanningHour || 8)) return null;
    const day = now.toISOString().slice(0, 10);
    const state = this.readState();
    if (state.lastDailyPlanDate === day) return null;
    if (state.queue.some((task) => task.type === "plan" && task.status === "QUEUED")) return null;
    state.lastDailyPlanDate = day;
    this.writeState(state);
    return this.enqueue({
      type: "plan",
      title: `Plan local AIONE du ${day}`,
      risk: "low",
      payload: { sourceFiles: ["PRIORITY.md", "TASK.md", "KANBAN.md"] }
    });
  }

  ensureCouncilTask({ readiness = null } = {}) {
    if (!this.councilConfig?.enabled) return null;
    if (this.developmentCapacityConfig?.enabled && !readiness?.allowed) return null;
    const now = this.clock();
    const days = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
    const dayCode = days[now.getDay()];
    const currentMinute = now.getHours() * 60 + now.getMinutes();
    const dateKey = localDateKey(now);
    const state = this.readState();
    const meeting = (this.councilConfig.meetings || []).find((item) =>
      item.day === dayCode &&
      currentMinute >= minuteOfDay(item.time) &&
      state.lastCouncilRuns[item.id] !== dateKey &&
      !state.queue.some((task) =>
        task.type === "council-meeting" &&
        task.payload?.meetingId === item.id &&
        ["QUEUED", "RUNNING"].includes(task.status)
      )
    );
    if (!meeting) return null;
    const routing = this.developmentCapacityConfig?.modelRouting || {};
    let selectedModel = meeting.model;
    if (readiness && !readiness.gates?.userAbsent) {
      selectedModel = routing.whileUserActive || this.config.models.fast;
    } else if (
      readiness &&
      meeting.model === routing.deepCouncilOnlyWhenCapacityProven &&
      Number(readiness.freeRamGb || 0) < 16
    ) {
      selectedModel = routing.whileUserAbsent || this.config.models.balanced;
    }
    return this.enqueue({
      id: `council-${meeting.id}-${dateKey}`,
      type: "council-meeting",
      title: `${meeting.name} — ${dateKey}`,
      risk: "low",
      payload: {
        meetingId: meeting.id,
        scheduledDate: dateKey,
        selectedModel,
        capabilities: ["agent-council"]
      }
    });
  }

  ensureDevelopmentCapacityTask({ readiness, quietHours = false } = {}) {
    const config = this.developmentCapacityConfig;
    if (!config?.enabled || !readiness?.allowed) return null;
    if (quietHours && config.workPackages?.runAtNightOnlyWhenReadinessAllows === false) return null;
    const now = this.clock();
    const dateKey = localDateKey(now);
    const weekKey = mondayWeekKey(now);
    const state = this.readState();
    if (state.developmentCapacity.weekKey !== weekKey) {
      state.developmentCapacity = {
        weekKey,
        nominalAgentHours: 0,
        actualWallClockMs: 0,
        packagesCompleted: 0,
        lastRunAt: null,
        dailyPackages: {}
      };
      this.writeState(state);
    }
    const capacity = state.developmentCapacity;
    const target = Number(config.weeklyTargetAgentHours || 0);
    if (Number(capacity.nominalAgentHours || 0) >= target) return null;
    const activeDevelopment = state.queue.some((task) =>
      task.type === "development-work-package" &&
      ["QUEUED", "RUNNING"].includes(task.status)
    );
    if (config.workPackages?.oneAtATime !== false && activeDevelopment) return null;
    const higherPriority = state.queue.some((task) =>
      task.status === "QUEUED" &&
      !task.payload?.maintenance &&
      task.type !== "development-work-package"
    );
    if (higherPriority) return null;
    const maximumPerDay = Number(config.workPackages?.maximumPerDay || 1);
    if (Number(capacity.dailyPackages?.[dateKey] || 0) >= maximumPerDay) return null;
    const minimumIntervalMs = Number(config.workPackages?.minimumIntervalMinutes || 120) * 60000;
    if (capacity.lastRunAt && now.getTime() - new Date(capacity.lastRunAt).getTime() < minimumIntervalMs) return null;

    const nominalHours = Number(config.workPackages?.nominalHours || 1);
    const weightedFocuses = (config.allocation || []).flatMap((entry) =>
      Array.from(
        { length: Math.max(1, Math.round(Number(entry.agentHours || nominalHours) / nominalHours)) },
        () => entry.focus
      )
    );
    const focuses = weightedFocuses.length ? weightedFocuses : ["diagnostic"];
    const packageIndex = Number(capacity.packagesCompleted || 0);
    const focus = focuses[packageIndex % focuses.length];
    const priorityProjects = config.priorityProjects || ["aione-fractalos"];
    const projectId = priorityProjects[packageIndex % priorityProjects.length];
    const antiEmpty = config.antiEmptyQueue || ["repository-diagnostic"];
    const source = antiEmpty[packageIndex % antiEmpty.length];
    const routing = config.modelRouting || {};
    const selectedModel = readiness.gates?.userAbsent
      ? (routing.whileUserAbsent || this.config.models.balanced)
      : (routing.whileUserActive || this.config.models.fast);
    return this.enqueue({
      type: "development-work-package",
      title: `Capacité DEV — ${focus} — ${projectId}`,
      projectId,
      risk: "low",
      payload: {
        focus,
        source,
        nominalAgentHours: nominalHours,
        scheduledDate: dateKey,
        selectedModel,
        readinessReason: readiness.reason,
        capabilities: ["development-capacity", "read", "audit", "plan", "test.existing"]
      }
    });
  }

  ensureMaintenanceTask({ quietHours = false } = {}) {
    const policy = this.config.continuous?.neverIdle;
    if (!this.config.continuous?.enabled || !policy?.enabled) return null;
    const rotation = (policy.rotation || []).filter((entry) => !quietHours || entry.quietSafe);
    if (!rotation.length) return null;
    const state = this.readState();
    const runnableUserTask = state.queue.some((task) =>
      task.status === "QUEUED" &&
      !task.payload?.maintenance &&
      (!quietHours || rotation.some((entry) => entry.type === task.type))
    );
    if (runnableUserTask) return null;
    if (state.queue.some((task) => task.status === "QUEUED" && task.payload?.maintenance)) return null;
    const startIndex = state.nextMaintenanceIndex % rotation.length;
    let selected = null;
    let selectedIndex = -1;
    for (let offset = 0; offset < rotation.length; offset += 1) {
      const index = (startIndex + offset) % rotation.length;
      const candidate = rotation[index];
      const minimumIntervalMs = Number(candidate.minimumIntervalMinutes || 0) * 60000;
      const lastRunAt = state.maintenanceLastRun[candidate.type];
      const lastRunMs = lastRunAt ? new Date(lastRunAt).getTime() : Number.NaN;
      const due = minimumIntervalMs <= 0 ||
        !Number.isFinite(lastRunMs) ||
        this.clock().getTime() - lastRunMs >= minimumIntervalMs;
      if (due) {
        selected = candidate;
        selectedIndex = index;
        break;
      }
    }
    if (!selected) return null;
    state.nextMaintenanceIndex = (selectedIndex + 1) % rotation.length;
    this.writeState(state);
    return this.enqueue({
      type: selected.type,
      title: `Maintenance autonome — ${selected.type}`,
      risk: "low",
      payload: {
        maintenance: true,
        capabilities: [selected.type],
        quietSafe: Boolean(selected.quietSafe)
      }
    });
  }

  async runNextSafeTask({ allowedTypes = null } = {}) {
    const state = this.readState();
    const task = state.queue.find((item) =>
      item.status === "QUEUED" &&
      (!allowedTypes || allowedTypes.has(item.type))
    );
    if (!task) return { ran: false, reason: "queue-empty" };
    task.status = "RUNNING";
    task.attempts += 1;
    task.startedAt = iso(this.clock);
    this.writeState(state);
    try {
      let result;
      if (task.type === "plan") result = await this.runPlanningTask(task);
      else if (task.type === "validate") result = await this.runValidationTask(task);
      else if (task.type === "memory-compact") result = this.memory.compact();
      else if (task.type === "health-audit") result = await this.audit();
      else if (task.type === "context-audit") result = this.runContextAudit();
      else if (task.type === "portfolio-audit") result = this.runPortfolioAudit();
      else if (task.type === "documentation-audit") result = this.runDocumentationAudit();
      else if (task.type === "security-audit") result = this.runSecurityAudit();
      else if (task.type === "capability-audit") result = await this.runCapabilityAudit();
      else if (task.type === "model-capability-audit") result = await this.runCapabilityAudit();
      else if (task.type === "backlog-refill") result = this.runBacklogRefill();
      else if (task.type === "backup-verify") result = this.runLatestBackupVerification();
      else if (task.type === "editorial-sync") result = this.runEditorialSync();
      else if (task.type === "council-meeting") result = await this.runCouncilMeetingTask(task);
      else if (task.type === "development-work-package") result = await this.runDevelopmentWorkPackage(task);
      else throw new Error(`Type de tâche non autorisé en autonomie: ${task.type}`);
      const nextState = this.readState();
      const stored = nextState.queue.find((item) => item.id === task.id);
      stored.status = "COMPLETED";
      stored.completedAt = iso(this.clock);
      stored.result = result;
      nextState.metrics.tasksCompleted += 1;
      if (task.payload?.maintenance) {
        nextState.metrics.maintenanceCompleted += 1;
        nextState.maintenanceLastRun[task.type] = stored.completedAt;
      }
      if (task.type === "council-meeting") {
        nextState.lastCouncilRuns[task.payload.meetingId] = task.payload.scheduledDate || localDateKey(this.clock());
        nextState.metrics.councilMeetingsCompleted += 1;
      }
      if (task.type === "development-work-package") {
        const dateKey = task.payload.scheduledDate || localDateKey(this.clock());
        const nominalHours = Number(task.payload.nominalAgentHours || 0);
        nextState.developmentCapacity.nominalAgentHours += nominalHours;
        nextState.developmentCapacity.actualWallClockMs += Number(result.actualWallClockMs || 0);
        nextState.developmentCapacity.packagesCompleted += 1;
        nextState.developmentCapacity.lastRunAt = stored.completedAt;
        nextState.developmentCapacity.dailyPackages[dateKey] =
          Number(nextState.developmentCapacity.dailyPackages[dateKey] || 0) + 1;
        nextState.metrics.developmentWorkPackagesCompleted += 1;
        nextState.metrics.nominalDevelopmentAgentHours += nominalHours;
        nextState.metrics.actualDevelopmentWallClockMs += Number(result.actualWallClockMs || 0);
      }
      this.writeState(nextState);
      this.memory.captureAtom("task-completed", { id: task.id, type: task.type, result });
      return { ran: true, taskId: task.id, status: "COMPLETED", result };
    } catch (error) {
      const nextState = this.readState();
      const stored = nextState.queue.find((item) => item.id === task.id);
      stored.status = stored.attempts >= 2 ? "AWAITING_HUMAN_REVIEW" : "QUEUED";
      stored.error = error instanceof Error ? error.message : String(error);
      stored.completedAt = iso(this.clock);
      if (stored.status === "AWAITING_HUMAN_REVIEW") {
        nextState.approvalsRequired.push({
          taskId: stored.id,
          capabilities: ["local-task-recovery"],
          reason: stored.error,
          createdAt: stored.completedAt
        });
      }
      this.writeState(nextState);
      this.memory.captureAtom("task-failed", { id: task.id, type: task.type, error: stored.error });
      return { ran: true, taskId: task.id, status: stored.status, error: stored.error };
    }
  }

  runContextAudit() {
    const state = this.readState();
    const memory = this.memory.audit();
    return {
      ok: memory.ok,
      queue: {
        total: state.queue.length,
        queued: state.queue.filter((task) => task.status === "QUEUED").length,
        awaitingApproval: state.queue.filter((task) => task.status === "AWAITING_HUMAN_APPROVAL").length,
        awaitingReview: state.queue.filter((task) => task.status === "AWAITING_HUMAN_REVIEW").length
      },
      eventsRetained: state.events.length,
      approvalsRequired: state.approvalsRequired.length,
      memory
    };
  }

  runPortfolioAudit() {
    const path = join(this.root, "config", "project-portfolio.json");
    const portfolio = readJson(path, null);
    if (!portfolio?.schema || !Array.isArray(portfolio.projects)) {
      throw new Error("Registre de projets absent ou invalide.");
    }
    const projects = portfolio.projects.map((project) => ({
      id: project.id,
      category: project.category,
      path: project.path,
      exists: project.path ? existsSync(project.path) : null,
      authority: project.authority
    }));
    return {
      ok: true,
      path,
      counts: projects.reduce((counts, project) => {
        counts[project.category] = (counts[project.category] || 0) + 1;
        return counts;
      }, {}),
      missingCurrentPaths: projects.filter((project) => project.category === "CURRENT" && project.path && !project.exists),
      projects
    };
  }

  runDocumentationAudit() {
    const required = [
      "AGENTS.md",
      "AUTONOMY_STATE.md",
      "docs/forge/LOCAL_AUTONOMY_RUNBOOK.md",
      "docs/forge/TRELLO_AUTONOMY_RUNBOOK.md",
      "docs/forge/AGENT_COUNCIL_AND_96H_RUNBOOK.md",
      "docs/forge/council/COUNCIL_PROTOCOL.md",
      "docs/forge/council/COUNCIL_SYNTHESIS_2026-07-26.md",
      "docs/forge/council/PLANNING_SCENARIOS_2026-07-27.md"
    ];
    const files = required.map((relative) => {
      const path = join(this.root, relative);
      return { relative, exists: existsSync(path), size: existsSync(path) ? statSync(path).size : 0 };
    });
    return { ok: files.every((file) => file.exists && file.size > 0), files };
  }

  runEditorialSync() {
    const generatedAt = iso(this.clock);
    const dateKey = localDateKey(this.clock());
    const state = this.readState();
    const memory = this.memory.audit();
    const portfolioPath = join(this.root, "config", "project-portfolio.json");
    const portfolio = readJson(portfolioPath, { projects: [] });
    const latestCycleReportPath = state.lastCycle?.id
      ? join(this.paths.reports, `${state.lastCycle.id}.json`)
      : null;
    const latestCycleReport = latestCycleReportPath && existsSync(latestCycleReportPath)
      ? readJson(latestCycleReportPath, null)
      : null;
    const openIncidents = Object.values(state.incidents || {})
      .filter((incident) => incident.status !== "RESOLVED")
      .sort((left, right) => (
        Number(Boolean(right.critical)) - Number(Boolean(left.critical)) ||
        String(left.serviceId).localeCompare(String(right.serviceId)) ||
        String(left.id).localeCompare(String(right.id))
      ))
      .map((incident) => ({
        id: incident.id,
        serviceId: incident.serviceId,
        label: redactEditorialText(incident.label),
        critical: Boolean(incident.critical),
        status: incident.status,
        occurrences: Number(incident.occurrences || 0),
        lastSeenAt: incident.lastSeenAt || null,
        error: redactEditorialText(incident.error).slice(0, 320)
      }));
    const recentTasks = (state.queue || [])
      .filter((task) => task.status === "COMPLETED")
      .sort((left, right) => String(right.completedAt || "").localeCompare(String(left.completedAt || "")))
      .slice(0, 8)
      .map((task) => ({
        id: task.id,
        type: task.type,
        title: redactEditorialText(task.title),
        completedAt: task.completedAt || null,
        engine: task.result?.engine || null,
        model: task.result?.model || null,
        mutationPerformed: Boolean(task.result?.mutationPerformed)
      }));
    const projects = (portfolio.projects || [])
      .map((project) => ({
        id: project.id,
        category: project.category || "UNCLASSIFIED",
        authority: project.authority || null
      }))
      .sort((left, right) => String(left.id).localeCompare(String(right.id)));
    const projectCounts = projects.reduce((counts, project) => {
      counts[project.category] = Number(counts[project.category] || 0) + 1;
      return counts;
    }, {});
    const queue = {
      total: (state.queue || []).length,
      queued: (state.queue || []).filter((task) => task.status === "QUEUED").length,
      running: (state.queue || []).filter((task) => task.status === "RUNNING").length,
      awaitingHuman: (state.queue || []).filter((task) =>
        ["AWAITING_HUMAN_APPROVAL", "AWAITING_HUMAN_REVIEW"].includes(task.status)
      ).length
    };
    const provenance = [
      { kind: "runtime-state", path: this.paths.state },
      { kind: "memory-index", path: join(this.paths.memory, "index.json") },
      { kind: "project-portfolio", path: portfolioPath },
      ...(latestCycleReportPath && latestCycleReport
        ? [{ kind: "cycle-report", path: latestCycleReportPath }]
        : [])
    ];
    const snapshot = {
      schema: "aione.editorial-snapshot.v1",
      generatedAt,
      dateKey,
      status: "DRAFT_LOCAL_ONLY",
      mode: state.mode,
      lastCycle: state.lastCycle || null,
      queue,
      metrics: state.metrics,
      developmentCapacity: this.developmentCapacityStatus(state),
      memory,
      openIncidents,
      recentTasks,
      projects,
      projectCounts,
      provenance
    };
    const snapshotSha256 = createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
    const outputDir = join(this.paths.editorial, dateKey);
    const siteDir = join(outputDir, "site");
    mkdirSync(siteDir, { recursive: true });
    const statusBanner = [
      "> Statut : `DRAFT_LOCAL_ONLY`",
      ">",
      "> Généré localement sans réseau. Toute publication externe exige une validation humaine."
    ].join("\n");
    const incidentLines = openIncidents.length
      ? openIncidents.map((incident) =>
          `- ${incident.critical ? "CRITIQUE" : "optionnel"} — ${incident.label || incident.serviceId}: ${incident.status}; ${incident.error || "détail non fourni"}`
        ).join("\n")
      : "- Aucun incident ouvert mesuré.";
    const taskLines = recentTasks.length
      ? recentTasks.map((task) =>
          `- ${task.completedAt || "date inconnue"} — ${task.type}: ${task.title}${task.model ? ` (${task.model})` : ""}`
        ).join("\n")
      : "- Aucune tâche terminée conservée dans l'historique borné.";
    const projectCountLines = Object.entries(projectCounts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([category, count]) => `- ${category}: ${count}`)
      .join("\n") || "- Aucun projet mesuré.";
    const projectStatus = [
      "# État local du projet AIONE",
      "",
      statusBanner,
      "",
      `- Généré: ${generatedAt}`,
      `- Mode: ${state.mode}`,
      `- Dernier cycle: ${state.lastCycle?.id || "inconnu"} / ${state.lastCycle?.status || "inconnu"}`,
      `- File: ${queue.queued} en attente, ${queue.running} en cours, ${queue.awaitingHuman} sous validation humaine`,
      `- Mémoire: ${memory.ok ? "saine" : "à vérifier"}`,
      `- Cycles réussis/échoués: ${Number(state.metrics?.successfulCycles || 0)} / ${Number(state.metrics?.failedCycles || 0)}`,
      "",
      "## Incidents ouverts",
      "",
      incidentLines,
      "",
      "## Portefeuille",
      "",
      projectCountLines,
      "",
      "## Provenance",
      "",
      ...provenance.map((source) => `- ${source.kind}: \`${source.path}\``),
      ""
    ].join("\n");
    const devlog = [
      `# Devlog AIONE — ${dateKey}`,
      "",
      statusBanner,
      "",
      `- Tâches terminées cumulées: ${Number(state.metrics?.tasksCompleted || 0)}`,
      `- Maintenances terminées: ${Number(state.metrics?.maintenanceCompleted || 0)}`,
      `- Conseils terminés: ${Number(state.metrics?.councilMeetingsCompleted || 0)}`,
      `- Paquets DEV terminés: ${Number(state.metrics?.developmentWorkPackagesCompleted || 0)}`,
      `- Heures-agent nominales cette semaine: ${Number(snapshot.developmentCapacity.nominalAgentHoursCompleted || 0)} / ${Number(snapshot.developmentCapacity.weeklyTargetAgentHours || 0)}`,
      "",
      "## Activité récente mesurée",
      "",
      taskLines,
      "",
      "## Limites",
      "",
      "- Aucune publication, synchronisation Trello ou écriture Calendar n'a été effectuée par ce lot.",
      "- Les résultats non présents dans l'état ou les rapports locaux ne sont pas inventés.",
      ""
    ].join("\n");
    const devblogDraft = [
      `# Brouillon de devblog — AIONE ${dateKey}`,
      "",
      statusBanner,
      "",
      "La Forge AIONE poursuit son fonctionnement local autonome avec une boucle bornée: observer, planifier, exécuter une action sûre, mesurer puis conserver la preuve.",
      "",
      `Le dernier état mesuré compte ${Number(state.metrics?.tasksCompleted || 0)} tâches terminées et ${Number(state.metrics?.maintenanceCompleted || 0)} maintenances. La mémoire fractale est ${memory.ok ? "saine" : "signalée à vérifier"}.`,
      "",
      "Les services optionnels indisponibles restent visibles comme incidents sans bloquer le travail local lorsque les services critiques sont sains.",
      "",
      "Avant publication, relire les formulations, retirer les chemins locaux et confirmer les chiffres depuis le manifeste de provenance.",
      ""
    ].join("\n");
    const forumDraft = [
      `# Brouillon forum — Point AIONE du ${dateKey}`,
      "",
      statusBanner,
      "",
      "## Ce qui fonctionne localement",
      "",
      `- Orchestration cyclique: ${state.lastCycle?.status || "inconnue"}`,
      `- File autonome actuelle: ${queue.queued} tâche(s)`,
      `- Mémoire fractale: ${memory.ok ? "OK" : "À VÉRIFIER"}`,
      `- Production DEV nominale hebdomadaire: ${Number(snapshot.developmentCapacity.nominalAgentHoursCompleted || 0)} / ${Number(snapshot.developmentCapacity.weeklyTargetAgentHours || 0)}`,
      "",
      "## Points ouverts",
      "",
      incidentLines,
      "",
      "Question proposée à la communauté: quel test local et reproductible améliorerait le plus la robustesse du prochain cycle ?",
      ""
    ].join("\n");
    const htmlIncidents = openIncidents.length
      ? openIncidents.map((incident) =>
          `<li><strong>${escapeHtml(incident.critical ? "Critique" : "Optionnel")}</strong> — ${escapeHtml(incident.label || incident.serviceId)}: ${escapeHtml(incident.status)}</li>`
        ).join("")
      : "<li>Aucun incident ouvert mesuré.</li>";
    const htmlTasks = recentTasks.length
      ? recentTasks.map((task) =>
          `<li>${escapeHtml(task.completedAt || "")} — ${escapeHtml(task.type)}: ${escapeHtml(task.title)}</li>`
        ).join("")
      : "<li>Aucune tâche récente conservée.</li>";
    const localSite = [
      "<!doctype html>",
      '<html lang="fr"><head><meta charset="utf-8">',
      '<meta name="viewport" content="width=device-width,initial-scale=1">',
      `<title>AIONE — état local ${escapeHtml(dateKey)}</title>`,
      "<style>body{font:16px/1.5 system-ui;max-width:920px;margin:auto;padding:2rem;background:#0b1020;color:#e8eefc}section{background:#151d33;padding:1rem 1.25rem;margin:1rem 0;border-radius:12px}.draft{color:#ffd166}code{color:#8bd3ff}</style>",
      "</head><body>",
      `<h1>AIONE — état local du ${escapeHtml(dateKey)}</h1>`,
      '<p class="draft"><strong>DRAFT_LOCAL_ONLY</strong> — aucune publication réseau.</p>',
      `<section><h2>Cycle</h2><p><code>${escapeHtml(state.lastCycle?.id || "inconnu")}</code> — ${escapeHtml(state.lastCycle?.status || "inconnu")}</p></section>`,
      `<section><h2>Activité</h2><p>${Number(state.metrics?.tasksCompleted || 0)} tâches, ${Number(state.metrics?.maintenanceCompleted || 0)} maintenances.</p><ul>${htmlTasks}</ul></section>`,
      `<section><h2>Incidents</h2><ul>${htmlIncidents}</ul></section>`,
      `<section><h2>Preuve</h2><p>Empreinte du snapshot: <code>${snapshotSha256}</code></p></section>`,
      "</body></html>",
      ""
    ].join("\n");
    const contentByRelativePath = {
      "PROJECT_STATUS.md": projectStatus,
      "DEVLOG.md": devlog,
      "DEVBLOG_DRAFT.md": devblogDraft,
      "FORUM_DRAFT.md": forumDraft,
      "site/index.html": localSite
    };
    const files = Object.entries(contentByRelativePath).map(([relativePath, content]) => {
      const sanitized = redactEditorialText(content);
      const path = join(outputDir, ...relativePath.split("/"));
      atomicText(path, sanitized);
      return {
        path: relativePath,
        bytes: Buffer.byteLength(sanitized, "utf8"),
        sha256: createHash("sha256").update(sanitized).digest("hex")
      };
    });
    const manifest = {
      schema: "aione.editorial-package.v1",
      generatedAt,
      dateKey,
      status: "DRAFT_LOCAL_ONLY",
      published: false,
      networkUsed: false,
      generator: "deterministic-local-runtime",
      modelUsed: null,
      humanValidationRequired: true,
      snapshotSha256,
      files,
      provenance,
      uncertainties: [
        "Les connecteurs externes ne sont pas interrogés par editorial-sync.",
        "Toute information absente des preuves locales reste non mesurée.",
        "Les brouillons doivent être relus avant toute diffusion."
      ]
    };
    const manifestPath = join(outputDir, "PUBLICATION_MANIFEST.json");
    atomicJson(manifestPath, manifest);
    return {
      ok: true,
      status: manifest.status,
      published: false,
      networkUsed: false,
      outputDir,
      manifestPath,
      files: [...files, {
        path: "PUBLICATION_MANIFEST.json",
        bytes: statSync(manifestPath).size
      }],
      snapshotSha256
    };
  }

  runSecurityAudit() {
    const human = new Set(this.config.approvals.alwaysRequireHuman || []);
    const required = [
      "delete",
      "git-write",
      "dependency-install",
      "mail-send",
      "calendar-write-other",
      "calendar-invite",
      "calendar-delete",
      "external-publication",
      "model-download"
    ];
    const missing = required.filter((capability) => !human.has(capability));
    const protectedPath = resolve("S:\\AI_LAB\\Validation");
    const projectCollision = (this.config.projects || []).some((project) => resolve(project.path) === protectedPath);
    return {
      ok: missing.length === 0 && !projectCollision && this.config.approvals.externalActionsDefault === "deny",
      externalActionsDefault: this.config.approvals.externalActionsDefault,
      missingHumanGates: missing,
      protectedPathRegisteredAsProject: projectCollision
    };
  }

  async runCapabilityAudit() {
    const registryPath = join(this.root, "config", "capability-registry.json");
    if (!existsSync(registryPath)) throw new Error("Registre de capacités absent.");
    const { createControlPlaneRuntime } = await import("./control-plane.mjs");
    const controlPlane = createControlPlaneRuntime({ root: this.root, clock: this.clock });
    const audit = controlPlane.audit();
    controlPlane.recordEvidence({
      eventType: "capability-audit",
      action: "audit.capabilities",
      decision: "ALLOW",
      status: audit.ok ? "PASS" : "FAIL",
      proofs: [
        `engines:${audit.engineCount}`,
        `capabilities:${audit.capabilityCount}`,
        `waves:${audit.waveCount}`
      ],
      metadata: { issues: audit.issues }
    });
    return audit;
  }

  runBacklogRefill() {
    if (!this.dualGpuConfig?.enabled) {
      return { ok: true, status: "DUAL_GPU_DISABLED", generatedTasks: 0 };
    }
    const runtimeRoot = expandEnvironmentPath(this.dualGpuConfig.runtimeDir);
    const requestDir = join(runtimeRoot, "requests");
    const requestFiles = existsSync(requestDir)
      ? readdirSync(requestDir).filter((name) => name.endsWith("-backlog-refresh.json")).sort()
      : [];
    const allRequests = requestFiles
      .map((name) => ({ name, value: readJson(join(requestDir, name), null) }))
      .filter((entry) => entry.value?.schema === "aione.backlog-refresh-request.v1");
    // Only the newest request per lane is actionable. Keeping every historical
    // request in the generation key made the backlog header grow forever and
    // obscured which workers were currently starved.
    const latestByLane = new Map();
    for (const entry of allRequests) {
      const laneId = String(entry.value.laneId || "unknown");
      const current = latestByLane.get(laneId);
      const entryTime = Date.parse(entry.value.createdAt || "") || 0;
      const currentTime = Date.parse(current?.value?.createdAt || "") || 0;
      if (!current || entryTime >= currentTime) latestByLane.set(laneId, entry);
    }
    const requests = [...latestByLane.values()].sort((left, right) => left.name.localeCompare(right.name));
    if (!requests.length) return { ok: true, status: "NO_REQUEST", generatedTasks: 0 };

    const continuityWorkstreams = this.developmentContinuityConfig?.enabled
      ? (this.developmentContinuityConfig.workstreams || [])
          .filter((entry) => ["ACTIVE", "READY"].includes(entry.status))
          .slice(0, Number(this.developmentContinuityConfig.cycle?.workstreamsPerGeneration || 15))
      : [];
    const continuityRevision = continuityWorkstreams.length
      ? stableId("continuity", JSON.stringify(continuityWorkstreams))
      : "fallback";
    const absoluteWorkstreams = this.absolutePriorityProgram.enabled && this.absolutePriorityProgram.valid
      ? this.absolutePriorityProgram.activeWorkstreams
          .slice(0, Number(this.absolutePriorityConfig?.priorityPolicy?.maximumWorkstreamsPerGeneration || 18))
      : [];
    const absoluteRevision = absoluteWorkstreams.length
      ? stableId("absolute-prompts", JSON.stringify(absoluteWorkstreams))
      : "disabled";
    const fractalOsWorkstreams = this.fractalOsHardDevelopmentConfig?.enabled
      ? (this.fractalOsHardDevelopmentConfig.workstreams || [])
          .filter((entry) => ["ACTIVE", "READY"].includes(entry.status))
          .slice(0, Number(this.fractalOsHardDevelopmentConfig.cycle?.workstreamsPerGeneration || 14))
      : [];
    const fractalOsRevision = fractalOsWorkstreams.length
      ? stableId("fractalos", JSON.stringify(fractalOsWorkstreams))
      : "disabled";
    const authorityRevision = this.contextAuthorityResolution?.resolutionId || "not-configured";
    const generationRecipe = `contextual-authority-${authorityRevision}-historical-prompts-v1-${absoluteRevision}-continuity-v6-${continuityRevision}-fractalos-${fractalOsRevision}`;
    const requestKey = stableId("backlog", [
      generationRecipe,
      requests.map((entry) => [
        entry.name,
        entry.value.createdAt,
        entry.value.laneId,
        entry.value.partition?.id,
        entry.value.focus
      ].join(":")).join("|")
    ].join("|"));
    const state = this.readState();
    if (state.backlogRefill.lastRequestKey === requestKey) {
      return {
        ok: true,
        status: "ALREADY_GENERATED",
        generatedTasks: state.backlogRefill.generatedTasks,
        outputPath: state.backlogRefill.outputPath,
        requestKey
      };
    }

    const fallbackSystemicTasks = [
      "implémenter les identités HUMAN et AI, rôles, plafonds L0–L7 et CASE_AUTONOMY_GRANT dans `forge-control/autonomy/control-plane.mjs`",
      "vérifier une permission fraîche par action, ressource, finalité et écosystème dans `forge-control/autonomy/control-plane.mjs`",
      "implémenter le dossier Owner, les décisions VALIDATE/REFUSE et le jeton borné de `config/owner-review-policy.json` dans `forge-control/autonomy/runtime.mjs`",
      "ajouter une revue Owner locale authentifiée sans mutation directe depuis le courriel dans `forge-control/server.mjs`",
      "implémenter l’envelope, l’idempotence, l’ordre causal et la provenance dans `forge-control/autonomy/ecosystem-fabric.mjs`",
      "implémenter retry borné, backpressure, circuit breaker, quarantaine et reprise après crash dans `forge-control/autonomy/runtime.mjs`",
      "refuser réseau externe, processus enfants, liens et écritures hors scope dans `forge-control/autonomy/isolated-implementation.mjs`",
      "bloquer et tester toute lecture inter-écosystème non accordée dans `forge-control/autonomy/ecosystem-fabric.mjs`",
      "neutraliser prompt injection et instructions issues de données non fiables dans `forge-control/autonomy/continuous-development-worker.mjs`",
      "donner aux écosystèmes numérique, scientifique, social et création leurs registres, agents, queues, mémoires et budgets isolés dans `forge-control/autonomy/ecosystem-fabric.mjs`",
      "implémenter une boucle cognitive explicable avec incertitude et dérive d’objectif dans `forge-control/autonomy/runtime.mjs`",
      "tester l’harmonie temporelle par horloges causales, séquences, délais et TTL dans `forge-control/autonomy/ecosystem-fabric.test.mjs`",
      "produire continuellement des projets dédupliqués sans gêner l’utilisateur dans `forge-control/autonomy/continuous-development-worker.mjs`",
      "après validation Owner exécuter sans micro-approbation code, documentation, tests, correction et publication uniquement dans le mandat approuvé dans `forge-control/autonomy/runtime.mjs`",
      "tester attaque, rejeu, révocation, spoofing, crash et concurrence dans `forge-control/autonomy/control-plane.test.mjs`"
    ];
    const continuityTasks = continuityWorkstreams.length
      ? continuityWorkstreams.map((entry) => {
          const targets = (entry.targetFiles || []).map((path) => `\`${path}\``).join(" et ");
          const acceptance = (entry.acceptance || []).join(", ");
          return { priority: entry.priority || "P0", text: `${entry.id} ${entry.objective} dans ${targets}; preuves attendues: ${acceptance}` };
        })
      : fallbackSystemicTasks.map((text) => ({ priority: "P0", text }));
    const absoluteTasks = absoluteWorkstreams.map((entry) => {
      const targets = [...new Set([entry.promptSource, ...(entry.targetFiles || [])])]
        .filter(Boolean)
        .map((path) => `\`${path}\``)
        .join(" et ");
      const acceptance = (entry.acceptance || []).join(", ");
      return {
        priority: "P0",
        text: `${entry.id} [${entry.promptId}] ${entry.objective} dans ${targets}; preuves fonctionnelles attendues: ${acceptance}; base historique contextuellement révisable: local, borné, test réel, rollback, aucune mutation canonique ni autorité auto-accordée`
      };
    });
    const fractalOsTasks = fractalOsWorkstreams.map((entry) => {
      const targets = (entry.targetFiles || []).map((path) => `\`${path}\``).join(" et ");
      const acceptance = (entry.acceptance || []).join(", ");
      return {
        priority: entry.priority || "P1",
        text: `${entry.id} ${entry.objective} dans ${targets}; preuves attendues: ${acceptance}; contrat FractalOS: local, isolé, non destructif et sans mutation canonique`
      };
    });
    const systemicTasks = [...continuityTasks, ...absoluteTasks, ...fractalOsTasks];
    const angles = this.absolutePriorityConfig?.priorityPolicy?.angles
      || this.developmentContinuityConfig?.cycle?.angles || [
      "architecture et contrat",
      "implémentation locale bornée",
      "tests d'échec et sécurité",
      "documentation, mesures et critères d'arrêt"
    ];
    const generationId = requestKey.replace(/^backlog-/, "");
    const tasks = [];
    let index = 0;
    for (const systemicTask of systemicTasks) {
      for (const angle of angles) {
        index += 1;
        tasks.push(
          `- ${systemicTask.priority} TASK-AUTOGEN-${generationId}-${String(index).padStart(3, "0")} — Améliorer et tester ${systemicTask.text}; angle: ${angle}.`
        );
      }
    }
    const outputPath = join(runtimeRoot, "generated-backlog.md");
    const content = [
      "# Backlog systémique généré par AIONE Autonomous Forge",
      "",
      `Génération: ${generationId}`,
      `Créée: ${iso(this.clock)}`,
      `Requêtes sources: ${requests.map((entry) => entry.name).join(", ")}`,
      "Mutation canonique autorisée: NON",
      `Recette: ${generationRecipe}`,
      `Bases historiques 4 prompts: ${absoluteWorkstreams.length}`,
      `Résolution d'autorité contextuelle: ${authorityRevision}`,
      `Interfaces OpenWebUI/LobeHub: ${this.absolutePriorityProgram.interfaceActivation.effectiveStatus}`,
      `Lots FractalOS 24/7: ${fractalOsWorkstreams.length}`,
      "",
      ...tasks,
      ""
    ].join("\n");
    atomicText(outputPath, content);
    state.backlogRefill = {
      lastRequestKey: requestKey,
      lastGeneratedAt: iso(this.clock),
      outputPath,
      generatedTasks: tasks.length,
      absolutePriorityWorkstreams: absoluteWorkstreams.length,
      contextAuthorityResolutionId: authorityRevision,
      interfaceActivation: this.absolutePriorityProgram.interfaceActivation.effectiveStatus
    };
    state.events.push({
      at: state.backlogRefill.lastGeneratedAt,
      type: "dual-gpu-backlog-refilled",
      requestKey,
      generatedTasks: tasks.length,
      absolutePriorityWorkstreams: absoluteWorkstreams.length,
      contextAuthorityResolutionId: authorityRevision,
      outputPath
    });
    this.writeState(state);
    this.memory.captureAtom("backlog-refill", {
      requestKey,
      requestCount: requests.length,
      generatedTasks: tasks.length,
      absolutePriorityWorkstreams: absoluteWorkstreams.length,
      contextAuthorityResolutionId: authorityRevision,
      outputPath
    });
    return {
      ok: true,
      status: "GENERATED",
      requestKey,
      requestCount: requests.length,
      generatedTasks: tasks.length,
      absolutePriorityWorkstreams: absoluteWorkstreams.length,
      contextAuthorityResolutionId: authorityRevision,
      interfaceActivation: this.absolutePriorityProgram.interfaceActivation.effectiveStatus,
      outputPath,
      canonicalMutation: false
    };
  }

  runBacklogRefillGuarded() {
    const lock = this.acquireCycleLock();
    if (!lock.ok) {
      return {
        ok: true,
        status: "DEFERRED_ACTIVE_CYCLE",
        generatedTasks: 0,
        lockPath: lock.path
      };
    }
    try {
      return this.runBacklogRefill();
    } finally {
      this.releaseCycleLock(lock);
    }
  }

  runLatestBackupVerification() {
    const backups = readdirSync(this.paths.backups)
      .filter((name) => name.startsWith("backup-") && existsSync(join(this.paths.backups, name, "manifest.json")))
      .sort()
      .reverse();
    if (!backups.length) return { ok: true, status: "NO_BACKUP_YET" };
    return this.verifyBackup(join(this.paths.backups, backups[0]));
  }

  async runPlanningTask(task) {
    const context = this.readWorkspaceContext([
      "AGENTS.md",
      "PRIORITY.md",
      "TASK.md",
      "KANBAN.md",
      "config/project-portfolio.json"
    ]);
    const prompt = [
      "Tu es AIONE Planner, agent local de la Forge.",
      "Prépare uniquement un plan borné et vérifiable pour la prochaine petite tâche.",
      "Interdictions: aucune modification, aucun Git en écriture, aucune installation, aucune publication externe.",
      `Tâche de planification: ${task.title}`,
      "Retourne: objectif, fichiers concernés, étapes, risques, tests, critères d'arrêt et permissions éventuellement requises.",
      "",
      context
    ].join("\n");
    const result = await this.runLocalAgentPrompt({
      model: this.config.models.fast,
      prompt,
      timeoutMs: 20 * 60 * 1000
    });
    const output = result.output;
    const reportPath = join(this.paths.reports, `${task.id}.md`);
    const temporary = `${reportPath}.${process.pid}.tmp`;
    writeFileSync(temporary, `${output}\n`, "utf8");
    renameWithRetry(temporary, reportPath);
    return {
      reportPath,
      engine: "ollama-direct",
      model: result.model,
      actualWallClockMs: result.actualWallClockMs,
      outputPreview: output.slice(0, 1000)
    };
  }

  async runCouncilMeetingTask(task) {
    const meeting = this.councilConfig?.meetings?.find((item) => item.id === task.payload.meetingId);
    if (!meeting) throw new Error(`Réunion inconnue: ${task.payload.meetingId}`);
    const relays = this.councilConfig.relay || [];
    let upstreamIds = relays.filter((relay) => relay.to === meeting.id).map((relay) => relay.from);
    if (meeting.id === "council") {
      upstreamIds = [...new Set([...upstreamIds, ...(this.councilConfig.meetings || []).map((item) => item.id)])];
    }
    const maximumContext = Number(this.councilConfig.policy?.maximumContextCharactersPerUpstream || 6000);
    const artifacts = [];
    for (const upstreamId of upstreamIds) {
      const candidates = readdirSync(this.paths.council)
        .filter((name) => name.startsWith(`${upstreamId}-`) && name.endsWith(".md"))
        .sort()
        .reverse();
      if (!candidates.length) continue;
      const path = join(this.paths.council, candidates[0]);
      artifacts.push({
        upstreamId,
        path,
        content: readFileSync(path, "utf8").slice(0, maximumContext)
      });
    }
    const context = artifacts.length
      ? artifacts.map((artifact) => `## Relais ${artifact.upstreamId}\n${artifact.content}`).join("\n\n")
      : "Aucun artefact amont disponible: produire un démarrage prudent à partir des fichiers canoniques.";
    const canonicalContext = this.readWorkspaceContext([
      "PRIORITY.md",
      "TASK.md",
      "config/project-portfolio.json",
      "config/development-capacity.json",
      "projects/fractal-formula-corpus/CORPUS_MANIFEST.json",
      "projects/fractal-formula-corpus/BACKLOG.md"
    ]);
    const prompt = [
      `Tu animes la réunion interne « ${meeting.name} » de la Forge AIONE.`,
      `But: ${meeting.purpose}`,
      `Entrées canoniques: ${(meeting.inputs || []).join("; ")}`,
      `Sorties attendues: ${(meeting.outputs || []).join("; ")}`,
      `Destinataires suivants: ${(meeting.recipients || []).join(", ")}`,
      "Lis les fichiers utiles du workspace en lecture seule.",
      "Sépare faits prouvés, hypothèses, désaccords, décisions, paquets de travail, tests, risques et questions réellement bloquantes.",
      "Chaque affirmation importante doit indiquer sa provenance. Ne masque jamais un désaccord.",
      "Interdictions: aucune modification de fichier, aucun Git en écriture, aucune installation, aucun secret, aucune publication ni action externe.",
      "Ne touche jamais C:\\Dev\\AIONE-Validation.",
      "",
      context,
      "",
      canonicalContext
    ].join("\n");
    const selectedModel = task.payload.selectedModel || meeting.model;
    const result = await this.runLocalAgentPrompt({
      model: selectedModel,
      prompt,
      timeoutMs: 30 * 60 * 1000
    });
    const output = result.output;
    const reportPath = join(this.paths.council, `${meeting.id}-${task.payload.scheduledDate || localDateKey(this.clock())}.md`);
    const temporary = `${reportPath}.${process.pid}.tmp`;
    const header = [
      `# ${meeting.name}`,
      "",
      `- Réunion: ${meeting.id}`,
      `- Date planifiée: ${task.payload.scheduledDate || localDateKey(this.clock())}`,
      `- Rôle interne: ${meeting.role}`,
      `- Modèle local: ${selectedModel}`,
      `- Relais lus: ${artifacts.map((item) => item.upstreamId).join(", ") || "aucun"}`,
      `- Destinataires: ${(meeting.recipients || []).join(", ")}`,
      "",
      "## Synthèse",
      ""
    ].join("\n");
    writeFileSync(temporary, `${header}${output}\n`, "utf8");
    renameWithRetry(temporary, reportPath);
    return {
      reportPath,
      engine: "ollama-direct",
      model: result.model,
      upstreamArtifacts: artifacts.map((item) => item.path),
      recipients: meeting.recipients || [],
      actualWallClockMs: result.actualWallClockMs,
      outputPreview: output.slice(0, 1000)
    };
  }

  async runDevelopmentWorkPackage(task) {
    const config = this.developmentCapacityConfig;
    if (!config?.enabled) throw new Error("Capacité DEV désactivée.");
    const context = this.readWorkspaceContext([
      "AGENTS.md",
      "PRIORITY.md",
      "TASK.md",
      "KANBAN.md",
      "docs/IMPLEMENTATION_BACKLOG.md",
      "docs/UNFINISHED_FEATURES_AUDIT.md",
      "config/project-portfolio.json",
      "projects/fractal-formula-corpus/BACKLOG.md"
    ]);
    const prompt = [
      "Tu exécutes un paquet de capacité DEV interne pour AIONE Autonomous Forge.",
      `Projet prioritaire: ${task.projectId}`,
      `Axe: ${task.payload.focus}`,
      `Source anti-file-vide: ${task.payload.source}`,
      `Valeur comptable: ${task.payload.nominalAgentHours} heure(s)-agent nominale(s), distincte(s) du temps réel.`,
      `Raison de disponibilité: ${task.payload.readinessReason || "non fournie"}`,
      `Sources de backlog: ${(config.backlogSources || []).join("; ")}`,
      "Produis un diagnostic prouvé, un petit lot de code proposé, les tests à exécuter, les critères de validation, les risques et la prochaine action exacte.",
      "Tu peux lire le code et les résultats existants. Tu peux exécuter uniquement des diagnostics et tests existants non destructifs.",
      "Le laboratoire d'écriture isolé n'est pas encore validé: ne modifie aucun fichier, aucune branche et aucun worktree.",
      "Interdictions: Git en écriture, installation, téléchargement de modèle, secret, réseau externe, publication, mail ou calendrier.",
      "Ne touche jamais C:\\Dev\\AIONE-Validation.",
      "S'il semble ne rien y avoir à faire, audite les lacunes de tests, sécurité, documentation, dette, corpus et robustesse; une sortie vide est un échec.",
      "",
      context
    ].join("\n");
    const selectedModel = task.payload.selectedModel || this.config.models.fast;
    const result = await this.runLocalAgentPrompt({
      model: selectedModel,
      prompt,
      timeoutMs: 30 * 60 * 1000
    });
    const output = result.output;
    if (!output) throw new Error("Le paquet DEV n'a produit aucune preuve ni proposition.");
    const reportPath = join(this.paths.reports, `${task.id}.md`);
    const temporary = `${reportPath}.${process.pid}.tmp`;
    const elapsed = result.actualWallClockMs;
    const header = [
      `# Paquet DEV — ${task.payload.focus}`,
      "",
      `- Projet: ${task.projectId}`,
      `- Source: ${task.payload.source}`,
      `- Heures-agent nominales: ${task.payload.nominalAgentHours}`,
      `- Modèle local: ${task.payload.selectedModel || this.config.models.fast}`,
      `- Temps réel mesuré (ms): ${elapsed}`,
      "- Mode: analyse, diagnostic, tests existants et préparation de code",
      "- Mutation de dépôt: interdite jusqu'à validation du runner isolé",
      "",
      "## Résultat",
      ""
    ].join("\n");
    writeFileSync(temporary, `${header}${output}\n`, "utf8");
    renameWithRetry(temporary, reportPath);
    return {
      reportPath,
      engine: "ollama-direct",
      model: result.model,
      focus: task.payload.focus,
      nominalAgentHours: Number(task.payload.nominalAgentHours || 0),
      actualWallClockMs: elapsed,
      mutationPerformed: false,
      outputPreview: output.slice(0, 1000)
    };
  }

  async runValidationTask(task) {
    const project = this.config.projects.find((item) => item.id === task.projectId && item.enabled);
    if (!project) throw new Error(`Projet inconnu ou désactivé: ${task.projectId}`);
    const selected = project.validationCommands[Number(task.payload.commandIndex || 0)];
    if (!selected) throw new Error("Commande de validation non allowlistée.");
    const result = await this.commandRunner(selected.command, selected.args || [], {
      cwd: project.path,
      timeoutMs: selected.timeoutMs || 180000
    });
    return {
      command: [selected.command, ...(selected.args || [])].join(" "),
      stdout: String(result.stdout || "").slice(-5000),
      stderr: String(result.stderr || "").slice(-5000)
    };
  }

  async handleFailure(failure, cycleId) {
    const state = this.readState();
    const signature = stableId("incident", `${failure.id}:${failure.code || "availability"}`);
    for (const [previousSignature, previousIncident] of Object.entries(state.incidents)) {
      if (
        previousSignature === signature
        || previousIncident.serviceId !== failure.id
        || previousIncident.status === "RESOLVED"
      ) continue;
      previousIncident.status = "RESOLVED";
      previousIncident.resolvedAt = iso(this.clock);
      previousIncident.resolutionReason = "SUPERSEDED_BY_STABLE_INCIDENT_SIGNATURE";
      previousIncident.supersededBy = signature;
      state.incidents[previousSignature] = previousIncident;
      state.events.push({
        at: previousIncident.resolvedAt,
        type: "incident-superseded",
        incidentId: previousSignature,
        supersededBy: signature,
        serviceId: failure.id
      });
      atomicJson(join(this.paths.incidents, `${previousIncident.id}.json`), previousIncident);
      this.writeIncidentMarkdown(previousIncident);
    }
    const existing = state.incidents[signature];
    const incident = existing || {
      schema: "aione.major-failure-incident.v1",
      id: signature,
      serviceId: failure.id,
      label: failure.label,
      critical: Boolean(failure.critical),
      status: "OPEN",
      episodes: 1,
      firstSeenAt: iso(this.clock),
      lastSeenAt: iso(this.clock),
      occurrences: 0,
      localRepairAttempts: 0,
      codexInvocations: 0,
      cycleIds: [],
      error: failure.error
    };
    const previousCritical = existing ? Boolean(incident.critical) : Boolean(failure.critical);
    incident.serviceId = failure.id;
    incident.label = failure.label;
    incident.critical = Boolean(failure.critical);
    incident.error = failure.error;
    const reclassified = Boolean(existing && previousCritical !== incident.critical);
    const reopened = Boolean(existing && incident.status === "RESOLVED");
    if (reopened) {
      incident.status = "OPEN";
      incident.episodes = Number(incident.episodes || 1) + 1;
      incident.reopenedAt = iso(this.clock);
      incident.previousResolvedAt = incident.resolvedAt || null;
      incident.localRepairAttempts = 0;
      incident.codexInvocations = 0;
      delete incident.resolvedAt;
      delete incident.resolvedByCycle;
      delete incident.lastRepairAt;
      delete incident.lastRepair;
      delete incident.recheck;
    }
    incident.occurrences += 1;
    incident.lastSeenAt = iso(this.clock);
    incident.cycleIds.push(cycleId);
    incident.cycleIds = incident.cycleIds.slice(-20);
    state.incidents[signature] = incident;
    state.events.push({
      at: incident.lastSeenAt,
      type: reopened ? "incident-reopened" : "incident-open",
      incidentId: signature,
      serviceId: failure.id
    });
    if (reclassified) {
      state.events.push({
        at: incident.lastSeenAt,
        type: "incident-reclassified",
        incidentId: signature,
        serviceId: failure.id,
        previousCritical,
        critical: incident.critical
      });
    }
    this.writeState(state);

    const serviceConfig = this.config.services.find((service) => service.id === failure.id);
    if (incident.critical && serviceConfig?.repair && this.canAttemptRepair(incident)) {
      const repair = await this.attemptRepair(serviceConfig, incident);
      incident.localRepairAttempts += 1;
      incident.lastRepairAt = iso(this.clock);
      incident.lastRepair = repair;
      const updatedState = this.readState();
      updatedState.metrics.repairsAttempted += 1;
      updatedState.incidents[signature] = incident;
      this.writeState(updatedState);
      if (repair.ok) {
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 1200));
        const recheck = await this.checkService(serviceConfig);
        incident.recheck = recheck;
        if (recheck.ok) {
          incident.status = "RESOLVED";
          incident.resolvedAt = iso(this.clock);
        }
      }
    }

    const incidentPath = join(this.paths.incidents, `${incident.id}.json`);
    atomicJson(incidentPath, incident);
    this.writeIncidentMarkdown(incident);
    if (incident.critical && incident.status !== "RESOLVED" && !this.canAttemptRepair(incident)) {
      await this.maybeInvokeCodex(incident);
    }
    const finalState = this.readState();
    finalState.incidents[signature] = incident;
    this.writeState(finalState);
    atomicJson(incidentPath, incident);
    return incident;
  }

  resolveHealthyIncidents(healthyServices, cycleId) {
    const healthyIds = new Set(healthyServices.map((service) => service.id));
    if (healthyIds.size === 0) return [];
    const state = this.readState();
    const resolved = [];
    for (const incident of Object.values(state.incidents)) {
      if (incident.status === "RESOLVED" || !healthyIds.has(incident.serviceId)) continue;
      incident.status = "RESOLVED";
      incident.resolvedAt = iso(this.clock);
      incident.resolvedByCycle = cycleId;
      state.incidents[incident.id] = incident;
      state.events.push({
        at: incident.resolvedAt,
        type: "incident-resolved",
        incidentId: incident.id,
        serviceId: incident.serviceId,
        cycleId
      });
      atomicJson(join(this.paths.incidents, `${incident.id}.json`), incident);
      this.writeIncidentMarkdown(incident);
      resolved.push(incident.id);
    }
    if (resolved.length > 0) this.writeState(state);
    return resolved;
  }

  canAttemptRepair(incident) {
    const maximum = Number(this.config.guardian.maximumLocalRepairAttempts || 0);
    if (incident.localRepairAttempts >= maximum) return false;
    if (!incident.lastRepairAt) return true;
    const cooldown = Number(this.config.guardian.repairCooldownMinutes || 30) * 60000;
    return this.clock().getTime() - new Date(incident.lastRepairAt).getTime() >= cooldown;
  }

  async attemptRepair(service, incident) {
    const repair = service.repair;
    if (repair.kind !== "start-process") return { ok: false, reason: "repair-kind-not-allowlisted" };
    try {
      const command = executableCandidates(repair.command)[0] || repair.command;
      const child = spawn(command, repair.args || [], {
        cwd: this.root,
        detached: true,
        windowsHide: true,
        stdio: "ignore"
      });
      child.unref();
      return { ok: true, kind: repair.kind, command: repair.command, pid: child.pid, incidentId: incident.id };
    } catch (error) {
      return { ok: false, kind: repair.kind, error: error instanceof Error ? error.message : String(error) };
    }
  }

  writeIncidentMarkdown(incident) {
    const path = join(this.paths.incidents, `${incident.id}.md`);
    const text = [
      `# Incident majeur ${incident.id}`,
      "",
      `- Service: ${incident.label} (${incident.serviceId})`,
      `- Critique: ${incident.critical ? "oui" : "non"}`,
      `- Statut: ${incident.status}`,
      `- Première détection: ${incident.firstSeenAt}`,
      `- Dernière détection: ${incident.lastSeenAt}`,
      `- Occurrences: ${incident.occurrences}`,
      `- Réparations locales: ${incident.localRepairAttempts}`,
      `- Appels Codex: ${incident.codexInvocations}`,
      "",
      "## Erreur",
      "",
      "```text",
      String(incident.error || ""),
      "```",
      "",
      "## Politique",
      "",
      "Le cycle défectueux reste isolé. Aucune suppression, publication, écriture Git ou action externe n'est autorisée.",
      ""
    ].join("\n");
    const temporary = `${path}.${process.pid}.tmp`;
    writeFileSync(temporary, text, "utf8");
    renameWithRetry(temporary, path);
    return path;
  }

  async maybeInvokeCodex(incident) {
    const codex = this.config.guardian.codex || {};
    const maximum = Number(this.config.guardian.maximumCodexInvocationsPerIncident || 0);
    const flagName = codex.requiredEnvironmentFlag;
    const allowedByFlag = !flagName || process.env[flagName] === "1";
    const recoveryPromptPath = join(this.paths.recovery, `${incident.id}-prompt.md`);
    const recoveryOutputPath = join(this.paths.recovery, `${incident.id}-codex-result.md`);
    const prompt = [
      "Tu es le dernier niveau de récupération de la Forge AIONE.",
      `Incident: ${incident.id}`,
      `Service: ${incident.label}`,
      `Erreur: ${incident.error}`,
      `Workspace: ${this.root}`,
      "Commence en lecture seule. Préserve les données.",
      "Tente uniquement une correction locale sûre et minimale dans le workspace.",
      "Interdictions: suppression, Git en écriture, dépendance, publication, mail, action distante, accès à C:\\Dev\\AIONE-Validation.",
      "Lance les tests ciblés puis rends un rapport exact. Ne relance jamais Codex."
    ].join("\n");
    writeFileSync(recoveryPromptPath, `${prompt}\n`, "utf8");

    if (!codex.enabled || !allowedByFlag || incident.codexInvocations >= maximum) {
      incident.codexRecovery = {
        invoked: false,
        promptPath: recoveryPromptPath,
        reason: !allowedByFlag ? `environment-flag-required:${flagName}=1` : "disabled-or-circuit-open"
      };
      return incident.codexRecovery;
    }

    try {
      const args = ["exec"];
      if (codex.ephemeral) args.push("--ephemeral");
      args.push("--sandbox", codex.sandbox || "workspace-write", "-o", recoveryOutputPath, prompt);
      const result = await this.commandRunner("codex", args, { cwd: this.root, timeoutMs: 30 * 60 * 1000 });
      incident.codexInvocations += 1;
      incident.codexRecovery = {
        invoked: true,
        ok: true,
        outputPath: recoveryOutputPath,
        stdoutPreview: String(result.stdout || "").slice(-2000)
      };
      const state = this.readState();
      state.metrics.codexInvocations += 1;
      this.writeState(state);
    } catch (error) {
      incident.codexInvocations += 1;
      incident.codexRecovery = {
        invoked: true,
        ok: false,
        outputPath: recoveryOutputPath,
        error: error instanceof Error ? error.message : String(error)
      };
    }
    return incident.codexRecovery;
  }
}

export function createAutonomyRuntime(options = {}) {
  return new LocalAutonomyRuntime(options);
}

export { defaultCommandRunner, expandEnvironmentPath };
