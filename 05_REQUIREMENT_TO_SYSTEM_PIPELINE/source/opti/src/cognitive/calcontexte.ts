import { fold, jaccard, stableId, tokens } from "./ids.js";
import type { CognitiveRelation, ContextSelection, SelectionEntry, Tile } from "./types.js";

function rounded(value: number): number { return Math.round(value * 10000) / 10000; }

export class CalContexteSelector {
  select(question: string, tiles: Tile[], relations: CognitiveRelation[], budget = 12000, allowedTypes?: Tile["tile_type"][]): ContextSelection {
    if (question.trim() === "") throw new Error("A context question is required.");
    if (!Number.isInteger(budget) || budget <= 0) throw new Error("Context budget must be a positive integer.");
    const questionTokens = tokens(question);
    const candidates = allowedTypes ? tiles.filter((tile) => allowedTypes.includes(tile.tile_type)) : tiles;
    const ranked = candidates.map((tile): SelectionEntry => {
      const body = tile.claims.map((claim) => claim.content).join("\n");
      const lexical = jaccard(questionTokens, tokens(body));
      const subject = fold(question).includes(fold(tile.subject)) ? 1 : 0;
      const dependencyRelations = relations.filter((relation) => relation.from === tile.tile_id && relation.relation_type === "depends_on");
      const contradictionRelations = relations.filter((relation) => (relation.from === tile.tile_id || relation.to === tile.tile_id) && relation.relation_type === "contradicts");
      const dependency = Math.min(1, dependencyRelations.length / 3);
      const sourceAuthority = tile.source_id === "SRC-0001" ? 1 : 0.75;
      const epistemic = tile.epistemic_status === "source_explicit" ? 1 : tile.epistemic_status === "reconstructed" ? 0.7 : 0.4;
      const freshness = 1;
      const contradiction = contradictionRelations.length > 0 ? Math.min(1, contradictionRelations.length / 3) : 0;
      const total = rounded(lexical * 0.3 + subject * 0.3 + dependency * 0.05 + sourceAuthority * 0.15 + epistemic * 0.15 + freshness * 0.05 - contradiction * 0.1);
      const reasons = [
        ...(subject === 1 ? [`Le sujet canonique « ${tile.subject} » apparaît dans la question.`] : []),
        ...(lexical > 0 ? [`Recouvrement lexical mesuré à ${rounded(lexical)}.`] : []),
        `Autorité de source=${sourceAuthority}; statut épistémique=${tile.epistemic_status}.`,
        ...(dependencyRelations.length > 0 ? [`${dependencyRelations.length} dépendance(s) suivie(s).`] : []),
      ];
      return {
        tile_id: tile.tile_id, selected: false,
        scores: { lexical: rounded(lexical), semantic: null, subject, dependency: rounded(dependency), source_authority: sourceAuthority, epistemic, freshness, contradiction, total },
        reasons, exclusion_reasons: [], estimated_chars: body.length,
      };
    }).sort((a, b) => b.scores.total - a.scores.total || a.tile_id.localeCompare(b.tile_id));

    let used = 0;
    for (const entry of ranked) {
      if (entry.scores.subject === 0 && entry.scores.lexical < 0.1) {
        entry.exclusion_reasons.push("Aucune correspondance de sujet et recouvrement lexical inférieur à 0.1 ; l'autorité seule ne peut pas justifier l'inclusion.");
        continue;
      }
      if (entry.scores.total < 0.25) { entry.exclusion_reasons.push("Score détaillé inférieur au seuil minimal 0.25."); continue; }
      if (used + entry.estimated_chars > budget) { entry.exclusion_reasons.push(`Budget dépassé (${used}+${entry.estimated_chars}>${budget}).`); continue; }
      entry.selected = true; used += entry.estimated_chars;
      entry.reasons.push(`Incluse dans le budget cumulatif (${used}/${budget} caractères).`);
    }
    const selectedTiles = ranked.filter((entry) => entry.selected).map((entry) => entry.tile_id);
    const dependencyPaths = relations
      .filter((relation) => relation.relation_type === "depends_on" && selectedTiles.includes(relation.from))
      .map((relation) => [relation.from, relation.to]);
    const contradictions = relations
      .filter((relation) => relation.relation_type === "contradicts" && (selectedTiles.includes(relation.from) || selectedTiles.includes(relation.to)))
      .map((relation) => relation.relation_id);
    return {
      selection_id: stableId("SEL", question, budget, ...selectedTiles), question, budget,
      selected_tiles: selectedTiles, entries: ranked, dependency_paths: dependencyPaths,
      contradictions_retrieved: contradictions, semantic_method: "unavailable", created_at: new Date().toISOString(),
    };
  }
}
