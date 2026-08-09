from __future__ import annotations

import unittest
from pathlib import Path


class BareMetalKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / "bare_metal"

    def test_bare_metal_kernel_sources_exist(self) -> None:
        required = [
            "README.md",
            "TOOLCHAIN.md",
            "kernel/fractal_kernel.c",
            "kernel/boot.S",
            "kernel/include/fractal_kernel.h",
            "kernel/arch/x86_64/serial.c",
            "kernel/arch/x86_64/gdt.c",
            "kernel/arch/x86_64/idt.c",
            "kernel/arch/x86_64/pic.c",
            "kernel/arch/x86_64/keyboard.c",
            "kernel/arch/x86_64/timer.c",
            "kernel/core/syscall.c",
            "kernel/core/console.c",
            "kernel/core/task.c",
            "kernel/core/userspace.c",
            "kernel/core/regime.c",
            "kernel/core/semantic_memory.c",
            "kernel/core/universe.c",
            "kernel/core/illusion.c",
            "kernel/core/foundry.c",
            "kernel/core/proofstate.c",
            "kernel/core/desktop_plane.c",
            "kernel/core/scientific_formula.c",
            "kernel/core/vfs.c",
            "kernel/core/package.c",
            "kernel/core/storage_plane.c",
            "kernel/core/pmm.c",
            "kernel/core/heap.c",
            "kernel/core/slab.c",
            "kernel/core/vmm.c",
            "kernel/core/scheduler.c",
            "kernel/core/triple_kernel.c",
            "kernel/linker.ld",
            "limine/limine.conf",
            "Makefile",
            "build.ps1",
        ]
        for rel in required:
            self.assertTrue((self.root / rel).exists(), rel)

    def test_kernel_uses_limine_framebuffer_and_halts(self) -> None:
        source = (self.root / "kernel" / "fractal_kernel.c").read_text(encoding="utf-8")
        triple = (self.root / "kernel" / "core" / "triple_kernel.c").read_text(encoding="utf-8")
        self.assertIn("limine_framebuffer_request", source)
        self.assertIn("fractal_kernel_main", source)
        self.assertIn("fk_gdt_init", source)
        self.assertIn("fk_idt_init", source)
        self.assertIn("fk_pic_init", source)
        self.assertIn("fk_serial_init", source)
        self.assertIn("fk_timer_init", source)
        self.assertIn("memmap_request", source)
        self.assertIn("fk_pmm_init", source)
        self.assertIn("fk_pmm_report", source)
        self.assertIn("fk_pmm_alloc_frame", source)
        self.assertIn("fk_pmm_free_frame", source)
        self.assertIn("fk_heap_init", source)
        self.assertIn("fk_heap_alloc", source)
        self.assertIn("fk_heap_report", source)
        self.assertIn("fk_slab_init", source)
        self.assertIn("fk_slab_alloc", source)
        self.assertIn("fk_slab_report", source)
        self.assertIn("kernel_address_request", source)
        self.assertIn("fk_vmm_init", source)
        self.assertIn("fk_vmm_report", source)
        self.assertIn("fk_keyboard_init", source)
        self.assertIn("fk_keyboard_report", source)
        self.assertIn("fk_syscall_init", source)
        self.assertIn("fk_syscall_invoke", source)
        self.assertIn("fk_syscall_report", source)
        self.assertIn("fk_console_init", source)
        self.assertIn("fk_console_write", source)
        self.assertIn("fk_console_report", source)
        self.assertIn("fk_task_init", source)
        self.assertIn("fk_task_spawn_kernel", source)
        self.assertIn("fk_task_report", source)
        self.assertIn("fk_userspace_init", source)
        self.assertIn("fk_userspace_report", source)
        self.assertIn("fk_regime_init", source)
        self.assertIn("fk_regime_report", source)
        self.assertIn("fk_semantic_memory_init", source)
        self.assertIn("fk_semantic_memory_report", source)
        self.assertIn("fk_universe_init", source)
        self.assertIn("fk_universe_report", source)
        self.assertIn("fk_illusion_init", source)
        self.assertIn("fk_illusion_report", source)
        self.assertIn("fk_foundry_init", source)
        self.assertIn("fk_foundry_report", source)
        self.assertIn("fk_proofstate_init", source)
        self.assertIn("fk_proofstate_report", source)
        self.assertIn("fk_desktop_plane_init", source)
        self.assertIn("fk_desktop_plane_report", source)
        self.assertIn("fk_scientific_formula_init", source)
        self.assertIn("fk_scientific_formula_report", source)
        self.assertIn("fk_vfs_init", source)
        self.assertIn("fk_vfs_report", source)
        self.assertIn("fk_package_init", source)
        self.assertIn("fk_package_report", source)
        self.assertIn("Type: help", source)
        self.assertIn("sti", source)
        self.assertIn("fk_triple_kernel_init", source)
        self.assertIn("fk_triple_kernel_report", source)
        self.assertIn("hlt", source)
        self.assertIn("fk_triple_kernel_bridges", triple)
        self.assertIn("strength", triple)

    def test_linker_defines_kernel_entry(self) -> None:
        linker = (self.root / "kernel" / "linker.ld").read_text(encoding="utf-8")
        boot = (self.root / "kernel" / "boot.S").read_text(encoding="utf-8")
        self.assertIn("ENTRY(_start)", linker)
        self.assertIn(".global _start", boot)

    def test_build_scripts_include_kernel_subsystems(self) -> None:
        makefile = (self.root / "Makefile").read_text(encoding="utf-8")
        build_ps1 = (self.root / "build.ps1").read_text(encoding="utf-8")
        for needle in ["serial.c", "gdt.c", "idt.c", "pic.c", "keyboard.c", "timer.c", "syscall.c", "console.c", "task.c", "userspace.c", "regime.c", "semantic_memory.c", "universe.c", "illusion.c", "foundry.c", "proofstate.c", "desktop_plane.c", "scientific_formula.c", "vfs.c", "package.c", "storage_plane.c", "pmm.c", "heap.c", "slab.c", "vmm.c", "scheduler.c", "triple_kernel.c"]:
            self.assertIn(needle, makefile)
            self.assertIn(needle, build_ps1)

    def test_pmm_exposes_frame_allocator_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        pmm = (self.root / "kernel" / "core" / "pmm.c").read_text(encoding="utf-8")
        self.assertIn("FK_PAGE_SIZE", header)
        self.assertIn("fk_pmm_alloc_frame", header)
        self.assertIn("fk_pmm_free_frame", header)
        self.assertIn("pmm_frame_stack", pmm)
        self.assertIn("FK_PMM_MAX_FRAMES", pmm)

    def test_heap_exposes_bootstrap_allocator_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        heap = (self.root / "kernel" / "core" / "heap.c").read_text(encoding="utf-8")
        self.assertIn("fk_heap_init", header)
        self.assertIn("fk_heap_alloc", header)
        self.assertIn("fk_heap_free", header)
        self.assertIn("heap_arena", heap)
        self.assertIn("FK_HEAP_BOOTSTRAP_RESERVE_FRAMES", heap)

    def test_slab_exposes_object_cache_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        slab = (self.root / "kernel" / "core" / "slab.c").read_text(encoding="utf-8")
        self.assertIn("fk_slab_init", header)
        self.assertIn("fk_slab_alloc", header)
        self.assertIn("fk_slab_free", header)
        self.assertIn("FK_SLAB_CLASS_COUNT", slab)
        self.assertIn("slab_classes", slab)

    def test_vmm_exposes_bootstrap_paging_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        vmm = (self.root / "kernel" / "core" / "vmm.c").read_text(encoding="utf-8")
        self.assertIn("fk_vmm_init", header)
        self.assertIn("fk_vmm_mapped_bytes", header)
        self.assertIn("pml4", vmm)
        self.assertIn("preserving Limine CR3", vmm)

    def test_keyboard_exposes_irq_buffer_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        keyboard = (self.root / "kernel" / "arch" / "x86_64" / "keyboard.c").read_text(encoding="utf-8")
        idt = (self.root / "kernel" / "arch" / "x86_64" / "idt.c").read_text(encoding="utf-8")
        self.assertIn("fk_keyboard_init", header)
        self.assertIn("fk_keyboard_pop_char", header)
        self.assertIn("FK_KEYBOARD_BUFFER_CAPACITY", keyboard)
        self.assertIn("fk_keyboard_irq", keyboard)
        self.assertIn("set_gate(33", idt)

    def test_syscall_gate_exposes_interrupt_dispatch_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        idt = (self.root / "kernel" / "arch" / "x86_64" / "idt.c").read_text(encoding="utf-8")
        self.assertIn("fk_syscall_init", header)
        self.assertIn("fk_syscall_invoke", header)
        self.assertIn("fk_syscall_dispatch", header)
        self.assertIn("fk_syscall_irq", syscall)
        self.assertIn("int $0x80", syscall)
        self.assertIn("FK_SYSCALL_SCHEDULER_SCORE", syscall)
        self.assertIn("set_gate_with_attr(128", idt)

    def test_console_surface_exposes_framebuffer_terminal_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        console = (self.root / "kernel" / "core" / "console.c").read_text(encoding="utf-8")
        self.assertIn("fk_console_init", header)
        self.assertIn("fk_console_write", header)
        self.assertIn("fk_console_tick", header)
        self.assertIn("fk_console_report", header)
        self.assertIn("FK_CONSOLE_CELL_W", console)
        self.assertIn("console_put_char", console)
        self.assertIn("fk_keyboard_pop_char", console)
        self.assertIn("shell_execute", console)
        self.assertIn("help tasks syscalls score clear ping apps launch-echo regimes regime-latency memory-map promote-page universe universe-chaos universe-evolution shadow shadow-shift contradict foundry foundry-batch proofs prove-state desktop overlay overlay-cycle formulas formula-storage vfs vfs-open packages package-policy storage storage-snapshot", console)
        self.assertIn("launch-echo", console)
        self.assertIn("regime-latency", console)
        self.assertIn("promote-page", console)
        self.assertIn("universe-chaos", console)
        self.assertIn("shadow-shift", console)
        self.assertIn("contradict", console)
        self.assertIn("foundry-batch", console)
        self.assertIn("prove-state", console)
        self.assertIn("overlay-cycle", console)
        self.assertIn("formula-storage", console)
        self.assertIn("shell_vfs", console)
        self.assertIn("shell_packages", console)

    def test_task_model_exposes_kernel_task_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        task = (self.root / "kernel" / "core" / "task.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_task_init", header)
        self.assertIn("fk_task_spawn_kernel", header)
        self.assertIn("fk_task_set_current", header)
        self.assertIn("FK_TASK_MAX", task)
        self.assertIn("task_table", task)
        self.assertIn("FK_SYSCALL_TASK_COUNT", syscall)

    def test_userspace_loader_exposes_program_registry_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        userspace = (self.root / "kernel" / "core" / "userspace.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_userspace_init", header)
        self.assertIn("fk_userspace_launch_by_name", header)
        self.assertIn("FK_USERSPACE_MAX_PROGRAMS", userspace)
        self.assertIn("register_program", userspace)
        self.assertIn("echo", userspace)
        self.assertIn("init", userspace)
        self.assertIn("packages", userspace)
        self.assertIn("FK_SYSCALL_USERSPACE_PROGRAMS", syscall)

    def test_regime_and_semantic_memory_expose_physical_interpreter_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        regime = (self.root / "kernel" / "core" / "regime.c").read_text(encoding="utf-8")
        semantic = (self.root / "kernel" / "core" / "semantic_memory.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_regime_init", header)
        self.assertIn("fk_semantic_memory_init", header)
        self.assertIn("FK_REGIME_MAX", regime)
        self.assertIn("latency", regime)
        self.assertIn("FK_SEMANTIC_CLASS_COUNT", semantic)
        self.assertIn("fk_semantic_memory_promote_pages", semantic)
        self.assertIn("FK_SYSCALL_REGIME_CURRENT", syscall)

    def test_universe_laws_expose_programmable_field_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        universe = (self.root / "kernel" / "core" / "universe.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_universe_init", header)
        self.assertIn("fk_universe_select_law", header)
        self.assertIn("FK_UNIVERSE_LAW_MAX", universe)
        self.assertIn("chaos", universe)
        self.assertIn("evolution", universe)
        self.assertIn("FK_SYSCALL_UNIVERSE_LAW", syscall)

    def test_illusion_layer_exposes_shadow_dimension_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        illusion = (self.root / "kernel" / "core" / "illusion.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_illusion_init", header)
        self.assertIn("fk_illusion_shift_mode", header)
        self.assertIn("FK_ILLUSION_MODE_MAX", illusion)
        self.assertIn("shadowed", illusion)
        self.assertIn("fk_illusion_raise_contradiction", illusion)
        self.assertIn("FK_SYSCALL_ILLUSION_MODE", syscall)

    def test_foundry_and_proofstate_expose_industrial_kernel_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        foundry = (self.root / "kernel" / "core" / "foundry.c").read_text(encoding="utf-8")
        proofstate = (self.root / "kernel" / "core" / "proofstate.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_foundry_init", header)
        self.assertIn("fk_foundry_run_batch", header)
        self.assertIn("FK_FOUNDRY_LINE_MAX", foundry)
        self.assertIn("formalize", foundry)
        self.assertIn("fk_proofstate_init", header)
        self.assertIn("fk_proofstate_promote", header)
        self.assertIn("proof_attestation_level", proofstate)
        self.assertIn("FK_SYSCALL_FOUNDRY_BATCHES", syscall)
        self.assertIn("FK_SYSCALL_PROOF_LEVEL", syscall)

    def test_desktop_plane_exposes_persistent_overlay_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        desktop = (self.root / "kernel" / "core" / "desktop_plane.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_desktop_plane_init", header)
        self.assertIn("fk_desktop_plane_cycle_overlay", header)
        self.assertIn("FK_DESKTOP_LAYER_MAX", desktop)
        self.assertIn("login-greeter", desktop)
        self.assertIn("start-menu", desktop)
        self.assertIn("global-search", desktop)
        self.assertIn("tile-explorer", desktop)
        self.assertIn("package-center", desktop)
        self.assertIn("agent-overlay", desktop)
        self.assertIn("command-veil", desktop)
        self.assertIn("FK_SYSCALL_DESKTOP_LAYERS", syscall)
        self.assertIn("FK_SYSCALL_DESKTOP_OVERLAY", syscall)

    def test_scientific_formula_plane_exposes_hardware_formula_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        formula = (self.root / "kernel" / "core" / "scientific_formula.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_scientific_formula_init", header)
        self.assertIn("fk_scientific_formula_boost_storage", header)
        self.assertIn("FK_SCIENTIFIC_FORMULA_MAX", formula)
        self.assertIn("entropy-tile-density", formula)
        self.assertIn("thermal-throughput-envelope", formula)
        self.assertIn("FK_SYSCALL_FORMULA_COUNT", syscall)
        self.assertIn("FK_SYSCALL_FORMULA_ACTIVATION", syscall)

    def test_vfs_and_package_planes_expose_userspace_alpha_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        vfs = (self.root / "kernel" / "core" / "vfs.c").read_text(encoding="utf-8")
        package = (self.root / "kernel" / "core" / "package.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        self.assertIn("fk_vfs_init", header)
        self.assertIn("fk_vfs_open_home_readme", header)
        self.assertIn("FK_VFS_NODE_MAX", vfs)
        self.assertIn("/apps/packages.json", vfs)
        self.assertIn("fk_package_init", header)
        self.assertIn("runtime.python", package)
        self.assertIn("browser.firefox-domain", package)
        self.assertIn("FK_SYSCALL_VFS_NODES", syscall)
        self.assertIn("FK_SYSCALL_PACKAGE_AVAILABLE", syscall)

    def test_storage_plane_exposes_persistent_vfs_journal_api(self) -> None:
        header = (self.root / "kernel" / "include" / "fractal_kernel.h").read_text(encoding="utf-8")
        storage = (self.root / "kernel" / "core" / "storage_plane.c").read_text(encoding="utf-8")
        syscall = (self.root / "kernel" / "core" / "syscall.c").read_text(encoding="utf-8")
        console = (self.root / "kernel" / "core" / "console.c").read_text(encoding="utf-8")
        source = (self.root / "kernel" / "fractal_kernel.c").read_text(encoding="utf-8")
        self.assertIn("fk_storage_plane_init", header)
        self.assertIn("fk_storage_plane_snapshot", header)
        self.assertIn("fk_storage_plane_persistence_score", header)
        self.assertIn("StorageVFS", storage)
        self.assertIn("fk_storage_plane_report", storage)
        self.assertIn("FK_SYSCALL_STORAGE_SLOTS", syscall)
        self.assertIn("FK_SYSCALL_STORAGE_SNAPSHOT", syscall)
        self.assertIn("shell_storage", console)
        self.assertIn("Storage VFS plane online", source)


if __name__ == "__main__":
    unittest.main()
