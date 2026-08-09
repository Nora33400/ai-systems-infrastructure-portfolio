import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  enqueueMutationProposal,
  extractMutationProposal,
  runNextIsolatedImplementation,
  runPermissionedTests,
  validateMutationProposal
} from "./isolated-implementation.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function proposal(changes, extra = {}) {
  return {
    schema: "aione.isolated-mutation-proposal.v1",
    goal: "Créer une amélioration locale petite, réversible et vérifiable.",
    confidence: 0.9,
    changes,
    testFiles: [],
    ...extra
  };
}

test("mutation contracts are parsed and unsafe paths are refused", () => {
  const markdown = [
    "## Contrat de mutation isolée",
    "```aione-mutation",
    JSON.stringify(proposal([{
      operation: "create-file",
      path: "docs/forge/generated-check.md",
      content: "# Vérification\n"
    }])),
    "```"
  ].join("\n");
  const extracted = extractMutationProposal(markdown);
  assert.equal(extracted.ok, true);
  assert.equal(validateMutationProposal(extracted.proposal).ok, true);
  assert.equal(validateMutationProposal(proposal([{
    operation: "create-file",
    path: "aione_cognitive_engine/core/cognitive_loop.py",
    content: "def run():\n    return 'bounded'\n"
  }])).ok, true);
  const noisyFence = markdown.replace(
    "```aione-mutation\n",
    "```aione-mutation contenant du JSON compact.\nSchéma exact: "
  );
  assert.equal(extractMutationProposal(noisyFence).ok, true);
  assert.equal(validateMutationProposal(proposal([{
    operation: "create-file",
    path: "../secret.txt",
    content: "non"
  }])).ok, false);
  assert.equal(validateMutationProposal(proposal([{
    operation: "create-file",
    path: "package.json",
    content: "{}"
  }])).ok, false);
});

test("fundamental autonomy guard booleans cannot be commented out or weakened", () => {
  const contract = proposal([{
    operation: "replace-fragment",
    path: "config/development-capacity.json",
    oldText: "\"isolatedCodeRunnerRequiredForFileMutation\": true",
    newText: "// \"isolatedCodeRunnerRequiredForFileMutation\": true"
  }]);
  const validation = validateMutationProposal(contract);
  assert.equal(validation.ok, false);
  assert.match(validation.errors.join(" "), /garde-fou fondamental non affaiblissable/u);
});

test("a queued proposal mutates only the S isolated workspace", () => {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-isolated-canonical-"));
  const runtimeBase = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(runtimeBase, { recursive: true });
  const runtimeRoot = mkdtempSync(join(runtimeBase, "isolated-implementation-"));
  try {
    mkdirSync(join(root, "forge-control", "autonomy"), { recursive: true });
    mkdirSync(join(root, "docs", "forge"), { recursive: true });
    mkdirSync(join(root, "config"), { recursive: true });
    writeFileSync(join(root, "package.json"), "{\"type\":\"module\"}\n", "utf8");
    writeFileSync(join(root, "AGENTS.md"), "# règles\n", "utf8");
    writeFileSync(join(root, "docs", "forge", "source.md"), "# Source\nancienne valeur\n", "utf8");
    const mutation = proposal([{
      operation: "replace-fragment",
      path: "docs/forge/source.md",
      oldText: "ancienne valeur",
      newText: "nouvelle valeur testée dans le bac à sable"
    }]);
    const markdown = `\`\`\`aione-mutation\n${JSON.stringify(mutation)}\n\`\`\``;
    const queued = enqueueMutationProposal({
      runtimeRoot,
      manifestPath: join(runtimeRoot, "manifest.json"),
      markdown,
      packageId: "PKG-001",
      laneId: "test-lane"
    });
    assert.equal(queued.ok, true);
    const result = runNextIsolatedImplementation({ canonicalRoot: root, runtimeRoot });
    assert.equal(result.ok, true);
    assert.equal(result.status, "STATIC_VALIDATED_ISOLATED");
    assert.equal(result.canonicalMutationPerformed, false);
    assert.equal(result.isolatedMutationPerformed, true);
    assert.equal(result.humanReviewRequired, false);
    assert.equal(result.autonomousContinuation, true);
    assert.equal(result.isolatedRetentionDecision, "AUTO_KEEP_IF_VALIDATED");
    assert.equal(result.canonicalPromotionDecision, "ASK_OWNER");
    assert.match(readFileSync(join(root, "docs", "forge", "source.md"), "utf8"), /ancienne valeur/);
    assert.match(readFileSync(join(result.workspace, "docs", "forge", "source.md"), "utf8"), /nouvelle valeur/);
    assert.equal(existsSync(join(runtimeRoot, "isolated-implementation-state.json")), true);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(runtimeRoot, { recursive: true, force: true });
  }
});

test("create-file never overwrites an existing workspace file", () => {
  const contract = proposal([{
    operation: "create-file",
    path: "docs/forge/existing.md",
    content: "# Nouveau\n"
  }]);
  assert.equal(validateMutationProposal(contract).ok, true);
});

