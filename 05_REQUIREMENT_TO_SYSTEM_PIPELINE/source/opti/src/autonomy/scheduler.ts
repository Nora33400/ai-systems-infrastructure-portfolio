import { analyzeDependencies, type DependencyAnalysis } from "./dependency-planner.js";
import { resourceKeysConflict, taskResourceKeys } from "./resource-locks.js";
import type { TaskRecord } from "./types.js";
import { StateStore } from "./state-store.js";

export interface ConsideredTask {
  id: string;
  ready: boolean;
  reason: string;
}

export interface ScheduleDecision {
  task: TaskRecord | null;
  considered: ConsideredTask[];
  dependency_analysis: DependencyAnalysis;
}

export interface MultiScheduleDecision {
  tasks: TaskRecord[];
  considered: ConsideredTask[];
  dependency_analysis: DependencyAnalysis;
}

export interface ScheduleOptions {
  limit?: number;
  now?: Date;
  transition?: boolean;
}

const CANDIDATE_STATUSES = ["pending", "ready", "retryable_failure", "DISCOVERED", "READY_LOCAL_AI", "FAILED_RETRYABLE"];
const COMPLETED_STATUSES = ["completed", "COMPLETED", "ARCHIVED"];

export class Scheduler {
  constructor(private readonly store: StateStore) {}

  selectNext(): ScheduleDecision {
    const decision = this.selectReady({ limit: 1, transition: true });
    return { task: decision.tasks[0] ?? null, considered: decision.considered, dependency_analysis: decision.dependency_analysis };
  }

  selectReady(options: ScheduleOptions = {}): MultiScheduleDecision {
    const limit = Math.max(1, options.limit ?? 1);
    const transition = options.transition ?? false;
    const now = options.now ?? new Date();
    const tasks = this.store.listTasks();
    const byId = new Map(tasks.map((task) => [task.id, task]));
    const analysis = analyzeDependencies(tasks);
    const considered: ConsideredTask[] = [];
    const selected: TaskRecord[] = [];
    const selectedResourceKeys: string[] = [];

    const candidates = tasks
      .filter((task) => task.autonomy_eligible)
      .filter((task) => CANDIDATE_STATUSES.includes(task.status))
      .sort((left, right) => right.priority - left.priority || left.attempts - right.attempts || left.id.localeCompare(right.id));

    for (const task of candidates) {
      if (selected.length >= limit) break;
      const missingDefinitions = analysis.missing_dependencies.get(task.id);
      if (missingDefinitions?.length) {
        considered.push({ id: task.id, ready: false, reason: `dependencies_missing:${missingDefinitions.join(",")}` });
        continue;
      }
      if (analysis.cycle_members.has(task.id)) {
        considered.push({ id: task.id, ready: false, reason: "dependency_cycle" });
        continue;
      }
      const incomplete = task.dependencies.filter((id) => !COMPLETED_STATUSES.includes(byId.get(id)?.status ?? ""));
      if (incomplete.length > 0) {
        considered.push({ id: task.id, ready: false, reason: `dependencies_not_completed:${incomplete.join(",")}` });
        continue;
      }
      if (task.acceptance.length === 0) {
        considered.push({ id: task.id, ready: false, reason: "no_machine_verifiable_acceptance" });
        continue;
      }
      if (task.next_retry_at && new Date(task.next_retry_at).getTime() > now.getTime()) {
        considered.push({ id: task.id, ready: false, reason: `retry_not_due:${task.next_retry_at}` });
        continue;
      }

      const resourceKeys = taskResourceKeys(task);
      const persistedConflicts = this.store.conflictingResourceLocks(resourceKeys);
      if (persistedConflicts.length > 0) {
        considered.push({ id: task.id, ready: false, reason: `resource_locked:${persistedConflicts.map((lock) => lock.resource_key).join(",")}` });
        continue;
      }
      if (resourceKeys.some((key) => selectedResourceKeys.some((selectedKey) => resourceKeysConflict(key, selectedKey)))) {
        considered.push({ id: task.id, ready: false, reason: "resource_conflict_with_selected_task" });
        continue;
      }

      let selectedTask = task;
      if (transition && task.status !== "ready" && task.status !== "READY_LOCAL_AI") {
        const target = ["DISCOVERED", "FAILED_RETRYABLE"].includes(task.status) ? "READY_LOCAL_AI" : "ready";
        selectedTask = this.store.transition(task.id, target, "dependencies_satisfied");
        selectedTask.next_retry_at = null;
        this.store.saveTask(selectedTask);
      }
      considered.push({ id: task.id, ready: true, reason: "ready" });
      selected.push(selectedTask);
      selectedResourceKeys.push(...resourceKeys);
    }
    return { tasks: selected, considered, dependency_analysis: analysis };
  }
}
