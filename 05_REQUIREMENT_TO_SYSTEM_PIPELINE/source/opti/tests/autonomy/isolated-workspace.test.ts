import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  IsolatedWorkspaceManager,
  IsolatedWorkspaceViolation,
} from "../../src/autonomy/isolated-workspace-manager.js";
import type { AutonomyConfig } from "../../src/autonomy/types.js";
import { testConfig } from "./test-helpers.js";

interface RepositoryFixture {
  root: string;
  repository: string;
  config: AutonomyConfig;
  manager: IsolatedWorkspaceManager;
  head: string | null;
  branch: string;
}

function git(cwd: string, args: string[]): string {
  return execFileSync("git", args, {
    cwd,
    encoding: "utf8",
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  }).trimEnd();
}

function fixture(t: { after(callback: () => void): void }, committed = true): RepositoryFixture {
  const root = mkdtempSync(join(tmpdir(), "aione phase 4 "));
  const repository = join(root, "canonical repository with spaces");
  mkdirSync(join(repository, "src"), { recursive: true });
  git(root, ["init", repository]);
  git(repository, ["config", "user.name", "AIONE Test"]);
  git(repository, ["config", "user.email", "portfolio@example.invalid"]);
  writeFileSync(join(repository, "src", "allowed.txt"), "baseline\n", "utf8");
  let head: string | null = null;
  if (committed) {
    git(repository, ["add", "src/allowed.txt"]);
    git(repository, ["commit", "-m", "test baseline"]);
    head = git(repository, ["rev-parse", "HEAD"]);
  }
  const config = testConfig(repository);
  const runtime = join(root, "runtime outside repository");
  config.runtime.database = join(runtime, "state", "autonomy.db");
  config.runtime.backup_directory = join(runtime, "state", "backups");
  config.runtime.lock_file = join(runtime, "state", "autonomy.lock");
  config.runtime.stop_file = join(runtime, "state", "stop.requested");
  config.runtime.event_log = join(runtime, "logs", "events.jsonl");
  config.runtime.command_log_directory = join(runtime, "logs", "commands");
  const manager = new IsolatedWorkspaceManager(config);
  const branch = committed ? git(repository, ["branch", "--show-current"]) : "";
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return { root, repository, config, manager, head, branch };
}

function createWorkspace(f: RepositoryFixture, execution = "EXE-0001") {
  return f.manager.create({
    task_id: "WQ-0045",
    execution_id: execution,
    allowed_paths: ["src"],
    forbidden_paths: [".git", ".env", "secrets"],
  });
}

test("refuses a repository without a valid HEAD", (t) => {
  const f = fixture(t, false);
  assert.throws(
    () => createWorkspace(f),
    (error: unknown) => error instanceof IsolatedWorkspaceViolation && /valid HEAD/.test(error.message),
  );
});

test("creates a detached worktree from the exact canonical HEAD", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  assert.equal(git(workspace.worktree_path, ["rev-parse", "HEAD"]), f.head);
  assert.equal(git(workspace.worktree_path, ["rev-parse", "--abbrev-ref", "HEAD"]), "HEAD");
  assert.equal(workspace.base_head, f.head);
});

test("writes occur only in the isolated worktree", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "isolated\n", "utf8");
  assert.equal(readFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "utf8"), "isolated\n");
  assert.equal(readFileSync(join(f.repository, "src", "allowed.txt"), "utf8"), "baseline\n");
});

test("canonical HEAD, branch and status remain unchanged after an isolated mutation", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "isolated\n", "utf8");
  assert.equal(git(f.repository, ["rev-parse", "HEAD"]), f.head);
  assert.equal(git(f.repository, ["branch", "--show-current"]), f.branch);
  assert.equal(git(f.repository, ["status", "--porcelain"]), "");
});

test("produces a non-empty deterministic binary-capable patch", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed\n", "utf8");
  const first = f.manager.extractPatch(workspace.workspace_id);
  const second = f.manager.extractPatch(workspace.workspace_id);
  assert.ok(first.size_bytes > 0);
  assert.equal(first.patch_sha256, second.patch_sha256);
  assert.match(f.manager.readPatch(first).toString("utf8"), /diff --git a\/src\/allowed\.txt b\/src\/allowed\.txt/);
});

test("includes a newly created allowed file in the patch", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "new file.txt"), "new\n", "utf8");
  const artifact = f.manager.extractPatch(workspace.workspace_id);
  assert.deepEqual(artifact.touched_files, ["src/new file.txt"]);
  assert.match(f.manager.readPatch(artifact).toString("utf8"), /new file\.txt/);
});

