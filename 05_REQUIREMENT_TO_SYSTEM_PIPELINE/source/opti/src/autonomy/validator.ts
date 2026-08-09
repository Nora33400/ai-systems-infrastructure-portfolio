import { existsSync, readFileSync } from "node:fs";
import type { AutonomyConfig, TaskRecord, TestResult } from "./types.js";
import { SecurityPolicy } from "./security-policy.js";
import { CommandExecutor } from "./command-executor.js";
import { validateDocumentation } from "./document-validator.js";

export class Validator {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly policy: SecurityPolicy,
    private readonly commands: CommandExecutor,
  ) {}

  async validateTask(task: TaskRecord, full = false, workspaceRoot = this.config.workspace): Promise<TestResult[]> {
    const results: TestResult[] = [];
    for (const criterion of task.acceptance) {
      const timestamp = new Date().toISOString();
      try {
        if (criterion.type === "file_exists") {
          const path = this.policy.resolveReadPathAt(workspaceRoot, criterion.path);
          results.push({ criterion, passed: existsSync(path), detail: existsSync(path) ? "file exists" : "file missing", timestamp });
        } else if (criterion.type === "file_contains" || criterion.type === "file_not_contains") {
          const path = this.policy.resolveReadPathAt(workspaceRoot, criterion.path);
          const content = existsSync(path) ? readFileSync(path, "utf8") : "";
          const contains = content.includes(criterion.text);
          const passed = criterion.type === "file_contains" ? contains : !contains;
          results.push({ criterion, passed, detail: passed ? "text condition satisfied" : "text condition failed: " + criterion.text, timestamp });
        } else if (criterion.type === "command_succeeds") {
          const result = await this.commands.execute(criterion.command, criterion.cwd ?? ".", this.config.limits.command_timeout_ms, task.id, workspaceRoot);
          results.push({ criterion, passed: result.exit_code === 0 && !result.timed_out, detail: "exit=" + result.exit_code + " timeout=" + result.timed_out + " log=" + result.log_path, timestamp });
        } else if (criterion.type === "docs_validate") {
          const result = validateDocumentation(workspaceRoot);
          results.push({ criterion, passed: result.issues.length === 0, detail: result.issues.length === 0 ? "validated " + result.yaml_files + " YAML, " + result.json_files + " JSON, " + result.markdown_files + " Markdown" : result.issues.join("; "), timestamp });
        } else if (criterion.type === "tests_pass") {
          const command = criterion.command ?? "npm test";
          const result = await this.commands.execute(command, ".", this.config.limits.command_timeout_ms, task.id, workspaceRoot);
          results.push({ criterion, passed: result.exit_code === 0 && !result.timed_out, detail: "exit=" + result.exit_code + " timeout=" + result.timed_out + " log=" + result.log_path, timestamp });
        }
      } catch (error) {
        results.push({ criterion, passed: false, detail: error instanceof Error ? error.message : String(error), timestamp });
      }
    }

    const commands = full ? [...this.config.validation.light_commands, ...this.config.validation.full_commands] : this.config.validation.light_commands;
    for (const command of commands) {
      const criterion = { type: "validation_command" as const, command };
      const timestamp = new Date().toISOString();
      try {
        const result = await this.commands.execute(command, ".", this.config.limits.command_timeout_ms, task.id, workspaceRoot);
        results.push({ criterion, passed: result.exit_code === 0 && !result.timed_out, detail: "exit=" + result.exit_code + " timeout=" + result.timed_out + " log=" + result.log_path, timestamp });
      } catch (error) {
        results.push({ criterion, passed: false, detail: error instanceof Error ? error.message : String(error), timestamp });
      }
    }
    return results;
  }
}
