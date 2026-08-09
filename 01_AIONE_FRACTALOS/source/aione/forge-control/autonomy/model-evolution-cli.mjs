import { readModelEvolutionHandoffStatus, writeModelEvolutionHandoff } from "./model-evolution-handoff.mjs";

const command = String(process.argv[2] || "status").toLowerCase();
if (command === "handoff") {
  process.stdout.write(`${JSON.stringify(writeModelEvolutionHandoff(), null, 2)}\n`);
} else if (command === "status") {
  process.stdout.write(`${JSON.stringify(readModelEvolutionHandoffStatus(), null, 2)}\n`);
} else {
  process.stderr.write("Usage: node model-evolution-cli.mjs status|handoff\n");
  process.exitCode = 2;
}
