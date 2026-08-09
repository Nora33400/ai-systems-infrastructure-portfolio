import type {
  Lot,
  LotState,
} from "../models/lot.model.js";

import {
  appendAuditEvent,
} from "../events/audit.event.js";

import {
  canonicalize,
  calculateLotArtifactHash,
  deterministicHash,
} from "../utils/deterministic-hash.util.js";

import {
  ApprovalError,
  TransitionError,
  approveLot,
  isLotState,
  mutateLot,
  refreshApprovalState,
  transitionLot,
} from "../states/lot-state.machine.js";

import {
  MemoryIdempotencyStore,
  createCommandId,
  createIdempotencyRecord,
  executeOnce,
  type IdempotencyCommand,
} from "../utils/idempotence.util.js";

interface TestCase {
  name: string;
  run: () => void;
}

const tests: TestCase[] = [];

function test(
  name: string,
  run: () => void,
): void {
  tests.push({ name, run });
}

function assert(
  condition: unknown,
  message: string,
): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

function assertEqual<T>(
  actual: T,
  expected: T,
  message: string,
): void {
  if (actual !== expected) {
    throw new Error(
      `${message}\nExpected: ${String(expected)}` +
      `\nActual: ${String(actual)}`,
    );
  }
}

function assertNotEqual<T>(
  actual: T,
  expected: T,
  message: string,
): void {
  if (actual === expected) {
    throw new Error(
      `${message}\nBoth values were: ${String(actual)}`,
    );
  }
}

function assertThrows(
  operation: () => void,
  predicate: (error: unknown) => boolean,
  message: string,
): void {
  let captured: unknown;

  try {
    operation();
  } catch (error: unknown) {
    captured = error;
  }

  assert(
    captured !== undefined,
    `${message}: no error was thrown.`,
  );

  assert(
    predicate(captured),
    `${message}: an unexpected error was thrown.`,
  );
}

function createLot(
  status: LotState = "DRAFT",
): Lot {
  const now = "2026-07-23T16:00:00.000Z";

  return {
    schema_version: "1.0",
    lot_id: "LOT-AUTONOMY-001",
    task_id: "TASK-AUTONOMY",
    title: "Autonomy foundation",
    description: "Implement the controlled autonomy foundation.",
    status,

    scope: {
      allowed_paths: [
        "src/autonomy/**",
      ],
      allowed_actions: [
        "write_project_files",
        "run_tests",
      ],
      forbidden_actions: [
        "deploy_publicly",
      ],
    },

    dependencies: [],
    requested_capabilities: [
      "write_project_files",
      "run_tests",
    ],

    artifacts: {
      created: [],
      modified: [],
      deleted: [],
    },

    verification: {
      commands: [
        "npm test",
      ],
      tests_passed: false,
      lint_passed: false,
      security_scan_passed: false,
      results: [],
    },

    risk: {
      level: "medium",
      reasons: [
        "Introduces autonomous task controls.",
      ],
    },

    approval: {
      required_level: "A2",
      artifact_hash: null,
      approved_hash: null,
      approved_by: null,
      approved_at: null,
      expires_at: null,
      allowed_capabilities: [],
      valid: false,
    },

    rollback: {
      strategy: "git_revert",
      instructions: [
        "Revert the lot commit.",
      ],
    },

    audit: {
      created_at: now,
      updated_at: now,
      events: [],
    },
  };
}

function createApprovedLot(): Lot {
  const lot = createLot("AWAITING_APPROVAL");
  const hash = calculateLotArtifactHash(lot);

  lot.approval.artifact_hash = hash;

  return approveLot(lot, {
    approved_hash: hash,
    approved_by: "the owner",
    expires_at: "2099-01-01T00:00:00.000Z",
    allowed_capabilities: [
      "write_project_files",
      "run_tests",
    ],
  });
}

test("creates a valid lot", () => {
  const lot = createLot();

  assertEqual(
    lot.schema_version,
    "1.0",
    "Schema version must be present.",
  );

  assertEqual(
    lot.status,
    "DRAFT",
    "A new lot must start in DRAFT.",
  );

  assertEqual(
    lot.audit.events.length,
    0,
    "A new lot must have an empty audit history.",
  );
});

test("rejects unknown state identifiers", () => {
  assertEqual(
    isLotState("DRAFT"),
    true,
    "DRAFT must be a known state.",
  );

  assertEqual(
    isLotState("UNKNOWN_STATE"),
    false,
    "Unknown states must be rejected.",
  );
});

test("performs an allowed transition", () => {
  const lot = createLot();

  transitionLot(lot, "DESIGNED", {
    agent_id: "test-agent",
    reason: "Design completed.",
  });

  assertEqual(
    lot.status,
    "DESIGNED",
    "The lot must enter DESIGNED.",
  );

  assertEqual(
    lot.audit.events.at(-1)?.event_type,
    "STATE_TRANSITION",
    "A successful transition must be audited.",
  );
});

