import {
  applyChanges,
  extractMutationProposal,
  normalizeProposalPath,
  validateChangedFiles,
  validateMutationProposal
} from "./isolated-implementation.mjs";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const MUTATION_CAPABILITIES = new Set(["write-approved", "docs.write-approved"]);
const UNSUPPORTED_DOCUMENTATION_COMPLETION_CLAIM = /\b(?:blocage|probl[eè]me|incident|erreur)\b[^\r\n]{0,120}\b(?:a été|est|has been)\s+(?:corrig(?:é|e)|r[eé]solu|r[eé]par(?:é|e)|fixed|resolved)(?=[\s.,;:!?]|$)/iu;

const FORGE_QUEUE_SAFE_CAPABILITIES = new Set([
  "read",
  "plan",
  "test",
  "test-approved",
  ...MUTATION_CAPABILITIES
]);

function inspectQueueCapabilities(task = {}) {
  const required = Array.isArray(task.requiredCapabilities) ? task.requiredCapabilities : [];
  const unsupportedCapabilities = required.filter((capability) => !FORGE_QUEUE_SAFE_CAPABILITIES.has(capability));
  const mutationRequested = required.some((capability) => MUTATION_CAPABILITIES.has(capability));
  const documentationOnly = required.includes("docs.write-approved") && !required.includes("write-approved");
  return {
    eligible: unsupportedCapabilities.length === 0,
    mutationRequested,
    documentationOnly,
    unsupportedCapabilities,
    reason: unsupportedCapabilities.length === 0
      ? mutationRequested
        ? "eligible-isolated-mutation-worker"
        : "eligible-read-diagnostic-test-worker"
      : `capabilities-not-yet-supported-by-isolated-worker:${unsupportedCapabilities.join(",")}`
  };
}

function normalizeUnambiguousCreateFileIntent(proposal, workspace) {
  const warnings = [];
  if (!proposal || !Array.isArray(proposal.changes)) return { proposal, warnings };
  const changes = proposal.changes.map((raw, index) => {
    if (
      String(raw?.operation || "") !== "replace-fragment" ||
      String(raw?.oldText ?? "").length > 0 ||
      !String(raw?.newText ?? "").trim()
    ) {
      return raw;
    }
    try {
      const path = normalizeProposalPath(raw.path);
      if (existsSync(resolve(workspace, path))) return raw;
      warnings.push(
        `changes[${index}]: replace-fragment sans ancre converti en create-file car ${path} est absent dans le workspace isole`
      );
      return {
        operation: "create-file",
        path,
        content: String(raw.newText)
      };
    } catch {
      // La validation normale conserve l'erreur de chemin ou de contrat. Cette
      // normalisation ne doit jamais rendre un chemin invalide acceptable.
      return raw;
    }
  });
  return { proposal: { ...proposal, changes }, warnings };
}

