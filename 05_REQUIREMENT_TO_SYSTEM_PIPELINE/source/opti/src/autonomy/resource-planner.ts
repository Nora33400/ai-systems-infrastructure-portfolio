import { execFile } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parse } from "yaml";

export type ResourceMode = "PERSONAL_INTERACTIVE" | "AI_BALANCED" | "AUTONOMOUS_CODING" | "HEAVY_REASONING" | "LOW_POWER" | "GAMING";
export type UserActivity = "ACTIVE" | "IDLE" | "UNKNOWN";

export interface GpuSnapshot {
  index: number;
  name: string;
  memory_total_mb: number;
  memory_used_mb: number;
  utilization_percent: number;
  temperature_c: number;
  driver_version: string;
}

export interface HardwareSnapshot {
  observed_at: string;
  observer: "nvidia-smi";
  user_activity: UserActivity;
  fullscreen: boolean;
  game_detected: boolean;
  gpus: GpuSnapshot[];
}

export interface ResourceDemand {
  requested_workers: number;
  heavy_reasoning: boolean;
  gpu_required: boolean;
}

export interface ResourceRecommendation {
  mode: ResourceMode;
  dry_run: true;
  allowed_parallel_workers: number;
  reasons: string[];
  warnings: string[];
  assignments: Array<{ gpu_index: number; role: string }>;
}

interface ResourcePolicyDocument {
  schema_version: 1;
  activation: "dry_run_only";
  user_activity_priority: "absolute";
  safeguards: {
    max_gpu_temperature_c: number;
    reserve_vram_gpu1_mb: number;
    pause_on_fullscreen_application: boolean;
    pause_on_game_detected: boolean;
    checkpoint_before_mode_switch: boolean;
    never_kill_uncommitted_agent_work: boolean;
  };
  modes: Record<string, { max_parallel_agents: number }>;
  source_refs: string[];
}

type NvidiaRunner = (args: string[]) => Promise<string>;

function defaultNvidiaRunner(args: string[]): Promise<string> {
  return new Promise((resolveOutput, reject) => {
    execFile("nvidia-smi", args, { windowsHide: true, timeout: 5_000, maxBuffer: 1024 * 1024 }, (error, stdout) => {
      if (error) reject(error);
      else resolveOutput(stdout);
    });
  });
}

export class NvidiaSmiObserver {
  constructor(private readonly runner: NvidiaRunner = defaultNvidiaRunner) {}

  async observe(activity: Pick<HardwareSnapshot, "user_activity" | "fullscreen" | "game_detected">): Promise<HardwareSnapshot> {
    const output = await this.runner([
      "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu,driver_version",
      "--format=csv,noheader,nounits",
    ]);
    const gpus = output.trim().split(/\r?\n/).filter(Boolean).map((line): GpuSnapshot => {
      const fields = line.split(",").map((field) => field.trim());
      if (fields.length !== 7) throw new Error(`Unexpected nvidia-smi row: ${line}`);
      const numbers = [fields[0], fields[2], fields[3], fields[4], fields[5]].map(Number);
      if (numbers.some((value) => !Number.isFinite(value))) throw new Error(`Invalid numeric nvidia-smi row: ${line}`);
      return {
        index: numbers[0]!,
        name: fields[1]!,
        memory_total_mb: numbers[1]!,
        memory_used_mb: numbers[2]!,
        utilization_percent: numbers[3]!,
        temperature_c: numbers[4]!,
        driver_version: fields[6]!,
      };
    });
    return { observed_at: new Date().toISOString(), observer: "nvidia-smi", ...activity, gpus };
  }
}

export class ResourcePlanner {
  private constructor(readonly document: ResourcePolicyDocument) {}

  static load(policyPathInput: string, schemaPathInput: string): ResourcePlanner {
    const document = parse(readFileSync(resolve(policyPathInput), "utf8")) as ResourcePolicyDocument;
    const schema = JSON.parse(readFileSync(resolve(schemaPathInput), "utf8")) as Record<string, unknown>;
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    const validate = ajv.compile<ResourcePolicyDocument>(schema);
    if (!validate(document)) throw new Error(`Invalid resource policy: ${ajv.errorsText(validate.errors, { separator: "; " })}`);
    return new ResourcePlanner(document);
  }

