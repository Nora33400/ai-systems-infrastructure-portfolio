import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { AutonomyConfig, TaskRecord } from "../../src/autonomy/types.js";

export function testConfig(workspace: string): AutonomyConfig {
  const runtimeRoot = join(workspace, ".runtime");
  for (const directory of ["docs", "src", "tests", "config", "schemas", "scripts", "modules"]) {
    mkdirSync(join(workspace, directory), { recursive: true });
  }
  mkdirSync(runtimeRoot, { recursive: true });
  return {
    version: 1,
    configPath: join(workspace, "config", "autonomy.yaml"),
    workspace,
    mode: "GO_BATCH_OUI",
    ollama: {
      url: "http://127.0.0.1:11434",
      coder_model: "qwen2.5-coder:7b",
      reviewer_model: "qwen2.5-coder:7b",
      readonly_model: "qwen2.5-coder:7b",
      fallback_models: ["qwen2.5-coder:14b"],
      temperature: 0.1,
      context_size: 4096,
      timeout_ms: 120000,
      response_retries: 1,
      availability_retries: 1,
      availability_delay_ms: 10,
    },
    limits: {
      max_actions_per_task: 10,
      max_task_retries: 2,
      command_timeout_ms: 10000,
      prompt_output_chars: 1000,
      max_context_chars: 10000,
      max_consecutive_failures: 3,
      max_tasks_per_session: 10,
      full_validation_every_tasks: 5,
    },
    security: {
      allowed_directories: ["src", "tests", "config", "schemas", "scripts", "docs", "modules"],
      readable_root_files: ["README.md", "WORK_QUEUE.yaml"],
      writable_root_files: ["WORK_QUEUE.yaml"],
      protected_files: ["AGENTS.md", "SOURCE_MANIFEST.yaml"],
      allowed_command_families: ["node", "npm", "git", "powershell"],
      forbidden_command_patterns: ["(?i)git\\s+push", "(?i)remove-item.*-recurse"],
      deny_secret_name_patterns: ["(?i)^\\.env", "(?i)secret"],
    },
    git: { enabled: true, auto_commit: false, allow_push: false, require_clean_baseline: false },
    validation: { light_commands: [], full_commands: [] },
    runtime: {
      database: join(runtimeRoot, "autonomy.db"),
      lock_file: join(runtimeRoot, "autonomy.lock"),
      stop_file: join(runtimeRoot, "stop.requested"),
      backup_directory: join(runtimeRoot, "backups"),
      event_log: join(runtimeRoot, "events.jsonl"),
      command_log_directory: join(runtimeRoot, "commands"),
      work_queue: join(workspace, "WORK_QUEUE.yaml"),
      workspace_write_backend: "direct",
      wsl_distro: "Ubuntu",
      dry_run: false,
      log_level: "info",
    },
  };
}

export function task(id: string, overrides: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id,
    title: id,
    module: "autonomy-engine",
    description: "test task",
    dependencies: [],
    priority: 100,
    status: "ready",
    acceptance: [{ type: "file_exists", path: "docs/result.md" }],
    likely_files: ["docs/result.md"],
    source_refs: ["SRC-0007"],
    attempts: 0,
    history: [],
    blockers: [],
    test_results: [],
    last_agent: null,
    updated_at: new Date().toISOString(),
    autonomy_eligible: true,
    objective: "test objective",
    project: "opti-test",
    risk_level: "SAFE",
    parent_task: null,
    subtask_depth: 0,
    assigned_agent: "LOCAL_SYSTEM",
    required_supervisor: null,
    required_validator: "LOCAL_SYSTEM",
    allowed_paths: ["docs"],
    forbidden_paths: [".git", ".env"],
    allowed_commands: [],
    context_requirements: [],
    resource_budget: { max_duration_minutes: 1 },
    retry_policy: { max_retries: 2, retry_delay_seconds: 0, retryable_errors: ["test_failure"] },
    next_retry_at: null,
    trello: { card_id: null, sync_enabled: false },
    isolation: { enabled: false, cleanup_on_success: true },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}
