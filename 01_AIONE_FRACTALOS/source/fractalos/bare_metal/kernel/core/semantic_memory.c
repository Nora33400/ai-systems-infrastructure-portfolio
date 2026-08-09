#include "../include/fractal_kernel.h"

#define FK_SEMANTIC_CLASS_COUNT 5u

static struct fk_boot_context *semantic_ctx = 0;
static uint64_t semantic_promoted = 0;

void fk_semantic_memory_init(struct fk_boot_context *ctx) {
    semantic_ctx = ctx;
    semantic_promoted = fk_pmm_free_frames() > 32 ? 8 : fk_pmm_free_frames() > 8 ? 2 : 0;
    if (ctx) {
        ctx->semantic_memory_ready = 1;
        ctx->semantic_page_classes = FK_SEMANTIC_CLASS_COUNT;
        ctx->semantic_promoted_pages = semantic_promoted;
    }
}

uint64_t fk_semantic_memory_class_count(void) {
    return FK_SEMANTIC_CLASS_COUNT;
}

uint64_t fk_semantic_memory_promoted_pages(void) {
    return semantic_promoted;
}

uint64_t fk_semantic_memory_promote_pages(uint64_t pages) {
    semantic_promoted += pages;
    if (semantic_ctx) {
        semantic_ctx->semantic_promoted_pages = semantic_promoted;
    }
    return semantic_promoted;
}

void fk_semantic_memory_report(void) {
    fk_serial_write("SemanticMemory classes=");
    fk_serial_write_hex64(FK_SEMANTIC_CLASS_COUNT);
    fk_serial_write(" promoted=");
    fk_serial_write_hex64(semantic_promoted);
    fk_serial_write("\n");
}