function buildDocumentationFallbackContract(task = {}, rejectedImplementation = {}) {
  const taskId = String(task.id || "task-inconnue")
    .replace(/[^A-Za-z0-9._-]/g, "-")
    .slice(0, 100);
  const safeTitle = String(task.title || "Tâche documentaire locale")
    .replace(/[\u0000-\u001f`<>]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
  const rejectedStatus = String(rejectedImplementation.status || "CONTRAT_MODELE_REFUSE")
    .replace(/[^A-Za-z0-9._:-]/g, "-")
    .slice(0, 100);
  const path = `docs/forge/reviews/${taskId.toLowerCase()}-incident.md`;
  const content = [
    `# Dossier de revue — ${safeTitle || taskId}`,
    "",
    "## Statut",
    "",
    "Proposition documentaire générée dans un environnement S: isolé. Aucune mutation canonique, publication, installation, suppression ou modification de permission n’a été effectuée.",
    "",
    "## Incident observé",
    "",
    `- Tâche : ${taskId}`,
    `- Contrat local refusé : ${rejectedStatus}`,
    "- Cause opérationnelle : le modèle local n’a pas respecté le contrat borné après les corrections automatiques.",
    "- Décision : ne pas affaiblir les garde-fous et produire ce dossier factuel pour revue.",
    "",
    "## Garde-fous maintenus",
    "",
    "- écriture limitée à la documentation du clone isolé ;",
    "- aucune écriture dans config/, scripts/, code, Git ou chemins protégés ;",
    "- aucun secret, accès réseau externe ou publication ;",
    "- tests Forge obligatoires avant présentation à l’Owner ;",
    "- application canonique soumise à une revue humaine séparée.",
    "",
    "## Suite proposée",
    "",
    "Analyser les preuves et le diff isolé, corriger la spécification si nécessaire, puis accepter ou refuser depuis le dossier Owner. Un refus ne bloque pas les autres pipelines locaux.",
    ""
  ].join("\n");
  return `\`\`\`aione-mutation\n${JSON.stringify({
    schema: "aione.isolated-mutation-proposal.v1",
    goal: "Produire un dossier local factuel après refus sécurisé du contrat du modèle.",
    confidence: 1,
    changes: [{ operation: "create-file", path, content }],
    testFiles: []
  })}\n\`\`\``;
}

function applyIsolatedModelProposal({ markdown, workspace, allowedPathPrefixes = null }) {
  const extracted = extractMutationProposal(markdown);
  if (!extracted.ok) return extracted;
  const normalizedIntent = normalizeUnambiguousCreateFileIntent(extracted.proposal, workspace);
  const validation = validateMutationProposal(normalizedIntent.proposal, {
    maximumChanges: 3,
    maximumTotalCharacters: 64 * 1024,
    minimumConfidence: 0.72,
    // Les chemins de tests suggérés par le modèle ne sont jamais exécutés sans
    // validation. Une suggestion mal formée peut être ignorée car le worker
    // lance toujours sa suite Forge fixe et sûre.
    tolerateInvalidTestFiles: true
  });
  if (!validation.ok) {
    return {
      ok: false,
      status: "INVALID_CONTRACT",
      errors: validation.errors,
      warnings: [...normalizedIntent.warnings, ...validation.warnings],
      proposal: validation.proposal
    };
  }
  if (Array.isArray(allowedPathPrefixes) && allowedPathPrefixes.length) {
    const outsideScope = validation.proposal.changes
      .map((change) => change.path)
      .filter((path) => !allowedPathPrefixes.some((prefix) => path.startsWith(prefix)));
    if (outsideScope.length) {
      return {
        ok: false,
        status: "INVALID_CAPABILITY_SCOPE",
        errors: [`portée de capacité refusée: ${outsideScope.join(", ")}; préfixes autorisés=${allowedPathPrefixes.join(",")}`],
        warnings: validation.warnings,
        proposal: validation.proposal
      };
    }
  }
  const warnings = [...normalizedIntent.warnings, ...(validation.warnings || [])];
  const proposal = {
    ...validation.proposal,
    testFiles: validation.proposal.testFiles.filter((path) => {
      if (existsSync(resolve(workspace, path))) return true;
      warnings.push(`testFiles: fichier inexistant ignoré: ${path}; tests Forge obligatoires conservés`);
      return false;
    })
  };
  if (
    Array.isArray(allowedPathPrefixes) &&
    allowedPathPrefixes.length === 1 &&
    allowedPathPrefixes[0] === "docs/"
  ) {
    const unsupportedClaim = proposal.changes.find((change) =>
      UNSUPPORTED_DOCUMENTATION_COMPLETION_CLAIM.test(String(change.content || change.newText || ""))
    );
    if (unsupportedClaim) {
      return {
        ok: false,
        status: "UNSUPPORTED_DOCUMENTATION_CLAIM",
        errors: [`affirmation de résolution sans preuve opérationnelle refusée dans ${unsupportedClaim.path}`],
        warnings,
        proposal,
        canonicalMutationPerformed: false
      };
    }
  }
  let changedFiles;
  let staticValidation = [];
  try {
    changedFiles = applyChanges(workspace, proposal.changes, {
      validate(files) {
        staticValidation = validateChangedFiles(workspace, files);
        const failed = staticValidation.filter((item) => item.ok === false);
        return {
          ok: failed.length === 0,
          errors: failed.map((item) => `${item.path}: ${item.detail || item.stderr || item.error || "validation statique échouée"}`)
        };
      }
    });
  } catch (error) {
    return {
      ok: false,
      status: error.code === "STATIC_VALIDATION_REJECTED" ? "STATIC_VALIDATION_REJECTED" : "APPLY_PREFLIGHT_REJECTED",
      errors: [error.message],
      warnings,
      proposal,
      staticValidation: error.validation ? staticValidation : [],
      totalCharacters: validation.totalCharacters,
      canonicalMutationPerformed: false
    };
  }
  return {
    ok: true,
    status: "APPLIED_IN_ISOLATED_WORKSPACE",
    changedFiles,
    proposal,
    totalCharacters: validation.totalCharacters,
    warnings,
    staticValidation,
    canonicalMutationPerformed: false
  };
}

export {
  FORGE_QUEUE_SAFE_CAPABILITIES,
  applyIsolatedModelProposal,
  buildDocumentationFallbackContract,
  inspectQueueCapabilities
};
