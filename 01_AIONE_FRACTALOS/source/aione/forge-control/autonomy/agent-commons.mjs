import { createHash, randomBytes, randomUUID } from "node:crypto";
import {
  appendFileSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inspectUntrustedInput } from "./input-security-firewall.mjs";

const MODULE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HUMAN_ROLES = new Set(["PUBLIC_USER", "AUTHENTICATED_USER", "OWNER"]);
const ACTION_TYPES = new Set(["YES_NO", "YES_NO_MAYBE", "SCALE_1_5", "SELECT", "TIME_SELECT", "TEXT"]);
const IMPORTANCE_LEVELS = new Set(["NORMAL", "IMPORTANT"]);
const HUMAN_MESSAGE_KINDS = new Set(["CHAT", "QUESTION", "IDEA", "REQUEST", "ADJUSTMENT"]);
const PROPOSAL_CATEGORIES = new Set(["SELF", "PROJECT", "USER", "COLLABORATION", "SYSTEM"]);

function hash(value) {
  return createHash("sha256").update(JSON.stringify(value), "utf8").digest("hex");
}

function clean(value, label, maximum) {
  const text = String(value || "").replaceAll("\0", "").trim();
  if (!text || text.length > maximum) throw new Error(`${label} invalide`);
  return text;
}

function readLines(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, "utf8").split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
}

function utcDay(value) {
  return new Date(value).toISOString().slice(0, 10);
}

function normalizeActions(value) {
  if (!value) return [{ type: "YES_NO_MAYBE", label: "Décision", options: ["OUI", "NON", "PEUT_ETRE"] }];
  if (!Array.isArray(value) || value.length < 1 || value.length > 5) throw new Error("actions invalides");
  return value.map((action) => {
    const type = String(action.type || "").toUpperCase();
    if (!ACTION_TYPES.has(type)) throw new Error(`type d'action invalide: ${type}`);
    const options = (action.options || []).map((item) => clean(item, "option", 120));
    if (["SELECT", "TIME_SELECT"].includes(type) && options.length < 1) throw new Error("options requises");
    return { type, label: clean(action.label || "Réponse", "action.label", 160), options };
  });
}

function cleanList(value, label, maximumItems = 12, maximumChars = 500) {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value) || value.length > maximumItems) throw new Error(`${label} invalide`);
  return [...new Set(value.map((item) => clean(item, label, maximumChars)))];
}

function normalizeImportance(value, fallback = "NORMAL") {
  const importance = String(value || fallback).toUpperCase();
  if (!IMPORTANCE_LEVELS.has(importance)) throw new Error("importance invalide");
  return importance;
}

function normalizeProposal(value) {
  if (!value) return null;
  if (typeof value !== "object" || Array.isArray(value)) throw new Error("proposal invalide");
  const category = String(value.category || "SYSTEM").toUpperCase();
  if (!PROPOSAL_CATEGORIES.has(category)) throw new Error("proposal.category invalide");
  const priority = String(value.priority || "P2").toUpperCase();
  if (!/^P[0-3]$/u.test(priority)) throw new Error("proposal.priority invalide");
  return {
    category,
    project: clean(value.project || "AIONE", "proposal.project", 200),
    title: clean(value.title, "proposal.title", 240),
    objective: clean(value.objective, "proposal.objective", 4000),
    priority,
    acceptanceCriteria: cleanList(value.acceptanceCriteria, "proposal.acceptanceCriteria", 12, 600)
  };
}

function eventHash(event) {
  const unsigned = { ...event };
  delete unsigned.hash;
  return hash(unsigned);
}

export class AgentCommons {
  constructor({
    configPath = join(MODULE_ROOT, "config", "agent-commons.json"),
    now = () => new Date()
  } = {}) {
    this.config = JSON.parse(readFileSync(resolve(configPath), "utf8"));
    this.now = now;
    this.runtimeRoot = resolve(this.config.runtimeRoot);
    this.paths = Object.freeze({
      ledger: join(this.runtimeRoot, "agent-commons-ledger.jsonl"),
      mailOutbox: join(this.runtimeRoot, "mail-outbox.jsonl"),
      lock: join(this.runtimeRoot, ".agent-commons.lock")
    });
    mkdirSync(this.runtimeRoot, { recursive: true });
    this.accounts = new Map(this.config.accounts.map((account) => [account.id, Object.freeze({ ...account })]));
  }

