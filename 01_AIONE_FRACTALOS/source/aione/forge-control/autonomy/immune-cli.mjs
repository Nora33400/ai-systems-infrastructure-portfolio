import { createImmuneRuntime } from "./immune-runtime.mjs";
import { createAgentCommons } from "./agent-commons.mjs";

function notifyHumanIfRequired(result) {
  const receipt = result?.repair?.receipts?.find((item) =>
    ["REQUESTED", "REQUESTED_DUPLICATE"].includes(item.status)
  );
  if (!receipt) return null;
  const commons = createAgentCommons();
  const day = String(result.completedAt || new Date().toISOString()).slice(0, 10);
  try {
    return commons.createPost({
      actor: { id: "immune-anesthetist", principalType: "AI", role: "AI_AGENT" },
      loopId: `immune:${day}:${receipt.action}:${receipt.target}`,
      channel: "HUMAN_REQUEST",
      title: `Maintenance requise : ${receipt.target}`,
      summary: "IMMUNE a terminé son diagnostic local. La correction restante exige un droit administrateur ou un redémarrage décidé par l’humain.",
      details: `Action demandée: ${receipt.action}. Cible: ${receipt.target}. Aucune destruction, élévation de permission ou publication n’a été exécutée. Demande IMMUNE: ${receipt.requestPath}`,
      audience: "OWNER",
      actions: [{ type: "YES_NO_MAYBE", label: "Autoriser la maintenance", options: ["OUI", "NON", "PEUT_ETRE"] }]
    });
  } catch (error) {
    if (["ONE_AI_POST_PER_LOOP", "AI_DAILY_POST_QUOTA"].includes(String(error?.message))) {
      return { ok: true, duplicate: true, reason: String(error.message) };
    }
    return { ok: false, reason: String(error?.message || error) };
  }
}

const runtime = createImmuneRuntime();
const [command = "status", ...args] = process.argv.slice(2);

try {
  let result;
  if (command === "status") result = { source: runtime.sourceStatus(), autoupgrade: runtime.autoupgrade() };
  else if (command === "doctor") result = await runtime.doctor();
  else if (command === "cycle") {
    result = await runtime.cycle({ applySafe: args.includes("--apply-safe") });
    result.agentCommonsNotification = notifyHumanIfRequired(result);
  }
  else if (command === "autoupgrade") result = runtime.autoupgrade({ apply: args.includes("--apply") });
  else if (command === "bootstrap") result = runtime.bootstrap();
  else throw new Error(`Commande IMMUNE inconnue: ${command}`);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result?.ok === false && !["status", "autoupgrade"].includes(command)) process.exitCode = 1;
} catch (error) {
  process.stderr.write(`${JSON.stringify({ ok: false, command, error: String(error?.message || error) })}\n`);
  process.exitCode = 1;
}
