import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import type {
  Atom, AtomizationReport, Claim, CognitiveExecution, CognitiveReceipt, CognitiveRelation,
  CoherenceDiagnostic, ContextSelection, Tile, TraceableAnswer,
} from "./types.js";

interface JsonRow { data_json: string }

export class CognitiveStore {
  private readonly db: DatabaseSync;
  readonly receiptDirectory: string;

  constructor(readonly databasePath: string) {
    mkdirSync(dirname(databasePath), { recursive: true });
    this.receiptDirectory = join(dirname(databasePath), "cognitive-receipts");
    mkdirSync(this.receiptDirectory, { recursive: true });
    this.db = new DatabaseSync(databasePath);
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA synchronous = FULL;
      PRAGMA foreign_keys = ON;
      PRAGMA busy_timeout = 200;
      CREATE TABLE IF NOT EXISTS cog_sources (
        source_id TEXT PRIMARY KEY, source_path TEXT NOT NULL UNIQUE, content_hash TEXT NOT NULL,
        parser_version TEXT NOT NULL, imported_at TEXT NOT NULL, valid INTEGER NOT NULL, execution_id TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS cog_atoms (
        atom_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
        content_hash TEXT NOT NULL, valid INTEGER NOT NULL, data_json TEXT NOT NULL,
        FOREIGN KEY(source_id) REFERENCES cog_sources(source_id)
      );
      CREATE INDEX IF NOT EXISTS cog_atoms_source_valid ON cog_atoms(source_id, valid, start_line);
      CREATE TABLE IF NOT EXISTS cog_tiles (
        tile_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, subject TEXT NOT NULL, data_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS cog_tiles_source_subject ON cog_tiles(source_id, subject);
      CREATE TABLE IF NOT EXISTS cog_claims (
        claim_id TEXT PRIMARY KEY, tile_id TEXT NOT NULL, data_json TEXT NOT NULL,
        FOREIGN KEY(tile_id) REFERENCES cog_tiles(tile_id) ON DELETE CASCADE
      );
      CREATE TABLE IF NOT EXISTS cog_relations (
        relation_id TEXT PRIMARY KEY, relation_type TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL, data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS cog_selections (selection_id TEXT PRIMARY KEY, data_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS cog_diagnostics (diagnostic_id TEXT PRIMARY KEY, data_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS cog_answers (answer_id TEXT PRIMARY KEY, data_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS cog_executions (
        execution_id TEXT PRIMARY KEY, stage TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS cog_receipts (
        receipt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, execution_id TEXT NOT NULL, data_json TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS cog_model_runs (
        model_run_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, model TEXT NOT NULL, prompt_hash TEXT NOT NULL,
        created_at TEXT NOT NULL, valid INTEGER NOT NULL, data_json TEXT NOT NULL
      );
    `);
  }

  close(): void { this.db.close(); }

  source(sourceId: string): { source_id: string; source_path: string; content_hash: string; parser_version: string; imported_at: string; valid: number; execution_id: string } | null {
    return (this.db.prepare("SELECT * FROM cog_sources WHERE source_id = ?").get(sourceId) as ReturnType<CognitiveStore["source"]>) ?? null;
  }

  ingest(sourceId: string, sourcePath: string, atoms: Atom[], report: AtomizationReport): { atoms: Atom[]; report: AtomizationReport } {
    const existing = this.source(sourceId);
    if (existing?.content_hash === report.source_hash && existing.parser_version === report.parser_version) {
      return { atoms: this.atoms(sourceId), report: { ...report, idempotent: true } };
    }
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare(`
        INSERT INTO cog_sources(source_id, source_path, content_hash, parser_version, imported_at, valid, execution_id)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(source_id) DO UPDATE SET source_path=excluded.source_path, content_hash=excluded.content_hash,
          parser_version=excluded.parser_version, imported_at=excluded.imported_at, valid=1, execution_id=excluded.execution_id
      `).run(sourceId, sourcePath, report.source_hash, report.parser_version, new Date().toISOString(), report.execution_id);
      this.db.prepare("UPDATE cog_atoms SET valid = 0 WHERE source_id = ?").run(sourceId);
      const upsert = this.db.prepare(`
        INSERT INTO cog_atoms(atom_id, source_id, start_line, end_line, content_hash, valid, data_json)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(atom_id) DO UPDATE SET start_line=excluded.start_line, end_line=excluded.end_line,
          content_hash=excluded.content_hash, valid=1, data_json=excluded.data_json
      `);
      for (const atom of atoms) {
        upsert.run(atom.atom_id, sourceId, atom.source_position.start_line, atom.source_position.end_line, atom.content_hash, JSON.stringify(atom));
      }
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return { atoms: this.atoms(sourceId), report };
  }

  atoms(sourceId?: string): Atom[] {
    const rows = sourceId
      ? this.db.prepare("SELECT data_json FROM cog_atoms WHERE source_id = ? AND valid = 1 ORDER BY start_line, atom_id").all(sourceId)
      : this.db.prepare("SELECT data_json FROM cog_atoms WHERE valid = 1 ORDER BY source_id, start_line, atom_id").all();
    return (rows as unknown as JsonRow[]).map((row) => JSON.parse(row.data_json) as Atom);
  }

  saveTiles(sourceId: string, tiles: Tile[]): void {
    for (const tile of tiles) {
      if (tile.source_id !== sourceId || tile.atom_ids.length === 0) throw new Error(`Tile ${tile.tile_id} has invalid source or no provenance.`);
      if (!tile.provenance || tile.provenance.source_ids.length === 0 || tile.provenance.atom_ids.length === 0) {
        throw new Error(`Tile ${tile.tile_id} has no provenance.`);
      }
      for (const atomId of tile.atom_ids) {
        const found = this.db.prepare("SELECT 1 AS ok FROM cog_atoms WHERE atom_id = ? AND valid = 1").get(atomId);
        if (!found) throw new Error(`Tile ${tile.tile_id} references orphan atom ${atomId}.`);
      }
    }
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const previous = this.db.prepare("SELECT tile_id FROM cog_tiles WHERE source_id = ?").all(sourceId) as unknown as Array<{ tile_id: string }>;
      for (const entry of previous) this.db.prepare("DELETE FROM cog_claims WHERE tile_id = ?").run(entry.tile_id);
      this.db.prepare("DELETE FROM cog_tiles WHERE source_id = ?").run(sourceId);
      const insertTile = this.db.prepare("INSERT INTO cog_tiles(tile_id, source_id, subject, data_json) VALUES (?, ?, ?, ?)");
      const insertClaim = this.db.prepare("INSERT INTO cog_claims(claim_id, tile_id, data_json) VALUES (?, ?, ?)");
      for (const tile of tiles) {
        insertTile.run(tile.tile_id, tile.source_id, tile.subject, JSON.stringify(tile));
        for (const claim of tile.claims) insertClaim.run(claim.claim_id, tile.tile_id, JSON.stringify(claim));
      }
      this.db.exec("COMMIT");
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }

  tiles(sourceId?: string): Tile[] {
    const rows = sourceId
      ? this.db.prepare("SELECT data_json FROM cog_tiles WHERE source_id = ? ORDER BY subject, tile_id").all(sourceId)
      : this.db.prepare("SELECT data_json FROM cog_tiles ORDER BY source_id, subject, tile_id").all();
    return (rows as unknown as JsonRow[]).map((row) => JSON.parse(row.data_json) as Tile);
  }

  claims(tileIds?: string[]): Claim[] {
    if (!tileIds || tileIds.length === 0) {
      return (this.db.prepare("SELECT data_json FROM cog_claims ORDER BY claim_id").all() as unknown as JsonRow[]).map((row) => JSON.parse(row.data_json) as Claim);
    }
    const rows: Claim[] = [];
    const query = this.db.prepare("SELECT data_json FROM cog_claims WHERE tile_id = ? ORDER BY claim_id");
    for (const id of tileIds) rows.push(...(query.all(id) as unknown as JsonRow[]).map((row) => JSON.parse(row.data_json) as Claim));
    return rows;
  }

  saveRelations(relations: CognitiveRelation[]): void {
    this.rejectForbiddenCycles(relations);
    const upsert = this.db.prepare(`INSERT INTO cog_relations(relation_id, relation_type, from_id, to_id, data_json)
      VALUES (?, ?, ?, ?, ?) ON CONFLICT(relation_id) DO UPDATE SET data_json=excluded.data_json`);
    this.db.exec("BEGIN IMMEDIATE");
    try {
      for (const relation of relations) {
        if (!this.nodeExists(relation.from) || !this.nodeExists(relation.to)) {
          throw new Error(`Relation ${relation.relation_id} has an orphan endpoint: ${relation.from} -> ${relation.to}.`);
        }
        upsert.run(relation.relation_id, relation.relation_type, relation.from, relation.to, JSON.stringify(relation));
      }
      this.db.exec("COMMIT");
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }

  relations(): CognitiveRelation[] {
    return (this.db.prepare("SELECT data_json FROM cog_relations ORDER BY relation_id").all() as unknown as JsonRow[]).map((row) => JSON.parse(row.data_json) as CognitiveRelation);
  }

  saveExecution(value: CognitiveExecution): void {
    value.updated_at = new Date().toISOString();
    this.db.prepare(`INSERT INTO cog_executions(execution_id, stage, status, updated_at, data_json) VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(execution_id) DO UPDATE SET stage=excluded.stage,status=excluded.status,updated_at=excluded.updated_at,data_json=excluded.data_json`)
      .run(value.execution_id, value.stage, value.status, value.updated_at, JSON.stringify(value));
  }

  execution(id: string): CognitiveExecution | null {
    const row = this.db.prepare("SELECT data_json FROM cog_executions WHERE execution_id = ?").get(id) as JsonRow | undefined;
    return row ? JSON.parse(row.data_json) as CognitiveExecution : null;
  }

  saveSelection(value: ContextSelection): void { this.saveJson("cog_selections", "selection_id", value.selection_id, value); }
  selection(id: string): ContextSelection | null { return this.loadJson<ContextSelection>("cog_selections", "selection_id", id); }
  saveDiagnostic(value: CoherenceDiagnostic): void { this.saveJson("cog_diagnostics", "diagnostic_id", value.diagnostic_id, value); }
  diagnostic(id: string): CoherenceDiagnostic | null { return this.loadJson<CoherenceDiagnostic>("cog_diagnostics", "diagnostic_id", id); }
  saveAnswer(value: TraceableAnswer): void { this.saveJson("cog_answers", "answer_id", value.answer_id, value); }
  answer(id: string): TraceableAnswer | null { return this.loadJson<TraceableAnswer>("cog_answers", "answer_id", id); }

  saveReceipt(receipt: CognitiveReceipt): string {
    this.db.prepare(`INSERT INTO cog_receipts(receipt_id, task_id, execution_id, data_json) VALUES (?, ?, ?, ?)
      ON CONFLICT(receipt_id) DO UPDATE SET data_json=excluded.data_json`)
      .run(receipt.receipt_id, receipt.task_id, receipt.execution_id, JSON.stringify(receipt));
    const directory = join(this.receiptDirectory, receipt.execution_id);
    mkdirSync(directory, { recursive: true });
    const path = join(directory, `${receipt.task_id}.json`);
    writeFileSync(path, JSON.stringify(receipt, null, 2), "utf8");
    return path;
  }

  receipts(executionId: string): CognitiveReceipt[] {
    return (this.db.prepare("SELECT data_json FROM cog_receipts WHERE execution_id = ? ORDER BY task_id").all(executionId) as unknown as JsonRow[])
      .map((row) => JSON.parse(row.data_json) as CognitiveReceipt);
  }

  saveModelRun(value: {
    model_run_id: string; execution_id: string; model: string; prompt_hash: string; created_at: string;
    valid: boolean; parameters: Record<string, unknown>; atom_ids: string[]; raw_output: string;
    validated_output: unknown; errors: string[];
  }): void {
    this.db.prepare(`INSERT INTO cog_model_runs(model_run_id, execution_id, model, prompt_hash, created_at, valid, data_json)
      VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(model_run_id) DO UPDATE SET valid=excluded.valid,data_json=excluded.data_json`)
      .run(value.model_run_id, value.execution_id, value.model, value.prompt_hash, value.created_at, value.valid ? 1 : 0, JSON.stringify(value));
  }

  modelRuns(executionId: string): Array<Record<string, unknown>> {
    return (this.db.prepare("SELECT data_json FROM cog_model_runs WHERE execution_id = ? ORDER BY created_at").all(executionId) as unknown as JsonRow[])
      .map((row) => JSON.parse(row.data_json) as Record<string, unknown>);
  }

  counts(): Record<string, number> {
    const tables = ["cog_sources", "cog_atoms", "cog_tiles", "cog_claims", "cog_relations", "cog_selections", "cog_diagnostics", "cog_answers", "cog_executions", "cog_receipts", "cog_model_runs"];
    return Object.fromEntries(tables.map((table) => [table, Number((this.db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get() as { count: number }).count)]));
  }

  private saveJson(table: string, key: string, id: string, value: unknown): void {
    this.db.prepare(`INSERT INTO ${table}(${key}, data_json) VALUES (?, ?) ON CONFLICT(${key}) DO UPDATE SET data_json=excluded.data_json`).run(id, JSON.stringify(value));
  }

  private loadJson<T>(table: string, key: string, id: string): T | null {
    const row = this.db.prepare(`SELECT data_json FROM ${table} WHERE ${key} = ?`).get(id) as JsonRow | undefined;
    return row ? JSON.parse(row.data_json) as T : null;
  }

  private nodeExists(id: string): boolean {
    if (/^SRC-/.test(id)) return Boolean(this.db.prepare("SELECT 1 AS ok FROM cog_sources WHERE source_id = ?").get(id));
    const mapping: Array<[RegExp, string, string]> = [
      [/^ATM-/, "cog_atoms", "atom_id"], [/^TILE-/, "cog_tiles", "tile_id"], [/^CLM-/, "cog_claims", "claim_id"],
      [/^COG-EXE-/, "cog_executions", "execution_id"], [/^SEL-/, "cog_selections", "selection_id"],
      [/^DIA-/, "cog_diagnostics", "diagnostic_id"], [/^ANS-/, "cog_answers", "answer_id"],
    ];
    const entry = mapping.find(([pattern]) => pattern.test(id));
    return entry ? Boolean(this.db.prepare(`SELECT 1 AS ok FROM ${entry[1]} WHERE ${entry[2]} = ?`).get(id)) : false;
  }

  private rejectForbiddenCycles(incoming: CognitiveRelation[]): void {
    const relevant = [...this.relations(), ...incoming].filter((relation) => relation.relation_type === "depends_on" || relation.relation_type === "implies");
    const graph = new Map<string, string[]>();
    for (const relation of relevant) graph.set(relation.from, [...(graph.get(relation.from) ?? []), relation.to]);
    const visiting = new Set<string>(); const visited = new Set<string>();
    const visit = (node: string): void => {
      if (visiting.has(node)) throw new Error(`Unauthorized circular cognitive relation detected at ${node}.`);
      if (visited.has(node)) return;
      visiting.add(node); for (const next of graph.get(node) ?? []) visit(next); visiting.delete(node); visited.add(node);
    };
    for (const node of graph.keys()) visit(node);
  }
}
