#include "../include/fractal_kernel.h"

#define FK_FOUNDRY_LINE_MAX 4ull

struct fk_foundry_line {
    uint64_t id;
    const char *name;
    uint64_t batches_completed;
};

static struct fk_boot_context *foundry_ctx = 0;
static struct fk_foundry_line foundry_lines[FK_FOUNDRY_LINE_MAX] = {
    {1, "interpret", 0},
    {2, "formalize", 0},
    {3, "verify", 0},
    {4, "promote", 0},
};
static uint64_t foundry_batch_count = 0;

static void sync_context(void) {
    if (!foundry_ctx) {
        return;
    }
    foundry_ctx->foundry_line_count = FK_FOUNDRY_LINE_MAX;
    foundry_ctx->foundry_batch_count = foundry_batch_count;
}

void fk_foundry_init(struct fk_boot_context *ctx) {
    foundry_ctx = ctx;
    foundry_batch_count = 0;
    for (uint64_t i = 0; i < FK_FOUNDRY_LINE_MAX; i++) {
        foundry_lines[i].batches_completed = 0;
    }
    if (ctx) {
        ctx->foundry_ready = 1;
        ctx->foundry_line_count = FK_FOUNDRY_LINE_MAX;
        ctx->foundry_batch_count = 0;
    }
}

uint64_t fk_foundry_line_count(void) {
    return FK_FOUNDRY_LINE_MAX;
}

uint64_t fk_foundry_batch_count(void) {
    return foundry_batch_count;
}

uint64_t fk_foundry_run_batch(uint64_t line_id) {
    if (line_id == 0 || line_id > FK_FOUNDRY_LINE_MAX) {
        return foundry_batch_count;
    }
    foundry_lines[line_id - 1].batches_completed += 1;
    foundry_batch_count += 1;
    sync_context();
    return foundry_batch_count;
}

void fk_foundry_report(void) {
    fk_serial_write("Foundry lines=");
    fk_serial_write_hex64(fk_foundry_line_count());
    fk_serial_write(" batches=");
    fk_serial_write_hex64(fk_foundry_batch_count());
    fk_serial_write("\n");
}
