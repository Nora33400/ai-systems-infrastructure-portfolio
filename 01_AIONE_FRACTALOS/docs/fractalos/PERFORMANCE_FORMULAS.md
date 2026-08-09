# FractalOS Performance Formulas

FractalOS now includes a software-level `PerformanceGovernor` designed to make the runtime faster without treating the machine as disposable.

The governor does not overclock hardware. It adapts the FractalOS runtime itself:

- planner parallelism
- planner resource budget
- OmegaRAM hot and warm cache budgets
- runtime posture during `tick`

## Scientific model

### 1. Thermal headroom

For each processor class:

```text
H = clamp((T_safe - T) / (T_safe - T_idle), 0, 1)
```

Where:

- `T` is the current measured temperature
- `T_safe` is the configured safe ceiling
- `T_idle` is a conservative idle reference

If a sensor is unavailable, FractalOS applies a penalty instead of assuming infinite safety.

### 2. CPU pressure

```text
P_cpu = 0.55U_cpu + 0.20U_mem + 0.15F_cpu + 0.10U_gpu
```

Where:

- `U_cpu` is CPU utilization
- `U_mem` is RAM utilization
- `F_cpu` is current CPU frequency ratio
- `U_gpu` is dominant GPU utilization

This expresses a simple systems idea: heat and instability correlate not only with CPU load, but with memory pressure and sustained boost behavior.

### 3. GPU pressure

```text
P_gpu = 0.70U_gpu + 0.30U_vram
```

Where:

- `U_gpu` is GPU compute utilization
- `U_vram` is GPU memory utilization

### 4. Memory guard

```text
M = clamp((U_mem_target - U_mem) / U_mem_target, 0, 1)
```

This prevents FractalOS from growing cache budgets when RAM is already under pressure.

### 5. Stability index

```text
S = (H_cpu * H_gpu)^0.45 * (1 - P_cpu)^0.8 * (1 - 0.5P_gpu)^0.6 * (0.35 + 0.65M)
```

Interpretation:

- high thermal margin increases `S`
- high sustained pressure decreases `S`
- low free RAM directly reduces `S`

### 6. Throughput index

```text
Phi = (0.45 + 0.55S) * (0.60 + 0.40H_cpu) * (0.70 + 0.30H_gpu)
```

`Phi` is used to scale work budgets conservatively rather than aggressively.

## Practical application in FractalOS

The governor converts the formulas into:

- `recommended_concurrency`
- `recommended_planner_top_k`
- `recommended_resource_limit`
- `recommended_hot_budget_bytes`
- `recommended_warm_budget_bytes`

These values are written into the runtime config during `perf-tune` and automatically during `tick`.

## Safety stance

The governor is intentionally conservative:

- it never increases hardware voltages or firmware limits
- it only changes FractalOS internal scheduling and cache budgets
- it treats missing thermal sensors as uncertainty, not permission
- it degrades concurrency and cache aggressiveness when headroom shrinks

## Validation approach

Validation lives in `tests/test_perf_governor.py`.

The test suite proves three important properties:

1. rising thermal load lowers the stability and throughput indices
2. stressed scenarios reduce recommended concurrency and resource budgets
3. cache budgets grow only when RAM headroom is genuinely available

## Important limit

This is a software governor, not a hardware warranty.

It improves the odds of stable operation by keeping the runtime inside a conservative operating envelope, but it cannot guarantee absolute thermal safety in the presence of dust, failing cooling, bad BIOS settings, or external overclocking.

## Performance Lab

FractalOS also includes a safe benchmark laboratory in `omega_tile_os/core/perf_lab.py`.

It is intentionally different from a blind stress test:

- it samples the governor before every burst
- it adjusts batch size and pause time from the live stability and throughput indices
- it stops early if critical risk persists or if the thermal envelope collapses

Command:

```powershell
python -m omega_tile_os perf-benchmark --workspace .\workspace --seconds 6
```

The benchmark returns:

