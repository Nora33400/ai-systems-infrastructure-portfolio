import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { StructuredRequest } from "./ollama-client.js";
import type {
  AutonomyConfig,
  AutonomyReceipt,
  OllamaReadOnlyReport,
  ReadOnlyReportRecord,
  ReadOnlyTaskPackage,
} from "./types.js";
import { EventLogger } from "./event-logger.js";
import { hashReadOnlyValue, ReadOnlyTaskPackageBuilder } from "./read-only-task-package.js";
import { ReceiptEngine } from "./receipt-engine.js";
import { RuntimeLock, StopController } from "./runtime-control.js";
import { StateStore } from "./state-store.js";

export interface ReadOnlyOllamaPort {
  availableModels(): Promise<string[]>;
  structured<T>(request: StructuredRequest<T>): Promise<T>;
}

export interface OllamaReadOnlyRunResult {
  report: ReadOnlyReportRecord;
  receipt: AutonomyReceipt;
  attempted_models: string[];
}

const PATCH_MARKERS = /(\*\*\* Begin Patch|diff --git|^@@\s+-\d)/m;

export class OllamaReadOnlyWorker {
  private readonly schema: Record<string, unknown>;
  private readonly ajv: Ajv2020;
  private readonly validateSchema: ReturnType<Ajv2020["compile"]>;
  private validationIssue = "unknown validation issue";

  constructor(
    private readonly config: AutonomyConfig,
    private readonly store: StateStore,
    private readonly receipts: ReceiptEngine,
    private readonly logger: EventLogger,
    private readonly lock: RuntimeLock,
    private readonly stop: StopController,
    private readonly ollama: ReadOnlyOllamaPort,
    schemaPath: string,
  ) {
    this.schema = JSON.parse(readFileSync(schemaPath, "utf8")) as Record<string, unknown>;
    this.ajv = new Ajv2020({ allErrors: true, strict: false });
    this.validateSchema = this.ajv.compile(this.schema);
  }

  async run(taskId: string): Promise<OllamaReadOnlyRunResult> {
    this.lock.acquire();
    let executionId: string | null = null;
    let built: ReturnType<ReadOnlyTaskPackageBuilder["build"]> | null = null;
    const attemptedModels: string[] = [];
    try {
      const disabled = this.stop.disabledReason();
      if (disabled) throw new Error(`Autonomy is disabled: ${disabled}`);
      const task = this.store.getTask(taskId);
      if (!task) throw new Error(`Unknown task: ${taskId}`);
      if (["SENSITIVE", "CRITICAL"].includes(task.risk_level)) {
        throw new Error(`Read-only Ollama refuses ${task.risk_level} task context without explicit human authorization.`);
      }

      built = new ReadOnlyTaskPackageBuilder(this.config).build(task);
      executionId = `EXE-${randomUUID()}`;
      const startedAt = new Date().toISOString();
      this.store.startExecution({
        execution_id: executionId,
        task_id: task.id,
        status: "RUNNING",
        actor: "OLLAMA_READ_ONLY",
        started_at: startedAt,
        updated_at: startedAt,
        finished_at: null,
        attempt: task.attempts + 1,
        checkpoint: {
          phase: "readonly_package_built",
          input_hash: hashReadOnlyValue(built.taskPackage),
          task_status_unchanged: task.status,
        },
        result: null,
      });

      const installed = await this.ollama.availableModels();
      const candidates = [...new Set([
        this.config.ollama.readonly_model,
        ...this.config.ollama.fallback_models,
      ])].filter((model) => installed.includes(model));
      if (candidates.length === 0) {
        throw new Error(`No configured read-only Ollama model is installed. Configured: ${[
          this.config.ollama.readonly_model,
          ...this.config.ollama.fallback_models,
        ].join(", ")}`);
      }

      let selectedModel: string | null = null;
      let report: OllamaReadOnlyReport | null = null;
      let rawOutput = "";
      let lastError: unknown;
      for (const model of candidates) {
        attemptedModels.push(model);
        try {
          const current = await this.ollama.structured<OllamaReadOnlyReport>({
            model,
            schema: this.schema,
            system: this.systemPrompt(built.taskPackage),
            user: JSON.stringify(built.taskPackage),
            taskId: task.id,
            validate: (value): value is OllamaReadOnlyReport => this.validateReport(value, built!.taskPackage),
            validationError: () => this.validationIssue,
            onRawResponse: (content) => { rawOutput = content; },
          });
          selectedModel = model;
          report = current;
          break;
        } catch (error) {
          lastError = error;
          this.logger.log("ollama_readonly_model_failed", {
            model,
            error: error instanceof Error ? error.message : String(error),
            fallback_remaining: candidates.slice(attemptedModels.length),
          }, { taskId: task.id, level: "warn" });
        }
      }
      if (!selectedModel || !report) {
        throw new Error(`All configured read-only Ollama models failed: ${lastError instanceof Error ? lastError.message : String(lastError)}`);
      }

      const record: ReadOnlyReportRecord = {
        report_id: `ORR-${randomUUID()}`,
        task_id: task.id,
        execution_id: executionId,
        created_at: new Date().toISOString(),
        model: selectedModel,
        input_hash: hashReadOnlyValue(built.taskPackage),
        output_hash: hashReadOnlyValue(report),
        raw_output_hash: hashReadOnlyValue(rawOutput),
        task_package: built.taskPackage,
        report,
      };
      this.store.insertReadOnlyReport(record, hashReadOnlyValue(record));
      const receipt = this.receipts.create({
        task_id: task.id,
        execution_id: executionId,
        actor: "OLLAMA_READ_ONLY",
        action: "generate_schema_validated_readonly_report",
        inputs: built.taskPackage,
        outputs: report,
        files_read: built.filesRead,
        files_modified: [],
        commands: [],
        tests: [{
          name: "ollama_readonly_report_schema_and_semantics",
          passed: true,
          model: selectedModel,
          fallback_used: selectedModel !== this.config.ollama.readonly_model,
        }],
        decision: "READY_FOR_INDEPENDENT_REVIEW",
        result: {
          report_id: record.report_id,
          model: selectedModel,
          task_state_changed: false,
          repository_files_modified: 0,
        },
      });
      this.store.updateExecution(executionId, {
        status: "COMPLETED",
        finished_at: new Date().toISOString(),
        result: { report_id: record.report_id, receipt_id: receipt.receipt_id, model: selectedModel },
      });
      this.logger.log("ollama_readonly_report_completed", {
        execution_id: executionId,
        report_id: record.report_id,
        receipt_id: receipt.receipt_id,
        model: selectedModel,
        task_state_changed: false,
      }, { taskId: task.id });
      return { report: record, receipt, attempted_models: attemptedModels };
    } catch (error) {
      if (executionId) {
        const message = error instanceof Error ? error.message : String(error);
        const receipt = this.receipts.create({
          task_id: taskId,
          execution_id: executionId,
          actor: "OLLAMA_READ_ONLY",
          action: "generate_schema_validated_readonly_report",
          inputs: built?.taskPackage ?? { task_id: taskId },
          outputs: { error: message },
          files_read: built?.filesRead ?? [],
          files_modified: [],
          commands: [],
          tests: [{ name: "ollama_readonly_report", passed: false, error: message }],
          decision: "FAILED_RETRYABLE",
          result: { error: message, task_state_changed: false, repository_files_modified: 0 },
        });
        this.store.updateExecution(executionId, {
          status: "FAILED",
          finished_at: new Date().toISOString(),
          result: { error: message, receipt_id: receipt.receipt_id },
        });
      }
      throw error;
    } finally {
      this.lock.release();
    }
  }

