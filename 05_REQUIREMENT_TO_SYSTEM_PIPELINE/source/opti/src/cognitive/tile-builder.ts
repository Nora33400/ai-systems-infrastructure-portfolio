import { readFileSync } from "node:fs";
import { parse } from "yaml";
import { fold, stableId } from "./ids.js";
import type { Atom, Claim, Tile } from "./types.js";

interface Registry { modules?: Array<{ id?: string; name?: string }> }

export function registrySubjects(registryPath: string): string[] {
  const registry = parse(readFileSync(registryPath, "utf8")) as Registry;
  return [...new Set((registry.modules ?? []).flatMap((entry) => entry.name ? [entry.name.split(" — ")[0]?.trim() ?? entry.name] : []))]
    .filter((name) => name.length >= 3);
}

function tileType(content: string): Tile["tile_type"] {
  const value = fold(content);
  if (/\b(ne doit|ne pas|interdit|fusionner|jamais)\b/.test(value)) return "negative_constraint";
  if (/vraie definition|reellement|ne connait pas|a definir|reste ouvert/.test(value)) return "open_definition";
  if (/architecture|module|role|responsabilit|lien avec|separe/.test(value)) return "architectural_requirement";
  return "source_excerpt";
}

export class TileBuilder {
  constructor(private readonly subjects: string[]) {}

  build(sourceId: string, atoms: Atom[], createdAt = new Date().toISOString()): Tile[] {
    const tiles: Tile[] = [];
    for (const subject of this.subjects) {
      const needle = fold(subject);
      const matching = atoms.filter((atom) => fold(atom.content).includes(needle));
      if (matching.length === 0) continue;
      const atomIds = matching.map((atom) => atom.atom_id);
      const claims: Claim[] = matching.map((atom) => ({
        claim_id: stableId("CLM", sourceId, subject, atom.atom_id, atom.content_hash),
        content: atom.content,
        epistemic_status: "source_explicit",
        atom_ids: [atom.atom_id],
        source_refs: [`${sourceId}:L${atom.source_position.start_line}-L${atom.source_position.end_line}`],
      }));
      const combined = matching.map((atom) => atom.content).join("\n");
      tiles.push({
        schema_version: 1,
        tile_id: stableId("TILE", sourceId, subject, ...atomIds),
        tile_type: tileType(combined),
        subject,
        source_id: sourceId,
        atom_ids: atomIds,
        claims,
        epistemic_status: "source_explicit",
        provenance: { source_ids: [sourceId], atom_ids: atomIds, method: "deterministic_subject_lexical_grouping/v1" },
        confidence: { level: "high", basis: "Every included atom contains the canonical subject name." },
        version: 1,
        created_at: createdAt,
      });
    }
    return tiles.sort((a, b) => a.subject.localeCompare(b.subject));
  }

  validateModelProposal(value: unknown, allowedAtoms: Map<string, string>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    if (!value || typeof value !== "object" || Array.isArray(value)) return { valid: false, errors: ["proposal must be an object"] };
    const candidate = value as { subject?: unknown; atom_ids?: unknown; claims?: unknown };
    if (typeof candidate.subject !== "string" || candidate.subject.trim() === "") errors.push("subject is required");
    if (!Array.isArray(candidate.atom_ids) || candidate.atom_ids.length === 0 || candidate.atom_ids.some((id) => typeof id !== "string" || !allowedAtoms.has(id))) {
      errors.push("all atom_ids must reference supplied atoms");
    }
    if (!Array.isArray(candidate.claims) || candidate.claims.length === 0) errors.push("claims must be a non-empty array");
    else for (const claim of candidate.claims) {
      const content = claim && typeof claim === "object" ? (claim as { content?: unknown }).content : undefined;
      if (typeof content !== "string") errors.push("every claim requires content");
      else if (![...allowedAtoms.values()].includes(content)) errors.push("claim content must be copied verbatim from a supplied atom");
    }
    return { valid: errors.length === 0, errors };
  }
}
