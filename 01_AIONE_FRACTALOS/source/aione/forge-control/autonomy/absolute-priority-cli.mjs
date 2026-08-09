import { readAbsolutePriorityProgram } from "./absolute-priority-program.mjs";

const command = String(process.argv[2] || "status").toLowerCase();
if (command !== "status") {
  process.stderr.write("Usage: node absolute-priority-cli.mjs status\n");
  process.exitCode = 2;
} else {
  process.stdout.write(`${JSON.stringify(readAbsolutePriorityProgram(), null, 2)}\n`);
}

