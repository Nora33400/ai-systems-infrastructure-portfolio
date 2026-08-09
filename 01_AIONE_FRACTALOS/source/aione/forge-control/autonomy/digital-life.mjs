import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync
} from "node:fs";
import { dirname, join, resolve } from "node:path";

function expandEnvironmentPath(value) {
  return resolve(String(value || "").replace(/%([^%]+)%/g, (_, name) => process.env[name] || `%${name}%`));
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function atomicJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  renameSync(temporary, path);
}

function atomicText(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, value.endsWith("\n") ? value : `${value}\n`, "utf8");
  renameSync(temporary, path);
}

function localDay(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localDateTime(date, time) {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  return new Date(year, month - 1, day, hour, minute, 0, 0);
}

function weekdayCode(date) {
  return ["SU", "MO", "TU", "WE", "TH", "FR", "SA"][date.getDay()];
}

function defaultState(clock) {
  return {
    schema: "aione.digital-life-state.v1",
    createdAt: clock().toISOString(),
    updatedAt: clock().toISOString(),
    meetingOverrides: {},
    notified: {},
    briefs: []
  };
}

function defaultLearningConfig() {
  return {
    schema: "aione.learning-coaching-os.unconfigured.v1",
    authority: "AIONE Autonomous Forge",
    status: "NOT_CONFIGURED",
    attentionModes: [],
    sessionTemplates: [],
    groups: [],
    councilFlow: [],
    recurringSessions: [],
    weeklyAgentCapacity: {
      minimumAgentHours: 0,
      resourceGovernorRequired: true,
      neverIdlePolicy: "Aucune action externe ou écriture non autorisée."
    }
  };
}

export class DigitalLifeRuntime {
  constructor({
    root = resolve(process.cwd()),
    configPath = join(root, "config", "digital-life.json"),
    learningPath = join(root, "config", "learning-coaching-os.json"),
    portfolioPath = join(root, "config", "project-portfolio.json"),
    autonomyStatePath,
    stateDir,
    clock = () => new Date()
  } = {}) {
    this.root = resolve(root);
    this.configPath = resolve(configPath);
    this.learningPath = resolve(learningPath);
    this.portfolioPath = resolve(portfolioPath);
    this.config = JSON.parse(readFileSync(this.configPath, "utf8"));
    this.learning = readJson(this.learningPath, defaultLearningConfig());
    this.portfolio = JSON.parse(readFileSync(this.portfolioPath, "utf8"));
    this.clock = clock;
    this.stateDir = stateDir ? resolve(stateDir) : expandEnvironmentPath(this.config.storage);
    this.autonomyStatePath = autonomyStatePath || join(dirname(this.stateDir), "ForgeAutonomy", "state.json");
    this.paths = {
      state: join(this.stateDir, "state.json"),
      briefs: join(this.stateDir, "briefs"),
      meetings: join(this.stateDir, "meetings")
    };
    mkdirSync(this.paths.briefs, { recursive: true });
    mkdirSync(this.paths.meetings, { recursive: true });
    if (!existsSync(this.paths.state)) atomicJson(this.paths.state, defaultState(this.clock));
  }

  readState() {
    return readJson(this.paths.state, defaultState(this.clock));
  }

  writeState(state) {
    state.updatedAt = this.clock().toISOString();
    const cutoff = this.clock().getTime() - Number(this.config.privacy.retentionDays || 90) * 86400000;
    state.notified = Object.fromEntries(
      Object.entries(state.notified || {}).filter(([, value]) => new Date(value).getTime() >= cutoff)
    );
    state.briefs = (state.briefs || []).slice(-120);
    atomicJson(this.paths.state, state);
  }

  meetings() {
    const overrides = this.readState().meetingOverrides || {};
    return this.config.proposedMeetings.map((meeting) => ({
      ...meeting,
      status: overrides[meeting.id]?.status || meeting.status,
      updatedAt: overrides[meeting.id]?.updatedAt || null
    }));
  }

  setMeetingStatus(id, status) {
    if (!["PROPOSED", "CONFIRMED", "DECLINED"].includes(status)) {
      throw new Error(`Statut de rendez-vous invalide: ${status}`);
    }
    if (!this.config.proposedMeetings.some((meeting) => meeting.id === id)) {
      throw new Error(`Rendez-vous inconnu: ${id}`);
    }
    const state = this.readState();
    state.meetingOverrides[id] = { status, updatedAt: this.clock().toISOString() };
    this.writeState(state);
    return this.meetings().find((meeting) => meeting.id === id);
  }

  status() {
    const autonomy = readJson(this.autonomyStatePath, null);
    const studios = this.config.studios.reduce((counts, studio) => {
      counts[studio.status] = (counts[studio.status] || 0) + 1;
      return counts;
    }, {});
    return {
      ok: true,
      localOnly: this.config.privacy.localOnly,
      externalActionsDefault: this.config.privacy.externalActionsDefault,
      stateDir: this.stateDir,
      studios,
      meetings: this.meetings(),
      learning: {
        authority: this.learning.authority,
        status: this.learning.status,
        attentionModes: this.learning.attentionModes,
        sessionTemplates: this.learning.sessionTemplates,
        groups: this.learning.groups,
        councilFlow: this.learning.councilFlow,
        weeklyAgentCapacity: this.learning.weeklyAgentCapacity,
        recurringSessions: this.learning.recurringSessions,
        observation: this.learning.observation,
        reports: this.learning.reports
      },
      autonomy: autonomy ? {
        paused: autonomy.paused,
        lastCycle: autonomy.lastCycle,
        nextCycle: autonomy.nextCycle,
        metrics: autonomy.metrics
      } : { available: false }
    };
  }

  prepareMeeting(studioId, horizon = "30d") {
    const studio = this.config.studios.find((entry) => entry.id === studioId);
    if (!studio) throw new Error(`Studio inconnu: ${studioId}`);
    const content = [
      `# Préparation — ${studio.name}`,
      "",
      `- Statut : \`${studio.status}\``,
      `- Responsable : \`${studio.lead}\``,
      `- Modèle local : \`${studio.model}\``,
      `- Autorité maximale : \`${studio.authority}\``,
      `- Horizon : \`${horizon}\``,
      studio.disclaimer ? `- Limite : ${studio.disclaimer}` : "",
      "",
      "## Ordre du jour",
      "",
      "1. reformuler le besoin et le résultat attendu ;",
      "2. comparer trois plans d'exécution ;",
      "3. chiffrer ressources, dépendances et coût local ;",
      "4. préciser sécurité, droits, tests et preuves ;",
      "5. définir arrêt, retour arrière et données conservées ;",
      "6. lister les extensions à autoriser ;",
      "7. demander un accord avant toute activation.",
      "",
      "## Frontière",
      "",
      "Ce document prépare un accord. Il n'active ni moteur, ni connecteur, ni",
      "publication et ne crée aucun rendez-vous externe."
    ].filter(Boolean).join("\n");
    const path = join(this.paths.meetings, `${studio.id}-${horizon}.md`);
    atomicText(path, content);
    return { studioId, horizon, path, content };
  }

  dailyBrief(date = localDay(this.clock())) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error(`Date invalide: ${date}`);
    const meetings = this.meetings().filter((meeting) => meeting.date === date && meeting.status !== "DECLINED");
    const confirmed = meetings.filter((meeting) => meeting.status === "CONFIRMED");
    const proposed = meetings.filter((meeting) => meeting.status === "PROPOSED");
    const autonomy = readJson(this.autonomyStatePath, null);
    const currentProjects = this.portfolio.projects.filter((project) => project.category === "CURRENT");
    const activeStudios = this.config.studios.filter((studio) => studio.status.startsWith("ACTIVE"));
    const dateObject = localDateTime(date, "12:00");
    const routines = (this.config.routines || []).filter((routine) =>
      routine.status === "ACTIVE" && routine.days.includes(weekdayCode(dateObject))
    );
    const lines = [
      `# Brief AIONE — ${date}`,
      "",
      "## État",
      "",
      `- autonomie : ${autonomy?.paused ? "PAUSED" : autonomy ? autonomy.lastCycle?.status || "INITIALIZED" : "état non encore disponible"} ;`,
      `- projets courants recensés : ${currentProjects.length} ;`,
      `- studios actifs : ${activeStudios.map((studio) => studio.name).join(", ") || "aucun"} ;`,
      "- actions externes : verrouillées.",
      "",
      "## Validations",
      "",
      proposed.length
        ? `- ${proposed.length} rendez-vous restent à valider, déplacer ou refuser.`
        : "- Aucun rendez-vous en attente de validation.",
      "- Définir le résultat utilisateur de FractalOS `PRIO-0002`.",
      "- Choisir les projets et extensions autorisés à passer à `CODE_ALLOWLISTED`.",
      "- Choisir le premier studio de production à sortir de veille.",
      "",
      "## Planning local",
      "",
      ...meetings.map((meeting) => {
        const studio = this.config.studios.find((entry) => entry.id === meeting.studio);
        return `- ${meeting.start} — ${studio?.name || meeting.studio} (${meeting.durationMinutes} min, ${meeting.status})`;
      }),
      ...(meetings.length ? [] : ["- Aucun bloc local pour cette date."]),
      ...routines.map((routine) => `- ${routine.time} — ${routine.title} (routine locale)`),
      "",
      "## Apprentissage et bien-être",
      "",
      "- une session d'apprentissage courte avec une note reliée ;",
      "- une pause de mouvement avant le bloc de l'après-midi ;",
      "- une revue de l'attention et des notifications en fin de journée ;",
      "- ces propositions sont non cliniques et adaptables.",
      "",
      "## Prochaine action exacte",
      "",
      confirmed.length
        ? `Ouvrir la préparation du premier rendez-vous confirmé à ${confirmed[0].start}.`
        : "Valider, déplacer ou refuser les rendez-vous proposés ; aucune création externe n'est nécessaire."
    ];
    const content = lines.join("\n");
    const path = join(this.paths.briefs, `${date}.md`);
    atomicText(path, content);
    atomicText(join(this.stateDir, "LATEST_BRIEF.md"), content);
    const state = this.readState();
    if (!state.briefs.some((item) => item.date === date)) {
      state.briefs.push({ date, path, createdAt: this.clock().toISOString() });
      this.writeState(state);
    }
    return { date, path, content, proposed: proposed.length, confirmed: confirmed.length };
  }

  claimBriefNotification(date = localDay(this.clock())) {
    const key = `brief:${date}`;
    const state = this.readState();
    if (state.notified[key]) return { claimed: false, key, notifiedAt: state.notified[key] };
    const brief = this.dailyBrief(date);
    const now = this.clock();
    const [hour, minute] = this.config.notifications.dailyBriefAt.split(":").map(Number);
    const dueAt = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
    if (now.getTime() < dueAt.getTime()) {
      return { claimed: false, key, reason: "before-daily-brief-time", dueAt: dueAt.toISOString() };
    }
    state.notified[key] = now.toISOString();
    this.writeState(state);
    return {
      claimed: true,
      key,
      title: `AIONE — brief du ${date}`,
      body: `${brief.proposed} rendez-vous à valider. Ouvrir le brief pour les instructions.`,
      path: brief.path
    };
  }

  claimDueReminders() {
    const now = this.clock();
    const state = this.readState();
    const reminders = [];
    for (const meeting of this.meetings().filter((entry) => entry.status === "CONFIRMED")) {
      const startsAt = localDateTime(meeting.date, meeting.start);
      for (const leadMinutes of this.config.notifications.reminderLeadMinutes || []) {
        const dueAt = new Date(startsAt.getTime() - Number(leadMinutes) * 60000);
        const ageMs = now.getTime() - dueAt.getTime();
        const key = `${meeting.id}:${leadMinutes}`;
        if (ageMs >= 0 && ageMs <= 5 * 60000 && !state.notified[key]) {
          const studio = this.config.studios.find((entry) => entry.id === meeting.studio);
          reminders.push({
            key,
            meetingId: meeting.id,
            title: `AIONE — rendez-vous dans ${leadMinutes} min`,
            body: `${studio?.name || meeting.studio} à ${meeting.start}`,
            dueAt: dueAt.toISOString()
          });
          state.notified[key] = now.toISOString();
        }
      }
    }
    const today = localDay(now);
    const dayCode = weekdayCode(now);
    for (const routine of (this.config.routines || []).filter((entry) =>
      entry.status === "ACTIVE" && entry.days.includes(dayCode)
    )) {
      const dueAt = localDateTime(today, routine.time);
      const ageMs = now.getTime() - dueAt.getTime();
      const key = `${routine.id}:${today}`;
      if (ageMs >= 0 && ageMs <= 5 * 60000 && !state.notified[key]) {
        reminders.push({
          key,
          routineId: routine.id,
          title: `AIONE — ${routine.title}`,
          body: routine.body,
          dueAt: dueAt.toISOString()
        });
        state.notified[key] = now.toISOString();
      }
    }
    if (reminders.length) this.writeState(state);
    return reminders;
  }
}

export function createDigitalLifeRuntime(options = {}) {
  return new DigitalLifeRuntime(options);
}
