import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_PATH = fileURLToPath(import.meta.url);
const DEFAULT_ROOT = resolve(dirname(MODULE_PATH), "..", "..");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
}

function atomicText(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, content.endsWith("\n") ? content : `${content}\n`, "utf8");
  renameSync(temporary, path);
}

function atomicJson(path, value) {
  atomicText(path, JSON.stringify(value, null, 2));
}

function writeIfChanged(path, content) {
  const normalized = content.endsWith("\n") ? content : `${content}\n`;
  if (existsSync(path) && readFileSync(path, "utf8") === normalized) return false;
  atomicText(path, normalized);
  return true;
}

function localDateKey(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0")
  ].join("-");
}

function startOfLocalDay(date) {
  const value = new Date(date);
  value.setHours(0, 0, 0, 0);
  return value;
}

function moduleForDate(config, now) {
  const start = startOfLocalDay(new Date(`${config.startDate}T00:00:00`));
  const current = startOfLocalDay(now);
  const elapsedDays = Math.max(0, Math.floor((current - start) / 86400000));
  const weekIndex = Math.floor(elapsedDays / 7);
  return {
    weekIndex,
    cycle: Math.floor(weekIndex / config.modules.length) + 1,
    module: config.modules[weekIndex % config.modules.length]
  };
}

function nextSessionDate(now, session) {
  const dayIndex = { SU: 0, MO: 1, TU: 2, WE: 3, TH: 4, FR: 5, SA: 6 }[session.day];
  const [hour, minute] = session.start.split(":").map(Number);
  const candidate = new Date(now);
  candidate.setHours(hour, minute, 0, 0);
  let delta = (dayIndex - candidate.getDay() + 7) % 7;
  if (delta === 0 && candidate <= now) delta = 7;
  candidate.setDate(candidate.getDate() + delta);
  return candidate;
}

function sessionKit(config, moduleState, session, date) {
  const { module, weekIndex, cycle } = moduleState;
  return [
    `# ${module.id} — ${module.title}`,
    "",
    `Séance: ${session.id}`,
    `Date prévue: ${date.toLocaleString("fr-FR", { timeZone: config.timezone })}`,
    `Semaine du parcours: ${weekIndex + 1} · cycle ${cycle}`,
    `Durée: ${session.durationMinutes} minutes`,
    "",
    "## Contexte objectif utilisateur",
    config.purpose,
    "",
    "## Contexte subjectif machine",
    "La Forge prépare ce support depuis son état local et ses conventions. Elle ne suppose ni compréhension acquise, ni permission supplémentaire, ni réussite sans preuve.",
    "",
    "## Résultats attendus",
    ...module.outcomes.map((item) => `- ${item}`),
    "",
    "## Déroulé",
    ...session.structure.map((item, index) => `${index + 1}. ${item}`),
    "",
    "## Exercice concret",
    module.exercise,
    "",
    "## Preuve à produire",
    module.evidence,
    "",
    "## Convention de la semaine",
    module.convention,
    "",
    "## Commandes de départ",
    "- État global : `powershell -File S:\\AI_LAB\\Ecosystem\\scripts\\get-aione-ecosystem-status.ps1`",
    "- État GPU : `powershell -File S:\\AI_LAB\\Ecosystem\\scripts\\get-dual-gpu-development-status.ps1`",
    "- Interface Forge : `http://127.0.0.1:4310`",
    "- Résultats isolés : `S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\isolated-implementations`",
    "",
    "## Fin de séance",
    "Écrire : ce que j'ai compris, ce que j'ai vérifié, ce qui reste incertain, la prochaine action et la permission nécessaire.",
    ""
  ].join("\n");
}

function runUserLearningPlanner({
  root = DEFAULT_ROOT,
  configPath = join(root, "config", "user-learning-plan.json"),
  now = new Date()
} = {}) {
  root = resolve(root);
  const config = readJson(resolve(configPath));
  if (!config.enabled) return { ok: true, status: "DISABLED" };
  const runtimeRoot = resolve(config.runtimeRoot);
  if (!/^S:\\/i.test(runtimeRoot)) throw new Error(`LearningCoach doit rester sur S: ${runtimeRoot}`);
  const moduleState = moduleForDate(config, now);
  const candidates = config.sessionCadence
    .map((session) => ({ session, date: nextSessionDate(now, session) }))
    .sort((left, right) => left.date - right.date);
  const weekKey = `${config.startDate}-W${String(moduleState.weekIndex + 1).padStart(2, "0")}`;
  const generated = [];
  for (const candidate of candidates) {
    const path = join(runtimeRoot, "session-kits", weekKey, `${candidate.session.id}.md`);
    if (writeIfChanged(path, sessionKit(config, moduleState, candidate.session, candidate.date))) generated.push(path);
  }
  const next = candidates[0];
  const nextContent = sessionKit(config, moduleState, next.session, next.date);
  const currentPath = join(runtimeRoot, "current-session.md");
  writeIfChanged(currentPath, nextContent);
  const state = {
    schema: "aione.user-learning-state.v1",
    updatedAt: now.toISOString(),
    localDate: localDateKey(now),
    weekIndex: moduleState.weekIndex,
    cycle: moduleState.cycle,
    moduleId: moduleState.module.id,
    moduleTitle: moduleState.module.title,
    nextSession: {
      id: next.session.id,
      at: next.date.toISOString(),
      calendarSeriesId: next.session.calendarSeriesId,
      kit: currentPath
    },
    generatedFiles: generated,
    sessionKitRoot: join(runtimeRoot, "session-kits"),
    canonicalMutationPerformed: false
  };
  atomicJson(join(runtimeRoot, "state.json"), state);
  return { ok: true, status: "READY", ...state };
}

function parseArguments(values) {
  const options = {};
  for (let index = 0; index < values.length; index += 1) {
    if (values[index] === "--root") options.root = values[++index];
    else if (values[index] === "--config") options.configPath = values[++index];
  }
  return options;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(MODULE_PATH)) {
  try {
    process.stdout.write(`${JSON.stringify(runUserLearningPlanner(parseArguments(process.argv.slice(2))), null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  }
}

export { moduleForDate, nextSessionDate, runUserLearningPlanner };
