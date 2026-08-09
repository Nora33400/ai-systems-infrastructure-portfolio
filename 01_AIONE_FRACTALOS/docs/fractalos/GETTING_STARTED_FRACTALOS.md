# FractalOS Getting Started

This guide starts from the current local machine state on 2026-04-26.

## 1. What FractalOS is today

FractalOS has two tracks:

- Bare-metal OS track: `bare_metal/` builds a real x86_64 kernel and boots from `build/FractalOS.iso`.
- Hosted control plane: `omega_tile_os/` runs on Windows/Python and provides agents, TileMindFS, OmegaRAM, doctor, auto-upgrade, dashboard, formulas, mesh and desktop preview.

The bare-metal kernel is real but early. It is not yet a Windows/Linux replacement.
The hosted control plane is the usable layer today for code, research, automation and ecosystem evolution.

## 2. Build and test the ISO

From the project root:

```powershell
cd <FRACTALOS_WORKSPACE>
powershell -ExecutionPolicy Bypass -File .\bare_metal\build.ps1
$env:PYTHONPATH='<FRACTALOS_WORKSPACE>'
python -m fractal_os build-iso --output-iso .\build\FractalOS.iso
python -m unittest discover -s .\tests
python -m fractal_os build-report
```

Expected current result:

- `bare_metal\build\fractal_kernel.elf` exists.
- `build\FractalOS.iso` exists.
- `python -m unittest discover -s .\tests` passes the current suite.
- `build-report` says `bootable_iso_ready`, `qemu_ready` and `virtualbox_ready` are true.

## 3. Boot in QEMU

BIOS-style boot:

```powershell
& 'C:\Program Files\qemu\qemu-system-x86_64.exe' -m 512M -cdrom .\build\FractalOS.iso -boot d -serial stdio -no-reboot
```

UEFI-style boot with QEMU EDK2:

```powershell
& 'C:\Program Files\qemu\qemu-system-x86_64.exe' -m 512M -drive if=pflash,format=raw,readonly=on,file='C:\Program Files\qemu\share\edk2-x86_64-code.fd' -cdrom .\build\FractalOS.iso -boot d -serial stdio -no-reboot
```

If QEMU/OVMF shows a Limine warning and asks to press a key, press Enter. The kernel continues after that.

## 4. Use the hosted OS control plane

Health:

```powershell
python -m omega_tile_os doctor --workspace .\workspace
python -m omega_tile_os usage-errors --workspace .\workspace
python -m omega_tile_os restart-recovery --workspace .\workspace --reason manual-check
```

Desktop preview and views:

```powershell
python -m omega_tile_os desktop --workspace .\workspace
python -m omega_tile_os onboarding-pack --workspace .\workspace
python -m omega_tile_os classic-os-report --workspace .\workspace
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
python -m omega_tile_os storage-vfs-read --workspace .\workspace --path /home/user/notes.txt
python -m omega_tile_os storage-vfs-snapshot --workspace .\workspace --label manual-checkpoint
python -m omega_tile_os storage-vfs-verify --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
python -m omega_tile_os ui-views --workspace .\workspace
python -m omega_tile_os dashboard --workspace .\workspace --host 127.0.0.1 --port 8765
```

AI development:

```powershell
python -m omega_tile_os ai-dev-plan --workspace .\workspace --queue
python -m omega_tile_os supervisor-plan --workspace .\workspace
python -m omega_tile_os worker-report --workspace .\workspace
```

Ollama local models:

```powershell
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull deepseek-coder-v2:16b
python -m omega_tile_os ai-model-plan --workspace .\workspace
```

## 5. Use FractalOS for code, research and automation today

For code:

```powershell
python -m omega_tile_os ai-dev-plan --workspace .\workspace --focus code --queue
python -m omega_tile_os worker-run --workspace .\workspace --max-items 1
```

For research and formulas:

```powershell
python -m omega_tile_os corpus-report --workspace .\workspace
python -m omega_tile_os formula-programs --workspace .\workspace
python -m omega_tile_os scientific-formula-report --workspace .\workspace
```

For safe runtime tuning:

```powershell
python -m omega_tile_os perf-report --workspace .\workspace
python -m omega_tile_os perf-tune --workspace .\workspace
python -m omega_tile_os gpu-runtime --workspace .\workspace
```

## 6. Current honest limits

- No full native graphical desktop yet in bare-metal mode.
- No native browser, TCP/IP stack or NIC driver yet in bare-metal mode.
- No native persistent disk filesystem yet in bare-metal mode; Stage22 adds a hosted persistent Storage VFS and a kernel storage plane, but not a native block driver.
- No `.exe` compatibility layer yet in bare-metal mode.
- No native Python/Rust/Java runtime installation inside bare-metal mode yet.
- The hosted control plane can use Windows/Python tools and host internet today.
- `classic-os-report` now tracks the gap between a classic desktop OS and the current FractalOS kernel/control-plane split.
- `native-os-report` adds the installable desktop plan: login, start menu, search, TileMind explorer, terminal, web gateway, package center, office/media centers, settings, persistent VM disk and rollback slots.
- `userspace-alpha-report` adds the first OS matter model: sessions, RAM VFS, `/home/user`, `/apps/packages.json`, TileMindFS bridge and bare-metal VFS/package probes.
- `storage-vfs-report` adds persistent hosted `/home` writes, journal, snapshots, rollback and bare-metal storage-plane probes.

## 7. Best next milestone

The next major OS milestone is `FractalOS Stage23 Native Storage And Init`:

- native block-device abstraction and fake-disk harness;
- kernel storage-backed VFS bound to the persistent VM disk;
- file association registry for text, image, PDF, office and media;
- first `init` handoff from kernel console to desktop session;
- ring3/ELF loader preparation;
- package/runtime bridge for Python, Rust and Java through hosted or VM-backed domains.
