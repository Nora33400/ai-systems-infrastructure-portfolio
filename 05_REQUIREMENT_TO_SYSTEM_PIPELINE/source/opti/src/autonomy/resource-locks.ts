import { posix } from "node:path";
import type { TaskRecord } from "./types.js";

function normalizedPath(value: string): string {
  const portable = value.trim().replace(/\\/g, "/").replace(/^\.\//, "");
  const normalized = posix.normalize(portable).replace(/^\/+|\/+$/g, "").toLowerCase();
  return normalized === "." ? "" : normalized;
}

export function normalizeResourceKey(value: string): string {
  const trimmed = value.trim();
  if (trimmed.toLowerCase().startsWith("path:")) {
    return `path:${normalizedPath(trimmed.slice(5))}`;
  }
  return trimmed.toLowerCase();
}

export function resourceKeysConflict(leftInput: string, rightInput: string): boolean {
  const left = normalizeResourceKey(leftInput);
  const right = normalizeResourceKey(rightInput);
  if (left === right) return true;
  if (!left.startsWith("path:") || !right.startsWith("path:")) return false;
  const leftPath = left.slice(5);
  const rightPath = right.slice(5);
  if (!leftPath || !rightPath) return true;
  return leftPath.startsWith(`${rightPath}/`) || rightPath.startsWith(`${leftPath}/`);
}

export function taskResourceKeys(task: TaskRecord): string[] {
  const keys = new Set<string>([`task:${task.id.toLowerCase()}`]);
  for (const path of task.allowed_paths) {
    const normalized = normalizeResourceKey(`path:${path}`);
    if (normalized !== "path:") keys.add(normalized);
  }
  const gpu = task.resource_budget.gpu?.trim().toLowerCase();
  if (gpu && gpu !== "none") keys.add(`gpu:${gpu}`);
  return [...keys].sort();
}
