import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  applyIsolatedModelProposal,
  buildDocumentationFallbackContract,
  inspectQueueCapabilities
} from "./forge-queue-capabilities.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

test("write-approved is eligible only as an isolated mutation", () => {
  const result = inspectQueueCapabilities({ requiredCapabilities: ["read", "write-approved", "test"] });
  assert.equal(result.eligible, true);
  assert.equal(result.mutationRequested, true);
  assert.equal(result.documentationOnly, false);
  assert.equal(result.reason, "eligible-isolated-mutation-worker");
  assert.equal(inspectQueueCapabilities({ requiredCapabilities: ["admin"] }).eligible, false);
  assert.equal(inspectQueueCapabilities({ requiredCapabilities: ["read", "docs.write-approved"] }).documentationOnly, true);
});

test("documentation-only capability cannot mutate config or code even in isolation", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-doc-scope-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "config"), { recursive: true });
  writeFileSync(join(workspace, "config", "safe.json"), "{\"enabled\":true}\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Tenter une mutation hors permission documentation.","confidence":0.9,"changes":[{"operation":"replace-fragment","path":"config/safe.json","oldText":"true","newText":"false"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes: ["docs/"] });
  assert.equal(result.status, "INVALID_CAPABILITY_SCOPE");
  assert.equal(readFileSync(join(workspace, "config", "safe.json"), "utf8"), "{\"enabled\":true}\n");
});

test("an empty replacement anchor becomes create-file only when the bounded target is absent", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-create-intent-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Documenter le déblocage autonome sécurisé dans un nouveau fichier.","confidence":0.9,"changes":[{"operation":"replace-fragment","path":"docs/SECURITY.md","oldText":"","newText":"# Sécurité\\n\\nPreuve locale bornée.\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes: ["docs/"] });
  assert.equal(result.ok, true);
  assert.equal(result.proposal.changes[0].operation, "create-file");
  assert.equal(readFileSync(join(workspace, "docs", "SECURITY.md"), "utf8"), "# Sécurité\n\nPreuve locale bornée.\n");
  assert.ok(result.warnings.some((warning) => /converti en create-file/u.test(warning)));
});

test("an empty replacement anchor stays rejected when its target already exists", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-empty-anchor-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "docs"), { recursive: true });
  writeFileSync(join(workspace, "docs", "SECURITY.md"), "# Existant\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Ne jamais écraser implicitement une documentation existante.","confidence":0.9,"changes":[{"operation":"replace-fragment","path":"docs/SECURITY.md","oldText":"","newText":"# Remplacement interdit\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes: ["docs/"] });
  assert.equal(result.ok, false);
  assert.equal(result.status, "INVALID_CONTRACT");
  assert.equal(readFileSync(join(workspace, "docs", "SECURITY.md"), "utf8"), "# Existant\n");
});

test("documentation fallback records a refused model contract without widening permissions", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-doc-fallback-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  const markdown = buildDocumentationFallbackContract({
    id: "TASK-P0/unsafe",
    title: "Réparation `bornée` <locale>"
  }, {
    status: "INVALID_CAPABILITY_SCOPE"
  });
  const result = applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes: ["docs/"] });
  assert.equal(result.ok, true);
  assert.equal(result.proposal.changes.length, 1);
  assert.match(result.proposal.changes[0].path, /^docs\/forge\/reviews\//u);
  assert.doesNotMatch(result.proposal.changes[0].content, /<locale>|`bornée`/u);
  assert.match(result.proposal.changes[0].content, /Aucune mutation canonique/u);
  assert.equal(existsSync(join(workspace, "config")), false);
});

test("documentation-only output cannot claim a blockage is fixed without operational evidence", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-doc-overclaim-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Refuser une affirmation de résolution documentaire non démontrée.","confidence":0.9,"changes":[{"operation":"create-file","path":"docs/repair.md","content":"Le blocage critique a été corrigé automatiquement.\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes: ["docs/"] });
  assert.equal(result.ok, false);
  assert.equal(result.status, "UNSUPPORTED_DOCUMENTATION_CLAIM");
  assert.equal(existsSync(join(workspace, "docs", "repair.md")), false);
});

