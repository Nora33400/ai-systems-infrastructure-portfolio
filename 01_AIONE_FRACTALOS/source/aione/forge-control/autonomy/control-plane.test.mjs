import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ControlPlaneRuntime } from "./control-plane.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function fixtures(root) {
  const registryPath = join(root, "capabilities.json");
  const permissionPath = join(root, "permissions.json");
  const roadmapPath = join(root, "roadmap.json");
  const portfolioPath = join(root, "portfolio.json");
  const githubPath = join(root, "github.json");
  writeJson(registryPath, {
    controller: {
      id: "aione-autonomous-forge",
      topology: "SINGLE_CONTROL_PLANE",
      agentIdentityCount: 1,
      externalActionsDefault: "DENY"
    },
    statuses: ["OPERATIONAL", "PARTIAL", "EVALUATE", "STANDBY", "REJECT_NOW"],
    engines: [
      { id: "ollama", category: "model-runtime", status: "OPERATIONAL", probe: { kind: "command", target: "ollama" } },
      { id: "openhands", category: "development", status: "EVALUATE", probe: { kind: "docker-image", target: "openhands" } }
    ],
    capabilities: [
      { id: "control-plane", domain: "core", status: "OPERATIONAL" },
      { id: "tilegraph", domain: "memory", status: "PARTIAL" }
    ]
  });
  writeJson(permissionPath, {
    defaultDecision: "ASK",
    protectedPaths: [join(root, "protected")],
    allowedRoots: [root],
    allow: ["read", "audit", "evidence.write"],
    ask: ["dependency.install", "git.write"],
    deny: ["delete.recursive", "write.protected-path"],
    redactKeys: ["token", "secret", "password"],
    decisionTTLSeconds: 300,
    requireFreshDecisionAtCommit: true
  });
  writeJson(roadmapPath, { waves: [{ id: "S0", status: "IMPLEMENTED" }] });
  writeJson(portfolioPath, { projects: [{ id: "aione", category: "CURRENT", path: root, status: "ACTIVE" }] });
  writeJson(githubPath, { categories: [] });
  return { registryPath, permissionPath, roadmapPath, portfolioPath, githubPath };
}

function runtime(root) {
  const files = fixtures(root);
  return new ControlPlaneRuntime({
    root,
    ...files,
    stateDir: join(root, "state"),
    clock: () => new Date("2026-07-26T03:00:00.000Z"),
    commandRunner: (command, args) => {
      if (command === "where.exe" && args[0] === "ollama") return { ok: true, stdout: "C:\\Ollama\\ollama.exe\n", stderr: "" };
      if (command === "docker") {
        return {
          ok: true,
          stdout: `${JSON.stringify({ ID: "1", Names: "openhands", Image: "openhands:local", State: "exited", Status: "Exited", Ports: "", Labels: "" })}\n`,
          stderr: ""
        };
      }
      if (command === "ollama") return { ok: true, stdout: "NAME  ID\nqwen:7b  1\n", stderr: "" };
      if (command === "nvidia-smi") return { ok: true, stdout: "RTX 4060, 8192 MiB\n", stderr: "" };
      if (command === "netstat.exe") return { ok: true, stdout: "TCP  127.0.0.1:4310  0.0.0.0:0  LISTENING  42\n", stderr: "" };
      if (command === "powershell.exe") return { ok: true, stdout: "[]", stderr: "" };
      return { ok: false, stdout: "", stderr: "not found" };
    }
  });
}

test("control plane validates a single controller and unique capability ids", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-control-plane-"));
  let control;
  try {
    control = runtime(root);
    const audit = control.audit();
    assert.equal(audit.ok, true);
    assert.equal(audit.engineCount, 2);
    assert.equal(audit.capabilityCount, 2);
  } finally {
    control?.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("permission broker allows local reads, asks for installs, and denies protected paths", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-permission-"));
  let control;
  try {
    control = runtime(root);
    assert.equal(control.authorize({ action: "read.project", targetPath: root }).decision, "ALLOW");
    assert.equal(control.authorize({ action: "dependency.install", targetPath: root }).decision, "ASK");
    assert.equal(control.authorize({ action: "read.project", targetPath: join(root, "protected", "data") }).decision, "DENY");
    assert.equal(control.verifyLedger().ok, true);
  } finally {
    control?.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("evidence ledger is hash chained and redacts secrets", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-evidence-"));
  let control;
  try {
    control = runtime(root);
    control.recordEvidence({
      eventType: "test",
      metadata: { token: "never-write-me", result: "PASS" }
    });
    control.recordEvidence({ eventType: "test-2", status: "PASS" });
    const verification = control.verifyLedger();
    assert.equal(verification.ok, true);
    assert.equal(verification.entries, 2);
    const content = readFileSync(control.paths.ledger, "utf8");
    assert.doesNotMatch(content, /never-write-me/);
    assert.match(content, /\[REDACTED\]/);
  } finally {
    control?.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("list of lists separates measured facts from unmeasured claims", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-lists-"));
  let control;
  try {
    control = runtime(root);
    const lists = control.lists();
    assert.equal(lists.reality.find((item) => item.id === "projects-present").count, 1);
    assert.equal(lists.capabilities.find((item) => item.id === "capabilities-duplicated").status, "UNMEASURED");
    assert.equal(lists.permissions.find((item) => item.id === "actions-forbidden").count, 2);
    assert.equal(lists.reality.find((item) => item.id === "ollama-models").items[0], "qwen:7b");
  } finally {
    control?.close();
    rmSync(root, { recursive: true, force: true });
  }
});
