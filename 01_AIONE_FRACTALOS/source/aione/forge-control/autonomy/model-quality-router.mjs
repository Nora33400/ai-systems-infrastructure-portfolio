const PERMISSIVE_LICENSES = new Set(["MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE"]);
const RISK = Object.freeze({ LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 });
const COMPLEXITY = Object.freeze({ SIMPLE: 0, NORMAL: 1, COMPLEX: 2, DEEP: 3 });

function boundedNumber(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Math.max(minimum, Math.min(maximum, Number.isFinite(parsed) ? parsed : fallback));
}

function normalized(value, fallback) {
  return String(value ?? fallback).trim().toUpperCase().replaceAll("-", "_");
}

function normalizeInventory(inventory = []) {
  return (Array.isArray(inventory) ? inventory : []).map((item) => ({
    id: String(item?.id || item?.name || "").trim(),
    installed: item?.installed !== false,
    roles: new Set((Array.isArray(item?.roles) ? item.roles : []).map((role) => normalized(role, ""))),
    licenseClass: normalized(item?.licenseClass, "UNKNOWN").replaceAll("_", "-"),
    requiredVramMb: boundedNumber(item?.requiredVramMb, Number.POSITIVE_INFINITY, 0, 1_000_000),
    endpoint: String(item?.endpoint || "").trim(),
    contextLength: boundedNumber(item?.contextLength, 2048, 512, 1_000_000)
  })).filter((item) => item.id && item.installed);
}

function normalizeBenchmarks(benchmarks = []) {
  return new Map((Array.isArray(benchmarks) ? benchmarks : []).map((item) => [String(item?.modelId || item?.id || ""), {
    stableRuns: boundedNumber(item?.stableRuns, 0, 0, 10_000),
    compositeScore: boundedNumber(item?.compositeScore, 0, 0, 100),
    latencyMs: boundedNumber(item?.latencyMs, Number.POSITIVE_INFINITY, 0, 10_000_000),
    criticalSafetyFailures: boundedNumber(item?.criticalSafetyFailures, 0, 0, 10_000),
    contractValidityRate: boundedNumber(item?.contractValidityRate, 0, 0, 1),
    promoted: item?.promoted === true,
    baseline: item?.baseline === true
  }]));
}

function licenseAllowed(model, allowReviewedCustomLicense) {
  return PERMISSIVE_LICENSES.has(model.licenseClass) || (allowReviewedCustomLicense && model.licenseClass === "REVIEWED-CUSTOM");
}

function roleScore(model, desiredRoles) {
  return desiredRoles.reduce((score, role, index) => score + (model.roles.has(role) ? desiredRoles.length - index : 0), 0);
}

function desiredRoute(task) {
  const risk = normalized(task?.risk, "LOW");
  const complexity = normalized(task?.complexity, "NORMAL");
  const contextCharacters = boundedNumber(task?.contextCharacters, 0, 0, 10_000_000);
  const code = task?.code === true || normalized(task?.kind, "") === "CODE";
  const vision = task?.vision === true || normalized(task?.kind, "") === "VISION";
  const toolUse = task?.toolUse === true;
  const deep = (RISK[risk] ?? 1) >= RISK.HIGH || (COMPLEXITY[complexity] ?? 1) >= COMPLEXITY.COMPLEX || contextCharacters > 24_000;
  if (vision) return { mode: "SPECIALIST", roles: ["VISION", "MULTIMODAL"], stages: 1, multiplier: 1 };
  if (deep) return { mode: "DELIBERATIVE", roles: code ? ["CODE", "REASONING"] : ["REASONING", "PLANNING"], stages: 4, multiplier: 2 };
  if (toolUse) return { mode: "VERIFIED_TOOL", roles: ["FUNCTION_CALLING", "ROUTER", "REASONING"], stages: 2, multiplier: 1.5 };
  if ((COMPLEXITY[complexity] ?? 1) === COMPLEXITY.SIMPLE && (RISK[risk] ?? 1) === RISK.LOW) {
    return { mode: "FAST", roles: code ? ["FAST_CODE", "CODE"] : ["ROUTER", "REASONING"], stages: 1, multiplier: 1 };
  }
  return { mode: "BALANCED", roles: code ? ["CODE", "REASONING"] : ["PLANNING", "REASONING"], stages: 2, multiplier: 1.5 };
}

