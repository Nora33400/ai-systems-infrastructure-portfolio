import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { AutonomyReceipt } from "./types.js";
import { StateStore } from "./state-store.js";

function hash(value: unknown): string {
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  return createHash("sha256").update(serialized).digest("hex");
}

export interface ReceiptDraft {
  task_id: string;
  execution_id: string;
  actor: string;
  action: string;
  inputs: unknown;
  outputs: unknown;
  files_read: string[];
  files_modified: string[];
  commands: string[];
  tests: Array<Record<string, unknown>>;
  decision: string;
  result: unknown;
  parent_receipt?: string | null;
}

export interface ReceiptVerification {
  valid: boolean;
  count: number;
  issues: string[];
}

export class ReceiptEngine {
  private readonly validate: ReturnType<Ajv2020["compile"]>;
  private readonly ajv: Ajv2020;

  constructor(private readonly store: StateStore, schemaPath: string) {
    const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as Record<string, unknown>;
    this.ajv = new Ajv2020({ allErrors: true, strict: false });
    this.validate = this.ajv.compile(schema);
  }

  create(draft: ReceiptDraft): AutonomyReceipt {
    const parent = draft.parent_receipt === undefined
      ? this.store.lastReceiptForTask(draft.task_id)?.receipt_id ?? null
      : draft.parent_receipt;
    const receipt: AutonomyReceipt = {
      receipt_id: `RCP-${randomUUID()}`,
      task_id: draft.task_id,
      execution_id: draft.execution_id,
      timestamp: new Date().toISOString(),
      actor: draft.actor,
      action: draft.action,
      inputs_hash: hash(draft.inputs),
      outputs_hash: hash(draft.outputs),
      files_read: [...draft.files_read],
      files_modified: [...draft.files_modified],
      commands: [...draft.commands],
      tests: draft.tests.map((entry) => ({ ...entry })),
      decision: draft.decision,
      result: draft.result,
      parent_receipt: parent,
    };
    if (!this.validate(receipt)) {
      throw new Error(`Invalid receipt: ${this.ajv.errorsText(this.validate.errors, { separator: "; " })}`);
    }
    this.store.insertReceipt(receipt, hash(JSON.stringify(receipt)));
    return receipt;
  }

  verifyAll(): ReceiptVerification {
    const rows = this.store.listReceiptRows();
    const ids = new Set(rows.map((row) => row.receipt.receipt_id));
    const issues: string[] = [];
    for (const row of rows) {
      if (!this.validate(row.receipt)) {
        issues.push(`${row.receipt.receipt_id}:schema:${this.ajv.errorsText(this.validate.errors)}`);
      }
      if (hash(row.data_json) !== row.content_hash) {
        issues.push(`${row.receipt.receipt_id}:content_hash_mismatch`);
      }
      if (row.receipt.parent_receipt && !ids.has(row.receipt.parent_receipt)) {
        issues.push(`${row.receipt.receipt_id}:missing_parent:${row.receipt.parent_receipt}`);
      }
    }
    return { valid: issues.length === 0, count: rows.length, issues };
  }
}
