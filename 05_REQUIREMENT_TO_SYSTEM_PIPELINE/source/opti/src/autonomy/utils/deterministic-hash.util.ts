import { createHash } from "crypto";

import type { Lot } from "../models/lot.model.js";

type CanonicalValue =
  | null
  | boolean
  | number
  | string
  | CanonicalValue[]
  | { [key: string]: CanonicalValue };

function normalizeValue(
  value: unknown,
  ancestors: WeakSet<object>,
): CanonicalValue {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "string"
  ) {
    return value;
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError(
        "Canonical JSON does not support NaN or infinite numbers.",
      );
    }

    return Object.is(value, -0) ? 0 : value;
  }

  if (typeof value === "undefined") {
    throw new TypeError(
      "Canonical JSON does not support undefined values.",
    );
  }

  if (typeof value === "bigint") {
    throw new TypeError(
      "Canonical JSON does not support bigint values.",
    );
  }

  if (
    typeof value === "function" ||
    typeof value === "symbol"
  ) {
    throw new TypeError(
      `Canonical JSON does not support ${typeof value} values.`,
    );
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (typeof value !== "object") {
    throw new TypeError("Unsupported canonical value.");
  }

  if (ancestors.has(value)) {
    throw new TypeError(
      "Cannot canonicalize a value containing circular references.",
    );
  }

  ancestors.add(value);

  try {
    if (Array.isArray(value)) {
      return value.map((item: unknown) =>
        normalizeValue(item, ancestors),
      );
    }

    const prototype = Object.getPrototypeOf(value);

    if (
      prototype !== Object.prototype &&
      prototype !== null
    ) {
      throw new TypeError(
        "Canonical JSON only supports plain objects.",
      );
    }

    const source = value as Record<string, unknown>;
    const normalized: Record<string, CanonicalValue> = {};

    for (const key of Object.keys(source).sort()) {
      normalized[key] = normalizeValue(
        source[key],
        ancestors,
      );
    }

    return normalized;
  } finally {
    ancestors.delete(value);
  }
}

export function canonicalize(value: unknown): string {
  return JSON.stringify(
    normalizeValue(value, new WeakSet<object>()),
  );
}

export function deterministicHash(value: unknown): string {
  return createHash("sha256")
    .update(canonicalize(value), "utf8")
    .digest("hex");
}

/**
 * Returns only the fields whose modification must invalidate
 * a previous approval.
 *
 * Runtime state, approval metadata, audit events and technical
 * timestamps are intentionally excluded.
 */
export function getApprovableLotPayload(
  lot: Lot,
): Record<string, unknown> {
  return {
    schema_version: lot.schema_version,
    lot_id: lot.lot_id,
    task_id: lot.task_id,
    title: lot.title,
    description: lot.description,
    scope: lot.scope,
    dependencies: lot.dependencies,
    requested_capabilities:
      lot.requested_capabilities,
    artifacts: lot.artifacts,
    verification: lot.verification,
    risk: lot.risk,
    rollback: lot.rollback,
    required_approval_level:
      lot.approval.required_level,
  };
}

export function calculateLotArtifactHash(
  lot: Lot,
): string {
  return deterministicHash(
    getApprovableLotPayload(lot),
  );
}
