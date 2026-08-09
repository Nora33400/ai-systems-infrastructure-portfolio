import { closeSync, existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export class RuntimeLock {
  private owned = false;

  constructor(private readonly lockPath: string) {
    mkdirSync(dirname(lockPath), { recursive: true });
  }

  acquire(): void {
    try {
      const fd = openSync(this.lockPath, "wx");
      writeFileSync(fd, JSON.stringify({ pid: process.pid, started_at: new Date().toISOString() }));
      closeSync(fd);
      this.owned = true;
      return;
    } catch (error) {
      if (!existsSync(this.lockPath)) throw error;
    }

    let existing: { pid?: number } = {};
    try {
      existing = JSON.parse(readFileSync(this.lockPath, "utf8")) as { pid?: number };
    } catch {
      // An unreadable lock is treated as stale.
    }
    if (existing.pid && isPidAlive(existing.pid)) {
      throw new Error(`Autonomy engine is already running with PID ${existing.pid}.`);
    }
    rmSync(this.lockPath, { force: true });
    this.acquire();
  }

  release(): void {
    if (this.owned) {
      rmSync(this.lockPath, { force: true });
      this.owned = false;
    }
  }
}

export class StopController {
  constructor(private readonly stopPath: string) {
    mkdirSync(dirname(stopPath), { recursive: true });
  }

  request(reason = "user_request"): void {
    writeFileSync(this.stopPath, JSON.stringify({ requested_at: new Date().toISOString(), reason }, null, 2));
  }

  clear(): void {
    rmSync(this.stopPath, { force: true });
  }

  isRequested(): boolean {
    return existsSync(this.stopPath);
  }

  disabledReason(): string | null {
    const value = process.env.AUTONOMY_DISABLED?.trim().toLowerCase();
    if (value && !["0", "false", "no", "off"].includes(value)) return "AUTONOMY_DISABLED environment variable";
    if (this.isRequested()) return `stop sentinel: ${this.stopPath}`;
    return null;
  }

  assertEnabled(entrypoint: string): void {
    const reason = this.disabledReason();
    if (reason) throw new Error(`Autonomy is disabled for ${entrypoint}: ${reason}`);
  }
}
