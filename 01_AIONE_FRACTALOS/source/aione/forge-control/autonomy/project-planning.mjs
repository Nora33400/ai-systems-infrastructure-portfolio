import { createHash, randomUUID } from "node:crypto";
import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync
} from "node:fs";
import { dirname, resolve } from "node:path";

const DAY_MS = 86_400_000;
const DEFAULT_DURATIONS = Object.freeze({
  CURRENT: 90,
  BACKLOG: 180,
  SPECULATIVE: 365,
  IDEA: 730
});
const TRELLO_LISTS = Object.freeze({
  "00-ideas": "Propositions",
  "05-clarify": "À clarifier",
  "10-verify": "À vérifier",
  "15-to-validate": "À valider",
  "18-accepted": "Planifié",
  "20-todo": "Planifié",
  "22-ready": "Planifié",
  "24-queue": "Planifié",
  "30-prep": "Planifié",
  "40-dev": "En cours",
  "50-tests": "Tests",
  "60-review": "Revue",
  "70-validation": "Revue Owner",
  "72-corrections": "Corrections",
  "80-blocked": "Bloqué",
  "90-done": "Terminé",
  "95-stable": "Terminé"
});

function hash(value) {
  return createHash("sha256").update(JSON.stringify(value), "utf8").digest("hex");
}

function safeDate(value, fallback) {
  const parsed = new Date(value || "");
  return Number.isFinite(parsed.getTime()) ? parsed : new Date(fallback);
}

function monday(date) {
  const result = new Date(date);
  result.setUTCHours(0, 0, 0, 0);
  const weekday = result.getUTCDay() || 7;
  result.setUTCDate(result.getUTCDate() - weekday + 1);
  return result;
}

function boundedText(value, max = 500) {
  return String(value || "").replaceAll("\0", "").trim().slice(0, max);
}

function projectKeys(project) {
  return new Set([project.id, project.name, ...(project.aliases || [])]
    .map((value) => String(value || "").trim().toLowerCase())
    .filter(Boolean));
}

export function buildProjectPlanning({ portfolio, tasks = [], at = new Date() } = {}) {
  const now = safeDate(at, new Date());
  const generatedAt = safeDate(portfolio?.generatedAt, now);
  const projects = (portfolio?.projects || []).map((project) => {
    const durationDays = Math.max(1, Math.min(
      Number(project.planning?.durationDays || DEFAULT_DURATIONS[project.category] || 180),
      3650
    ));
    const start = safeDate(project.planning?.startAt, generatedAt);
    const end = project.planning?.targetAt
      ? safeDate(project.planning.targetAt, new Date(start.getTime() + durationDays * DAY_MS))
      : new Date(start.getTime() + durationDays * DAY_MS);
    const keys = projectKeys(project);
    const linkedTasks = tasks.filter((task) => {
      const ref = String(task.projectId || task.project || "").toLowerCase();
      return keys.has(ref);
    });
    return {
      id: project.id,
      name: project.name,
      aliases: [...(project.aliases || [])],
      category: project.category,
      status: project.status,
      authority: project.authority,
      startAt: start.toISOString(),
      targetAt: end.toISOString(),
      durationDays: Math.ceil((end - start) / DAY_MS),
      durationWeeks: Number(((end - start) / (7 * DAY_MS)).toFixed(1)),
      durationMonths: Number(((end - start) / (30.4375 * DAY_MS)).toFixed(1)),
      scheduleSource: project.planning ? "DECLARED" : "SYSTEM_ESTIMATE",
      taskCount: linkedTasks.length,
      activeTaskCount: linkedTasks.filter((task) => !["90-done", "95-stable", "99-archived"].includes(task.status)).length,
      next: project.next || null
    };
  });
  const weekStart = monday(now);
  const weekEnd = new Date(weekStart.getTime() + 7 * DAY_MS);
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const monthEnd = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
  const overlaps = (project, start, end) =>
    new Date(project.startAt) < end && new Date(project.targetAt) >= start;
  return {
    schema: "aione.project-planning.v1",
    generatedAt: now.toISOString(),
    projects,
    week: {
      startAt: weekStart.toISOString(),
      endAt: weekEnd.toISOString(),
      projectIds: projects.filter((project) => overlaps(project, weekStart, weekEnd)).map((project) => project.id)
    },
    month: {
      startAt: monthStart.toISOString(),
      endAt: monthEnd.toISOString(),
      projectIds: projects.filter((project) => overlaps(project, monthStart, monthEnd)).map((project) => project.id)
    },
    warning: "Les durées SYSTEM_ESTIMATE sont des horizons de pilotage, pas des promesses de livraison."
  };
}

function readLines(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, "utf8").split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
}

export function createTrelloPlanningOutbox({
  runtimeRoot = "S:\\AI_LAB\\Runtime\\Planning",
  boardName = "AIONE — Agents autonomes",
  now = () => new Date()
} = {}) {
  const path = resolve(runtimeRoot, "trello-task-outbox.jsonl");
  mkdirSync(dirname(path), { recursive: true });

  function verify() {
    const entries = readLines(path);
    const issues = [];
    let previousHash = null;
    entries.forEach((entry, index) => {
      const stored = entry.hash;
      const unsigned = { ...entry };
      delete unsigned.hash;
      if (entry.previousHash !== previousHash) issues.push({ index, code: "CHAIN_MISMATCH" });
      if (hash(unsigned) !== stored) issues.push({ index, code: "HASH_MISMATCH" });
      previousHash = stored;
    });
    return { ok: issues.length === 0, entries: entries.length, head: previousHash, issues };
  }

  function prepare(tasks, { maximumCards = 3 } = {}) {
    const entries = readLines(path);
    const existing = new Set(entries.map((entry) => entry.idempotencyKey));
    const candidates = tasks
      .filter((task) => TRELLO_LISTS[task.status])
      .map((task) => {
        const payload = {
          boardName,
          listName: TRELLO_LISTS[task.status],
          taskId: boundedText(task.id, 160),
          project: boundedText(task.project || task.projectId || "AIONE", 200),
          title: boundedText(task.title, 300),
          description: boundedText(task.description, 1200),
          priority: boundedText(task.priority, 40),
          status: boundedText(task.status, 80)
        };
        return { payload, idempotencyKey: hash(payload) };
      })
      .filter((entry) => !existing.has(entry.idempotencyKey))
      .slice(0, Math.max(0, Math.min(Number(maximumCards) || 3, 3)));
    let previousHash = entries.at(-1)?.hash || null;
    const prepared = [];
    for (const candidate of candidates) {
      const entry = {
        schema: "aione.trello-task-outbox.v1",
        id: randomUUID(),
        createdAt: now().toISOString(),
        state: "READY_FOR_AUTHENTICATED_SYNC",
        externalMutationPerformed: false,
        idempotencyKey: candidate.idempotencyKey,
        previousHash,
        ...candidate.payload
      };
      entry.hash = hash(entry);
      appendFileSync(path, `${JSON.stringify(entry)}\n`, "utf8");
      previousHash = entry.hash;
      prepared.push(entry);
    }
    return { ok: true, prepared: prepared.length, entries: prepared, integrity: verify(), path };
  }

  function status() {
    const entries = readLines(path);
    return {
      schema: "aione.trello-planning-outbox-status.v1",
      boardName,
      pending: entries.filter((entry) => entry.state === "READY_FOR_AUTHENTICATED_SYNC").length,
      externalMutationPerformed: false,
      path,
      integrity: verify()
    };
  }

  return Object.freeze({ path, prepare, status, verify });
}
