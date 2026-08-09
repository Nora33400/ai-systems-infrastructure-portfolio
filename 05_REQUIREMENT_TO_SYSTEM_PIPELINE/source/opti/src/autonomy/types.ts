export const LEGACY_TASK_STATUSES = [
  "pending", "ready", "running", "testing", "reviewing", "completed",
  "retryable_failure", "blocked", "quarantined", "cancelled",
] as const;

export const PLANNING_TASK_STATUSES = [
  "DISCOVERED", "NEEDS_CONTEXT", "READY_LOCAL_AI", "RUNNING_LOCAL_AI",
  "READY_CODEX_REVIEW", "RUNNING_CODEX_REVIEW", "NEEDS_CHATGPT_REVIEW",
  "NEEDS_OWNER_DECISION", "BLOCKED", "FAILED_RETRYABLE", "FAILED_FINAL",
  "VALIDATED", "COMPLETED", "ARCHIVED", "CANCELLED",
] as const;

export const TASK_STATUSES = [...LEGACY_TASK_STATUSES, ...PLANNING_TASK_STATUSES] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];
export type PlanningTaskStatus = (typeof PLANNING_TASK_STATUSES)[number];
export type RiskLevel = "SAFE" | "CONTROLLED" | "SENSITIVE" | "CRITICAL";
export type AutonomyLevel = "READ_ONLY" | "LOCAL_SAFE" | "PATCH_ISOLATED" | "CODEX_REVIEW_REQUIRED" | "CHATGPT_REVIEW_REQUIRED" | "OWNER_REQUIRED" | "FORBIDDEN";

export type AcceptanceCriterion =
  | { type: "file_exists"; path: string }
  | { type: "file_contains"; path: string; text: string }
  | { type: "file_not_contains"; path: string; text: string }
  | { type: "command_succeeds"; command: string; cwd?: string }
  | { type: "docs_validate" }
  | { type: "tests_pass"; command?: string };

export interface TaskHistoryEntry {
  timestamp: string;
  event: string;
  detail?: unknown;
}

export interface TestResult {
  criterion: AcceptanceCriterion | { type: "validation_command"; command: string };
  passed: boolean;
  detail: string;
  timestamp: string;
}

export interface TaskRecord {
  id: string;
  title: string;
  module: string;
  description: string;
  dependencies: string[];
  priority: number;
  status: TaskStatus;
  acceptance: AcceptanceCriterion[];
  acceptance_criteria?: unknown[];
  likely_files: string[];
  source_refs: string[];
  attempts: number;
  history: TaskHistoryEntry[];
  blockers: unknown[];
  test_results: TestResult[];
  last_agent: string | null;
  updated_at: string;
  autonomy_eligible: boolean;
  objective: string;
  project: string;
  risk_level: RiskLevel;
  parent_task: string | null;
  subtask_depth: number;
  assigned_agent: string;
  required_supervisor: string | null;
  required_validator: string | null;
  allowed_paths: string[];
  forbidden_paths: string[];
  allowed_commands: string[];
  context_requirements: string[];
  resource_budget: {
    cpu?: string;
    ram_mb?: number;
    gpu?: string;
    max_duration_minutes?: number;
  };
  retry_policy: {
    max_retries: number;
    retry_delay_seconds: number;
    retryable_errors: string[];
  };
  next_retry_at: string | null;
  trello: {
    card_id: string | null;
    sync_enabled: boolean;
  };
  isolation: {
    enabled: boolean;
    cleanup_on_success: boolean;
  };
  created_at: string;
  result?: {
    summary: string;
    modified_files: string[];
    validation: TestResult[];
    commit: string | null;
    isolation?: {
      execution_id: string;
      base_head: string;
      worktree_path: string;
      patch_path: string;
      patch_sha256: string;
      cleanup_result: string;
    };
  };
}

