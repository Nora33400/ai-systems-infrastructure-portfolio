import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import {
  createThermalContextStore,
  thermalScore,
  thermalStateForScore,
  THERMAL_STATES,
  TILE_FAMILIES,
  TILE_LEVELS
} from "./thermal-context-tiles.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function fixture() {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-thermal-tiles-"));
  const clock = { value: new Date("2026-07-30T10:00:00.000Z") };
  const store = createThermalContextStore({
    runtimeRoot: root,
    now: () => new Date(clock.value)
  });
  return {
    root,
    clock,
    store,
    cleanup: () => rmSync(root, { recursive: true, force: true })
  };
}

function input(suffix = "", overrides = {}) {
  return {
    category: "programmation-python",
    title: `Comprendre les fonctions ${suffix}`,
    subjectiveMachine: `La machine rapproche la demande ${suffix} des concepts de fonction et de portée.`,
    objectiveUser: `L'utilisateur veut écrire et tester une fonction Python ${suffix}.`,
    reconstructionCompressed: `Fonctions Python ${suffix}: intention, paramètres, résultat et test.`,
    level: "tile",
    family: "utile",
    importance: 0.5,
    confidence: 0.5,
    provenance: {
      sourceId: `session-${suffix || "base"}`,
      sourceType: "conversation",
      capturedAt: "2026-07-30T09:59:00.000Z"
    },
    ...overrides
  };
}

function expectCode(code, operation) {
  assert.throws(operation, (error) => error?.code === code);
}

test("score thermique et hystérésis couvrent COLD, WARM, HOT et BURNING", () => {
  assert.deepEqual(THERMAL_STATES, ["COLD", "WARM", "HOT", "BURNING"]);
  assert.equal(thermalStateForScore(0.2, "COLD"), "COLD");
  assert.equal(thermalStateForScore(0.4, "COLD"), "WARM");
  assert.equal(thermalStateForScore(0.65, "WARM"), "HOT");
  assert.equal(thermalStateForScore(0.85, "HOT"), "BURNING");
  assert.equal(thermalStateForScore(0.76, "BURNING"), "BURNING");
  assert.equal(thermalStateForScore(0.7, "BURNING"), "HOT");
  assert.equal(thermalStateForScore(0.56, "HOT"), "HOT");
  assert.equal(thermalStateForScore(0.5, "HOT"), "WARM");
  assert.ok(
    thermalScore(
      {
        usageCount: 20,
        lastUsedAt: "2026-07-30T10:00:00.000Z",
        importance: 1,
        confidence: 1
      },
      new Date("2026-07-30T10:00:00.000Z")
    ) > 0.9
  );
});

test("ingestion catégorisée, déduplication, niveaux et familles", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const first = fx.store.ingest(input()).tile;
  const duplicate = fx.store.ingest(input());
  assert.equal(duplicate.idempotent, true);
  assert.equal(duplicate.tile.id, first.id);
  assert.ok(TILE_LEVELS.includes(first.level));
  assert.ok(TILE_FAMILIES.includes(first.family));
  assert.match(first.tileHash, /^[a-f0-9]{64}$/);
  assert.match(first.sourceContentHash, /^[a-f0-9]{64}$/);
  assert.equal(fx.store.list({ category: "programmation-python" }).length, 1);
  const integrity = fx.store.verifyIntegrity();
  assert.deepEqual(
    { ok: integrity.ok, events: integrity.events, tiles: integrity.tiles, snapshots: integrity.snapshots },
    { ok: true, events: 1, tiles: 1, snapshots: 1 }
  );
});

test("usage, récence et importance pilotent les transitions persistées", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const cold = fx.store.ingest(
    input("-thermal", { importance: 0, confidence: 0 })
  ).tile;
  assert.equal(cold.temperature, "COLD");
  const burning = fx.store.touch(cold.id, {
    expectedRevision: cold.revision,
    weight: 100,
    importance: 1,
    confidence: 1
  }).tile;
  assert.equal(burning.temperature, "BURNING");
  fx.clock.value = new Date("2026-09-30T10:00:00.000Z");
  const refreshed = fx.store.refreshTemperatures({ at: fx.clock.value }).tiles[0];
  assert.notEqual(refreshed.temperature, "BURNING");
  assert.ok(refreshed.heatScore < burning.heatScore);
});

