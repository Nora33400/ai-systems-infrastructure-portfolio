import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { afterEach, test } from "node:test";
import {
  FractalCatalogError,
  SDriveFractalCatalog
} from "./s-drive-fractal-catalog.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const TEST_PARENT = testRuntimeRoot();
const temporaryRoots = [];

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) {
    const absolute = resolve(root);
    const allowedParent = resolve(TEST_PARENT);
    const delta = relative(allowedParent, absolute);
    assert.ok(delta && !delta.startsWith(".."), `Nettoyage refuse hors ${allowedParent}`);
    rmSync(absolute, { recursive: true, force: true });
  }
});

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

function createFixture() {
  const rootPath = mkdtempSync(join(TEST_PARENT, "FractalCatalogSynthetic-"));
  temporaryRoots.push(rootPath);
  const runtimeParent = join(rootPath, "AIONE", "Runtime");
  mkdirSync(runtimeParent, { recursive: true });
  for (const category of ["Programming", "Science", "Social", "Creation"]) {
    mkdirSync(join(rootPath, category), { recursive: true });
  }
  mkdirSync(join(rootPath, "Programming", "src"), { recursive: true });
  mkdirSync(join(rootPath, "Programming", "node_modules"), { recursive: true });
  mkdirSync(join(rootPath, "System Volume Information"), { recursive: true });
  writeFileSync(join(rootPath, "Programming", "README.md"), "# Programming\n", "utf8");
  writeFileSync(join(rootPath, "Programming", "package.json"), "{\"name\":\"fixture\"}\n", "utf8");
  writeFileSync(join(rootPath, "Programming", "src", "app.js"), "export const value = 1;\n", "utf8");
  writeFileSync(join(rootPath, "Programming", ".env"), "SECRET=must-not-be-read\n", "utf8");
  writeFileSync(join(rootPath, "Programming", "node_modules", "ignored.js"), "ignored\n", "utf8");
  writeFileSync(join(rootPath, "Science", "protocol.txt"), "observe\n", "utf8");
  return {
    rootPath,
    runtimePath: join(runtimeParent, "FractalCatalog")
  };
}

function sourceFiles(rootPath, runtimePath) {
  const output = {};
  function visit(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const absolute = join(directory, entry.name);
      const deltaFromRuntime = relative(runtimePath, absolute);
      const inRuntime = deltaFromRuntime === "" ||
        (!deltaFromRuntime.startsWith("..") && !deltaFromRuntime.startsWith(`..\\`));
      if (inRuntime) continue;
      if (entry.isDirectory()) visit(absolute);
      else if (entry.isFile()) {
        const bytes = readFileSync(absolute);
        output[relative(rootPath, absolute).replaceAll("\\", "/")] = {
          size: bytes.length,
          digest: sha256(bytes)
        };
      }
    }
  }
  visit(rootPath);
  return output;
}

function catalog(fixture, overrides = {}) {
  const { policy: policyOverrides = {}, ...otherOverrides } = overrides;
  return new SDriveFractalCatalog({
    ...fixture,
    clock: () => new Date("2026-07-30T16:00:00.000Z"),
    ...otherOverrides,
    policy: {
      maxDepth: 5,
      maxEntries: 1_000,
      maxEntriesPerDirectory: 100,
      contentAllowlist: ["**/README.md", "**/package.json", "**/.env"],
      ...policyOverrides
    },
    rootPath: fixture.rootPath,
    runtimePath: fixture.runtimePath
  });
}

