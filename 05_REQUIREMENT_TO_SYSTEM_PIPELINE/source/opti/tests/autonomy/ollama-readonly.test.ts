import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parseStructuredJson, type StructuredRequest } from "../../src/autonomy/ollama-client.js";
import { OllamaReadOnlyWorker, type ReadOnlyOllamaPort } from "../../src/autonomy/ollama-readonly-worker.js";
import { ReadOnlyTaskPackageBuilder } from "../../src/autonomy/read-only-task-package.js";
import { ReceiptEngine } from "../../src/autonomy/receipt-engine.js";
import { RuntimeLock, StopController } from "../../src/autonomy/runtime-control.js";
import { EventLogger } from "../../src/autonomy/event-logger.js";
import { StateStore } from "../../src/autonomy/state-store.js";
import type { OllamaReadOnlyReport } from "../../src/autonomy/types.js";
import { task, testConfig } from "./test-helpers.js";

const repository = resolve(process.env.AIONE_WORKSPACE ?? process.cwd());

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function validReport(taskId = "WQ-9100"): OllamaReadOnlyReport {
  return {
    schema_version: 1,
    task_id: taskId,
    summary: "Le paquet est borné et nécessite une revue indépendante.",
    findings: [{ statement: "La tâche interdit les mutations du modèle.", evidence_refs: [taskId] }],
    risks: [{ risk: "Une preuve externe reste nécessaire.", mitigation: "Conserver la revue Codex.", evidence_refs: [taskId] }],
    suggested_next_actions: ["Exécuter les validations déterministes hors du modèle."],
    open_questions: [],
    confidence: 0.8,
    mutation_requested: false,
  };
}

class MockOllama implements ReadOnlyOllamaPort {
  readonly calls: string[] = [];

  constructor(
    private readonly models: string[],
    private readonly responses: Record<string, unknown | Error>,
  ) {}

  async availableModels(): Promise<string[]> {
    return this.models;
  }

  async structured<T>(request: StructuredRequest<T>): Promise<T> {
    this.calls.push(request.model);
    const response = this.responses[request.model];
    if (response instanceof Error) throw response;
    if (!request.validate(response)) throw new Error(request.validationError());
    const content = JSON.stringify(response);
    request.onRawResponse?.(content, response);
    return response;
  }
}

function fixture(): {
  workspace: string;
  store: StateStore;
  receipts: ReceiptEngine;
  logger: EventLogger;
  lock: RuntimeLock;
  stop: StopController;
  config: ReturnType<typeof testConfig>;
} {
  const workspace = mkdtempSync(join(tmpdir(), "opti-readonly-"));
  const config = testConfig(workspace);
  mkdirSync(join(workspace, "modules", "autonomy-engine"), { recursive: true });
  mkdirSync(join(workspace, "docs", "autonomy-planning"), { recursive: true });
  writeFileSync(join(workspace, "modules", "autonomy-engine", "contract.yaml"), "id: autonomy-engine\nstatus: TESTED\n", "utf8");
  writeFileSync(join(workspace, "docs", "autonomy-planning", "local-capability-audit-2026-07-18.md"), "# Audit\nOllama local observé.\n", "utf8");
  const store = new StateStore(config.runtime.database);
  const receipts = new ReceiptEngine(store, join(repository, "schemas", "autonomy-receipt.schema.json"));
  return {
    workspace,
    store,
    receipts,
    logger: new EventLogger(config.runtime.event_log),
    lock: new RuntimeLock(config.runtime.lock_file),
    stop: new StopController(config.runtime.stop_file),
    config,
  };
}

test("structured parser accepts only raw JSON or one exact JSON fence", () => {
  assert.deepEqual(parseStructuredJson('{"ok":true}'), { ok: true });
  assert.deepEqual(parseStructuredJson('```json\n{"ok":true}\n```'), { ok: true });
  assert.throws(() => parseStructuredJson('Voici le résultat:\n```json\n{"ok":true}\n```'));
  assert.throws(() => parseStructuredJson('```json\n{"ok":true}\n```\ntexte'));
});

