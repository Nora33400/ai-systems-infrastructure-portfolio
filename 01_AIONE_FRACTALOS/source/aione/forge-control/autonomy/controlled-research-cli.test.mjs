import assert from "node:assert/strict";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";

const cliPath = join(dirname(fileURLToPath(import.meta.url)), "controlled-research-cli.mjs");

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "aione-research-cli-"));
  const runtimeRoot = join(root, "runtime");
  const configPath = join(root, "controlled-research.json");
  writeFileSync(configPath, JSON.stringify({
    schema: "aione.controlled-research-lab-config.v1",
    enabled: true,
    runtimeRoot,
    schedule: { minimumIntervalHours: 24, offlineFallback: true },
    budgets: {
      maxSourcesPerRun: 1,
      maxRequestsPerRun: 1,
      maxItemsPerSource: 2,
      maxItemsPerRun: 2,
      maxBytesPerResponse: 10_000,
      maxBytesPerRun: 10_000,
      timeoutMs: 50,
      maxGraphNodes: 10,
      maxGraphEdges: 20,
      maxGraphDepth: 1,
      maxProposalsPerRun: 2
    },
    sources: [{
      id: "arxiv-test",
      provider: "ARXIV_ATOM",
      baseUrl: "https://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=2",
      allowedHosts: ["export.arxiv.org"],
      enabled: true,
      optional: true,
      ecosystemId: "scientific"
    }]
  }, null, 2), "utf8");
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return { configPath, runtimeRoot };
}

function invoke(configPath, ...args) {
  const result = spawnSync(process.execPath, [cliPath, ...args], {
    encoding: "utf8",
    env: {
      ...process.env,
      NODE_ENV: "test",
      AIONE_CONTROLLED_RESEARCH_CONFIG: configPath
    }
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(result.stdout);
}

test("simulate remains read-only and status is JSON", (t) => {
  const { configPath, runtimeRoot } = fixture(t);
  const simulated = invoke(configPath, "simulate");
  assert.equal(simulated.mutationPerformed, false);
  assert.equal(simulated.networkPerformed, false);
  assert.equal(simulated.schedule.due, true);
  assert.equal(existsSync(join(runtimeRoot, "state.json")), false);

  const status = invoke(configPath, "status");
  assert.equal(status.configuredEnabled, true);
  assert.equal(status.counts.runs, 0);
  assert.equal(status.runtimeRoot, runtimeRoot);
});

test("offline cycle degrades safely and daily gate prevents duplicate work", (t) => {
  const { configPath, runtimeRoot } = fixture(t);
  const first = invoke(configPath, "cycle", "--offline");
  assert.equal(first.run.state, "DEGRADED_NO_DATA");
  assert.equal(first.run.offlineRequested, true);
  assert.equal(first.externalMutationPerformed, false);
  assert.equal(first.publicationPerformed, false);
  assert.equal(existsSync(join(runtimeRoot, "state.json")), true);

  const second = invoke(configPath, "cycle", "--offline");
  assert.equal(second.state, "SKIPPED_NOT_DUE");
  assert.equal(second.mutationPerformed, false);

  const status = invoke(configPath, "status");
  assert.equal(status.counts.runs, 1);
  assert.equal(status.schedule.due, false);
});
