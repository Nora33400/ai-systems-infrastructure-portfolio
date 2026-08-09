import { createDigitalLifeRuntime } from "./digital-life.mjs";

const runtime = createDigitalLifeRuntime();
const [command = "status", ...args] = process.argv.slice(2);

function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

try {
  let result;
  if (command === "status") {
    result = runtime.status();
  } else if (command === "brief") {
    result = runtime.dailyBrief(option("--date") || undefined);
  } else if (command === "brief-notification") {
    result = runtime.claimBriefNotification(option("--date") || undefined);
  } else if (command === "meeting-plan") {
    result = runtime.prepareMeeting(option("--studio"), option("--horizon", "30d"));
  } else if (command === "meeting-status") {
    result = runtime.setMeetingStatus(option("--id"), option("--status"));
  } else if (command === "reminders") {
    result = runtime.claimDueReminders();
  } else {
    throw new Error(`Commande inconnue: ${command}`);
  }
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    command,
    error: error instanceof Error ? error.message : String(error)
  }, null, 2));
  process.exitCode = 1;
}
