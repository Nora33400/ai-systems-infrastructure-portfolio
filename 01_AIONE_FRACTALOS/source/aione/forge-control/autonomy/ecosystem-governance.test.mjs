import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { afterEach, test } from "node:test";
import {
  EcosystemGovernance,
  EXCHANGE_REQUIRED_FIELDS,
  GovernanceError,
  REQUIRED_SUBSYSTEMS,
  loadEcosystemDomains,
  validateEcosystemDomains
} from "./ecosystem-governance.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

const CONFIG_PATH = new URL("../../config/ecosystem-domains.json", import.meta.url);
const temporaryDirectories = [];

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

function temporaryStorage() {
  const directory = mkdtempSync(join(testRuntimeRoot(), "aione-ecosystem-governance-"));
  temporaryDirectories.push(directory);
  return directory;
}

function fixedClock(value = "2026-07-30T14:00:00.000Z") {
  let current = new Date(value);
  return {
    clock: () => new Date(current),
    set(valueToSet) {
      current = new Date(valueToSet);
    }
  };
}

function governance(options = {}) {
  return new EcosystemGovernance({
    configPath: CONFIG_PATH,
    storageDirectory: temporaryStorage(),
    clock: fixedClock().clock,
    ...options
  });
}

function permission({
  id = "permission:exchange:1",
  source = "digital-programming",
  target = "scientific-extension",
  principal = "agent:programming:1",
  actions = ["exchange.send"],
  dataClasses = ["INTERNAL"],
  licenses = ["AIONE-INTERNAL-1.0"],
  validFrom = "2026-07-30T13:00:00.000Z",
  expiresAt = "2026-07-31T14:00:00.000Z"
} = {}) {
  return {
    permissionDecisionId: id,
    principalId: principal,
    authority: "HUMAN_OWNER",
    issuedBy: "human-owner:the owner",
    decision: "ALLOW",
    actions,
    sourceEcosystemId: source,
    targetEcosystemIds: [target],
    allowedDataClasses: dataClasses,
    allowedLicenses: licenses,
    validFrom,
    expiresAt,
    reason: "Autorisation bornee pour le test local."
  };
}

function exchange({
  flowId = "flow:programming-to-science:1",
  counter = 1,
  wallTime = "2026-07-30T13:59:00.000Z",
  ttl = 300,
  permissionDecisionId = "permission:exchange:1"
} = {}) {
  const payload = { module: "simulation-core", revision: "r1" };
  return {
    flowId,
    sourceEcosystemId: "digital-programming",
    targetEcosystemId: "scientific-extension",
    principalId: "agent:programming:1",
    purpose: "Partager un composant de simulation valide.",
    offeredValue: {
      kind: "software-component",
      quantity: 1,
      unit: "capability-unit",
      description: "Composant local teste."
    },
    requestedValue: {
      kind: "scientific-review",
      quantity: 1,
      unit: "review-slot",
      description: "Relecture scientifique."
    },
    dataClass: "INTERNAL",
    provenance: {
      sourceRefs: ["evidence:test:simulation-core"],
      checksum: createHash("sha256").update(JSON.stringify(payload)).digest("hex"),
      transformation: "none"
    },
    license: "AIONE-INTERNAL-1.0",
    permissionDecisionId,
    causalClock: {
      sourceCounter: counter,
      wallTime,
      observed: { "scientific-extension": 0 }
    },
    ttl,
    compensation: {
      kind: "validated-evidence",
      quantity: 1,
      unit: "evidence-unit",
      description: "Retour de preuve, sans valeur financiere."
    },
    payload
  };
}

test("charge et valide la configuration federale sure", () => {
  const config = loadEcosystemDomains(CONFIG_PATH);
  assert.equal(config.exchangeContract.defaultDecision, "DENY");
  assert.equal(config.exchangeContract.missingOrInvalid, "QUARANTINE");
  assert.equal(config.ecosystems.length, 4);
  for (const subsystem of REQUIRED_SUBSYSTEMS) {
    assert.ok(config.requiredSubsystemsPerEcosystem.includes(subsystem));
  }
  for (const field of EXCHANGE_REQUIRED_FIELDS) {
    assert.ok(config.exchangeContract.requiredFields.includes(field));
  }

  const unsafe = JSON.parse(readFileSync(CONFIG_PATH, "utf8"));
  unsafe.exchangeContract.defaultDecision = "ALLOW";
  assert.throws(
    () => validateEcosystemDomains(unsafe),
    (error) => error instanceof GovernanceError && error.code === "UNSAFE_EXCHANGE_DEFAULT"
  );
});

