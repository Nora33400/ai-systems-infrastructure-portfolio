import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadConfig } from "../../src/autonomy/config.js";
import { EventLogger } from "../../src/autonomy/event-logger.js";
import { OllamaClient } from "../../src/autonomy/ollama-client.js";
import { testConfig } from "../autonomy/test-helpers.js";

test("invalid YAML is rejected explicitly", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-invalid-yaml-"));
  const configPath = join(workspace, "invalid.yaml");
  writeFileSync(configPath, "ollama: [unterminated", "utf8");
  assert.throws(() => loadConfig(configPath));
});

test("an unavailable Ollama endpoint fails after configured retries", async () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-ollama-unavailable-"));
  const config = testConfig(workspace);
  config.ollama.url = "http://127.0.0.1:1";
  config.ollama.timeout_ms = 250;
  config.ollama.availability_retries = 0;
  const client = new OllamaClient(config, new EventLogger(config.runtime.event_log));
  await assert.rejects(() => client.waitUntilAvailable(), /Ollama unavailable after configured retries/);
});
