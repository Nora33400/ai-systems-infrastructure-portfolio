# FractalOS Boot Audit - 2026-04-25

## Result

FractalOS now builds a bootable ISO and reaches the bare-metal kernel in QEMU.

Validated artifacts:

- ISO: `<FRACTALOS_WORKSPACE>\build\FractalOS.iso`
- Kernel: `<FRACTALOS_WORKSPACE>\bare_metal\build\fractal_kernel.elf`
- BIOS screenshot: `<FRACTALOS_WORKSPACE>\workspace\vm_validation\qemu_boot_vmmpreview_screendump.bmp`
- UEFI screenshot: `<FRACTALOS_WORKSPACE>\workspace\vm_validation\qemu_boot_uefi3_screendump.bmp`
- BIOS serial log: `<FRACTALOS_WORKSPACE>\qemu_kernel_root_serial.log`
- UEFI serial log: `<FRACTALOS_WORKSPACE>\qemu_uefi3_serial.log`

## Fixes applied

1. Tool discovery was expanded to find installed tools outside PATH:

- `C:\Program Files\qemu\qemu-system-x86_64.exe`
- `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe`
- `C:\Program Files\LLVM\bin\clang.exe`
- `C:\Program Files\LLVM\bin\ld.lld.exe`
- `C:\Program Files\LLVM\bin\lld-link.exe`

2. ISO generation was stabilized without `xorriso` or `oscdimg`:

- `pycdlib` builds the ISO.
- Limine BIOS install is applied.
- BIOS and UEFI El Torito entries are staged.
- Limine files are copied to root, `/boot`, `/limine` and `/boot/limine`.

3. Limine request ABI was corrected:

- Common request magic is present in request IDs.
- Modern Limine start marker is used.
- `limine.conf` uses current syntax.

4. Early interrupt stability was improved:

- `_start` now executes `cli` before stack handoff.
- PIC remap no longer inherits firmware masks.
- Only IRQ0 and IRQ1 are unmasked during early boot.

5. Kernel compiler flags were hardened:

- `-mgeneral-regs-only`
- `-mno-mmx`
- `-mno-sse`
- `-mno-sse2`

This prevents invalid opcode exceptions before FPU/SSE state is initialized.

6. VMM takeover was made safe:

- The prototype VMM keeps Limine CR3 for now.
- It does not switch to incomplete 2 MiB bootstrap page tables.
- This avoids page faults caused by non-2MiB-aligned kernel placement and framebuffer mappings.

## Current verification

- Unit tests: 130 passed.
- Build report: `bootable_iso_ready=true`, `qemu_ready=true`, `virtualbox_ready=true`.
- QEMU BIOS: kernel reaches `TripleKernel score=0x000000000000031b`.
- QEMU UEFI: kernel reaches `TripleKernel score=0x000000000000031b` after OVMF/Limine key prompt.
- Doctor: 0 failures, warnings only.
- Restart recovery: scanned 47 modules, 0 failed, 0 rollbacks.

## Doctor warnings that remain

- `performance`: risk stays `critical` because the conservative governor detects pressure/uncertainty and keeps protect mode.
- `autonomy`: 69 queued autonomy items remain, by design; this is backlog, not corruption.
- `gpu`: native Python GPU backend is not installed (`torch_not_installed`, `cupy_not_installed`) even though NVIDIA devices are visible through telemetry.
- `formula-advice`: warning after tuning because the safest action is to keep protection instead of starting more work.

## Hardware and corpus status

- Motherboard detected: `ASUSTeK COMPUTER INC. TUF GAMING B550-PLUS WIFI II`.
- GPU telemetry sees `NVIDIA GeForce RTX 3060` and `NVIDIA GeForce RTX 4060`.
- Corpus index coverage: `14996/14996` files from `<FORMULA_CORPUS>`.
- Formula/equation count indexed: `1499600`.

## Honest limits

- Physical USB boot has not been tested.
- Native UEFI boot works in QEMU after a Limine/OVMF prompt, but should be refined.
- Bare-metal does not yet include storage drivers, native filesystem, network stack, browser, media, office apps or user sessions.
- VMM is currently a safe preview, not a full CR3-owning kernel memory manager.

## Next engineering gates

1. Build a real 4 KiB page table mapper before taking over CR3.
2. Add page fault and exception handlers with vector-specific serial logs.
3. Add APIC/HPET path after PIC stability.
4. Add VFS + RAM disk before persistent disk write support.
5. Add ELF userspace loader and ring 3 transition.
6. Add first graphical desktop shell as a user program.
7. Add network stack and browser/container strategy.
