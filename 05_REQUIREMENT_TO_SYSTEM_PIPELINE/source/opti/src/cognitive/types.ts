export type AtomType = "heading" | "paragraph" | "list_item" | "blockquote" | "code_block" | "separator" | "isolated_line";
export type ClaimStatus = "source_explicit" | "reconstructed" | "inferred" | "hypothetical" | "normative";
export type RelationType = "derived_from" | "contains" | "supports" | "contradicts" | "depends_on" | "clarifies" | "replaces" | "example_of" | "implies" | "implements" | "used_in_response";

export interface Atom {
  schema_version: 1; atom_id: string; source_id: string; content: string;
  source_position: { start_line: number; end_line: number };
  content_hash: string; atom_type: AtomType; epistemic_status: "observed";
  created_at: string; valid: boolean;
}

export interface AtomizationReport {
  source_id: string; parser_version: string; source_hash: string; line_count: number;
  atom_count: number; counts_by_type: Record<string, number>; ignored_blank_lines: number;
  idempotent: boolean; execution_id: string;
}

export interface Claim {
  claim_id: string; content: string; epistemic_status: ClaimStatus;
  atom_ids: string[]; source_refs: string[];
}

export interface Tile {
  schema_version: 1; tile_id: string;
  tile_type: "source_excerpt" | "architectural_requirement" | "negative_constraint" | "open_definition";
  subject: string; source_id: string; atom_ids: string[]; claims: Claim[];
  epistemic_status: ClaimStatus;
  provenance: { source_ids: string[]; atom_ids: string[]; method: string };
  confidence: { level: "low" | "medium" | "high"; basis: string };
  version: number; created_at: string;
}

export interface CognitiveRelation {
  schema_version: 1; relation_id: string; from: string; to: string;
  relation_type: RelationType; provenance: Record<string, unknown>;
  confidence: "low" | "medium" | "high"; justification: string;
  status: "explicit_structure" | "source_explicit" | "generated" | "inferred" | "rejected";
  created_at: string;
}

export interface ScoreBreakdown {
  lexical: number; semantic: number | null; subject: number; dependency: number;
  source_authority: number; epistemic: number; freshness: number; contradiction: number;
  total: number;
}

export interface SelectionEntry {
  tile_id: string; selected: boolean; scores: ScoreBreakdown; reasons: string[];
  exclusion_reasons: string[]; estimated_chars: number;
}

export interface ContextSelection {
  selection_id: string; question: string; budget: number; selected_tiles: string[];
  entries: SelectionEntry[]; dependency_paths: string[][]; contradictions_retrieved: string[];
  semantic_method: "unavailable" | "embedding"; created_at: string;
}

export interface DiagnosticEntry {
  id: string; claim_ids: string[]; tile_ids: string[]; atom_ids: string[];
  justification: string; confidence: "low" | "medium" | "high"; method: string;
}

export interface CoherenceDiagnostic {
  diagnostic_id: string; question: string;
  policy: { single_score_rejected: true; diagnostic_shape: "structured_categories"; source_refs: ["SRC-0008"] };
  compatible_claims: DiagnosticEntry[]; tensions: DiagnosticEntry[]; contradictions: DiagnosticEntry[];
  missing_dependencies: DiagnosticEntry[]; ambiguous_terms: DiagnosticEntry[]; unsupported_inferences: DiagnosticEntry[];
  duplicated_claims: DiagnosticEntry[]; obsolete_claims: DiagnosticEntry[]; suggested_resolutions: DiagnosticEntry[];
  created_at: string;
}

export interface AnswerAssertion {
  text: string; epistemic_status: "source_explicit" | "reconstructed" | "inferred" | "unknown";
  support_claim_ids: string[];
}

export interface TraceableAnswer {
  answer_id: string; question: string; text: string; assertions: AnswerAssertion[];
  used_tiles: string[]; used_atoms: string[]; explicit_claims: string[]; inferred_claims: string[];
  unresolved_questions: string[]; confidence: "low" | "medium" | "high";
  support_check: { passed: boolean; issues: string[] }; created_at: string;
}

export type CognitiveStage = "created" | "ingested" | "tiles_built" | "graph_built" | "context_selected" | "diagnosed" | "answered" | "completed" | "failed";

export interface CognitiveExecution {
  execution_id: string; source_id: string; source_path: string; question: string;
  stage: CognitiveStage; status: "running" | "interrupted" | "completed" | "failed";
  atom_ids: string[]; tile_ids: string[]; relation_ids: string[];
  selection_id: string | null; diagnostic_id: string | null; answer_id: string | null;
  created_at: string; updated_at: string; error: string | null; version: number;
}

export interface CognitiveReceipt {
  receipt_id: string; task_id: string; execution_id: string; inputs: Record<string, unknown>;
  files_read: string[]; files_modified: string[]; commands_executed: string[];
  test_results: Array<Record<string, unknown>>; artifacts_produced: string[];
  state_before: string; state_after: string; errors: string[]; decisions: string[];
  known_limits: string[]; created_at: string;
}
