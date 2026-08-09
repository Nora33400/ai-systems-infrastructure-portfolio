import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { WorkspaceWriter } from "../../src/autonomy/workspace-writer.js";
import { RecoveryManager } from "../../src/autonomy/recovery-manager.js";
import { task, testConfig } from "./test-helpers.js";

test("writer mutates atomically and recovery restores changed and newly-created files", async () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-recovery-"));
  const config = testConfig(workspace);
  const writer = new WorkspaceWriter(config);
  const recovery = new RecoveryManager(config, writer);
  const existing = join(workspace, "docs", "existing.md");
  const created = join(workspace, "docs", "created.md");
  writeFileSync(existing, "before", "utf8");
  recovery.begin(task("T-REC", { attempts: 1 }));
  recovery.backup(existing);
  recovery.backup(created);
  await writer.writeFile(existing, "after");
  await writer.writeFile(created, "new");
  assert.deepEqual(recovery.changedFiles().sort(), ["docs/created.md", "docs/existing.md"]);
  assert.match(recovery.diff(), /after/);
  await recovery.restore();
  assert.equal(readFileSync(existing, "utf8"), "before");
  assert.throws(() => readFileSync(created, "utf8"));
});
