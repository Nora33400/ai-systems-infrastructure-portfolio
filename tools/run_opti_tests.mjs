import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const workspace = process.cwd();
const testRoot = resolve(workspace, "dist", "tests");

function collect(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const path = resolve(directory, entry.name);
      return entry.isDirectory() ? collect(path) : path.endsWith(".test.js") ? [path] : [];
    });
}

const tests = collect(testRoot).sort();
if (tests.length === 0) {
  process.stderr.write("No compiled Opti tests found.\n");
  process.exit(2);
}

const result = spawnSync(process.execPath, ["--test", ...tests], {
  cwd: workspace,
  env: { ...process.env, AIONE_WORKSPACE: workspace },
  stdio: "inherit"
});
process.exit(result.status ?? 1);

