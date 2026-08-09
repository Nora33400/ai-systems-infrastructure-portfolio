import { createHash } from "node:crypto";

const DAY_MS = 86_400_000;
const DEFAULT_PROJECT_DURATIONS = Object.freeze({
  CURRENT: 90,
  BACKLOG: 180,
  SPECULATIVE: 365,
  IDEA: 730
});
const TERMINAL_TASK_STATES = new Set(["COMPLETED", "DONE", "STABLE", "90-DONE", "95-STABLE", "99-ARCHIVED"]);
const BLOCKED_TASK_STATES = new Set(["BLOCKED", "FAILED", "80-BLOCKED", "QUARANTINED", "AWAITING-PERMISSION"]);
const PLANNABLE_TASK_STATES = new Set(["20-TODO", "22-READY", "24-QUEUE", "READY", "QUEUED"]);
const TERMINAL_PROJECT_STATES = new Set(["COMPLETED", "DONE", "STABLE", "OPERATIONAL", "95-STABLE", "99-ARCHIVED"]);
const KEYWORD_HINTS = Object.freeze({
  "digital-programming": [
    "software", "programming", "programme", "code", "automation", "interface", "data", "infrastructure",
    "developer", "runtime", "forge", "docker", "webui", "mousecode", "fractalos", "autonomy"
  ],
  "scientific-extension": [
    "scientific", "science", "research", "recherche", "mathematics", "math", "simulation", "experiment",
    "hypothesis", "corpus", "formula", "formule", "moda", "cognitive"
  ],
  "social-mediation": [
    "social", "mediation", "communication", "community", "communaute", "accessibility", "consent",
    "collective", "wellbeing", "digital life", "vie numerique"
  ],
  "local-creation": [
    "image", "video", "audio", "music", "musique", "3d", "writing", "ecriture", "creative", "creation", "media"
  ]
});

const PROVIDER_POLICY = Object.freeze({
  selectedMode: "LOCAL_FREE",
  externalActionPerformed: false,
  modes: Object.freeze([
    Object.freeze({
      id: "LOCAL_FREE",
      enabled: true,
      active: true,
      autoSelectable: true,
      cost: "FREE",
      fallbackMode: null
    }),
    Object.freeze({
      id: "OPTIONAL_FREE_CONNECTOR",
      enabled: true,
      active: false,
      autoSelectable: false,
      degradable: true,
      cost: "FREE",
      fallbackMode: "LOCAL_FREE"
    }),
    Object.freeze({
      id: "FUTURE_PAID",
      enabled: false,
      active: false,
      autoSelectable: false,
      cost: "PAID_OR_UNKNOWN",
      activation: "EXPLICIT_FUTURE_CONFIGURATION_ONLY"
    })
  ])
});

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
}

function hash(value) {
  return createHash("sha256").update(JSON.stringify(stable(value)), "utf8").digest("hex");
}

function copy(value) {
  return structuredClone(value);
}

function safeDate(value, fallback) {
  const candidate = new Date(value ?? "");
  return Number.isFinite(candidate.getTime()) ? candidate : new Date(fallback);
}

function boundedInteger(value, fallback, minimum, maximum) {
  const candidate = Number(value);
  if (!Number.isFinite(candidate)) return fallback;
  return Math.max(minimum, Math.min(Math.trunc(candidate), maximum));
}

function canonical(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, " ")
    .trim();
}

function uniqueStrings(values) {
  return [...new Set((Array.isArray(values) ? values : [])
    .map((value) => typeof value === "object" && value ? value.id : value)
    .map((value) => String(value ?? "").trim())
    .filter(Boolean))];
}

function normalizeStatus(value) {
  return String(value || "QUEUED").trim().toUpperCase().replaceAll("_", "-");
}

function priorityScore(value) {
  const normalized = String(value || "P2").toUpperCase();
  const match = /^P([0-9])$/u.exec(normalized);
  return match ? 1_000 - Number(match[1]) * 100 : 0;
}

function ecosystemDefinitions(domains) {
  const entries = Array.isArray(domains?.ecosystems) ? domains.ecosystems : [];
  const seen = new Set();
  return entries.map((entry, index) => {
    const id = String(entry?.id || `ecosystem-${index + 1}`).trim();
    if (!id || seen.has(id)) throw new Error(`ecosystemId duplique ou vide: ${id || "<vide>"}`);
    seen.add(id);
    return {
      id,
      name: String(entry.name || id),
      mission: String(entry.mission || ""),
      domains: uniqueStrings(entry.domains),
      orchestratorRole: String(entry.orchestratorRole || "AI_ECOSYSTEM_ORCHESTRATOR")
    };
  });
}

