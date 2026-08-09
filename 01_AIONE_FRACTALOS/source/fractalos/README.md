# FractalOS

FractalOS is a local fusion/runtime prototype assembled from selected historical project components.

It combines:

- the runnable core from `omega_tilemind_os`
- the orchestration grammar from `OmegaSystem`
- the daemon and router mindset from `Omegafusion`
- the local AI stack from `local_ai_stack_pack`
- the command-center ambition from `fractal_auto_evolution_realtime`
- the forge pipeline from `fractal_ecosystem_build_v6` and `hypi`
- the overlay direction from `LAYER_HUD`
- the identity conventions from `IA`
- the advanced module bank from `folder0001/OmegaSystem2.12`

## What is inside

### 1. Live runtime

Current live runtime remains in `omega_tile_os/` and already provides:

- TileMindFS
- OmegaRAM
- PerformanceGovernor
- planner
- daemon
- dashboard
- Autonomy runtime for `code`, `research`, `automation`, and `ecosystem`

### 2. Fusion wrapper

The new top-level wrapper is `fractal_os/`.

Commands:

```powershell
cd 01_AIONE_FRACTALOS\source\fractalos
python -m fractal_os fusion-report
python -m fractal_os build-report
python -m fractal_os stage-runtime
python -m fractal_os stage-iso
python -m fractal_os build-iso
```

### 3. Boot and ISO builder

- `boot/uefi/` contains a custom UEFI x64 bootloader source
- `builder/` contains the staging and ISO build helpers

### 4. Fusion runtime

`FractalOS` now stages a concrete merged runtime snapshot in `build/fusion_runtime/`.

This pulls selected high-value files from:

- `OmegaSystem`
- `Omegafusion`
- `omega_tilemind_os`
- `fractal_ecosystem_build_v6`
- `fractal_auto_evolution_realtime`
- `local_ai_stack_pack`
- `LAYER_HUD`
- `hypi`
- `IA`
- `folder0001/OmegaSystem2.12`

So the builder now works with a real staged fusion payload, not only a conceptual registry.

## Important truth

This workspace now contains:

- a fused FractalOS project;
- a hosted control plane for agents, research, automation, TileMindFS, OmegaRAM and auto-upgrade;
- a real x86_64 bare-metal kernel line in `bare_metal/`;
- a bootable ISO at `build/FractalOS.iso`;
- a Limine BIOS + UEFI boot path staged by the ISO builder.

Current verification on 2026-04-26:

- LLVM, QEMU and VirtualBox are installed outside PATH and detected by FractalOS.
- `pycdlib` is used for ISO generation; `xorriso` and `oscdimg` are not required for the current path.
- QEMU BIOS reaches the FractalOS kernel and emits `TripleKernel score=0x000000000000031b`, VFS probes and package probes.
- QEMU UEFI reaches the FractalOS kernel after the OVMF/Limine key prompt.
- The bare-metal kernel is real but early; it is not yet a daily Windows/Linux replacement.
- Native Desktop Alpha now models the missing classic OS surface: login, start menu, search, TileMind explorer, terminal, web gateway, package center, office/media centers, settings and install center.
- Persistent installation is staged as a VM/machine install plan with QEMU disk profile and A/B rollback slots; the ISO does not yet self-install until native storage-backed VFS, ring3/session and package gates are implemented.
- Userspace + VFS Alpha now adds runtime sessions, a RAM-backed VFS, home directories, package manifests, TileMindFS bridge and bare-metal VFS/package probes.
- Storage VFS Stage22 now adds a hosted persistent `/home`, journaled writes, snapshots, rollback, Doctor verification, UI actions and a kernel storage plane visible during boot.

Start here:

- `docs/GETTING_STARTED_FRACTALOS.md`
- `docs/CLASSIC_OS_CAPABILITY_MATRIX.md`
- `docs/NATIVE_DESKTOP_AND_INSTALLATION_ALPHA.md`
- `docs/USERSPACE_VFS_ALPHA.md`
- `docs/STORAGE_VFS_STAGE22.md`
- `docs/FRACTALOS_REAUDIT_STAGE22_2026-04-26.md`
- `docs/FRACTALOS_REAUDIT_STAGE21_2026-04-26.md`
- `docs/FRACTALOS_BOOT_AUDIT_2026-04-25.md`

## Recommended next commands

### Runtime

