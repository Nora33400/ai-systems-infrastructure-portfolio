import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import type {
  AutonomyConfig,
  IsolatedPatchArtifact,
  IsolatedWorkspaceMetadata,
  IsolatedWorkspaceRequest,
  IsolatedWorkspaceStatus,
} from "./types.js";

const SAFE_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SECRET_SEGMENT = /^(?:\.env(?:\..*)?|secrets?|credentials?|private[_-]?keys?|tokens?)$/i;

function sha256(value: Buffer | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function normalizeIdentifier(value: string, name: string): string {
  if (!SAFE_IDENTIFIER.test(value) || value === "." || value === ".." || value.includes("..")) {
    throw new Error(`${name} contains unsafe path characters: ${value}`);
  }
  return value;
}

function normalizedRelativePath(value: string, name = "path"): string {
  const normalized = value.replaceAll("\\", "/").replace(/^\.\/+/, "").replace(/\/+/g, "/");
  if (
    normalized === ""
    || normalized === "."
    || isAbsolute(value)
    || /^[A-Za-z]:/.test(normalized)
    || normalized.split("/").some((segment) => segment === "" || segment === "." || segment === "..")
  ) {
    throw new Error(`${name} must be a safe repository-relative path: ${value}`);
  }
  return normalized;
}

function pathWithin(root: string, candidate: string): boolean {
  const rel = relative(root, candidate);
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

function pathMatches(candidate: string, boundary: string): boolean {
  return candidate === boundary || candidate.startsWith(`${boundary}/`);
}

export class IsolatedWorkspaceViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IsolatedWorkspaceViolation";
  }
}

export class IsolatedWorkspaceManager {
  readonly runtimeRoot: string;
  readonly worktreeRoot: string;
  readonly metadataRoot: string;
  readonly patchRoot: string;
  private readonly canonicalWorkspace: string;

  constructor(private readonly config: AutonomyConfig) {
    this.canonicalWorkspace = resolve(config.workspace);
    this.runtimeRoot = resolve(dirname(dirname(config.runtime.database)));
    this.worktreeRoot = join(this.runtimeRoot, "worktrees");
    this.metadataRoot = join(this.runtimeRoot, "state", "isolated-workspaces");
    this.patchRoot = join(this.runtimeRoot, "patches");
    if (pathWithin(this.canonicalWorkspace, this.worktreeRoot)) {
      throw new IsolatedWorkspaceViolation("Runtime worktrees must be outside the canonical repository.");
    }
    mkdirSync(this.worktreeRoot, { recursive: true });
    mkdirSync(this.metadataRoot, { recursive: true });
    mkdirSync(this.patchRoot, { recursive: true });
  }

  verifyCanonicalRepository(requireClean = true): { head: string; status: string } {
    if (this.gitText(this.canonicalWorkspace, ["rev-parse", "--is-inside-work-tree"]) !== "true") {
      throw new IsolatedWorkspaceViolation("Canonical workspace is not a Git worktree.");
    }
    let head: string;
    try {
      head = this.gitText(this.canonicalWorkspace, ["rev-parse", "--verify", "HEAD^{commit}"]);
    } catch {
      throw new IsolatedWorkspaceViolation("Canonical repository has no valid HEAD commit.");
    }
    const status = this.gitText(this.canonicalWorkspace, ["status", "--porcelain=v1", "--untracked-files=all"]);
    if (requireClean && status !== "") {
      throw new IsolatedWorkspaceViolation("Canonical repository is not clean enough to create an isolated workspace.");
    }
    return { head, status };
  }