test("the canonical WQ-0044 Codex review receipt keeps its schema and runtime hash", () => {
  const receipt = JSON.parse(readFileSync(join(repository, "receipts", "autonomy-planning", "WQ-0044.json"), "utf8")) as Record<string, unknown>;
  const schema = JSON.parse(readFileSync(join(repository, "schemas", "autonomy-receipt.schema.json"), "utf8")) as Record<string, unknown>;
  const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema);
  assert.equal(validate(receipt), true);
  assert.equal(createHash("sha256").update(JSON.stringify(receipt)).digest("hex"), "7d3ce70f9cd1bb60230a6bf7b4053004e0ad512a295944764e21ffdee041edc5");
});

test("read-only package is bounded, preserves canonical acceptance criteria and exposes no action capability", () => {
  const { store, config } = fixture();
  const record = task("WQ-9100", {
    status: "READY_CODEX_REVIEW",
    objective: "Produire un rapport local sans patch.",
    acceptance_criteria: ["task_package_bounded", "no_patch_or_file_mutation"],
    acceptance: [],
    allowed_paths: ["modules/autonomy-engine", "docs/autonomy-planning"],
    forbidden_paths: [".git", ".env"],
    context_requirements: ["SRC-0012", "autonomy_engine_contract", "local_capability_audit"],
    source_refs: ["SRC-0012"],
    allowed_commands: ["npm test"],
  });
  const built = new ReadOnlyTaskPackageBuilder(config).build(record);
  assert.deepEqual(built.taskPackage.acceptance_criteria, ["task_package_bounded", "no_patch_or_file_mutation"]);
  assert.deepEqual(built.taskPackage.context_documents.map((entry) => entry.id), ["autonomy_engine_contract", "local_capability_audit"]);
  assert.deepEqual(built.taskPackage.unresolved_context_requirements, []);
  assert.equal(built.taskPackage.safety_rules.may_modify_files, false);
  assert.equal(built.taskPackage.safety_rules.may_execute_commands, false);
  assert.equal(built.taskPackage.validation_commands_reference_only[0], "npm test");
  assert.ok(JSON.stringify(built.taskPackage).length < config.limits.max_context_chars);
  store.close();
});

test("read-only worker falls back after timeout, persists hashes and never changes task or repository files", async () => {
  const fx = fixture();
  const record = task("WQ-9100", {
    status: "READY_CODEX_REVIEW",
    risk_level: "CONTROLLED",
    allowed_paths: ["modules/autonomy-engine", "docs/autonomy-planning"],
    forbidden_paths: [".git", ".env"],
    context_requirements: ["autonomy_engine_contract"],
    source_refs: ["SRC-0012"],
  });
  fx.store.saveTask(record);
  const contract = join(fx.workspace, "modules", "autonomy-engine", "contract.yaml");
  const before = sha256(readFileSync(contract, "utf8"));
  const mock = new MockOllama(
    [fx.config.ollama.readonly_model, fx.config.ollama.fallback_models[0]!],
    {
      [fx.config.ollama.readonly_model]: new Error("timeout"),
      [fx.config.ollama.fallback_models[0]!]: validReport(),
    },
  );
  const worker = new OllamaReadOnlyWorker(
    fx.config, fx.store, fx.receipts, fx.logger, fx.lock, fx.stop, mock,
    join(repository, "schemas", "ollama-readonly-report.schema.json"),
  );
  const result = await worker.run(record.id);
  assert.deepEqual(result.attempted_models, [fx.config.ollama.readonly_model, fx.config.ollama.fallback_models[0]]);
  assert.equal(result.report.model, fx.config.ollama.fallback_models[0]);
  assert.equal(fx.store.getTask(record.id)?.status, "READY_CODEX_REVIEW");
  assert.equal(sha256(readFileSync(contract, "utf8")), before);
  assert.deepEqual(result.receipt.files_modified, []);
  assert.deepEqual(result.receipt.commands, []);
  assert.deepEqual(fx.store.verifyReadOnlyReports(), { valid: true, count: 1, issues: [] });
  assert.deepEqual(fx.receipts.verifyAll(), { valid: true, count: 1, issues: [] });
  fx.store.close();
});

