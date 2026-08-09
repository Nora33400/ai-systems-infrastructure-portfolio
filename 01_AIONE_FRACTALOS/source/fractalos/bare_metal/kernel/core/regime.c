#include "../include/fractal_kernel.h"

#define FK_REGIME_MAX 5u

struct fk_regime {
    uint64_t id;
    const char *name;
    const char *purpose;
};

static const struct fk_regime regimes[FK_REGIME_MAX] = {
    {1, "latency", "reponse immediate, faible interference, IRQ courtes"},
    {2, "throughput", "debit massif, longues tranches, prefetch agressif"},
    {3, "speculative", "branches rapides, prechauffage et essais bornes"},
    {4, "isolated", "charges critiques, confiance et interferences reduites"},
    {5, "cold", "economique, thermique stable, fond systeme"},
};

static struct fk_boot_context *regime_ctx = 0;
static uint64_t current_regime = 0;

void fk_regime_init(struct fk_boot_context *ctx) {
    regime_ctx = ctx;
    current_regime = regimes[0].id;
    if (ctx) {
        ctx->regime_ready = 1;
        ctx->regime_count = FK_REGIME_MAX;
        ctx->current_regime_id = current_regime;
    }
}

uint64_t fk_regime_count(void) {
    return FK_REGIME_MAX;
}

uint64_t fk_regime_current_id(void) {
    return current_regime;
}

uint64_t fk_regime_select(uint64_t regime_id) {
    if (regime_id == 0 || regime_id > FK_REGIME_MAX) {
        return current_regime;
    }
    current_regime = regime_id;
    if (regime_ctx) {
        regime_ctx->current_regime_id = current_regime;
    }
    return current_regime;
}

void fk_regime_report(void) {
    fk_serial_write("Regimes count=");
    fk_serial_write_hex64(FK_REGIME_MAX);
    fk_serial_write(" current=");
    fk_serial_write_hex64(current_regime);
    fk_serial_write("\n");
}
