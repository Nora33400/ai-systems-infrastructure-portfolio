import type { AutonomyConfig } from "../autonomy/types.js";
import { OllamaClient } from "../autonomy/ollama-client.js";
import { sha256, stableId } from "./ids.js";
import { CognitiveStore } from "./cognitive-store.js";
import { TileBuilder } from "./tile-builder.js";
import type { Atom } from "./types.js";

interface Proposal {
  subject: string;
  atom_ids: string[];
  claims: Array<{ content: string }>;
}

const PROPOSAL_SCHEMA: Record<string, unknown> = {
  type: "object",
  additionalProperties: false,
  required: ["subject", "atom_ids", "claims"],
  properties: {
    subject: { type: "string" },
    atom_ids: { type: "array", minItems: 1, items: { type: "string" } },
    claims: { type: "array", minItems: 1, items: { type: "object", additionalProperties: false, required: ["content"], properties: { content: { type: "string" } } } },
  },
};

export class OllamaTileProposer {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly ollama: OllamaClient,
    private readonly store: CognitiveStore,
  ) {}

  async propose(executionId: string, atoms: Atom[], requestedSubject: string): Promise<Proposal> {
    if (atoms.length === 0) throw new Error("Ollama proposal requires supplied atoms.");
    const allowed = new Map(atoms.map((atom) => [atom.atom_id, atom.content]));
    const validator = new TileBuilder([requestedSubject]);
    const system = "Propose one grouping using only supplied atom ids and verbatim claim content. Do not add knowledge. Return schema-valid JSON only.";
    const user = JSON.stringify({ requested_subject: requestedSubject, atoms: atoms.map((atom) => ({ atom_id: atom.atom_id, content: atom.content })) }, null, 2);
    const promptHash = sha256(`${system}\n${user}`);
    let rawOutput = "";
    const errors: string[] = [];
    try {
      const proposal = await this.ollama.structured<Proposal>({
        model: this.config.ollama.coder_model, schema: PROPOSAL_SCHEMA, system, user,
        validate: (value): value is Proposal => validator.validateModelProposal(value, allowed).valid,
        validationError: () => "Proposal references unavailable atoms or has invalid claims.",
        onRawResponse: (content) => { rawOutput = content; },
      });
      this.store.saveModelRun({
        model_run_id: stableId("MODRUN", executionId, promptHash), execution_id: executionId,
        model: this.config.ollama.coder_model, prompt_hash: `sha256:${promptHash}`, created_at: new Date().toISOString(), valid: true,
        parameters: { temperature: this.config.ollama.temperature, context_size: this.config.ollama.context_size },
        atom_ids: atoms.map((atom) => atom.atom_id), raw_output: rawOutput, validated_output: proposal, errors,
      });
      return proposal;
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
      this.store.saveModelRun({
        model_run_id: stableId("MODRUN", executionId, promptHash), execution_id: executionId,
        model: this.config.ollama.coder_model, prompt_hash: `sha256:${promptHash}`, created_at: new Date().toISOString(), valid: false,
        parameters: { temperature: this.config.ollama.temperature, context_size: this.config.ollama.context_size },
        atom_ids: atoms.map((atom) => atom.atom_id), raw_output: rawOutput, validated_output: null, errors,
      });
      throw error;
    }
  }
}
