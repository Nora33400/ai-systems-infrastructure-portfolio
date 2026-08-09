import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SecurityPolicy } from "../../src/autonomy/security-policy.js";
import { testConfig } from "./test-helpers.js";

test("security policy accepts scoped paths and rejects escapes, secrets, protected files, and dangerous commands", () => {
  const workspace = mkdtempSync(join(tmpdir(), "aione-security-"));
  const config = testConfig(workspace);
  writeFileSync(join(workspace, "docs", "safe.md"), "safe");
  const policy = new SecurityPolicy(config);

  assert.equal(policy.resolveReadPath("docs/safe.md"), join(workspace, "docs", "safe.md"));
  assert.throws(() => policy.resolveReadPath("../escape.txt"), /escapes workspace/);
  assert.throws(() => policy.resolveWritePath("AGENTS.md"), /outside configured areas|Protected/);
  assert.throws(() => policy.resolveWritePath("docs/secret-token.txt"), /secret-like/);
  assert.throws(() => policy.validateCommand("git push origin main"), /Forbidden|read-only/);
  assert.throws(() => policy.validateCommand("node ok.js && node bad.js"), /metacharacters/);
  assert.doesNotThrow(() => policy.validateCommand("npm test"));
});
