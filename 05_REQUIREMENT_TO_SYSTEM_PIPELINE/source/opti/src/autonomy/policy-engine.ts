import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parse } from "yaml";
import type { AutonomyLevel, PolicyDocument, TaskRecord } from "./types.js";

export interface PolicyDecision {
  level: AutonomyLevel;
  allowed: boolean;
  reason: string;
}

export class PolicyEngine {
  private constructor(readonly document: PolicyDocument) {}

  static load(policyPathInput: string, schemaPathInput: string): PolicyEngine {
    const policyPath = resolve(policyPathInput);
    const schemaPath = resolve(schemaPathInput);
    const document = parse(readFileSync(policyPath, "utf8")) as PolicyDocument;
    const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as Record<string, unknown>;
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    const validate = ajv.compile<PolicyDocument>(schema);
    if (!validate(document)) {
      throw new Error(`Invalid autonomy policy: ${ajv.errorsText(validate.errors, { separator: "; " })}`);
    }
    return new PolicyEngine(document);
  }

  decide(task: TaskRecord): PolicyDecision {
    if (task.subtask_depth > this.document.limits.max_subtask_depth) {
      return { level: "FORBIDDEN", allowed: false, reason: "max_subtask_depth_exceeded" };
    }
    if (task.risk_level === "CRITICAL" || task.risk_level === "SENSITIVE" || task.required_supervisor === "the owner") {
      return { level: "OWNER_REQUIRED", allowed: false, reason: "sensitive_or_human_authority_required" };
    }
    if (task.assigned_agent === "LOCAL_SYSTEM") {
      return { level: "LOCAL_SAFE", allowed: task.risk_level === "SAFE", reason: task.risk_level === "SAFE" ? "safe_local_system_task" : "local_system_requires_safe_risk" };
    }
    if (task.assigned_agent === "LOCAL_AI" || task.assigned_agent === "OLLAMA") {
      return { level: "READ_ONLY", allowed: false, reason: "ollama_write_execution_is_phase_3_or_later" };
    }
    if (task.required_supervisor === "CHATGPT") {
      return { level: "CHATGPT_REVIEW_REQUIRED", allowed: false, reason: "strategic_supervisor_required" };
    }
    if (task.required_supervisor === "CODEX" || task.assigned_agent === "CODEX_LOCAL") {
      return { level: "CODEX_REVIEW_REQUIRED", allowed: false, reason: "technical_supervisor_required" };
    }
    return { level: "FORBIDDEN", allowed: false, reason: "unrecognized_or_unassigned_agent" };
  }
}
