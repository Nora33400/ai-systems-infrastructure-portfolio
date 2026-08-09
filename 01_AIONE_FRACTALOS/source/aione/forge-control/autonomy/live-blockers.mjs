const PIPELINE_STAGES = Object.freeze([
  "QUEUED",
  "PREPARING",
  "CONTEXT_LOADING",
  "EXECUTING",
  "TESTING",
  "REVIEWING",
  "AWAITING_HUMAN_REVIEW",
  "COMPLETED"
]);

const STATUS_ALIASES = Object.freeze({
  READY: "QUEUED",
  "20-todo": "QUEUED",
  "24-queue": "QUEUED",
  STARTING: "PREPARING",
  "30-prep": "PREPARING",
  WORKTREE_READY: "CONTEXT_LOADING",
  RUNNING: "EXECUTING",
  "40-dev": "EXECUTING",
  "50-tests": "TESTING",
  REVIEW: "REVIEWING",
  "60-review": "REVIEWING",
  "70-validation": "AWAITING_HUMAN_REVIEW",
  "95-stable": "COMPLETED",
  FAILED: "BLOCKED",
  "80-blocked": "BLOCKED"
});

const ACTIVE_STATES = new Set([
  "PREPARING",
  "CONTEXT_LOADING",
  "EXECUTING",
  "TESTING",
  "REVIEWING"
]);

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.values(value);
  return [];
}

function isoNow(now) {
  const value = typeof now === "function" ? now() : now;
  const date = value instanceof Date ? value : new Date(value || Date.now());
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString();
}

function normalizeStatus(value) {
  const raw = String(value || "QUEUED");
  return STATUS_ALIASES[raw] || STATUS_ALIASES[raw.toUpperCase()] || raw.toUpperCase();
}

function timestampOf(entry = {}) {
  return entry.at || entry.date || entry.createdAt || entry.updatedAt || entry.lastHeartbeat || entry.startedAt || null;
}

function compactHistory(entries, maximum = 20) {
  return asArray(entries)
    .map((entry) => ({
      at: timestampOf(entry),
      actor: entry.actor || entry.source || null,
      action: entry.action || entry.type || entry.stage || "state-observed",
      summary: entry.summary || entry.message || entry.lastAction || entry.status || "État observé",
      status: entry.status || entry.stage || null
    }))
    .sort((left, right) => String(left.at || "").localeCompare(String(right.at || "")))
    .slice(-maximum);
}

function stageTimeline(currentStatus) {
  const current = normalizeStatus(currentStatus);
  const currentIndex = PIPELINE_STAGES.indexOf(current);
  const stopped = ["BLOCKED", "PAUSED"].includes(current);
  return PIPELINE_STAGES.map((stage, index) => {
    let state = "PENDING";
    if (current === "COMPLETED" || (currentIndex >= 0 && index < currentIndex)) state = "DONE";
    if (currentIndex === index) state = "CURRENT";
    if (stopped && index === 0) state = "BLOCKED";
    return { id: stage, state };
  });
}

