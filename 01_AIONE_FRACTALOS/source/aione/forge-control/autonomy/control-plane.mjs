import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync
} from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve, sep } from "node:path";
import { EcosystemFabric } from "./ecosystem-fabric.mjs";

function expandEnvironmentPath(value) {
  return resolve(String(value || "").replace(/%([^%]+)%/g, (_, name) => process.env[name] || `%${name}%`));
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function defaultCommandRunner(command, args = [], options = {}) {
  try {
    return {
      ok: true,
      stdout: execFileSync(command, args, {
        cwd: options.cwd,
        encoding: "utf8",
        timeout: options.timeoutMs || 5000,
        windowsHide: true,
        maxBuffer: options.maxBuffer || 4 * 1024 * 1024,
        stdio: ["ignore", "pipe", "pipe"]
      }),
      stderr: ""
    };
  } catch (error) {
    return {
      ok: false,
      stdout: String(error?.stdout || ""),
      stderr: String(error?.stderr || error?.message || error)
    };
  }
}

function redact(value, redactKeys) {
  if (Array.isArray(value)) return value.map((item) => redact(item, redactKeys));
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => {
    const sensitive = redactKeys.some((pattern) => key.toLowerCase().includes(pattern.toLowerCase()));
    return [key, sensitive ? "[REDACTED]" : redact(item, redactKeys)];
  }));
}

function ruleMatches(action, rule) {
  return action === rule || action.startsWith(`${rule}.`);
}

function withinPath(target, root) {
  const normalizedTarget = resolve(target).toLowerCase();
  const normalizedRoot = resolve(root).toLowerCase();
  return normalizedTarget === normalizedRoot || normalizedTarget.startsWith(`${normalizedRoot}${sep}`);
}

function measured(id, items, extra = {}) {
  return { id, status: "MEASURED", count: items.length, items, ...extra };
}

function unmeasured(id, reason) {
  return { id, status: "UNMEASURED", count: null, items: [], reason };
}

function localOllamaModels() {
  const profile = process.env.USERPROFILE || process.env.HOME || "";
  const library = join(profile, ".ollama", "models", "manifests", "registry.ollama.ai", "library");
  if (!profile || !existsSync(library)) return [];
  const models = [];
  for (const model of readdirSync(library, { withFileTypes: true })) {
    if (!model.isDirectory()) continue;
    const modelRoot = join(library, model.name);
    for (const tag of readdirSync(modelRoot, { withFileTypes: true })) {
      if (tag.isFile()) models.push(`${model.name}:${tag.name}`);
    }
  }
  return models.sort();
}

export class ControlPlaneRuntime {
  constructor({
    root = resolve(process.cwd()),
    registryPath = join(root, "config", "capability-registry.json"),
    permissionPath = join(root, "config", "permission-broker.json"),
    roadmapPath = join(root, "config", "integration-roadmap.json"),
    portfolioPath = join(root, "config", "project-portfolio.json"),
    githubPath = join(root, "config", "github-exploration.json"),
    fabricConfigPath = join(root, "config", "ecosystem-fabric.json"),
    stateDir,
    clock = () => new Date(),
    commandRunner = defaultCommandRunner
  } = {}) {
    this.root = resolve(root);
    this.registryPath = resolve(registryPath);
    this.permissionPath = resolve(permissionPath);
    this.roadmapPath = resolve(roadmapPath);
    this.portfolioPath = resolve(portfolioPath);
    this.githubPath = resolve(githubPath);
    this.fabricConfigPath = resolve(fabricConfigPath);
    this.registry = JSON.parse(readFileSync(this.registryPath, "utf8"));
    this.permissions = JSON.parse(readFileSync(this.permissionPath, "utf8"));
    this.roadmap = JSON.parse(readFileSync(this.roadmapPath, "utf8"));
    this.portfolio = readJson(this.portfolioPath, { projects: [] });
    this.github = readJson(this.githubPath, { categories: [] });
    this.fabricConfig = readJson(this.fabricConfigPath, {
      enabled: true,
      namespace: "aione",
      shardCount: 256,
      bootstrap: []
    });
    this.clock = clock;
    this.commandRunner = commandRunner;
    this.stateDir = stateDir
      ? resolve(stateDir)
      : resolve(dirname(this.root), "Runtime", "ControlPlane");
    this.paths = {
      ledger: join(this.stateDir, "evidence-ledger.jsonl"),
      autonomyState: join(dirname(this.stateDir), "ForgeAutonomy", "state.json"),
      memoryIndex: join(dirname(this.stateDir), "ForgeAutonomy", "memory", "index.json"),
      backups: join(dirname(this.stateDir), "ForgeAutonomy", "backups"),
      fabric: this.fabricConfig.databasePath
        ? expandEnvironmentPath(this.fabricConfig.databasePath)
        : join(this.stateDir, "ecosystem-fabric.sqlite")
    };
    mkdirSync(this.stateDir, { recursive: true });
    this.fabric = new EcosystemFabric({
      databasePath: this.paths.fabric,
      namespace: this.fabricConfig.namespace || "aione",
      shardCount: this.fabricConfig.shardCount || 256,
      actorId: this.registry.controller.id,
      rootPolicy: this.fabricConfig.rootPolicy,
      clock: this.clock
    });
    this.bootstrapFabric();
  }

