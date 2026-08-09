import test from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { CognitivePipeline } from "../../src/cognitive/cognitive-pipeline.js";
import { testConfig } from "../autonomy/test-helpers.js";

function fixture(): { workspace: string; source: string } {
  const workspace = mkdtempSync(join(tmpdir(), "aione-cog-pipeline-"));
  const actual = resolve(process.env.AIONE_WORKSPACE ?? process.cwd());
  const config = testConfig(workspace);
  cpSync(join(actual, "schemas"), join(workspace, "schemas"), { recursive: true, force: true });
  mkdirSync(join(workspace, "sources"), { recursive: true });
  const source = "sources/SRC-0001-conversation-excerpt.md";
  writeFileSync(join(workspace, source), [
    "# Architecture", "", "Cohérental", "", "Ne pas fusionner Cohérental et CorrexAI.", "",
    "Codex ne connaît pas la vraie définition de Cohérental.", "", "Pourquoi Cohérental est séparé de CorrexAI ?",
  ].join("\n"), "utf8");
  writeFileSync(join(workspace, "SOURCE_MANIFEST.yaml"), `schema_version: 1\nsources:\n  - id: SRC-0001\n    path: ${source}\n`, "utf8");
  writeFileSync(join(workspace, "MASTER_MODULE_REGISTRY.yaml"), "modules:\n  - {id: coherental, name: Cohérental}\n  - {id: correxai, name: CorrexAI}\n", "utf8");
  writeFileSync(join(workspace, "config", "autonomy.yaml"), "fixture: true\n", "utf8");
  return { workspace, source };
}

test("vertical source-to-answer pipeline resumes after interruption and preserves ids without duplication", async () => {
  const { workspace, source } = fixture(); const config = testConfig(workspace);
  let pipeline = new CognitivePipeline(config);
  const stopped = await pipeline.run(source, "Quel rôle Cohérental doit-il réellement jouer ?", { stopAfter: "tiles_built", command: "test interrupted run" });
  assert.equal(stopped.status, "interrupted"); assert.equal(stopped.stage, "tiles_built");
  const atomsBefore = pipeline.store.atoms("SRC-0001").map((atom) => atom.atom_id); pipeline.close();
  pipeline = new CognitivePipeline(config);
  const completed = await pipeline.resume(stopped.execution_id, { command: "test resume" });
  assert.equal(completed.status, "completed");
  assert.deepEqual(pipeline.store.atoms("SRC-0001").map((atom) => atom.atom_id), atomsBefore);
  const answer = pipeline.store.answer(completed.answer_id ?? ""); const diagnostic = pipeline.store.diagnostic(completed.diagnostic_id ?? "");
  assert.equal(answer?.support_check.passed, true); assert.match(answer?.text ?? "", /Cohérental/);
  assert.equal(diagnostic?.policy.single_score_rejected, true); assert.ok((diagnostic?.ambiguous_terms.length ?? 0) > 0);
  assert.deepEqual(pipeline.store.receipts(completed.execution_id).map((receipt) => receipt.task_id), ["WQ-0011", "WQ-0012", "WQ-0013", "WQ-0014", "WQ-0015", "WQ-0016", "WQ-0017", "WQ-0018", "WQ-0019", "WQ-0020"]);
  assert.ok(pipeline.store.receipts(completed.execution_id).every((receipt) => receipt.files_modified.length > 0));
  const duplicate = pipeline.ingestOnly(source, "test duplicate ingestion");
  assert.equal(pipeline.store.atoms("SRC-0001").length, atomsBefore.length); assert.equal(duplicate.stage, "ingested");
  pipeline.close();
});

test("pipeline rejects absent and empty sources", async () => {
  const { workspace } = fixture(); const config = testConfig(workspace); const pipeline = new CognitivePipeline(config);
  await assert.rejects(() => pipeline.run("sources/missing.md", "question"), /does not exist/);
  writeFileSync(join(workspace, "sources", "empty.md"), "\n", "utf8");
  writeFileSync(join(workspace, "SOURCE_MANIFEST.yaml"), "sources:\n  - {id: SRC-0002, path: sources/empty.md}\n", "utf8");
  await assert.rejects(() => pipeline.run("sources/empty.md", "question"), /empty/);
  pipeline.close();
});
