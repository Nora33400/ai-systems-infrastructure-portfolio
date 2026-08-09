import { randomUUID } from "node:crypto";
import { taskResourceKeys } from "./resource-locks.js";
import type { PolicyDecision, PolicyEngine } from "./policy-engine.js";
import type { Scheduler } from "./scheduler.js";
import type { StateStore } from "./state-store.js";
import type { TaskImporter } from "./task-importer.js";

export interface Phase2Plan {
  plan_id: string;
  created_at: string;
  dry_run: true;
  max_parallel_tasks: number;
  dependency_cycles: string[][];
  missing_dependencies: Record<string, string[]>;
  selected: Array<{ task_id: string; resources: string[]; policy: PolicyDecision }>;
  considered: Array<{ id: string; ready: boolean; reason: string }>;
  active_locks: ReturnType<StateStore["listResourceLocks"]>;
}

export class Phase2Planner {
  constructor(
    private readonly store: StateStore,
    private readonly importer: TaskImporter,
    private readonly scheduler: Scheduler,
    private readonly policy: PolicyEngine,
  ) {}

  plan(now = new Date()): Phase2Plan {
    this.importer.import();
    const maxParallel = this.policy.document.limits.max_parallel_tasks;
    const decision = this.scheduler.selectReady({ limit: maxParallel, now, transition: false });
    const plan: Phase2Plan = {
      plan_id: `PLAN-${randomUUID()}`,
      created_at: now.toISOString(),
      dry_run: true,
      max_parallel_tasks: maxParallel,
      dependency_cycles: decision.dependency_analysis.cycles,
      missing_dependencies: Object.fromEntries(decision.dependency_analysis.missing_dependencies),
      selected: decision.tasks.map((task) => ({ task_id: task.id, resources: taskResourceKeys(task), policy: this.policy.decide(task) })),
      considered: decision.considered,
      active_locks: this.store.listResourceLocks(),
    };
    this.store.setMeta("last_phase_2_plan", plan);
    return plan;
  }
}
