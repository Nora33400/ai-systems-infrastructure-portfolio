import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import type { AutonomyConfig, ReadOnlyContextDocument, ReadOnlyTaskPackage, TaskRecord } from "./types.js";
import { SecurityPolicy, SecurityViolation } from "./security-policy.js";

const MAX_DOCUMENT_CHARS = 4_000;
const MAX_CONTEXT_CHARS = 10_000;

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function normalizedRelativePath(value: string): string {
  if (isAbsolute(value)) throw new SecurityViolation(`Absolute task path is denied: ${value}`);
  const normalized = value.replaceAll("\\", "/").replace(/^\.\//, "");
  if (normalized === "" || normalized === "." || normalized.split("/").includes("..")) {
    throw new SecurityViolation(`Unsafe task path is denied: ${value}`);
  }
  return normalized.replace(/\/$/, "");
}

function pathWithin(candidate: string, declaredRoot: string): boolean {
  return candidate === declaredRoot || candidate.startsWith(`${declaredRoot}/`);
}

export interface BuiltReadOnlyTaskPackage {
  taskPackage: ReadOnlyTaskPackage;
  filesRead: string[];
}

export class ReadOnlyTaskPackageBuilder {
  private readonly security: SecurityPolicy;

  constructor(private readonly config: AutonomyConfig) {
    this.security = new SecurityPolicy(config);
  }

  build(task: TaskRecord): BuiltReadOnlyTaskPackage {
    const forbiddenPaths = [...new Set(task.forbidden_paths.map(normalizedRelativePath))].sort();
    const allowedReadPaths = [...new Set(task.allowed_paths.map((entry) => {
      const normalized = normalizedRelativePath(entry);
      this.security.resolveReadPath(normalized);
      if (forbiddenPaths.some((forbidden) => pathWithin(normalized, forbidden) || pathWithin(forbidden, normalized))) {
        throw new SecurityViolation(`Allowed path overlaps a forbidden path: ${normalized}`);
      }
      return normalized;
    }))].sort();

    const documents: ReadOnlyContextDocument[] = [];
    const unresolved: string[] = [];
    let remainingContextChars = Math.min(MAX_CONTEXT_CHARS, Math.floor(this.config.limits.max_context_chars / 2));

    for (const requirement of task.context_requirements) {
      if (/^SRC-[0-9]{4}$/.test(requirement)) continue;
      const relativePath = this.resolveContextAlias(task, requirement);
      if (!relativePath) {
        unresolved.push(requirement);
        continue;
      }
      if (!allowedReadPaths.some((allowed) => pathWithin(relativePath, allowed))) {
        unresolved.push(requirement);
        continue;
      }
      const absolutePath = this.security.resolveReadPath(relativePath);
      if (!existsSync(absolutePath) || remainingContextChars <= 0) {
        unresolved.push(requirement);
        continue;
      }
      const fullContent = readFileSync(absolutePath, "utf8");
      const limit = Math.min(MAX_DOCUMENT_CHARS, remainingContextChars);
      const content = fullContent.slice(0, limit);
      remainingContextChars -= content.length;
      documents.push({
        id: requirement,
        path: relativePath,
        content,
        content_sha256: sha256(content),
        truncated: content.length < fullContent.length,
      });
    }

    const taskPackage: ReadOnlyTaskPackage = {
      schema_version: 1,
      task_id: task.id,
      title: task.title,
      objective: task.objective,
      project: task.project,
      module: task.module,
      risk_level: task.risk_level,
      dependencies: [...new Set(task.dependencies)],
      source_refs: [...new Set(task.source_refs)],
      acceptance_criteria: [...(task.acceptance_criteria ?? task.acceptance)],
      allowed_read_paths: allowedReadPaths,
      forbidden_paths: forbiddenPaths,
      validation_commands_reference_only: [...new Set(task.allowed_commands)],
      context_requirements: [...new Set(task.context_requirements)],
      unresolved_context_requirements: [...new Set(unresolved)],
      context_documents: documents,
      safety_rules: {
        mode: "READ_ONLY",
        may_read_supplied_package: true,
        may_propose_next_actions: true,
        may_modify_files: false,
        may_emit_patch: false,
        may_execute_commands: false,
        may_access_secrets: false,
        may_change_task_state: false,
        may_expand_permissions: false,
      },
    };

    const serialized = JSON.stringify(taskPackage);
    if (serialized.length > this.config.limits.max_context_chars) {
      throw new Error(`Read-only task package exceeds max_context_chars: ${serialized.length}`);
    }
    return { taskPackage, filesRead: documents.map((document) => document.path) };
  }

  private resolveContextAlias(task: TaskRecord, requirement: string): string | null {
    const contractAlias = `${task.module.replaceAll("-", "_")}_contract`;
    if (requirement === contractAlias || (task.module === "autonomy-engine" && requirement === "autonomy_engine_contract")) {
      return `modules/${task.module}/contract.yaml`;
    }
    if (requirement === "local_capability_audit") {
      return "docs/autonomy-planning/local-capability-audit-2026-07-18.md";
    }
    return null;
  }
}

export function hashReadOnlyValue(value: unknown): string {
  return sha256(JSON.stringify(value));
}

export function relativeToWorkspace(workspace: string, absolutePath: string): string {
  return relative(resolve(workspace), absolutePath).replaceAll("\\", "/");
}
