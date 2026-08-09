import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import type { AutonomyEvent } from "./types.js";

const SECRET_VALUE = /(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*([^\s,;]+)/gi;

function redact(value: unknown): unknown {
  if (typeof value === "string") {
    return value.replace(SECRET_VALUE, "$1=[REDACTED]");
  }
  if (Array.isArray(value)) {
    return value.map(redact);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => {
        if (/(token|password|secret|authorization|api[_-]?key)/i.test(key) && typeof item === "string") {
          return [key, "[REDACTED]"];
        }
        return [key, redact(item)];
      }),
    );
  }
  return value;
}

export class EventLogger {
  constructor(private readonly filePath: string) {
    mkdirSync(dirname(filePath), { recursive: true });
  }

  log(type: string, data: Record<string, unknown> = {}, options: { taskId?: string | undefined; level?: AutonomyEvent["level"] | undefined } = {}): AutonomyEvent {
    const event: AutonomyEvent = {
      id: randomUUID(),
      timestamp: new Date().toISOString(),
      type,
      level: options.level ?? "info",
      ...(options.taskId ? { task_id: options.taskId } : {}),
      data: redact(data) as Record<string, unknown>,
    };
    appendFileSync(this.filePath, `${JSON.stringify(event)}\n`, "utf8");
    return event;
  }
}
