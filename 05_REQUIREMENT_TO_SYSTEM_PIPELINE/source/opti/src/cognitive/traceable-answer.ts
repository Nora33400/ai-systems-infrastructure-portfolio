import { fold, jaccard, stableId, tokens } from "./ids.js";
import type { AnswerAssertion, Claim, CoherenceDiagnostic, ContextSelection, Tile, TraceableAnswer } from "./types.js";

export class AnswerSupportVerifier {
  verify(answer: TraceableAnswer, claims: Claim[]): { passed: boolean; issues: string[] } {
    const byId = new Map(claims.map((claim) => [claim.claim_id, claim]));
    const issues: string[] = [];
    for (const assertion of answer.assertions) {
      if (assertion.support_claim_ids.length === 0) issues.push(`Unsupported assertion without claim ids: ${assertion.text}`);
      const support = assertion.support_claim_ids.flatMap((id) => byId.get(id) ? [byId.get(id) as Claim] : []);
      for (const id of assertion.support_claim_ids) if (!byId.has(id)) issues.push(`Unknown supporting claim: ${id}`);
      if (assertion.epistemic_status === "source_explicit" && !support.some((claim) => claim.content === assertion.text)) {
        issues.push(`Explicit assertion is not verbatim source content: ${assertion.text}`);
      }
      if ((assertion.epistemic_status === "reconstructed" || assertion.epistemic_status === "inferred") && support.length > 0) {
        const overlap = jaccard(tokens(assertion.text), tokens(support.map((claim) => claim.content).join(" ")));
        if (overlap < 0.05) issues.push(`Reconstruction lacks lexical support (${overlap}): ${assertion.text}`);
      }
    }
    return { passed: issues.length === 0, issues };
  }
}

export class TraceableAnswerBuilder {
  constructor(private readonly verifier = new AnswerSupportVerifier()) {}

  build(question: string, selection: ContextSelection, diagnostic: CoherenceDiagnostic, tiles: Tile[]): TraceableAnswer {
    const selected = tiles.filter((tile) => selection.selected_tiles.includes(tile.tile_id));
    const rankedEntries = selection.entries.filter((entry) => entry.selected).sort((a, b) => b.scores.subject - a.scores.subject || b.scores.total - a.scores.total);
    const primaryTile = selected.find((tile) => tile.tile_id === rankedEntries[0]?.tile_id) ?? selected[0];
    if (!primaryTile) throw new Error("Cannot answer without a selected tile.");
    const subject = primaryTile.subject;
    const allClaims = selected.flatMap((tile) => tile.claims);
    const subjectFolded = fold(subject);
    const directness = (claim: Claim): number => {
      const content = fold(claim.content);
      let score = content.includes(subjectFolded) ? 1 : -10;
      if (new RegExp(`pourquoi ${subjectFolded} (est |reste )?separe`).test(content)) score += 6;
      if (content.includes("fusionner") && content.includes(subjectFolded)) score += 5;
      if (content.includes("definition") && content.includes(subjectFolded)) score += 4;
      if (content.includes(`lien avec ${subjectFolded}`)) score -= 4;
      if (content.includes("modules/") || content.includes("readme.md")) score -= 5;
      const lines = claim.content.split("\n").filter(Boolean);
      if (lines.length >= 4 && lines.every((line) => line.trim().split(/\s+/u).length <= 4)) score -= 4;
      return score;
    };
    const relevant = allClaims
      .filter((claim) => directness(claim) >= 4)
      .sort((a, b) => {
        return directness(b) - directness(a) || a.content.length - b.content.length;
      }).slice(0, 5);
    if (relevant.length === 0) throw new Error(`No directly relevant source claim supports the question about ${subject}.`);
    const assertions: AnswerAssertion[] = relevant.map((claim) => ({ text: claim.content, epistemic_status: "source_explicit", support_claim_ids: [claim.claim_id] }));
    const gaps = relevant.filter((claim) => /vraie définition|réellement|ne connaît pas|pourquoi/i.test(claim.content));
    if (gaps.length > 0) assertions.push({
      text: `La définition opérationnelle complète de ${subject} demeure inconnue dans cette source.`,
      epistemic_status: "unknown", support_claim_ids: gaps.map((claim) => claim.claim_id),
    });
    const explicit = assertions.filter((item) => item.epistemic_status === "source_explicit");
    const reconstructed = assertions.filter((item) => item.epistemic_status !== "source_explicit");
    const text = [
      ...(reconstructed.length > 0 ? ["Réponse traçable et limite :", ...reconstructed.map((item) => `- [${item.epistemic_status}] ${item.text}`), ""] : []),
      `Éléments explicitement présents dans ${primaryTile.source_id} :`,
      ...explicit.map((item) => `- ${item.text}`),
    ].join("\n");
    const answer: TraceableAnswer = {
      answer_id: stableId("ANS", question, diagnostic.diagnostic_id, ...assertions.map((item) => item.text)),
      question, text, assertions,
      used_tiles: selected.map((tile) => tile.tile_id),
      used_atoms: [...new Set(relevant.flatMap((claim) => claim.atom_ids))],
      explicit_claims: explicit.flatMap((item) => item.support_claim_ids),
      inferred_claims: reconstructed.flatMap((item) => item.support_claim_ids),
      unresolved_questions: diagnostic.ambiguous_terms.map((item) => item.justification),
      confidence: gaps.length > 0 ? "medium" : "high",
      support_check: { passed: false, issues: [] }, created_at: new Date().toISOString(),
    };
    answer.support_check = this.verifier.verify(answer, allClaims);
    if (!answer.support_check.passed) throw new Error(`Answer support verification failed: ${answer.support_check.issues.join("; ")}`);
    return answer;
  }
}