  recommend(snapshot: HardwareSnapshot, demand: ResourceDemand): ResourceRecommendation {
    const warnings: string[] = [];
    const hot = snapshot.gpus.filter((gpu) => gpu.temperature_c >= this.document.safeguards.max_gpu_temperature_c);
    if (hot.length > 0) warnings.push(`temperature_limit_reached:${hot.map((gpu) => gpu.index).join(",")}`);
    const unsafe = hot.length > 0 || snapshot.gpus.length === 0;

    if (snapshot.game_detected && this.document.safeguards.pause_on_game_detected) {
      return this.result("GAMING", ["game_detected", "owner_activity_priority"], warnings, snapshot, 1);
    }
    if (snapshot.fullscreen && this.document.safeguards.pause_on_fullscreen_application) {
      return this.result("PERSONAL_INTERACTIVE", ["fullscreen_application", "owner_activity_priority"], warnings, snapshot, Math.min(demand.requested_workers, 1));
    }
    if (snapshot.user_activity !== "IDLE") {
      const allowedWorkers = snapshot.user_activity === "UNKNOWN" ? 0 : Math.min(demand.requested_workers, 1);
      return this.result("PERSONAL_INTERACTIVE", [snapshot.user_activity === "ACTIVE" ? "user_active" : "user_activity_unknown", "fail_closed_for_gpu_work"], warnings, snapshot, allowedWorkers);
    }
    if (!demand.gpu_required || demand.requested_workers === 0 || unsafe) {
      return this.result("LOW_POWER", [unsafe ? "gpu_unavailable_or_hot" : "no_gpu_work_requested"], warnings, snapshot, 0);
    }
    if (demand.heavy_reasoning) {
      if (snapshot.gpus.length < 2) warnings.push("heavy_reasoning_requires_two_verified_gpus");
      const mode = snapshot.gpus.length >= 2 ? "HEAVY_REASONING" : "AI_BALANCED";
      return this.result(mode, [snapshot.gpus.length >= 2 ? "bounded_two_gpu_heavy_demand" : "single_gpu_fallback"], warnings, snapshot, 1);
    }
    if (demand.requested_workers >= 2 && snapshot.gpus.length >= 2) {
      return this.result("AUTONOMOUS_CODING", ["two_independent_workers_requested"], warnings, snapshot, 2);
    }
    return this.result("AI_BALANCED", ["single_gpu_worker_requested"], warnings, snapshot, 1);
  }

  private result(mode: ResourceMode, reasons: string[], warnings: string[], snapshot: HardwareSnapshot, requestedWorkers: number): ResourceRecommendation {
    const configured = this.document.modes[mode.toLowerCase()]?.max_parallel_agents ?? requestedWorkers;
    const allowed = Math.min(requestedWorkers, configured);
    const assignments: ResourceRecommendation["assignments"] = [];
    if (mode === "AUTONOMOUS_CODING" && allowed >= 2) {
      if (snapshot.gpus[0]) assignments.push({ gpu_index: snapshot.gpus[0].index, role: "developer" });
      if (snapshot.gpus[1]) assignments.push({ gpu_index: snapshot.gpus[1].index, role: "reviewer" });
    } else if (mode === "HEAVY_REASONING") {
      assignments.push(...snapshot.gpus.slice(0, 2).map((gpu) => ({ gpu_index: gpu.index, role: "shared_model" })));
    } else if (["AI_BALANCED", "PERSONAL_INTERACTIVE"].includes(mode) && allowed > 0 && snapshot.gpus[0]) {
      assignments.push({ gpu_index: snapshot.gpus[0].index, role: mode === "PERSONAL_INTERACTIVE" ? "background_ai_limited" : "ai_primary" });
    }
    return { mode, dry_run: true, allowed_parallel_workers: allowed, reasons, warnings, assignments };
  }
}