  create(request: IsolatedWorkspaceRequest): IsolatedWorkspaceMetadata {
    const taskId = normalizeIdentifier(request.task_id, "task_id");
    const executionId = normalizeIdentifier(request.execution_id, "execution_id");
    const workspaceId = `${taskId}-${executionId}`;
    const previous = this.readMetadata(workspaceId, false);
    if (previous) {
      if (previous.state === "ACTIVE" || previous.state === "PATCH_EXTRACTED") {
        if (!existsSync(previous.worktree_path)) {
          throw new IsolatedWorkspaceViolation(`Recorded worktree is missing and requires recovery: ${workspaceId}`);
        }
        return previous;
      }
      throw new IsolatedWorkspaceViolation(`Workspace identifier was already finalized: ${workspaceId}`);
    }

    const canonical = this.verifyCanonicalRepository(request.require_clean_baseline ?? true);
    const worktreePath = resolve(this.worktreeRoot, workspaceId);
    if (!pathWithin(this.worktreeRoot, worktreePath) || worktreePath === this.worktreeRoot) {
      throw new IsolatedWorkspaceViolation("Derived worktree path escapes the configured runtime root.");
    }
    if (existsSync(worktreePath)) {
      throw new IsolatedWorkspaceViolation(`Unmanaged worktree path already exists: ${worktreePath}`);
    }

    this.gitText(this.canonicalWorkspace, ["worktree", "add", "--detach", worktreePath, canonical.head]);
    const actualHead = this.gitText(worktreePath, ["rev-parse", "--verify", "HEAD^{commit}"]);
    if (actualHead !== canonical.head) {
      throw new IsolatedWorkspaceViolation(`Worktree HEAD mismatch: expected ${canonical.head}, received ${actualHead}`);
    }
    const now = new Date().toISOString();
    const metadata: IsolatedWorkspaceMetadata = {
      schema_version: 1,
      workspace_id: workspaceId,
      task_id: taskId,
      execution_id: executionId,
      canonical_workspace: this.canonicalWorkspace,
      worktree_path: worktreePath,
      base_head: canonical.head,
      canonical_status_at_create: canonical.status,
      allowed_paths: this.normalizeBoundaries(request.allowed_paths, "allowed_paths"),
      forbidden_paths: this.normalizeBoundaries(request.forbidden_paths, "forbidden_paths"),
      state: "ACTIVE",
      created_at: now,
      updated_at: now,
      patch_path: null,
      patch_sha256: null,
      touched_files: [],
      cleanup_result: null,
      recovery_note: null,
    };
    this.writeMetadata(metadata);
    return metadata;
  }

  status(workspaceIdInput: string): IsolatedWorkspaceStatus {
    const metadata = this.readMetadata(normalizeIdentifier(workspaceIdInput, "workspace_id"));
    const exists = existsSync(metadata.worktree_path);
    if (!exists) {
      return {
        metadata,
        exists: false,
        head: null,
        porcelain: "",
        touched_files: [],
        clean: metadata.state === "CLEANED",
      };
    }
    const head = this.gitText(metadata.worktree_path, ["rev-parse", "--verify", "HEAD^{commit}"]);
    const porcelain = this.gitText(metadata.worktree_path, ["status", "--porcelain=v1", "--untracked-files=all"]);
    const touched = this.touchedFiles(metadata.worktree_path);
    return { metadata, exists: true, head, porcelain, touched_files: touched, clean: touched.length === 0 };
  }

  validateTouchedFiles(
    paths: string[],
    allowedPaths: string[],
    forbiddenPaths: string[],
  ): string[] {
    const allowed = this.normalizeBoundaries(allowedPaths, "allowed_paths");
    const forbidden = this.normalizeBoundaries(forbiddenPaths, "forbidden_paths");
    if (allowed.length === 0 && paths.length > 0) {
      throw new IsolatedWorkspaceViolation("No path is authorized for this isolated task.");
    }
    const normalized = [...new Set(paths.map((entry) => normalizedRelativePath(entry)))].sort();
    for (const candidate of normalized) {
      const segments = candidate.split("/");
      if (segments.some((segment) => segment === ".git")) {
        throw new IsolatedWorkspaceViolation(`Direct .git mutation is forbidden: ${candidate}`);
      }
      if (segments.some((segment) => SECRET_SEGMENT.test(segment))) {
        throw new IsolatedWorkspaceViolation(`Secret-like path is forbidden: ${candidate}`);
      }
      if (forbidden.some((boundary) => pathMatches(candidate, boundary))) {
        throw new IsolatedWorkspaceViolation(`Touched path is explicitly forbidden: ${candidate}`);
      }
      if (!allowed.some((boundary) => pathMatches(candidate, boundary))) {
        throw new IsolatedWorkspaceViolation(`Touched path is outside allowed_paths: ${candidate}`);
      }
    }
    return normalized;
  }

