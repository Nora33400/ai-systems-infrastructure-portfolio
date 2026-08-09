import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createControlledResearchLab } from "./controlled-research-lab.mjs";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const defaultConfigPath = join(projectRoot, "config", "controlled-research.json");

function loadConfiguration() {
  const testOverride = process.env.NODE_ENV === "test"
    ? String(process.env.AIONE_CONTROLLED_RESEARCH_CONFIG || "").trim()
    : "";
  const configPath = resolve(testOverride || defaultConfigPath);
  const config = JSON.parse(readFileSync(configPath, "utf8"));
  const configuredRuntimeRoot = String(config.runtimeRoot || "").trim();
  if (!configuredRuntimeRoot) throw new Error("RUNTIME_ROOT_REQUIRED");
  const runtimeRoot = resolve(configuredRuntimeRoot);
  if (!testOverride && !/^S:\\/iu.test(runtimeRoot)) throw new Error("RUNTIME_MUST_STAY_ON_S_DRIVE");
  return { config, configPath, runtimeRoot };
}

function minimumIntervalMs(config) {
  const value = Number(config?.schedule?.minimumIntervalHours ?? 24);
  return (Number.isFinite(value) && value >= 1 ? value : 24) * 60 * 60 * 1_000;
}

function latestCompletedRun(lab) {
  return [...(lab.state?.runs ?? [])]
    .reverse()
    .find((run) => Number.isFinite(Date.parse(run.completedAt || run.startedAt || ""))) ?? null;
}

function dueState(lab, config, now = new Date()) {
  const latest = latestCompletedRun(lab);
  const intervalMs = minimumIntervalMs(config);
  if (!latest) {
    return { due: true, reason: "NEVER_RUN", lastRunAt: null, nextRunAt: now.toISOString() };
  }
  const lastRunAt = new Date(latest.completedAt || latest.startedAt);
  const nextRunAt = new Date(lastRunAt.getTime() + intervalMs);
  return {
    due: now.getTime() >= nextRunAt.getTime(),
    reason: now.getTime() >= nextRunAt.getTime() ? "INTERVAL_ELAPSED" : "MINIMUM_INTERVAL_ACTIVE",
    lastRunAt: lastRunAt.toISOString(),
    nextRunAt: nextRunAt.toISOString()
  };
}

function hasFlag(args, name) {
  return args.includes(name);
}

function print(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function main() {
  const [command = "status", ...args] = process.argv.slice(2);
  if (!new Set(["status", "simulate", "cycle"]).has(command)) {
    const error = new Error("USAGE: controlled-research-cli.mjs <status|simulate|cycle> [--offline] [--force]");
    error.exitCode = 2;
    throw error;
  }

  const { config, configPath, runtimeRoot } = loadConfiguration();
  const lab = createControlledResearchLab({ config, runtimeRoot });
  const schedule = dueState(lab, config);
  const common = {
    configuredEnabled: config.enabled !== false,
    configPath,
    runtimeRoot,
    schedule: {
      timezone: String(config.schedule?.timezone || "Europe/Paris"),
      minimumIntervalHours: minimumIntervalMs(config) / (60 * 60 * 1_000),
      ...schedule
    }
  };

  if (command === "status") {
    print({ ...lab.status(), ...common });
    return;
  }
  if (command === "simulate") {
    print({ ...lab.simulate(), ...common });
    return;
  }

  const offline = hasFlag(args, "--offline");
  const force = hasFlag(args, "--force");
  if (config.enabled === false) {
    print({
      schema: "aione.controlled-research-cycle-dispatch.v1",
      state: "SKIPPED_DISABLED",
      offline,
      mutationPerformed: false,
      ...common
    });
    return;
  }
  if (!force && !schedule.due) {
    print({
      schema: "aione.controlled-research-cycle-dispatch.v1",
      state: "SKIPPED_NOT_DUE",
      offline,
      mutationPerformed: false,
      ...common
    });
    return;
  }

  const result = await lab.run({ offline });
  print({ ...result, dispatch: { offline, forced: force, configPath, runtimeRoot } });
}

try {
  await main();
} catch (error) {
  print({
    schema: "aione.controlled-research-cli-error.v1",
    ok: false,
    error: error instanceof Error ? error.message : String(error)
  });
  process.exitCode = Number(error?.exitCode || 1);
}