  bootstrapFabric() {
    const references = new Map();
    const results = [];
    for (const entry of this.fabricConfig.bootstrap || []) {
      const parentId = entry.parentRef ? references.get(entry.parentRef) : entry.parentId;
      if (entry.parentRef && !parentId) {
        throw new Error(`Reference de parent introuvable dans ecosystem-fabric.json: ${entry.parentRef}`);
      }
      const result = this.fabric.registerNode({ ...entry, parentId });
      if (entry.ref) references.set(entry.ref, result.node.id);
      const contextResult = entry.context
        ? this.fabric.updateContext(result.node.id, entry.context)
        : { changed: false };
      results.push({ ref: entry.ref || null, id: result.node.id, created: result.created });
      results.at(-1).contextUpdated = contextResult.changed;
    }
    return results;
  }

  close() {
    this.fabric?.close();
  }

  audit() {
    const issues = [];
    const engineIds = this.registry.engines.map((item) => item.id);
    const capabilityIds = this.registry.capabilities.map((item) => item.id);
    const validStatuses = new Set(this.registry.statuses);
    for (const [kind, ids] of [["engine", engineIds], ["capability", capabilityIds]]) {
      const seen = new Set();
      for (const id of ids) {
        if (seen.has(id)) issues.push({ code: "duplicate-id", kind, id });
        seen.add(id);
      }
    }
    for (const item of [...this.registry.engines, ...this.registry.capabilities]) {
      if (!validStatuses.has(item.status)) issues.push({ code: "invalid-status", id: item.id, status: item.status });
    }
    if (this.registry.controller.agentIdentityCount !== 1) {
      issues.push({ code: "central-controller-count", actual: this.registry.controller.agentIdentityCount });
    }
    const permissionSets = ["allow", "ask", "deny"].map((key) => new Set(this.permissions[key] || []));
    for (const rule of permissionSets[0]) {
      if (permissionSets[1].has(rule) || permissionSets[2].has(rule)) {
        issues.push({ code: "permission-overlap", rule });
      }
    }
    for (const rule of permissionSets[1]) {
      if (permissionSets[2].has(rule)) issues.push({ code: "permission-overlap", rule });
    }
    const ledger = this.verifyLedger();
    if (!ledger.ok) issues.push(...ledger.issues.map((item) => ({ code: "ledger", ...item })));
    const fabric = this.fabric.verifyEventChains();
    if (!fabric.ok) issues.push(...fabric.issues.map((item) => ({ code: "ecosystem-fabric", ...item })));
    return {
      ok: issues.length === 0,
      controller: this.registry.controller,
      engineCount: this.registry.engines.length,
      capabilityCount: this.registry.capabilities.length,
      waveCount: this.roadmap.waves.length,
      ledger,
      fabric,
      issues
    };
  }

