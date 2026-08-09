function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function evaluateStrategy(strategy = {}, minimumConfidence = 0.35) {
  const confidence = finite(strategy.confidence);
  const utility = finite(strategy.utility);
  const cost = Math.max(0, finite(strategy.cost));
  const risk = Math.max(0, finite(strategy.risk));
  const eligible = strategy.allowed !== false && confidence >= minimumConfidence;
  return {
    id: String(strategy.id || "").trim(),
    eligible,
    confidence,
    utility,
    cost,
    risk,
    score: eligible ? (utility * confidence) - cost - risk : Number.NEGATIVE_INFINITY,
    evidence: Array.isArray(strategy.evidence) ? strategy.evidence.map(String) : []
  };
}

function selectBestStrategy(strategies = [], { minimumConfidence = 0.35 } = {}) {
  const evaluated = strategies.map((strategy) => evaluateStrategy(strategy, minimumConfidence));
  const ranked = evaluated
    .filter((strategy) => strategy.id && strategy.eligible)
    .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id));
  const selected = ranked[0] || null;
  return {
    status: selected ? "SELF_SELECTED" : "NO_ELIGIBLE_STRATEGY",
    selected,
    evaluated,
    explanation: selected
      ? `Stratégie ${selected.id} sélectionnée sur utilité, confiance, coût et risque observables.`
      : "Aucune stratégie ne satisfait les seuils locaux."
  };
}

export { evaluateStrategy, selectBestStrategy };
