import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parse } from "yaml";

export interface DocumentationValidation {
  yaml_files: number;
  json_files: number;
  markdown_files: number;
  module_contracts: number;
  issues: string[];
}

const SKIP = new Set([".git", "node_modules", "state", "logs", "dist"]);

function walk(root: string): string[] {
  const files: string[] = [];
  const visit = (directory: string): void => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.isDirectory() && SKIP.has(entry.name)) continue;
      const path = join(directory, entry.name);
      if (entry.isDirectory()) visit(path);
      else files.push(path);
    }
  };
  visit(root);
  return files;
}

export function validateDocumentation(workspaceInput: string): DocumentationValidation {
  const workspace = resolve(workspaceInput);
  const files = walk(workspace);
  const yamlFiles = files.filter((path) => /\.ya?ml$/i.test(path));
  const jsonFiles = files.filter((path) => /\.json$/i.test(path) && path !== join(workspace, "package-lock.json"));
  const markdownFiles = files.filter((path) => /\.md$/i.test(path));
  const issues: string[] = [];
  const parsed = new Map<string, unknown>();

  for (const path of yamlFiles) {
    try { parsed.set(path, parse(readFileSync(path, "utf8"))); }
    catch (error) { issues.push("YAML " + relative(workspace, path) + ": " + (error instanceof Error ? error.message : String(error))); }
  }
  for (const path of jsonFiles) {
    try { parsed.set(path, JSON.parse(readFileSync(path, "utf8"))); }
    catch (error) { issues.push("JSON " + relative(workspace, path) + ": " + (error instanceof Error ? error.message : String(error))); }
  }

  const ajv = new Ajv2020({ allErrors: true, strict: false });
  const moduleSchemaPath = join(workspace, "schemas", "module-contract.schema.json");
  const moduleSchema = parsed.get(moduleSchemaPath) as Record<string, unknown> | undefined;
  let moduleContracts = 0;
  if (moduleSchema) {
    const validate = ajv.compile(moduleSchema);
    const modulesDir = join(workspace, "modules");
    for (const moduleEntry of readdirSync(modulesDir, { withFileTypes: true }).filter((entry) => entry.isDirectory())) {
      const contractPath = join(modulesDir, moduleEntry.name, "contract.yaml");
      if (!existsSync(contractPath)) {
        issues.push("Missing module contract: modules/" + moduleEntry.name + "/contract.yaml");
        continue;
      }
      moduleContracts += 1;
      const value = parsed.get(contractPath);
      if (!validate(value)) issues.push("SCHEMA " + relative(workspace, contractPath) + ": " + ajv.errorsText(validate.errors));
    }
  }

  const manifestPath = join(workspace, "SOURCE_MANIFEST.yaml");
  const manifest = parsed.get(manifestPath) as { sources?: Array<Record<string, unknown>> } | undefined;
  const sourceIds = new Set<string>();
  for (const source of manifest?.sources ?? []) {
    const id = typeof source.id === "string" ? source.id : "";
    sourceIds.add(id);
    const sourcePath = typeof source.path === "string" ? join(workspace, source.path) : "";
    if (!sourcePath || !existsSync(sourcePath)) {
      issues.push("Missing source for " + id);
      continue;
    }
    const digest = createHash("sha256").update(readFileSync(sourcePath)).digest("hex");
    if (digest !== source.repository_sha256) issues.push("Source hash mismatch: " + id);
    const sourceText = readFileSync(sourcePath, "utf8");
    const splitLines = sourceText.split(/\r?\n/);
    const lineCount = sourceText.endsWith("\n") ? splitLines.length - 1 : splitLines.length;
    if (lineCount !== source.line_count) issues.push("Source line count mismatch: " + id);
  }

  for (const path of yamlFiles) {
    const content = readFileSync(path, "utf8");
    for (const match of content.matchAll(/\bSRC-\d{4}\b/g)) {
      if (!sourceIds.has(match[0])) issues.push("Unknown source ref " + match[0] + " in " + relative(workspace, path));
    }
  }

  const architecturePath = join(workspace, "ARCHITECTURE_GRAPH.yaml");
  const graph = parsed.get(architecturePath) as { nodes?: Array<{ id?: string }>; edges?: Array<{ id?: string; from?: string; to?: string }> } | undefined;
  const nodeIds = new Set((graph?.nodes ?? []).map((node) => node.id).filter((id): id is string => Boolean(id)));
  for (const edge of graph?.edges ?? []) {
    if (!edge.from || !nodeIds.has(edge.from) || !edge.to || !nodeIds.has(edge.to)) {
      issues.push("Architecture edge has missing endpoint: " + (edge.id ?? "<unknown>"));
    }
  }

  const linkPattern = /\[[^\]]+\]\(([^)]+)\)/g;
  for (const path of markdownFiles) {
    const content = readFileSync(path, "utf8");
    for (const match of content.matchAll(linkPattern)) {
      const target = match[1];
      if (!target || target.includes("://") || target.startsWith("#")) continue;
      const withoutAnchor = target.split("#", 1)[0];
      if (withoutAnchor && !existsSync(resolve(join(path, ".."), withoutAnchor))) {
        issues.push("Broken link " + relative(workspace, path) + " -> " + target);
      }
    }
  }

  return {
    yaml_files: yamlFiles.length,
    json_files: jsonFiles.length,
    markdown_files: markdownFiles.length,
    module_contracts: moduleContracts,
    issues,
  };
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === invokedPath) {
  const result = validateDocumentation(process.cwd());
  console.log(JSON.stringify(result, null, 2));
  if (result.issues.length > 0) process.exitCode = 1;
}