test("validated model contract changes only the isolated workspace", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-mutation-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "docs", "forge"), { recursive: true });
  writeFileSync(join(workspace, "docs", "forge", "existing.md"), "avant\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Tester une mutation strictement isolée et réversible.","confidence":0.91,"changes":[{"operation":"replace-fragment","path":"docs/forge/existing.md","oldText":"avant\\n","newText":"après\\n"},{"operation":"create-file","path":"docs/forge/new-proof.md","content":"preuve locale\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace });
  assert.equal(result.ok, true);
  assert.deepEqual(result.changedFiles.map((item) => item.path).sort(), ["docs/forge/existing.md", "docs/forge/new-proof.md"]);
  assert.equal(readFileSync(join(workspace, "docs", "forge", "existing.md"), "utf8"), "après\n");
});

test("unsafe or missing mutation contracts remain rejected", () => {
  assert.equal(applyIsolatedModelProposal({ markdown: "audit seulement", workspace: testRuntimeRoot() }).status, "NO_CONTRACT");
  const unsafe = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Tenter une sortie de périmètre interdite.","confidence":0.99,"changes":[{"operation":"create-file","path":"../outside.md","content":"non"}],"testFiles":[]}
\`\`\``;
  assert.equal(applyIsolatedModelProposal({ markdown: unsafe, workspace: testRuntimeRoot() }).status, "INVALID_CONTRACT");
});

test("a stale replacement anchor is returned as a repairable preflight rejection", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-stale-anchor-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "docs", "forge"), { recursive: true });
  writeFileSync(join(workspace, "docs", "forge", "existing.md"), "contenu actuel\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Refuser proprement un ancrage devenu obsolète.","confidence":0.91,"changes":[{"operation":"replace-fragment","path":"docs/forge/existing.md","oldText":"contenu ancien\\n","newText":"contenu corrigé\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace });
  assert.equal(result.ok, false);
  assert.equal(result.status, "APPLY_PREFLIGHT_REJECTED");
  assert.match(result.errors[0], /trouvé=0/);
  assert.equal(result.proposal.changes[0].path, "docs/forge/existing.md");
  assert.equal(readFileSync(join(workspace, "docs", "forge", "existing.md"), "utf8"), "contenu actuel\n");
});

test("a rejected multi-file contract leaves no partial mutation", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-transactional-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "docs", "forge"), { recursive: true });
  writeFileSync(join(workspace, "docs", "forge", "existing.md"), "stable\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Garantir un préflight transactionnel avant toute écriture.","confidence":0.94,"changes":[{"operation":"create-file","path":"docs/forge/partial.md","content":"ne doit pas être créé\\n"},{"operation":"replace-fragment","path":"docs/forge/existing.md","oldText":"absent\\n","newText":"nouveau\\n"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace });
  assert.equal(result.status, "APPLY_PREFLIGHT_REJECTED");
  assert.equal(existsSync(join(workspace, "docs", "forge", "partial.md")), false);
  assert.equal(readFileSync(join(workspace, "docs", "forge", "existing.md"), "utf8"), "stable\n");
});

test("invalid model-suggested tests are dropped while mandatory Forge tests remain authoritative", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-test-hint-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Documenter une amélioration locale sans exécuter un test inventé.","confidence":0.9,"changes":[{"operation":"create-file","path":"docs/forge/model-test-hint.md","content":"preuve locale\\n"}],"testFiles":[{"path":"tests/invente.test.mjs","content":"non fiable"},"tests/absent.test.mjs"]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace });
  assert.equal(result.ok, true);
  assert.deepEqual(result.proposal.testFiles, []);
  assert.ok(result.warnings.some((warning) => /suggestion ignorée/u.test(warning)));
  assert.ok(result.warnings.some((warning) => /fichier inexistant ignoré/u.test(warning)));
});

test("invalid JSON is rejected transactionally and restored before contract repair", (context) => {
  const workspace = mkdtempSync(join(testRuntimeRoot(), "aione-forge-worker-json-rollback-"));
  context.after(() => rmSync(workspace, { recursive: true, force: true }));
  mkdirSync(join(workspace, "config"), { recursive: true });
  writeFileSync(join(workspace, "config", "safe.json"), "{\"enabled\":true}\n", "utf8");
  const markdown = `\`\`\`aione-mutation
{"schema":"aione.isolated-mutation-proposal.v1","goal":"Refuser un JSON invalide sans laisser de mutation partielle.","confidence":0.9,"changes":[{"operation":"replace-fragment","path":"config/safe.json","oldText":"{\\\"enabled\\\":true}","newText":"// {\\\"enabled\\\":true}"}],"testFiles":[]}
\`\`\``;
  const result = applyIsolatedModelProposal({ markdown, workspace });
  assert.equal(result.status, "STATIC_VALIDATION_REJECTED");
  assert.equal(readFileSync(join(workspace, "config", "safe.json"), "utf8"), "{\"enabled\":true}\n");
  assert.equal(result.staticValidation[0].ok, false);
});