test("rejects an invalid transition without changing state", () => {
  const lot = createLot();

  assertThrows(
    () => transitionLot(lot, "COMPLETED"),
    (error: unknown) =>
      error instanceof TransitionError &&
      error.code === "INVALID_LOT_TRANSITION",
    "Invalid transition must throw TransitionError",
  );

  assertEqual(
    lot.status,
    "DRAFT",
    "The state must remain unchanged.",
  );

  assertEqual(
    lot.audit.events.at(-1)?.event_type,
    "STATE_TRANSITION_REJECTED",
    "The rejected transition must be audited.",
  );
});

test("appends audit events", () => {
  const lot = createLot();

  appendAuditEvent(lot, {
    event_type: "TEST_EVENT",
    reason: "Testing audit.",
  });

  assertEqual(
    lot.audit.events.length,
    1,
    "One audit event must be stored.",
  );

  assertEqual(
    lot.audit.events[0]?.event_type,
    "TEST_EVENT",
    "The audit event type must be preserved.",
  );
});

test("produces stable hashes for nested object key order", () => {
  const first = {
    outer: {
      beta: 2,
      alpha: 1,
    },
    array: [
      { z: 3, a: 1 },
      4,
    ],
  };

  const second = {
    array: [
      { a: 1, z: 3 },
      4,
    ],
    outer: {
      alpha: 1,
      beta: 2,
    },
  };

  assertEqual(
    deterministicHash(first),
    deterministicHash(second),
    "Nested key order must not affect the hash.",
  );
});

test("preserves array order in canonical hashes", () => {
  assertNotEqual(
    deterministicHash([1, 2, 3]),
    deterministicHash([3, 2, 1]),
    "Array order must affect the hash.",
  );
});

test("excludes audit events from the lot artifact hash", () => {
  const lot = createLot();
  const before = calculateLotArtifactHash(lot);

  appendAuditEvent(lot, {
    event_type: "AUDIT_ONLY",
  });

  const after = calculateLotArtifactHash(lot);

  assertEqual(
    before,
    after,
    "Audit-only changes must not alter the artifact hash.",
  );
});

test("includes scope changes in the lot artifact hash", () => {
  const lot = createLot();
  const before = calculateLotArtifactHash(lot);

  lot.scope.allowed_paths.push(
    "src/new-module/**",
  );

  const after = calculateLotArtifactHash(lot);

  assertNotEqual(
    before,
    after,
    "Scope changes must alter the artifact hash.",
  );
});

test("rejects circular values during canonicalization", () => {
  const cyclic: Record<string, unknown> = {};
  cyclic.self = cyclic;

  assertThrows(
    () => canonicalize(cyclic),
    (error: unknown) => error instanceof TypeError,
    "Circular references must be rejected",
  );
});

test("approves a lot with a valid hash", () => {
  const lot = createApprovedLot();

  assertEqual(
    lot.status,
    "APPROVED",
    "The lot must transition to APPROVED.",
  );

  assertEqual(
    lot.approval.valid,
    true,
    "Approval must be valid.",
  );

  assertEqual(
    lot.approval.approved_by,
    "the owner",
    "The approver must be recorded.",
  );
});

test("rejects approval with an incorrect hash", () => {
  const lot = createLot("AWAITING_APPROVAL");

  assertThrows(
    () =>
      approveLot(lot, {
        approved_hash: "incorrect-hash",
        approved_by: "the owner",
        expires_at: "2099-01-01T00:00:00.000Z",
        allowed_capabilities: [],
      }),
    (error: unknown) =>
      error instanceof ApprovalError &&
      error.code === "APPROVAL_HASH_MISMATCH",
    "Incorrect hash must be rejected",
  );

  assertEqual(
    lot.status,
    "AWAITING_APPROVAL",
    "Rejected approval must not change state.",
  );
});

test("rejects expired approvals", () => {
  const lot = createLot("AWAITING_APPROVAL");
  const hash = calculateLotArtifactHash(lot);

  assertThrows(
    () =>
      approveLot(lot, {
        approved_hash: hash,
        approved_by: "the owner",
        expires_at: "2020-01-01T00:00:00.000Z",
        allowed_capabilities: [],
      }),
    (error: unknown) =>
      error instanceof ApprovalError &&
      error.code === "APPROVAL_EXPIRED",
    "Expired approval must be rejected",
  );
});

test("rejects unauthorized capabilities", () => {
  const lot = createLot("AWAITING_APPROVAL");
  const hash = calculateLotArtifactHash(lot);

  assertThrows(
    () =>
      approveLot(lot, {
        approved_hash: hash,
        approved_by: "the owner",
        expires_at: "2099-01-01T00:00:00.000Z",
        allowed_capabilities: [
          "deploy_publicly",
        ],
      }),
    (error: unknown) =>
      error instanceof ApprovalError &&
      error.code === "CAPABILITY_NOT_REQUESTED",
    "Unrequested capabilities must be rejected",
  );
});

