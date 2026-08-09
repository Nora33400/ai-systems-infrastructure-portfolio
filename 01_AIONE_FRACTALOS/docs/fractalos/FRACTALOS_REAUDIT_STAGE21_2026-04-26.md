# FractalOS Reaudit Stage21

Date: 2026-04-26

## Verdict

FractalOS boots as a real x86_64 bare-metal ISO and now exposes a Stage21 native userspace alpha: desktop-plane primitives, session roles, RAM VFS, TileMindFS bridge, package manifest and kernel VFS/package probes.

It is not yet a daily Windows/Linux replacement. The next native gate is storage-backed VFS, init/ring3 process isolation, network, compositor and package installation with signed rollback slots.

## What Was Rechecked

| Area | Result |
|---|---|
| Bare-metal ISO | Built as `build/FractalOS.iso` |
| QEMU boot | Boot log confirms kernel, userspace, VFS and packages |
| Persistent VM disk | Disk profile and QEMU start script exist |
| Doctor | `fail=0`, Stage21 recognized |
| Tests | Unit suite expected to pass before release |
| Docs in ISO | Stage21 docs are included in the ISO tree |

## Classic OS Capability Answers

| Question | Current answer |
|---|---|
| Desktop usable like Windows/Linux? | Partial. Hosted dashboard and native desktop-plane model exist; real compositor/window manager is next. |
| Internet/browser? | Partial. Host bridge/catalog exists; native NIC/TCP/IP/browser domain is next. |
| PNG/JPEG/TXT/PDF extensions? | Partial. Host can process files; native MIME registry/viewers are next. |
| Video playback? | Not native yet. Needs audio/video drivers and codecs. |
| Read/write/modify files? | Yes in hosted workspace and RAM VFS; not yet persistent native disk writes. |
| Word/LibreOffice documents? | Planned through package catalog and office domain; native office container is next. |
| Execute `.exe` or other binaries? | Not native yet. ELF first, then EXE compatibility through isolated domain. |
| Install Python/Rust/Java/modules? | Catalog exists; signed native package manager/dependency solver is next. |
| Intuitive onboarding? | Yes in docs/dashboard model; native first-run overlay is next. |
| User sessions? | Roles exist in runtime (`guest`, `user`, `admin`, `doctor`); native auth/homes are next. |

## Stage21 Kernel Additions

- `kernel/core/vfs.c`: RAM VFS seed, mount/node counters and `/home/user/README.txt` open probe.
- `kernel/core/package.c`: package catalog counters and policy score.
- `kernel/core/userspace.c`: native program registry now includes `init`, `vfs`, `packages` and `desktop`.
- `kernel/core/syscall.c`: VFS and package syscalls.
- `kernel/core/console.c`: shell commands for `vfs`, `vfs-open`, `packages`, `package-policy`.

## Runtime Additions

- `native-userspace` Doctor check.
- `userspace-alpha-report`, `session-start`, `vfs-ls`, `vfs-read`, `vfs-write`, `package-manifest` CLI commands.
- UI view `userspace-vfs-alpha`.
- Atomic/resilient state writes for `native_userspace.json`.
- Event log reader skips corrupt JSONL fragments instead of crashing Doctor/UI.

## Remaining Native Gates

1. Storage-backed VFS connected to the persistent VM disk.
2. Ring3 process loading, ELF execution and init.
3. Native compositor/window manager with input focus and app surfaces.
4. NIC driver, TCP/IP, DNS, TLS and browser sandbox.
5. Signed package manager with dependency solver and boot-slot rollback.
6. MIME registry and viewers for text, image, PDF, office and media files.
7. Real installer writing EFI, boot A/B, system, state, home and recovery slots.

## Next Upgrade Target

Stage22 should implement the storage-backed VFS simulator first, then bind it to the installer plan. That creates the bridge from "FractalOS can boot and model a desktop" to "FractalOS can persist user files and system state across VM restarts."
