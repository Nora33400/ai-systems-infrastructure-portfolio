import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import {
  buildPolicyContextResolution,
  readContextAuthorityPolicy
} from "./context-authority.mjs";

function text(value, maximum = 2_000) {
  return String(value ?? "").replaceAll("\0", "").trim().slice(0, maximum);
}

function gateHasRealEvidence(gate = {}) {
  if (String(gate.status || "").toUpperCase() !== "VERIFIED") return false;
  const required = Array.isArray(gate.requires) ? gate.requires.map(String) : [];
  const evidence = Array.isArray(gate.evidence) ? gate.evidence : [];
  return required.length > 0 && required.every((criterion) => evidence.some((item) => (
    item?.criterion === criterion
    && item?.ok === true
    && text(item?.proof, 1_000).length > 0
  )));
}

export function buildAbsolutePriorityProgram(configuration = {}, { authorityResolution = null } = {}) {
  const promptIds = new Set();
  const workstreamIds = new Set();
  const prompts = [];
  const workstreams = [];
  const issues = [];

  for (const prompt of Array.isArray(configuration.prompts) ? configuration.prompts : []) {
    const promptId = text(prompt.id, 80);
    if (!promptId || promptIds.has(promptId)) {
      issues.push(`duplicate-or-missing-prompt:${promptId || "unknown"}`);
      continue;
    }
    promptIds.add(promptId);
    const promptRecord = {
      id: promptId,
      name: text(prompt.name, 200),
      source: text(prompt.source, 500),
      status: text(prompt.status || "BLOCKED", 40),
      functionalGate: text(prompt.functionalGate || "NOT_VERIFIED", 40),
      dependsOn: (Array.isArray(prompt.dependsOn) ? prompt.dependsOn : []).map((item) => text(item, 100)).filter(Boolean)
    };
    prompts.push(promptRecord);
    for (const stream of Array.isArray(prompt.workstreams) ? prompt.workstreams : []) {
      const id = text(stream.id, 160);
      if (!id || workstreamIds.has(id)) {
        issues.push(`duplicate-or-missing-workstream:${id || "unknown"}`);
        continue;
      }
      workstreamIds.add(id);
      workstreams.push({
        ...stream,
        id,
        promptId,
        promptSource: promptRecord.source,
        priority: text(stream.priority || "P0", 10),
        status: text(stream.status || "BLOCKED", 40),
        objective: text(stream.objective, 2_000),
        targetFiles: (Array.isArray(stream.targetFiles) ? stream.targetFiles : []).map((item) => text(item, 500)).filter(Boolean).slice(0, 8),
        acceptance: (Array.isArray(stream.acceptance) ? stream.acceptance : []).map((item) => text(item, 300)).filter(Boolean).slice(0, 20)
      });
    }
  }

  const gates = (Array.isArray(configuration.functionalGates) ? configuration.functionalGates : []).map((gate) => ({
    ...gate,
    id: text(gate.id, 120),
    verifiedWithRealEvidence: gateHasRealEvidence(gate)
  }));
  const expectedGateCount = prompts.length;
  const allFunctional = expectedGateCount === 4
    && gates.length === expectedGateCount
    && gates.every((gate) => gate.verifiedWithRealEvidence);
  const configuredInterface = configuration.interfaceActivation || {};

  const inheritedRevision = authorityResolution?.artifactRevisions?.find((entry) => (
    entry.ref === "legacy.absolute-prompt-preemption"
  ));
  const contextualAuthorityApplied = authorityResolution?.schema === "aione.context-authority-resolution.v1"
    && authorityResolution?.decision !== "BLOCK";
  const legacyPreemption = !(contextualAuthorityApplied && inheritedRevision?.status === "SUPERSEDED");
  const contextualStatus = legacyPreemption ? "ACTIVE" : "ADAPTED";
  const contextualWorkstreams = workstreams.map((stream) => ({ ...stream, contextStatus: contextualStatus }));
  const configuredPriorityClass = text(configuration.priorityPolicy?.class || "ABSOLUTE_P0", 40);
  const effectivePriorityClass = legacyPreemption ? configuredPriorityClass : "CONTEXTUAL_P0_REVISABLE_BASE";

  return {
    schema: "aione.absolute-priority-program-status.v1",
    enabled: configuration.enabled === true,
    mode: text(configuration.mode, 100),
    configuredPriorityClass,
    effectivePriorityClass,
    priorityClass: effectivePriorityClass,
    prompts,
    workstreams: contextualWorkstreams,
    activeWorkstreams: contextualWorkstreams.filter((stream) => ["ACTIVE", "READY"].includes(stream.status)),
    gates,
    allFunctional,
    interfaceActivation: {
      configuredStatus: text(configuredInterface.status || "BLOCKED_BY_FUNCTIONAL_GATES", 80),
      effectiveStatus: allFunctional ? "READY_FOR_INTERFACE_PLANNING" : "BLOCKED_BY_FUNCTIONAL_GATES",
      targets: (Array.isArray(configuredInterface.targets) ? configuredInterface.targets : []).map((item) => text(item, 80)).filter(Boolean),
      automaticActivation: false,
      reason: allFunctional
        ? "ALL_FOUR_FUNCTIONAL_GATES_HAVE_REAL_TEST_EVIDENCE"
        : "PROMPT_GATES_NOT_YET_VERIFIED_WITH_REAL_EVIDENCE"
    },
    contextualAuthority: {
      applied: contextualAuthorityApplied,
      resolutionId: text(authorityResolution?.resolutionId, 100) || null,
      decision: text(authorityResolution?.decision, 40) || "NOT_PROVIDED",
      legacyPreemption,
      historicalPromptsRemainAvailable: true,
      overlays: (Array.isArray(configuration.directiveOverlays) ? configuration.directiveOverlays : [])
        .map((entry) => text(typeof entry === "string" ? entry : entry?.path, 500))
        .filter(Boolean)
    },
    issues,
    valid: issues.length === 0
      && promptIds.size === 4
      && configuration.enabled === true
      && authorityResolution?.decision !== "BLOCK"
  };
}

export function readAbsolutePriorityProgram({ root, authorityResolution } = {}) {
  const base = resolve(root || process.cwd());
  const path = join(base, "config", "absolute-priority-program.json");
  const configuration = JSON.parse(readFileSync(path, "utf8"));
  let effectiveAuthorityResolution = authorityResolution;
  if (effectiveAuthorityResolution === undefined) {
    try {
      const { policy, validation } = readContextAuthorityPolicy(base);
      if (validation.ok) effectiveAuthorityResolution = buildPolicyContextResolution(policy);
    } catch {
      // Backward-compatible degraded mode: absence of a readable authority policy
      // is reported by contextualAuthority instead of preventing status inspection.
      effectiveAuthorityResolution = null;
    }
  }
  return {
    path,
    ...buildAbsolutePriorityProgram(configuration, {
      authorityResolution: effectiveAuthorityResolution
    })
  };
}
