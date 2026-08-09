#include "../include/fractal_kernel.h"

struct fk_interrupt_frame {
    uint64_t rip;
    uint64_t cs;
    uint64_t rflags;
    uint64_t rsp;
    uint64_t ss;
};

struct fk_syscall_request {
    uint64_t id;
    uint64_t arg0;
    uint64_t arg1;
    uint64_t arg2;
    uint64_t result;
    uint8_t armed;
};

static struct fk_boot_context *syscall_ctx = 0;
static volatile struct fk_syscall_request pending_request = {0};
static volatile uint64_t syscall_counter = 0;
static volatile uint64_t last_syscall = 0;

enum fk_syscall_id {
    FK_SYSCALL_PING = 1,
    FK_SYSCALL_TIMER_TICKS = 2,
    FK_SYSCALL_SCHEDULER_SCORE = 3,
    FK_SYSCALL_KEYBOARD_DEPTH = 4,
    FK_SYSCALL_TRIPLE_SCORE = 5,
    FK_SYSCALL_TASK_COUNT = 6,
    FK_SYSCALL_CURRENT_TASK = 7,
    FK_SYSCALL_USERSPACE_PROGRAMS = 8,
    FK_SYSCALL_USERSPACE_LAUNCHES = 9,
    FK_SYSCALL_REGIME_CURRENT = 10,
    FK_SYSCALL_SEMANTIC_PROMOTED = 11,
    FK_SYSCALL_UNIVERSE_LAW = 12,
    FK_SYSCALL_FIELD_FORCE = 13,
    FK_SYSCALL_ILLUSION_MODE = 14,
    FK_SYSCALL_CONTRADICTIONS = 15,
    FK_SYSCALL_FOUNDRY_BATCHES = 16,
    FK_SYSCALL_PROOF_LEVEL = 17,
    FK_SYSCALL_DESKTOP_LAYERS = 18,
    FK_SYSCALL_DESKTOP_OVERLAY = 19,
    FK_SYSCALL_FORMULA_COUNT = 20,
    FK_SYSCALL_FORMULA_ACTIVATION = 21,
    FK_SYSCALL_VFS_NODES = 22,
    FK_SYSCALL_VFS_OPEN_HOME = 23,
    FK_SYSCALL_PACKAGE_AVAILABLE = 24,
    FK_SYSCALL_PACKAGE_POLICY = 25,
    FK_SYSCALL_STORAGE_SLOTS = 26,
    FK_SYSCALL_STORAGE_JOURNAL = 27,
    FK_SYSCALL_STORAGE_SNAPSHOT = 28,
    FK_SYSCALL_STORAGE_SCORE = 29,
};

