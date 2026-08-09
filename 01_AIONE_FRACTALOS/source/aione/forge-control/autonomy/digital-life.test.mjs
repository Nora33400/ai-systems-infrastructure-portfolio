import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DigitalLifeRuntime } from "./digital-life.mjs";
import { AgentAutomationRunner } from "./automation-runner.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function fixtures(root) {
  const digitalPath = join(root, "digital-life.json");
  const portfolioPath = join(root, "portfolio.json");
  const automationsPath = join(root, "automations.json");
  writeJson(digitalPath, {
    storage: join(root, "digital-state"),
    privacy: {localOnly: true, retentionDays: 90, externalActionsDefault: "deny"},
    notifications: {dailyBriefAt: "08:00", reminderLeadMinutes: [30, 5]},
    studios: [
      {id: "development", name: "Développement", status: "ACTIVE_GUARDED", lead: "aione-architect", model: "m14", authority: "CODE_ALLOWLISTED"}
    ],
    proposedMeetings: [
      {id: "RDV-1", date: "2026-07-27", start: "09:00", durationMinutes: 30, studio: "development", status: "PROPOSED"}
    ],
    routines: [
      {id: "RT-1", days: ["MO"], time: "10:25", title: "Pause", body: "Bouger.", status: "ACTIVE"}
    ]
  });
  writeJson(portfolioPath, {
    projects: [{id: "aione", name: "AIONE", category: "CURRENT"}]
  });
  writeJson(automationsPath, {
    outputDir: join(root, "runs"),
    automations: [{
      id: "prepare",
      agent: "aione-architect",
      model: "m14",
      mode: "LOCAL_MODEL_ONLY",
      arguments: {studio: {type: "studio", required: true}, horizon: {type: "enum", values: ["7d", "30d"], default: "30d"}},
      prompt: "Studio {studio}, horizon {horizon}"
    }]
  });
  return {digitalPath, portfolioPath, automationsPath};
}

test("digital secretary prepares a brief, requires confirmation, and deduplicates reminders", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-digital-life-"));
  try {
    const files = fixtures(root);
    let now = new Date(2026, 6, 27, 8, 5, 0, 0);
    const runtime = new DigitalLifeRuntime({
      root,
      configPath: files.digitalPath,
      portfolioPath: files.portfolioPath,
      stateDir: join(root, "state"),
      clock: () => now
    });
    const brief = runtime.dailyBrief("2026-07-27");
    assert.equal(brief.proposed, 1);
    assert.match(readFileSync(brief.path, "utf8"), /rendez-vous restent à valider/);
    assert.equal(runtime.claimDueReminders().length, 0);
    runtime.setMeetingStatus("RDV-1", "CONFIRMED");
    now = new Date(2026, 6, 27, 8, 30, 0, 0);
    assert.equal(runtime.claimDueReminders().length, 1);
    assert.equal(runtime.claimDueReminders().length, 0);
    now = new Date(2026, 6, 27, 10, 25, 0, 0);
    assert.equal(runtime.claimDueReminders()[0].routineId, "RT-1");
    assert.equal(runtime.claimDueReminders().length, 0);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("daily brief notification is claimed once and not before configured time", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-brief-"));
  try {
    const files = fixtures(root);
    let now = new Date(2026, 6, 27, 7, 55, 0, 0);
    const runtime = new DigitalLifeRuntime({
      root,
      configPath: files.digitalPath,
      portfolioPath: files.portfolioPath,
      stateDir: join(root, "state"),
      clock: () => now
    });
    assert.equal(runtime.claimBriefNotification("2026-07-27").claimed, false);
    now = new Date(2026, 6, 27, 8, 1, 0, 0);
    assert.equal(runtime.claimBriefNotification("2026-07-27").claimed, true);
    assert.equal(runtime.claimBriefNotification("2026-07-27").claimed, false);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});

test("parameterized automations reject unknown arguments and persist local results", async () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-automation-"));
  try {
    const files = fixtures(root);
    const runner = new AgentAutomationRunner({
      root,
      configPath: files.automationsPath,
      portfolioPath: files.portfolioPath,
      digitalLifePath: files.digitalPath,
      outputDir: join(root, "runs"),
      clock: () => new Date("2026-07-27T06:00:00.000Z"),
      localModelRunner: async ({prompt}) => `OK: ${prompt}`
    });
    assert.throws(() => runner.prepare("prepare", {studio: "development", shell: "rm"}), /non déclarés/);
    const result = await runner.run("prepare", {studio: "development", horizon: "7d"});
    assert.equal(result.executed, true);
    assert.equal(result.externalActions, "DENIED");
    assert.match(readFileSync(result.markdownPath, "utf8"), /OK: Studio development/);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
