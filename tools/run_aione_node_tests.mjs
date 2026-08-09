import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const workspace = resolve(root, "01_AIONE_FRACTALOS", "source", "aione");
const names = [
  "thermal-context-tiles.test.mjs",
  "live-blockers.test.mjs",
  "repair-retry.test.mjs",
  "resilience-manager.test.mjs",
  "controlled-research-lab.test.mjs",
  "local-model-benchmark.test.mjs",
  "model-quality-router.test.mjs",
  "continuous-development-worker.test.mjs",
  "cognitive-immune-system.test.mjs",
  "offline-resilience.test.mjs",
  "context-authority.test.mjs",
  "reflection-engine.test.mjs"
];
const tests = names.map((name) => resolve(workspace, "forge-control", "autonomy", name));
const runtime = mkdtempSync(resolve(tmpdir(), "aione-portfolio-tests-"));
try {
  const result = spawnSync(process.execPath, ["--test", ...tests], {
    cwd: workspace,
    env: { ...process.env, AIONE_TEST_RUNTIME_ROOT: runtime },
    stdio: "inherit"
  });
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(runtime, { recursive: true, force: true });
}
