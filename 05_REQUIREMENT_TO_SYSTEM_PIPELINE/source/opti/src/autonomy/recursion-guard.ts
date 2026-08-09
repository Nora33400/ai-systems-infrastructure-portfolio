import type { PolicyDocument, TaskRecord } from "./types.js";

export interface RecursionDecision {
  allowed: boolean;
  reason: string;
}

export class RecursionGuard {
  constructor(private readonly policy: PolicyDocument) {}

  canCreateChild(parent: TaskRecord, proposed: TaskRecord, existing: TaskRecord[]): RecursionDecision {
    if (proposed.parent_task !== parent.id) return { allowed: false, reason: "parent_task_mismatch" };
    if (proposed.subtask_depth > this.policy.limits.max_subtask_depth) return { allowed: false, reason: "max_subtask_depth_exceeded" };
    if (proposed.subtask_depth !== parent.subtask_depth + 1) return { allowed: false, reason: "subtask_depth_mismatch" };
    const children = existing.filter((task) => task.parent_task === parent.id);
    if (children.length >= this.policy.limits.max_children_per_task) return { allowed: false, reason: "max_children_per_task_reached" };
    if (existing.some((task) => task.id === proposed.id)) return { allowed: false, reason: "duplicate_task_id" };

    const byId = new Map(existing.map((task) => [task.id, task]));
    let cursor: TaskRecord | undefined = parent;
    const visited = new Set<string>();
    while (cursor) {
      if (cursor.id === proposed.id) return { allowed: false, reason: "recursive_parent_cycle" };
      if (visited.has(cursor.id)) return { allowed: false, reason: "existing_parent_cycle" };
      visited.add(cursor.id);
      cursor = cursor.parent_task ? byId.get(cursor.parent_task) : undefined;
    }
    return { allowed: true, reason: "bounded_child_allowed" };
  }

  canReopen(task: TaskRecord, newEvidenceRefs: string[]): RecursionDecision {
    if (!this.policy.autonomy.require_new_evidence_to_reopen) return { allowed: true, reason: "new_evidence_not_required" };
    const known = new Set(task.source_refs);
    return newEvidenceRefs.some((reference) => !known.has(reference))
      ? { allowed: true, reason: "new_evidence_supplied" }
      : { allowed: false, reason: "new_evidence_required_to_reopen" };
  }
}