test("maintient les sous-systemes par ecosysteme et refuse la lecture croisee implicite", () => {
  const system = governance();
  const own = system.readEcosystem("digital-programming", "digital-programming");
  for (const key of [
    "projectRegistry",
    "goalDependencyGraph",
    "taskQueueAndScheduler",
    "specializedAgentPool",
    "workflowRegistry",
    "tileContextMemory",
    "resourceBudget",
    "permissionOverlay",
    "healthAndIncidents",
    "testAndEvidenceLedger",
    "backupAndRestore",
    "ownerReviewInbox"
  ]) {
    assert.ok(Object.hasOwn(own, key), `${key} doit exister`);
  }

  assert.throws(
    () => system.readEcosystem("scientific-extension", "digital-programming"),
    (error) => error instanceof GovernanceError && error.code === "IMPLICIT_CROSS_READ_DENIED"
  );

  system.upsertProject("digital-programming", {
    id: "project:forge-governance",
    name: "Forge governance",
    objective: "Gouverner sans microgerer.",
    ownerPrincipalId: "human-owner:the owner",
    updatedAt: "2026-07-30T14:00:00.000Z"
  });
  system.upsertGoal("digital-programming", {
    id: "goal:governance-safe",
    projectId: "project:forge-governance",
    objective: "Prouver l'isolation.",
    status: "ACTIVE"
  });
  system.upsertGoal("digital-programming", {
    id: "goal:governance-tested",
    projectId: "project:forge-governance",
    objective: "Prouver le redemarrage.",
    status: "ACTIVE"
  });
  system.recordDependency("digital-programming", {
    id: "dependency:safe-before-tested",
    fromGoalId: "goal:governance-tested",
    toGoalId: "goal:governance-safe"
  });
  system.registerWorkflow("digital-programming", {
    id: "workflow:test-first",
    name: "Test first",
    steps: ["analyse", "isolation", "test", "owner-review"]
  });
  system.registerAgent("digital-programming", {
    id: "agent:qa:1",
    role: "QA local",
    capabilities: ["test", "evidence"],
    permissionCeiling: ["read", "test.existing"]
  });
  system.enqueueTask("digital-programming", {
    id: "task:governance:1",
    projectId: "project:forge-governance",
    title: "Verifier la gouvernance.",
    workflowId: "workflow:test-first"
  });
  system.appendMemory("digital-programming", {
    id: "memory:governance:1",
    level: "tile",
    perspective: "dual",
    subject: "isolation",
    reconstruction: "La lecture croisee exige une permission explicite.",
    sourceRefs: ["evidence:isolation:1"]
  });
  system.reportHealth("digital-programming", { status: "HEALTHY", details: { queue: "ready" } });
  system.recordIncident("digital-programming", {
    id: "incident:test:1",
    signature: "simulated-only",
    severity: "LOW",
    status: "RESOLVED",
    summary: "Incident synthetique ferme."
  });
  system.recordEvidence("digital-programming", {
    id: "evidence:isolation:1",
    kind: "node-test",
    result: "PASS",
    checksum: "sha256:test",
    sourceRefs: ["test:ecosystem-governance"]
  });
  system.recordBackup("digital-programming", {
    id: "backup:governance:1",
    locationRef: "local://governance-test",
    checksum: "sha256:backup",
    restoreTest: "PASS"
  });
  system.submitOwnerReview("digital-programming", {
    id: "review:governance:1",
    projectId: "project:forge-governance",
    title: "Revue Owner",
    dossierRef: "local://owner-review/governance"
  });

  const state = system.readEcosystem("digital-programming", "digital-programming");
  assert.equal(Object.keys(state.projectRegistry).length, 1);
  assert.equal(state.goalDependencyGraph.dependencies.length, 1);
  assert.equal(state.taskQueueAndScheduler.length, 1);
  assert.equal(Object.keys(state.specializedAgentPool).length, 1);
  assert.equal(Object.keys(state.workflowRegistry).length, 1);
  assert.equal(state.tileContextMemory.length, 1);
  assert.equal(state.healthAndIncidents.status, "HEALTHY");
  assert.equal(state.testAndEvidenceLedger.length, 1);
  assert.equal(state.backupAndRestore.records.length, 1);
  assert.equal(state.ownerReviewInbox.length, 1);

  state.projectRegistry["project:forge-governance"].name = "mutation externe";
  assert.equal(
    system.readEcosystem("digital-programming", "digital-programming")
      .projectRegistry["project:forge-governance"].name,
    "Forge governance"
  );
  const map = system.getFederationMap();
  assert.equal(map.ecosystems.find((item) => item.id === "digital-programming").projectCount, 1);
  assert.equal(Object.hasOwn(map.ecosystems[0], "tileContextMemory"), false, "le gouverneur ne lit pas le contenu metier");
  assert.equal(system.verifyIntegrity().ok, true);
});

