import { readFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { parse } from "yaml";
import type { AutonomyConfig } from "./types.js";

function requiredObject(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Configuration section "${name}" must be an object.`);
  }
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, name: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Configuration value "${name}" must be a non-empty string.`);
  }
  return value;
}

function requiredNumber(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Configuration value "${name}" must be a finite number.`);
  }
  return value;
}

function stringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || value.some((entry) => typeof entry !== "string")) {
    throw new Error(`Configuration value "${name}" must be an array of strings.`);
  }
  return [...value] as string[];
}

function resolveFromWorkspace(workspace: string, value: string): string {
  return isAbsolute(value) ? resolve(value) : resolve(workspace, value);
}

function expandEnvironment(value: string, name: string): string {
  return value.replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_match, variable: string) => {
    const expanded = process.env[variable];
    if (!expanded) throw new Error(`Environment variable "${variable}" required by "${name}" is unavailable.`);
    return expanded;
  });
}

function runtimePath(workspace: string, value: unknown, name: string): string {
  return resolveFromWorkspace(workspace, expandEnvironment(requiredString(value, name), name));
}

export function loadConfig(configPathInput = "config/autonomy.yaml"): AutonomyConfig {
  const configPath = resolve(configPathInput);
  const raw = parse(readFileSync(configPath, "utf8")) as Record<string, unknown>;
  const configDir = dirname(configPath);
  const workspaceValue = requiredString(raw.workspace, "workspace");
  const workspace = resolve(configDir, workspaceValue);

  const ollama = requiredObject(raw.ollama, "ollama");
  const limits = requiredObject(raw.limits, "limits");
  const security = requiredObject(raw.security, "security");
  const git = requiredObject(raw.git, "git");
  const validation = requiredObject(raw.validation, "validation");
  const runtime = requiredObject(raw.runtime, "runtime");

  const config: AutonomyConfig = {
    version: requiredNumber(raw.version, "version"),
    configPath,
    workspace,
    mode: requiredString(raw.mode, "mode"),
    ollama: {
      url: requiredString(ollama.url, "ollama.url").replace(/\/$/, ""),
      coder_model: requiredString(ollama.coder_model, "ollama.coder_model"),
      reviewer_model: requiredString(ollama.reviewer_model, "ollama.reviewer_model"),
      readonly_model: requiredString(ollama.readonly_model, "ollama.readonly_model"),
      fallback_models: stringArray(ollama.fallback_models, "ollama.fallback_models"),
      temperature: requiredNumber(ollama.temperature, "ollama.temperature"),
      context_size: requiredNumber(ollama.context_size, "ollama.context_size"),
      timeout_ms: requiredNumber(ollama.timeout_ms, "ollama.timeout_ms"),
      response_retries: requiredNumber(ollama.response_retries, "ollama.response_retries"),
      availability_retries: requiredNumber(ollama.availability_retries, "ollama.availability_retries"),
      availability_delay_ms: requiredNumber(ollama.availability_delay_ms, "ollama.availability_delay_ms"),
    },
    limits: {
      max_actions_per_task: requiredNumber(limits.max_actions_per_task, "limits.max_actions_per_task"),
      max_task_retries: requiredNumber(limits.max_task_retries, "limits.max_task_retries"),
      command_timeout_ms: requiredNumber(limits.command_timeout_ms, "limits.command_timeout_ms"),
      prompt_output_chars: requiredNumber(limits.prompt_output_chars, "limits.prompt_output_chars"),
      max_context_chars: requiredNumber(limits.max_context_chars, "limits.max_context_chars"),
      max_consecutive_failures: requiredNumber(limits.max_consecutive_failures, "limits.max_consecutive_failures"),
      max_tasks_per_session: requiredNumber(limits.max_tasks_per_session, "limits.max_tasks_per_session"),
      full_validation_every_tasks: requiredNumber(limits.full_validation_every_tasks, "limits.full_validation_every_tasks"),
    },
    security: {
      allowed_directories: stringArray(security.allowed_directories, "security.allowed_directories"),
      readable_root_files: stringArray(security.readable_root_files, "security.readable_root_files"),
      writable_root_files: stringArray(security.writable_root_files, "security.writable_root_files"),
      protected_files: stringArray(security.protected_files, "security.protected_files"),
      allowed_command_families: stringArray(security.allowed_command_families, "security.allowed_command_families"),
      forbidden_command_patterns: stringArray(security.forbidden_command_patterns, "security.forbidden_command_patterns"),
      deny_secret_name_patterns: stringArray(security.deny_secret_name_patterns, "security.deny_secret_name_patterns"),
    },
    git: {
      enabled: Boolean(git.enabled),
      auto_commit: Boolean(git.auto_commit),
      allow_push: Boolean(git.allow_push),
      require_clean_baseline: Boolean(git.require_clean_baseline),
    },
    validation: {
      light_commands: stringArray(validation.light_commands, "validation.light_commands"),
      full_commands: stringArray(validation.full_commands, "validation.full_commands"),
    },
    runtime: {
      database: runtimePath(workspace, runtime.database, "runtime.database"),
      lock_file: runtimePath(workspace, runtime.lock_file, "runtime.lock_file"),
      stop_file: runtimePath(workspace, runtime.stop_file, "runtime.stop_file"),
      backup_directory: runtimePath(workspace, runtime.backup_directory, "runtime.backup_directory"),
      event_log: runtimePath(workspace, runtime.event_log, "runtime.event_log"),
      command_log_directory: runtimePath(workspace, runtime.command_log_directory, "runtime.command_log_directory"),
      work_queue: runtimePath(workspace, runtime.work_queue, "runtime.work_queue"),
      workspace_write_backend: requiredString(runtime.workspace_write_backend, "runtime.workspace_write_backend") as "direct" | "wsl",
      wsl_distro: requiredString(runtime.wsl_distro, "runtime.wsl_distro"),
      dry_run: Boolean(runtime.dry_run),
      log_level: requiredString(runtime.log_level, "runtime.log_level") as AutonomyConfig["runtime"]["log_level"],
    },
  };

  if (config.mode !== "GO_BATCH_OUI") {
    throw new Error(`Unsupported autonomy mode: ${config.mode}`);
  }
  if (!(["direct", "wsl"] as const).includes(config.runtime.workspace_write_backend)) {
    throw new Error(`Unsupported workspace write backend: ${config.runtime.workspace_write_backend}`);
  }
  return config;
}
