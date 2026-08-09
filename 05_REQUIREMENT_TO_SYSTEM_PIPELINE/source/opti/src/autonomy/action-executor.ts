import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { relative, resolve } from "node:path";
import type { ActionObservation, AgentAction, AutonomyConfig } from "./types.js";
import { SecurityPolicy } from "./security-policy.js";
import { CommandExecutor } from "./command-executor.js";
import { GitManager } from "./git-manager.js";
import { RecoveryManager } from "./recovery-manager.js";
import { EventLogger } from "./event-logger.js";
import { WorkspaceWriter } from "./workspace-writer.js";

const SKIP_DIRECTORIES = new Set([".git", "node_modules", "state", "logs", "dist"]);

export class ActionExecutor {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly policy: SecurityPolicy,
    private readonly commands: CommandExecutor,
    private readonly git: GitManager,
    private readonly recovery: RecoveryManager,
    private readonly logger: EventLogger,
    private readonly writer: WorkspaceWriter,
  ) {}

  async execute(action: AgentAction, taskId: string, workspaceRoot = this.config.workspace): Promise<ActionObservation> {
    try {
      const observation = await this.executeUnsafe(action, taskId, workspaceRoot);
      this.logger.log("action_accepted", { action: action.action, summary: observation.summary }, { taskId });
      return observation;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.logger.log("action_refused", { action: action.action, error: message }, { taskId, level: "warn" });
      return { ok: false, action: action.action, summary: message };
    }
  }

  private async executeUnsafe(action: AgentAction, taskId: string, workspaceRoot: string): Promise<ActionObservation> {
    const isolated = resolve(workspaceRoot) !== resolve(this.config.workspace);
    switch (action.action) {
      case "list_directory": {
        const path = this.policy.resolveReadPathAt(workspaceRoot, action.path);
        if (!statSync(path).isDirectory()) throw new Error("list_directory requires a directory.");
        const results: string[] = [];
        const walk = (directory: string): void => {
          for (const entry of readdirSync(directory, { withFileTypes: true })) {
            if (SKIP_DIRECTORIES.has(entry.name)) continue;
            const full = `${directory}/${entry.name}`;
            results.push(relative(workspaceRoot, full).replaceAll("\\", "/"));
            if (action.recursive && entry.isDirectory() && results.length < 500) walk(full);
            if (results.length >= 500) return;
          }
        };
        walk(path);
        return { ok: true, action: action.action, summary: `${results.length} entries`, data: results };
      }
      case "read_file": {
        const path = this.policy.resolveReadPathAt(workspaceRoot, action.path);
        const content = readFileSync(path, "utf8");
        const limit = this.config.limits.prompt_output_chars;
        return { ok: true, action: action.action, summary: `Read ${action.path}`, data: content.length > limit ? `${content.slice(0, limit)}\n...[truncated]` : content };
      }
      case "read_file_range": {
        if (action.end_line < action.start_line) throw new Error("end_line must be greater than or equal to start_line.");
        const path = this.policy.resolveReadPathAt(workspaceRoot, action.path);
        const lines = readFileSync(path, "utf8").split(/\r?\n/);
        const selected = lines.slice(action.start_line - 1, action.end_line).map((line, index) => `${action.start_line + index}: ${line}`).join("\n");
        return { ok: true, action: action.action, summary: `Read ${action.path}:${action.start_line}-${action.end_line}`, data: selected };
      }
      case "search_text": {
        const root = this.policy.resolveReadPathAt(workspaceRoot, action.path);
        const max = action.max_results ?? 50;
        const results: string[] = [];
        const inspect = (path: string): void => {
          if (results.length >= max) return;
          const stat = lstatSync(path);
          if (stat.isDirectory()) {
            for (const entry of readdirSync(path, { withFileTypes: true })) {
              if (entry.isDirectory() && SKIP_DIRECTORIES.has(entry.name)) continue;
              inspect(`${path}/${entry.name}`);
              if (results.length >= max) break;
            }
            return;
          }
          if (stat.size > 2_000_000) return;
          let content: string;
          try { content = readFileSync(path, "utf8"); } catch { return; }
          content.split(/\r?\n/).forEach((line, index) => {
            if (results.length < max && line.toLowerCase().includes(action.query.toLowerCase())) {
              results.push(`${relative(workspaceRoot, path).replaceAll("\\", "/")}:${index + 1}:${line}`);
            }
          });
        };
        inspect(root);
        return { ok: true, action: action.action, summary: `${results.length} matches`, data: results };
      }
      case "inspect_git_diff":
        return {
          ok: true,
          action: action.action,
          summary: "Current Git diff",
          data: isolated
            ? this.git.diffAt(workspaceRoot, this.config.limits.max_context_chars)
            : this.git.diff(this.config.limits.max_context_chars),
        };
      case "create_file": {
        if (this.config.runtime.dry_run) throw new Error("Mutation denied in dry-run mode.");
        const path = this.policy.resolveWritePathAt(workspaceRoot, action.path);
        const existed = existsSync(path);
        if (existed && !action.overwrite) throw new Error(`File already exists and overwrite was not requested: ${action.path}`);
        if (!isolated) this.recovery.backup(path);
        await this.writer.writeFile(path, action.content);
        this.logger.log("file_modified", { path: action.path, operation: existed ? "write" : "create" }, { taskId });
        return { ok: true, action: action.action, summary: `Wrote ${action.path}`, data: { bytes: Buffer.byteLength(action.content) } };
      }
      case "delete_file": {
        if (this.config.runtime.dry_run) throw new Error("Mutation denied in dry-run mode.");
        const path = this.policy.resolveWritePathAt(workspaceRoot, action.path);
        if (!existsSync(path) || !statSync(path).isFile()) throw new Error("delete_file only accepts an existing file.");
        if (!isolated) this.recovery.backup(path);
        await this.writer.deleteFile(path);
        this.logger.log("file_modified", { path: action.path, operation: "delete", reason: action.reason }, { taskId });
        return { ok: true, action: action.action, summary: `Deleted ${action.path}` };
      }
      case "apply_patch": {
        if (this.config.runtime.dry_run) throw new Error("Mutation denied in dry-run mode.");
        const paths = [...action.patch.matchAll(/^(?:\+\+\+|---)\s+(?:[ab]\/)?(.+)$/gm)]
          .map((match) => match[1]?.trim())
          .filter((path): path is string => Boolean(path) && path !== "/dev/null");
        if (paths.length === 0) throw new Error("Patch contains no recognizable file paths.");
        for (const rel of [...new Set(paths)]) {
          const path = this.policy.resolveWritePathAt(workspaceRoot, rel);
          if (!isolated) this.recovery.backup(path);
        }
        await this.writer.applyPatch(action.patch, true, workspaceRoot);
        await this.writer.applyPatch(action.patch, false, workspaceRoot);
        return { ok: true, action: action.action, summary: `Applied patch to ${new Set(paths).size} file(s)`, data: [...new Set(paths)] };
      }
      case "run_command":
      case "run_tests": {
        const result = await this.commands.execute(
          action.command,
          action.cwd ?? ".",
          "timeout_ms" in action && action.timeout_ms ? action.timeout_ms : this.config.limits.command_timeout_ms,
          taskId,
          workspaceRoot,
        );
        return {
          ok: result.exit_code === 0 && !result.timed_out,
          action: action.action,
          summary: `Command exit=${result.exit_code} timed_out=${result.timed_out}`,
          data: { stdout: result.prompt_stdout, stderr: result.prompt_stderr, log_path: result.log_path, duration_ms: result.duration_ms },
        };
      }
      case "report_blocker":
        return { ok: true, action: action.action, summary: "Structured blocker reported", data: action };
      case "finish_task":
        return { ok: true, action: action.action, summary: action.summary };
    }
  }
}
