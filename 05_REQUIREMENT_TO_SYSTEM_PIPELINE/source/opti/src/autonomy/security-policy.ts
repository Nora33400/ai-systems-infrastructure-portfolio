import { basename, isAbsolute, relative, resolve, sep } from "node:path";
import type { AutonomyConfig } from "./types.js";

export class SecurityViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SecurityViolation";
  }
}

function configuredRegex(source: string): RegExp {
  if (source.startsWith("(?i)")) return new RegExp(source.slice(4), "i");
  return new RegExp(source);
}

export class SecurityPolicy {
  private readonly workspace: string;
  private readonly forbiddenCommands: RegExp[];
  private readonly secretNames: RegExp[];

  constructor(private readonly config: AutonomyConfig) {
    this.workspace = resolve(config.workspace);
    this.forbiddenCommands = config.security.forbidden_command_patterns.map(configuredRegex);
    this.secretNames = config.security.deny_secret_name_patterns.map(configuredRegex);
  }

  private insideWorkspace(workspace: string, candidate: string): boolean {
    const rel = relative(workspace, candidate);
    return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
  }

  private checkSecretPath(workspace: string, candidate: string): void {
    const rel = relative(workspace, candidate);
    for (const segment of rel.split(/[\\/]/)) {
      if (this.secretNames.some((pattern) => pattern.test(segment))) {
        throw new SecurityViolation(`Access to secret-like path is denied: ${rel}`);
      }
    }
  }

  resolveReadPath(input: string): string {
    return this.resolveReadPathAt(this.workspace, input);
  }

  resolveReadPathAt(workspaceInput: string, input: string): string {
    const workspace = resolve(workspaceInput);
    if (isAbsolute(input)) throw new SecurityViolation("Absolute paths are not accepted from agents.");
    const candidate = resolve(workspace, input);
    if (!this.insideWorkspace(workspace, candidate)) throw new SecurityViolation(`Path escapes workspace: ${input}`);
    if (relative(workspace, candidate).split(sep).includes(".git")) {
      throw new SecurityViolation("Direct .git access is denied.");
    }
    this.checkSecretPath(workspace, candidate);

    const rel = relative(workspace, candidate).replaceAll("\\", "/");
    const rootFileAllowed = rel === "" || (!rel.includes("/") && this.config.security.readable_root_files.includes(rel));
    const directoryAllowed = this.config.security.allowed_directories
      .map((entry) => resolve(workspace, entry))
      .some((root) => candidate === root || candidate.startsWith(`${root}${sep}`));
    if (!rootFileAllowed && !directoryAllowed) {
      throw new SecurityViolation(`Read path is outside configured areas: ${input}`);
    }
    return candidate;
  }

  resolveWritePath(input: string): string {
    return this.resolveWritePathAt(this.workspace, input);
  }

  resolveWritePathAt(workspaceInput: string, input: string): string {
    const workspace = resolve(workspaceInput);
    const candidate = this.resolveReadPathAt(workspace, input);
    const rel = relative(workspace, candidate).replaceAll("\\", "/");
    if (this.config.security.protected_files.includes(rel)) {
      throw new SecurityViolation(`Protected file cannot be modified: ${rel}`);
    }
    const rootWritable = !rel.includes("/") && this.config.security.writable_root_files.includes(rel);
    const directoryWritable = this.config.security.allowed_directories
      .map((entry) => resolve(workspace, entry))
      .some((root) => candidate.startsWith(`${root}${sep}`));
    if (!rootWritable && !directoryWritable) {
      throw new SecurityViolation(`Write path is outside configured areas: ${input}`);
    }
    return candidate;
  }

  validateCommand(command: string): void {
    const trimmed = command.trim();
    if (!trimmed) throw new SecurityViolation("Empty command.");
    if (/[\r\n]/.test(trimmed) || /&&|\|\||[;&|\x60]/.test(trimmed)) {
      throw new SecurityViolation("Shell chaining and metacharacters are denied.");
    }
    for (const pattern of this.forbiddenCommands) {
      pattern.lastIndex = 0;
      if (pattern.test(trimmed)) throw new SecurityViolation(`Forbidden command pattern: ${pattern.source}`);
    }
    const first = trimmed.match(/^\s*"?([^\s"]+)/)?.[1]?.toLowerCase().replace(/\.(cmd|exe)$/i, "");
    if (!first || !this.config.security.allowed_command_families.includes(basename(first))) {
      throw new SecurityViolation(`Command family is not allowed: ${first ?? "<unknown>"}`);
    }
    if (/^git\s+/i.test(trimmed) && !/^git\s+(status|diff|show|rev-parse|log)\b/i.test(trimmed)) {
      throw new SecurityViolation("Only read-only Git commands are allowed to agents.");
    }
    if (/^npm\s+/i.test(trimmed) && !/^npm\s+(test|run|exec)\b/i.test(trimmed)) {
      throw new SecurityViolation("Only npm test/run/exec are allowed to agents.");
    }
  }
}
