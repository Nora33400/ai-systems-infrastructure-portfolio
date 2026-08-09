#include "../include/fractal_kernel.h"

#define FK_ILLUSION_MODE_MAX 3u

struct fk_illusion_mode {
    uint64_t id;
    const char *name;
    uint64_t shadow_depth;
};

static const struct fk_illusion_mode modes[FK_ILLUSION_MODE_MAX] = {
    {1, "faithful", 1},
    {2, "adaptive", 2},
    {3, "shadowed", 4},
};

static struct fk_boot_context *illusion_ctx = 0;
static uint64_t current_mode = 0;
static uint64_t shadow_depth = 0;
static uint64_t contradiction_count = 0;

static const struct fk_illusion_mode *mode_slot(uint64_t id) {
    if (id == 0 || id > FK_ILLUSION_MODE_MAX) {
        return 0;
    }
    return &modes[id - 1];
}

void fk_illusion_init(struct fk_boot_context *ctx) {
    const struct fk_illusion_mode *mode = &modes[1];
    illusion_ctx = ctx;
    current_mode = mode->id;
    shadow_depth = mode->shadow_depth;
    contradiction_count = 0;
    if (ctx) {
        ctx->illusion_ready = 1;
        ctx->illusion_mode_id = current_mode;
        ctx->shadow_dimension_depth = shadow_depth;
        ctx->contradiction_count = contradiction_count;
    }
}

uint64_t fk_illusion_mode_id(void) {
    return current_mode;
}

uint64_t fk_illusion_shadow_depth(void) {
    return shadow_depth;
}

uint64_t fk_illusion_contradiction_count(void) {
    return contradiction_count;
}

uint64_t fk_illusion_shift_mode(uint64_t mode_id) {
    const struct fk_illusion_mode *mode = mode_slot(mode_id);
    if (!mode) {
        return current_mode;
    }
    current_mode = mode->id;
    shadow_depth = mode->shadow_depth;
    if (illusion_ctx) {
        illusion_ctx->illusion_mode_id = current_mode;
        illusion_ctx->shadow_dimension_depth = shadow_depth;
    }
    return current_mode;
}

uint64_t fk_illusion_raise_contradiction(void) {
    contradiction_count += 1;
    if (illusion_ctx) {
        illusion_ctx->contradiction_count = contradiction_count;
    }
    return contradiction_count;
}

void fk_illusion_report(void) {
    fk_serial_write("Illusion mode=");
    fk_serial_write_hex64(current_mode);
    fk_serial_write(" shadow_depth=");
    fk_serial_write_hex64(shadow_depth);
    fk_serial_write(" contradictions=");
    fk_serial_write_hex64(contradiction_count);
    fk_serial_write("\n");
}
