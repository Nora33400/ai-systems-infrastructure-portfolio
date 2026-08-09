export const LOT_STATES = [
  "DRAFT",
  "DESIGNED",
  "WORKING_ISOLATED",
  "TESTING",
  "QUARANTINED",
  "AWAITING_APPROVAL",
  "APPROVED",
  "EXECUTING",
  "VERIFYING",
  "COMPLETED",
  "REJECTED",
  "BLOCKED",
  "FAILED",
  "ROLLING_BACK",
  "ROLLED_BACK",
  "DEAD_LETTER",
] as const;

export type LotState = (typeof LOT_STATES)[number];

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface LotScope {
  allowed_paths: string[];
  allowed_actions: string[];
  forbidden_actions: string[];
}

export interface LotArtifacts {
  created: string[];
  modified: string[];
  deleted: string[];
}

export interface LotVerification {
  commands: string[];
  tests_passed: boolean;
  lint_passed: boolean;
  security_scan_passed: boolean;
  results: string[];
}

export interface LotRisk {
  level: RiskLevel;
  reasons: string[];
}

export interface LotApproval {
  required_level: "A0" | "A1" | "A2" | "A3" | "A4";
  artifact_hash: string | null;
  approved_hash: string | null;
  approved_by: string | null;
  approved_at: string | null;
  expires_at: string | null;
  allowed_capabilities: string[];
  valid: boolean;
}

export interface LotRollback {
  strategy: string;
  instructions: string[];
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  task_id: string;
  lot_id: string;
  agent_id: string | null;
  previous_state: LotState | null;
  new_state: LotState | null;
  reason: string;
  correlation_id: string;
  created_at: string;
  details?: Record<string, unknown> | undefined;
}

export interface LotAudit {
  created_at: string;
  updated_at: string;
  events: AuditEvent[];
}

export interface Lot {
  schema_version: "1.0";
  lot_id: string;
  task_id: string;
  title: string;
  description: string;
  status: LotState;

  scope: LotScope;
  dependencies: string[];
  requested_capabilities: string[];

  artifacts: LotArtifacts;
  verification: LotVerification;
  risk: LotRisk;
  approval: LotApproval;
  rollback: LotRollback;
  audit: LotAudit;
}
