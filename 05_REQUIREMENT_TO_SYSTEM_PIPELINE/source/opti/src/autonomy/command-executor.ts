import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import type { AutonomyConfig, CommandResult } from "./types.js";
import { EventLogger } from "./event-logger.js";
import { SecurityPolicy } from "./security-policy.js";

export class CommandExecutor {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly policy: SecurityPolicy,
    private readonly logger: EventLogger,
  ) {
    mkdirSync(config.runtime.command_log_directory, { recursive: true });
  }

  async execute(
    command: string,
    cwdInput = ".",
    timeoutMs = this.config.limits.command_timeout_ms,
    taskId?: string,
    workspaceRoot = this.config.workspace,
  ): Promise<CommandResult> {
    this.policy.validateCommand(command);
    const parsed = parseCommand(command);
    const executable = resolveExecutable(parsed.executable);
    const cwd = cwdInput === "." ? workspaceRoot : this.policy.resolveReadPathAt(workspaceRoot, cwdInput);
    const id = randomUUID();
    const started = Date.now();
    this.logger.log("command_started", { id, command, cwd: relative(workspaceRoot, cwd), timeout_ms: timeoutMs }, { taskId });

    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let exitCode: number | null = null;

    await new Promise<void>((resolvePromise, reject) => {
      const child = spawn(executable.command, [...executable.prefixArgs, ...parsed.args], {
        cwd,
        shell: false,
        windowsHide: true,
        env: { ...process.env, NO_COLOR: "1", FORCE_COLOR: "0" },
      });
      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGKILL");
      }, timeoutMs);
      child.stdout?.on("data", (chunk: Buffer) => { stdout += chunk.toString("utf8"); });
      child.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString("utf8"); });
      child.on("error", (error) => {
        clearTimeout(timer);
        reject(error);
      });
      child.on("close", (code) => {
        clearTimeout(timer);
        exitCode = code;
        resolvePromise();
      });
    });

    const duration = Date.now() - started;
    const logPath = `${this.config.runtime.command_log_directory}/${id}.log`;
    writeFileSync(logPath, [
      `command: ${command}`,
      `cwd: ${cwd}`,
      `exit_code: ${exitCode}`,
      `timed_out: ${timedOut}`,
      `duration_ms: ${duration}`,
      "",
      "--- stdout ---",
      stdout,
      "--- stderr ---",
      stderr,
    ].join("\n"), "utf8");

    const limit = this.config.limits.prompt_output_chars;
    const result: CommandResult = {
      id,
      command,
      cwd,
      stdout,
      stderr,
      prompt_stdout: stdout.length > limit ? `${stdout.slice(0, limit)}\n...[truncated; full log: ${logPath}]` : stdout,
      prompt_stderr: stderr.length > limit ? `${stderr.slice(0, limit)}\n...[truncated; full log: ${logPath}]` : stderr,
      exit_code: exitCode,
      timed_out: timedOut,
      duration_ms: duration,
      log_path: logPath,
    };
    this.logger.log("command_finished", {
      id,
      command,
      exit_code: exitCode,
      timed_out: timedOut,
      duration_ms: duration,
      stdout_chars: stdout.length,
      stderr_chars: stderr.length,
      log_path: relative(this.config.workspace, logPath),
    }, { taskId, level: exitCode === 0 && !timedOut ? "info" : "warn" });
    return result;
  }
}

export function parseCommand(command: string): { executable: string; args: string[] } {
  const parts: string[] = [];
  let current = "";
  let quote: "'" | '"' | null = null;
  for (let index = 0; index < command.length; index += 1) {
    const char = command[index];
    if ((char === "'" || char === '"')) {
      if (quote === char) quote = null;
      else if (quote === null) quote = char;
      else current += char;
      continue;
    }
    if (/\s/.test(char ?? "") && quote === null) {
      if (current) {
        parts.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (quote !== null) throw new Error("Unterminated quote in command.");
  if (current) parts.push(current);
  const executable = parts.shift();
  if (!executable) throw new Error("Empty command.");
  return { executable, args: parts };
}

function resolveExecutable(input: string): { command: string; prefixArgs: string[] } {
  const family = input.toLowerCase().replace(/\.(cmd|exe)$/i, "");
  if (family === "node") return { command: process.execPath, prefixArgs: [] };
  if (family === "npm" || family === "npx") {
    const fromEnvironment = process.env.npm_execpath;
    const installed = join(dirname(process.execPath), "node_modules", "npm", "bin", family === "npm" ? "npm-cli.js" : "npx-cli.js");
    const cli = fromEnvironment && existsSync(fromEnvironment) && family === "npm" ? fromEnvironment : installed;
    if (!existsSync(cli)) throw new Error(`Unable to locate ${family} CLI without a shell.`);
    return { command: process.execPath, prefixArgs: [cli] };
  }
  const suffix = process.platform === "win32" ? ".exe" : "";
  return { command: `${family}${suffix}`, prefixArgs: [] };
}
