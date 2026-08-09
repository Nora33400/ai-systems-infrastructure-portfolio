import { createHash } from "node:crypto";
import { chooseReflectiveAction } from "../../forge-control/autonomy/reflective-autonomy.mjs";
import { selectBestStrategy } from "../cognition/strategy-selector.mjs";
import { ReflectionMemory } from "../memory/reflection-memory.mjs";
import { AppendOnlyAudit } from "../audit/append-only-audit.mjs";

function stableId(prefix, value) {
  return `${prefix}-${createHash("sha256").update(JSON.stringify(value)).digest("hex").slice(0, 12)}`;
}

class ReflectiveCognitiveEngine {
  #policy;
  #memory;
  #audit;
  #subgoals = new Map();

  constructor({ policy, memory = new ReflectionMemory(), audit = new AppendOnlyAudit() }) {
    if (!policy?.enabled) throw new Error("Politique réflexive active requise.");
    this.#policy = policy;
    this.#memory = memory;
    this.#audit = audit;
  }

  createSubgoal({ title, utility = 0, acceptance = [], parentId = null }) {
    const subgoal = {
      id: stableId("subgoal", { title, parentId }),
      title: String(title),
      utility: Number(utility),
      acceptance: acceptance.map(String),
      parentId,
      status: "PROPOSED"
    };
    this.#subgoals.set(subgoal.id, subgoal);
    this.#audit.append({ type: "SUBGOAL_CREATED", decisionId: subgoal.id, summary: subgoal.title });
    return structuredClone(subgoal);
  }

  prioritizeSubgoals() {
    return [...this.#subgoals.values()]
      .filter((goal) => !["RETIRED", "COMPLETED"].includes(goal.status))
      .sort((left, right) => right.utility - left.utility || left.id.localeCompare(right.id))
      .map((goal) => structuredClone(goal));
  }

  setSubgoalStatus(id, status) {
    if (!new Set(["ADOPTED", "PAUSED", "COMPLETED", "RETIRED"]).has(status)) throw new Error(`Statut refusé: ${status}`);
    const subgoal = this.#subgoals.get(id);
    if (!subgoal) throw new Error(`Sous-objectif inconnu: ${id}`);
    subgoal.status = status;
    this.#audit.append({ type: `SUBGOAL_${status}`, decisionId: id, summary: subgoal.title });
    return structuredClone(subgoal);
  }

  reflect({ decisions = [], strategies = [] } = {}) {
    const decisionChoice = chooseReflectiveAction(this.#policy, decisions);
    const strategyChoice = selectBestStrategy(strategies);
    const result = {
      status: decisionChoice.selected || strategyChoice.selected ? "REFLECTED" : "NO_ELIGIBLE_CHOICE",
      decision: decisionChoice.selected?.candidate || null,
      decisionEvaluation: decisionChoice.selected?.decision || null,
      strategy: strategyChoice.selected,
      explanation: [decisionChoice.selected?.decision?.explanation, strategyChoice.explanation].filter(Boolean)
    };
    this.#memory.append({
      type: "STRUCTURED_REFLECTION",
      decisionId: result.decision?.id || null,
      strategyId: result.strategy?.id || null,
      status: result.status,
      evidence: result.decisionEvaluation?.audit?.evidence || []
    });
    this.#audit.append({
      type: "REFLECTIVE_CHOICE",
      decisionId: result.decision?.id || null,
      summary: result.explanation.join(" "),
      evidence: result.decisionEvaluation?.audit?.evidence || []
    });
    return result;
  }

  recordPrediction(input) {
    return this.#memory.recordPrediction(input);
  }

  snapshot() {
    return { subgoals: this.prioritizeSubgoals(), memory: this.#memory.list(), audit: this.#audit.list() };
  }
}

export { ReflectiveCognitiveEngine, stableId };
