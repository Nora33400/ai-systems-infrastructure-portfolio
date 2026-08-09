import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync
} from "node:fs";
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { dirname, join, resolve } from "node:path";

const execFileAsync = promisify(execFile);

function expandEnvironmentPath(value) {
  return resolve(String(value || "").replace(/%([^%]+)%/g, (_, name) => process.env[name] || `%${name}%`));
}

function atomicText(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, value.endsWith("\n") ? value : `${value}\n`, "utf8");
  renameSync(temporary, path);
}

function atomicJson(path, value) {
  atomicText(path, JSON.stringify(value, null, 2));
}

function opencodeExecutable() {
  if (process.platform !== "win32") return "opencode";
  const candidates = execFileSync("where.exe", ["opencode"], { encoding: "utf8", windowsHide: true })
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const executable = candidates.find((candidate) => candidate.toLowerCase().endsWith(".exe"));
  if (executable) return executable;
  for (const candidate of candidates) {
    const native = join(dirname(candidate), "node_modules", "opencode-ai", "bin", "opencode.exe");
    if (existsSync(native)) return native;
  }
  throw new Error("Exécutable natif OpenCode introuvable.");
}

async function ollamaGenerate({ model, prompt, timeoutMs = 10 * 60 * 1000 }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch("http://127.0.0.1:11434/api/generate", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({
        model,
        prompt,
        stream: false,
        options: {temperature: 0.2, num_ctx: 16384, num_predict: 1800}
      }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`Ollama HTTP ${response.status}`);
    const body = await response.json();
    return String(body.response || "").trim();
  } finally {
    clearTimeout(timer);
  }
}

async function opencodeReadOnly({ root, agent, model, prompt, timeoutMs = 20 * 60 * 1000 }) {
  const result = await execFileAsync(opencodeExecutable(), [
    "run",
    "--agent",
    agent,
    "--model",
    `ollama/${model}`,
    "--format",
    "default",
    prompt
  ], {cwd: root, timeout: timeoutMs, windowsHide: true, maxBuffer: 8 * 1024 * 1024});
  return String(result.stdout || "").trim();
}

function validateValue(spec, value, context) {
  const normalized = value ?? spec.default;
  if ((normalized === undefined || normalized === "") && spec.required) {
    throw new Error(`Argument requis: ${context.name}`);
  }
  if (normalized === undefined) return "";
  const text = String(normalized);
  if (text.length > 500) throw new Error(`Argument trop long: ${context.name}`);
  if (/[\u0000-\u001f]/.test(text)) throw new Error(`Caractère de contrôle interdit: ${context.name}`);
  if (spec.type === "enum" && !spec.values.includes(text)) {
    throw new Error(`Valeur invalide pour ${context.name}: ${text}`);
  }
  if (spec.type === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    throw new Error(`Date invalide pour ${context.name}`);
  }
  if (spec.type === "project" && !context.projects.some((project) => project.id === text)) {
    throw new Error(`Projet inconnu: ${text}`);
  }
  if (spec.type === "studio" && !context.studios.some((studio) => studio.id === text)) {
    throw new Error(`Studio inconnu: ${text}`);
  }
  return text;
}

export class AgentAutomationRunner {
  constructor({
    root = resolve(process.cwd()),
    configPath = join(root, "config", "agent-automations.json"),
    portfolioPath = join(root, "config", "project-portfolio.json"),
    digitalLifePath = join(root, "config", "digital-life.json"),
    outputDir,
    clock = () => new Date(),
    localModelRunner = ollamaGenerate,
    codeAgentRunner = opencodeReadOnly
  } = {}) {
    this.root = resolve(root);
    this.config = JSON.parse(readFileSync(configPath, "utf8"));
    this.portfolio = JSON.parse(readFileSync(portfolioPath, "utf8"));
    this.digitalLife = JSON.parse(readFileSync(digitalLifePath, "utf8"));
    this.outputDir = outputDir ? resolve(outputDir) : expandEnvironmentPath(this.config.outputDir);
    this.clock = clock;
    this.localModelRunner = localModelRunner;
    this.codeAgentRunner = codeAgentRunner;
    mkdirSync(this.outputDir, { recursive: true });
  }

