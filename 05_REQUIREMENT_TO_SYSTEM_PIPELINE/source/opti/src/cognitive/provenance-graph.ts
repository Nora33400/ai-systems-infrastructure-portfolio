import { stableId } from "./ids.js";
import type { Atom, CognitiveRelation, Tile } from "./types.js";

export class ProvenanceGraphBuilder {
  build(sourceId: string, atoms: Atom[], tiles: Tile[], createdAt = new Date().toISOString()): CognitiveRelation[] {
    const relations: CognitiveRelation[] = [];
    const add = (from: string, to: string, relationType: CognitiveRelation["relation_type"], status: CognitiveRelation["status"], justification: string): void => {
      relations.push({
        schema_version: 1,
        relation_id: stableId("REL", from, relationType, to),
        from, to, relation_type: relationType,
        provenance: { source_refs: [sourceId], method: "deterministic_provenance_graph/v1" },
        confidence: status === "inferred" ? "medium" : "high",
        justification, status, created_at: createdAt,
      });
    };
    for (const atom of atoms) add(sourceId, atom.atom_id, "contains", "explicit_structure", "The atom was parsed from this exact source.");
    for (const tile of tiles) {
      for (const atomId of tile.atom_ids) add(tile.tile_id, atomId, "derived_from", "generated", "The deterministic tile groups this subject-matching atom.");
      for (const claim of tile.claims) {
        add(tile.tile_id, claim.claim_id, "contains", "generated", "The claim is stored in this tile.");
        for (const atomId of claim.atom_ids) add(atomId, claim.claim_id, "supports", "source_explicit", "The claim content is copied verbatim from the atom.");
      }
    }
    return relations;
  }

  usedInAnswer(answerId: string, tileIds: string[], claimIds: string[], sourceId: string, createdAt = new Date().toISOString()): CognitiveRelation[] {
    return [...tileIds, ...claimIds].map((id) => ({
      schema_version: 1,
      relation_id: stableId("REL", answerId, "used_in_response", id),
      from: answerId, to: id, relation_type: "used_in_response",
      provenance: { source_refs: [sourceId], method: "answer_support_registration/v1" },
      confidence: "high", justification: "The persisted answer explicitly declares this supporting object.",
      status: "explicit_structure", created_at: createdAt,
    }));
  }
}
