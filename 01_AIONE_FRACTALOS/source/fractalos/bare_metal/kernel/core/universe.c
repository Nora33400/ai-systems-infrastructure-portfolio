#include "../include/fractal_kernel.h"

#define FK_UNIVERSE_LAW_MAX 4u

struct fk_universe_law {
    uint64_t id;
    const char *name;
    uint64_t force_level;
};

static const struct fk_universe_law laws[FK_UNIVERSE_LAW_MAX] = {
    {1, "rigid", 2},
    {2, "balanced", 5},
    {3, "chaos", 9},
    {4, "evolution", 7},
};

static struct fk_boot_context *universe_ctx = 0;
static uint64_t current_law = 0;
static uint64_t field_force = 0;

static const struct fk_universe_law *law_slot(uint64_t id) {
    if (id == 0 || id > FK_UNIVERSE_LAW_MAX) {
        return 0;
    }
    return &laws[id - 1];
}

void fk_universe_init(struct fk_boot_context *ctx) {
    const struct fk_universe_law *law = &laws[1];
    universe_ctx = ctx;
    current_law = law->id;
    field_force = law->force_level;
    if (ctx) {
        ctx->universe_ready = 1;
        ctx->universe_law_count = FK_UNIVERSE_LAW_MAX;
        ctx->current_universe_law_id = current_law;
        ctx->field_force_level = field_force;
    }
}

uint64_t fk_universe_law_count(void) {
    return FK_UNIVERSE_LAW_MAX;
}

uint64_t fk_universe_current_law_id(void) {
    return current_law;
}

uint64_t fk_universe_field_force_level(void) {
    return field_force;
}

uint64_t fk_universe_select_law(uint64_t law_id) {
    const struct fk_universe_law *law = law_slot(law_id);
    if (!law) {
        return current_law;
    }
    current_law = law->id;
    field_force = law->force_level;
    if (universe_ctx) {
        universe_ctx->current_universe_law_id = current_law;
        universe_ctx->field_force_level = field_force;
    }
    return current_law;
}

void fk_universe_report(void) {
    fk_serial_write("Universe laws=");
    fk_serial_write_hex64(FK_UNIVERSE_LAW_MAX);
    fk_serial_write(" current=");
    fk_serial_write_hex64(current_law);
    fk_serial_write(" field_force=");
    fk_serial_write_hex64(field_force);
    fk_serial_write("\n");
}
