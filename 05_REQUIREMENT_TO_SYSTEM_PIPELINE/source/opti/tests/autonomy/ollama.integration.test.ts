import test from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";
import { loadConfig } from "../../src/autonomy/config.js";
import { EventLogger } from "../../src/autonomy/event-logger.js";
import { OllamaClient } from "../../src/autonomy/ollama-client.js";

const enabled = process.env.AIONE_RUN_OLLAMA_TEST === "1";

test("real Ollama endpoint returns schema-valid structured JSON", { skip: !enabled }, async () => {
  const workspace = resolve(process.env.AIONE_WORKSPACE ?? process.cwd());
  const config = loadConfig(resolve(workspace, "config/autonomy.yaml"));
  const client = new OllamaClient(config, new EventLogger(config.runtime.event_log));
  const models = await client.waitUntilAvailable();
  assert.ok(models.includes(config.ollama.coder_model));
  const schema = {
    type: "object",
    properties: { ok: { type: "boolean" }, marker: { const: "real-ollama" } },
    required: ["ok", "marker"],
    additionalProperties: false,
  };
  const response = await client.structured<{ ok: boolean; marker: string }>({
    model: config.ollama.coder_model,
    schema,
    system: "Return the required JSON object. Set ok true and marker exactly real-ollama.",
    user: "Produce the object now.",
    validate: (value): value is { ok: boolean; marker: string } => {
      const candidate = value as { ok?: unknown; marker?: unknown };
      return candidate.ok === true && candidate.marker === "real-ollama";
    },
    validationError: () => "Expected ok=true and marker=real-ollama.",
  });
  assert.deepEqual(response, { ok: true, marker: "real-ollama" });
});
