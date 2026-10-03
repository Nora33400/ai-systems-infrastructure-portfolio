# Hardware runtime smoke test

Purpose: verify that the Forge/AIONE runtime can perform real work on the target machine rather than merely remaining idle.

Target profile:
- CPU: Ryzen 7 5700X
- RAM: 32 GB DDR4
- GPU A: RTX 3060 12 GB
- GPU B: RTX 4060 8 GB

The test is intentionally a smoke/load test, not a benchmark. It must be safe to stop and must not require Internet access.

## Test phases
1. CPU/RAM baseline.
2. GPU discovery and CUDA visibility.
3. Single-GPU inference/workload on each GPU.
4. Concurrent dual-GPU workloads with isolated workers.
5. Context/memory pressure exercise.
6. Recovery after worker completion.
7. Resource report and pass/fail decision.

## Pass criteria
- Both GPUs are detected with expected VRAM class.
- CPU worker performs measurable work.
- RAM usage rises above idle during workload and returns toward baseline after cleanup.
- Each GPU shows non-trivial utilization during its assigned workload.
- Dual-GPU phase runs concurrently without treating VRAM as pooled.
- No worker requires external network access.
- No unbounded memory growth.
- Workloads terminate cleanly and produce a machine-readable report.

The test should report observed values rather than claiming a pass when telemetry is unavailable.
