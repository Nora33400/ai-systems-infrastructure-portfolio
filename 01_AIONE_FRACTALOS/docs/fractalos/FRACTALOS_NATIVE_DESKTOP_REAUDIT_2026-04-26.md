# FractalOS Native Desktop Reaudit

Date: 2026-04-26

## Summary

FractalOS was re-audited against the conversation requirements for a bootable, installable, classic-usable OS with FractalOS extensions.

The ISO boots in QEMU and the new persistent VM profile exists. The bare-metal ISO does not yet self-install because native storage, VFS, package manager, network and compositor gates are still required.

## Implemented in this pass

- Native Desktop Alpha module with login, home menu, search, TileMind explorer, terminal, web gateway, package center, office desk, media center, settings and install center.
- Persistent installation plan for VM/machine with `EFI`, `boot_a`, `boot_b`, `system`, `state`, `home` and `recovery` slots.
- A QEMU persistent-disk profile and local launcher were used during the recorded experiment but are intentionally excluded from the public portfolio because they contained machine-specific runtime paths and referenced generated disk/ISO artifacts.
- Package catalog covering Python, Rust, Java, Firefox/web domain, LibreOffice domain, codecs, Code Studio, Ollama, TileMindFS, Doctor and EXE compatibility domain.
- Runtime commands: `native-os-report`, `native-os-blueprint`, `native-os-install-plan`, `native-os-app-catalog`, `desktop-search`, `desktop-files`, `desktop-packages`, `desktop-login`.
- Bare-metal `desktop_plane` expanded from 5 layers to 10 layers, including login, start menu, search, TileMind explorer, terminal, web gateway and package center.
- Documentation: `NATIVE_DESKTOP_AND_INSTALLATION_ALPHA.md`.

## Boot validation

Command class: QEMU x86_64, ISO boot, attached persistent qcow2 disk.

Serial evidence:

- `DesktopPlane layers=0x000000000000000a overlay=0x0000000000000001 persistent=0x0000000000000009`
- `Desktop probe layers=0x000000000000000a`
- `TripleKernel score=0x000000000000031b`

Serial log: `workspace/vm_validation/native_persistent_boot_serial.log`

## Build validation

- Unit tests: 139 tests OK.
- ISO rebuilt: `build/FractalOS.iso`.
- ISO size: 5,206,016 bytes.
- Boot entries: BIOS and UEFI.
- ISO contains the new native desktop documentation.
- Doctor: 25 OK, 2 WARN, 0 FAIL.

## Current truth

FractalOS now has:

- a bootable bare-metal kernel;
- a persistent VM disk profile;
- a generated installation architecture;
- a hosted/controlled desktop model;
- a package catalog and app surfaces;
- a clear native roadmap to become daily usable.

FractalOS still needs:

- writable storage driver;
- native VFS;
- init/session manager;
- compositor/window manager;
- network stack;
- package manager implementation;
- browser/media/office runtime domains.

## User-facing next gate

The strongest next engineering step is `Userspace + VFS Alpha`: implement a RAM-backed init process, file namespace, session home model and package manifest reader. That makes the installer and desktop stop being only a model and become a native boot-time experience.