test("autorise une lecture croisee uniquement avec une decision bornee du proprietaire", () => {
  const system = governance();
  system.recordPermissionDecision("digital-programming", permission({
    id: "permission:read:1",
    source: "digital-programming",
    target: "scientific-extension",
    principal: "agent:science:1",
    actions: ["ecosystem.read"],
    dataClasses: [],
    licenses: []
  }));
  const target = system.readEcosystem("scientific-extension", "digital-programming", {
    principalId: "agent:science:1",
    permissionDecisionId: "permission:read:1"
  });
  assert.equal(target.id, "digital-programming");
  assert.throws(
    () => system.readEcosystem("social-mediation", "digital-programming", {
      principalId: "agent:science:1",
      permissionDecisionId: "permission:read:1"
    }),
    (error) => error instanceof GovernanceError && error.code === "CROSS_READ_DENIED"
  );
});

test("accepte un contrat type autorise et deduplique son rejeu, y compris apres reouverture", () => {
  const storageDirectory = temporaryStorage();
  const time = fixedClock();
  let system = new EcosystemGovernance({
    configPath: CONFIG_PATH,
    storageDirectory,
    clock: time.clock
  });
  system.recordPermissionDecision("digital-programming", permission());
  const contract = exchange();
  const first = system.submitExchange(contract);
  assert.equal(first.status, "ACCEPTED");
  assert.equal(first.replayed, false);
  const eventCount = system.verifyIntegrity().eventCount;
  const replay = system.submitExchange(contract);
  assert.equal(replay.status, "ACCEPTED");
  assert.equal(replay.replayed, true);
  assert.equal(system.verifyIntegrity().eventCount, eventCount, "un rejeu ne doit pas ajouter d'evenement");

  system = new EcosystemGovernance({
    configPath: CONFIG_PATH,
    storageDirectory,
    clock: time.clock
  });
  const reopenedReplay = system.submitExchange(contract);
  assert.equal(reopenedReplay.replayed, true);
  const source = system.readEcosystem("digital-programming", "digital-programming");
  const target = system.readEcosystem("scientific-extension", "scientific-extension");
  assert.equal(source.valueExchange.outbox.length, 1);
  assert.equal(target.valueExchange.inbox.length, 1);
  assert.equal(system.verifyIntegrity().ok, true);

  const conflicting = exchange();
  conflicting.payload.revision = "r2";
  const conflict = system.submitExchange(conflicting);
  assert.equal(conflict.status, "QUARANTINED");
  assert.deepEqual(conflict.reasons, ["IDEMPOTENCY_CONFLICT"]);
});

test("met en quarantaine expiration, causalite, permission absente et valeur financiere", () => {
  const time = fixedClock();
  const system = governance({ clock: time.clock });

  const noPermission = system.submitExchange(exchange());
  assert.equal(noPermission.status, "QUARANTINED");
  assert.deepEqual(noPermission.reasons, ["PERMISSION_DENIED_OR_EXPIRED"]);

  system.recordPermissionDecision("digital-programming", permission());
  const expired = system.submitExchange(exchange({
    flowId: "flow:expired:1",
    wallTime: "2026-07-30T12:00:00.000Z",
    ttl: 60
  }));
  assert.deepEqual(expired.reasons, ["EXPIRED_TTL"]);

  const accepted = system.submitExchange(exchange({ flowId: "flow:causal:1", counter: 2 }));
  assert.equal(accepted.status, "ACCEPTED");
  const stale = system.submitExchange(exchange({ flowId: "flow:causal:2", counter: 1 }));
  assert.deepEqual(stale.reasons, ["CAUSAL_REPLAY_OR_REORDER"]);

  const financial = exchange({ flowId: "flow:financial:1", counter: 3 });
  financial.offeredValue.price = 100;
  financial.offeredValue.currency = "EUR";
  const rejectedFinancial = system.submitExchange(financial);
  assert.equal(rejectedFinancial.status, "QUARANTINED");
  assert.deepEqual(rejectedFinancial.reasons, ["FINANCIAL_VALUE_DENIED"]);

  const missing = system.submitExchange({ flowId: "flow:missing:1" });
  assert.equal(missing.status, "QUARANTINED");
  assert.deepEqual(missing.reasons, ["MISSING_CONTRACT_FIELD"]);
  assert.equal(system.getQuarantine().length, 5);
});

