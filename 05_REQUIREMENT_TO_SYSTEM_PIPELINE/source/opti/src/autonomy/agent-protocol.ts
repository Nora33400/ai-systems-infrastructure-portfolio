import { readFileSync } from "node:fs";
import { Ajv2020, type ValidateFunction } from "ajv/dist/2020.js";
import type { AutonomyConfig, AgentAction } from "./types.js";

export class AgentProtocol {
  readonly schema: Record<string, unknown>;
  readonly correctionSchema: Record<string, unknown>;
  private readonly validateAction: ValidateFunction<AgentAction>;
  private readonly ajv: Ajv2020;

  constructor(config: AutonomyConfig) {
    this.schema = JSON.parse(readFileSync(`${config.workspace}/schemas/agent-action.schema.json`, "utf8")) as Record<string, unknown>;
    const variants = Array.isArray(this.schema.oneOf) ? this.schema.oneOf as Array<Record<string, unknown>> : [];
    const correctionActions = new Set(["create_file"]);
    this.correctionSchema = {
      $schema: this.schema.$schema,
      $id: "https://aione.local/schemas/agent-correction-action.schema.json",
      title: "Autonomy corrective mutation action",
      oneOf: variants
        .filter((variant) => {
          const properties = variant.properties as { action?: { const?: unknown } } | undefined;
          return typeof properties?.action?.const === "string" && correctionActions.has(properties.action.const);
        })
        .map((variant) => {
          const properties = variant.properties as Record<string, unknown>;
          if ((properties.action as { const?: unknown })?.const !== "create_file") return variant;
          return {
            ...variant,
            properties: { ...properties, overwrite: { const: true } },
            required: [...new Set([...(variant.required as string[]), "overwrite"])],
          };
        }),
    };
    this.ajv = new Ajv2020({ allErrors: true, strict: false });
    this.validateAction = this.ajv.compile<AgentAction>(this.schema);
  }

  validate(value: unknown): value is AgentAction {
    return this.validateAction(value);
  }

  errors(): string {
    return this.ajv.errorsText(this.validateAction.errors, { separator: "; " });
  }
}
