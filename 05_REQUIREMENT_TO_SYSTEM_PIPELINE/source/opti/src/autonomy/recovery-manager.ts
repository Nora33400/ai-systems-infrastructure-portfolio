import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import type { AutonomyConfig, TaskRecord } from "./types.js";
import { WorkspaceWriter } from "./workspace-writer.js";

interface BackupEntry {
  relative_path: string;
  existed: boolean;
  backup_path?: string;
}

interface BackupManifest {
  task_id: string;
  attempt: number;
  created_at: string;
  entries: BackupEntry[];
}

export class RecoveryManager {
  private manifestPath: string | null = null;
  private manifest: BackupManifest | null = null;

  constructor(
    private readonly config: AutonomyConfig,
    private readonly writer: WorkspaceWriter,
  ) {
    mkdirSync(config.runtime.backup_directory, { recursive: true });
  }

  begin(task: TaskRecord): void {
    const directory = join(this.config.runtime.backup_directory, task.id, `attempt-${task.attempts}`);
    mkdirSync(directory, { recursive: true });
    this.manifestPath = join(directory, "manifest.json");
    let inheritedEntries: BackupEntry[] = [];
    if (task.attempts > 1) {
      const previousPath = join(this.config.runtime.backup_directory, task.id, `attempt-${task.attempts - 1}`, "manifest.json");
      if (existsSync(previousPath)) {
        const previous = JSON.parse(readFileSync(previousPath, "utf8")) as BackupManifest;
        inheritedEntries = previous.entries;
      }
    }
    this.manifest = {
      task_id: task.id,
      attempt: task.attempts,
      created_at: new Date().toISOString(),
      entries: inheritedEntries,
    };
    this.persist();
  }

  backup(filePath: string): void {
    if (!this.manifest || !this.manifestPath) throw new Error("Recovery attempt has not been started.");
    const rel = relative(this.config.workspace, filePath).replaceAll("\\", "/");
    if (this.manifest.entries.some((entry) => entry.relative_path === rel)) return;

    const existed = existsSync(filePath);
    const entry: BackupEntry = { relative_path: rel, existed };
    if (existed) {
      const backupPath = join(dirname(this.manifestPath), "files", rel);
      mkdirSync(dirname(backupPath), { recursive: true });
      copyFileSync(filePath, backupPath);
      entry.backup_path = backupPath;
    }
    this.manifest.entries.push(entry);
    this.persist();
  }

  async restore(manifestPath = this.manifestPath): Promise<void> {
    if (!manifestPath || !existsSync(manifestPath)) throw new Error("Backup manifest is unavailable.");
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as BackupManifest;
    for (const entry of [...manifest.entries].reverse()) {
      const destination = resolve(this.config.workspace, entry.relative_path);
      if (entry.existed && entry.backup_path) {
        await this.writer.writeFile(destination, readFileSync(entry.backup_path));
      } else {
        await this.writer.deleteFile(destination);
      }
    }
  }

  changedFiles(): string[] {
    if (!this.manifest) return [];
    return this.manifest.entries
      .filter((entry) => {
        const current = resolve(this.config.workspace, entry.relative_path);
        if (!entry.existed) return existsSync(current);
        if (!entry.backup_path || !existsSync(current)) return true;
        return !readFileSync(current).equals(readFileSync(entry.backup_path));
      })
      .map((entry) => entry.relative_path);
  }

  diff(maxChars = 60000): string {
    if (!this.manifest) return "No active recovery manifest.";
    let output = "";
    for (const entry of this.manifest.entries) {
      const current = resolve(this.config.workspace, entry.relative_path);
      if (!this.changedFiles().includes(entry.relative_path)) continue;
      const before = entry.existed && entry.backup_path ? readFileSync(entry.backup_path, "utf8") : "<FILE DID NOT EXIST>";
      const after = existsSync(current) ? readFileSync(current, "utf8") : "<FILE DELETED>";
      output += `\n=== ${entry.relative_path} ===\n--- BEFORE ---\n${before}\n--- AFTER ---\n${after}\n`;
      if (output.length >= maxChars) return `${output.slice(0, maxChars)}\n...[change set truncated]`;
    }
    return output || "No task-local changes.";
  }

  currentManifestPath(): string | null {
    return this.manifestPath;
  }

  private persist(): void {
    if (this.manifest && this.manifestPath) {
      writeFileSync(this.manifestPath, JSON.stringify(this.manifest, null, 2), "utf8");
    }
  }
}