function pipelineForTask(task, cards, workerRuns) {
  const card = cards.find((item) => item.queueTaskId === task.id) || null;
  const workers = workerRuns.filter((item) => item.queueTaskId === task.id);
  const worker = workers.at(-1) || null;
  const queueStatus = normalizeStatus(task.status || card?.status || worker?.status);
  const workerStatus = normalizeStatus(worker?.status);
  // Un worker en cours décrit l'étape la plus précise. Une fois terminal, la
  // file redevient la source de vérité : une reprise QUEUED ne doit pas rester
  // visuellement bloquée par l'ancien résultat FAILED.
  const status = worker && ACTIVE_STATES.has(workerStatus) ? workerStatus : queueStatus;
  const history = compactHistory([
    ...asArray(card?.history),
    ...asArray(task.history),
    ...asArray(task.evidence),
    ...workers.flatMap((run) => [
      { at: run.startedAt, actor: "Forge Queue Worker", action: "worker-started", summary: run.currentTask || task.title, status: "PREPARING" },
      ...(run.lastHeartbeat ? [{ at: run.lastHeartbeat, actor: "Forge Queue Worker", action: "worker-heartbeat", summary: run.lastAction, status: run.status }] : []),
      ...(run.completedAt ? [{ at: run.completedAt, actor: "Forge Queue Worker", action: "worker-completed", summary: run.inactivityReason || run.status, status: run.status }] : [])
    ])
  ]);
  return {
    id: task.id,
    queueTaskId: task.id,
    cardId: card?.id || null,
    title: task.title || card?.title || task.id,
    project: task.project || card?.project || "AIONE Forge",
    priority: task.priority || card?.priority || null,
    status,
    rawState: {
      queue: task.status || null,
      card: card?.status || null,
      worker: worker?.status || null
    },
    active: ACTIVE_STATES.has(status),
    blocked: ["BLOCKED", "PAUSED"].includes(status),
    worker: worker ? {
      id: worker.id,
      pid: worker.pid || null,
      model: worker.model || null,
      lastHeartbeat: worker.lastHeartbeat || null,
      lastAction: worker.lastAction || null,
      currentCommand: worker.currentCommand || null,
      worktree: worker.worktree || null,
      historical: workerStatus !== status && !ACTIVE_STATES.has(workerStatus)
    } : null,
    stages: stageTimeline(status),
    history,
    updatedAt: history.at(-1)?.at || task.lastHeartbeat || task.completedAt || worker?.lastHeartbeat || worker?.completedAt || null
  };
}

function isResolved(incident) {
  return ["RESOLVED", "CLOSED", "RECOVERED"].includes(String(incident?.status || "OPEN").toUpperCase());
}

function blockerId(kind, id) {
  return `${kind}:${id || "unknown"}`;
}