  private validateReport(value: unknown, taskPackage: ReadOnlyTaskPackage): value is OllamaReadOnlyReport {
    if (!this.validateSchema(value)) {
      this.validationIssue = this.ajv.errorsText(this.validateSchema.errors, { separator: "; " });
      return false;
    }
    const report = value as OllamaReadOnlyReport;
    if (report.task_id !== taskPackage.task_id) {
      this.validationIssue = `task_id mismatch: expected ${taskPackage.task_id}`;
      return false;
    }
    const permittedEvidence = new Set([
      taskPackage.task_id,
      ...taskPackage.source_refs,
      ...taskPackage.dependencies,
      ...taskPackage.context_documents.flatMap((document) => [document.id, document.path]),
    ]);
    const evidence = [...report.findings, ...report.risks].flatMap((item) => item.evidence_refs);
    const unknownEvidence = evidence.filter((reference) => !permittedEvidence.has(reference));
    if (unknownEvidence.length > 0) {
      this.validationIssue = `unknown evidence refs: ${[...new Set(unknownEvidence)].join(", ")}`;
      return false;
    }
    if (PATCH_MARKERS.test(JSON.stringify(report))) {
      this.validationIssue = "patch-like content is forbidden in a read-only report";
      return false;
    }
    this.validationIssue = "valid";
    return true;
  }

  private systemPrompt(taskPackage: ReadOnlyTaskPackage): string {
    const evidence = [
      taskPackage.task_id,
      ...taskPackage.source_refs,
      ...taskPackage.dependencies,
      ...taskPackage.context_documents.flatMap((document) => [document.id, document.path]),
    ];
    return [
      "Tu es un analyste local AIONE strictement en lecture seule.",
      "Analyse uniquement le paquet JSON fourni. N'invente aucun fait absent.",
      "Tu ne peux ni lire d'autres fichiers, ni exécuter une commande, ni produire un patch, ni changer un état ou une permission.",
      "Retourne exactement un objet JSON conforme au schéma. mutation_requested doit être false.",
      `Chaque finding et risque doit citer au moins une référence parmi: ${[...new Set(evidence)].join(", ")}.`,
      "Les commandes éventuelles du paquet sont des références de validation; ne les exécute pas.",
    ].join("\n");
  }
}
