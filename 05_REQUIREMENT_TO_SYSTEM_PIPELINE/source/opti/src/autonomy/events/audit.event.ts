import type {
  AuditEvent,
  Lot,
  LotState,
} from "../models/lot.model.js";

export interface AuditEventInput {
  event_type: string;
  agent_id?: string | null | undefined;
  previous_state?: LotState | null | undefined;
  new_state?: LotState | null | undefined;
  reason?: string | undefined;
  correlation_id?: string | undefined;
  created_at?: string | undefined;
  event_id?: string | undefined;
  details?: Record<string, unknown> | undefined;
}

function createIdentifier(prefix: string): string {
  const timestamp = Date.now();
  const randomPart = Math.random().toString(36).slice(2, 12);

  return `${prefix}-${timestamp}-${randomPart}`;
}

export function createAuditEvent(
  lot: Pick<Lot, "lot_id" | "task_id">,
  input: AuditEventInput,
): AuditEvent {
  return {
    event_id: input.event_id ?? createIdentifier("evt"),
    event_type: input.event_type,
    task_id: lot.task_id,
    lot_id: lot.lot_id,
    agent_id: input.agent_id ?? null,
    previous_state: input.previous_state ?? null,
    new_state: input.new_state ?? null,
    reason: input.reason ?? "",
    correlation_id:
      input.correlation_id ?? createIdentifier("corr"),
    created_at:
      input.created_at ?? new Date().toISOString(),
    details: input.details,
  };
}

export function appendAuditEvent(
  lot: Lot,
  input: AuditEventInput,
): AuditEvent {
  const event = createAuditEvent(lot, input);

  lot.audit.events.push(event);
  lot.audit.updated_at = event.created_at;

  return event;
}

export function getAuditEvents(
  lot: Lot,
): readonly AuditEvent[] {
  return [...lot.audit.events];
}

export function getAuditEventsByType(
  lot: Lot,
  eventType: string,
): AuditEvent[] {
  return lot.audit.events.filter(
    (event: AuditEvent) =>
      event.event_type === eventType,
  );
}

export function getLatestAuditEvent(
  lot: Lot,
): AuditEvent | undefined {
  if (lot.audit.events.length === 0) {
    return undefined;
  }

  return lot.audit.events[lot.audit.events.length - 1];
}
