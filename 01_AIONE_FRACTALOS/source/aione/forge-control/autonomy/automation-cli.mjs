import { AgentAutomationRunner } from "./automation-runner.mjs";

const runner = new AgentAutomationRunner();
const [command = "list", automationId = "", ...args] = process.argv.slice(2);

function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

try {
  let result;
  if (command === "list") {
    result = runner.list();
  } else if (command === "preview" || command === "run") {
    const raw = option("--args-json", "{}");
    const supplied = JSON.parse(raw);
    result = await runner.run(automationId, supplied, {execute: command === "run"});
  } else {
    throw new Error(`Commande inconnue: ${command}`);
  }
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    command,
    automationId,
    error: error instanceof Error ? error.message : String(error)
  }, null, 2));
  process.exitCode = 1;
}