test("arbitre les enveloppes sans microgerer et resout les conflits de ressources", () => {
  const system = governance({
    globalCapacity: { cpuUnits: 20, gpuUnits: 10, ramUnits: 20, storageUnits: 20 }
  });
  system.setResourceBudget("digital-programming", {
    cpuUnits: 10,
    gpuUnits: 10,
    ramUnits: 10,
    storageUnits: 10
  });
  system.setResourceBudget("scientific-extension", {
    cpuUnits: 10,
    gpuUnits: 10,
    ramUnits: 10,
    storageUnits: 10
  });
  system.requestResources("digital-programming", {
    requestId: "request:programming:gpu",
    resources: { gpuUnits: 8 },
    priority: "P1",
    reason: "Compiler et tester."
  });
  system.requestResources("scientific-extension", {
    requestId: "request:science:gpu",
    resources: { gpuUnits: 8 },
    priority: "P0",
    reason: "Simulation prioritaire."
  });
  system.requestResources("digital-programming", {
    requestId: "request:programming:over-budget",
    resources: { cpuUnits: 11 },
    priority: "P0",
    reason: "Demande volontairement excessive."
  });

  const result = system.arbitrateResources();
  const byId = Object.fromEntries(result.decisions.map((decision) => [decision.requestId, decision]));
  assert.equal(byId["request:science:gpu"].status, "GRANTED");
  assert.equal(byId["request:programming:gpu"].status, "DENIED");
  assert.equal(byId["request:programming:gpu"].reason, "GLOBAL_RESOURCE_CONFLICT");
  assert.equal(byId["request:programming:over-budget"].status, "DENIED");
  assert.equal(byId["request:programming:over-budget"].reason, "ECOSYSTEM_BUDGET_EXCEEDED");

  const map = system.getFederationMap();
  assert.equal(map.activeAllocations.length, 1);
  assert.equal(map.activeAllocations[0].ecosystemId, "scientific-extension");
  assert.equal(system.releaseResources("alloc:request:science:gpu").status, "RELEASED");
  assert.equal(system.getFederationMap().activeAllocations.length, 0);
  assert.equal(system.verifyIntegrity().ok, true);
});

test("persiste offres et demandes non financieres et rejette les prix", () => {
  const system = governance();
  const published = system.publishValueOffer("local-creation", {
    id: "offer:creative:1",
    value: {
      kind: "design-system",
      quantity: 1,
      unit: "knowledge-unit",
      description: "Systeme visuel reutilisable."
    },
    availableUntil: "2026-08-30T14:00:00.000Z",
    constraints: { localOnly: true }
  });
  assert.equal(published.status, "PUBLISHED");
  system.publishValueDemand("digital-programming", {
    id: "demand:design:1",
    value: {
      kind: "design-review",
      quantity: 2,
      unit: "review-slot"
    },
    neededBy: "2026-08-01T14:00:00.000Z",
    purpose: "Verifier l'interface."
  });
  assert.throws(
    () => system.publishValueOffer("local-creation", {
      id: "offer:forbidden-price",
      value: {
        kind: "asset",
        quantity: 1,
        unit: "service-unit",
        price: 10
      },
      availableUntil: "2026-08-30T14:00:00.000Z"
    }),
    (error) => error instanceof GovernanceError && error.code === "FINANCIAL_VALUE_DENIED"
  );
  const creation = system.readEcosystem("local-creation", "local-creation");
  const programming = system.readEcosystem("digital-programming", "digital-programming");
  assert.equal(creation.valueExchange.offers.length, 1);
  assert.equal(programming.valueExchange.demands.length, 1);
});

test("recupere un evenement atomique apres crash entre journal et snapshot", () => {
  const storageDirectory = temporaryStorage();
  const time = fixedClock();
  let injected = false;
  const crashing = new EcosystemGovernance({
    configPath: CONFIG_PATH,
    storageDirectory,
    clock: time.clock,
    faultInjector(stage) {
      if (stage === "event-written" && !injected) {
        injected = true;
        throw new Error("simulated-process-crash");
      }
    }
  });
  const project = {
    id: "project:crash-recovery",
    name: "Crash recovery",
    objective: "Prouver la reprise append-only.",
    ownerPrincipalId: "human-owner:the owner",
    updatedAt: "2026-07-30T14:00:00.000Z"
  };
  assert.throws(() => crashing.upsertProject("digital-programming", project), /simulated-process-crash/);

  const reopened = new EcosystemGovernance({
    configPath: CONFIG_PATH,
    storageDirectory,
    clock: time.clock
  });
  assert.equal(
    reopened.readEcosystem("digital-programming", "digital-programming")
      .projectRegistry["project:crash-recovery"].name,
    "Crash recovery"
  );
  assert.equal(reopened.upsertProject("digital-programming", project).status, "UNCHANGED");
  assert.equal(reopened.verifyIntegrity().ok, true);
  assert.equal(reopened.verifyIntegrity().eventCount, 1);
});
