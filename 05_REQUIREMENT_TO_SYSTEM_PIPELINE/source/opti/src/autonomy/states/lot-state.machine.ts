import {
  LOT_STATES,
  type Lot,
  type LotState,
} from "../models/lot.model.js";

import { appendAuditEvent } from "../events/audit.event.js";

import {
  calculateLotArtifactHash,
} from "../utils/deterministic-hash.util.js";

export const LOT_TRANSITIONS: Readonly<
  Record<LotState, readonly LotState[]>
> = {
  DRAFT: [
    "DESIGNED",
    "REJECTED",
  ],
  DESIGNED: [
    "WORKING_ISOLATED",
    "QUARANTINED",
    "BLOCKED",
    "REJECTED",
  ],
  WORKING_ISOLATED: [
    "TESTING",
    "QUARANTINED",
    "BLOCKED",
    "FAILED",
  ],
  TESTING: [
    "QUARANTINED",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "FAILED",
  ],
  QUARANTINED: [
    "TESTING",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "REJECTED",
  ],
  AWAITING_APPROVAL: [
    "APPROVED",
    "QUARANTINED",
    "REJECTED",
  ],
  APPROVED: [
    "EXECUTING",
    "QUARANTINED",
    "BLOCKED",
    "REJECTED",
  ],
  EXECUTING: [
    "VERIFYING",
    "FAILED",
    "BLOCKED",
    "ROLLING_BACK",
  ],
  VERIFYING: [
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "ROLLING_BACK",
  ],
  COMPLETED: [],
  REJECTED: [
    "DRAFT",
    "DEAD_LETTER",
  ],
  BLOCKED: [
    "WORKING_ISOLATED",
    "TESTING",
    "QUARANTINED",
    "FAILED",
    "REJECTED",
  ],
  FAILED: [
    "ROLLING_BACK",
    "QUARANTINED",
    "DEAD_LETTER",
  ],
  ROLLING_BACK: [
    "ROLLED_BACK",
    "FAILED",
    "DEAD_LETTER",
  ],
  ROLLED_BACK: [
    "DRAFT",
    "DESIGNED",
    "QUARANTINED",
  ],
  DEAD_LETTER: [],
};

export class TransitionError extends Error {
  readonly code = "INVALID_LOT_TRANSITION";

  constructor(
    readonly lotId: string,
    readonly currentState: LotState,
    readonly requestedState: LotState,
  ) {
    super(
      `Lot ${lotId} cannot transition from ` +
      `${currentState} to ${requestedState}.`,
    );

    this.name = "TransitionError";
  }
}

export class ApprovalError extends Error {
  constructor(
    readonly code:
      | "INVALID_APPROVAL_STATE"
      | "APPROVAL_HASH_MISMATCH"
      | "APPROVAL_EXPIRED"
      | "CAPABILITY_NOT_REQUESTED",
    message: string,
  ) {
    super(message);
    this.name = "ApprovalError";
  }
}

export interface TransitionOptions {
  agent_id?: string | null | undefined;
  reason?: string | undefined;
  correlation_id?: string | undefined;
}

export interface ApprovalInput {
  approved_hash: string;
  approved_by: string;
  expires_at: string;
  allowed_capabilities: string[];
  agent_id?: string | null | undefined;
  correlation_id?: string | undefined;
}

export function isLotState(
  value: string,
): value is LotState {
  return (
    LOT_STATES as readonly string[]
  ).includes(value);
}

export function canTransition(
  currentState: LotState,
  nextState: LotState,
): boolean {
  const allowedTransitions =
    LOT_TRANSITIONS[currentState];

  return (
    allowedTransitions?.includes(nextState) ??
    false
  );
}

export function transitionLot(
  lot: Lot,
  nextState: LotState,
  options: TransitionOptions = {},
): Lot {
  const previousState = lot.status;

  if (!canTransition(previousState, nextState)) {
    appendAuditEvent(lot, {
      event_type: "STATE_TRANSITION_REJECTED",
      agent_id: options.agent_id ?? null,
      previous_state: previousState,
      new_state: nextState,
      reason:
        options.reason ??
        "The requested state transition is not allowed.",
      correlation_id: options.correlation_id,
      details: {
        error_code: "INVALID_LOT_TRANSITION",
      },
    });

    throw new TransitionError(
      lot.lot_id,
      previousState,
      nextState,
    );
  }

  lot.status = nextState;

  appendAuditEvent(lot, {
    event_type: "STATE_TRANSITION",
    agent_id: options.agent_id ?? null,
    previous_state: previousState,
    new_state: nextState,
    reason: options.reason ?? "",
    correlation_id: options.correlation_id,
  });

  return lot;
}