  status() {
    const audit = this.audit();
    const byStatus = [...this.registry.engines, ...this.registry.capabilities].reduce((result, item) => {
      result[item.status] = (result[item.status] || 0) + 1;
      return result;
    }, {});
    return {
      ok: audit.ok,
      mode: this.registry.controller.topology,
      controller: this.registry.controller,
      engines: this.registry.engines.length,
      capabilities: this.registry.capabilities.length,
      statuses: byStatus,
      permissionDefault: this.permissions.defaultDecision,
      evidence: audit.ledger,
      ecosystemFabric: this.fabric.summary(),
      stateDir: this.stateDir
    };
  }

  authorize({ action, targetPath = "", actor = "aione-autonomous-forge", metadata = {} } = {}) {
    const normalizedAction = String(action || "").trim().toLowerCase();
    if (!normalizedAction) throw new Error("Action requise.");
    let decision = this.permissions.defaultDecision || "ASK";
    let reason = "default-policy";
    if (targetPath && (this.permissions.protectedPaths || []).some((path) => withinPath(targetPath, path))) {
      decision = "DENY";
      reason = "protected-path";
    } else if ((this.permissions.deny || []).some((rule) => ruleMatches(normalizedAction, rule))) {
      decision = "DENY";
      reason = "explicit-deny";
    } else if ((this.permissions.ask || []).some((rule) => ruleMatches(normalizedAction, rule))) {
      decision = "ASK";
      reason = "human-approval-required";
    } else if ((this.permissions.allow || []).some((rule) => ruleMatches(normalizedAction, rule))) {
      decision = "ALLOW";
      reason = "standing-local-approval";
    }
    if (
      decision === "ALLOW" &&
      targetPath &&
      !(this.permissions.allowedRoots || []).some((path) => withinPath(targetPath, path))
    ) {
      decision = "ASK";
      reason = "outside-allowed-roots";
    }
    const now = this.clock();
    const result = {
      action: normalizedAction,
      targetPath: targetPath || null,
      actor,
      decision,
      reason,
      decidedAt: now.toISOString(),
      expiresAt: new Date(now.getTime() + Number(this.permissions.decisionTTLSeconds || 300) * 1000).toISOString(),
      requireFreshDecisionAtCommit: this.permissions.requireFreshDecisionAtCommit === true
    };
    const evidence = this.recordEvidence({
      eventType: "authorization-decision",
      actor,
      action: normalizedAction,
      target: targetPath || null,
      decision,
      status: decision === "ALLOW" ? "AUTHORIZED" : decision,
      metadata
    });
    return { ...result, evidenceId: evidence.id };
  }

  recordEvidence(entry = {}) {
    const records = this.readLedger();
    const previousHash = records.at(-1)?.hash || null;
    const sanitized = redact(entry, this.permissions.redactKeys || []);
    const record = {
      schema: "aione.evidence-ledger-entry.v1",
      id: `ev-${this.clock().toISOString().replace(/[-:.TZ]/g, "")}-${randomUUID().slice(0, 8)}`,
      at: this.clock().toISOString(),
      eventType: sanitized.eventType || "observation",
      actor: sanitized.actor || this.registry.controller.id,
      action: sanitized.action || null,
      target: sanitized.target || null,
      decision: sanitized.decision || null,
      status: sanitized.status || "RECORDED",
      durationMs: Number.isFinite(sanitized.durationMs) ? sanitized.durationMs : null,
      proofs: Array.isArray(sanitized.proofs) ? sanitized.proofs.slice(0, 40) : [],
      metadata: sanitized.metadata && typeof sanitized.metadata === "object" ? sanitized.metadata : {},
      previousHash
    };
    record.hash = sha256(JSON.stringify(record));
    mkdirSync(dirname(this.paths.ledger), { recursive: true });
    appendFileSync(this.paths.ledger, `${JSON.stringify(record)}\n`, "utf8");
    return record;
  }

  readLedger(limit = 1000) {
    if (!existsSync(this.paths.ledger)) return [];
    const lines = readFileSync(this.paths.ledger, "utf8")
      .split(/\r?\n/)
      .filter(Boolean)
      .slice(-Math.max(1, Math.min(Number(limit) || 1000, 10000)));
    const records = [];
    for (const line of lines) {
      try {
        records.push(JSON.parse(line));
      } catch {
        // The verifier reports malformed lines. Readers stay available for incident recovery.
      }
    }
    return records;
  }