  extractPatch(workspaceIdInput: string): IsolatedPatchArtifact {
    const metadata = this.readMetadata(normalizeIdentifier(workspaceIdInput, "workspace_id"));
    this.assertActive(metadata);
    this.assertCanonicalUnchanged(metadata);
    if (!existsSync(metadata.worktree_path)) {
      throw new IsolatedWorkspaceViolation(`Worktree is unavailable: ${metadata.worktree_path}`);
    }
    const touched = this.validateTouchedFiles(
      this.touchedFiles(metadata.worktree_path),
      metadata.allowed_paths,
      metadata.forbidden_paths,
    );
    if (touched.length === 0) {
      throw new IsolatedWorkspaceViolation("Cannot produce a patch from a clean worktree.");
    }

    const untracked = this.nullSeparated(
      this.gitBuffer(metadata.worktree_path, ["ls-files", "--others", "--exclude-standard", "-z"]),
    );
    if (untracked.length > 0) {
      this.validateTouchedFiles(untracked, metadata.allowed_paths, metadata.forbidden_paths);
      this.gitText(metadata.worktree_path, ["add", "--intent-to-add", "--", ...untracked]);
    }
    const patch = this.gitBuffer(metadata.worktree_path, [
      "diff", "--binary", "--no-ext-diff", "--full-index", "HEAD", "--",
    ]);
    if (patch.length === 0) {
      throw new IsolatedWorkspaceViolation("Git produced an empty patch for a dirty isolated worktree.");
    }
    const patchPath = resolve(this.patchRoot, `${metadata.workspace_id}.patch`);
    if (!pathWithin(this.patchRoot, patchPath)) {
      throw new IsolatedWorkspaceViolation("Derived patch path escapes the configured runtime root.");
    }
    writeFileSync(patchPath, patch);
    const patchSha256 = sha256(patch);
    const updated: IsolatedWorkspaceMetadata = {
      ...metadata,
      state: "PATCH_EXTRACTED",
      updated_at: new Date().toISOString(),
      patch_path: patchPath,
      patch_sha256: patchSha256,
      touched_files: touched,
      recovery_note: null,
    };
    this.writeMetadata(updated);
    this.assertCanonicalUnchanged(updated);
    return {
      workspace_id: updated.workspace_id,
      task_id: updated.task_id,
      execution_id: updated.execution_id,
      base_head: updated.base_head,
      patch_path: patchPath,
      patch_sha256: patchSha256,
      size_bytes: patch.length,
      touched_files: touched,
    };
  }

  cleanup(workspaceIdInput: string): IsolatedWorkspaceMetadata {
    const metadata = this.readMetadata(normalizeIdentifier(workspaceIdInput, "workspace_id"));
    if (metadata.state === "CLEANED") return metadata;
    this.assertCanonicalUnchanged(metadata);
    if (existsSync(metadata.worktree_path)) {
      const touched = this.touchedFiles(metadata.worktree_path);
      if (touched.length > 0) {
        if (!metadata.patch_path || !metadata.patch_sha256) {
          throw new IsolatedWorkspaceViolation("Refusing cleanup because isolated changes have no patch artifact.");
        }
        const patchPath = resolve(metadata.patch_path);
        if (!pathWithin(this.patchRoot, patchPath) || !existsSync(patchPath)) {
          throw new IsolatedWorkspaceViolation("Refusing cleanup because the captured patch artifact is missing or unmanaged.");
        }
        const capturedPatch = readFileSync(patchPath);
        const currentPatch = this.gitBuffer(metadata.worktree_path, [
          "diff", "--binary", "--no-ext-diff", "--full-index", "HEAD", "--",
        ]);
        if (sha256(capturedPatch) !== metadata.patch_sha256 || sha256(currentPatch) !== metadata.patch_sha256) {
          throw new IsolatedWorkspaceViolation("Refusing cleanup because isolated changes differ from the captured patch artifact.");
        }
      }
      this.gitText(this.canonicalWorkspace, ["worktree", "remove", "--force", metadata.worktree_path]);
    } else if (this.registeredWorktrees().includes(resolve(metadata.worktree_path))) {
      this.gitText(this.canonicalWorkspace, ["worktree", "prune", "--expire=now"]);
    }
    const cleaned: IsolatedWorkspaceMetadata = {
      ...metadata,
      state: "CLEANED",
      updated_at: new Date().toISOString(),
      cleanup_result: "REMOVED",
      recovery_note: metadata.recovery_note,
    };
    this.writeMetadata(cleaned);
    this.assertCanonicalUnchanged(cleaned);
    return cleaned;
  }

  recover(workspaceIdInput: string): IsolatedWorkspaceMetadata {
    const metadata = this.readMetadata(normalizeIdentifier(workspaceIdInput, "workspace_id"));
    if (metadata.state === "CLEANED") return metadata;
    if (!existsSync(metadata.worktree_path)) {
      const missing: IsolatedWorkspaceMetadata = {
        ...metadata,
        updated_at: new Date().toISOString(),
        recovery_note: "WORKTREE_MISSING_PRUNED",
      };
      this.writeMetadata(missing);
      return this.cleanup(missing.workspace_id);
    }
    const touched = this.touchedFiles(metadata.worktree_path);
    if (touched.length > 0) {
      try {
        this.extractPatch(metadata.workspace_id);
      } catch (error) {
        const blocked: IsolatedWorkspaceMetadata = {
          ...this.readMetadata(metadata.workspace_id),
          state: "RECOVERY_REQUIRED",
          updated_at: new Date().toISOString(),
          recovery_note: error instanceof Error ? error.message : String(error),
        };
        this.writeMetadata(blocked);
        return blocked;
      }
    }
    return this.cleanup(metadata.workspace_id);
  }