function assignmentFor(project, definitions) {
  const known = new Set(definitions.map((entry) => entry.id));
  const explicit = String(project.ecosystemId || project.planning?.ecosystemId || "").trim();
  if (explicit && known.has(explicit)) {
    return { ecosystemId: explicit, source: "DECLARED", confidence: 1 };
  }

  const text = canonical([
    project.id,
    project.name,
    ...(project.aliases || []),
    ...(project.tags || []),
    project.category,
    project.status,
    project.next
  ].join(" "));
  let best = null;
  for (const definition of definitions) {
    const keywords = uniqueStrings([
      ...(KEYWORD_HINTS[definition.id] || []),
      ...definition.domains
    ]).map(canonical).filter((entry) => entry.length >= 3);
    const hits = keywords.filter((keyword) => text.includes(keyword));
    const candidate = { ecosystemId: definition.id, hits };
    if (!best || hits.length > best.hits.length || (hits.length === best.hits.length && definition.id < best.ecosystemId)) {
      best = candidate;
    }
  }
  if (best?.hits.length) {
    return {
      ecosystemId: best.ecosystemId,
      source: "INFERRED_KEYWORDS",
      confidence: Math.min(0.9, 0.55 + best.hits.length * 0.1),
      evidence: best.hits.slice(0, 8)
    };
  }
  const preferred = known.has("digital-programming")
    ? "digital-programming"
    : definitions[0]?.id || "unassigned";
  return { ecosystemId: preferred, source: "DEFAULT_LOCAL_ECOSYSTEM", confidence: 0.25, evidence: [] };
}

function projectReferences(project) {
  return new Set([project.id, project.name, ...(project.aliases || [])].map(canonical).filter(Boolean));
}

function linkedTasksFor(project, tasks) {
  const references = projectReferences(project);
  return tasks.filter((task) => references.has(canonical(task.projectId || task.project)));
}

function taskState(task, byId, now, projectDependencyState = {}) {
  const status = normalizeStatus(task.status);
  const dependencyIds = uniqueStrings(task.dependencies);
  const missingDependencyIds = dependencyIds.filter((id) => !byId.has(id));
  const incompleteDependencyIds = dependencyIds.filter((id) => {
    const dependency = byId.get(id);
    return dependency && !TERMINAL_TASK_STATES.has(normalizeStatus(dependency.status));
  });
  const notBefore = safeDate(task.notBefore, now);
  const reasons = [];
  if (BLOCKED_TASK_STATES.has(status)) reasons.push(`TASK_STATE:${status}`);
  if (missingDependencyIds.length) reasons.push("MISSING_DEPENDENCY");
  if (incompleteDependencyIds.length) reasons.push("INCOMPLETE_DEPENDENCY");
  if (notBefore > now) reasons.push("NOT_BEFORE");
  if (projectDependencyState.missing?.length) reasons.push("MISSING_PROJECT_DEPENDENCY");
  if (projectDependencyState.incomplete?.length) reasons.push("INCOMPLETE_PROJECT_DEPENDENCY");
  const terminal = TERMINAL_TASK_STATES.has(status);
  const schedulable = PLANNABLE_TASK_STATES.has(status);
  const waiting = !terminal && !schedulable && !BLOCKED_TASK_STATES.has(status);
  return {
    terminal,
    schedulable,
    ready: !terminal && schedulable && reasons.length === 0,
    blocked: !terminal && !waiting && reasons.length > 0,
    waiting,
    reasons,
    dependencyIds,
    missingDependencyIds,
    incompleteDependencyIds
  };
}

function milestoneWindows(now, projects, tasks) {
  return [7, 30, 90, 365].map((days) => {
    const end = new Date(now.getTime() + days * DAY_MS);
    return {
      horizonDays: days,
      startAt: now.toISOString(),
      endAt: end.toISOString(),
      projectIds: projects
        .filter((project) => new Date(project.targetAt) <= end)
        .map((project) => project.id),
      taskIds: tasks
        .filter((task) => {
          const dueAt = task.dueAt || task.targetAt;
          return dueAt && safeDate(dueAt, new Date(8.64e15)) <= end;
        })
        .map((task) => String(task.id))
    };
  });
}

function normalizedLanes(gpuConfig) {
  const lanes = (Array.isArray(gpuConfig?.lanes) ? gpuConfig.lanes : [])
    .filter((lane) => lane?.id)
    .map((lane) => ({
      id: String(lane.id),
      label: String(lane.label || lane.id),
      roles: uniqueStrings(lane.roles),
      focusRotation: uniqueStrings(lane.focusRotation)
    }));
  if (lanes.length === 0) {
    return [
      { id: "local-cpu-fallback", label: "Local free fallback", roles: ["analysis"], focusRotation: ["analysis"] }
    ];
  }
  return lanes;
}

