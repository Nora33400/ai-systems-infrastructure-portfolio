# FractalOS Reaudit Stage22

Date: 2026-04-26

## Result

Stage22 is integrated and verified.

FractalOS now has a persistent hosted Storage VFS for `/home`, journaled writes, snapshots, rollback, Doctor verification, dashboard/UI actions, CLI commands and a bare-metal kernel storage plane visible during boot.

## What Was Added

- `omega_tile_os/core/storage_vfs.py`: hosted persistent `/home` layer with journal, verify, snapshot, rollback and report.
- Native userspace bridge: `/home` writes now persist through Storage VFS while RAM VFS remains available.
- CLI commands: `storage-vfs-status`, `storage-vfs-write`, `storage-vfs-read`, `storage-vfs-snapshot`, `storage-vfs-rollback`, `storage-vfs-verify`, `storage-vfs-report`.
- Dashboard/UI: new `storage-vfs-stage22` view and actions.
- Doctor: new `storage-vfs` check and Stage22 bare-metal kernel check.
- Bare-metal kernel: `kernel/core/storage_plane.c`, syscalls `26..29`, console commands `storage` and `storage-snapshot`, serial boot report.
- Documentation: `docs/STORAGE_VFS_STAGE22.md` plus updated getting-started and classic OS capability docs.

## Verified Commands

```powershell
python -m unittest tests.test_storage_vfs tests.test_native_userspace tests.test_doctor tests.test_bare_metal_kernel
python -m unittest discover -s tests
python -m omega_tile_os storage-vfs-write --workspace .\workspace --path /home/user/stage22-validation.txt --text "FractalOS Stage22 persistent home validation" --owner codex-stage22
python -m omega_tile_os storage-vfs-snapshot --workspace .\workspace --label stage22-validation
python -m omega_tile_os storage-vfs-verify --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
python -m omega_tile_os doctor --workspace .\workspace
powershell -ExecutionPolicy Bypass -File .\bare_metal\build.ps1
python -m fractal_os build-iso --output-iso <FRACTALOS_WORKSPACE>\build\FractalOS.iso
python -m fractal_os build-report
```

## Test Evidence

- Targeted Stage22 tests: `33` tests passed.
- Full suite: `150` tests passed.
- Doctor: `26 ok`, `3 warn`, `0 fail`.
- Kernel build: `bare_metal/build/fractal_kernel.elf` built successfully.
- ISO: `build/FractalOS.iso`, about `5.24 MB`.

Doctor warnings are non-blocking:

- autonomy queue is high;
- one historical usage-blackbox error is recorded;
- native GPU runtime was not detected.

## QEMU Boot Evidence

Boot was validated with QEMU using the rebuilt ISO and the persistent VM disk.

Serial proof:

```text
FractalOS bare-metal kernel 0.5.0 booting
Userspace programs=0x0000000000000008 launches=0x0000000000000000 last_program=0x0000000000000000
VFS mounts=0x0000000000000002 nodes=0x000000000000000a opens=0x0000000000000000
VFS probe nodes=0x000000000000000a
Packages manifests=0x0000000000000001 available=0x000000000000000c policy=0x00000000000000ea
Package probe available=0x000000000000000c
StorageVFS slots=0x0000000000000007 journal=0x0000000000000001 snapshots=0x0000000000000001 score=0x0000000000000157
Storage probe slots=0x0000000000000007
TripleKernel score=0x000000000000031b
```

Serial log:

```text
workspace/vm_validation/stage22_final_serial.log
workspace/vm_validation/stage22_final_iso_serial.log
```

## Classic OS Capability Status

- Desktop for office work: modeled through hosted desktop/control plane, not yet native compositor.
- Internet/browser: host internet available to control plane, no native NIC/TCP/browser yet.
- File extensions: text and hosted file manipulation exist; native PNG/JPEG/PDF/video viewers remain future gates.
- Video: not native yet.
- Read/write files: yes in hosted Storage VFS under `/home`; not yet native disk-backed kernel VFS.
- Word/LibreOffice: host/domain plan exists; no native suite yet.
- `.exe`: no native compatibility layer yet; planned as isolated domain.
- Python/Rust/Java modules: host/toolchain support exists; native package install still planned.
- Onboarding: docs, Doctor, dashboard and UI views exist.
- User sessions: hosted roles/sessions are modeled; native auth/session isolation remains Stage23+.

## Truth Gate

Stage22 does not claim a full Windows/Linux replacement. It closes one important gap: FractalOS can now persist user-home state in the hosted runtime and expose storage readiness in the booted kernel.

The next big native gate is Stage23:

- native block-device abstraction;
- kernel storage-backed VFS;
- init/session handoff;
- file associations;
- ring3/ELF process path;
- package/runtime domains with rollback.