export interface IsolatedWorkspaceRequest {
  task_id: string;
  execution_id: string;
  allowed_paths: string[];
  forbidden_paths: string[];
  require_clean_baseline?: boolean;
}

export type IsolatedWorkspaceState = "ACTIVE" | "PATCH_EXTRACTED" | "RECOVERY_REQUIRED" | "CLEANED";

export interface IsolatedWorkspaceMetadata {
  schema_version: 1;
  workspace_id: string;
  task_id: string;
  execution_id: string;
  canonical_workspace: string;
  worktree_path: string;
  base_head: string;
  canonical_status_at_create: string;
  allowed_paths: string[];
  forbidden_paths: string[];
  state: IsolatedWorkspaceState;
  created_at: string;
  updated_at: string;
  patch_path: string | null;
  patch_sha256: string | null;
  touched_files: string[];
  cleanup_result: string | null;
  recovery_note: string | null;
}

export interface IsolatedWorkspaceStatus {
  metadata: IsolatedWorkspaceMetadata;
  exists: boolean;
  head: string | null;
  porcelain: string;
  touched_files: string[];
  clean: boolean;
}

export interface IsolatedPatchArtifact {
  workspace_id: string;
  task_id: string;
  execution_id: string;
  base_head: string;
  patch_path: string;
  patch_sha256: string;
  size_bytes: number;
  touched_files: string[];
}

export interface ExecutionRecord {
  execution_id: string;
  task_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "ABANDONED" | "BLOCKED";
  actor: string;
  started_at: string;
  updated_at: string;
  finished_at: string | null;
  attempt: number;
  checkpoint: Record<string, unknown> | null;
  result: unknown;
}

export interface AutonomyReceipt {
  receipt_id: string;
  task_id: string;
  execution_id: string;
  timestamp: string;
  actor: string;
  action: string;
  inputs_hash: string;
  outputs_hash: string;
  files_read: string[];
  files_modified: string[];
  commands: string[];
  tests: Array<Record<string, unknown>>;
  decision: string;
  result: unknown;
  parent_receipt: string | null;
}

export interface PolicyDocument {
  schema_version: 1;
  autonomy: Record<string, boolean>;
  limits: {
    max_retries: number;
    max_subtask_depth: number;
    max_children_per_task: number;
    max_parallel_tasks: number;
    max_task_duration_minutes: number;
  };
  local_ai: Record<string, boolean>;
  codex: Record<string, boolean>;
  require_owner: string[];
  on_missing_decision: Record<string, boolean>;
  external: {
    trello_enabled: boolean;
    trello_dry_run: boolean;
    codex_adapter: "manual_bundle" | "codex_cli" | "external_command" | "api_adapter";
    chatgpt_adapter: "manual_bundle" | "openai_api" | "external_command";
  };
  source_refs: string[];
}

export interface AutonomyConfig {
  version: number;
  configPath: string;
  workspace: string;
  mode: string;
  ollama: {
    url: string;
    coder_model: string;
    reviewer_model: string;
    readonly_model: string;
    fallback_models: string[];
    temperature: number;
    context_size: number;
    timeout_ms: number;
    response_retries: number;
    availability_retries: number;
    availability_delay_ms: number;
  };
  limits: {
    max_actions_per_task: number;
    max_task_retries: number;
    command_timeout_ms: number;
    prompt_output_chars: number;
    max_context_chars: number;
    max_consecutive_failures: number;
    max_tasks_per_session: number;
    full_validation_every_tasks: number;
  };
  security: {
    allowed_directories: string[];
    readable_root_files: string[];
    writable_root_files: string[];
    protected_files: string[];
    allowed_command_families: string[];
    forbidden_command_patterns: string[];
    deny_secret_name_patterns: string[];
  };
  git: {
    enabled: boolean;
    auto_commit: boolean;
    allow_push: boolean;
    require_clean_baseline: boolean;
  };
  validation: {
    light_commands: string[];
    full_commands: string[];
  };
  runtime: {
    database: string;
    lock_file: string;
    stop_file: string;
    backup_directory: string;
    event_log: string;
    command_log_directory: string;
    work_queue: string;
    workspace_write_backend: "direct" | "wsl";
    wsl_distro: string;
    dry_run: boolean;
    log_level: "debug" | "info" | "warn" | "error";
  };
}

