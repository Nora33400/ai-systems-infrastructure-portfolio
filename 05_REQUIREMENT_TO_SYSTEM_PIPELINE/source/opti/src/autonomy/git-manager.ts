import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import type { AutonomyConfig } from "./types.js";

export class GitManager {
  constructor(private readonly config: AutonomyConfig) {}

  private git(args: string[], cwd = this.config.workspace): string {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    }).trimEnd();
  }

  isRepository(): boolean {
    try {
      return this.git(["rev-parse", "--is-inside-work-tree"]) === "true";
    } catch {
      return false;
    }
  }

  status(): string {
    if (!this.isRepository()) return "not-a-git-repository";
    return this.git(["status", "--short", "--branch"]);
  }

  head(): string | null {
    if (!this.isRepository()) return null;
    try {
      return this.git(["rev-parse", "HEAD"]);
    } catch {
      return null;
    }
  }

  snapshot(): { head: string | null; status: string; created_at: string } {
    return { head: this.head(), status: this.status(), created_at: new Date().toISOString() };
  }

  diff(maxChars = 60000): string {
    if (!this.isRepository()) return "Git repository unavailable.";
    let output = this.git(["diff", "--no-ext-diff", "--unified=3"]);
    const status = this.git(["status", "--porcelain"]);
    const untracked = status
      .split(/\r?\n/)
      .filter((line) => line.startsWith("?? "))
      .map((line) => line.slice(3).trim())
      .filter(Boolean);

    for (const rel of untracked) {
      if (/^(state|logs|node_modules|dist)[\\/]/.test(rel)) continue;
      const full = resolve(this.config.workspace, rel);
      try {
        const content = readFileSync(full, "utf8");
        output += `\n--- /dev/null\n+++ b/${rel.replaceAll("\\", "/")}\n@@ new file @@\n${content}`;
      } catch {
        output += `\n[untracked binary or unreadable: ${rel}]`;
      }
      if (output.length >= maxChars) break;
    }
    if (output.length > maxChars) {
      return `${output.slice(0, maxChars)}\n...[diff truncated]`;
    }
    return output || "No diff.";
  }

  diffAt(workspace: string, maxChars = 60000): string {
    const output = this.git(["diff", "--binary", "--no-ext-diff", "--full-index", "HEAD", "--"], workspace);
    return output.length > maxChars ? `${output.slice(0, maxChars)}\n...[diff truncated]` : output || "No diff.";
  }

  modifiedFiles(): string[] {
    if (!this.isRepository()) return [];
    return this.git(["status", "--porcelain"])
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => line.slice(3).trim().replaceAll("\\", "/"));
  }

  relativePath(path: string): string {
    return relative(this.config.workspace, path).replaceAll("\\", "/");
  }
}
