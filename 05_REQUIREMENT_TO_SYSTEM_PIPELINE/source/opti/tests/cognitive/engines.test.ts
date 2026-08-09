import test from "node:test";
import assert from "node:assert/strict";
import { CalContexteSelector } from "../../src/cognitive/calcontexte.js";
import { CoherentalDiagnosticEngine } from "../../src/cognitive/coherental-diagnostic.js";
import { AnswerSupportVerifier, TraceableAnswerBuilder } from "../../src/cognitive/traceable-answer.js";
import { TileBuilder } from "../../src/cognitive/tile-builder.js";
import type { Claim, ContextSelection, Tile, TraceableAnswer } from "../../src/cognitive/types.js";

function claim(id: string, content: string): Claim { return { claim_id: id, content, epistemic_status: "source_explicit", atom_ids: [`ATM-${id}`], source_refs: ["SRC-0001:L1-L1"] }; }
function tile(id: string, subject: string, claims: Claim[]): Tile {
  return { schema_version: 1, tile_id: id, tile_type: "architectural_requirement", subject, source_id: "SRC-0001", atom_ids: claims.flatMap((item) => item.atom_ids), claims,
    epistemic_status: "source_explicit", provenance: { source_ids: ["SRC-0001"], atom_ids: claims.flatMap((item) => item.atom_ids), method: "test" },
    confidence: { level: "high", basis: "test" }, version: 1, created_at: new Date().toISOString() };
}

test("CalContexte exposes every sub-score and authority alone cannot select an irrelevant tile", () => {
  const relevant = tile("TILE-AAAAAAAAAAAAAAAA", "Cohérental", [claim("CLM-A", "Pourquoi Cohérental est séparé de CorrexAI ?")]);
  const irrelevant = tile("TILE-BBBBBBBBBBBBBBBB", "TileMindFS", [claim("CLM-B", "Archive mémoire persistante")]);
  const selection = new CalContexteSelector().select("Quel rôle Cohérental doit-il jouer ?", [irrelevant, relevant], [], 1000);
  assert.deepEqual(selection.selected_tiles, [relevant.tile_id]);
  assert.equal(selection.entries.find((entry) => entry.tile_id === irrelevant.tile_id)?.selected, false);
  assert.equal(selection.entries[0]?.scores.semantic, null);
  assert.match(selection.entries.find((entry) => entry.tile_id === irrelevant.tile_id)?.exclusion_reasons.join(" ") ?? "", /autorité seule/);
});

test("Cohérental distinguishes contradiction, definition gaps and a structured no-single-score policy", () => {
  const positive = claim("CLM-P", "Cohérental doit fusionner les rôles logiques.");
  const negative = claim("CLM-N", "Cohérental ne doit pas fusionner les rôles logiques.");
  const gap = claim("CLM-G", "Pourquoi Cohérental est séparé de CorrexAI ?");
  const value = tile("TILE-CCCCCCCCCCCCCCCC", "Cohérental", [positive, negative, gap]);
  const selection: ContextSelection = { selection_id: "SEL-X", question: "rôle", budget: 1000, selected_tiles: [value.tile_id], entries: [], dependency_paths: [], contradictions_retrieved: [], semantic_method: "unavailable", created_at: new Date().toISOString() };
  const diagnostic = new CoherentalDiagnosticEngine().diagnose("rôle", selection, [value]);
  assert.equal(diagnostic.policy.single_score_rejected, true);
  assert.equal(diagnostic.contradictions.length, 1);
  assert.ok(diagnostic.ambiguous_terms.length >= 1);
  assert.ok(diagnostic.missing_dependencies.length >= 1);
});

test("answer provenance verifier rejects unsupported or non-verbatim assertions", () => {
  const support = claim("CLM-S", "Cohérental est distinct.");
  const verifier = new AnswerSupportVerifier();
  const answer = { assertions: [{ text: "Affirmation inventée", epistemic_status: "source_explicit", support_claim_ids: [] }] } as unknown as TraceableAnswer;
  assert.equal(verifier.verify(answer, [support]).passed, false);
  const proposal = new TileBuilder(["Cohérental"]).validateModelProposal({ subject: "Cohérental", atom_ids: ["ATM-X"], claims: [{ content: "inventé" }] }, new Map([["ATM-X", "source exacte"]]));
  assert.equal(proposal.valid, false);
});
