# FractalOS Native Desktop And Installation Alpha

Date: 2026-04-26

## Truth gate

FractalOS boots today as a real x86_64 bare-metal prototype from `build/FractalOS.iso`.

It is not yet a complete daily Windows/Linux replacement because the native kernel still needs native block-backed writes, ring3 init, native auth/session isolation, network, package manager and compositor. The current alpha includes RAM VFS, hosted persistent Storage VFS, package manifest, desktop-plane probes and storage-plane probes, so this document turns the remaining gap into an installable architecture instead of hiding it.

## What is integrated now

- Login model: `guest`, `user`, `admin`, `doctor`.
- Desktop model: welcome, start menu, search, TileMind file explorer, terminal, web gateway, package center, office desk, media center, settings and install center.
- Persistent VM plan: generated QEMU disk profile, start script, disk slots and rollback model.
- Package catalog: Python, Rust, Java, Firefox/web domain, LibreOffice domain, codecs, Code Studio, Ollama, TileMindFS, Doctor and EXE compatibility domain.
- Fractal extensions: intent overlay, proof ribbon, energy strip, agent orbit, formula lab and rollback-safe package promotion.
- Userspace + VFS Alpha: sessions, RAM VFS, `/home/user`, `/apps/packages.json`, TileMindFS bridge and kernel VFS/package probes.
- Storage VFS Stage22: hosted persistent `/home`, journaled writes, snapshots, rollback, Doctor verification, UI actions and kernel storage-plane telemetry.

## Commands

```powershell
python -m omega_tile_os native-os-report --workspace .\workspace
python -m omega_tile_os native-os-blueprint --workspace .\workspace
python -m omega_tile_os native-os-install-plan --workspace .\workspace --target vm --create-vm-disk
python -m omega_tile_os native-os-app-catalog --workspace .\workspace
python -m omega_tile_os desktop-login --workspace .\workspace --role user
python -m omega_tile_os desktop-search --workspace .\workspace --query package
python -m omega_tile_os desktop-files --workspace .\workspace
python -m omega_tile_os desktop-packages --workspace .\workspace
python -m omega_tile_os storage-vfs-status --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
```

## Persistent disk slots

- `EFI`: UEFI boot files and Limine.
- `boot_a`: current verified FractalOS kernel slot.
- `boot_b`: known-good rollback kernel slot.
- `system`: native services and package base.
- `state`: doctor logs, proofs, policies and sessions.
- `home`: user files, tiles, documents and app data.
- `recovery`: known-good modules and repair bundles.

## Install flow target

- Boot ISO with persistent disk attached.
- Doctor verifies kernel, bootloader, package signatures and rollback slot.
- Installer writes `EFI` and `boot_a`, keeps `boot_b` known-good, then creates `system`, `state`, `home` and `recovery`.
- Safe restart validates desktop, sessions, package catalog and TileMindFS.
- If validation passes, FractalOS promotes the new slot; otherwise it falls back.

## Native gates still required

- Native writable storage driver.
- Kernel storage-backed VFS and file associations.
- Init process and user session manager.
- Network stack and browser domain.
- Desktop compositor/window manager.
- Signed package manager with dependency solver.