  evidence(limit = 100) {
    const entries = this.readLedger(limit);
    return { entries, verification: this.verifyLedger() };
  }

  verifyLedger() {
    if (!existsSync(this.paths.ledger)) return { ok: true, entries: 0, head: null, issues: [] };
    const issues = [];
    let previousHash = null;
    const lines = readFileSync(this.paths.ledger, "utf8").split(/\r?\n/).filter(Boolean);
    for (let index = 0; index < lines.length; index += 1) {
      let record;
      try {
        record = JSON.parse(lines[index]);
      } catch {
        issues.push({ index, code: "invalid-json" });
        continue;
      }
      const hash = record.hash;
      const unsigned = { ...record };
      delete unsigned.hash;
      if (sha256(JSON.stringify(unsigned)) !== hash) issues.push({ index, code: "hash-mismatch", id: record.id });
      if (record.previousHash !== previousHash) issues.push({ index, code: "chain-mismatch", id: record.id });
      previousHash = hash;
    }
    return { ok: issues.length === 0, entries: lines.length, head: previousHash, issues };
  }

  probeEngine(engine, dockerRows = []) {
    const probe = engine.probe || {};
    if (probe.kind === "self") {
      return { detected: true, evidence: probe.target || this.registry.controller.id };
    }
    if (probe.kind === "command") {
      const result = this.commandRunner("where.exe", [probe.target], { timeoutMs: 3000 });
      return { detected: result.ok && Boolean(result.stdout.trim()), evidence: result.ok ? result.stdout.trim().split(/\r?\n/)[0] : null };
    }
    if (probe.kind === "package") {
      const packagePath = join(process.env.LOCALAPPDATA || "", "AIONE", "BuildDeps", "node_modules", ...probe.target.split("/"), "package.json");
      return { detected: existsSync(packagePath), evidence: existsSync(packagePath) ? packagePath : null };
    }
    if (probe.kind === "node-builtin") {
      const script = probe.feature === "fts5"
        ? `import('${probe.target}').then(({DatabaseSync})=>{const db=new DatabaseSync(':memory:');db.exec('CREATE VIRTUAL TABLE aione_fts USING fts5(value)');db.close();}).then(()=>process.exit(0)).catch(()=>process.exit(1))`
        : `import('${probe.target}').then(()=>process.exit(0)).catch(()=>process.exit(1))`;
      const result = this.commandRunner(process.execPath, ["--no-warnings", "-e", script], { timeoutMs: 3000 });
      return { detected: result.ok, evidence: result.ok ? `${probe.target}${probe.feature ? `:${probe.feature}` : ""}` : null };
    }
    if (probe.kind === "docker-image") {
      const row = dockerRows.find((item) => String(item.Image || "").toLowerCase().includes(String(probe.target).toLowerCase()));
      return { detected: Boolean(row), evidence: row ? `${row.Image}:${row.State}` : null };
    }
    if (probe.kind === "docker-label") {
      const row = dockerRows.find((item) => String(item.Labels || "").includes(probe.target));
      return { detected: Boolean(row), evidence: row ? `${row.Names}:${row.State}` : null };
    }
    return { detected: null, evidence: "not-probed" };
  }

  dockerInventory() {
    const result = this.commandRunner("docker", ["ps", "-a", "--format", "{{json .}}"], { timeoutMs: 10000 });
    if (!result.ok) return [];
    return result.stdout.split(/\r?\n/).filter(Boolean).map((line) => {
      try {
        const item = JSON.parse(line);
        return {
          ID: item.ID,
          Names: item.Names,
          Image: item.Image,
          State: item.State,
          Status: item.Status,
          Ports: item.Ports,
          Labels: item.Labels
        };
      } catch {
        return null;
      }
    }).filter(Boolean);
  }

