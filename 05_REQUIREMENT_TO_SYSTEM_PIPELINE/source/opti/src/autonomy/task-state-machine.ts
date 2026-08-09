import type { TaskStatus } from "./types.js";

const transitions: Record<TaskStatus, readonly TaskStatus[]> = {
  pending: ["ready", "blocked", "cancelled"],
  ready: ["running", "completed", "blocked", "cancelled"],
  running: ["testing", "reviewing", "completed", "retryable_failure", "blocked", "quarantined", "cancelled"],
  testing: ["running", "reviewing", "completed", "retryable_failure", "blocked", "quarantined"],
  reviewing: ["running", "completed", "retryable_failure", "blocked", "quarantined"],
  completed: [],
  retryable_failure: ["ready", "running", "blocked", "quarantined", "cancelled"],
  blocked: ["ready", "retryable_failure", "quarantined", "cancelled"],
  quarantined: ["ready", "cancelled"],
  cancelled: [],
  DISCOVERED: ["NEEDS_CONTEXT", "READY_LOCAL_AI", "NEEDS_OWNER_DECISION", "BLOCKED", "CANCELLED"],
  NEEDS_CONTEXT: ["READY_LOCAL_AI", "NEEDS_OWNER_DECISION", "BLOCKED", "CANCELLED"],
  READY_LOCAL_AI: ["RUNNING_LOCAL_AI", "BLOCKED", "CANCELLED"],
  RUNNING_LOCAL_AI: ["READY_CODEX_REVIEW", "NEEDS_CHATGPT_REVIEW", "NEEDS_OWNER_DECISION", "FAILED_RETRYABLE", "FAILED_FINAL", "VALIDATED", "BLOCKED"],
  READY_CODEX_REVIEW: ["RUNNING_CODEX_REVIEW", "BLOCKED", "CANCELLED"],
  RUNNING_CODEX_REVIEW: ["READY_LOCAL_AI", "NEEDS_CHATGPT_REVIEW", "NEEDS_OWNER_DECISION", "FAILED_RETRYABLE", "FAILED_FINAL", "VALIDATED", "BLOCKED"],
  NEEDS_CHATGPT_REVIEW: ["READY_LOCAL_AI", "READY_CODEX_REVIEW", "NEEDS_OWNER_DECISION", "VALIDATED", "BLOCKED", "CANCELLED"],
  NEEDS_OWNER_DECISION: ["READY_LOCAL_AI", "READY_CODEX_REVIEW", "NEEDS_CHATGPT_REVIEW", "VALIDATED", "BLOCKED", "CANCELLED"],
  BLOCKED: ["NEEDS_CONTEXT", "READY_LOCAL_AI", "READY_CODEX_REVIEW", "NEEDS_CHATGPT_REVIEW", "NEEDS_OWNER_DECISION", "FAILED_FINAL", "CANCELLED"],
  FAILED_RETRYABLE: ["READY_LOCAL_AI", "BLOCKED", "FAILED_FINAL", "CANCELLED"],
  FAILED_FINAL: ["ARCHIVED"],
  VALIDATED: ["COMPLETED", "READY_LOCAL_AI", "NEEDS_OWNER_DECISION"],
  COMPLETED: ["ARCHIVED"],
  ARCHIVED: [],
  CANCELLED: ["ARCHIVED"],
};

export class InvalidTaskTransition extends Error {
  constructor(from: TaskStatus, to: TaskStatus) {
    super(`Invalid task transition: ${from} -> ${to}`);
    this.name = "InvalidTaskTransition";
  }
}

export class TaskStateMachine {
  canTransition(from: TaskStatus, to: TaskStatus): boolean {
    return from === to || transitions[from].includes(to);
  }

  assertTransition(from: TaskStatus, to: TaskStatus): void {
    if (!this.canTransition(from, to)) throw new InvalidTaskTransition(from, to);
  }

  allowedFrom(status: TaskStatus): readonly TaskStatus[] {
    return transitions[status];
  }
}
