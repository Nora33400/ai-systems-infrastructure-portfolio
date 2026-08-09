import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { spawn } from "node:child_process";
import type { AutonomyConfig } from "./types.js";

const WRITE_SCRIPT = [
  "import os,sys,tempfile",
  "p=sys.argv[1]",
  "parent=os.path.dirname(p)",
  "os.makedirs(parent,exist_ok=True)",
  "fd,tmp=tempfile.mkstemp(prefix='.aione-',dir=parent)",
  "f=os.fdopen(fd,'wb')",
  "f.write(sys.stdin.buffer.read())",
  "f.flush()",
  "os.fsync(f.fileno())",
  "f.close()",
  "os.replace(tmp,p)",
].join(";");

const DELETE_SCRIPT = "import os,sys; p=sys.argv[1]; os.remove(p) if os.path.isfile(p) or os.path.islink(p) else None";

function windowsToWsl(path: string): string {
  const match = /^([A-Za-z]):[\\/](.*)$/.exec(path);
  if (!match) throw new Error(`Cannot convert path to WSL: ${path}`);
  const drive = match[1];
  const remainder = match[2];
  if (!drive || remainder === undefined) throw new Error(`Cannot convert path to WSL: ${path}`);
  return `/mnt/${drive.toLowerCase()}/${remainder.replaceAll("\\", "/")}`;
}

export class WorkspaceWriter {
  constructor(private readonly config: AutonomyConfig) {}

  async writeFile(path: string, content: string | Buffer): Promise<void> {
    const data = Buffer.isBuffer(content) ? content : Buffer.from(content, "utf8");
    if (this.config.runtime.workspace_write_backend === "direct") {
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, data);
      return;
    }
    await this.runWsl(["python3", "-c", WRITE_SCRIPT, windowsToWsl(path)], data);
  }

  async deleteFile(path: string): Promise<void> {
    if (this.config.runtime.workspace_write_backend === "direct") {
      rmSync(path, { force: true });
      return;
    }
    await this.runWsl(["python3", "-c", DELETE_SCRIPT, windowsToWsl(path)]);
  }

  async applyPatch(patch: string, check: boolean, workspace = this.config.workspace): Promise<void> {
    const args = [
      "git", "-C", windowsToWsl(workspace), "apply", "--whitespace=nowarn",
      ...(check ? ["--check"] : []), "-",
    ];
    await this.runWsl(args, Buffer.from(patch, "utf8"));
  }

  private async runWsl(command: string[], stdin?: Buffer): Promise<void> {
    await new Promise<void>((resolvePromise, reject) => {
      const child = spawn("wsl.exe", ["-d", this.config.runtime.wsl_distro, "--", ...command], {
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      });
      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString("utf8"); });
      child.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString("utf8"); });
      child.on("error", reject);
      child.on("close", (code) => {
        if (code === 0) resolvePromise();
        else reject(new Error(`WSL workspace operation failed (exit ${code}): ${stderr || stdout}`));
      });
      child.stdin.end(stdin);
    });
  }
}
