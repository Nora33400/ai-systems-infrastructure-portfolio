import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { CognitiveImmuneSystem, observeLocalSystem } from "./cognitive-immune-system.mjs";

const MODULE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value), "utf8").digest("hex");
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/u, ""));
}

function safeError(error) {
  return String(error?.stderr || error?.message || error || "erreur inconnue")
    .replace(/(token|password|secret|authorization)\s*[:=]\s*\S+/giu, "$1=[REDACTED]")
    .replaceAll("\0", "")
    .slice(0, 1000);
}

function loopback(endpoint) {
  const url = new URL(endpoint);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error(`IMMUNE refuse le probe non local: ${endpoint}`);
  }
  return url;
}

function commandProbe(component) {
  try {
    const stdout = execFileSync(component.command, component.args || [], {
      encoding: "utf8",
      timeout: Number(component.timeoutMs || 5000),
      windowsHide: true,
      maxBuffer: 1024 * 1024
    });
    return { ok: true, status: "HEALTHY", evidence: String(stdout).replaceAll("\0", "").trim().slice(0, 500) };
  } catch (error) {
    return {
      ok: false,
      status: error?.code === "ETIMEDOUT" || error?.killed ? "TIMEOUT" : "FAILED",
      error: safeError(error)
    };
  }
}

async function httpProbe(component) {
  const url = loopback(component.endpoint);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Number(component.timeoutMs || 5000));
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      redirect: "error",
      headers: { accept: "application/json" }
    });
    return { ok: response.ok, status: response.ok ? "HEALTHY" : "UNHEALTHY", httpStatus: response.status };
  } catch (error) {
    return { ok: false, status: error?.name === "AbortError" ? "TIMEOUT" : "FAILED", error: safeError(error) };
  } finally {
    clearTimeout(timeout);
  }
}

function appendChained(path, body) {
  mkdirSync(dirname(path), { recursive: true });
  const lines = existsSync(path) ? readFileSync(path, "utf8").split(/\r?\n/u).filter(Boolean) : [];
  const previous = lines.length ? JSON.parse(lines.at(-1)) : null;
  const entry = { ...body, previousHash: previous?.hash || null };
  entry.hash = digest(entry);
  appendFileSync(path, `${JSON.stringify(entry)}\n`, "utf8");
  return entry;
}

export class ImmuneRuntime {
  constructor({
    configPath = join(MODULE_ROOT, "config", "immune-runtime.json"),
    now = () => new Date(),
    commandRunner = commandProbe,
    httpRunner = httpProbe,
    systemObserver = observeLocalSystem,
    cognitiveImmune = null
  } = {}) {
    this.configPath = resolve(configPath);
    this.config = readJson(this.configPath);
    this.now = now;
    this.commandRunner = commandRunner;
    this.httpRunner = httpRunner;
    this.systemObserver = systemObserver;
    this.cognitiveImmune = cognitiveImmune || new CognitiveImmuneSystem({
      policyPath: join(MODULE_ROOT, "config", "cognitive-immune-system.json")
    });
    this.runtimeRoot = resolve(this.config.runtimeRoot);
    this.paths = Object.freeze({
      ledger: join(this.runtimeRoot, "immune-ledger.jsonl"),
      requests: join(this.runtimeRoot, "requests"),
      quarantine: join(this.runtimeRoot, "quarantine"),
      upgrades: join(this.runtimeRoot, "upgrades"),
      bootstrap: resolve(this.config.bootstrap.destination)
    });
    [this.runtimeRoot, this.paths.requests, this.paths.quarantine, this.paths.upgrades, this.paths.bootstrap]
      .forEach((path) => mkdirSync(path, { recursive: true }));
  }

  sourceStatus() {
    const sourcePath = resolve(this.config.source.path);
    const missing = (this.config.source.requiredFiles || []).filter((name) => !existsSync(join(sourcePath, name)));
    return {
      ok: existsSync(sourcePath) && missing.length === 0,
      path: sourcePath,
      access: "READ_ONLY",
      missing,
      bootstrapRequired: !existsSync(sourcePath) || missing.length > 0
    };
  }

