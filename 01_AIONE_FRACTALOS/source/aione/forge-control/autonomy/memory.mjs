import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync
} from "node:fs";
import { join } from "node:path";
import { createHash, randomUUID } from "node:crypto";

function ensureDirectory(path) {
  mkdirSync(path, { recursive: true });
  return path;
}

function atomicJson(path, value) {
  ensureDirectory(path.slice(0, Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"))));
  const temporary = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  renameSync(temporary, path);
}

function readJson(path, fallback) {
  if (!existsSync(path)) return fallback;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function listJson(path) {
  if (!existsSync(path)) return [];
  return readdirSync(path)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => readJson(join(path, name), null))
    .filter(Boolean);
}

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function itemId(prefix, time = new Date()) {
  return `${prefix}-${time.toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}-${randomUUID().slice(0, 8)}`;
}

export class FractalMemory {
  constructor({ rootDir, clock = () => new Date() }) {
    this.rootDir = rootDir;
    this.clock = clock;
    this.paths = {
      atoms: ensureDirectory(join(rootDir, "atoms")),
      tiles: ensureDirectory(join(rootDir, "tiles")),
      kiloTiles: ensureDirectory(join(rootDir, "kilo-tiles")),
      megaTiles: ensureDirectory(join(rootDir, "mega-tiles")),
      gigaTiles: ensureDirectory(join(rootDir, "giga-tiles")),
      quarantine: ensureDirectory(join(rootDir, "quarantine")),
      index: join(rootDir, "index.json")
    };
    this.ensureIndex();
  }

  ensureIndex() {
    if (!existsSync(this.paths.index)) {
      atomicJson(this.paths.index, {
        schema: "aione.memory-index.v1",
        updatedAt: this.clock().toISOString(),
        atoms: [],
        tiles: [],
        kiloTiles: [],
        megaTiles: [],
        gigaTiles: []
      });
    }
  }

  readIndex() {
    const index = readJson(this.paths.index, {
      schema: "aione.memory-index.v1",
      updatedAt: this.clock().toISOString(),
      atoms: [],
      tiles: [],
      kiloTiles: [],
      megaTiles: [],
      gigaTiles: []
    });
    for (const key of ["atoms", "tiles", "kiloTiles", "megaTiles", "gigaTiles"]) {
      if (!Array.isArray(index[key])) index[key] = [];
    }
    return index;
  }

  writeIndex(index) {
    index.updatedAt = this.clock().toISOString();
    atomicJson(this.paths.index, index);
  }

  captureAtom(type, payload = {}, metadata = {}) {
    const createdAt = this.clock().toISOString();
    const atom = {
      schema: "aione.memory-atom.v1",
      id: itemId("atom", this.clock()),
      type,
      createdAt,
      payload,
      metadata,
      checksum: ""
    };
    atom.checksum = digest({ ...atom, checksum: "" });
    atomicJson(join(this.paths.atoms, `${atom.id}.json`), atom);
    const index = this.readIndex();
    index.atoms.push({ id: atom.id, type, createdAt, compacted: false, checksum: atom.checksum });
    this.writeIndex(index);
    return atom;
  }

  compact({ atomsPerTile = 16, tilesPerKilo = 16, kilosPerMega = 16, megasPerGiga = 16 } = {}) {
    const index = this.readIndex();
    const created = { tiles: [], kiloTiles: [], megaTiles: [], gigaTiles: [] };

    const pendingAtoms = index.atoms.filter((entry) => !entry.compacted).slice(0, atomsPerTile);
    if (pendingAtoms.length > 0) {
      const atomMap = new Map(listJson(this.paths.atoms).map((item) => [item.id, item]));
      const atoms = pendingAtoms.map((entry) => atomMap.get(entry.id)).filter(Boolean);
      if (atoms.length > 0) {
        const tile = this.createAggregate("tile", "aione.memory-tile.v1", atoms);
        atomicJson(join(this.paths.tiles, `${tile.id}.json`), tile);
        index.tiles.push({ id: tile.id, createdAt: tile.createdAt, compacted: false, checksum: tile.checksum });
        for (const entry of pendingAtoms) entry.compacted = true;
        created.tiles.push(tile);
      }
    }

    const pendingTiles = index.tiles.filter((entry) => !entry.compacted).slice(0, tilesPerKilo);
    if (pendingTiles.length >= tilesPerKilo) {
      const tileMap = new Map(listJson(this.paths.tiles).map((item) => [item.id, item]));
      const tiles = pendingTiles.map((entry) => tileMap.get(entry.id)).filter(Boolean);
      const kilo = this.createAggregate("kilo", "aione.memory-kilo-tile.v1", tiles);
      atomicJson(join(this.paths.kiloTiles, `${kilo.id}.json`), kilo);
      index.kiloTiles.push({ id: kilo.id, createdAt: kilo.createdAt, compacted: false, checksum: kilo.checksum });
      for (const entry of pendingTiles) entry.compacted = true;
      created.kiloTiles.push(kilo);
    }

    const pendingKilos = index.kiloTiles.filter((entry) => !entry.compacted).slice(0, kilosPerMega);
    if (pendingKilos.length >= kilosPerMega) {
      const kiloMap = new Map(listJson(this.paths.kiloTiles).map((item) => [item.id, item]));
      const kilos = pendingKilos.map((entry) => kiloMap.get(entry.id)).filter(Boolean);
      const mega = this.createAggregate("mega", "aione.memory-mega-tile.v1", kilos);
      atomicJson(join(this.paths.megaTiles, `${mega.id}.json`), mega);
      index.megaTiles.push({ id: mega.id, createdAt: mega.createdAt, compacted: false, checksum: mega.checksum });
      for (const entry of pendingKilos) entry.compacted = true;
      created.megaTiles.push(mega);
    }

    const pendingMegas = index.megaTiles.filter((entry) => !entry.compacted).slice(0, megasPerGiga);
    if (pendingMegas.length >= megasPerGiga) {
      const megaMap = new Map(listJson(this.paths.megaTiles).map((item) => [item.id, item]));
      const megas = pendingMegas.map((entry) => megaMap.get(entry.id)).filter(Boolean);
      const giga = this.createAggregate("giga", "aione.memory-giga-tile.v1", megas);
      atomicJson(join(this.paths.gigaTiles, `${giga.id}.json`), giga);
      index.gigaTiles.push({ id: giga.id, createdAt: giga.createdAt, checksum: giga.checksum });
      for (const entry of pendingMegas) entry.compacted = true;
      created.gigaTiles.push(giga);
    }

    this.writeIndex(index);
    return { created, index };
  }

  createAggregate(prefix, schema, items) {
    const createdAt = this.clock().toISOString();
    const aggregate = {
      schema,
      id: itemId(prefix, this.clock()),
      createdAt,
      sourceIds: items.map((item) => item.id),
      count: items.length,
      summary: items.map((item) => item.type || item.summary || item.id).slice(0, 32),
      checksum: ""
    };
    aggregate.checksum = digest({ ...aggregate, checksum: "" });
    return aggregate;
  }

  audit() {
    const index = this.readIndex();
    const issues = [];
    const collections = [
      ["atoms", this.paths.atoms],
      ["tiles", this.paths.tiles],
      ["kiloTiles", this.paths.kiloTiles],
      ["megaTiles", this.paths.megaTiles],
      ["gigaTiles", this.paths.gigaTiles]
    ];
    for (const [key, path] of collections) {
      const files = new Map(listJson(path).map((item) => [item.id, item]));
      for (const entry of index[key] || []) {
        const item = files.get(entry.id);
        if (!item) {
          issues.push({ code: "missing-memory-item", level: key, id: entry.id });
          continue;
        }
        const expected = digest({ ...item, checksum: "" });
        if (expected !== item.checksum) issues.push({ code: "invalid-memory-checksum", level: key, id: entry.id });
      }
    }
    return {
      ok: issues.length === 0,
      issues,
      counts: {
        atoms: index.atoms.length,
        tiles: index.tiles.length,
        kiloTiles: index.kiloTiles.length,
        megaTiles: index.megaTiles.length,
        gigaTiles: index.gigaTiles.length
      }
    };
  }
}

export { atomicJson, readJson };