export interface ReadOnlyContextDocument {
  id: string;
  path: string;
  content: string;
  content_sha256: string;
  truncated: boolean;
}

export interface ReadOnlyTaskPackage {
  schema_version: 1;
  task_id: string;
  title: string;
  objective: string;
  project: string;
  module: string;
  risk_level: RiskLevel;
  dependencies: string[];
  source_refs: string[];
  acceptance_criteria: unknown[];
  allowed_read_paths: string[];
  forbidden_paths: string[];
  validation_commands_reference_only: string[];
  context_requirements: string[];
  unresolved_context_requirements: string[];
  context_documents: ReadOnlyContextDocument[];
  safety_rules: {
    mode: "READ_ONLY";
    may_read_supplied_package: true;
    may_propose_next_actions: true;
    may_modify_files: false;
    may_emit_patch: false;
    may_execute_commands: false;
    may_access_secrets: false;
    may_change_task_state: false;
    may_expand_permissions: false;
  };
}

export interface ReadOnlyFinding {
  statement: string;
  evidence_refs: string[];
}

export interface ReadOnlyRisk {
  risk: string;
  mitigation: string;
  evidence_refs: string[];
}

export interface OllamaReadOnlyReport {
  schema_version: 1;
  task_id: string;
  summary: string;
  findings: ReadOnlyFinding[];
  risks: ReadOnlyRisk[];
  suggested_next_actions: string[];
  open_questions: string[];
  confidence: number;
  mutation_requested: false;
}

export interface ReadOnlyReportRecord {
  report_id: string;
  task_id: string;
  execution_id: string;
  created_at: string;
  model: string;
  input_hash: string;
  output_hash: string;
  raw_output_hash: string;
  task_package: ReadOnlyTaskPackage;
  report: OllamaReadOnlyReport;
}

export type AgentAction =
  | { action: "list_directory"; path: string; recursive?: boolean }
  | { action: "read_file"; path: string }
  | { action: "read_file_range"; path: string; start_line: number; end_line: number }
  | { action: "search_text"; query: string; path: string; max_results?: number }
  | { action: "inspect_git_diff" }
  | { action: "apply_patch"; patch: string }
  | { action: "create_file"; path: string; content: string; overwrite?: boolean }
  | { action: "delete_file"; path: string; reason: string }
  | { action: "run_command"; command: string; cwd?: string; timeout_ms?: number }
  | { action: "run_tests"; command: string; cwd?: string }
  | {
      action: "report_blocker";
      facts: string[];
      files?: string[];
      commands?: string[];
      errors: string[];
      attempts: string[];
      human_information_needed: string;
      independent_tasks_can_continue: boolean;
    }
  | { action: "finish_task"; summary: string };

export interface ActionObservation {
  ok: boolean;
  action: AgentAction["action"];
  summary: string;
  data?: unknown;
}

export interface CommandResult {
  id: string;
  command: string;
  cwd: string;
  stdout: string;
  stderr: string;
  prompt_stdout: string;
  prompt_stderr: string;
  exit_code: number | null;
  timed_out: boolean;
  duration_ms: number;
  log_path: string;
}

export interface ReviewDecision {
  approved: boolean;
  summary: string;
  issues: Array<{ severity: "low" | "medium" | "high"; description: string; file?: string }>;
  required_actions: string[];
}

export interface AutonomyEvent {
  id: string;
  timestamp: string;
  type: string;
  level: "debug" | "info" | "warn" | "error";
  task_id?: string;
  data: Record<string, unknown>;
}
