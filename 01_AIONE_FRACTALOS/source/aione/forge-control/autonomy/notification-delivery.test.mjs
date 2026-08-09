import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const notifier = join(root, "scripts", "show-aione-notification.ps1");

function invokeToast(actionUrl) {
  return spawnSync("powershell.exe", [
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",
    "-File", notifier,
    "-Title", "AIONE test",
    "-Body", "Validation sans toast réel",
    "-ActionUrl", actionUrl,
    "-ActionsJson", JSON.stringify([{ label: "OUI", url: actionUrl }]),
    "-DryRun"
  ], { cwd: root, encoding: "utf8", windowsHide: true, timeout: 30_000 });
}

test("Windows toast uses loopback first and keeps Tailscale only as HTTPS fallback", () => {
  const config = JSON.parse(readFileSync(join(root, "config", "agent-commons.json"), "utf8"));
  assert.equal(config.transports.windowsToast.loopbackFirst, true);
  assert.match(config.transports.windowsToast.url, /^http:\/\/127\.0\.0\.1:4310\//u);
  assert.match(config.transports.windowsToast.fallbackUrl, /^https:\/\//u);
});

test("toast action validation accepts loopback HTTP and rejects external HTTP", () => {
  const local = invokeToast("http://127.0.0.1:4310/agents-space.html?request=test&action=OUI");
  assert.equal(local.status, 0, `${local.stdout}\n${local.stderr}`);
  assert.match(local.stdout, /ActionCount\s*:\s*1/u);
  assert.match(local.stdout, /127\.0\.0\.1:4310/u);

  const unsafe = invokeToast("http://example.com/unsafe");
  assert.notEqual(unsafe.status, 0);
  assert.match(`${unsafe.stdout}\n${unsafe.stderr}`, /HTTPS ou HTTP loopback uniquement/u);
});

test("notification landing page exposes a visible guarded confirmation", () => {
  const html = readFileSync(join(root, "forge-control", "web", "agents-space.html"), "utf8");
  const script = readFileSync(join(root, "forge-control", "web", "agents-space.js"), "utf8");
  const worker = readFileSync(join(root, "forge-control", "web", "agent-space-sw.js"), "utf8");
  assert.match(html, /notificationActionBanner/u);
  assert.match(script, /focusNotificationAction/u);
  assert.match(script, /clique une seconde fois pour confirmer/u);
  assert.match(script, /"Notification" in window/u);
  assert.match(script, /localStorage\.removeItem/u);
  assert.match(worker, /self\.location\.origin/u);
  assert.match(worker, /skipWaiting/u);
  assert.match(worker, /needs-confirmation/u);
});
