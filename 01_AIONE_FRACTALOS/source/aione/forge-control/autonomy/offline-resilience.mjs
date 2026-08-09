const EXTERNAL_CONNECTIONS = new Set(["trello", "google-calendar", "gmail", "email", "ntfy", "tailscale"]);

function buildOfflineResilience({ connections = [], planningOutbox = {}, commons = {}, runtimeRoot = "S:\\AI_LAB\\Runtime" } = {}) {
  const normalized = (Array.isArray(connections) ? connections : [])
    .filter((connection) => EXTERNAL_CONNECTIONS.has(String(connection.id || "").toLowerCase()))
    .map((connection) => {
      const state = String(connection.state || "").toUpperCase();
      const connectorOnly = state === "CONNECTOR_ONLY";
      const connected = connection.runtimeCredential === true || (
        !connectorOnly &&
        connection.live?.ok !== false &&
        ["ACTIVE", "CONNECTED", "READY"].includes(state)
      );
      return {
        id: connection.id,
        connected,
        blocking: false,
        localFallback: connected ? "NOT_NEEDED" : "LOCAL_OUTBOX_AND_LEDGER",
        replayWhenAvailable: true,
        state: connected ? "CONNECTED_OPTIONAL" : "DEFERRED_LOCAL"
      };
    });
  const unavailable = normalized.filter((connection) => !connection.connected);
  return {
    schema: "aione.offline-resilience.v1",
    mode: "LOCAL_LOCAL",
    developmentAutonomy: "AVAILABLE_WITHOUT_EXTERNAL_CONNECTIONS",
    sourceOfTruth: runtimeRoot,
    externalDependenciesBlocking: 0,
    externalConnections: normalized,
    deferredExternalConnections: unavailable.length,
    outboxes: {
      planning: planningOutbox,
      ownerMail: commons.transports?.emailOutbox || null,
      privateDevice: commons.transports?.tailscaleWebInbox || null
    },
    recovery: {
      strategy: "LOCAL_LEDGER_THEN_IDEMPOTENT_REPLAY",
      automaticDevelopmentPause: false,
      externalPublicationAllowedOffline: false,
      secretRequiredToContinueLocalWork: false
    }
  };
}

export { buildOfflineResilience };
