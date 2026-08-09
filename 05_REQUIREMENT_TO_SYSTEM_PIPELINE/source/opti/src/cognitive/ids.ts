import { createHash } from "node:crypto";

export function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

export function stableId(prefix: string, ...parts: Array<string | number>): string {
  return `${prefix}-${sha256(parts.join("\u001f")).slice(0, 16).toUpperCase()}`;
}

export function fold(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

const STOP = new Set(["a", "au", "aux", "avec", "ce", "ces", "de", "des", "du", "et", "il", "la", "le", "les", "ne", "ou", "par", "pas", "pour", "que", "quel", "quelle", "qui", "son", "sa", "ses", "un", "une", "doit"]);

export function tokens(value: string): string[] {
  return [...new Set(fold(value).match(/[a-z0-9][a-z0-9-]{1,}/g) ?? [])].filter((token) => !STOP.has(token));
}

export function jaccard(left: string[], right: string[]): number {
  const a = new Set(left); const b = new Set(right);
  if (a.size === 0 && b.size === 0) return 0;
  let intersection = 0;
  for (const item of a) if (b.has(item)) intersection += 1;
  return intersection / (a.size + b.size - intersection);
}