  withLock(operation) {
    let descriptor;
    try {
      descriptor = openSync(this.paths.lock, "wx");
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, at: this.now().toISOString() }));
      return operation();
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
      if (descriptor !== undefined && existsSync(this.paths.lock)) unlinkSync(this.paths.lock);
    }
  }

  verify(path = this.paths.ledger) {
    const events = readLines(path);
    const issues = [];
    let previousHash = null;
    events.forEach((event, index) => {
      if (event.previousHash !== previousHash) issues.push({ index, code: "CHAIN_MISMATCH" });
      if (eventHash(event) !== event.hash) issues.push({ index, code: "HASH_MISMATCH" });
      previousHash = event.hash;
    });
    return { ok: issues.length === 0, events: events.length, head: previousHash, issues };
  }

  append(path, type, data) {
    const events = readLines(path);
    const event = {
      schema: "aione.agent-commons-event.v1",
      sequence: events.length + 1,
      eventId: randomUUID(),
      at: this.now().toISOString(),
      type,
      previousHash: events.at(-1)?.hash || null,
      data
    };
    event.hash = eventHash(event);
    appendFileSync(path, `${JSON.stringify(event)}\n`, "utf8");
    return event;
  }

  snapshot() {
    const posts = new Map();
    const comments = [];
    const humanMessages = new Map();
    for (const event of readLines(this.paths.ledger)) {
      if (event.type === "POST_CREATED") posts.set(event.data.id, structuredClone(event.data));
      if (event.type === "HUMAN_RESPONSE") {
        const post = posts.get(event.data.postId);
        if (post) {
          post.state = "ANSWERED";
          post.response = structuredClone(event.data);
        }
      }
      if (event.type === "POST_SCHEDULED") {
        const post = posts.get(event.data.postId);
        if (post) post.schedule = structuredClone(event.data.schedule);
      }
      if (event.type === "COMMENT_CREATED") comments.push(structuredClone(event.data));
      if (event.type === "HUMAN_MESSAGE_CREATED") humanMessages.set(event.data.id, structuredClone(event.data));
      if (event.type === "HUMAN_MESSAGE_LINKED") {
        const message = humanMessages.get(event.data.messageId);
        if (message) message.intake = structuredClone(event.data.intake);
      }
    }
    return { posts: [...posts.values()], comments, humanMessages: [...humanMessages.values()] };
  }

  assertAi(actor) {
    const account = this.accounts.get(String(actor?.id || actor?.principalId || ""));
    if (!account || actor?.principalType !== "AI" || account.role !== actor?.role) {
      throw new Error("AI_IDENTITY_NOT_REGISTERED");
    }
    return account;
  }

  assertHuman(actor, { write = false } = {}) {
    const role = String(actor?.role || "").toUpperCase();
    if (actor?.principalType !== "HUMAN" || !HUMAN_ROLES.has(role)) throw new Error("HUMAN_IDENTITY_REQUIRED");
    if (write && role === "PUBLIC_USER") throw new Error("PUBLIC_USER_OBSERVE_ONLY");
    return { id: clean(actor.id || actor.principalId, "human.id", 160), role };
  }

  createPost(input) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const account = this.assertAi(input.actor);
      const channel = String(input.channel || "").toUpperCase();
      if (!this.config.channels.includes(channel)) throw new Error("CHANNEL_NOT_ALLOWED");
      const loopId = clean(input.loopId, "loopId", 200);
      const state = this.snapshot();
      if (state.posts.some((post) => post.loopId === loopId)) throw new Error("ONE_AI_POST_PER_LOOP");
      const today = utcDay(this.now());
      const dailyCount = state.posts.filter((post) => post.authorId === account.id && utcDay(post.createdAt) === today).length;
      if (dailyCount >= Number(this.config.limits.maximumAiPostsPerAccountPerDay || 12)) throw new Error("AI_DAILY_POST_QUOTA");
      if (channel === "HUMAN_REQUEST") {
        const open = state.posts.filter((post) => post.channel === channel && post.state === "OPEN").length;
        if (open >= Number(this.config.limits.maximumOpenHumanRequests || 50)) throw new Error("HUMAN_REQUEST_QUOTA");
      }
      const title = clean(input.title, "title", Number(this.config.limits.maximumTitleChars || 240));
      const summary = clean(input.summary, "summary", Number(this.config.limits.maximumSummaryChars || 1200));
      const details = clean(input.details || summary, "details", Number(this.config.limits.maximumDetailsChars || 12000));
      const proposal = normalizeProposal(input.proposal);
      if (proposal && channel !== "HUMAN_REQUEST") throw new Error("PROPOSAL_REQUIRES_HUMAN_REQUEST");
      const importance = normalizeImportance(input.importance, channel === "HUMAN_REQUEST" ? "IMPORTANT" : "NORMAL");
      const screened = inspectUntrustedInput(`${title}\n${summary}\n${details}\n${JSON.stringify(proposal || {})}`);
      const contentFingerprint = hash({ channel, account: account.id, title, summary, details, proposal });
      const recentDuplicate = state.posts.find((post) =>
        post.contentFingerprint === contentFingerprint &&
        this.now().getTime() - new Date(post.createdAt).getTime() < 24 * 60 * 60 * 1000
      );
      if (recentDuplicate) return { ok: true, duplicate: true, post: recentDuplicate };
      const post = {
        schema: "aione.agent-commons-post.v1",
        id: randomUUID(),
        loopId,
        channel,
        authorId: account.id,
        authorName: account.displayName,
        authorRole: account.role,
        title,
        summary: screened.decision === "QUARANTINE" ? "Contenu mis en quarantaine par le pare-feu cognitif." : summary,
        details: screened.decision === "QUARANTINE" ? `[QUARANTINE ${screened.reasons.join(", ")} ${screened.fingerprint}]` : details,
        contentFingerprint,
        state: screened.decision === "QUARANTINE" ? "QUARANTINED" : channel === "HUMAN_REQUEST" ? "OPEN" : "PUBLISHED_LOCAL",
        direction: "AI_TO_HUMAN",
        importance,
        requiresHumanReply: channel === "HUMAN_REQUEST",
        actions: channel === "HUMAN_REQUEST" ? normalizeActions(input.actions) : [],
        audience: channel === "HUMAN_REQUEST" ? clean(input.audience || "OWNER", "audience", 80) : "LOCAL_ECOSYSTEM",
        proposal: screened.decision === "QUARANTINE" ? null : proposal,
        createdAt: this.now().toISOString(),
        publicPublication: false,
        actionCapability: channel === "HUMAN_REQUEST" ? randomBytes(24).toString("base64url") : null
      };
      this.append(this.paths.ledger, "POST_CREATED", post);
      if (post.channel === "HUMAN_REQUEST" && post.state === "OPEN") this.prepareMailDigest(post);
      return { ok: true, duplicate: false, post };
    });
  }

  createHumanMessage(input) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const human = this.assertHuman(input.actor, { write: true });
      const kind = String(input.kind || "REQUEST").toUpperCase();
      if (!HUMAN_MESSAGE_KINDS.has(kind)) throw new Error("HUMAN_MESSAGE_KIND_INVALID");
      const title = clean(input.title || "Message à la Forge", "title", Number(this.config.limits.maximumTitleChars || 240));
      const text = clean(input.text, "text", Number(this.config.limits.maximumDetailsChars || 12000));
      const importance = normalizeImportance(input.importance, kind === "CHAT" ? "NORMAL" : "IMPORTANT");
      const project = clean(input.project || "AIONE", "project", 200);
      const replyToPostId = String(input.replyToPostId || "").trim();
      const state = this.snapshot();
      if (replyToPostId && !state.posts.some((post) => post.id === replyToPostId)) throw new Error("REPLY_POST_NOT_FOUND");
      const clientMessageId = String(input.clientMessageId || "").replaceAll("\0", "").trim().slice(0, 200);
      if (clientMessageId) {
        const duplicate = state.humanMessages.find((message) => message.clientMessageId === clientMessageId);
        if (duplicate) return { ok: true, duplicate: true, message: duplicate };
      }
      const screened = inspectUntrustedInput(`${title}\n${text}`);
      const message = {
        schema: "aione.agent-commons-human-message.v1",
        id: randomUUID(),
        clientMessageId: clientMessageId || randomUUID(),
        direction: "HUMAN_TO_AI",
        actorIdHash: hash(human.id),
        actorRole: human.role,
        kind,
        importance,
        project,
        title,
        text: screened.decision === "QUARANTINE"
          ? `Contenu mis en quarantaine par le pare-feu cognitif (${screened.fingerprint}).`
          : text,
        replyToPostId: replyToPostId || null,
        state: screened.decision === "QUARANTINE" ? "QUARANTINED" : "RECEIVED",
        createdAt: this.now().toISOString()
      };
      this.append(this.paths.ledger, "HUMAN_MESSAGE_CREATED", message);
      return { ok: true, duplicate: false, message };
    });
  }

  linkHumanMessage(messageId, intake) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const message = this.snapshot().humanMessages.find((item) => item.id === messageId);
      if (!message) throw new Error("HUMAN_MESSAGE_NOT_FOUND");
      if (message.intake) return { ok: true, idempotent: true, intake: message.intake };
      const normalized = {
        ideaId: clean(intake.ideaId, "intake.ideaId", 200),
        taskId: clean(intake.taskId, "intake.taskId", 200),
        status: clean(intake.status || "05-clarify", "intake.status", 80)
      };
      this.append(this.paths.ledger, "HUMAN_MESSAGE_LINKED", { messageId, intake: normalized });
      return { ok: true, idempotent: false, intake: normalized };
    });
  }

  attachSchedule(postId, schedule) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const post = this.snapshot().posts.find((item) => item.id === postId);
      if (!post) throw new Error("POST_NOT_FOUND");
      if (post.schedule) return { ok: true, idempotent: true, schedule: post.schedule };
      const normalized = {
        taskId: clean(schedule.taskId, "schedule.taskId", 200),
        status: clean(schedule.status || "20-todo", "schedule.status", 80),
        project: clean(schedule.project || post.proposal?.project || "AIONE", "schedule.project", 200),
        scheduledAt: this.now().toISOString()
      };
      this.append(this.paths.ledger, "POST_SCHEDULED", { postId, schedule: normalized });
      return { ok: true, idempotent: false, schedule: normalized };
    });
  }

  prepareMailDigest(post) {
    const recipient = this.config.transports.emailOutbox.recipient;
    const data = {
      schema: "aione.agent-commons-mail-outbox.v1",
      id: randomUUID(),
      to: recipient,
      subject: `[AIONE] ${post.title}`,
      summary: post.summary,
      actionUrl: `${this.config.transports.tailscaleWebInbox.url}?request=${encodeURIComponent(post.id)}`,
      fallbackActionUrl: this.config.transports.tailscaleWebInbox.fallbackUrl
        ? `${this.config.transports.tailscaleWebInbox.fallbackUrl}?request=${encodeURIComponent(post.id)}`
        : null,
      sendState: this.config.transports.emailOutbox.sendEnabled ? "READY" : "WAITING_AUTHENTICATED_MAIL_TRANSPORT",
      sourcePostId: post.id,
      createdAt: this.now().toISOString()
    };
    this.append(this.paths.mailOutbox, "MAIL_PREPARED", data);
    return data;
  }

  respond(postId, { actor, action, text = "", capability = "" } = {}) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const human = this.assertHuman(actor, { write: true });
      const post = this.snapshot().posts.find((item) => item.id === postId);
      if (!post || post.channel !== "HUMAN_REQUEST") throw new Error("HUMAN_REQUEST_NOT_FOUND");
      if (post.state === "ANSWERED") return { ok: true, idempotent: true, post };
      if (post.state !== "OPEN") throw new Error("HUMAN_REQUEST_NOT_OPEN");
      if (capability !== post.actionCapability) throw new Error("ACTION_CAPABILITY_MISMATCH");
      const normalizedAction = clean(action, "action", 160);
      const available = post.actions.flatMap((item) => item.options);
      if (available.length && !available.includes(normalizedAction)) throw new Error("ACTION_NOT_OFFERED");
      const response = {
        schema: "aione.agent-commons-human-response.v1",
        responseId: randomUUID(),
        postId,
        actorIdHash: hash(human.id),
        actorRole: human.role,
        action: normalizedAction,
        text: String(text || "").replaceAll("\0", "").trim().slice(0, 4000),
        respondedAt: this.now().toISOString()
      };
      this.append(this.paths.ledger, "HUMAN_RESPONSE", response);
      return { ok: true, idempotent: false, response, post: { ...post, state: "ANSWERED", response } };
    });
  }

  comment(postId, { actor, text } = {}) {
    return this.withLock(() => {
      this.verifyOrThrow();
      const human = this.assertHuman(actor, { write: true });
      if (!this.snapshot().posts.some((post) => post.id === postId)) throw new Error("POST_NOT_FOUND");
      const comment = {
        schema: "aione.agent-commons-comment.v1",
        id: randomUUID(),
        postId,
        actorIdHash: hash(human.id),
        actorRole: human.role,
        text: clean(text, "comment", 4000),
        createdAt: this.now().toISOString()
      };
      this.append(this.paths.ledger, "COMMENT_CREATED", comment);
      return { ok: true, comment };
    });
  }

  feed({ channel, limit = 200 } = {}) {
    const state = this.snapshot();
    const posts = state.posts
      .filter((post) => !channel || post.channel === channel)
      .sort((left, right) => {
        const leftPinned = left.state === "OPEN" && left.importance === "IMPORTANT" ? 1 : 0;
        const rightPinned = right.state === "OPEN" && right.importance === "IMPORTANT" ? 1 : 0;
        return rightPinned - leftPinned || right.createdAt.localeCompare(left.createdAt);
      })
      .slice(0, Math.max(1, Math.min(Number(limit) || 200, 500)))
      .map((post) => ({ ...post, comments: state.comments.filter((comment) => comment.postId === post.id) }));
    const humanMessages = state.humanMessages
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
      .slice(0, Math.max(1, Math.min(Number(limit) || 200, 500)));
    return { posts, humanMessages, accounts: [...this.accounts.values()] };
  }

  notifications() {
    const windowsToast = this.config.transports.windowsToast || {};
    const remoteInbox = this.config.transports.tailscaleWebInbox || {};
    return this.feed({ channel: "HUMAN_REQUEST", limit: 100 }).posts
      .filter((post) => post.state === "OPEN")
      .map((post) => ({
        ...post,
        pcActionUrl: `${windowsToast.url || "http://127.0.0.1:4310/agents-space.html"}?request=${encodeURIComponent(post.id)}`,
        pcFallbackActionUrl: windowsToast.fallbackUrl
          ? `${windowsToast.fallbackUrl}?request=${encodeURIComponent(post.id)}`
          : null,
        remoteActionUrl: remoteInbox.url
          ? `${remoteInbox.url}?request=${encodeURIComponent(post.id)}`
          : null
      }));
  }

  status() {
    const state = this.snapshot();
    return {
      schema: "aione.agent-commons-status.v1",
      accounts: this.accounts.size,
      channels: [...this.config.channels],
      posts: state.posts.length,
      humanMessages: state.humanMessages.length,
      openHumanRequests: state.posts.filter((post) => post.channel === "HUMAN_REQUEST" && post.state === "OPEN").length,
      integrity: this.verify(),
      transports: this.config.transports,
      onePostPerLoop: true,
      publicPublication: false
    };
  }

  verifyOrThrow() {
    const result = this.verify();
    if (!result.ok) throw new Error("AGENT_COMMONS_LEDGER_TAMPERED");
    return result;
  }
}

export function createAgentCommons(options = {}) {
  return new AgentCommons(options);
}
