import { fold, jaccard, stableId, tokens } from "./ids.js";
import type { Claim, CoherenceDiagnostic, ContextSelection, DiagnosticEntry, Tile } from "./types.js";

function entry(kind: string, claims: Claim[], tiles: Tile[], justification: string, method: string, confidence: DiagnosticEntry["confidence"] = "high"): DiagnosticEntry {
  const claimIds = claims.map((claim) => claim.claim_id);
  const tileIds = [...new Set(tiles.filter((tile) => tile.claims.some((claim) => claimIds.includes(claim.claim_id))).map((tile) => tile.tile_id))];
  return {
    id: stableId("DIAITEM", kind, ...claimIds), claim_ids: claimIds, tile_ids: tileIds,
    atom_ids: [...new Set(claims.flatMap((claim) => claim.atom_ids))], justification, confidence, method,
  };
}

function withoutNegation(value: string): string[] {
  return tokens(fold(value).replace(/\b(ne|n|pas|jamais|interdit)\b/g, " "));
}

export class CoherentalDiagnosticEngine {
  diagnose(question: string, selection: ContextSelection, allTiles: Tile[]): CoherenceDiagnostic {
    const tiles = allTiles.filter((tile) => selection.selected_tiles.includes(tile.tile_id));
    const claims = tiles.flatMap((tile) => tile.claims);
    const duplicated: DiagnosticEntry[] = [];
    const contradictions: DiagnosticEntry[] = [];
    const ambiguous: DiagnosticEntry[] = [];
    const missing: DiagnosticEntry[] = [];
    const unsupported: DiagnosticEntry[] = [];
    const issueClaims = new Set<string>();
    const byText = new Map<string, Claim[]>();
    for (const claim of claims) byText.set(fold(claim.content).replace(/\s+/g, " ").trim(), [...(byText.get(fold(claim.content).replace(/\s+/g, " ").trim()) ?? []), claim]);
    for (const group of byText.values()) if (group.length > 1) {
      duplicated.push(entry("duplicate", group, tiles, "Contenu source identique présent dans plusieurs affirmations sélectionnées.", "exact_normalized_content/v1"));
      group.forEach((claim) => issueClaims.add(claim.claim_id));
    }
    for (let left = 0; left < claims.length; left += 1) for (let right = left + 1; right < claims.length; right += 1) {
      const a = claims[left]; const b = claims[right]; if (!a || !b) continue;
      const aNeg = /\b(ne|n['’]|pas|jamais|interdit)\b/i.test(a.content);
      const bNeg = /\b(ne|n['’]|pas|jamais|interdit)\b/i.test(b.content);
      const similarity = jaccard(withoutNegation(a.content), withoutNegation(b.content));
      if (aNeg !== bNeg && similarity >= 0.55) {
        contradictions.push(entry("contradiction", [a, b], tiles, `Polarités opposées avec similarité lexicale ${Math.round(similarity * 1000) / 1000}.`, "negation_plus_lexical_similarity/v1", "medium"));
        issueClaims.add(a.claim_id); issueClaims.add(b.claim_id);
      }
    }
    for (const claim of claims) {
      const text = fold(claim.content);
      if (/vraie definition|reellement|ne connait pas|pourquoi/.test(text) || tokens(claim.content).length <= 1) {
        ambiguous.push(entry("ambiguous", [claim], tiles, "Le passage mentionne le concept ou l'absence de définition sans fournir un contrat opérationnel complet.", "definition_gap_pattern/v1", "high"));
        issueClaims.add(claim.claim_id);
      }
      if (/pourquoi.*separe|lien avec/.test(text)) {
        missing.push(entry("missing_dependency", [claim], tiles, "Une frontière ou relation est demandée/citée sans justification contractuelle dans l'atome.", "relationship_gap_pattern/v1", "high"));
        issueClaims.add(claim.claim_id);
      }
      if (claim.epistemic_status !== "source_explicit" && claim.atom_ids.length === 0) {
        unsupported.push(entry("unsupported", [claim], tiles, "Affirmation non explicite sans atome de soutien.", "provenance_completeness/v1"));
        issueClaims.add(claim.claim_id);
      }
    }
    const compatible = claims.filter((claim) => !issueClaims.has(claim.claim_id)).map((claim) => entry("compatible", [claim], tiles, "Aucune contradiction structurelle n'a été détectée pour cette affirmation explicite.", "absence_of_detected_conflict/v1", "medium"));
    const resolutions = [...ambiguous, ...missing].map((problem) => ({
      ...problem,
      id: stableId("DIAITEM", "resolution", problem.id),
      justification: "Conserver cette lacune comme inconnue explicite et demander une source définissant le contrat ou la frontière.",
      method: "evidence_first_resolution/v1",
    }));
    return {
      diagnostic_id: stableId("DIA", question, selection.selection_id, ...claims.map((claim) => claim.claim_id)),
      question,
      policy: { single_score_rejected: true, diagnostic_shape: "structured_categories", source_refs: ["SRC-0008"] },
      compatible_claims: compatible, tensions: [], contradictions, missing_dependencies: missing,
      ambiguous_terms: ambiguous, unsupported_inferences: unsupported, duplicated_claims: duplicated,
      obsolete_claims: [], suggested_resolutions: resolutions, created_at: new Date().toISOString(),
    };
  }
}
