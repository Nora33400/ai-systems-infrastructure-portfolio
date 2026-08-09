import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { Ajv2020 } from "ajv/dist/2020.js";
import { analyzeDependencies } from "../../src/autonomy/dependency-planner.js";
import { PolicyEngine } from "../../src/autonomy/policy-engine.js";
import { RecursionGuard } from "../../src/autonomy/recursion-guard.js";
import { NvidiaSmiObserver, ResourcePlanner, type HardwareSnapshot } from "../../src/autonomy/resource-planner.js";
import { Scheduler } from "../../src/autonomy/scheduler.js";
import { StateStore } from "../../src/autonomy/state-store.js";
import { task, testConfig } from "./test-helpers.js";

const repository = resolve(process.env.AIONE_WORKSPACE ?? process.cwd());

function policy(): PolicyEngine {
  return PolicyEngine.load(join(repository, "config", "autonomy-policy.yaml"), join(repository, "schemas", "autonomy-policy.schema.json"));
}

function snapshot(overrides: Partial<HardwareSnapshot> = {}): HardwareSnapshot {
  return {
    observed_at: "2026-07-18T00:00:00.000Z",
    observer: "nvidia-smi",
    user_activity: "IDLE",
    fullscreen: false,
    game_detected: false,
    gpus: [
      { index: 0, name: "NVIDIA GeForce RTX 3060", memory_total_mb: 12288, memory_used_mb: 10, utilization_percent: 0, temperature_c: 50, driver_version: "610.74" },
      { index: 1, name: "NVIDIA GeForce RTX 4060", memory_total_mb: 8188, memory_used_mb: 1482, utilization_percent: 7, temperature_c: 47, driver_version: "610.74" },
    ],
    ...overrides,
  };
}

test("dependency analysis reports missing definitions and deterministic cycles", () => {
  const tasks = [
    task("A", { dependencies: ["B"] }),
    task("B", { dependencies: ["C"] }),
    task("C", { dependencies: ["A"] }),
    task("D", { dependencies: ["MISSING"] }),
  ];
  const analysis = analyzeDependencies(tasks);
  assert.deepEqual(analysis.cycles, [["A", "B", "C", "A"]]);
  assert.deepEqual([...analysis.cycle_members].sort(), ["A", "B", "C"]);
  assert.deepEqual(analysis.missing_dependencies.get("D"), ["MISSING"]);
});

test("scheduler continues independent branches while cycles, missing dependencies and path conflicts stay blocked", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-phase2-branches-"));
  const store = new StateStore(testConfig(workspace).runtime.database);
  store.saveTask(task("cycle-a", { dependencies: ["cycle-b"], priority: 100 }));
  store.saveTask(task("cycle-b", { dependencies: ["cycle-a"], priority: 99 }));
  store.saveTask(task("missing", { dependencies: ["absent"], priority: 98 }));
  store.saveTask(task("branch-a", { allowed_paths: ["docs/alpha"], priority: 90 }));
  store.saveTask(task("conflict-a", { allowed_paths: ["docs/alpha/file.md"], priority: 80 }));
  store.saveTask(task("branch-b", { allowed_paths: ["tests/beta"], priority: 70 }));

  const decision = new Scheduler(store).selectReady({ limit: 2 });
  assert.deepEqual(decision.tasks.map((entry) => entry.id), ["branch-a", "branch-b"]);
  assert.equal(decision.considered.find((entry) => entry.id === "cycle-a")?.reason, "dependency_cycle");
  assert.equal(decision.considered.find((entry) => entry.id === "missing")?.reason, "dependencies_missing:absent");
  assert.equal(decision.considered.find((entry) => entry.id === "conflict-a")?.reason, "resource_conflict_with_selected_task");
  store.close();
});

test("resource locks are atomic across store instances and detect parent-child path conflicts", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-phase2-locks-"));
  const database = testConfig(workspace).runtime.database;
  const first = new StateStore(database);
  const second = new StateStore(database);
  assert.equal(first.acquireResourceLocks(["path:src/shared", "gpu:0"], "EXE-A"), true);
  assert.equal(second.acquireResourceLocks(["path:src/shared/file.ts", "gpu:1"], "EXE-B"), false);
  assert.deepEqual(second.listResourceLocks().map((lock) => lock.execution_id), ["EXE-A", "EXE-A"]);
  first.releaseResourceLocks("EXE-A");
  assert.equal(second.acquireResourceLocks(["path:src/shared/file.ts", "gpu:1"], "EXE-B"), true);
  second.releaseResourceLocks("EXE-B");
  first.close();
  second.close();
});

