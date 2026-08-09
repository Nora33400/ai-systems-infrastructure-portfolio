const RETRYABLE_REPAIR_STATES = new Set(["BLOCKED", "FAILED", "PAUSED"]);

function planRepairRetry(task, { at = new Date().toISOString() } = {}) {
  if (!task || typeof task !== "object") {
    return { eligible: false, reason: "REPAIR_TASK_MISSING", patch: null };
  }
  const status = String(task.status || "").toUpperCase();
  if (!RETRYABLE_REPAIR_STATES.has(status)) {
    return { eligible: false, reason: "REPAIR_ALREADY_ACTIVE_OR_TERMINAL", patch: null };
  }
  const retryCount = Math.max(0, Number(task.retryCount) || 0);
  const maximumRetries = Math.max(0, Number(task.maximumRetries) || 0);
  if (retryCount >= maximumRetries) {
    return { eligible: false, reason: "REPAIR_RETRY_BUDGET_EXHAUSTED", patch: null };
  }
  return {
    eligible: true,
    reason: "BOUNDED_REPAIR_RETRY",
    patch: {
      status: "QUEUED",
      retryCount: retryCount + 1,
      scheduledAt: at,
      startedAt: null,
      lastHeartbeat: null,
      evidence: [
        ...(Array.isArray(task.evidence) ? task.evidence : []),
        {
          type: "bounded-repair-retry",
          at,
          summary: `Reprise locale bornée ${retryCount + 1}/${maximumRetries}; aucun sous-agent de réparation récursif n'est créé.`,
          data: {
            previousStatus: status,
            retryCount: retryCount + 1,
            maximumRetries,
            repairTargetQueueTaskId: task.repairTargetQueueTaskId || null
          }
        }
      ]
    }
  };
}

export { RETRYABLE_REPAIR_STATES, planRepairRetry };
