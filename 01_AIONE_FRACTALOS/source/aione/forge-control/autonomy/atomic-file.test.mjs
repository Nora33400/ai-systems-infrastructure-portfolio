import test from "node:test";
import assert from "node:assert/strict";
import { renameWithRetry } from "./atomic-file.mjs";

test("Windows transient file locks are retried with a strict bound", () => {
  let calls = 0;
  let waits = 0;
  const result = renameWithRetry("source.tmp", "state.json", {
    attempts: 4,
    delayMs: 1,
    rename: () => {
      calls += 1;
      if (calls < 3) throw Object.assign(new Error("locked"), { code: "EPERM" });
    },
    wait: () => { waits += 1; }
  });
  assert.equal(result.attempts, 3);
  assert.equal(waits, 2);
});

test("non-transient filesystem errors are never hidden", () => {
  assert.throws(() => renameWithRetry("a", "b", {
    rename: () => { throw Object.assign(new Error("missing"), { code: "ENOENT" }); },
    wait: () => { throw new Error("must not wait"); }
  }), /missing/u);
});
