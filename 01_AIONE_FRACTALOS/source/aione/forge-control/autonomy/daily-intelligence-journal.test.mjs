import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import {
  createDailyIntelligenceJournal,
  INTELLIGENCE_CLASSES
} from "./daily-intelligence-journal.mjs";
import { testRuntimeRoot } from "./test-paths.mjs";

function baseConfig(root) {
  return {
    schema: "aione.daily-intelligence-journal.v1",
    enabled: true,
    runtimeRoot: root,
    timezone: "Europe/Paris",
    outputs: [
      "daily-user-review",
      "daily-owner-review",
      "local-operations-news",
      "opportunity-watch"
    ],
    preferences: {
      ownerId: "owner-test",
      languages: ["fr"],
      priorities: ["IA locale gratuite", "sécurité et robustesse", "apprentissage de la Forge"],
      excludeByDefault: ["publicité", "rumeur sans source"]
    },
    sourceClasses: {
      LOCAL_FACT: {
        networkRequired: false,
        minimumProvenance: ["sourcePathOrEndpoint", "observedAt", "contentHash"]
      },
      AUTHORIZED_EXTERNAL_FACT: {
        networkRequired: true,
        defaultDecision: "DENY_UNTIL_SOURCE_AUTHORIZED",
        minimumProvenance: ["canonicalUrl", "publisher", "publishedAt", "retrievedAt", "contentHash"]
      },
      INFERENCE: {
        networkRequired: false,
        mustBeLabelled: true,
        minimumProvenance: ["supportingItemIds", "confidence", "expiresAt"]
      },
      OPPORTUNITY: {
        networkRequired: "SOURCE_DEPENDENT",
        mustBeLabelled: true,
        minimumProvenance: ["supportingItemIds", "fitReason", "cost", "risk", "nextVerification"]
      }
    },
    localSources: ["S:\\AI_LAB\\Runtime", "S:\\AI_LAB\\Ecosystem\\PRIORITY.md"],
    externalSourceRegistry: [
      { id: "official-docs", enabled: true, canonicalUrlPrefix: "https://docs.example.test/" }
    ],
    ranking: {
      weights: {
        preferenceFit: 0.25,
        projectImpact: 0.25,
        evidenceQuality: 0.2,
        urgency: 0.15,
        novelty: 0.1,
        actionability: 0.05
      },
      maximumItemsUserReview: 15,
      maximumItemsOwnerReview: 25,
      deduplicateWindowDays: 14
    },
    guardrails: {
      fabricatedNews: "DENY",
      missingProvenance: "QUARANTINE",
      expiredItem: "ARCHIVE_FROM_DAILY_VIEW",
      secretOrPrivateIdentifier: "REDACT",
      externalFetch: "PER_SOURCE_PERMISSION_REQUIRED",
      externalAction: "OWNER_REQUIRED",
      emailDelivery: "SEPARATE_AUTHENTICATED_TRANSPORT",
      sourceCodeAttachment: false
    }
  };
}

function fixture() {
  const root = mkdtempSync(join(testRuntimeRoot(), "aione-daily-journal-"));
  const clock = { value: new Date("2026-07-30T06:00:00.000Z") };
  const config = baseConfig(root);
  const journal = createDailyIntelligenceJournal({
    config,
    runtimeRoot: root,
    now: () => new Date(clock.value)
  });
  return {
    root,
    clock,
    config,
    journal,
    cleanup: () => rmSync(root, { recursive: true, force: true })
  };
}

function localFact(suffix = "", overrides = {}) {
  return {
    sourceClass: "LOCAL_FACT",
    title: `État de la Forge locale ${suffix}`,
    summary: `Les workers IA locale gratuite sont opérationnels ${suffix}.`,
    details: "Mesure locale contrôlée.",
    topics: ["IA locale gratuite", "sécurité et robustesse"],
    projectIds: ["aione-core"],
    preferenceTags: ["IA locale gratuite"],
    provenance: {
      sourcePathOrEndpoint: "S:\\AI_LAB\\Runtime\\DualGpuDevelopment\\status.json",
      observedAt: "2026-07-30T05:55:00.000Z",
      contentHash: "a".repeat(64)
    },
    rankSignals: {
      projectImpact: 0.9,
      evidenceQuality: 1,
      urgency: 0.8,
      novelty: 0.5,
      actionability: 0.9
    },
    ...overrides
  };
}

function expectCode(code, operation) {
  assert.throws(operation, (error) => error?.code === code);
}

