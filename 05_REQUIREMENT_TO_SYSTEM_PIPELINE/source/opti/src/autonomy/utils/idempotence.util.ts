import {
  canonicalize,
  deterministicHash,
} from "./deterministic-hash.util.js";

export interface IdempotencyCommand {
  lot_id: string;
  approved_hash: string;
  command_type: string;
  command_payload: unknown;
}

export interface IdempotencyRecord {
  command_id: string;
  lot_id: string;
  approved_hash: string;
  command_type: string;
  command_payload_hash: string;
  marked_at: string;
}

export interface IdempotencyStore {
  has(commandId: string): boolean;

  get(
    commandId: string,
  ): IdempotencyRecord | undefined;

  mark(record: IdempotencyRecord): boolean;

  clear(): void;
}

export function createCommandId(
  command: IdempotencyCommand,
): string {
  return deterministicHash({
    lot_id: command.lot_id,
    approved_hash: command.approved_hash,
    command_type: command.command_type,
    command_payload: command.command_payload,
  });
}

export function createIdempotencyRecord(
  command: IdempotencyCommand,
  markedAt = new Date().toISOString(),
): IdempotencyRecord {
  return {
    command_id: createCommandId(command),
    lot_id: command.lot_id,
    approved_hash: command.approved_hash,
    command_type: command.command_type,
    command_payload_hash: deterministicHash(
      command.command_payload,
    ),
    marked_at: markedAt,
  };
}

function cloneRecord(
  record: IdempotencyRecord,
): IdempotencyRecord {
  return {
    ...record,
  };
}

export class MemoryIdempotencyStore
implements IdempotencyStore {
  private readonly records =
    new Map<string, IdempotencyRecord>();

  has(commandId: string): boolean {
    return this.records.has(commandId);
  }

  get(
    commandId: string,
  ): IdempotencyRecord | undefined {
    const record = this.records.get(commandId);

    return record
      ? cloneRecord(record)
      : undefined;
  }

  mark(record: IdempotencyRecord): boolean {
    if (this.records.has(record.command_id)) {
      return false;
    }

    this.records.set(
      record.command_id,
      cloneRecord(record),
    );

    return true;
  }

  clear(): void {
    this.records.clear();
  }

  get size(): number {
    return this.records.size;
  }
}

export function executeOnce<T>(
  store: IdempotencyStore,
  command: IdempotencyCommand,
  operation: () => T,
): {
  executed: boolean;
  command_id: string;
  result?: T;
} {
  const record =
    createIdempotencyRecord(command);

  if (store.has(record.command_id)) {
    return {
      executed: false,
      command_id: record.command_id,
    };
  }

  const result = operation();

  const marked = store.mark(record);

  if (!marked) {
    return {
      executed: false,
      command_id: record.command_id,
    };
  }

  return {
    executed: true,
    command_id: record.command_id,
    result,
  };
}

export function serializeIdempotencyRecord(
  record: IdempotencyRecord,
): string {
  return canonicalize(record);
}
