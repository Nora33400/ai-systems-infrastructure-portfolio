import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ImmuneRuntime } from "./immune-runtime.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function fixture(probes = {}) {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-immune-"));
  const source = join(root, "source");
  mkdirSync(source, { recursive: true });
  for (const name of ["README.md", "contract.yaml", "evidence.yaml"]) writeFileSync(join(source, name), "preuve\n");
  const config = {
    schema: "aione.immune-runtime.v1",
    source: { path: source, requiredFiles: ["README.md", "contract.yaml", "evidence.yaml"] },
    runtimeRoot: join(root, "runtime"),
    automaticActions: ["RESTART_APPROVED_USER_SERVICE"],
    components: [
      { id: "wsl", kind: "COMMAND", command: "wsl", args: [], critical: false, repair: "REQUEST_ADMIN_SERVICE_RESTART_OR_REBOOT" },
      { id: "docker", kind: "COMMAND", command: "docker", args: [], critical: false, repair: "DEPENDENCY_WSL_FIRST" },
      { id: "forge", kind: "HTTP", endpoint: "http://127.0.0.1:4310/health", critical: true, repair: "RESTART_APPROVED_USER_SERVICE" }
    ],
    programUpdates: [{ id: "docker", manager: "winget", packageId: "Docker.DockerDesktop", automaticApply: false, reason: "system" }],
    bootstrap: { enabled: false, repositoryUrl: null, pinnedCommit: null, allowedHost: "github.com", destination: join(root, "bootstrap") }
  };
  const configPath = join(root, "config.json");
  writeFileSync(configPath, JSON.stringify(config));
  const runtime = new ImmuneRuntime({
    configPath,
    now: () => new Date("2026-07-31T12:00:00.000Z"),
    commandRunner: (component) => probes[component.id] || { ok: true, status: "HEALTHY" },
    httpRunner: (component) => probes[component.id] || { ok: true, status: "HEALTHY" }
  });
  return { root, runtime, cleanup: () => rmSync(root, { recursive: true, force: true }) };
}

test("IMMUNE keeps source read-only and records a healthy hash-chained cycle", async (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const result = await fx.runtime.cycle();
  assert.equal(result.status, "HEALTHY");
  assert.equal(result.doctor.source.access, "READ_ONLY");
  assert.ok(["GREEN", "YELLOW", "ORANGE", "RED", "BLACK"].includes(result.doctor.cognitiveHealth.level));
  assert.equal(result.doctor.cognitiveHealth.automaticMutationPerformed, false);
  assert.match(result.ledgerHash, /^[a-f0-9]{64}$/u);
});

test("WSL timeout explains Docker chain and requests admin action without reboot", async (context) => {
  const fx = fixture({
    wsl: { ok: false, status: "TIMEOUT", error: "timeout" },
    docker: { ok: false, status: "FAILED", error: "daemon" }
  });
  context.after(fx.cleanup);
  const doctor = await fx.runtime.doctor();
  const diagnosis = fx.runtime.diagnose(doctor);
  const plan = fx.runtime.anesthetize(diagnosis);
  const repair = fx.runtime.repair(plan, { applySafe: true });
  assert.ok(diagnosis.diagnoses.some((entry) => entry.cause === "WSL_UNRESPONSIVE_DEPENDENCY_CHAIN"));
  assert.equal(plan.rebootAutomatic, false);
  assert.equal(repair.receipts[0].status, "REQUESTED");
  const repeated = fx.runtime.repair(plan, { applySafe: true });
  assert.equal(repeated.receipts[0].status, "REQUESTED_DUPLICATE");
  assert.equal(repeated.receipts[0].requestPath, repair.receipts[0].requestPath);
});

test("autoupgrade refuses arbitrary or automatic system upgrades", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const plan = fx.runtime.autoupgrade({ apply: true });
  assert.equal(plan.programs[0].decision, "CHECK_ONLY_OR_MAINTENANCE_WINDOW");
  assert.equal(plan.arbitraryProgramUpgrade, false);
  assert.equal(plan.unsignedInstallAllowed, false);
});

test("bootstrap does not guess or download an unpinned repository", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  rmSync(fx.runtime.config.source.path, { recursive: true, force: true });
  const result = fx.runtime.bootstrap();
  assert.equal(result.status, "OWNER_PINNED_REPOSITORY_REQUIRED");
});