function roundRobinReady(ecosystems) {
  const queues = ecosystems
    .filter((ecosystem) => ecosystem.readyTasks.length)
    .map((ecosystem) => ({ ecosystemId: ecosystem.id, tasks: [...ecosystem.readyTasks], index: 0 }));
  const result = [];
  let remaining = queues.reduce((sum, queue) => sum + queue.tasks.length, 0);
  while (remaining > 0) {
    for (const queue of queues) {
      if (queue.index >= queue.tasks.length) continue;
      result.push({ ecosystemId: queue.ecosystemId, task: queue.tasks[queue.index] });
      queue.index += 1;
      remaining -= 1;
    }
  }
  return result;
}

function buildSchedule({ ecosystems, gpuConfig, now }) {
  const lanes = normalizedLanes(gpuConfig);
  const partitionMinutes = boundedInteger(gpuConfig?.schedule?.partitionMinutes, 60, 15, 240);
  const partitionMs = partitionMinutes * 60_000;
  const startMs = Math.ceil(now.getTime() / partitionMs) * partitionMs;
  const partitionCount = Math.ceil((24 * 60) / partitionMinutes);
  const ready = roundRobinReady(ecosystems);
  let assignmentIndex = 0;
  const slots = [];
  for (let partition = 0; partition < partitionCount; partition += 1) {
    const startAt = new Date(startMs + partition * partitionMs);
    const endAt = new Date(startAt.getTime() + partitionMs);
    for (const lane of lanes) {
      const assignment = ready[assignmentIndex++] || null;
      slots.push({
        id: `${startAt.toISOString()}::${lane.id}`,
        laneId: lane.id,
        laneLabel: lane.label,
        startAt: startAt.toISOString(),
        endAt: endAt.toISOString(),
        focus: lane.focusRotation[partition % Math.max(1, lane.focusRotation.length)] || "safe-local-maintenance",
        assignmentKind: assignment ? "PROJECT_TASK" : "SAFE_LOCAL_MAINTENANCE",
        ecosystemId: assignment?.ecosystemId || null,
        projectId: assignment?.task.projectId || null,
        taskId: assignment?.task.id || null,
        providerMode: "LOCAL_FREE",
        externalActionAllowed: false
      });
    }
  }
  return {
    mode: "CONTINUOUS_24_7_LOCAL_PLAN",
    startAt: new Date(startMs).toISOString(),
    endAt: new Date(startMs + partitionCount * partitionMs).toISOString(),
    partitionMinutes,
    lanes,
    slots,
    assignedTaskCount: slots.filter((slot) => slot.assignmentKind === "PROJECT_TASK").length,
    maintenanceSlotCount: slots.filter((slot) => slot.assignmentKind === "SAFE_LOCAL_MAINTENANCE").length
  };
}

