import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  ContextAuthorityLedger,
  buildPolicyContextResolution,
  readContextAuthorityPolicy,
  verifyContextAuthorityResolution
} from "./context-authority.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const DEFAULT_DATABASE = resolve(
  process.env.AIONE_CONTEXT_AUTHORITY_DB || "S:\\AI_LAB\\Runtime\\ContextAuthority\\authority.sqlite"
);
const command = String(process.argv[2] || "status").toLowerCase();

function inspect({ record = false } = {}) {
  const { path, policy, validation } = readContextAuthorityPolicy(ROOT);
  const resolution = buildPolicyContextResolution(policy);
  const existed = existsSync(DEFAULT_DATABASE);
  const ledger = new ContextAuthorityLedger({ databasePath: DEFAULT_DATABASE, policy });
  let appendStatus = "NOT_REQUESTED";
  let appended = null;
  try {
    if (record) {
      try {
        appended = ledger.appendRevision({
          ...policy.activeRevision,
          sourceType: "CURRENT_AUTHENTICATED_REQUEST"
        });
        appendStatus = "RECORDED";
      } catch (error) {
        if (/UNIQUE constraint failed/iu.test(String(error?.message || error))) appendStatus = "ALREADY_RECORDED";
        else throw error;
      }
    }
    return {
      schema: "aione.context-authority-cli-status.v1",
      policyPath: path,
      policyValidation: validation,
      resolution: {
        resolutionId: resolution.resolutionId,
        decision: resolution.decision,
        verified: verifyContextAuthorityResolution(resolution),
        authorization: resolution.authorization,
        effectiveDirectiveIds: resolution.effectiveDirectives.map((entry) => entry.id),
        revisedArtifacts: resolution.artifactRevisions
      },
      ledger: {
        databasePath: DEFAULT_DATABASE,
        existedBeforeCommand: existed,
        appendStatus,
        appended,
        integrity: ledger.verifyIntegrity(),
        limitation: "LOCAL_SQLITE_WAL_HASH_CHAIN_IS_TRACEABILITY_NOT_OWNER_AUTHENTICATION"
      }
    };
  } finally {
    ledger.close();
  }
}

if (!["status", "record-active"].includes(command)) {
  process.stderr.write("Usage: node context-authority-cli.mjs <status|record-active>\n");
  process.exitCode = 2;
} else {
  const result = inspect({ record: command === "record-active" });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.policyValidation.ok || !result.resolution.verified || !result.ledger.integrity.ok) process.exitCode = 1;
}