  list() {
    return this.config.automations.map(({id, agent, model, mode, arguments: argumentSchema}) => ({
      id,
      agent,
      model,
      mode,
      arguments: argumentSchema
    }));
  }

  prepare(id, supplied = {}) {
    const automation = this.config.automations.find((item) => item.id === id);
    if (!automation) throw new Error(`Automatisation inconnue: ${id}`);
    const values = {};
    for (const [name, spec] of Object.entries(automation.arguments || {})) {
      values[name] = validateValue(spec, supplied[name], {
        name,
        projects: this.portfolio.projects,
        studios: this.digitalLife.studios
      });
    }
    const unexpected = Object.keys(supplied).filter((name) => !(name in (automation.arguments || {})));
    if (unexpected.length) throw new Error(`Arguments non déclarés: ${unexpected.join(", ")}`);
    let prompt = automation.prompt;
    for (const [name, value] of Object.entries(values)) {
      prompt = prompt.replaceAll(`{${name}}`, value);
    }
    let executionAgent = automation.agent;
    let executionModel = automation.model;
    if (automation.id === "prepare-studio-meeting") {
      const studio = this.digitalLife.studios.find((entry) => entry.id === values.studio);
      executionAgent = studio.lead;
      executionModel = studio.model;
      const projectSummary = this.portfolio.projects
        .filter((project) => ["CURRENT", "BACKLOG", "IDEA"].includes(project.category))
        .map((project) => `${project.id}:${project.category}:${project.status}`)
        .join(", ");
      prompt += [
        "",
        `Responsable: ${studio.lead}`,
        `Statut: ${studio.status}`,
        `Autorité maximale: ${studio.authority}`,
        studio.disclaimer ? `Limite: ${studio.disclaimer}` : "",
        `Portefeuille: ${projectSummary}`,
        "Toute activation au-delà de cette autorité devient une question."
      ].filter(Boolean).join("\n");
    }
    return {automation, values, prompt, executionAgent, executionModel};
  }

  async run(id, supplied = {}, {execute = true} = {}) {
    const prepared = this.prepare(id, supplied);
    const startedAt = this.clock().toISOString();
    let output = "PREVIEW_ONLY";
    if (execute) {
      if (prepared.automation.mode === "READ_ONLY") {
        output = await this.codeAgentRunner({
          root: this.root,
          agent: prepared.executionAgent,
          model: prepared.executionModel,
          prompt: prepared.prompt
        });
      } else {
        output = await this.localModelRunner({
          model: prepared.executionModel,
          prompt: prepared.prompt
        });
      }
    }
    const stamp = startedAt.replace(/[-:.TZ]/g, "");
    const base = `${stamp}-${prepared.automation.id}`;
    const result = {
      schema: "aione.agent-automation-run.v1",
      id: base,
      automationId: prepared.automation.id,
      agent: prepared.executionAgent,
      model: prepared.executionModel,
      mode: prepared.automation.mode,
      executed: execute,
      startedAt,
      completedAt: this.clock().toISOString(),
      arguments: prepared.values,
      prompt: prepared.prompt,
      output,
      externalActions: "DENIED"
    };
    const jsonPath = join(this.outputDir, `${base}.json`);
    const markdownPath = join(this.outputDir, `${base}.md`);
    atomicJson(jsonPath, result);
    atomicText(markdownPath, [
      `# Automatisation ${prepared.automation.id}`,
      "",
      `- Agent : \`${prepared.executionAgent}\``,
      `- Modèle : \`${prepared.executionModel}\``,
      `- Mode : \`${prepared.automation.mode}\``,
      `- Exécutée : \`${execute}\``,
      "- Actions externes : `DENIED`",
      "",
      "## Résultat",
      "",
      output
    ].join("\n"));
    return {...result, jsonPath, markdownPath};
  }
}
