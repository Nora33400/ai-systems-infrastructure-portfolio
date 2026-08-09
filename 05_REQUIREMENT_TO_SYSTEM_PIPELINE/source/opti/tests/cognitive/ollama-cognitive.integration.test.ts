import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EventLogger } from "../../src/autonomy/event-logger.js";
import { OllamaClient } from "../../src/autonomy/ollama-client.js";
import { CognitiveStore } from "../../src/cognitive/cognitive-store.js";
import { OllamaTileProposer } from "../../src/cognitive/ollama-tile-proposer.js";
import type { Atom } from "../../src/cognitive/types.js";
import { testConfig } from "../autonomy/test-helpers.js";

const enabled = process.env.AIONE_RUN_COGNITIVE_OLLAMA_TEST === "1";

test("real Ollama proposal is schema-gated, atom-bounded and auditable", { skip: !enabled, timeout: 180_000 }, async () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-cognitive-ollama-"));
  const config = testConfig(workspace);
  config.ollama.coder_model = "qwen2.5-coder:14b";
  config.ollama.reviewer_model = "qwen2.5-coder:14b";
  config.ollama.context_size = 16_384;
  config.ollama.timeout_ms = 120_000;
  config.ollama.response_retries = 2;
  config.ollama.availability_retries = 0;
  const store = new CognitiveStore(config.runtime.database);
  const client = new OllamaClient(config, new EventLogger(config.runtime.event_log));
  await client.waitUntilAvailable();
  const atom: Atom = {
    schema_version: 1,
    atom_id: "ATM-OLLAMA-0001",
    source_id: "SRC-0001",
    atom_type: "paragraph",
    content: "Cohérental doit effectuer une passe globale de cohérence.",
    content_hash: "sha256:test",
    source_position: { start_line: 1, end_line: 1 },
    epistemic_status: "observed",
    created_at: new Date().toISOString(),
    valid: true,
  };
  const executionId = "COG-EXE-OLLAMA-REAL";
  const proposal = await new OllamaTileProposer(config, client, store).propose(executionId, [atom], "Cohérental");
  assert.ok(proposal.atom_ids.length > 0);
  assert.ok(proposal.atom_ids.every((id) => id === atom.atom_id));
  assert.ok(proposal.claims.length > 0);
  assert.ok(proposal.claims.every((claim) => claim.content === atom.content));
  const runs = store.modelRuns(executionId);
  assert.equal(runs.length, 1);
  assert.equal(runs[0]?.valid, true);
  assert.equal(runs[0]?.model, "qwen2.5-coder:14b");
  assert.match(String(runs[0]?.prompt_hash), /^sha256:/);
  assert.ok(String(runs[0]?.raw_output).length > 0);
  store.close();
});
