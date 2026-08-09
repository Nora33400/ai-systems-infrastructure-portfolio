import test from "node:test";
import assert from "node:assert/strict";
import { buildOfflineResilience } from "./offline-resilience.mjs";

test("external outages never block local-local development", () => {
  const result = buildOfflineResilience({
    connections: [
      { id: "trello", state: "NOT_CONFIGURED", live: { ok: false } },
      { id: "google-calendar", state: "DISCONNECTED", live: { ok: false } }
    ],
    planningOutbox: { pending: 3 },
    commons: { transports: { emailOutbox: { state: "WAITING" } } }
  });
  assert.equal(result.mode, "LOCAL_LOCAL");
  assert.equal(result.developmentAutonomy, "AVAILABLE_WITHOUT_EXTERNAL_CONNECTIONS");
  assert.equal(result.externalDependenciesBlocking, 0);
  assert.equal(result.deferredExternalConnections, 2);
  assert.equal(result.externalConnections.every((connection) => connection.blocking === false), true);
  assert.equal(result.recovery.strategy, "LOCAL_LEDGER_THEN_IDEMPOTENT_REPLAY");
});

test("Codex-only connectors remain deferred when the autonomous runtime has no credential", () => {
  const result = buildOfflineResilience({
    connections: [
      { id: "trello", state: "CONNECTOR_ONLY", runtimeCredential: false, live: { ok: true, reason: "connector-mediated" } },
      { id: "gmail", state: "CONNECTOR_ONLY", runtimeCredential: false, live: { ok: true, reason: "connector-mediated" } }
    ]
  });
  assert.equal(result.deferredExternalConnections, 2);
  assert.equal(result.externalDependenciesBlocking, 0);
  assert.equal(result.externalConnections.every((connection) => connection.state === "DEFERRED_LOCAL"), true);
});
