# FractalOS Bare Metal

This directory is the real OS track: a bootable x86_64 kernel skeleton, separate
from the Python host tools used to plan, test, and build the ecosystem.

## Goal

FractalOS is intended to become a real operating system with:

- a small x86_64 kernel entry point;
- framebuffer text output;
- interrupt and memory subsystems added incrementally;
- a userspace/agent bridge later, not inside the first kernel;
- host-side builders that can produce an ISO safely.

## Current Stage

Stage 20 extends the bare-metal line into a first scientific formula hardware plane:

- `kernel/fractal_kernel.c`: freestanding kernel entry point;
- `kernel/boot.S`: stack setup and `_start` handoff;
- `kernel/arch/x86_64/serial.c`: COM1 serial logging;
- `kernel/arch/x86_64/gdt.c`: minimal 64-bit GDT;
- `kernel/arch/x86_64/idt.c`: minimal IDT loading;
- `kernel/arch/x86_64/pic.c`: PIC remap and IRQ acknowledge path;
- `kernel/arch/x86_64/timer.c`: PIT heartbeat and IRQ0 counter;
- `kernel/arch/x86_64/keyboard.c`: PS/2 keyboard IRQ1 buffering and basic ASCII translation;
- `kernel/core/syscall.c`: `int 0x80` syscall gate with bounded dispatch telemetry;
- `kernel/core/console.c`: framebuffer-backed console surface fed by keyboard input;
- `kernel/core/task.c`: bounded kernel task table with current-task selection;
- shell commands: `help`, `tasks`, `syscalls`, `score`, `clear`, `ping`;
- `kernel/core/userspace.c`: first bounded userspace program registry and launch lane;
- `kernel/core/regime.c`: hardware execution regimes as first-class scheduler modes;
- `kernel/core/semantic_memory.c`: first semantic memory layer with promoted pages;
- `kernel/core/universe.c`: local laws of execution and field-force intensity;
- `kernel/core/illusion.c`: shadow dimension, projection modes and contradictions;
- `kernel/core/foundry.c`: bounded local software foundry lines and batch counters;
- `kernel/core/proofstate.c`: bounded attestation level and state promotion counters;
- `kernel/core/desktop_plane.c`: persistent desktop layers above apps and command surfaces;
- `kernel/core/scientific_formula.c`: bounded hardware formulas for storage, RAM, thermal and proof lanes;
- `kernel/core/pmm.c`: first physical memory manager census from bootloader memory map;
- `kernel/core/heap.c`: bootstrap heap backed by reserved PMM frames and a bounded arena;
- `kernel/core/slab.c`: fixed-size slab classes for frequent kernel objects;
- `kernel/core/vmm.c`: bootstrap page-table preview while preserving Limine CR3 for safe first boot;
- bounded 4 KiB frame stack allocation for early kernel growth;
- `kernel/core/scheduler.c`: first deterministic kernel scheduler score;
- `kernel/core/triple_kernel.c`: triangle topology for Matter/Mind/Mesh kernel vertices;
- `kernel/linker.ld`: higher-half linker script;
- `limine/limine.conf`: boot menu;
- `build.ps1`: guarded builder script;
- `fetch_limine.ps1`: fetch official Limine binary branch for staging;
- `stage_iso.ps1`: prepare an ISO root with kernel + Limine assets;
- `Makefile`: Linux-like build entry.

The current kernel is intentionally tiny but real: it boots, initializes serial,
loads GDT/IDT, remaps the PIC, arms a PIT heartbeat, reads the bootloader memory
map into a first PMM census, computes a Triple Kernel topology, clears the
screen through the Limine framebuffer protocol, draws a deterministic triangle
sigil, emits serial telemetry, and idles safely with interrupts enabled.
The allocators are still intentionally simple and bounded, but the kernel can
now reserve/release early physical frames, expose a bootstrap heap, serve small
fixed-size kernel objects through slab classes, prepare a safe VMM preview while
preserving Limine's proven boot mappings, receive first keyboard input through
IRQ1, route a first software interrupt syscall gate through vector `0x80`,
paint a live framebuffer console that drains typed characters during idle,
maintain a first bounded kernel task model for boot/console services, parse a
first local shell command line, expose a bounded userspace loader foundation,
start interpreting hardware through execution regimes plus semantic memory, let
the kernel switch between programmable local laws, maintain a first shadow
dimension with controlled contradictions, and host a first local software
foundry plus proof-oriented promotion lane. It also exposes a first desktop
plane with persistent overlay layers for intent, agents, proofs and commands.
The kernel now carries a scientific formula plane for reversible hardware-aware
policies such as entropy tile density, thermal throughput envelopes and
proof-gated promotion.
Real CR3 takeover, privilege transitions and ELF loading come next.

## Toolchain

You need a cross compiler or compatible local compiler:

- `x86_64-elf-gcc` or clang targeting `x86_64-elf`;
- `nasm` or GNU assembler support;
- Limine bootloader files for ISO creation;
- `pycdlib` for the current ISO generation path.

The host Python FractalOS can generate plans and verify source files, but it does
not fake a kernel. The files here are the beginning of the real kernel.
