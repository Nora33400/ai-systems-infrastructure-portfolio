import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "era-binary");

test("the dependency-free HCI/CIR reference runtime passes its Python suite", () => {
  const result = spawnSync(
    "python",
    ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    { cwd: ROOT, encoding: "utf8", timeout: 60_000, windowsHide: true }
  );
  assert.equal(result.error, undefined, result.error?.message);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stderr, /OK/u);
});

test("HCI topology CLI emits observed local-only topology", () => {
  const result = spawnSync("python", ["-m", "era_binary.cli", "topology"], {
    cwd: ROOT,
    encoding: "utf8",
    timeout: 15_000,
    windowsHide: true
  });
  assert.equal(result.status, 0, result.stderr);
  const topology = JSON.parse(result.stdout);
  assert.equal(topology.schema, "aione.hardware-topology.v1");
  assert.equal(topology.networkInspection, "NOT_PERFORMED");
  assert.ok(topology.cpu.logicalProcessors >= 1);
});
