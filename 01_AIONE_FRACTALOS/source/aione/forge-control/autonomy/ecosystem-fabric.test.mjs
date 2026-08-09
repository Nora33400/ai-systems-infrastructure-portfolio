import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import {
  EcosystemFabric,
  deterministicId,
  partitionFor
} from "./ecosystem-fabric.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function fixture() {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-fabric-"));
  const fabric = new EcosystemFabric({
    databasePath: join(root, "fabric.sqlite"),
    namespace: "test",
    shardCount: 256,
    clock: () => new Date("2026-07-29T12:00:00.000Z")
  });
  return { root, fabric };
}

function seed(fabric) {
  const federation = fabric.registerNode({
    kind: "federation",
    naturalKey: "federation/aione",
    name: "AIONE Federation"
  }).node;
  const ecosystem = fabric.registerNode({
    kind: "ecosystem",
    naturalKey: "ecosystem/aione",
    name: "AIONE Ecosystem",
    parentId: federation.id
  }).node;
  const organization = fabric.registerNode({
    kind: "organization",
    naturalKey: "organization/local",
    name: "Local Organization",
    parentId: ecosystem.id
  }).node;
  return { federation, ecosystem, organization };
}

test("fabric registers a deterministic hierarchy and survives reopening", () => {
  const { root, fabric } = fixture();
  try {
    const hierarchy = seed(fabric);
    const duplicate = fabric.registerNode({
      kind: "organization",
      naturalKey: "organization/local",
      name: "Local Organization",
      parentId: hierarchy.ecosystem.id
    });
    assert.equal(duplicate.created, false);
    assert.equal(fabric.summary().totalNodes, 3);
    assert.equal(fabric.summary().organizations, 1);
    assert.equal(fabric.verifyEventChains().ok, true);
    const databasePath = fabric.databasePath;
    fabric.close();

    const reopened = new EcosystemFabric({ databasePath, namespace: "test" });
    assert.equal(reopened.getNode(hierarchy.organization.id).name, "Local Organization");
    assert.equal(reopened.summary().totalNodes, 3);
    reopened.close();
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("child governance can narrow but never widen its parent ceiling", () => {
  const { root, fabric } = fixture();
  try {
    const { organization } = seed(fabric);
    const result = fabric.registerNode({
      kind: "project",
      naturalKey: "project/guarded",
      name: "Guarded project",
      parentId: organization.id,
      policy: {
        permissions: { allow: ["read", "remote.push"] },
        limits: { maxConcurrentAgents: 10_000 },
        crossOrganizationRead: true,
        destructiveMutation: true,
        externalActionsDefault: "ALLOW"
      }
    });
    assert.deepEqual(result.node.policy.permissions.allow, ["read"]);
    assert.equal(result.node.policy.limits.maxConcurrentAgents, 256);
    assert.equal(result.node.policy.crossOrganizationRead, false);
    assert.equal(result.node.policy.destructiveMutation, false);
    assert.equal(result.node.policy.externalActionsDefault, "DENY");
    assert.ok(result.simulation.policyClamps.length >= 5);
    const attemptedExpansion = fabric.narrowPolicy(result.node.id, {
      permissions: { allow: ["read", "audit"] },
      limits: { maxConcurrentAgents: 999 }
    });
    assert.equal(attemptedExpansion.changed, false);
    assert.deepEqual(attemptedExpansion.node.policy.permissions.allow, ["read"]);
    assert.ok(attemptedExpansion.clamps.some((item) => item.field === "permissions.allow.audit"));
  } finally {
    fabric.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("simulation is non-mutating and cross-organization links are denied by default", () => {
  const { root, fabric } = fixture();
  try {
    const { ecosystem, organization } = seed(fabric);
    const simulation = fabric.simulateNode({
      kind: "project",
      naturalKey: "project/simulated",
      name: "Simulated only",
      parentId: organization.id,
      context: {
        level: "gigatile",
        perspective: "dual",
        machineSubjective: "Hypothese de la machine",
        userObjective: "Effet observable pour l'utilisateur"
      }
    });
    assert.equal(simulation.allowed, true);
    assert.equal(simulation.wouldMutate, true);
    assert.equal(simulation.node.context.level, "gigatile");
    assert.equal(simulation.node.context.perspective, "dual");
    assert.equal(fabric.getNode(simulation.node.id), null);

    const secondOrganization = fabric.registerNode({
      kind: "organization",
      naturalKey: "organization/second",
      name: "Second Organization",
      parentId: ecosystem.id
    }).node;
    const source = fabric.registerNode({
      kind: "project",
      naturalKey: "project/source",
      name: "Source",
      parentId: organization.id
    }).node;
    const target = fabric.registerNode({
      kind: "project",
      naturalKey: "project/target",
      name: "Target",
      parentId: secondOrganization.id
    }).node;
    const link = fabric.simulateLink({ sourceId: source.id, targetId: target.id });
    assert.equal(link.allowed, false);
    assert.equal(link.issues[0].code, "cross-organization-link-denied");
  } finally {
    fabric.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("causal time orders agents that disagree about wall-clock time", () => {
  const { root, fabric } = fixture();
  try {
    const { organization } = seed(fabric);
    const project = fabric.registerNode({
      kind: "project",
      naturalKey: "project/time",
      name: "Temporal project",
      parentId: organization.id,
      time: {
        observedAt: "2026-07-29T12:00:00.000Z",
        effectiveAt: "2026-07-30T08:00:00.000Z",
        remoteLogicalTime: 40
      }
    }).node;
    const transition = fabric.transitionLifecycle(project.id, "dormant", {
      time: {
        observedAt: "2020-01-01T00:00:00.000Z",
        effectiveAt: "2030-01-01T00:00:00.000Z",
        remoteLogicalTime: 500
      }
    });
    assert.equal(transition.event.logicalTime, 501);
    assert.equal(transition.event.observedAt, "2020-01-01T00:00:00.000Z");
    assert.equal(transition.event.effectiveAt, "2030-01-01T00:00:00.000Z");
    const contextUpdate = fabric.updateContext(project.id, {
      level: "gigatile",
      perspective: "dual",
      utility: "contradictory",
      machineSubjective: "Deux agents signalent des etats incompatibles.",
      userObjective: "Le conflit reste visible et n'est pas fusionne silencieusement."
    }, {
      time: { remoteLogicalTime: 900 }
    });
    assert.equal(contextUpdate.event.logicalTime, 901);
    assert.equal(contextUpdate.node.context.utility, "contradictory");
    assert.equal(fabric.verifyEventChains().ok, true);
  } finally {
    fabric.close();
    rmSync(root, { recursive: true, force: true });
  }
});

test("100,000 deterministic identities distribute without collision across bounded partitions", () => {
  const identities = new Set();
  const partitions = new Map();
  for (let index = 0; index < 100_000; index += 1) {
    const id = deterministicId("organization", "scale-test", `organization/${index}`);
    identities.add(id);
    const partition = partitionFor(id, 256);
    partitions.set(partition, (partitions.get(partition) || 0) + 1);
  }
  assert.equal(identities.size, 100_000);
  assert.equal(partitions.size, 256);
  const counts = [...partitions.values()];
  assert.ok(Math.max(...counts) < Math.min(...counts) * 1.5);
});