test("scheduler respects retry delay without blocking another ready task", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opti-phase2-retry-"));
  const store = new StateStore(testConfig(workspace).runtime.database);
  store.saveTask(task("retry-later", { status: "FAILED_RETRYABLE", priority: 100, next_retry_at: "2026-07-18T12:10:00.000Z" }));
  store.saveTask(task("ready-now", { status: "READY_LOCAL_AI", priority: 80 }));
  const scheduler = new Scheduler(store);
  const before = scheduler.selectReady({ limit: 2, now: new Date("2026-07-18T12:00:00.000Z") });
  assert.deepEqual(before.tasks.map((entry) => entry.id), ["ready-now"]);
  assert.match(before.considered.find((entry) => entry.id === "retry-later")?.reason ?? "", /^retry_not_due:/);
  const after = scheduler.selectReady({ limit: 1, now: new Date("2026-07-18T12:11:00.000Z") });
  assert.equal(after.tasks[0]?.id, "retry-later");
  store.close();
});

test("recursion guard enforces depth, child count, ancestry and new evidence", () => {
  const guard = new RecursionGuard(policy().document);
  const parent = task("parent", { subtask_depth: 3 });
  const valid = task("valid-child", { parent_task: "parent", subtask_depth: 4 });
  assert.deepEqual(guard.canCreateChild(parent, valid, [parent]), { allowed: true, reason: "bounded_child_allowed" });
  assert.equal(guard.canCreateChild(parent, task("too-deep", { parent_task: "parent", subtask_depth: 5 }), [parent]).reason, "max_subtask_depth_exceeded");

  const children = Array.from({ length: 7 }, (_, index) => task(`child-${index}`, { parent_task: "parent", subtask_depth: 4 }));
  assert.equal(guard.canCreateChild(parent, valid, [parent, ...children]).reason, "max_children_per_task_reached");
  assert.equal(guard.canReopen(task("closed", { source_refs: ["SRC-0012"] }), ["SRC-0012"]).allowed, false);
  assert.equal(guard.canReopen(task("closed", { source_refs: ["SRC-0012"] }), ["SRC-0013"]).allowed, true);
});

test("resource planner is dry-run, prioritizes the owner and selects bounded dual-GPU modes", () => {
  const planner = ResourcePlanner.load(join(repository, "config", "resource-policy.yaml"), join(repository, "schemas", "resource-policy.schema.json"));
  const parallel = planner.recommend(snapshot(), { requested_workers: 2, heavy_reasoning: false, gpu_required: true });
  assert.equal(parallel.mode, "AUTONOMOUS_CODING");
  assert.equal(parallel.dry_run, true);
  assert.deepEqual(parallel.assignments.map((entry) => entry.role), ["developer", "reviewer"]);

  const active = planner.recommend(snapshot({ user_activity: "ACTIVE" }), { requested_workers: 2, heavy_reasoning: false, gpu_required: true });
  assert.equal(active.mode, "PERSONAL_INTERACTIVE");
  const unknown = planner.recommend(snapshot({ user_activity: "UNKNOWN" }), { requested_workers: 2, heavy_reasoning: false, gpu_required: true });
  assert.equal(unknown.mode, "PERSONAL_INTERACTIVE");
  assert.equal(unknown.allowed_parallel_workers, 0);
  const gaming = planner.recommend(snapshot({ game_detected: true }), { requested_workers: 2, heavy_reasoning: false, gpu_required: true });
  assert.equal(gaming.mode, "GAMING");
  const heavy = planner.recommend(snapshot(), { requested_workers: 1, heavy_reasoning: true, gpu_required: true });
  assert.equal(heavy.mode, "HEAVY_REASONING");
  const hot = planner.recommend(snapshot({ gpus: snapshot().gpus.map((gpu, index) => index === 0 ? { ...gpu, temperature_c: 79 } : gpu) }), { requested_workers: 1, heavy_reasoning: false, gpu_required: true });
  assert.equal(hot.mode, "LOW_POWER");
});

test("nvidia-smi observer parses a read-only inventory through an injected runner", async () => {
  const observer = new NvidiaSmiObserver(async (args) => {
    assert.equal(args[0]?.startsWith("--query-gpu="), true);
    return "0, NVIDIA GeForce RTX 3060, 12288, 10, 0, 50, 610.74\n1, NVIDIA GeForce RTX 4060, 8188, 1482, 7, 47, 610.74\n";
  });
  const result = await observer.observe({ user_activity: "UNKNOWN", fullscreen: false, game_detected: false });
  assert.equal(result.gpus.length, 2);
  assert.equal(result.gpus[1]?.memory_total_mb, 8188);
  assert.equal(result.user_activity, "UNKNOWN");
});

test("the canonical WQ-0049 review receipt keeps its schema and runtime hash", () => {
  const receipt = JSON.parse(readFileSync(join(repository, "receipts", "autonomy-planning", "WQ-0049.json"), "utf8")) as Record<string, unknown>;
  const schema = JSON.parse(readFileSync(join(repository, "schemas", "autonomy-receipt.schema.json"), "utf8")) as Record<string, unknown>;
  const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema);
  assert.equal(validate(receipt), true);
  assert.equal(createHash("sha256").update(JSON.stringify(receipt)).digest("hex"), "b31f062735a8f20b17f8162f767fa60a50f8f6bd5b0f887598fb60e85b35322c");
});