test("rejects a touched file outside allowed_paths", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  mkdirSync(join(workspace.worktree_path, "docs"), { recursive: true });
  writeFileSync(join(workspace.worktree_path, "docs", "outside.md"), "outside\n", "utf8");
  assert.throws(() => f.manager.extractPatch(workspace.workspace_id), /outside allowed_paths/);
});

test("rejects .env and .git paths", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, ".env"), "TOKEN=not-a-real-secret\n", "utf8");
  assert.throws(() => f.manager.extractPatch(workspace.workspace_id), /Secret-like path/);
  assert.throws(
    () => f.manager.validateTouchedFiles([".git/config"], ["src", ".git"], []),
    /Direct \.git mutation/,
  );
});

test("rejects unsafe task and execution identifiers", (t) => {
  const f = fixture(t);
  assert.throws(() => f.manager.create({
    task_id: "../WQ-0045",
    execution_id: "EXE-0001",
    allowed_paths: ["src"],
    forbidden_paths: [".git"],
  }), /unsafe path characters/);
  assert.throws(() => f.manager.create({
    task_id: "WQ-0045",
    execution_id: "..\\escape",
    allowed_paths: ["src"],
    forbidden_paths: [".git"],
  }), /unsafe path characters/);
});

test("refuses creation when the canonical repository is dirty", (t) => {
  const f = fixture(t);
  writeFileSync(join(f.repository, "src", "allowed.txt"), "user change\n", "utf8");
  assert.throws(() => createWorkspace(f), /not clean enough/);
  assert.equal(readFileSync(join(f.repository, "src", "allowed.txt"), "utf8"), "user change\n");
});

test("cleanup removes a captured isolated worktree", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed\n", "utf8");
  f.manager.extractPatch(workspace.workspace_id);
  const cleaned = f.manager.cleanup(workspace.workspace_id);
  assert.equal(cleaned.state, "CLEANED");
  assert.equal(f.manager.status(workspace.workspace_id).exists, false);
});

test("cleanup is idempotent", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed\n", "utf8");
  f.manager.extractPatch(workspace.workspace_id);
  const first = f.manager.cleanup(workspace.workspace_id);
  const second = f.manager.cleanup(workspace.workspace_id);
  assert.deepEqual(second, first);
});

test("cleanup refuses to discard an uncaptured modification", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed\n", "utf8");
  assert.throws(() => f.manager.cleanup(workspace.workspace_id), /no patch artifact/);
  assert.equal(f.manager.status(workspace.workspace_id).exists, true);
  f.manager.extractPatch(workspace.workspace_id);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed after capture\n", "utf8");
  assert.throws(() => f.manager.cleanup(workspace.workspace_id), /differ from the captured patch/);
  assert.equal(f.manager.status(workspace.workspace_id).exists, true);
});

test("recovery refreshes an interrupted allowed patch and then cleans", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "first capture\n", "utf8");
  f.manager.extractPatch(workspace.workspace_id);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "interrupted after capture\n", "utf8");
  const recovered = f.manager.recover(workspace.workspace_id);
  assert.equal(recovered.state, "CLEANED");
  assert.ok(recovered.patch_path);
  assert.ok(recovered.patch_sha256);
  assert.match(readFileSync(recovered.patch_path, "utf8"), /interrupted after capture/);
});

test("recovery prunes a missing interrupted worktree idempotently", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  rmSync(workspace.worktree_path, { recursive: true, force: true });
  const first = f.manager.recover(workspace.workspace_id);
  const second = f.manager.recover(workspace.workspace_id);
  assert.equal(first.state, "CLEANED");
  assert.deepEqual(second, first);
});

test("never changes master or creates a remote while producing and cleaning a patch", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "proposal\n", "utf8");
  f.manager.extractPatch(workspace.workspace_id);
  f.manager.cleanup(workspace.workspace_id);
  assert.equal(git(f.repository, ["branch", "--show-current"]), f.branch);
  assert.equal(git(f.repository, ["rev-parse", "HEAD"]), f.head);
  assert.equal(git(f.repository, ["remote"]), "");
  assert.equal(git(f.repository, ["status", "--porcelain"]), "");
});

test("verifies patch integrity and rejects a modified artifact", (t) => {
  const f = fixture(t);
  const workspace = createWorkspace(f);
  writeFileSync(join(workspace.worktree_path, "src", "allowed.txt"), "changed\n", "utf8");
  const artifact = f.manager.extractPatch(workspace.workspace_id);
  writeFileSync(artifact.patch_path, "tampered\n", "utf8");
  assert.throws(() => f.manager.readPatch(artifact), /hash verification failed/);
});