```powershell
python -m omega_tile_os init --workspace .\workspace
python -m omega_tile_os submit --workspace .\workspace --title "FractalOS fusion node" --intent "Build a sovereign FractalOS with TileMindFS, OmegaRAM, daemon, dashboard, local AI and HUD bridge."
python -m omega_tile_os tick --workspace .\workspace
python -m omega_tile_os status --workspace .\workspace
python -m omega_tile_os perf-report --workspace .\workspace
python -m omega_tile_os perf-tune --workspace .\workspace
python -m omega_tile_os perf-benchmark --workspace .\workspace --seconds 6
python -m omega_tile_os perf-calibration --workspace .\workspace
python -m omega_tile_os devices --workspace .\workspace
python -m omega_tile_os schedule --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os future-plan --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os future-run --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os mission-graph --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os mission-recovery --workspace .\workspace --jobs .\jobs.json --failed embed
python -m omega_tile_os mission-checkpoint --workspace .\workspace --jobs .\jobs.json
python -m omega_tile_os mission-journal --workspace .\workspace
python -m omega_tile_os mission-replay --workspace .\workspace --jobs .\jobs.json --from-job serve
python -m omega_tile_os gpu-runtime --workspace .\workspace
python -m omega_tile_os gpu-probe --workspace .\workspace --device gpu.1 --size 96
python -m omega_tile_os mesh-register --workspace .\workspace --name node-a --endpoint http://127.0.0.1:8890 --role control
python -m omega_tile_os mesh-status --workspace .\workspace
python -m omega_tile_os mesh-export --workspace .\workspace --jobs .\jobs.json --target-node node-a
python -m omega_tile_os mission-control --workspace .\workspace
python -m omega_tile_os autonomy-submit --workspace .\workspace --domain code --title "Code lane" --goal "Organize the next coding cycle."
python -m omega_tile_os autonomy-run --workspace .\workspace --max-items 2
python -m omega_tile_os autonomy-report --workspace .\workspace
python -m omega_tile_os autonomy-evolve --workspace .\workspace
python -m omega_tile_os auto-upgrade --workspace .\workspace --duration-minutes 60 --cycle-delay 60 --run-tests
python -m omega_tile_os auto-upgrade-report --workspace .\workspace
python -m omega_tile_os usage-errors --workspace .\workspace
python -m omega_tile_os restart-recovery --workspace .\workspace --reason manual-boot-check
python -m omega_tile_os ai-model-plan --workspace .\workspace
python -m omega_tile_os classic-os-report --workspace .\workspace
python -m omega_tile_os onboarding-pack --workspace .\workspace
python -m omega_tile_os native-os-report --workspace .\workspace
python -m omega_tile_os native-os-install-plan --workspace .\workspace --target vm --create-vm-disk
python -m omega_tile_os desktop-login --workspace .\workspace --role user
python -m omega_tile_os desktop-search --workspace .\workspace --query package
python -m omega_tile_os desktop-files --workspace .\workspace
python -m omega_tile_os desktop-packages --workspace .\workspace
python -m omega_tile_os userspace-alpha-report --workspace .\workspace
python -m omega_tile_os session-start --workspace .\workspace --role user
python -m omega_tile_os vfs-ls --workspace .\workspace --path /
python -m omega_tile_os vfs-read --workspace .\workspace --path /etc/fractalos-release
python -m omega_tile_os package-manifest --workspace .\workspace
python -m omega_tile_os storage-vfs-status --workspace .\workspace
python -m omega_tile_os storage-vfs-write --workspace .\workspace --path /home/user/notes.txt --text "FractalOS persists"
python -m omega_tile_os storage-vfs-snapshot --workspace .\workspace --label manual-checkpoint
python -m omega_tile_os storage-vfs-verify --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
```

### Builder

```powershell
python -m fractal_os fusion-report
python -m fractal_os build-report
python -m fractal_os stage-runtime
python -m fractal_os stage-iso
python -m fractal_os build-iso
```

## Performance and safety

FractalOS now includes a software-level performance governor that samples CPU, RAM and NVIDIA GPU telemetry, then adjusts:

- planner concurrency
- planner resource budget
- OmegaRAM hot budget
- OmegaRAM warm budget

The formulas and safety model are documented in `docs/PERFORMANCE_FORMULAS.md`.

## Auto-upgrade mode

FractalOS also includes a guarded auto-upgrade loop documented in `docs/AUTO_UPGRADE_MODE.md`.
It generates candidate upgrade programs, verifies them with doctor, simulation, tests and the
bare-metal build, performs a safe validation reboot, retests, then promotes only candidates that
pass the proof gate.

Restart recovery and local AI model orchestration are documented in
`docs/USAGE_ERROR_RECOVERY.md` and `docs/LOCAL_AI_AGENT_MODELS.md`.