test("catalogue la racine et chaque dossier de premier niveau sans muter la source", () => {
  const fixture = createFixture();
  const before = sourceFiles(fixture.rootPath, fixture.runtimePath);
  const system = catalog(fixture);
  const simulation = system.simulateScan();
  assert.equal(simulation.status, "READY");
  assert.equal(simulation.map.root.kind, "root");
  assert.equal(simulation.map.root.structuralRole, "CURRENT_ROOT_BRANCH");
  assert.equal(simulation.map.root.relativePath, ".");
  assert.equal(simulation.map.coherence.status, "COHERENT");
  assert.match(simulation.map.coherence.globalCoherenceFingerprint, /^[a-f0-9]{64}$/);
  const categoryNames = simulation.map.categories.map((entry) => entry.name);
  for (const expected of ["AIONE", "Creation", "Programming", "Science", "Social", "System Volume Information"]) {
    assert.ok(categoryNames.includes(expected), `Categorie absente: ${expected}`);
  }
  assert.equal(new Set(simulation.map.categories.map((entry) => entry.id)).size, simulation.map.categories.length);
  assert.ok(simulation.map.categories.every((entry) =>
    entry.parentId === simulation.map.root.id && entry.categoryId === entry.id));
  assert.ok(simulation.map.categories.every((entry) =>
    entry.structuralRole === "CATEGORY_DEFINITION" &&
    entry.coherenceStatus === "COHERENT" &&
    /^[a-f0-9]{64}$/.test(entry.localCoherenceFingerprint)));
  assert.ok(simulation.map.anchors.some((entry) =>
    entry.type === "PARENT_OF" && entry.from === simulation.map.root.id));

  const readme = simulation.map.nodes.find((entry) => entry.relativePath === "Programming/README.md");
  const packageJson = simulation.map.nodes.find((entry) => entry.relativePath === "Programming/package.json");
  const secret = simulation.map.nodes.find((entry) => entry.relativePath === "Programming/.env");
  const dependencyDirectory = simulation.map.nodes.find((entry) =>
    entry.relativePath === "Programming/node_modules");
  const protectedCategory = simulation.map.categories.find((entry) =>
    entry.name === "System Volume Information");
  assert.match(readme.contentEvidence.digest, /^[a-f0-9]{64}$/);
  assert.match(packageJson.contentEvidence.digest, /^[a-f0-9]{64}$/);
  assert.equal(Object.hasOwn(readme.contentEvidence, "content"), false);
  assert.equal(secret.contentEvidence, null);
  assert.equal(secret.policyReason, "PROTECTED_SECRET_NAME");
  assert.equal(dependencyDirectory.policyStatus, "METADATA_ONLY");
  assert.equal(
    simulation.map.nodes.some((entry) => entry.relativePath.endsWith("node_modules/ignored.js")),
    false
  );
  assert.equal(protectedCategory.policyStatus, "METADATA_ONLY");
  assert.equal(protectedCategory.policyReason, "PROTECTED_SYSTEM_DIRECTORY");
  assert.equal(simulation.map.statistics.contentFilesRead, 2);

  const committed = system.commitSimulation(simulation);
  assert.equal(committed.status, "COMMITTED");
  assert.equal(committed.revision, 1);
  const exported = system.exportMapJson();
  assert.equal(exported.status, "EXPORTED");
  assert.ok(exported.outputPath.startsWith(resolve(fixture.runtimePath)));
  assert.deepEqual(sourceFiles(fixture.rootPath, fixture.runtimePath), before);
});

test("calcule les changements incrementaux et reste idempotent a source identique", () => {
  const fixture = createFixture();
  let system = catalog(fixture);
  const first = system.simulateScan();
  assert.ok(first.changes.added.length > 0);
  assert.equal(system.commitSimulation(first).revision, 1);

  const unchanged = system.simulateScan();
  assert.equal(unchanged.status, "READY");
  assert.equal(unchanged.changes.changed, 0);
  assert.equal(system.commitSimulation(unchanged).status, "UNCHANGED");

  writeFileSync(
    join(fixture.rootPath, "Programming", "src", "app.js"),
    "export const value = 2;\nexport const added = true;\n",
    "utf8"
  );
  writeFileSync(join(fixture.rootPath, "Science", "result.txt"), "validated\n", "utf8");
  const changed = system.simulateScan();
  assert.equal(changed.status, "READY");
  assert.ok(changed.changes.modified.length >= 1);
  assert.ok(changed.changes.added.length >= 1);
  const secondCommit = system.commitSimulation(changed);
  assert.equal(secondCommit.status, "COMMITTED");
  assert.equal(secondCommit.revision, 2);

  system = catalog(fixture);
  assert.equal(system.getCurrentState().revision, 2);
  assert.equal(system.getCurrentState().map.mapFingerprint, changed.mapFingerprint);
  assert.equal(system.simulateScan().changes.changed, 0);
});