uint64_t fk_syscall_dispatch(uint64_t id, uint64_t arg0, uint64_t arg1, uint64_t arg2) {
    (void)arg0;
    (void)arg1;
    (void)arg2;
    switch (id) {
        case FK_SYSCALL_PING:
            return 0xF84C0A80ull;
        case FK_SYSCALL_TIMER_TICKS:
            return fk_timer_ticks();
        case FK_SYSCALL_SCHEDULER_SCORE:
            return fk_scheduler_score(syscall_ctx);
        case FK_SYSCALL_KEYBOARD_DEPTH:
            return fk_keyboard_buffered_keys();
        case FK_SYSCALL_TRIPLE_SCORE:
            return fk_triple_kernel_score();
        case FK_SYSCALL_TASK_COUNT:
            return fk_task_count();
        case FK_SYSCALL_CURRENT_TASK:
            return fk_task_current_id();
        case FK_SYSCALL_USERSPACE_PROGRAMS:
            return fk_userspace_program_count();
        case FK_SYSCALL_USERSPACE_LAUNCHES:
            return fk_userspace_launch_count();
        case FK_SYSCALL_REGIME_CURRENT:
            return fk_regime_current_id();
        case FK_SYSCALL_SEMANTIC_PROMOTED:
            return fk_semantic_memory_promoted_pages();
        case FK_SYSCALL_UNIVERSE_LAW:
            return fk_universe_current_law_id();
        case FK_SYSCALL_FIELD_FORCE:
            return fk_universe_field_force_level();
        case FK_SYSCALL_ILLUSION_MODE:
            return fk_illusion_mode_id();
        case FK_SYSCALL_CONTRADICTIONS:
            return fk_illusion_contradiction_count();
        case FK_SYSCALL_FOUNDRY_BATCHES:
            return fk_foundry_batch_count();
        case FK_SYSCALL_PROOF_LEVEL:
            return fk_proofstate_attestation_level();
        case FK_SYSCALL_DESKTOP_LAYERS:
            return fk_desktop_plane_layer_count();
        case FK_SYSCALL_DESKTOP_OVERLAY:
            return fk_desktop_plane_overlay_mode();
        case FK_SYSCALL_FORMULA_COUNT:
            return fk_scientific_formula_count();
        case FK_SYSCALL_FORMULA_ACTIVATION:
            return fk_scientific_formula_activation();
        case FK_SYSCALL_VFS_NODES:
            return fk_vfs_node_count();
        case FK_SYSCALL_VFS_OPEN_HOME:
            return fk_vfs_open_home_readme();
        case FK_SYSCALL_PACKAGE_AVAILABLE:
            return fk_package_available_count();
        case FK_SYSCALL_PACKAGE_POLICY:
            return fk_package_policy_score();
        case FK_SYSCALL_STORAGE_SLOTS:
            return fk_storage_plane_slot_count();
        case FK_SYSCALL_STORAGE_JOURNAL:
            return fk_storage_plane_journal_count();
        case FK_SYSCALL_STORAGE_SNAPSHOT:
            return fk_storage_plane_snapshot();
        case FK_SYSCALL_STORAGE_SCORE:
            return fk_storage_plane_persistence_score();
        default:
            return 0;
    }
}

__attribute__((interrupt))
void fk_syscall_irq(struct fk_interrupt_frame *frame) {
    (void)frame;
    if (!pending_request.armed) {
        return;
    }
    pending_request.result = fk_syscall_dispatch(
        pending_request.id,
        pending_request.arg0,
        pending_request.arg1,
        pending_request.arg2
    );
    syscall_counter += 1;
    last_syscall = pending_request.id;
    pending_request.armed = 0;
    if (syscall_ctx) {
        syscall_ctx->syscall_count = syscall_counter;
        syscall_ctx->last_syscall_id = last_syscall;
    }
}

void fk_syscall_init(struct fk_boot_context *ctx) {
    syscall_ctx = ctx;
    pending_request.id = 0;
    pending_request.arg0 = 0;
    pending_request.arg1 = 0;
    pending_request.arg2 = 0;
    pending_request.result = 0;
    pending_request.armed = 0;
    syscall_counter = 0;
    last_syscall = 0;
    if (ctx) {
        ctx->syscall_ready = 1;
        ctx->syscall_count = 0;
        ctx->last_syscall_id = 0;
    }
}

uint64_t fk_syscall_count(void) {
    return syscall_counter;
}

uint64_t fk_syscall_last_id(void) {
    return last_syscall;
}

uint64_t fk_syscall_invoke(uint64_t id, uint64_t arg0, uint64_t arg1, uint64_t arg2) {
    pending_request.id = id;
    pending_request.arg0 = arg0;
    pending_request.arg1 = arg1;
    pending_request.arg2 = arg2;
    pending_request.result = 0;
    pending_request.armed = 1;
    __asm__ volatile ("int $0x80" : : : "memory");
    return pending_request.result;
}

void fk_syscall_report(void) {
    fk_serial_write("Syscall gate count=");
    fk_serial_write_hex64(fk_syscall_count());
    fk_serial_write(" last_id=");
    fk_serial_write_hex64(fk_syscall_last_id());
    fk_serial_write("\n");
}