  inventory() {
    const dockerRows = this.dockerInventory();
    const engines = this.registry.engines.map((engine) => ({
      id: engine.id,
      category: engine.category,
      declaredStatus: engine.status,
      ...this.probeEngine(engine, dockerRows)
    }));
    const dualGpu = readJson(join(this.root, "config", "dual-gpu-development.json"), null);
    let models;
    if (dualGpu?.enabled === true) {
      // Ollama 0.32 peut auto-démarrer un serveur générique lors de `ollama list`.
      // En mode dual-GPU, l'inventaire lit les manifestes afin de ne jamais voler le port 11434.
      models = localOllamaModels();
    } else {
      const modelsResult = this.commandRunner("ollama", ["list"], { timeoutMs: 5000 });
      models = modelsResult.ok
        ? modelsResult.stdout.split(/\r?\n/).slice(1).map((line) => line.trim().split(/\s{2,}/)[0]).filter(Boolean)
        : [];
    }
    const gpuResult = this.commandRunner("nvidia-smi", ["--query-gpu=name,memory.total", "--format=csv,noheader"], { timeoutMs: 5000 });
    const gpus = gpuResult.ok
      ? gpuResult.stdout.split(/\r?\n/).filter(Boolean).map((line, index) => ({ id: index, value: line.trim() }))
      : [];
    const portsResult = this.commandRunner("netstat.exe", ["-ano", "-p", "tcp"], { timeoutMs: 5000 });
    const ports = portsResult.ok
      ? portsResult.stdout.split(/\r?\n/).map((line) => line.trim().match(/^TCP\s+(\S+)\s+\S+\s+LISTENING\s+(\d+)$/i)).filter(Boolean)
        .map((match) => ({ endpoint: match[1], pid: Number(match[2]) }))
      : [];
    const tasksResult = this.commandRunner("powershell.exe", [
      "-NoProfile",
      "-Command",
      "Get-ScheduledTask | Where-Object TaskName -Like 'AIONE*' | Select-Object TaskName,State | ConvertTo-Json -Compress"
    ], { timeoutMs: 10000 });
    let scheduledTasks = [];
    if (tasksResult.ok && tasksResult.stdout.trim()) {
      try {
        const parsed = JSON.parse(tasksResult.stdout);
        scheduledTasks = (Array.isArray(parsed) ? parsed : [parsed]).map((item) => ({
          name: item.TaskName,
          state: typeof item.State === "number" ? String(item.State) : item.State
        }));
      } catch {
        scheduledTasks = [];
      }
    }
    const memory = readJson(this.paths.memoryIndex, { atoms: [], tiles: [], kiloTiles: [], megaTiles: [], gigaTiles: [] });
    const autonomy = readJson(this.paths.autonomyState, null);
    const snapshots = existsSync(this.paths.backups)
      ? readdirSync(this.paths.backups).filter((name) => name.startsWith("backup-")).map((name) => {
        const path = join(this.paths.backups, name);
        return { name, updatedAt: statSync(path).mtime.toISOString() };
      }).sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
      : [];
    return {
      generatedAt: this.clock().toISOString(),
      engines,
      projects: this.portfolio.projects,
      models,
      gpus,
      ports,
      scheduledTasks,
      containers: dockerRows.map(({ Labels, ...item }) => item),
      mcps: dockerRows.filter((item) => String(item.Labels || "").includes("mcp.")).map((item) => ({
        name: item.Names,
        image: item.Image,
        state: item.State,
        ports: item.Ports
      })),
      memory: {
        atoms: memory.atoms?.length || 0,
        tiles: memory.tiles?.length || 0,
        kiloTiles: memory.kiloTiles?.length || 0,
        megaTiles: memory.megaTiles?.length || 0,
        gigaTiles: memory.gigaTiles?.length || 0
      },
      autonomy: autonomy ? {
        paused: autonomy.paused,
        lastCycle: autonomy.lastCycle,
        incidents: Object.values(autonomy.incidents || {}),
        metrics: autonomy.metrics
      } : null,
      snapshots
    };
  }