  async doctor() {
    const examinedAt = this.now().toISOString();
    const probes = [];
    for (const component of this.config.components || []) {
      const started = Date.now();
      const result = component.kind === "HTTP"
        ? await this.httpRunner(component)
        : await this.commandRunner(component);
      probes.push({
        id: component.id,
        kind: component.kind,
        critical: component.critical === true,
        repair: component.repair,
        durationMs: Date.now() - started,
        ...result
      });
    }
    const source = this.sourceStatus();
    let systemObservation;
    try {
      systemObservation = this.systemObserver({ runtimeRoot: this.runtimeRoot, probes, source });
    } catch (error) {
      systemObservation = { integrityOk: true, auditIntegrityOk: true, memoryIntegrity: true, gpus: [], errors: [{ id: "system-observer", critical: false, status: safeError(error) }] };
    }
    const cognitiveHealth = this.cognitiveImmune.assess(systemObservation);
    return {
      schema: "aione.immune-doctor-report.v1",
      reportId: randomUUID(),
      examinedAt,
      source,
      healthy: probes.every((probe) => probe.ok || !probe.critical),
      probes,
      cognitiveHealth
    };
  }

  diagnose(report) {
    const failed = report.probes.filter((probe) => !probe.ok);
    const byId = new Map(report.probes.map((probe) => [probe.id, probe]));
    const diagnoses = failed.map((probe) => {
      let cause = "COMPONENT_FAILURE";
      let confidence = 0.6;
      if (["docker", "openwebui"].includes(probe.id) && byId.get("wsl")?.ok === false) {
        cause = "WSL_UNRESPONSIVE_DEPENDENCY_CHAIN";
        confidence = 0.95;
      } else if (probe.id === "openwebui" && byId.get("docker")?.ok === false) {
        cause = "DOCKER_UNAVAILABLE_DEPENDENCY_CHAIN";
        confidence = 0.9;
      } else if (probe.status === "TIMEOUT") {
        cause = "COMPONENT_TIMEOUT";
        confidence = 0.85;
      }
      return {
        incidentId: `incident-${probe.id}-${digest([report.reportId, probe.id]).slice(0, 12)}`,
        componentId: probe.id,
        cause,
        confidence,
        critical: probe.critical,
        evidenceHash: digest(probe),
        repairHint: probe.repair
      };
    });
    return { schema: "aione.immune-diagnosis.v1", reportId: report.reportId, diagnosedAt: this.now().toISOString(), diagnoses };
  }

  anesthetize(diagnosis) {
    const actions = [];
    const wslFailed = diagnosis.diagnoses.some((entry) => entry.componentId === "wsl");
    if (wslFailed) {
      actions.push({
        action: "REQUEST_ADMIN_SERVICE_RESTART_OR_REBOOT",
        target: "WslService",
        automatic: false,
        reason: "WSL reste muet après terminaison des clients; un droit administrateur ou un redémarrage Windows est requis.",
        rollback: "aucune mutation appliquée"
      });
    }
    for (const entry of diagnosis.diagnoses) {
      if (["docker", "openwebui"].includes(entry.componentId) && wslFailed) continue;
      if (entry.repairHint === "RESTART_APPROVED_USER_SERVICE") {
        actions.push({
          action: "RESTART_APPROVED_USER_SERVICE",
          target: entry.componentId,
          automatic: true,
          reason: entry.cause,
          rollback: "arrêter le processus relancé et restaurer l'état précédent"
        });
      }
    }
    return {
      schema: "aione.immune-anesthesia-plan.v1",
      diagnosisHash: digest(diagnosis),
      plannedAt: this.now().toISOString(),
      actions,
      destructiveActions: 0,
      rebootAutomatic: false
    };
  }

