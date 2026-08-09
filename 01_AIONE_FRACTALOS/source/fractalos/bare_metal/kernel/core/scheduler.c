#include "../include/fractal_kernel.h"

void fk_scheduler_init(struct fk_boot_context *ctx) {
    if (!ctx) {
        return;
    }
    ctx->scheduler_ready = 1;
}

uint64_t fk_scheduler_score(const struct fk_boot_context *ctx) {
    if (!ctx) {
        return 0;
    }
    uint64_t score = 0;
    score += ctx->serial_ready ? 17 : 0;
    score += ctx->gdt_ready ? 23 : 0;
    score += ctx->idt_ready ? 19 : 0;
    score += ctx->pic_ready ? 11 : 0;
    score += ctx->timer_ready ? 17 : 0;
    score += ctx->pmm_ready ? 19 : 0;
    score += ctx->interrupts_enabled ? 13 : 0;
    score += ctx->scheduler_ready ? 29 : 0;
    score += ctx->usable_memory_bytes > (64ull * 1024ull * 1024ull) ? 11 : 0;
    score += ctx->free_frame_count > 1024 ? 13 : ctx->free_frame_count > 0 ? 7 : 0;
    score += ctx->heap_capacity_bytes >= (32ull * 1024ull) ? 13 : ctx->heap_capacity_bytes > 0 ? 7 : 0;
    score += ctx->heap_reserved_frames > 0 ? 11 : 0;
    score += ctx->slab_classes_ready >= 4 ? 11 : ctx->slab_classes_ready > 0 ? 5 : 0;
    score += ctx->slab_live_objects >= 1 ? 7 : 0;
    score += ctx->vmm_ready ? 17 : 0;
    score += ctx->vmm_mapped_bytes >= (2ull * 1024ull * 1024ull * 1024ull) ? 13 : ctx->vmm_mapped_bytes > 0 ? 7 : 0;
    score += ctx->keyboard_ready ? 13 : 0;
    score += ctx->keyboard_buffered_keys > 0 ? 7 : 0;
    score += ctx->syscall_ready ? 17 : 0;
    score += ctx->syscall_count > 0 ? 11 : 0;
    score += ctx->console_ready ? 19 : 0;
    score += ctx->console_written_chars > 0 ? 11 : 0;
    score += ctx->task_ready ? 19 : 0;
    score += ctx->task_count >= 2 ? 13 : ctx->task_count == 1 ? 7 : 0;
    score += ctx->userspace_ready ? 19 : 0;
    score += ctx->userspace_program_count >= 4 ? 13 : ctx->userspace_program_count > 0 ? 7 : 0;
    score += ctx->userspace_launch_count > 0 ? 11 : 0;
    score += ctx->regime_ready ? 19 : 0;
    score += ctx->current_regime_id == 1 || ctx->current_regime_id == 2 ? 11 : ctx->current_regime_id > 0 ? 7 : 0;
    score += ctx->semantic_memory_ready ? 19 : 0;
    score += ctx->semantic_promoted_pages > 0 ? 11 : 0;
    score += ctx->universe_ready ? 19 : 0;
    score += ctx->current_universe_law_id == 2 || ctx->current_universe_law_id == 4 ? 13 : ctx->current_universe_law_id > 0 ? 7 : 0;
    score += ctx->field_force_level >= 7 ? 11 : ctx->field_force_level > 0 ? 5 : 0;
    score += ctx->illusion_ready ? 17 : 0;
    score += ctx->shadow_dimension_depth >= 2 ? 11 : ctx->shadow_dimension_depth > 0 ? 5 : 0;
    score += ctx->contradiction_count > 0 ? 7 : 0;
    score += ctx->foundry_ready ? 17 : 0;
    score += ctx->foundry_batch_count > 0 ? 11 : 0;
    score += ctx->proof_ready ? 17 : 0;
    score += ctx->proof_attestation_level >= 3 ? 11 : ctx->proof_attestation_level > 0 ? 5 : 0;
    score += ctx->proof_promotion_count > 0 ? 7 : 0;
    score += ctx->desktop_ready ? 19 : 0;
    score += ctx->desktop_layer_count >= 5 ? 13 : ctx->desktop_layer_count > 0 ? 7 : 0;
    score += ctx->desktop_persistent_panels >= 3 ? 11 : ctx->desktop_persistent_panels > 0 ? 5 : 0;
    score += ctx->scientific_formula_ready ? 19 : 0;
    score += ctx->scientific_formula_activation >= 650 ? 13 : ctx->scientific_formula_activation > 0 ? 7 : 0;
    score += ctx->scientific_formula_safety >= 850 ? 13 : ctx->scientific_formula_safety > 0 ? 5 : 0;
    score += ctx->framebuffer_width > 0 ? 7 : 0;
    score += ctx->framebuffer_height > 0 ? 5 : 0;
    return score;
}
