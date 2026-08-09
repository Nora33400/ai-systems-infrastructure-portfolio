import { closeSync, existsSync, fsyncSync, mkdirSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const MODULE_PATH = fileURLToPath(import.meta.url);
const DEFAULT_ROOT = resolve(dirname(MODULE_PATH), "..", "..");
const TERMINAL = new Set(["DONE", "STABLE", "ARCHIVED", "CANCELLED"]);

function hash(value) {
  return createHash("sha256").update(String(value), "utf8").digest("hex");
}

function boundedText(value, maximum = 2_000) {
  return String(value ?? "").replaceAll("\0", "").trim().slice(0, maximum);
}

function readJsonSafely(path) {
  if (!existsSync(path)) return null;
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return null; }
}

function atomicWrite(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  let descriptor;
  try {
    descriptor = openSync(temporary, "wx");
    writeFileSync(descriptor, content, "utf8");
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    renameSync(temporary, path);
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
    if (existsSync(temporary)) unlinkSync(temporary);
  }
}

export function buildModelEvolutionBacklog(configuration = {}) {
  const circuits = new Map((configuration.circuits || []).map((circuit) => [circuit.id, circuit]));
  const items = (configuration.roadmap || []).filter((item) => !TERMINAL.has(String(item.status || "").toUpperCase())).map((item) => ({
    id: boundedText(item.id, 160),
    priority: boundedText(item.priority || "P2", 8),
    status: boundedText(item.status || "PROPOSED_LOCAL", 80),
    objective: boundedText(item.objective, 2_000),
    acceptance: (Array.isArray(item.acceptance) ? item.acceptance : []).map((criterion) => boundedText(criterion, 500)).filter(Boolean).slice(0, 20)
  })).filter((item) => item.id && item.objective);
  const lines = [
    "# Backlog autonome — évolution des modèles locaux",
    "",
    "Ce fichier est généré depuis `config/autonomous-model-evolution.json`.",
    "Il autorise analyse, benchmark, simulation, canary isolé et rollback local.",
    "Il n'autorise ni publication, ni Git, ni suppression, ni secret, ni sortie réseau publique.",
    "",
    "## Circuit obligatoire",
    "",
    ...[...circuits.values()].flatMap((circuit) => [
      `- **${boundedText(circuit.id, 80)}** : ${(circuit.stages || []).map((stage) => boundedText(stage, 120)).join(" → ")} ; sortie: ${boundedText(circuit.output, 200)} ; mutation: ${boundedText(circuit.mutation, 100)}`
    ]),
    "",
    "## Lots prioritaires",
    "",
    ...items.flatMap((item) => [
      `### ${item.priority} · ${item.id} · ${item.status}`,
      "",
      item.objective,
      "",
      "Critères d'acceptation :",
      ...item.acceptance.map((criterion) => `- ${criterion}`),
      "",
      "Contrat : petite étape réversible, preuve locale, comparaison au baseline, arrêt sur régression, aucun élargissement de permission.",
      ""
    ])
  ];
  const content = `${lines.join("\n").trim()}\n`;
  return {
    schema: "aione.model-evolution-handoff.v1",
    items,
    content,
    digest: hash(content)
  };
}

export function writeModelEvolutionHandoff({
  root = DEFAULT_ROOT,
  runtimeRoot = process.env.AIONE_RUNTIME_DIR || "S:\\AI_LAB\\Runtime"
} = {}) {
  const configPath = join(resolve(root), "config", "autonomous-model-evolution.json");
  const configuration = JSON.parse(readFileSync(configPath, "utf8"));
  const backlog = buildModelEvolutionBacklog(configuration);
  const outputDir = join(resolve(runtimeRoot), "ModelEvolution");
  const outputPath = join(outputDir, "generated-backlog.md");
  const statePath = join(outputDir, "handoff-state.json");
  const lastValidPath = join(outputDir, "handoff-state.last-valid.json");
  mkdirSync(outputDir, { recursive: true });
  const previous = readJsonSafely(statePath) || readJsonSafely(lastValidPath);
  if (!existsSync(outputPath) || previous?.digest !== backlog.digest) {
    atomicWrite(outputPath, backlog.content);
  }
  const state = {
    schema: "aione.model-evolution-handoff-state.v1",
    updatedAt: new Date().toISOString(),
    configPath,
    outputPath,
    digest: backlog.digest,
    items: backlog.items.length,
    changed: previous?.digest !== backlog.digest,
    localOnly: true,
    autoApproveScope: "MODEL_EVOLUTION_BOUNDED"
  };
  const serializedState = `${JSON.stringify(state, null, 2)}\n`;
  atomicWrite(lastValidPath, serializedState);
  atomicWrite(statePath, serializedState);
  return state;
}

export function readModelEvolutionHandoffStatus({ runtimeRoot = process.env.AIONE_RUNTIME_DIR || "S:\\AI_LAB\\Runtime" } = {}) {
  const outputDir = join(resolve(runtimeRoot), "ModelEvolution");
  const statePath = join(outputDir, "handoff-state.json");
  const current = readJsonSafely(statePath);
  if (current) return current;
  const recovered = readJsonSafely(join(outputDir, "handoff-state.last-valid.json"));
  if (recovered) return { ...recovered, recoveredFromLastValid: true };
  return { schema: "aione.model-evolution-handoff-state.v1", state: existsSync(statePath) ? "CORRUPT_STATE" : "NOT_GENERATED", statePath };
}
