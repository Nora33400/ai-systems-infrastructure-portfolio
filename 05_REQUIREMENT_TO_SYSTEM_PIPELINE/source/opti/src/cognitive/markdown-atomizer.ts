import { sha256, stableId } from "./ids.js";
import type { Atom, AtomType, AtomizationReport } from "./types.js";

export const MARKDOWN_PARSER_VERSION = "aione-markdown-atoms/1.0.0";

function structuralType(line: string): AtomType | null {
  if (/^ {0,3}#{1,6}\s+\S/.test(line)) return "heading";
  if (/^ {0,3}(?:[-*_]\s*){3,}$/.test(line)) return "separator";
  if (/^\s*(?:[-+*]|\d+[.)])\s+\S/.test(line)) return "list_item";
  if (/^\s*>/.test(line)) return "blockquote";
  return null;
}

export class MarkdownAtomizer {
  atomize(sourceId: string, content: string, executionId: string, createdAt = new Date().toISOString()): { atoms: Atom[]; report: AtomizationReport } {
    if (content.trim() === "") throw new Error("Cannot atomize an empty Markdown source.");
    const sourceHash = sha256(Buffer.from(content, "utf8"));
    const lines = content.replace(/\r\n/g, "\n").split("\n");
    if (content.endsWith("\n")) lines.pop();
    const units: Array<{ type: AtomType; content: string; start: number; end: number }> = [];
    let ignoredBlankLines = 0;

    for (let index = 0; index < lines.length;) {
      const line = lines[index] ?? "";
      if (line.trim() === "") { ignoredBlankLines += 1; index += 1; continue; }
      const fence = /^\s*(```|~~~)/.exec(line)?.[1];
      if (fence) {
        const start = index;
        index += 1;
        while (index < lines.length) {
          const current = lines[index] ?? "";
          index += 1;
          if (new RegExp(`^\\s*${fence}`).test(current)) break;
        }
        units.push({ type: "code_block", content: lines.slice(start, index).join("\n"), start: start + 1, end: index });
        continue;
      }
      const directType = structuralType(line);
      if (directType && directType !== "blockquote") {
        units.push({ type: directType, content: line, start: index + 1, end: index + 1 });
        index += 1;
        continue;
      }
      if (directType === "blockquote") {
        const start = index;
        while (index < lines.length && /^\s*>/.test(lines[index] ?? "")) index += 1;
        units.push({ type: "blockquote", content: lines.slice(start, index).join("\n"), start: start + 1, end: index });
        continue;
      }
      const start = index;
      while (index < lines.length) {
        const current = lines[index] ?? "";
        if (current.trim() === "" || /^\s*(```|~~~)/.test(current) || structuralType(current)) break;
        index += 1;
      }
      if (index === start) index += 1;
      const body = lines.slice(start, index).join("\n");
      units.push({ type: body.includes("\n") ? "paragraph" : "isolated_line", content: body, start: start + 1, end: index });
    }

    const occurrences = new Map<string, number>();
    const atoms = units.map((unit): Atom => {
      const contentHash = sha256(Buffer.from(unit.content, "utf8"));
      const key = `${unit.type}:${contentHash}`;
      const occurrence = (occurrences.get(key) ?? 0) + 1;
      occurrences.set(key, occurrence);
      return {
        schema_version: 1,
        atom_id: stableId("ATM", sourceId, unit.type, contentHash, occurrence),
        source_id: sourceId,
        content: unit.content,
        source_position: { start_line: unit.start, end_line: unit.end },
        content_hash: `sha256:${contentHash}`,
        atom_type: unit.type,
        epistemic_status: "observed",
        created_at: createdAt,
        valid: true,
      };
    });
    const counts: Record<string, number> = {};
    for (const atom of atoms) counts[atom.atom_type] = (counts[atom.atom_type] ?? 0) + 1;
    return {
      atoms,
      report: {
        source_id: sourceId, parser_version: MARKDOWN_PARSER_VERSION, source_hash: `sha256:${sourceHash}`,
        line_count: lines.length, atom_count: atoms.length, counts_by_type: counts,
        ignored_blank_lines: ignoredBlankLines, idempotent: false, execution_id: executionId,
      },
    };
  }
}
