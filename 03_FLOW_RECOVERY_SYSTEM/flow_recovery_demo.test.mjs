import assert from "node:assert/strict";
import test from "node:test";

import { runFlowRecoveryDemo } from "./flow_recovery_demo.mjs";

test("logical flow detects, bounds, restores, validates, and returns", () => {
  const report = runFlowRecoveryDemo();
  assert.equal(report.detection.state, "CRITICAL_LOCAL_BLOCKER");
  assert.ok(report.detection.local_blockers > 0);
  assert.equal(report.recovery.retry_eligible, true);
  assert.equal(report.recovery.retry_count, 1);
  assert.equal(report.recovery.corruption_detected, true);
  assert.equal(report.recovery.data_loss_risk_detected, true);
  assert.equal(report.recovery.restore_authorized, true);
  assert.equal(report.recovery.final_state, "LOCAL_READY");
  assert.equal(report.recovery.remaining_blockers, 0);
  assert.deepEqual(report.jobs, { submitted: 3, completed: 3, retried: 1, lost: 0 });
  assert.deepEqual(report.transitions, [
    "AVAILABLE", "OBSERVED", "SUSPECT", "RESTRICTED", "ISOLATED",
    "DIAGNOSTIC", "REPAIRING", "RELOADING", "VALIDATING",
    "LIMITED_RETURN", "AVAILABLE"
  ]);
});