test("invalidates approval after approvable mutation", () => {
  const lot = createApprovedLot();

  const invalidated = mutateLot(
    lot,
    (target: Lot) => {
      target.title = "Modified autonomy foundation";
    },
  );

  assertEqual(
    invalidated,
    true,
    "An approvable mutation must invalidate approval.",
  );

  assertEqual(
    lot.approval.valid,
    false,
    "Approval must become invalid.",
  );

  assertEqual(
    lot.status,
    "QUARANTINED",
    "The lot must return to quarantine.",
  );

  assertEqual(
    lot.audit.events.some(
      (event) =>
        event.event_type === "APPROVAL_INVALIDATED",
    ),
    true,
    "Invalidation must be audited.",
  );
});

test("does not invalidate approval after audit-only change", () => {
  const lot = createApprovedLot();

  appendAuditEvent(lot, {
    event_type: "INFORMATIONAL_EVENT",
  });

  const invalidated = refreshApprovalState(lot);

  assertEqual(
    invalidated,
    false,
    "Audit-only changes must not invalidate approval.",
  );

  assertEqual(
    lot.approval.valid,
    true,
    "Approval must remain valid.",
  );

  assertEqual(
    lot.status,
    "APPROVED",
    "The lot must remain approved.",
  );
});

test("creates identical command IDs for identical commands", () => {
  const first: IdempotencyCommand = {
    lot_id: "LOT-1",
    approved_hash: "hash-1",
    command_type: "RUN_TESTS",
    command_payload: {
      command: "npm test",
      options: {
        strict: true,
      },
    },
  };

  const second: IdempotencyCommand = {
    command_payload: {
      options: {
        strict: true,
      },
      command: "npm test",
    },
    command_type: "RUN_TESTS",
    approved_hash: "hash-1",
    lot_id: "LOT-1",
  };

  assertEqual(
    createCommandId(first),
    createCommandId(second),
    "Equivalent commands must share one command ID.",
  );
});

test("creates different IDs for different command payloads", () => {
  const first: IdempotencyCommand = {
    lot_id: "LOT-1",
    approved_hash: "hash-1",
    command_type: "RUN_TESTS",
    command_payload: {
      command: "npm test",
    },
  };

  const second: IdempotencyCommand = {
    ...first,
    command_payload: {
      command: "npm run lint",
    },
  };

  assertNotEqual(
    createCommandId(first),
    createCommandId(second),
    "Different payloads must produce different IDs.",
  );
});

test("executes identical operations only once", () => {
  const store = new MemoryIdempotencyStore();

  const command: IdempotencyCommand = {
    lot_id: "LOT-1",
    approved_hash: "hash-1",
    command_type: "RUN_TESTS",
    command_payload: {
      command: "npm test",
    },
  };

  let executions = 0;

  const first = executeOnce(
    store,
    command,
    () => {
      executions += 1;
      return "completed";
    },
  );

  const second = executeOnce(
    store,
    command,
    () => {
      executions += 1;
      return "completed-again";
    },
  );

  assertEqual(
    first.executed,
    true,
    "First execution must run.",
  );

  assertEqual(
    second.executed,
    false,
    "Second execution must be skipped.",
  );

  assertEqual(
    executions,
    1,
    "The operation must execute only once.",
  );
});

test("stores and retrieves idempotency records", () => {
  const store = new MemoryIdempotencyStore();

  const command: IdempotencyCommand = {
    lot_id: "LOT-1",
    approved_hash: "hash-1",
    command_type: "WRITE_FILE",
    command_payload: {
      path: "src/file.ts",
    },
  };

  const record = createIdempotencyRecord(
    command,
    "2026-07-23T16:30:00.000Z",
  );

  assertEqual(
    store.mark(record),
    true,
    "A new record must be stored.",
  );

  assertEqual(
    store.mark(record),
    false,
    "A duplicate record must be rejected.",
  );

  assertEqual(
    store.get(record.command_id)?.lot_id,
    "LOT-1",
    "The stored record must be retrievable.",
  );
});

test("serializes and reloads a lot without important loss", () => {
  const original = createLot("QUARANTINED");

  appendAuditEvent(original, {
    event_type: "SERIALIZATION_TEST",
  });

  const serialized = JSON.stringify(original);
  const restored = JSON.parse(serialized) as Lot;

  assertEqual(
    restored.lot_id,
    original.lot_id,
    "Lot ID must survive serialization.",
  );

  assertEqual(
    restored.status,
    "QUARANTINED",
    "State must survive serialization.",
  );

  assertEqual(
    restored.audit.events.length,
    1,
    "Audit events must survive serialization.",
  );
});

let passed = 0;
let failed = 0;

for (const currentTest of tests) {
  try {
    currentTest.run();
    passed += 1;
    console.log(`PASS ${currentTest.name}`);
  } catch (error: unknown) {
    failed += 1;
    console.error(`FAIL ${currentTest.name}`);

    if (error instanceof Error) {
      console.error(error.stack ?? error.message);
    } else {
      console.error(String(error));
    }
  }
}

console.log("");
console.log(`RESULT ${passed} passed, ${failed} failed`);

if (failed > 0) {
  throw new Error(
    `${failed} autonomy test(s) failed.`,
  );
}
