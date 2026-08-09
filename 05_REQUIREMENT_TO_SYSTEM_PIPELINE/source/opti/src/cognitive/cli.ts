import { resolve } from "node:path";
import { loadConfig } from "../autonomy/config.js";
import { CognitivePipeline } from "./cognitive-pipeline.js";
import type { CognitiveStage } from "./types.js";
import { EventLogger } from "../autonomy/event-logger.js";
import { OllamaClient } from "../autonomy/ollama-client.js";
import { OllamaTileProposer } from "./ollama-tile-proposer.js";

function option(name: string): string | undefined {
  const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] : undefined;
}

function numberOption(name: string, fallback: number): number {
  const value = option(name); if (!value) return fallback;
  const parsed = Number(value); if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer.`); return parsed;
}

function print(value: unknown): void { console.log(JSON.stringify(value, null, 2)); }

function printExecutionSummary(pipeline: CognitivePipeline, executionId: string): void {
  const result = pipeline.result(executionId) as {
    execution: { execution_id: string; source_id: string; stage: string; status: string; atom_ids: string[]; tile_ids: string[]; relation_ids: string[]; selection_id: string | null; diagnostic_id: string | null; answer_id: string | null; version: number; error: string | null };
    selection: { selected_tiles?: string[] } | null;
    diagnostic: Record<string, unknown[]> | null;
    answer: { text?: string; support_check?: { passed?: boolean } } | null;
    receipts: unknown[];
  };
  const diagnosticCounts = result.diagnostic ? Object.fromEntries(
    ["compatible_claims", "tensions", "contradictions", "missing_dependencies", "ambiguous_terms", "unsupported_inferences", "duplicated_claims", "obsolete_claims", "suggested_resolutions"]
      .map((key) => [key, Array.isArray(result.diagnostic?.[key]) ? result.diagnostic[key].length : 0]),
  ) : null;
  print({
    execution: {
      execution_id: result.execution.execution_id, source_id: result.execution.source_id,
      stage: result.execution.stage, status: result.execution.status, version: result.execution.version,
      atoms: result.execution.atom_ids.length, tiles: result.execution.tile_ids.length,
      relations: result.execution.relation_ids.length, selection_id: result.execution.selection_id,
      diagnostic_id: result.execution.diagnostic_id, answer_id: result.execution.answer_id, error: result.execution.error,
    },
    selected_tiles: result.selection?.selected_tiles ?? [], diagnostic_counts: diagnosticCounts,
    answer: result.answer?.text ?? null, support_check_passed: result.answer?.support_check?.passed ?? null,
    receipts: { count: result.receipts.length, directory: pipeline.store.receiptDirectory },
  });
}

async function main(): Promise<void> {
  const command = process.argv[2] ?? "status";
  const config = loadConfig(resolve(option("--config") ?? "config/autonomy.yaml"));
  const pipeline = new CognitivePipeline(config);
  try {
    if (command === "run" || command === "ask") {
      const source = option("--source") ?? "sources/SRC-0001-conversation-excerpt.md";
      const question = option("--question"); if (!question) throw new Error(`${command} requires --question.`);
      const stopAfter = option("--stop-after") as CognitiveStage | undefined;
      const execution = await pipeline.run(source, question, {
        budget: numberOption("--budget", 12000), ...(stopAfter ? { stopAfter } : {}),
        command: `cognitive ${command}`,
      });
      printExecutionSummary(pipeline, execution.execution_id);
    } else if (command === "resume") {
      const executionId = option("--execution"); if (!executionId) throw new Error("resume requires --execution.");
      const execution = await pipeline.resume(executionId, { budget: numberOption("--budget", 12000), command: "cognitive resume" });
      printExecutionSummary(pipeline, execution.execution_id);
    } else if (command === "ingest") {
      const source = option("--source") ?? "sources/SRC-0001-conversation-excerpt.md";
      const execution = pipeline.ingestOnly(source, "cognitive ingest");
      print({ execution, atoms: pipeline.store.atoms(execution.source_id).length, counts: pipeline.store.counts() });
    } else if (command === "atoms") {
      const sourceId = option("--source-id") ?? "SRC-0001"; const limit = numberOption("--limit", 50);
      const atoms = pipeline.store.atoms(sourceId); print({ total: atoms.length, items: atoms.slice(0, limit) });
    } else if (command === "tiles") {
      const sourceId = option("--source-id") ?? "SRC-0001"; const subject = option("--subject")?.toLowerCase();
      const tiles = pipeline.store.tiles(sourceId).filter((tile) => !subject || tile.subject.toLowerCase().includes(subject));
      print({ total: tiles.length, items: tiles.slice(0, numberOption("--limit", 50)) });
    } else if (command === "relations") {
      const relations = pipeline.store.relations(); print({ total: relations.length, items: relations.slice(0, numberOption("--limit", 100)) });
    } else if (command === "propose") {
      const executionId = option("--execution"); const subject = option("--subject");
      if (!executionId || !subject) throw new Error("propose requires --execution and --subject.");
      const execution = pipeline.store.execution(executionId); if (!execution) throw new Error(`Unknown cognitive execution: ${executionId}`);
      const matching = pipeline.store.atoms(execution.source_id).filter((atom) => atom.content.toLowerCase().includes(subject.toLowerCase()));
      const proposer = new OllamaTileProposer(config, new OllamaClient(config, new EventLogger(config.runtime.event_log)), pipeline.store);
      print({ proposal: await proposer.propose(executionId, matching.slice(0, 12), subject), model_runs: pipeline.store.modelRuns(executionId) });
    } else if (command === "audit-receipts") {
      const executionId = option("--execution"); if (!executionId) throw new Error("audit-receipts requires --execution.");
      print({ execution_id: executionId, receipts: pipeline.auditReceipts(executionId) });
    } else if (["diagnostic", "answer", "receipt", "result"].includes(command)) {
      const executionId = option("--execution"); if (!executionId) throw new Error(`${command} requires --execution.`);
      const result = pipeline.result(executionId);
      print(command === "diagnostic" ? result.diagnostic : command === "answer" ? result.answer : command === "receipt" ? result.receipts : result);
    } else if (command === "status") {
      print({ database: config.runtime.database, counts: pipeline.store.counts() });
    } else {
      throw new Error(`Unknown cognitive command: ${command}`);
    }
  } finally { pipeline.close(); }
}

main().catch((error) => { console.error(error instanceof Error ? error.stack ?? error.message : String(error)); process.exitCode = 1; });