  readPatch(artifact: IsolatedPatchArtifact): Buffer {
    const candidate = resolve(artifact.patch_path);
    if (!pathWithin(this.patchRoot, candidate) || !existsSync(candidate) || !statSync(candidate).isFile()) {
      throw new IsolatedWorkspaceViolation("Patch artifact is outside the managed patch root or missing.");
    }
    const content = readFileSync(candidate);
    if (sha256(content) !== artifact.patch_sha256) {
      throw new IsolatedWorkspaceViolation("Patch artifact hash verification failed.");
    }
    return content;
  }

  private normalizeBoundaries(values: string[], name: string): string[] {
    return [...new Set(values.map((entry) => normalizedRelativePath(entry, name)))].sort();
  }

  private assertActive(metadata: IsolatedWorkspaceMetadata): void {
    if (!["ACTIVE", "PATCH_EXTRACTED"].includes(metadata.state)) {
      throw new IsolatedWorkspaceViolation(`Workspace is not active: ${metadata.workspace_id} (${metadata.state})`);
    }
  }

  private assertCanonicalUnchanged(metadata: IsolatedWorkspaceMetadata): void {
    const currentHead = this.gitText(this.canonicalWorkspace, ["rev-parse", "--verify", "HEAD^{commit}"]);
    const currentStatus = this.gitText(this.canonicalWorkspace, ["status", "--porcelain=v1", "--untracked-files=all"]);
    if (currentHead !== metadata.base_head || currentStatus !== metadata.canonical_status_at_create) {
      throw new IsolatedWorkspaceViolation("Canonical repository changed during the isolated execution.");
    }
  }

  private touchedFiles(worktreePath: string): string[] {
    const tracked = this.nullSeparated(this.gitBuffer(worktreePath, ["diff", "--name-only", "-z", "HEAD", "--"]));
    const untracked = this.nullSeparated(this.gitBuffer(worktreePath, ["ls-files", "--others", "--exclude-standard", "-z"]));
    return [...new Set([...tracked, ...untracked].map((entry) => normalizedRelativePath(entry)))].sort();
  }

  private registeredWorktrees(): string[] {
    const lines = this.gitText(this.canonicalWorkspace, ["worktree", "list", "--porcelain"]).split(/\r?\n/);
    return lines
      .filter((line) => line.startsWith("worktree "))
      .map((line) => resolve(line.slice("worktree ".length)));
  }

  private metadataPath(workspaceId: string): string {
    const candidate = resolve(this.metadataRoot, `${workspaceId}.json`);
    if (!pathWithin(this.metadataRoot, candidate)) {
      throw new IsolatedWorkspaceViolation("Derived metadata path escapes the configured runtime root.");
    }
    return candidate;
  }

  private readMetadata(workspaceId: string): IsolatedWorkspaceMetadata;
  private readMetadata(workspaceId: string, required: true): IsolatedWorkspaceMetadata;
  private readMetadata(workspaceId: string, required: false): IsolatedWorkspaceMetadata | null;
  private readMetadata(workspaceId: string, required = true): IsolatedWorkspaceMetadata | null {
    const path = this.metadataPath(workspaceId);
    if (!existsSync(path)) {
      if (required) throw new IsolatedWorkspaceViolation(`Unknown isolated workspace: ${workspaceId}`);
      return null;
    }
    return JSON.parse(readFileSync(path, "utf8")) as IsolatedWorkspaceMetadata;
  }

  private writeMetadata(metadata: IsolatedWorkspaceMetadata): void {
    const target = this.metadataPath(metadata.workspace_id);
    const temporary = `${target}.${process.pid}.tmp`;
    writeFileSync(temporary, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
    renameSync(temporary, target);
  }

  private nullSeparated(buffer: Buffer): string[] {
    return buffer.toString("utf8").split("\0").filter(Boolean);
  }

  private gitText(cwd: string, args: string[]): string {
    return this.gitBuffer(cwd, args).toString("utf8").trimEnd();
  }

  private gitBuffer(cwd: string, args: string[]): Buffer {
    try {
      return execFileSync("git", args, {
        cwd,
        encoding: "buffer",
        maxBuffer: 40 * 1024 * 1024,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (error) {
      const stderr = (
        error && typeof error === "object" && "stderr" in error
          ? Buffer.from((error as { stderr?: Buffer | string }).stderr ?? "").toString("utf8").trim()
          : ""
      );
      throw new IsolatedWorkspaceViolation(`Git command failed (${args.join(" ")}): ${stderr || "unknown error"}`);
    }
  }
}
