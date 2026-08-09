import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, join, relative, resolve } from "node:path";
import { parse } from "yaml";
import type { AutonomyConfig, TaskRecord } from "./types.js";
import { GitManager } from "./git-manager.js";

function safeRead(path: string, maxChars: number): string {
  if (!existsSync(path)) return "[missing]";
  const content = readFileSync(path, "utf8");
  return content.length > maxChars ? `${content.slice(0, maxChars)}\n...[truncated]` : content;
}

export class ContextBuilder {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly git: GitManager,
  ) {}

  build(task: TaskRecord): string {
    const chunks: string[] = [];
    const add = (title: string, content: string): void => {
      chunks.push(`## ${title}\n\n${content}`);
    };

    add("Active task", JSON.stringify({
      id: task.id,
      title: task.title,
      module: task.module,
      description: task.description,
      dependencies: task.dependencies,
      priority: task.priority,
      status: task.status,
      acceptance: task.acceptance,
      likely_files: task.likely_files,
      source_refs: task.source_refs,
      attempts: task.attempts,
      recent_history: task.history.slice(-8),
      recent_test_results: task.test_results.slice(-16),
      recent_blockers: task.blockers.slice(-3),
    }, null, 2));

    for (const rel of task.likely_files) {
      const path = join(this.config.workspace, rel);
      add(`Likely file: ${rel}`, safeRead(path, 8000));
    }

    add("PROJECT_STATE.md", safeRead(join(this.config.workspace, "PROJECT_STATE.md"), 4000));
    add("DECISION_LOG.md", safeRead(join(this.config.workspace, "DECISION_LOG.md"), 4000));

    const registryPath = join(this.config.workspace, "MASTER_MODULE_REGISTRY.yaml");
    const registry = parse(readFileSync(registryPath, "utf8")) as {
      modules?: Array<Record<string, unknown>>;
      submodules?: Array<Record<string, unknown>>;
      protected_distinctions?: unknown;
    };
    const moduleData = registry.modules?.find((entry) => entry.id === task.module);
    const submodules = registry.submodules?.filter((entry) => entry.parent === task.module) ?? [];
    add("Relevant registry entries", JSON.stringify({
      module: moduleData ?? null,
      submodules,
      protected_distinctions: registry.protected_distinctions ?? [],
    }, null, 2));

    const graph = parse(readFileSync(join(this.config.workspace, "ARCHITECTURE_GRAPH.yaml"), "utf8")) as {
      nodes?: Array<Record<string, unknown>>;
      edges?: Array<Record<string, unknown>>;
      excluded_or_unresolved_edges?: unknown;
    };
    add("Relevant architecture graph", JSON.stringify({
      node: graph.nodes?.find((node) => node.id === task.module) ?? null,
      edges: graph.edges?.filter((edge) => edge.from === task.module || edge.to === task.module) ?? [],
      unresolved: graph.excluded_or_unresolved_edges ?? [],
    }, null, 2));

    const moduleDir = join(this.config.workspace, "modules", task.module);
    for (const name of ["README.md", "contract.yaml", "evidence.yaml", "SOURCE_RECONSTRUCTION.md"]) {
      const path = join(moduleDir, name);
      if (existsSync(path)) add(`modules/${task.module}/${name}`, safeRead(path, 5000));
    }

    add("Git snapshot", this.git.status());

    const combined = chunks.join("\n\n");
    const limit = Math.floor(this.config.limits.max_context_chars * 0.7);
    if (combined.length > limit) {
      return `${combined.slice(0, limit)}\n\n[context truncated at ${limit} characters]`;
    }
    return combined;
  }

  buildCorrection(task: TaskRecord): string {
    const targetPaths = [...new Set(task.acceptance.flatMap((criterion) => "path" in criterion ? [criterion.path] : []))];
    const targets = targetPaths.flatMap((rel) => {
      const absolute = resolve(this.config.workspace, rel);
      const relCheck = relative(this.config.workspace, absolute);
      if (isAbsolute(rel) || relCheck.startsWith("..") || isAbsolute(relCheck)) return [];
      return [`## Current target: ${rel}\n\n${safeRead(absolute, 16000)}`];
    });
    const correction = [
      "## Corrective task",
      JSON.stringify({
        id: task.id,
        title: task.title,
        description: task.description,
        acceptance: task.acceptance,
        source_refs: task.source_refs,
      }, null, 2),
      ...targets,
    ].join("\n\n");
    return correction.slice(0, Math.floor(this.config.limits.max_context_chars * 0.65));
  }

  describeFiles(task: TaskRecord): string[] {
    return task.likely_files.map((path) => relative(this.config.workspace, join(this.config.workspace, path)).replaceAll("\\", "/"));
  }
}