function rankModels(models, benchmarks, desiredRoles, policy) {
  return models.map((model) => {
    const benchmark = benchmarks.get(model.id) || null;
    const benchmarkEligible = !benchmark
      ? policy.allowConfiguredBaselineWithoutBenchmark && policy.baselineModelIds.includes(model.id)
      : benchmark.criticalSafetyFailures === 0 && benchmark.contractValidityRate >= policy.minimumContractValidityRate &&
        (benchmark.stableRuns >= policy.minimumStableRuns || benchmark.baseline);
    const fitsVram = model.requiredVramMb <= policy.maximumAdmissibleVramMb;
    return {
      model,
      benchmark,
      eligible: licenseAllowed(model, policy.allowReviewedCustomLicense) && benchmarkEligible && fitsVram,
      score: roleScore(model, desiredRoles) * 100 + (benchmark?.compositeScore || 0) - Math.min(100, (benchmark?.latencyMs || 0) / 1000),
      reasons: [
        ...(licenseAllowed(model, policy.allowReviewedCustomLicense) ? [] : ["LICENSE_NOT_APPROVED"]),
        ...(benchmarkEligible ? [] : ["BENCHMARK_GATE_NOT_MET"]),
        ...(fitsVram ? [] : ["VRAM_BUDGET_EXCEEDED"])
      ]
    };
  }).sort((left, right) => right.score - left.score || left.model.id.localeCompare(right.model.id));
}

export function routeLocalModelTask({ task = {}, inventory = [], benchmarks = [], resources = {}, policy = {} } = {}) {
  const desired = desiredRoute(task);
  const normalizedPolicy = {
    minimumStableRuns: boundedNumber(policy.minimumStableRuns, 3, 1, 100),
    minimumContractValidityRate: boundedNumber(policy.minimumContractValidityRate, 0.95, 0, 1),
    maximumAdmissibleVramMb: boundedNumber(resources.maximumAdmissibleVramMb, 12_288, 0, 1_000_000),
    maximumPhysicalConcurrentModels: boundedNumber(policy.maximumPhysicalConcurrentModels, 2, 1, 2),
    allowReviewedCustomLicense: policy.allowReviewedCustomLicense === true,
    allowConfiguredBaselineWithoutBenchmark: policy.allowConfiguredBaselineWithoutBenchmark === true,
    baselineModelIds: Array.isArray(policy.baselineModelIds) ? policy.baselineModelIds.map(String) : ["qwen2.5-coder:7b", "qwen2.5-coder:14b"]
  };
  const models = normalizeInventory(inventory);
  const benchmarkMap = normalizeBenchmarks(benchmarks);
  const ranked = rankModels(models, benchmarkMap, desired.roles, normalizedPolicy);
  const selected = ranked.filter((item) => item.eligible);
  if (!selected.length) {
    return {
      schema: "aione.local-model-route.v1",
      decision: "NO_SAFE_MODEL",
      executable: false,
      desired,
      models: [],
      rejected: ranked.map((item) => ({ id: item.model.id, reasons: item.reasons })),
      explanation: "Aucun modèle installé ne satisfait simultanément licence, benchmark et VRAM."
    };
  }
  const primary = selected[0];
  const alternative = selected.find((item) => item.model.id !== primary.model.id) || primary;
  const roles = desired.mode === "DELIBERATIVE" ? [
    { role: "proposer", modelId: primary.model.id },
    { role: "critic", modelId: alternative.model.id },
    { role: "verifier", modelId: alternative.model.id },
    { role: "synthesizer", modelId: primary.model.id }
  ] : [{ role: "primary", modelId: primary.model.id }];
  return {
    schema: "aione.local-model-route.v1",
    decision: "ROUTE_LOCAL",
    executable: true,
    mode: desired.mode,
    stages: Math.min(desired.stages, 4),
    executionBudgetMultiplier: Math.min(desired.multiplier, 2),
    physicalConcurrentModels: Math.min(new Set(roles.map((item) => item.modelId)).size, normalizedPolicy.maximumPhysicalConcurrentModels),
    roles,
    fallbackModelId: selected.find((item) => normalizedPolicy.baselineModelIds.includes(item.model.id))?.model.id || primary.model.id,
    qualityGate: {
      externalTestsRequired: task?.code === true || normalized(task?.kind, "") === "CODE",
      structuredOutputRequired: true,
      preserveDisagreements: roles.length > 1,
      criticalSafetyFailuresAllowed: 0
    },
    explanation: `${desired.mode}: ${roles.length} rôle(s) logique(s), ${new Set(roles.map((item) => item.modelId)).size} modèle(s) local(aux), budget x${Math.min(desired.multiplier, 2)}.`,
    performanceClaim: "NOT_CLAIMED_UNTIL_LIVE_BENCHMARK"
  };
}

export { PERMISSIVE_LICENSES };
