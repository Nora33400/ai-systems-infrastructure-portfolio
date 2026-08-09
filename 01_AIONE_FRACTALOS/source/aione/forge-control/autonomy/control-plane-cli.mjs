import { createControlPlaneRuntime } from "./control-plane.mjs";

const runtime = createControlPlaneRuntime();
const [command = "status", ...args] = process.argv.slice(2);

function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

try {
  let result;
  if (command === "status") result = runtime.status();
  else if (command === "audit") result = runtime.audit();
  else if (command === "record-audit") {
    const audit = runtime.audit();
    const evidence = runtime.recordEvidence({
      eventType: "capability-audit",
      action: "audit.capabilities",
      decision: "ALLOW",
      status: audit.ok ? "PASS" : "FAIL",
      proofs: [`engines:${audit.engineCount}`, `capabilities:${audit.capabilityCount}`, `waves:${audit.waveCount}`],
      metadata: { issues: audit.issues }
    });
    result = { ...audit, evidenceId: evidence.id };
  }
  else if (command === "inventory") result = runtime.inventory();
  else if (command === "lists") result = runtime.lists();
  else if (command === "evidence") result = runtime.evidence(Number(option("--limit", "100")));
  else if (command === "verify-evidence") result = runtime.verifyLedger();
  else if (command === "authorize") {
    result = runtime.authorize({
      action: option("--action"),
      targetPath: option("--target"),
      actor: option("--actor", "aione-autonomous-forge")
    });
  } else {
    throw new Error(`Commande inconnue: ${command}`);
  }
  console.log(JSON.stringify(result, null, 2));
  if (result?.ok === false) process.exitCode = 1;
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    command,
    error: error instanceof Error ? error.message : String(error)
  }, null, 2));
  process.exitCode = 1;
}
