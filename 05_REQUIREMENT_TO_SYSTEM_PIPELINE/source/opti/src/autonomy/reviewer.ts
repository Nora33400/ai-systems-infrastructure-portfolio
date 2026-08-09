import { Ajv2020 } from "ajv/dist/2020.js";
import type { AutonomyConfig, ReviewDecision, TaskRecord, TestResult } from "./types.js";
import { OllamaClient } from "./ollama-client.js";

const REVIEW_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    approved: { type: "boolean" },
    summary: { type: "string" },
    issues: {
      type: "array",
      items: {
        type: "object",
        properties: {
          severity: { enum: ["low", "medium", "high"] },
          description: { type: "string" },
          file: { type: "string" },
        },
        required: ["severity", "description"],
        additionalProperties: false,
      },
    },
    required_actions: { type: "array", items: { type: "string" } },
  },
  required: ["approved", "summary", "issues", "required_actions"],
  additionalProperties: false,
};

export class Reviewer {
  private readonly validate: ReturnType<Ajv2020["compile"]>;
  private readonly ajv: Ajv2020;

  constructor(
    private readonly config: AutonomyConfig,
    private readonly ollama: OllamaClient,
  ) {
    this.ajv = new Ajv2020({ allErrors: true, strict: false });
    this.validate = this.ajv.compile(REVIEW_SCHEMA);
  }

  async review(task: TaskRecord, context: string, diff: string, validation: TestResult[]): Promise<ReviewDecision> {
    const system = [
      "You are the independent reviewer for a controlled local coding agent.",
      "Review the actual diff against the task and validation evidence.",
      "Reject scope creep, unsafe paths or commands, missing tests, unjustified TODO/mocks/stubs, logical errors, and unsupported completion claims.",
      "The transport already guarantees schema-valid JSON; do not invent JSON-format issues in the work under review.",
      "Do not trust the coder summary. Return only the schema-valid review object.",
    ].join("\n");
    const taskSummary = {
      id: task.id,
      title: task.title,
      module: task.module,
      description: task.description,
      acceptance: task.acceptance,
      likely_files: task.likely_files,
      source_refs: task.source_refs,
      attempt: task.attempts,
    };
    const user = [
      "TASK\n" + JSON.stringify(taskSummary, null, 2),
      "VALIDATION\n" + JSON.stringify(validation, null, 2),
      "TARGETED CONTEXT\n" + context.slice(0, 10000),
      "ACTUAL DIFF\n" + diff.slice(0, 12000),
    ].join("\n\n");

    return await this.ollama.structured<ReviewDecision>({
      model: this.config.ollama.reviewer_model,
      schema: REVIEW_SCHEMA,
      system,
      user,
      taskId: task.id,
      validate: (value): value is ReviewDecision => Boolean(this.validate(value)),
      validationError: () => this.ajv.errorsText(this.validate.errors),
    });
  }
}
