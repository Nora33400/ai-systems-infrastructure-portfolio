# FractalOS Full Re-Audit - 2026-04-25

## Scope

This audit re-ran the full FractalOS check after adding the classic OS bridge:

- source scan for suspicious markers and incoherence;
- unit tests;
- Doctor;
- build report;
- ISO rebuild;
- QEMU boot validation;
- missing conversation elements integrated into runtime and docs.

## Current ISO

- Path: `<FRACTALOS_WORKSPACE>\build\FractalOS.iso`
- Builder: `python -m fractal_os build-iso`
- ISO backend: `pycdlib`
- Bootloader: Limine BIOS + UEFI
- BIOS install: successful
- Kernel payload: `bare_metal\build\fractal_kernel.elf`

## Validation Results

| Check | Result |
|---|---|
| Unit tests | 133 passed |
| Build report | `bootable_iso_ready=true` |
| QEMU availability | detected at `C:\Program Files\qemu\qemu-system-x86_64.exe` |
| VirtualBox availability | detected at `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe` |
| LLVM availability | detected at `C:\Program Files\LLVM\bin` |
| QEMU BIOS boot | reaches FractalOS kernel |
| Serial boot target | `TripleKernel score=0x000000000000031b` |
| Doctor | 0 fail, warnings only |
| Corpus integration | `14996/14996` formula files indexed |

## QEMU Evidence

- Screenshot: `<FRACTALOS_WORKSPACE>\workspace\vm_validation\qemu_boot_reaudit_screendump.bmp`
- Serial log: `<FRACTALOS_WORKSPACE>\qemu_reaudit_serial.log`

Serial confirmation:

```text
FractalOS bare-metal kernel 0.5.0 booting
VMM preview ready; preserving Limine CR3
FractalOS kernel online score=0x0000000000000266
TripleKernel score=0x000000000000031b
```

## Patches Integrated

### Runtime

- Added `omega_tile_os.core.classic_os_bridge`.
- Added `classic-os-report`, `classic-os-capabilities` and `onboarding-pack` CLI commands.
- Added guest/user/admin/doctor session model.
- Added first-run onboarding tips for `intent-lens`, `proof-ribbon`, `energy-strip`, `agent-orbit` and `command-veil`.
- Added explicit capability tracking for desktop, internet, file formats, video, editing, EXE compatibility, package/runtime install and user sessions.

### Tests

- Added `tests/test_classic_os_bridge.py`.
- Test count increased from 130 to 133.

### Documentation

- Updated `README.md`.
- Updated `docs/GETTING_STARTED_FRACTALOS.md`.
- Updated `docs/CLASSIC_OS_CAPABILITY_MATRIX.md`.
- Added this re-audit report.

## Classic OS Capability Answers

| Question | Bare-metal today | Hosted/control-plane today | Honest answer |
|---|---|---|---|
| Desktop for office work | No | Partial | Kernel has framebuffer console + desktop-plane primitives; real office desktop still needs compositor/window manager/apps. |
| Internet/browser | No | Yes if host online | Hosted can use host internet; bare-metal needs NIC, TCP/IP, DNS, TLS and browser/container. |
| PNG/JPEG/TXT/PDF | No | Partial | Hosted can manipulate files; bare-metal needs VFS, file associations and viewers. |
| Video playback | No | Host dependent | Bare-metal has no audio/video stack or codecs yet. |
| Read/write/edit files | No | Yes via host tools | Bare-metal needs writable storage, VFS and editors. |
| `.exe` execution | No | Yes via Windows host | Bare-metal needs ELF first, then PE/Win32 through VM/domain compatibility. |
| Python/Rust/Java modules | No | Yes if host toolchains installed | Bare-metal needs package manager and runtime domains. |
| Intuitive onboarding | Partial | Yes | Docs and overlay tips exist; bare-metal tips need interactive first-run UI. |
| Sessions guest/user/admin | No | Modeled | Runtime now has role model; bare-metal needs auth/session isolation. |

## Incoherence Scan

The scan found mostly expected technical words in source and vendored tooling:

- `panic` in kernel panic paths;
- `error` and `fail` in Doctor/recovery/third-party Limine code;
- `unsafe` in VMM documentation explaining why CR3 takeover is disabled;
- historical generated workspace files containing failure-analysis questions.

No source-level contradiction was found that blocks build, tests, Doctor or QEMU boot.

## Remaining Warnings

Doctor still reports warnings:

- `performance`: conservative critical risk because live stability formula keeps protection mode.
- `formula-advice`: no safe expansion action while protection mode is active.
- `autonomy`: backlog remains queued.
- `gpu`: NVIDIA telemetry is visible, but native Python GPU backend is missing (`torch`/`cupy` not installed).

These are not build failures. They are guardrails.

## Missing Conversation Elements Now Integrated

- Classic desktop gap tracking.
- Internet/browser gap tracking.
- File extension and media roadmap.
- Read/write/edit document roadmap.
- EXE and runtime compatibility roadmap.
- Python/Rust/Java install roadmap.
- Onboarding overlay tips.
- Guest/user/admin/doctor session model.
- First-run commands.
- Runtime report archived to TileMindFS/OmegaRAM.

## Next Technical Gates

1. Add vector-specific exception handlers for page fault, GPF, invalid opcode and double fault.
2. Build a 4 KiB page table mapper before taking CR3 from Limine.
3. Add RAM disk VFS and first writable filesystem abstraction.
4. Add ring 3 transition and ELF loader.
5. Add init process and session manager.
6. Add compositor/window manager and file manager.
7. Add NIC/TCP/IP/browser domain.
8. Add package manager and runtime domains for Python/Rust/Java.
9. Add compatibility domain for `.exe` through VM/PE isolation.
10. Automate QEMU BIOS + UEFI screenshots and serial-log assertions in CI.