  lists() {
    const inventory = this.inventory();
    const capabilities = this.registry.capabilities;
    const currentProjects = inventory.projects.filter((item) => item.category === "CURRENT");
    const nonOperational = this.registry.engines.filter((item) => !["OPERATIONAL", "AVAILABLE_GUARDED"].includes(item.status));
    const incidents = inventory.autonomy?.incidents || [];
    const githubRepositories = (this.github.categories || []).flatMap((category) =>
      (category.repositories || []).map((repository) => ({ category: category.id, ...repository }))
    );
    return {
      schema: "aione.system-list-catalog.v1",
      generatedAt: inventory.generatedAt,
      reality: [
        measured("projects-present", currentProjects),
        measured("canonical-and-historical-projects", inventory.projects),
        measured("software-detected", inventory.engines.filter((item) => item.detected === true)),
        measured("services-known", inventory.engines.filter((item) => ["OPERATIONAL", "AVAILABLE_GUARDED"].includes(item.declaredStatus))),
        measured("open-ports", inventory.ports),
        measured("ollama-models", inventory.models),
        measured("gpus", inventory.gpus),
        measured("windows-scheduled-tasks", inventory.scheduledTasks),
        measured("docker-containers", inventory.containers),
        measured("mcp-detected", inventory.mcps)
      ],
      capabilities: [
        measured("capabilities-operational", capabilities.filter((item) => item.status === "OPERATIONAL")),
        measured("capabilities-believed-untested", capabilities.filter((item) => ["PARTIAL", "AVAILABLE_GUARDED"].includes(item.status))),
        measured("capabilities-not-available", capabilities.filter((item) => ["PLANNED", "STANDBY"].includes(item.status))),
        measured("capabilities-partial", capabilities.filter((item) => item.status === "PARTIAL")),
        unmeasured("capabilities-without-ui", "UI coverage needs a dedicated route-to-surface audit."),
        unmeasured("capabilities-without-tests", "Per-capability test linkage is not complete yet."),
        unmeasured("capabilities-without-docs", "Per-capability documentation linkage is not complete yet."),
        unmeasured("capabilities-duplicated", "Semantic duplicate analysis is not implemented yet."),
        measured("capabilities-unused", capabilities.filter((item) => ["PLANNED", "STANDBY"].includes(item.status))),
        measured("capabilities-dangerous-or-obsolete", this.registry.engines.filter((item) => item.status === "REJECT_NOW"))
      ],
      permissions: [
        measured("actions-autonomous", this.permissions.allow),
        measured("actions-requiring-go", this.permissions.ask),
        measured("actions-forbidden", this.permissions.deny),
        measured("actions-reversible", this.permissions.allow.filter((item) => !item.includes("write"))),
        measured("actions-irreversible", this.permissions.deny),
        unmeasured("secrets-accessible", "Secrets are deliberately not enumerated."),
        measured("tools-that-can-send-data", this.registry.engines.filter((item) => ["tool-bus", "automation", "private-network"].includes(item.category))),
        measured("tools-that-can-modify-files", this.registry.engines.filter((item) => ["development", "automation"].includes(item.category))),
        measured("tools-that-can-run-commands", this.registry.engines.filter((item) => ["development", "automation", "component-runtime"].includes(item.category))),
        measured("tools-that-can-contact-people", this.permissions.ask.filter((item) => /mail|calendar|publication|trello|notion/.test(item)))
      ],
      memory: [
        measured("tile-types", ["atom", "unitile", "tile", "kilo-tile", "mega-tile", "giga-tile"]),
        measured("compression-levels", Object.entries(inventory.memory).map(([level, count]) => ({ level, count }))),
        unmeasured("tile-sources", "Source linkage exists per tile but requires a bounded export."),
        unmeasured("contradictory-tiles", "Contradiction detector is planned."),
        unmeasured("stale-tiles", "Knowledge decay policy is planned."),
        unmeasured("never-reused-tiles", "Reuse counters are not yet linked per tile."),
        unmeasured("tile-dependencies", "TileGraph dependency edges are partial."),
        measured("context-levels", ["unitile", "tile", "kilotile", "megatile", "gigatile"]),
        unmeasured("knowledge-to-keep-forever", "Retention classification requires a policy decision."),
        unmeasured("knowledge-to-forget-or-archive", "Autonomous deletion remains forbidden.")
      ],
      projects: [
        measured("main-objectives", inventory.projects.filter((item) => item.category === "CURRENT")),
        measured("secondary-objectives", inventory.projects.filter((item) => item.category === "SPECULATIVE")),
        unmeasured("missing-dependencies", "Dependency archaeology is planned."),
        measured("blockers", inventory.projects.filter((item) => /REQUIRES|NOT_FOUND|STANDBY/.test(item.status || ""))),
        measured("decisions-pending", inventory.projects.filter((item) => /IDEA|BACKLOG/.test(item.category))),
        unmeasured("completed-not-validated", "Needs traceability join with the task registry."),
        unmeasured("documented-but-missing", "Needs documentation-to-code reconciliation."),
        unmeasured("existing-but-undocumented", "Needs code-to-documentation reconciliation."),
        measured("active-experiments", inventory.projects.filter((item) => /EXPERIMENT|SPECULATIVE/.test(`${item.category} ${item.status}`))),
        measured("recoverable-abandoned-work", inventory.projects.filter((item) => /HISTOR|ABANDON|IDEA/.test(`${item.category} ${item.status}`)))
      ],
      ecosystems: [
        measured("fabric-nodes", this.fabric.listNodes({ limit: 500 }).items, {
          total: this.fabric.summary().totalNodes,
          bounded: this.fabric.summary().totalNodes > 500
        }),
        measured("organizations", this.fabric.listNodes({ kind: "organization", limit: 500 }).items, {
          total: this.fabric.summary().organizations,
          bounded: this.fabric.summary().organizations > 500
        }),
        measured("active-partitions", Array.from(
          new Set(this.fabric.listNodes({ limit: 500 }).items.map((item) => item.partitionKey))
        )),
        measured("fabric-integrity", [this.fabric.verifyEventChains()])
      ],
      reliability: [
        measured("recent-evidence", this.readLedger(50)),
        unmeasured("claims-without-tool-result", "Claim-to-tool reconciliation is planned."),
        measured("failed-tests", incidents.filter((item) => item.status !== "RESOLVED")),
        measured("recurring-errors", incidents.filter((item) => Number(item.occurrences || 0) > 1)),
        unmeasured("regressions", "Regression Hunter is planned."),
        measured("restore-options", inventory.snapshots),
        measured("snapshots", inventory.snapshots),
        measured("irreversible-actions", this.permissions.deny),
        measured("security-risks", [
          { id: "listener-review", status: inventory.ports.some((item) => /^(?:0\.0\.0\.0|\[?::\]?):/.test(item.endpoint)) ? "REVIEW" : "OK" },
          { id: "external-actions-default", status: this.registry.controller.externalActionsDefault }
        ]),
        measured("guardrail-prevented-incidents", incidents.filter((item) => item.status === "RESOLVED"))
      ],
      opportunities: [
        measured("free-tools-connectable", nonOperational),
        unmeasured("free-apis-connectable", "API terms, limits and privacy need individual review."),
        measured("unsupported-formats", ["OpenUSD", "MaterialX", "OpenTimelineIO", "Parquet", "WASI Component"]),
        unmeasured("apps-without-mcp", "Requires installed-application inventory and automation review."),
        measured("abandoned-tools-to-modernize", githubRepositories.filter((item) => item.priority === "COMPARE")),
        unmeasured("user-complaints-without-solution", "Problem Complaint Miner is planned."),
        unmeasured("repetitive-human-tasks", "Needs privacy-preserving activity sampling."),
        measured("surprising-integrations", [
          "Tree-sitter + MouseCode",
          "OpenTelemetry + Evidence Ledger",
          "Automerge + Fractal Spatial State",
          "DuckDB + JSONL incident history"
        ]),
        unmeasured("monetizable-capabilities", "Commercial decisions require the owner."),
        measured("open-source-candidates", capabilities.filter((item) => ["OPERATIONAL", "PARTIAL"].includes(item.status)))
      ]
    };
  }
}

export function createControlPlaneRuntime(options = {}) {
  return new ControlPlaneRuntime(options);
}

export { defaultCommandRunner };