test("unknown evidence and patch-like output are rejected with a failure receipt", async () => {
  const fx = fixture();
  const record = task("WQ-9101", {
    status: "READY_CODEX_REVIEW",
    allowed_paths: ["modules/autonomy-engine"],
    forbidden_paths: [".git", ".env"],
    source_refs: ["SRC-0012"],
  });
  fx.store.saveTask(record);
  const invalid = validReport(record.id);
  invalid.findings[0]!.evidence_refs = ["INVENTED-EVIDENCE"];
  invalid.suggested_next_actions = ["*** Begin Patch"];
  const mock = new MockOllama([fx.config.ollama.readonly_model], { [fx.config.ollama.readonly_model]: invalid });
  const worker = new OllamaReadOnlyWorker(
    fx.config, fx.store, fx.receipts, fx.logger, fx.lock, fx.stop, mock,
    join(repository, "schemas", "ollama-readonly-report.schema.json"),
  );
  await assert.rejects(() => worker.run(record.id), /All configured read-only Ollama models failed/);
  assert.equal(fx.store.listReadOnlyReports().length, 0);
  assert.equal(fx.store.getTask(record.id)?.status, "READY_CODEX_REVIEW");
  assert.equal(fx.store.listExecutions(record.id)[0]?.status, "FAILED");
  assert.equal(fx.receipts.verifyAll().count, 1);
  fx.store.close();
});

test("missing Ollama models fail locally without blocking the persistent kernel", async () => {
  const fx = fixture();
  const record = task("WQ-9102", {
    status: "READY_CODEX_REVIEW",
    allowed_paths: ["docs"],
    forbidden_paths: [".git", ".env"],
  });
  fx.store.saveTask(record);
  const worker = new OllamaReadOnlyWorker(
    fx.config, fx.store, fx.receipts, fx.logger, fx.lock, fx.stop, new MockOllama([], {}),
    join(repository, "schemas", "ollama-readonly-report.schema.json"),
  );
  await assert.rejects(() => worker.run(record.id), /No configured read-only Ollama model is installed/);
  fx.store.saveTask(task("WQ-9103", { status: "READY_LOCAL_AI" }));
  assert.equal(fx.store.getTask("WQ-9103")?.status, "READY_LOCAL_AI");
  assert.equal(fx.store.getTask(record.id)?.status, "READY_CODEX_REVIEW");
  fx.store.close();
});

test("read-only report verification detects database tampering", async () => {
  const fx = fixture();
  const record = task("WQ-9104", {
    status: "READY_CODEX_REVIEW",
    allowed_paths: ["docs"],
    forbidden_paths: [".git", ".env"],
  });
  fx.store.saveTask(record);
  const mock = new MockOllama([fx.config.ollama.readonly_model], {
    [fx.config.ollama.readonly_model]: validReport(record.id),
  });
  const worker = new OllamaReadOnlyWorker(
    fx.config, fx.store, fx.receipts, fx.logger, fx.lock, fx.stop, mock,
    join(repository, "schemas", "ollama-readonly-report.schema.json"),
  );
  const result = await worker.run(record.id);
  fx.store.close();

  const database = new DatabaseSync(fx.config.runtime.database);
  database.prepare("UPDATE autonomy_readonly_reports SET data_json = replace(data_json, '0.8', '0.1') WHERE report_id = ?")
    .run(result.report.report_id);
  database.close();

  const reopened = new StateStore(fx.config.runtime.database);
  const verification = reopened.verifyReadOnlyReports();
  assert.equal(verification.valid, false);
  assert.ok(verification.issues.some((issue) => issue.includes("content_hash_mismatch")));
  reopened.close();
});
