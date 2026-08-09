import assert from "node:assert/strict";
import test from "node:test";

import { planRepairRetry } from "./repair-retry.mjs";

test("a blocked repair is requeued within its existing retry budget", () => {
  const result = planRepairRetry({
    id: "REPAIR-1",
    status: "BLOCKED",
    retryCount: 1,
    maximumRetries: 3,
    repairTargetQueueTaskId: "TASK-1",
    evidence: []
  }, { at: "2026-08-03T20:30:00.000Z" });

  assert.equal(result.eligible, true);
  assert.equal(result.patch.status, "QUEUED");
  assert.equal(result.patch.retryCount, 2);
  assert.equal(result.patch.evidence.at(-1).data.repairTargetQueueTaskId, "TASK-1");
});

test("an active repair is not duplicated or requeued", () => {
  const result = planRepairRetry({ status: "QUEUED", retryCount: 0, maximumRetries: 3 });
  assert.equal(result.eligible, false);
  assert.equal(result.reason, "REPAIR_ALREADY_ACTIVE_OR_TERMINAL");
});

test("an exhausted repair cannot create an unbounded retry loop", () => {
  const result = planRepairRetry({ status: "FAILED", retryCount: 3, maximumRetries: 3 });
  assert.equal(result.eligible, false);
  assert.equal(result.reason, "REPAIR_RETRY_BUDGET_EXHAUSTED");
});