function buildLiveBlockerSnapshot({
  queue = [],
  cards = [],
  workerRuns = [],
  incidents = [],
  commons = {},
  eligibility = {},
  resilience = {},
  now = () => new Date()
} = {}) {
  const generatedAt = isoNow(now);
  const queueItems = asArray(queue);
  const cardItems = asArray(cards);
  const runs = asArray(workerRuns);
  const incidentItems = asArray(incidents).filter((incident) => !isResolved(incident));
  const pipelines = queueItems.map((task) => pipelineForTask(task, cardItems, runs));
  const repairsByRoot = new Map();
  for (const task of queueItems.filter((item) => item.repairTargetQueueTaskId)) {
    const rootId = task.repairRootQueueTaskId || task.repairTargetQueueTaskId;
    const entries = repairsByRoot.get(rootId) || [];
    entries.push(task);
    repairsByRoot.set(rootId, entries);
  }
  const blockers = [];
  const blockerKeys = new Set();
  const addBlocker = (blocker) => {
    const key = blocker.id;
    if (blockerKeys.has(key)) return;
    blockerKeys.add(key);
    blockers.push(blocker);
  };

  for (const pipeline of pipelines.filter((item) => item.blocked)) {
    const task = queueItems.find((item) => item.id === pipeline.queueTaskId) || {};
    // Une tentative de réparation reste visible dans `pipelines`, mais n'est
    // jamais une seconde cause actionnable. La cause racine porte son état.
    if (task.repairTargetQueueTaskId) continue;
    const cause = asArray(task.evidence).at(-1)?.summary || pipeline.history.at(-1)?.summary || task.reason || pipeline.status;
    const repair = (repairsByRoot.get(pipeline.queueTaskId) || []).at(-1) || null;
    const repairStatus = normalizeStatus(repair?.status);
    const retryCount = Math.max(0, Number(repair?.retryCount) || 0);
    const maximumRetries = Math.max(0, Number(repair?.maximumRetries) || 0);
    const repairActive = Boolean(repair && ["QUEUED", "PREPARING", "CONTEXT_LOADING", "EXECUTING", "TESTING", "REVIEWING", "AWAITING_HUMAN_REVIEW"].includes(repairStatus));
    const repairExhausted = Boolean(repair && ["BLOCKED", "FAILED", "PAUSED"].includes(repairStatus) && retryCount >= maximumRetries);
    const repairRetryable = Boolean(repair && ["BLOCKED", "FAILED", "PAUSED"].includes(repairStatus) && retryCount < maximumRetries);
    const repairable = !repair || repairRetryable;
    addBlocker({
      id: blockerId("queue", pipeline.queueTaskId),
      kind: "LOCAL_PIPELINE",
      scope: "LOCAL",
      title: pipeline.title,
      summary: cause,
      status: pipeline.status,
      severity: pipeline.status === "BLOCKED" ? "ERROR" : "WARNING",
      blocking: true,
      repairable,
      queueTaskId: pipeline.queueTaskId,
      cardId: pipeline.cardId,
      repairTaskId: repair?.id || null,
      repairStatus: repair ? repairStatus : null,
      repairActive,
      repairExhausted,
      retryCount: repair ? retryCount : null,
      maximumRetries: repair ? maximumRetries : null,
      quickActions: repairable ? ["IMMUNE_DOCTOR", "AI_LOCAL_REPAIR"] : ["IMMUNE_DOCTOR"],
      history: pipeline.history
    });
  }

  for (const inspected of asArray(eligibility.inspected).filter((item) => item.eligible === false)) {
    const pipeline = pipelines.find((item) => item.queueTaskId === inspected.queueTaskId);
    const task = queueItems.find((item) => item.id === inspected.queueTaskId);
    if (task?.repairTargetQueueTaskId) continue;
    addBlocker({
      id: blockerId("queue", inspected.queueTaskId),
      kind: "LOCAL_CAPABILITY",
      scope: "LOCAL",
      title: inspected.title || pipeline?.title || inspected.queueTaskId,
      summary: inspected.reason || `Capacité non disponible: ${asArray(inspected.unsupportedCapabilities).join(", ")}`,
      status: "BLOCKED",
      severity: "ERROR",
      blocking: true,
      repairable: true,
      queueTaskId: inspected.queueTaskId || null,
      cardId: inspected.cardId || pipeline?.cardId || null,
      quickActions: ["IMMUNE_DOCTOR", "AI_LOCAL_REPAIR"],
      history: pipeline?.history || []
    });
  }

  const knownQueueCards = new Set(queueItems.map((item) => item.id));
  for (const card of cardItems.filter((item) => normalizeStatus(item.status) === "BLOCKED" && !knownQueueCards.has(item.queueTaskId))) {
    const refused = /^refus/i.test(String(card.finalDecision || ""));
    addBlocker({
      id: blockerId("card", card.id),
      kind: refused ? "HUMAN_DECISION" : "LOCAL_CARD",
      scope: "LOCAL",
      title: card.title || card.id,
      summary: card.finalDecision || compactHistory(card.history).at(-1)?.summary || "Carte bloquée",
      status: "BLOCKED",
      severity: refused ? "INFO" : "WARNING",
      blocking: !refused,
      repairable: !refused,
      queueTaskId: card.queueTaskId || null,
      cardId: card.id,
      quickActions: refused ? [] : ["IMMUNE_DOCTOR", "AI_LOCAL_REPAIR"],
      history: compactHistory(card.history)
    });
  }

  const externalConnections = asArray(resilience.externalConnections);
  const externalIds = externalConnections.map((connection) => String(connection.id || "").toLowerCase());
  for (const incident of incidentItems) {
    const searchable = `${incident.id || ""} ${incident.component || ""} ${incident.title || ""} ${incident.summary || ""}`.toLowerCase();
    const external = externalIds.some((id) => id && searchable.includes(id));
    addBlocker({
      id: blockerId("incident", incident.id),
      kind: external ? "EXTERNAL_DEFERRED_INCIDENT" : "LOCAL_INCIDENT",
      scope: external ? "EXTERNAL_OPTIONAL" : "LOCAL",
      title: incident.title || incident.signature || incident.id || "Incident actif",
      summary: incident.summary || incident.lastError || incident.reason || incident.status || "Incident actif",
      status: external ? "DEFERRED_LOCAL" : String(incident.status || "OPEN").toUpperCase(),
      severity: incident.critical === true ? "CRITICAL" : "WARNING",
      blocking: !external,
      repairable: !external,
      incidentId: incident.id || null,
      quickActions: external ? [] : ["IMMUNE_DOCTOR", "AI_LOCAL_REPAIR"],
      history: compactHistory(incident.history || [incident])
    });
  }

  for (const connection of externalConnections.filter((item) => item.connected === false || item.state === "DEFERRED_LOCAL")) {
    addBlocker({
      id: blockerId("external", connection.id),
      kind: "EXTERNAL_DEPENDENCY_DEFERRED",
      scope: "EXTERNAL_OPTIONAL",
      title: connection.id || "Dépendance externe",
      summary: `Connexion différée; reprise locale via ${connection.localFallback || "LOCAL_OUTBOX_AND_LEDGER"}.`,
      status: "DEFERRED_LOCAL",
      severity: "INFO",
      blocking: false,
      repairable: false,
      connectionId: connection.id || null,
      quickActions: [],
      history: []
    });
  }

  const commonsPosts = asArray(commons.posts || commons.feed?.posts || commons.notifications);
  const openHumanRequests = commonsPosts.filter((post) => post.channel === "HUMAN_REQUEST" && String(post.state || "OPEN").toUpperCase() === "OPEN");
  const localBlockers = blockers.filter((item) => item.blocking);
  const externalDeferred = blockers.filter((item) => item.scope === "EXTERNAL_OPTIONAL");
  const activePipelines = pipelines.filter((item) => item.active);
  const currentPipeline = activePipelines.at(-1)
    || pipelines.find((item) => item.id === eligibility.selected?.queueTaskId)
    || pipelines.find((item) => item.status === "QUEUED")
    || pipelines.at(-1)
    || null;
  const state = localBlockers.some((item) => item.severity === "CRITICAL")
    ? "CRITICAL_LOCAL_BLOCKER"
    : localBlockers.length
      ? "LOCAL_BLOCKERS_PRESENT"
      : activePipelines.length
        ? "RUNNING_LOCAL"
        : "LOCAL_READY";

  return {
    schema: "aione.live-blockers.v1",
    generatedAt,
    mode: "LOCAL_LOCAL",
    state,
    developmentAutonomy: resilience.developmentAutonomy || "AVAILABLE_WITHOUT_EXTERNAL_CONNECTIONS",
    counts: {
      pipelines: pipelines.length,
      activePipelines: activePipelines.length,
      localBlocking: localBlockers.length,
      localRepairable: localBlockers.filter((item) => item.repairable).length,
      externalDeferred: externalDeferred.length,
      openHumanRequests: Number(commons.openHumanRequests ?? openHumanRequests.length)
    },
    blockers,
    localRepairable: blockers.filter((item) => item.blocking && item.repairable),
    externalDeferred,
    pipelines,
    currentContext: {
      currentPipelineId: currentPipeline?.id || null,
      activePipelineIds: activePipelines.map((item) => item.id),
      selectedQueueTaskId: eligibility.selected?.queueTaskId || null,
      latestWorkerRun: runs.at(-1) ? {
        id: runs.at(-1).id,
        queueTaskId: runs.at(-1).queueTaskId,
        status: normalizeStatus(runs.at(-1).status),
        lastHeartbeat: runs.at(-1).lastHeartbeat || null,
        lastAction: runs.at(-1).lastAction || null
      } : null,
      openHumanRequests: openHumanRequests.map((post) => ({
        id: post.id,
        title: post.title,
        importance: post.importance || "NORMAL",
        createdAt: post.createdAt || null
      })),
      localSourceOfTruth: resilience.sourceOfTruth || null,
      externalDependenciesBlocking: 0
    }
  };
}

export { PIPELINE_STAGES, buildLiveBlockerSnapshot };