test("Node tests run with filesystem, network and child-process permissions denied by default", () => {
  const runtimeBase = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(runtimeBase, { recursive: true });
  const workspace = mkdtempSync(join(runtimeBase, "permission-workspace-"));
  const tempRoot = join(workspace, ".test-temp");
  try {
    writeFileSync(join(workspace, "safe.test.mjs"), [
      "import test from 'node:test';",
      "import assert from 'node:assert/strict';",
      "test('isolated', () => assert.equal(2 + 2, 4));"
    ].join("\n"), "utf8");
    const results = runPermissionedTests(workspace, ["safe.test.mjs"], tempRoot);
    assert.equal(results.length, 1);
    assert.equal(results[0].ok, true, results[0].stderr);
    assert.match(results[0].command, /--permission/);
  } finally {
    rmSync(workspace, { recursive: true, force: true });
  }
});

test("invalid Python is rejected by syntax validation before review", () => {
  const base = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(base, { recursive: true });
  const root = mkdtempSync(join(base, "python-canonical-"));
  const runtimeRoot = mkdtempSync(join(base, "python-runtime-"));
  try {
    mkdirSync(join(root, "forge-control"), { recursive: true });
    mkdirSync(join(root, "config"), { recursive: true });
    writeFileSync(join(root, "package.json"), "{\"type\":\"module\"}\n", "utf8");
    writeFileSync(join(root, "AGENTS.md"), "# règles\n", "utf8");
    const mutation = proposal([{
      operation: "create-file",
      path: "src/broken.py",
      content: "def broken(:\n    pass\n"
    }]);
    const queued = enqueueMutationProposal({
      runtimeRoot,
      manifestPath: join(runtimeRoot, "manifest.json"),
      markdown: `\`\`\`aione-mutation\n${JSON.stringify(mutation)}\n\`\`\``,
      packageId: "PY-BROKEN",
      laneId: "test-lane"
    });
    assert.equal(queued.ok, true);
    const result = runNextIsolatedImplementation({ canonicalRoot: root, runtimeRoot });
    assert.equal(result.ok, false);
    assert.equal(result.status, "FAILED_ISOLATED_VALIDATION");
    assert.equal(result.staticValidation[0].ok, false);
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("only one contract may claim the same canonical target at a time", () => {
  const base = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(base, { recursive: true });
  const root = mkdtempSync(join(base, "dedupe-canonical-"));
  const runtimeRoot = mkdtempSync(join(base, "dedupe-runtime-"));
  try {
    mkdirSync(join(root, "docs"), { recursive: true });
    const mutation = proposal([{
      operation: "create-file",
      path: "docs/same-target.md",
      content: "# Première option\n"
    }]);
    const markdown = `\`\`\`aione-mutation\n${JSON.stringify(mutation)}\n\`\`\``;
    const first = enqueueMutationProposal({
      runtimeRoot,
      canonicalRoot: root,
      manifestPath: join(runtimeRoot, "one.json"),
      markdown,
      packageId: "DEDUPE-ONE",
      laneId: "lane-a"
    });
    const second = enqueueMutationProposal({
      runtimeRoot,
      canonicalRoot: root,
      manifestPath: join(runtimeRoot, "two.json"),
      markdown,
      packageId: "DEDUPE-TWO",
      laneId: "lane-b"
    });
    assert.equal(first.ok, true);
    assert.equal(second.ok, false);
    assert.equal(second.status, "DUPLICATE_TARGET_CONTRACT");
    assert.equal(second.existingPackageId, "DEDUPE-ONE");
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("an absent replace target is repaired into an isolated create and invalid model test hints are ignored", () => {
  const base = "S:\\AI_LAB\\Runtime\\Tests";
  mkdirSync(base, { recursive: true });
  const root = mkdtempSync(join(base, "repair-canonical-"));
  const runtimeRoot = mkdtempSync(join(base, "repair-runtime-"));
  try {
    mkdirSync(join(root, "config"), { recursive: true });
    writeFileSync(join(root, "package.json"), "{\"type\":\"module\"}\n", "utf8");
    const mutation = {
      schema: "aione.isolated-mutation-proposal.v1",
      goal: "Créer un prototype absent dans le seul workspace isolé.",
      confidence: 0.9,
      changes: [{
        operation: "replace-fragment",
        path: "aione_cognitive_engine/experiments/new-choice.mjs",
        oldText: "// TODO",
        newText: "export const choice = 'local';\n"
      }],
      testFiles: [{ path: "tests/invented.test.mjs" }]
    };
    const queued = enqueueMutationProposal({
      runtimeRoot,
      canonicalRoot: root,
      manifestPath: join(runtimeRoot, "manifest.json"),
      markdown: `\`\`\`aione-mutation\n${JSON.stringify(mutation)}\n\`\`\``,
      packageId: "REPAIRED-CONTRACT",
      laneId: "test-lane"
    });
    assert.equal(queued.ok, true);
    assert.deepEqual(queued.automaticRepairs, ["replace-fragment→create-file:aione_cognitive_engine/experiments/new-choice.mjs"]);
    assert.equal(queued.warnings.length, 1);
    const result = runNextIsolatedImplementation({ canonicalRoot: root, runtimeRoot });
    assert.equal(result.ok, true);
    assert.equal(result.changedFiles[0].path, "aione_cognitive_engine/experiments/new-choice.mjs");
  } finally {
    rmSync(runtimeRoot, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});
