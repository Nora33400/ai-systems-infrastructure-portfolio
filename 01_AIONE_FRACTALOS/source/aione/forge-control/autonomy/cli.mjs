import { createAutonomyRuntime } from "./runtime.mjs";

const runtime = createAutonomyRuntime();
const [command = "status", ...args] = process.argv.slice(2);

function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

try {
  let result;
  if (command === "status") {
    result = runtime.status();
  } else if (command === "audit") {
    result = await runtime.audit();
  } else if (command === "cycle") {
    result = await runtime.runCycle({ executeTasks: !args.includes("--health-only") });
  } else if (command === "incidents") {
    result = runtime.listIncidents();
  } else if (command === "compact") {
    result = runtime.memory.compact();
  } else if (command === "refill-backlog") {
    result = runtime.runBacklogRefillGuarded();
  } else if (command === "backup") {
    result = runtime.createBackup();
  } else if (command === "verify-backup") {
    const path = option("--path");
    if (!path) throw new Error("Option requise: --path <backup>");
    result = runtime.verifyBackup(path);
  } else if (command === "restore-test") {
    const path = option("--path");
    if (!path) throw new Error("Option requise: --path <backup>");
    result = runtime.testRestore(path);
  } else if (command === "enqueue") {
    result = runtime.enqueue({
      type: option("--type", "plan"),
      title: option("--title", "Tâche locale AIONE"),
      projectId: option("--project", "aione"),
      risk: option("--risk", "low")
    });
  } else {
    throw new Error(`Commande inconnue: ${command}`);
  }
  console.log(JSON.stringify(result, null, 2));
  if (result && result.ok === false && command !== "status") process.exitCode = 1;
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    command,
    error: error instanceof Error ? error.message : String(error)
  }, null, 2));
  process.exitCode = 1;
}