  repair(plan, { applySafe = false } = {}) {
    const allowed = new Set(this.config.automaticActions || []);
    const receipts = plan.actions.map((action) => {
      if (!action.automatic || !applySafe) {
        const requestFingerprint = digest({
          action: action.action,
          target: action.target,
          reason: action.reason
        });
        const path = join(this.paths.requests, `request-${requestFingerprint.slice(0, 24)}.json`);
        if (existsSync(path)) {
          const existing = readJson(path);
          return {
            action: action.action,
            target: action.target,
            status: "REQUESTED_DUPLICATE",
            requestId: existing.requestId,
            requestPath: path,
            requestFingerprint
          };
        }
        const request = {
          schema: "aione.immune-action-request.v1",
          requestId: randomUUID(),
          requestFingerprint,
          createdAt: this.now().toISOString(),
          state: "HUMAN_OR_ADMIN_ACTION_REQUIRED",
          ...action
        };
        const temporary = `${path}.${process.pid}.tmp`;
        appendFileSync(temporary, `${JSON.stringify(request, null, 2)}\n`, "utf8");
        renameSync(temporary, path);
        return {
          action: action.action,
          target: action.target,
          status: "REQUESTED",
          requestId: request.requestId,
          requestPath: path,
          requestFingerprint
        };
      }
      if (!allowed.has(action.action)) {
        return { action: action.action, target: action.target, status: "DENIED_NOT_ALLOWLISTED" };
      }
      return { action: action.action, target: action.target, status: "DEFERRED_EXECUTOR_NOT_PROVED" };
    });
    return { schema: "aione.immune-repair-receipts.v1", at: this.now().toISOString(), receipts };
  }

  autoupgrade({ apply = false } = {}) {
    const programs = (this.config.programUpdates || []).map((program) => ({
      id: program.id,
      manager: program.manager,
      packageId: program.packageId,
      decision: apply && program.automaticApply ? "PREPARE_CANDIDATE" : "CHECK_ONLY_OR_MAINTENANCE_WINDOW",
      automaticApply: program.automaticApply === true,
      reason: program.reason
    }));
    return {
      schema: "aione.immune-autoupgrade-plan.v1",
      createdAt: this.now().toISOString(),
      source: this.sourceStatus(),
      programs,
      arbitraryProgramUpgrade: false,
      unsignedInstallAllowed: false,
      rebootAutomatic: false
    };
  }

  bootstrap() {
    const source = this.sourceStatus();
    if (source.ok) return { ok: true, status: "SOURCE_PRESENT", source };
    const bootstrap = this.config.bootstrap || {};
    if (!bootstrap.enabled || !bootstrap.repositoryUrl || !bootstrap.pinnedCommit) {
      return { ok: false, status: "OWNER_PINNED_REPOSITORY_REQUIRED", source };
    }
    const url = new URL(bootstrap.repositoryUrl);
    if (url.protocol !== "https:" || url.hostname !== bootstrap.allowedHost || !/^[a-f0-9]{40}$/iu.test(bootstrap.pinnedCommit)) {
      return { ok: false, status: "BOOTSTRAP_POLICY_REFUSED", source };
    }
    const destination = join(this.paths.bootstrap, basename(url.pathname, ".git"));
    if (existsSync(destination)) return { ok: true, status: "CANDIDATE_ALREADY_PRESENT", destination };
    execFileSync("git", ["clone", "--no-checkout", "--filter=blob:none", bootstrap.repositoryUrl, destination], {
      timeout: 10 * 60 * 1000,
      windowsHide: true,
      stdio: "pipe"
    });
    execFileSync("git", ["-C", destination, "checkout", "--detach", bootstrap.pinnedCommit], {
      timeout: 2 * 60 * 1000,
      windowsHide: true,
      stdio: "pipe"
    });
    const actual = execFileSync("git", ["-C", destination, "rev-parse", "HEAD"], { encoding: "utf8", windowsHide: true }).trim();
    if (actual !== bootstrap.pinnedCommit) throw new Error("IMMUNE bootstrap commit mismatch");
    return { ok: true, status: "PINNED_CANDIDATE_READY_FOR_TESTS", destination, commit: actual };
  }

  async cycle({ applySafe = true } = {}) {
    const doctor = await this.doctor();
    const diagnosis = this.diagnose(doctor);
    const anesthesia = this.anesthetize(diagnosis);
    const repair = this.repair(anesthesia, { applySafe });
    const result = {
      schema: "aione.immune-cycle.v1",
      cycleId: randomUUID(),
      startedAt: doctor.examinedAt,
      completedAt: this.now().toISOString(),
      doctor,
      diagnosis,
      anesthesia,
      repair,
      status: diagnosis.diagnoses.length ? "DEGRADED_ACTIONS_BOUNDED" : "HEALTHY"
    };
    const event = appendChained(this.paths.ledger, result);
    return { ...result, ledgerHash: event.hash };
  }
}

export function createImmuneRuntime(options = {}) {
  return new ImmuneRuntime(options);
}