test("bloque les cycles logiques et les collisions d'ancres avant persistance", () => {
  const fixture = createFixture();
  const system = catalog(fixture);
  const cyclic = system.simulateScan({
    crossAnchors: [
      {
        id: "cross:science-programming",
        type: "DEPENDS_ON",
        fromPath: "Science",
        toPath: "Programming"
      },
      {
        id: "cross:programming-science",
        type: "DEPENDS_ON",
        fromPath: "Programming",
        toPath: "Science"
      }
    ]
  });
  assert.equal(cyclic.status, "BLOCKED");
  assert.ok(cyclic.map.issues.some((entry) => entry.code === "LOGICAL_CYCLE"));
  assert.throws(
    () => system.commitSimulation(cyclic),
    (error) => error instanceof FractalCatalogError && error.code === "SIMULATION_BLOCKED"
  );
  assert.equal(system.getCurrentState(), null);

  const collision = system.simulateScan({
    crossAnchors: [
      {
        id: "cross:duplicate",
        type: "RELATES_TO",
        fromPath: "Science",
        toPath: "Programming"
      },
      {
        id: "cross:duplicate",
        type: "RELATES_TO",
        fromPath: "Social",
        toPath: "Creation"
      }
    ]
  });
  assert.equal(collision.status, "BLOCKED");
  assert.ok(collision.map.issues.some((entry) => entry.code === "ANCHOR_ID_COLLISION"));
});

test("refuse toute lecture hors racine et tout export hors runtime", () => {
  const fixture = createFixture();
  const outside = mkdtempSync(join(TEST_PARENT, "FractalCatalogOutside-"));
  temporaryRoots.push(outside);
  writeFileSync(join(outside, "outside.txt"), "outside\n", "utf8");
  const system = catalog(fixture);
  assert.throws(
    () => system.inspectPath(join(outside, "outside.txt")),
    (error) => error instanceof FractalCatalogError && error.code === "PATH_OUTSIDE_ROOT"
  );
  assert.equal(system.inspectPath("Programming/README.md").kind, "file");
  const simulation = system.simulateScan();
  system.commitSimulation(simulation);
  assert.throws(
    () => system.exportMapJson(join(outside, "map.json")),
    (error) => error instanceof FractalCatalogError && error.code === "OUTPUT_OUTSIDE_RUNTIME"
  );
  assert.equal(existsSync(join(outside, "map.json")), false);
});

test("applique strictement les limites de contenu autorise", () => {
  const fixture = createFixture();
  const system = catalog(fixture, {
    policy: {
      maxContentFiles: 1,
      maxContentBytesPerFile: 4,
      maxTotalContentBytes: 4
    }
  });
  const simulation = system.simulateScan();
  assert.equal(simulation.status, "READY");
  assert.equal(simulation.map.statistics.contentFilesRead, 1);
  assert.equal(simulation.map.statistics.contentBytesRead, 4);
  const evidence = simulation.map.nodes.filter((entry) => entry.contentEvidence?.digest);
  assert.equal(evidence.length, 1);
  assert.equal(evidence[0].contentEvidence.bytesRead, 4);
  assert.equal(evidence[0].contentEvidence.truncated, true);
});

test("reprend depuis l'historique atomique apres crash avant current.json", () => {
  const fixture = createFixture();
  let injected = false;
  const crashing = catalog(fixture, {
    faultInjector(stage) {
      if (stage === "history-written" && !injected) {
        injected = true;
        throw new Error("simulated-catalog-crash");
      }
    }
  });
  const simulation = crashing.simulateScan();
  assert.throws(() => crashing.commitSimulation(simulation), /simulated-catalog-crash/);

  const reopened = catalog(fixture);
  const recovered = reopened.getCurrentState();
  assert.equal(recovered.revision, 1);
  assert.match(recovered.recoveredFrom, /^history\//);
  const replay = reopened.simulateScan();
  assert.equal(replay.changes.changed, 0);
  assert.equal(reopened.commitSimulation(replay).status, "UNCHANGED");
  assert.equal(readdirSync(join(fixture.runtimePath, "history")).filter((name) => name.endsWith(".json")).length, 1);
});

test("refuse de creer implicitement les parents du runtime dans la source", () => {
  const rootPath = mkdtempSync(join(TEST_PARENT, "FractalCatalogNoRuntimeParent-"));
  temporaryRoots.push(rootPath);
  const runtimePath = join(rootPath, "missing", "parent", "FractalCatalog");
  assert.throws(
    () => new SDriveFractalCatalog({ rootPath, runtimePath }),
    (error) => error instanceof FractalCatalogError && error.code === "RUNTIME_PARENT_NOT_FOUND"
  );
  assert.equal(existsSync(dirname(runtimePath)), false);
});
