import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Ajv2020, type ValidateFunction } from "ajv/dist/2020.js";

export class CognitiveSchemaValidator {
  private readonly ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });
  private readonly validators = new Map<string, ValidateFunction>();

  constructor(private readonly workspace: string) {}

  validate(schemaName: string, value: unknown): { valid: boolean; errors: string[] } {
    let validator = this.validators.get(schemaName);
    if (!validator) {
      const schema = JSON.parse(readFileSync(join(this.workspace, "schemas", schemaName), "utf8")) as Record<string, unknown>;
      validator = this.ajv.compile(schema);
      this.validators.set(schemaName, validator);
    }
    const valid = Boolean(validator(value));
    return { valid, errors: valid ? [] : (validator.errors ?? []).map((error) => `${error.instancePath || "/"} ${error.message ?? "invalid"}`) };
  }
}
