import test from "node:test";
import assert from "node:assert/strict";
import { StateStore } from "../../src/autonomy/state-store.js";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";

test("Directions Registry - Create and Retrieve", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Test create and retrieve
    const direction = store.createDirection({
      description: "Test direction",
      priority: 10,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });

    assert.ok(direction.id);
    assert.strictEqual(direction.description, "Test direction");
    assert.strictEqual(direction.priority, 10);
    assert.strictEqual(direction.status, 'ACTIVE');
    assert.strictEqual(direction.origin, "test-origin");
    assert.strictEqual(direction.constraints.test, "constraint");
    assert.strictEqual(direction.satisfaction_criteria.success, true);
    assert.deepStrictEqual(direction.task_refs, ["task-123"]);
    assert.deepStrictEqual(direction.capability_refs, ["capability-456"]);

    const retrieved = store.getDirection(direction.id);
    assert.ok(retrieved);
    assert.strictEqual(retrieved.id, direction.id);
    assert.strictEqual(retrieved.description, "Test direction");
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - Persistence after close and reopen", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create a direction
    const direction = store.createDirection({
      description: "Test persistence",
      priority: 5,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });

    // Close and reopen
    store.close();
    store = new StateStore(testDbPath);
    
    const retrieved = store.getDirection(direction.id);
    assert.ok(retrieved);
    assert.strictEqual(retrieved.description, "Test persistence");
    assert.strictEqual(retrieved.priority, 5);
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - List active directions with ordering", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create multiple directions
    const direction1 = store.createDirection({
      description: "Test direction 1",
      priority: 10,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint1" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });
    
    const direction2 = store.createDirection({
      description: "Test direction 2",
      priority: 5,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint2" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-456"],
      capability_refs: ["capability-789"],
    });
    
    const direction3 = store.createDirection({
      description: "Test direction 3",
      priority: 15,
      status: 'PAUSED',
      origin: "test-origin",
      constraints: { test: "constraint3" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });

    const activeDirections = store.listActiveDirections();
    assert.strictEqual(activeDirections.length, 2);
    
    // Check ordering by priority (descending)
    const first = activeDirections[0];
    const second = activeDirections[1];
    assert.ok(first);
    assert.ok(second);
    
    assert.strictEqual(first.priority, 10); // Higher priority first
    assert.strictEqual(second.priority, 5);
    
    // Test deterministic order when priorities are equal
    const direction4 = store.createDirection({
      description: "Test direction 4",
      priority: 10,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint4" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-456"],
      capability_refs: ["capability-789"],
    });
    
    const activeDirectionsAfter = store.listActiveDirections();
    // With equal priorities, should be ordered by created_at ASC, then id ASC
    const equalPriorityDirections = activeDirectionsAfter.filter(
      (candidate) => candidate.priority === 10,
    );

    assert.strictEqual(equalPriorityDirections.length, 2);

    const firstEqualPriority = equalPriorityDirections[0];
    const secondEqualPriority = equalPriorityDirections[1];

    assert.ok(firstEqualPriority);
    assert.ok(secondEqualPriority);

    assert.strictEqual(firstEqualPriority.priority, 10);
    assert.strictEqual(secondEqualPriority.priority, 10);

    const orderedByCreatedAt =
      firstEqualPriority.created_at < secondEqualPriority.created_at;

    const orderedByIdWhenDatesMatch =
      firstEqualPriority.created_at === secondEqualPriority.created_at &&
      firstEqualPriority.id.localeCompare(secondEqualPriority.id) <= 0;

    assert.ok(orderedByCreatedAt || orderedByIdWhenDatesMatch);
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - Update priority", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create a direction
    const direction = store.createDirection({
      description: "Test update priority",
      priority: 10,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });

    const updated = store.updateDirectionPriority(direction.id, 15);
    assert.ok(updated);
    assert.strictEqual(updated.priority, 15);

    const retrievedUpdated = store.getDirection(direction.id);
    assert.strictEqual(retrievedUpdated?.priority, 15);
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - PAUSED directions not in listActive", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create a PAUSED direction
    store.createDirection({
      description: "Test paused",
      priority: 10,
      status: 'PAUSED',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });
    
    // Create an ACTIVE direction
    store.createDirection({
      description: "Test active",
      priority: 5,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-456"],
      capability_refs: ["capability-789"],
    });

    const activeDirections = store.listActiveDirections();
    assert.strictEqual(activeDirections.length, 1);
    
    const first = activeDirections[0];
    assert.ok(first);
    assert.strictEqual(first.priority, 5);
    assert.strictEqual(first.description, "Test active");
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - CANCELLED directions not usable", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create a direction
    const direction = store.createDirection({
      description: "Test cancelled",
      priority: 10,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: { test: "constraint" },
      satisfaction_criteria: { success: true },
      task_refs: ["task-123"],
      capability_refs: ["capability-456"],
    });

    // Cancel the direction
    const cancelled = store.cancelDirection(direction.id);
    assert.ok(cancelled);
    assert.strictEqual(cancelled.status, 'CANCELLED');
    
    // Check if the direction is usable (should return false)
    assert.strictEqual(store.isDirectionUsable(direction.id), false);
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - Expired directions", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create an expired direction
    const expiredDir = store.createDirection({
      description: "Expired direction",
      priority: 1,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: {},
      satisfaction_criteria: {},
      expires_at: new Date(Date.now() - 1000).toISOString(),
      task_refs: ["task-expired"],
      capability_refs: [],
    });
    
    // Create a regular active direction
    store.createDirection({
      description: "Regular direction",
      priority: 2,
      status: 'ACTIVE',
      origin: "test-origin",
      constraints: {},
      satisfaction_criteria: {},
      task_refs: ["task-regular"],
      capability_refs: [],
    });
    
    // Actually expire the direction through checkAndExpire
    store.checkAndExpireDirections();
    
    // Verify that the EXPIRED status is persisted
    const retrieved = store.getDirection(expiredDir.id);
    assert.strictEqual(retrieved?.status, 'EXPIRED');
    
    const activeDirections = store.listActiveDirections();
    // Expired direction should not appear in listActiveDirections
    assert.ok(!activeDirections.some(d => d.id === expiredDir.id));
    
    // Check if expired direction is still usable (should be false)
    const isUsable = store.isDirectionUsable(expiredDir.id);
    assert.strictEqual(isUsable, false); // Expired directions should not be usable
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});

