import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";

export type DirectionStatus = 'ACTIVE' | 'PAUSED' | 'SATISFIED' | 'CANCELLED' | 'EXPIRED';

export interface DirectionRow {
  id: string;
  description: string;
  priority: number;
  status: DirectionStatus;
  origin: string;
  constraints_json: string;
  satisfaction_criteria_json: string;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
  task_refs_json: string;
  capability_refs_json: string;
}

export interface DirectionRecord {
  id: string;
  description: string;
  priority: number;
  status: DirectionStatus;
  origin: string;
  constraints: Record<string, unknown>;
  satisfaction_criteria: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
  task_refs: string[];
  capability_refs: string[];
}

export class DirectionsRegistry {
  private readonly db: DatabaseSync;

  constructor(db: DatabaseSync) {
    this.db = db;
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA synchronous = FULL;
      CREATE TABLE IF NOT EXISTS directions (
        id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        priority INTEGER NOT NULL,
        status TEXT NOT NULL,
        origin TEXT NOT NULL,
        constraints_json TEXT NOT NULL,
        satisfaction_criteria_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT,
        task_refs_json TEXT NOT NULL,
        capability_refs_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS directions_status_priority ON directions(status, priority DESC);
      CREATE INDEX IF NOT EXISTS directions_expires_at ON directions(expires_at);
    `);
  }

  create(direction: Omit<DirectionRecord, 'id' | 'created_at' | 'updated_at'>): DirectionRecord {
    const id = randomUUID();
    const now = new Date().toISOString();
    
    this.db.prepare(`
      INSERT INTO directions(id, description, priority, status, origin, constraints_json, satisfaction_criteria_json, created_at, updated_at, expires_at, task_refs_json, capability_refs_json)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      direction.description,
      direction.priority,
      direction.status,
      direction.origin,
      JSON.stringify(direction.constraints),
      JSON.stringify(direction.satisfaction_criteria),
      now,
      now,
      direction.expires_at || null,
      JSON.stringify(direction.task_refs),
      JSON.stringify(direction.capability_refs)
    );

    return {
      id,
      description: direction.description,
      priority: direction.priority,
      status: direction.status,
      origin: direction.origin,
      constraints: direction.constraints,
      satisfaction_criteria: direction.satisfaction_criteria,
      created_at: now,
      updated_at: now,
      expires_at: direction.expires_at || null,
      task_refs: direction.task_refs,
      capability_refs: direction.capability_refs
    };
  }

  get(id: string): DirectionRecord | null {
    const row = this.db.prepare("SELECT * FROM directions WHERE id = ?").get(id) as unknown as DirectionRow | undefined;
    if (!row) return null;

    return {
      id: row.id,
      description: row.description,
      priority: row.priority,
      status: row.status,
      origin: row.origin,
      constraints: JSON.parse(row.constraints_json),
      satisfaction_criteria: JSON.parse(row.satisfaction_criteria_json),
      created_at: row.created_at,
      updated_at: row.updated_at,
      expires_at: row.expires_at ?? null,
      task_refs: JSON.parse(row.task_refs_json),
      capability_refs: JSON.parse(row.capability_refs_json)
    };
  }

  listActive(taskId?: string): DirectionRecord[] {
    // Update expired directions first
    this.checkAndExpire();
    
    if (taskId) {
      const query = "SELECT * FROM directions WHERE status = 'ACTIVE' AND task_refs_json LIKE ? ORDER BY priority DESC, created_at ASC, id ASC";
      const rows = this.db.prepare(query).all(`%${taskId}%`) as unknown as DirectionRow[];
      return rows.map(row => ({
        id: row.id,
        description: row.description,
        priority: row.priority,
        status: row.status,
        origin: row.origin,
        constraints: JSON.parse(row.constraints_json),
        satisfaction_criteria: JSON.parse(row.satisfaction_criteria_json),
        created_at: row.created_at,
        updated_at: row.updated_at,
        expires_at: row.expires_at ?? null,
        task_refs: JSON.parse(row.task_refs_json),
        capability_refs: JSON.parse(row.capability_refs_json)
      }));
    } else {
      const query = "SELECT * FROM directions WHERE status = 'ACTIVE' ORDER BY priority DESC, created_at ASC, id ASC";
      const rows = this.db.prepare(query).all() as unknown as DirectionRow[];
      return rows.map(row => ({
        id: row.id,
        description: row.description,
        priority: row.priority,
        status: row.status,
        origin: row.origin,
        constraints: JSON.parse(row.constraints_json),
        satisfaction_criteria: JSON.parse(row.satisfaction_criteria_json),
        created_at: row.created_at,
        updated_at: row.updated_at,
        expires_at: row.expires_at ?? null,
        task_refs: JSON.parse(row.task_refs_json),
        capability_refs: JSON.parse(row.capability_refs_json)
      }));
    }
  }

  updatePriority(id: string, priority: number): DirectionRecord | null {
    const direction = this.get(id);
    if (!direction) return null;

    const now = new Date().toISOString();
    this.db.prepare(`
      UPDATE directions SET priority = ?, updated_at = ? WHERE id = ?
    `).run(priority, now, id);

    return {
      ...direction,
      priority,
      updated_at: now
    };
  }

  pause(id: string): DirectionRecord | null {
    const direction = this.get(id);
    if (!direction) return null;

    const now = new Date().toISOString();
    this.db.prepare(`
      UPDATE directions SET status = 'PAUSED', updated_at = ? WHERE id = ?
    `).run(now, id);

    return {
      ...direction,
      status: 'PAUSED',
      updated_at: now
    };
  }

  cancel(id: string): DirectionRecord | null {
    const direction = this.get(id);
    if (!direction) return null;

    const now = new Date().toISOString();
    this.db.prepare(`
      UPDATE directions SET status = 'CANCELLED', updated_at = ? WHERE id = ?
    `).run(now, id);

    return {
      ...direction,
      status: 'CANCELLED',
      updated_at: now
    };
  }

  // Handle expiration by checking and updating expired directions
  checkAndExpire(): DirectionRecord[] {
    const now = new Date().toISOString();
    const rows = this.db.prepare(`
      SELECT * FROM directions 
      WHERE expires_at IS NOT NULL AND expires_at < ? AND status != 'CANCELLED' AND status != 'EXPIRED'
    `).all(now) as unknown as DirectionRow[];
    
    const expired: DirectionRecord[] = [];
    
    for (const row of rows) {
      this.db.prepare(`
        UPDATE directions SET status = 'EXPIRED', updated_at = ? WHERE id = ?
      `).run(now, row.id);
      
      expired.push({
        id: row.id,
        description: row.description,
        priority: row.priority,
        status: 'EXPIRED',
        origin: row.origin,
        constraints: JSON.parse(row.constraints_json),
        satisfaction_criteria: JSON.parse(row.satisfaction_criteria_json),
        created_at: row.created_at,
        updated_at: now,
        expires_at: row.expires_at ?? null,
        task_refs: JSON.parse(row.task_refs_json),
        capability_refs: JSON.parse(row.capability_refs_json)
      });
    }
    
    return expired;
  }

  isDirectionUsable(id: string): boolean {
    const direction = this.get(id);
    if (!direction) return false;
    
    // CANCELLED and EXPIRED are unusable
    return direction.status !== 'CANCELLED' && direction.status !== 'EXPIRED';
  }
}