export function buildMultiEcosystemPlan({
  portfolio = { projects: [] },
  ecosystemDomains = { ecosystems: [] },
  gpuConfig = { lanes: [] },
  tasks = [],
  at = new Date()
} = {}) {
  const now = safeDate(at, new Date());
  const definitions = ecosystemDefinitions(ecosystemDomains);
  const sourceProjects = Array.isArray(portfolio?.projects) ? portfolio.projects : [];
  const sourceTasks = Array.isArray(tasks) ? tasks : [];
  const taskById = new Map(sourceTasks.filter((task) => task?.id).map((task) => [String(task.id), task]));
  const sourceProjectById = new Map(sourceProjects.filter((project) => project?.id).map((project) => [String(project.id), project]));
  const projects = sourceProjects.map((project) => {
    const assignment = assignmentFor(project, definitions);
    const durationDays = boundedInteger(
      project.planning?.durationDays,
      DEFAULT_PROJECT_DURATIONS[project.category] || 180,
      1,
      3650
    );
    const start = safeDate(project.planning?.startAt, portfolio.generatedAt || now);
    const target = project.planning?.targetAt
      ? safeDate(project.planning.targetAt, new Date(start.getTime() + durationDays * DAY_MS))
      : new Date(start.getTime() + durationDays * DAY_MS);
    const projectDependencies = uniqueStrings([...(project.dependencies || []), ...(project.planning?.dependencies || [])]);
    const projectDependencyState = {
      missing: projectDependencies.filter((id) => !sourceProjectById.has(id)),
      incomplete: projectDependencies.filter((id) => {
        const dependency = sourceProjectById.get(id);
        return dependency && !TERMINAL_PROJECT_STATES.has(normalizeStatus(dependency.status));
      })
    };
    const linkedTasks = linkedTasksFor(project, sourceTasks).map((task) => {
      const state = taskState(task, taskById, now, projectDependencyState);
      return {
        id: String(task.id),
        projectId: String(project.id),
        title: String(task.title || task.id),
        priority: String(task.priority || "P2"),
        status: normalizeStatus(task.status),
        notBefore: safeDate(task.notBefore, now).toISOString(),
        dueAt: task.dueAt || task.targetAt || null,
        ...state
      };
    }).sort((left, right) =>
      priorityScore(right.priority) - priorityScore(left.priority) ||
      left.notBefore.localeCompare(right.notBefore) ||
      left.id.localeCompare(right.id));
    return {
      id: String(project.id),
      name: String(project.name || project.id),
      ecosystemId: assignment.ecosystemId,
      ecosystemAssignment: assignment,
      category: String(project.category || "BACKLOG"),
      status: String(project.status || "UNKNOWN"),
      authority: String(project.authority || "READ_ONLY"),
      startAt: start.toISOString(),
      targetAt: target.toISOString(),
      durationDays: Math.max(1, Math.ceil((target - start) / DAY_MS)),
      dependencies: projectDependencies,
      dependencyState: projectDependencyState,
      tasks: linkedTasks,
      readyTaskIds: linkedTasks.filter((task) => task.ready).map((task) => task.id),
      blockedTaskIds: linkedTasks.filter((task) => task.blocked).map((task) => task.id),
      waitingTaskIds: linkedTasks.filter((task) => task.waiting).map((task) => task.id),
      completedTaskIds: linkedTasks.filter((task) => task.terminal).map((task) => task.id)
    };
  });

  const ecosystems = definitions.map((definition) => {
    const ecosystemProjects = projects.filter((project) => project.ecosystemId === definition.id);
    const ecosystemTasks = ecosystemProjects.flatMap((project) => project.tasks);
    const knownProjectIds = new Set(projects.map((project) => project.id));
    const dependencyEdges = ecosystemProjects.flatMap((project) => project.dependencies.map((dependencyId) => ({
      fromProjectId: project.id,
      toProjectId: dependencyId,
      state: knownProjectIds.has(dependencyId) ? "KNOWN" : "MISSING"
    })));
    return {
      ...definition,
      projects: ecosystemProjects,
      readyTasks: ecosystemTasks.filter((task) => task.ready),
      blockedTasks: ecosystemTasks.filter((task) => task.blocked),
      waitingTasks: ecosystemTasks.filter((task) => task.waiting),
      completedTasks: ecosystemTasks.filter((task) => task.terminal),
      dependencies: dependencyEdges,
      milestones: milestoneWindows(now, ecosystemProjects, ecosystemTasks)
    };
  });
  const schedule = buildSchedule({ ecosystems, gpuConfig, now });
  const result = {
    schema: "aione.multi-ecosystem-plan.v1",
    generatedAt: now.toISOString(),
    planningOnly: true,
    externalActionsPerformed: false,
    providerPolicy: copy(PROVIDER_POLICY),
    ecosystems,
    schedule,
    totals: {
      ecosystems: ecosystems.length,
      projects: projects.length,
      tasks: projects.reduce((sum, project) => sum + project.tasks.length, 0),
      ready: ecosystems.reduce((sum, ecosystem) => sum + ecosystem.readyTasks.length, 0),
      blocked: ecosystems.reduce((sum, ecosystem) => sum + ecosystem.blockedTasks.length, 0),
      waiting: ecosystems.reduce((sum, ecosystem) => sum + ecosystem.waitingTasks.length, 0),
      completed: ecosystems.reduce((sum, ecosystem) => sum + ecosystem.completedTasks.length, 0)
    },
    warnings: [
      "Ce plan n'execute aucune action et n'effectue aucune mutation externe.",
      "Les affectations INFERRED_KEYWORDS ou DEFAULT_LOCAL_ECOSYSTEM doivent rester visibles et contestables.",
      "Seuls TODO, READY et QUEUED sont affectes aux GPU; REVIEW et VALIDATION restent visibles en attente.",
      "Une dependance projet non terminale bloque ses nouvelles taches planifiables.",
      "OPTIONAL_FREE_CONNECTOR est degradable; son indisponibilite ne bloque jamais LOCAL_FREE.",
      "FUTURE_PAID est desactive et ne peut jamais etre selectionne automatiquement."
    ]
  };
  result.planHash = hash(result);
  return result;
}

export { PLANNABLE_TASK_STATES, PROVIDER_POLICY };