function rejectApproval(
  lot: Lot,
  error: ApprovalError,
  input: ApprovalInput,
): never {
  appendAuditEvent(lot, {
    event_type: "APPROVAL_REJECTED",
    agent_id: input.agent_id ?? null,
    previous_state: lot.status,
    new_state: lot.status,
    reason: error.message,
    correlation_id: input.correlation_id,
    details: {
      error_code: error.code,
    },
  });

  throw error;
}

export function approveLot(
  lot: Lot,
  input: ApprovalInput,
): Lot {
  if (lot.status !== "AWAITING_APPROVAL") {
    return rejectApproval(
      lot,
      new ApprovalError(
        "INVALID_APPROVAL_STATE",
        "A lot can only be approved from " +
        "AWAITING_APPROVAL.",
      ),
      input,
    );
  }

  const currentHash =
    calculateLotArtifactHash(lot);

  if (input.approved_hash !== currentHash) {
    return rejectApproval(
      lot,
      new ApprovalError(
        "APPROVAL_HASH_MISMATCH",
        "The approved hash does not match " +
        "the current lot content.",
      ),
      input,
    );
  }

  const expirationTime =
    Date.parse(input.expires_at);

  if (
    Number.isNaN(expirationTime) ||
    expirationTime <= Date.now()
  ) {
    return rejectApproval(
      lot,
      new ApprovalError(
        "APPROVAL_EXPIRED",
        "The approval expiration date is invalid " +
        "or already expired.",
      ),
      input,
    );
  }

  const unauthorizedCapabilities =
    input.allowed_capabilities.filter(
      (capability: string) =>
        !lot.requested_capabilities.includes(
          capability,
        ),
    );

  if (unauthorizedCapabilities.length > 0) {
    return rejectApproval(
      lot,
      new ApprovalError(
        "CAPABILITY_NOT_REQUESTED",
        "Approval contains capabilities that " +
        "were not requested by the lot.",
      ),
      input,
    );
  }

  const approvedAt = new Date().toISOString();

  lot.approval.artifact_hash = currentHash;
  lot.approval.approved_hash =
    input.approved_hash;
  lot.approval.approved_by =
    input.approved_by;
  lot.approval.approved_at = approvedAt;
  lot.approval.expires_at =
    input.expires_at;
  lot.approval.allowed_capabilities = [
    ...input.allowed_capabilities,
  ];
  lot.approval.valid = true;

  appendAuditEvent(lot, {
    event_type: "APPROVAL_GRANTED",
    agent_id: input.agent_id ?? null,
    previous_state: lot.status,
    new_state: "APPROVED",
    reason: "Lot approval granted.",
    correlation_id: input.correlation_id,
    details: {
      approved_by: input.approved_by,
      approved_hash: input.approved_hash,
      expires_at: input.expires_at,
      allowed_capabilities: [
        ...input.allowed_capabilities,
      ],
    },
  });

  return transitionLot(lot, "APPROVED", {
    agent_id: input.agent_id ?? null,
    reason: "Approved lot released.",
    correlation_id: input.correlation_id,
  });
}

export function refreshApprovalState(
  lot: Lot,
  reason = "Approvable lot content changed.",
  agentId: string | null = null,
): boolean {
  const currentHash =
    calculateLotArtifactHash(lot);

  lot.approval.artifact_hash =
    currentHash;

  if (
    !lot.approval.valid ||
    lot.approval.approved_hash === currentHash
  ) {
    return false;
  }

  const previousApprovedHash =
    lot.approval.approved_hash;

  lot.approval.valid = false;
  lot.approval.approved_by = null;
  lot.approval.approved_at = null;
  lot.approval.expires_at = null;
  lot.approval.allowed_capabilities = [];

  appendAuditEvent(lot, {
    event_type: "APPROVAL_INVALIDATED",
    agent_id: agentId,
    previous_state: lot.status,
    new_state: "QUARANTINED",
    reason,
    details: {
      previous_approved_hash:
        previousApprovedHash,
      current_artifact_hash:
        currentHash,
    },
  });

  if (
    lot.status !== "QUARANTINED" &&
    canTransition(lot.status, "QUARANTINED")
  ) {
    transitionLot(lot, "QUARANTINED", {
      agent_id: agentId,
      reason,
    });
  }

  return true;
}

export function mutateLot(
  lot: Lot,
  mutation: (target: Lot) => void,
  reason = "Approvable lot content changed.",
  agentId: string | null = null,
): boolean {
  const previousHash =
    calculateLotArtifactHash(lot);

  mutation(lot);

  const currentHash =
    calculateLotArtifactHash(lot);

  lot.approval.artifact_hash =
    currentHash;

  if (previousHash === currentHash) {
    return false;
  }

  return refreshApprovalState(
    lot,
    reason,
    agentId,
  );
}
