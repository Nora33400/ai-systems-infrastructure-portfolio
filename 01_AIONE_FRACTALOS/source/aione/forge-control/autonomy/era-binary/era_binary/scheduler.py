"""Deterministic heterogeneous scheduler for HCI reference programs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ComplexityVector:
    computational: float = 0.5
    memory: float = 0.5
    semantic: float = 0.5
    contextual: float = 0.5
    temporal: float = 0.5
    functional: float = 0.5
    relational: float = 0.5
    verification: float = 0.5
    coordination: float = 0.5
    uncertainty: float = 0.5
    reversibility: float = 0.5
    hardware_transfer: float = 0.5

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def plan_execution(
    topology: dict[str, Any],
    complexity: ComplexityVector | None = None,
    *,
    thermal_limit_celsius: int = 82,
    reserve_vram_mb: int = 1_024,
) -> dict[str, Any]:
    complexity = complexity or ComplexityVector()
    gpus = topology.get("gpus") or []
    usable = []
    rejected = []
    for gpu in gpus:
        free_mb = max(0, int(gpu.get("memoryTotalMb", 0)) - int(gpu.get("memoryUsedMb", 0)))
        temperature = int(gpu.get("temperatureCelsius", thermal_limit_celsius + 1))
        reasons = []
        if temperature >= thermal_limit_celsius:
            reasons.append("THERMAL_LIMIT")
        if free_mb < reserve_vram_mb:
            reasons.append("VRAM_RESERVE")
        entry = {"uuid": gpu.get("uuid"), "freeVramMb": free_mb, "temperatureCelsius": temperature}
        if reasons:
            rejected.append({**entry, "reasons": reasons})
        else:
            usable.append(entry)

    if len(usable) >= 2 and (complexity.computational + complexity.coordination) / 2 >= 0.65:
        morphology = "MULTI_GPU"
    elif usable and complexity.computational >= 0.35:
        morphology = "CPU_GPU"
    else:
        morphology = "CPU_ONLY"
    branch_budget = 1
    if morphology == "CPU_GPU":
        branch_budget = min(8, max(2, int(2 + 6 * complexity.uncertainty)))
    elif morphology == "MULTI_GPU":
        branch_budget = min(16, max(4, int(4 + 12 * complexity.uncertainty)))
    return {
        "schema": "aione.heterogeneous-cognitive-plan.v1",
        "morphology": morphology,
        "complexity": asdict(complexity),
        "allocations": {
            "cpuThreads": min(4, int(topology.get("cpu", {}).get("logicalProcessors", 1))),
            "gpuUuids": [item["uuid"] for item in usable[: 2 if morphology == "MULTI_GPU" else 1]],
            "hypothesisBranches": branch_budget,
            "verificationDomain": "CPU_DETERMINISTIC",
            "persistentDomain": "NVME_EVIDENCE_ONLY",
        },
        "rejectedResources": rejected,
        "fallbackTree": ["REDUCE_BRANCH_COUNT", "MIGRATE_TO_CPU", "STOP_WITH_EVIDENCE"],
        "explanation": (
            "Two safe GPU lanes selected for bounded branching."
            if morphology == "MULTI_GPU"
            else "One safe GPU lane selected; deterministic verification remains on CPU."
            if morphology == "CPU_GPU"
            else "GPU constraints or task profile require CPU-only reference execution."
        ),
    }

