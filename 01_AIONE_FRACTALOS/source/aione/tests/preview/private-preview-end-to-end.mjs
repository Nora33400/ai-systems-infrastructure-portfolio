import assert from "node:assert/strict";

const baseUrl = process.env.AIONE_FORGE_URL || "http://127.0.0.1:4310";
const actor = { id: "the owner", name: "the owner", role: "owner" };

const result = await api("/api/preview/private-readiness");
assert.equal(result.readiness.noAutomaticPublication, true);

const run = await api("/api/preview/run-readiness", {
  method: "POST",
  body: { actor }
});

assert.equal(run.result.noAutomaticPublication, true);
assert.equal(run.result.status, "NOT_READY");
assert.ok(run.result.tests.some((test) => test.id === "clean-install"));
assert.ok(run.result.tests.some((test) => test.id === "private-e2e"));

console.log("private-preview-e2e scaffold OK", {
  status: run.result.status,
  checkpointId: run.result.checkpointId
});

async function api(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method || "GET",
    headers: {
      "content-type": "application/json",
      "x-forge-actor": actor.name,
      "x-forge-role": actor.role
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || body.code || `HTTP ${response.status}`);
  return body;
}