- iteration count
- checksum of executed work
- stop reason
- pressure-wave summary across the run

This lets FractalOS learn whether the machine handles sustained work smoothly or with unstable oscillations.

## Learned machine profile

After each benchmark campaign, FractalOS stores the campaign and derives a learned profile.

Command:

```powershell
python -m omega_tile_os perf-calibration --workspace .\workspace
```

The learned profile adjusts only software-level baselines:

- governor mode
- thermal unknown penalty
- planner baseline resource limit
- planner baseline top-k
- OmegaRAM baseline hot/warm budgets

This means FractalOS can become smarter over time while remaining bounded by conservative ceilings.

## Heterogeneous scheduler

FractalOS now exposes a heterogeneous scheduler that chooses between:

- `cpu.local`
- `gpu.1`
- `gpu.2`

based on:

- live telemetry
- learned profile
- job affinity hints such as `vectorizable`, `matrix_heavy`, `latency_sensitive`, `serial`, `accelerator_hint`

Commands:

```powershell
python -m omega_tile_os devices --workspace .\workspace
python -m omega_tile_os schedule --workspace .\workspace --jobs .\jobs.json
```

The scheduler does not force hardware execution by itself. It computes the safest recommended placement so that future worker runtimes can follow a stable routing plan.

## Future Fabric

FractalOS now includes a predictive execution fabric:

- `future-plan` converts placements into execution waves
- each wave carries a predicted post-wave state
- `future-run` executes only the waves that remain inside a safe predicted envelope

Commands:

```powershell
python -m omega_tile_os future-plan --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os future-run --workspace .\workspace --jobs .\jobs.json
```

Current truth:

- CPU-targeted jobs are executed for real inside the local Python control plane
- GPU-targeted jobs are currently routed and staged, not claimed as native CUDA execution

This keeps FractalOS honest while still allowing the orchestration layer to evolve ahead of the hardware execution backends.

## Chrono Mesh

FractalOS now compiles missions into a resilient execution graph:

- dependency edges
- per-node criticality
- resilience score
- retry budget
- recovery mode

Commands:

```powershell
python -m omega_tile_os mission-graph --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os mission-recovery --workspace .\workspace --jobs .\jobs.json --failed embed
```

This layer treats execution as a living graph rather than a flat queue. It is the basis for future self-healing and distributed execution semantics.

## Continuum Mission Memory

FractalOS now persists mission continuity in a dedicated journal:

- mission checkpoint snapshots
- completed-node projection
- replay events
- selective replay from a chosen node

Commands:

```powershell
python -m omega_tile_os mission-checkpoint --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os mission-journal --workspace .\workspace
python -m omega_tile_os mission-replay --workspace .\workspace --jobs .\jobs.json --from-job serve
```

This is the first layer of a true continuity engine: the OS can remember where a mission stopped and resume from a causal cut, rather than starting the whole graph again.

## GPU Runtime and Federated Mesh

FractalOS now exposes three higher-level control surfaces:

- `gpu-runtime`: inspect real native GPU backend availability
- `gpu-probe`: run a safe GPU execution probe or an honest simulation
- `mesh-*`: register nodes, export missions, import bundles, and inspect relay status

Commands:

```powershell
python -m omega_tile_os gpu-runtime --workspace .\workspace
python -m omega_tile_os gpu-probe --workspace .\workspace --device gpu.1 --size 96
python -m omega_tile_os mesh-register --workspace .\workspace --name node-a --endpoint http://127.0.0.1:8890 --role control
python -m omega_tile_os mesh-status --workspace .\workspace
python -m omega_tile_os mesh-export --workspace .\workspace --jobs .\jobs.json --target-node node-a
python -m omega_tile_os mission-control --workspace .\workspace
```

Current truth:

- native GPU execution is used only when an actual backend such as `torch.cuda` is available
- otherwise the system stays explicit and falls back to a simulation/staging path
- mesh relays are file-backed for now, which keeps the system simple and auditable while preparing real federation later