test("ingestion locale sans fetch, provenance, déduplication 14 jours et idempotence", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  assert.deepEqual(INTELLIGENCE_CLASSES, [
    "LOCAL_FACT",
    "AUTHORIZED_EXTERNAL_FACT",
    "INFERENCE",
    "OPPORTUNITY"
  ]);
  const first = fx.journal.ingest({ ...localFact(), idempotencyKey: "worker-status-2026-07-30" });
  assert.equal(first.item.status, "ACCEPTED");
  assert.match(first.item.itemHash, /^[a-f0-9]{64}$/);
  const sameKey = fx.journal.ingest({
    ...localFact("-changed"),
    idempotencyKey: "worker-status-2026-07-30"
  });
  assert.equal(sameKey.idempotent, true);
  assert.equal(sameKey.item.id, first.item.id);
  const duplicate = fx.journal.ingest(localFact());
  assert.equal(duplicate.idempotent, true);
  fx.clock.value = new Date("2026-08-14T06:00:00.000Z");
  const afterWindow = fx.journal.ingest(localFact());
  assert.equal(afterWindow.idempotent, false);
  assert.equal(fx.journal.listItems().length, 2);
});

test("preuves absentes et sources externes non autorisées vont en quarantaine", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const missing = fx.journal.ingest({
    sourceClass: "LOCAL_FACT",
    title: "Information incomplète",
    summary: "Aucune preuve suffisante.",
    provenance: {}
  }).item;
  assert.equal(missing.status, "QUARANTINED");
  assert.ok(missing.quarantineReasons.includes("MISSING_PROVENANCE:contentHash"));

  const external = fx.journal.ingest({
    sourceClass: "AUTHORIZED_EXTERNAL_FACT",
    title: "Annonce extérieure",
    summary: "Information fournie par un appelant, sans collecte du module.",
    provenance: {
      canonicalUrl: "https://unknown.example/news",
      publisher: "Unknown",
      publishedAt: "2026-07-30T04:00:00.000Z",
      retrievedAt: "2026-07-30T05:00:00.000Z",
      contentHash: "b".repeat(64)
    }
  }).item;
  assert.equal(external.status, "QUARANTINED");
  assert.ok(external.quarantineReasons.includes("EXTERNAL_SOURCE_NOT_AUTHORIZED"));

  const authorized = fx.journal.ingest({
    sourceClass: "AUTHORIZED_EXTERNAL_FACT",
    title: "Documentation officielle",
    summary: "Fait externe autorisé et fourni explicitement.",
    provenance: {
      canonicalUrl: "https://docs.example.test/release",
      publisher: "Example",
      publishedAt: "2026-07-30T04:00:00.000Z",
      retrievedAt: "2026-07-30T05:00:00.000Z",
      contentHash: "c".repeat(64)
    }
  }).item;
  assert.equal(authorized.status, "ACCEPTED");
});

test("inférences et opportunités sont étiquetées, sourcées et expirables", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const source = fx.journal.ingest(localFact("-source")).item;
  const inference = fx.journal.ingest({
    sourceClass: "INFERENCE",
    title: "Risque de saturation",
    summary: "La hausse de charge pourrait réduire la fluidité.",
    topics: ["sécurité et robustesse"],
    provenance: {
      supportingItemIds: [source.id],
      confidence: 0.72,
      expiresAt: "2026-08-02T06:00:00.000Z"
    }
  }).item;
  assert.equal(inference.status, "ACCEPTED");
  assert.ok(inference.labels.includes("ANALYSIS_NOT_FACT"));
  assert.deepEqual(inference.provenance.supportingItemIds, [source.id]);

  const opportunity = fx.journal.ingest({
    sourceClass: "OPPORTUNITY",
    title: "Atelier de robustesse",
    summary: "Tester une session guidée autour des incidents.",
    topics: ["apprentissage de la Forge", "sécurité et robustesse"],
    provenance: {
      supportingItemIds: [source.id],
      fitReason: "Correspond aux priorités Owner",
      cost: "45 minutes locales",
      risk: "fatigue",
      nextVerification: "2026-07-31T06:00:00.000Z"
    }
  }).item;
  assert.equal(opportunity.status, "ACCEPTED");
  assert.ok(opportunity.labels.includes("OPPORTUNITY"));

  const unsupported = fx.journal.ingest({
    sourceClass: "INFERENCE",
    title: "Inférence sans source",
    summary: "Cette analyse doit rester isolée.",
    provenance: {
      supportingItemIds: ["missing-id"],
      confidence: 0.5,
      expiresAt: "2026-08-02T06:00:00.000Z"
    }
  }).item;
  assert.equal(unsupported.status, "QUARANTINED");
  assert.ok(unsupported.quarantineReasons.some((reason) => reason.startsWith("SUPPORTING_ITEM_NOT_FOUND")));

  fx.clock.value = new Date("2026-08-03T06:00:00.000Z");
  assert.equal(fx.journal.ranked({ audience: "USER", at: fx.clock.value }).some((item) => item.id === inference.id), false);
});