test("Directions Registry - SATISFIED directions", async () => {
  const tempDir = mkdtempSync(tmpdir() + "/autonomy-test-");
  const testDbPath = `${tempDir}/test.db`;
  let store: StateStore | undefined;

  try {
    store = new StateStore(testDbPath);
    
    // Create a SATISFIED direction
    const satisfiedDir = store.createDirection({
      description: "Satisfied direction",
      priority: 1,
      status: 'SATISFIED',
      origin: "test-origin",
      constraints: {},
      satisfaction_criteria: {},
      task_refs: ["task-satisfied"],
      capability_refs: [],
    });
    
    // Verify that the SATISFIED status is persisted
    const retrieved = store.getDirection(satisfiedDir.id);
    assert.strictEqual(retrieved?.status, 'SATISFIED');
    
    // Check that SATISFIED direction doesn't appear in listActiveDirections
    const activeDirections = store.listActiveDirections();
    assert.ok(!activeDirections.some(d => d.id === satisfiedDir.id));
    
    // SATISFIED is non-active but remains usable under the current WQ-0054 contract.
    // Changing this behavior requires a separate contract decision.
    const isUsable = store.isDirectionUsable(satisfiedDir.id);
    assert.strictEqual(isUsable, true); // SATISFIED directions are currently usable
  } finally {
    if (store) {
      store.close();
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
});