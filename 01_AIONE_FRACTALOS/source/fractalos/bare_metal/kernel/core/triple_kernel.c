#include "../include/fractal_kernel.h"

static struct fk_kernel_vertex vertices[3] = {
    {
        .id = FK_VERTEX_MATTER,
        .name = "Matter",
        .purpose = "bare-metal CPU, memory, interrupts, devices",
        .readiness = 0,
    },
    {
        .id = FK_VERTEX_MIND,
        .name = "Mind",
        .purpose = "agent scheduling, formulas, proof gates, local intelligence",
        .readiness = 0,
    },
    {
        .id = FK_VERTEX_MESH,
        .name = "Mesh",
        .purpose = "storage, distributed missions, service topology",
        .readiness = 0,
    },
};

static struct fk_kernel_bridge bridges[3] = {
    { .left = FK_VERTEX_MATTER, .right = FK_VERTEX_MIND, .strength = 0 },
    { .left = FK_VERTEX_MIND, .right = FK_VERTEX_MESH, .strength = 0 },
    { .left = FK_VERTEX_MESH, .right = FK_VERTEX_MATTER, .strength = 0 },
};

static uint64_t average_u64(uint64_t left, uint64_t right) {
    return (left + right) / 2;
}

void fk_triple_kernel_init(struct fk_boot_context *ctx) {
    if (!ctx) {
        return;
    }

    vertices[FK_VERTEX_MATTER].readiness = 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->gdt_ready ? 21 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->idt_ready ? 21 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->pic_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->timer_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->pmm_ready ? 21 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->free_frame_count > 0 ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->heap_reserved_frames > 0 ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->vmm_ready ? 21 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->syscall_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->console_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->task_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->userspace_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->regime_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->semantic_memory_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->universe_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->illusion_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->foundry_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->proof_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->desktop_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->scientific_formula_ready ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->framebuffer_width > 0 ? 13 : 0;
    vertices[FK_VERTEX_MATTER].readiness += ctx->serial_ready ? 8 : 0;

    vertices[FK_VERTEX_MIND].readiness = 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->scheduler_ready ? 34 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->interrupts_enabled ? 21 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->timer_ready ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->heap_capacity_bytes >= (32ull * 1024ull) ? 21 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->slab_classes_ready >= 4 ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->vmm_mapped_bytes > 0 ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->keyboard_buffered_keys > 0 ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->syscall_count > 0 ? 21 : ctx->syscall_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->console_written_chars > 0 ? 13 : ctx->console_ready ? 5 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->task_count >= 2 ? 21 : ctx->task_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->userspace_program_count >= 4 ? 21 : ctx->userspace_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->current_regime_id == 3 ? 21 : ctx->regime_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->semantic_page_classes >= 5 ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->current_universe_law_id == 3 || ctx->current_universe_law_id == 4 ? 21 : ctx->universe_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->illusion_mode_id == 2 || ctx->illusion_mode_id == 3 ? 21 : ctx->illusion_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->foundry_batch_count > 0 ? 21 : ctx->foundry_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->proof_attestation_level >= 3 ? 21 : ctx->proof_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->desktop_overlay_mode_id > 1 ? 21 : ctx->desktop_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->scientific_formula_activation >= 650 ? 21 : ctx->scientific_formula_ready ? 8 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->serial_ready ? 13 : 0;
    vertices[FK_VERTEX_MIND].readiness += ctx->framebuffer_height > 0 ? 8 : 0;

    vertices[FK_VERTEX_MESH].readiness = 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->serial_ready ? 21 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->interrupts_enabled ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->usable_memory_bytes > 0 ? 21 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->free_frame_count > 512 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->heap_capacity_bytes > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->slab_live_objects > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->kernel_virtual_base != 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->keyboard_ready ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->last_syscall_id > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->console_columns > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->current_task_id > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->userspace_last_program_id > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->current_regime_id == 4 || ctx->current_regime_id == 5 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->semantic_promoted_pages > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->field_force_level >= 7 ? 13 : ctx->universe_ready ? 8 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->contradiction_count > 0 ? 13 : ctx->shadow_dimension_depth > 0 ? 8 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->foundry_line_count >= 4 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->proof_promotion_count > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->desktop_persistent_panels >= 3 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->scientific_formula_safety >= 850 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->framebuffer_pitch > 0 ? 13 : 0;
    vertices[FK_VERTEX_MESH].readiness += ctx->scheduler_ready ? 13 : 0;

    bridges[0].strength = average_u64(vertices[FK_VERTEX_MATTER].readiness, vertices[FK_VERTEX_MIND].readiness);
    bridges[1].strength = average_u64(vertices[FK_VERTEX_MIND].readiness, vertices[FK_VERTEX_MESH].readiness);
    bridges[2].strength = average_u64(vertices[FK_VERTEX_MESH].readiness, vertices[FK_VERTEX_MATTER].readiness);

    ctx->triple_kernel_ready = 1;
}

uint64_t fk_triple_kernel_score(void) {
    uint64_t score = 0;
    for (uint64_t i = 0; i < 3; i++) {
        score += vertices[i].readiness;
    }
    return score;
}

const struct fk_kernel_vertex *fk_triple_kernel_vertices(void) {
    return vertices;
}

uint64_t fk_triple_kernel_vertex_count(void) {
    return 3;
}

const struct fk_kernel_bridge *fk_triple_kernel_bridges(void) {
    return bridges;
}

uint64_t fk_triple_kernel_bridge_count(void) {
    return 3;
}

void fk_triple_kernel_report(void) {
    fk_serial_write("FractalOS triple-kernel topology\n");
    for (uint64_t i = 0; i < fk_triple_kernel_vertex_count(); i++) {
        fk_serial_write(" - ");
        fk_serial_write(vertices[i].name);
        fk_serial_write(" readiness=");
        fk_serial_write_hex64(vertices[i].readiness);
        fk_serial_write(" purpose=");
        fk_serial_write(vertices[i].purpose);
        fk_serial_write("\n");
    }
    for (uint64_t i = 0; i < fk_triple_kernel_bridge_count(); i++) {
        fk_serial_write(" - bridge ");
        fk_serial_write_hex64(bridges[i].left);
        fk_serial_write("<->");
        fk_serial_write_hex64(bridges[i].right);
        fk_serial_write(" strength=");
        fk_serial_write_hex64(bridges[i].strength);
        fk_serial_write("\n");
    }
    fk_serial_write("TripleKernel score=");
    fk_serial_write_hex64(fk_triple_kernel_score());
    fk_serial_write("\n");
}