test("ranking suit les préférences et masque par défaut le contenu exclu", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const preferred = fx.journal.ingest(localFact("-preferred")).item;
  const advertisement = fx.journal.ingest(
    localFact("-ad", {
      title: "Publicité",
      summary: "Publicité sans rapport avec les projets.",
      topics: ["publicité"],
      preferenceTags: [],
      rankSignals: {
        projectImpact: 1,
        evidenceQuality: 1,
        urgency: 1,
        novelty: 1,
        actionability: 1
      },
      provenance: {
        sourcePathOrEndpoint: "S:\\AI_LAB\\Runtime\\advertisement.json",
        observedAt: "2026-07-30T05:56:00.000Z",
        contentHash: "d".repeat(64)
      }
    })
  ).item;
  const user = fx.journal.ranked({ audience: "USER" });
  assert.equal(user[0].id, preferred.id);
  assert.equal(user.some((item) => item.id === advertisement.id), false);
  const owner = fx.journal.ranked({ audience: "OWNER" });
  assert.equal(owner.some((item) => item.id === advertisement.id), true);
});

test("redaction précède stockage et aucune donnée privée/code source ne ressort", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const item = fx.journal.ingest(
    localFact("-redact", {
      summary: "Contact portfolio@example.invalid token=verysecretvalue",
      details: "Chemin %USERPROFILE%\\secret ```js\nconsole.log('secret')\n```",
      provenance: {
        sourcePathOrEndpoint: "S:\\AI_LAB\\Runtime\\redaction.json",
        observedAt: "2026-07-30T05:57:00.000Z",
        contentHash: "e".repeat(64)
      }
    })
  ).item;
  const raw = readFileSync(fx.journal.paths.ledger, "utf8");
  assert.doesNotMatch(raw, /user@example\.test|verysecretvalue|C:\\\\Users\\\\the-owner|console\.log/);
  assert.match(raw, /PRIVATE_EMAIL|SECRET_REDACTED|PRIVATE_USER_PATH|SOURCE_CODE_REDACTED/);
  assert.ok(item.redactions.length >= 4);
});

test("revues User/Owner JSON+Markdown, idempotence, reprise et intégrité", (context) => {
  const fx = fixture();
  context.after(fx.cleanup);
  const source = fx.journal.ingest(localFact("-review")).item;
  fx.journal.ingest({
    sourceClass: "INFERENCE",
    title: "Charge à surveiller",
    summary: "Une surveillance thermique est recommandée.",
    topics: ["sécurité et robustesse"],
    provenance: {
      supportingItemIds: [source.id],
      confidence: 0.8,
      expiresAt: "2026-08-02T06:00:00.000Z"
    }
  });
  fx.journal.ingest({
    sourceClass: "LOCAL_FACT",
    title: "Fait sans preuve",
    summary: "Visible seulement à Owner en quarantaine.",
    provenance: {}
  });

  const first = fx.journal.generateDailyReviews();
  assert.equal(first.idempotent, false);
  assert.equal(first.userReview.audience, "USER");
  assert.equal(first.ownerReview.audience, "OWNER");
  assert.equal(first.userReview.items.some((item) => item.status === "QUARANTINED"), false);
  assert.equal(first.ownerReview.items.some((item) => item.status === "QUARANTINED"), true);
  const userMarkdown = readFileSync(first.files.user.currentMarkdown, "utf8");
  const ownerMarkdown = readFileSync(first.files.owner.currentMarkdown, "utf8");
  assert.match(userMarkdown, /⚠ INFERENCE/);
  assert.match(userMarkdown, new RegExp(source.id));
  assert.match(ownerMarkdown, /Quarantaine/);

  const repeated = fx.journal.generateDailyReviews();
  assert.equal(repeated.idempotent, true);
  const resumed = createDailyIntelligenceJournal({
    config: fx.config,
    runtimeRoot: fx.root,
    now: () => new Date(fx.clock.value)
  });
  assert.equal(resumed.listItems().length, 3);
  assert.equal(resumed.generateDailyReviews().idempotent, true);
  assert.deepEqual(
    { ok: resumed.verifyIntegrity().ok, items: resumed.verifyIntegrity().items, reviews: resumed.verifyIntegrity().reviews },
    { ok: true, items: 3, reviews: 1 }
  );

  const markdownOriginal = readFileSync(first.files.user.versionedMarkdown, "utf8");
  writeFileSync(first.files.user.versionedMarkdown, `${markdownOriginal}\nALTÉRATION`, "utf8");
  expectCode("INTEGRITY_ERROR", () => resumed.generateDailyReviews());
  writeFileSync(first.files.user.versionedMarkdown, markdownOriginal, "utf8");
  assert.equal(resumed.verifyIntegrity().ok, true);

  const lines = readFileSync(fx.journal.paths.ledger, "utf8").trim().split(/\r?\n/);
  const event = JSON.parse(lines[0]);
  event.data.item.title = "ALTÉRÉ";
  lines[0] = JSON.stringify(event);
  writeFileSync(fx.journal.paths.ledger, `${lines.join("\n")}\n`, "utf8");
  expectCode("INTEGRITY_ERROR", () => resumed.listItems());
});