test("superposition par ancres et reconstruction rapide respectent les budgets", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const python = fx.store.ingest(input("-python")).tile;
  const tests = fx.store.ingest(
    input("-tests", {
      level: "kilotile",
      family: "iutile",
      subjectiveMachine: "La machine associe la fonction à des cas nominaux et limites.",
      objectiveUser: "L'utilisateur doit vérifier le résultat et les erreurs attendues."
    })
  ).tile;
  const linked = fx.store.link(python.id, tests.id, {
    relation: "validated-by",
    weight: 0.9,
    bidirectional: true,
    expectedRevision: python.revision,
    targetExpectedRevision: tests.revision
  });
  assert.equal(linked.from.anchors[0].tileId, tests.id);
  assert.equal(linked.to.anchors[0].tileId, python.id);

  const quick = fx.store.reconstruct({
    tileIds: [python.id],
    mode: "QUICK",
    includeAnchors: true,
    maxChars: 240,
    maxTokens: 60
  });
  assert.equal(quick.tileIds.length, 2);
  assert.ok(quick.usedChars <= 240);
  assert.ok(quick.estimatedTokens <= 60);
  assert.match(quick.text, /Superposition: 2/);
  assert.match(quick.reconstructionHash, /^[a-f0-9]{64}$/);

  const reflexive = fx.store.reconstruct({
    tileIds: [python.id],
    mode: "REFLEXIVE",
    includeAnchors: false,
    maxChars: 2_000,
    maxTokens: 500
  });
  assert.match(reflexive.text, /Subjectivité machine/);
  assert.match(reflexive.text, /Objectif utilisateur/);
});

test("zip/unzip logique réversible conserve la source et permet la documentation profonde", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const full = fx.store.ingest(input("-zip")).tile;
  const packed = fx.store.compact(full.id, {
    expectedRevision: full.revision,
    maxChars: 100
  }).tile;
  assert.equal(packed.contentMode, "LOGICALLY_ZIPPED");
  assert.equal(packed.subjectiveMachine, null);
  assert.ok(packed.reconstructionCompressed.length <= 100);

  const deepWhilePacked = fx.store.reconstruct({
    tileIds: [full.id],
    mode: "DEEP_DOCUMENTATION"
  });
  assert.match(deepWhilePacked.text, /La machine rapproche/);
  assert.match(deepWhilePacked.text, /L'utilisateur veut/);

  const expanded = fx.store.expand(full.id, { expectedRevision: packed.revision }).tile;
  assert.equal(expanded.contentMode, "FULL");
  assert.equal(expanded.subjectiveMachine, full.subjectiveMachine);
  assert.equal(expanded.objectiveUser, full.objectiveUser);
  assert.equal(expanded.sourceContentHash, full.sourceContentHash);
  assert.equal(fx.store.verifyIntegrity().events, 3);
});

test("intégrité, altération détectée et reprise depuis le même chemin", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const tile = fx.store.ingest(input("-resume")).tile;
  const resumed = createThermalContextStore({
    runtimeRoot: fx.root,
    now: () => new Date(fx.clock.value)
  });
  assert.equal(resumed.get(tile.id).tileHash, tile.tileHash);
  assert.equal(resumed.reconstruct({ tileIds: [tile.id] }).tileIds[0], tile.id);

  const snapshotFolder = join(
    fx.store.paths.tiles,
    "programmation-python",
    tile.temperature,
    tile.id
  );
  const snapshotPath = join(snapshotFolder, readdirSync(snapshotFolder)[0]);
  const snapshotOriginal = readFileSync(snapshotPath, "utf8");
  const snapshot = JSON.parse(snapshotOriginal);
  snapshot.tile.title = "SNAPSHOT ALTÉRÉ";
  writeFileSync(snapshotPath, JSON.stringify(snapshot), "utf8");
  expectCode("INTEGRITY_ERROR", () => resumed.verifyIntegrity());
  writeFileSync(snapshotPath, snapshotOriginal, "utf8");
  assert.equal(resumed.verifyIntegrity().ok, true);

  const lines = readFileSync(fx.store.paths.ledger, "utf8").trim().split(/\r?\n/);
  const event = JSON.parse(lines[0]);
  event.tile.objectiveUser = "CONTENU ALTÉRÉ";
  lines[0] = JSON.stringify(event);
  writeFileSync(fx.store.paths.ledger, `${lines.join("\n")}\n`, "utf8");
  expectCode("INTEGRITY_ERROR", () => resumed.get(tile.id));
});
