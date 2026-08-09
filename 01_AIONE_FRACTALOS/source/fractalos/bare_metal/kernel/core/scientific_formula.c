#include "../include/fractal_kernel.h"

#define FK_SCIENTIFIC_FORMULA_MAX 8ull
#define FK_FORMULA_SCALE 1000ull

struct fk_scientific_formula {
    uint64_t id;
    const char *name;
    uint64_t activation;
    uint64_t safety;
};

static struct fk_boot_context *formula_ctx = 0;
static struct fk_scientific_formula formulas[FK_SCIENTIFIC_FORMULA_MAX] = {
    {1, "entropy-tile-density", 720, 930},
    {2, "thermal-throughput-envelope", 680, 950},
    {3, "semantic-ram-retention", 700, 900},
    {4, "proof-gated-promotion", 640, 980},
    {5, "intent-latency-field", 690, 860},
    {6, "gpu-native-guard", 560, 940},
    {7, "mesh-route-resilience", 620, 880},
    {8, "future-branch-selection", 600, 920},
};
static uint64_t formula_activation = 0;
static uint64_t formula_safety = 0;

static void sync_context(void) {
    if (!formula_ctx) {
        return;
    }
    formula_ctx->scientific_formula_count = FK_SCIENTIFIC_FORMULA_MAX;
    formula_ctx->scientific_formula_activation = formula_activation;
    formula_ctx->scientific_formula_safety = formula_safety;
}

void fk_scientific_formula_init(struct fk_boot_context *ctx) {
    uint64_t activation_sum = 0;
    uint64_t safety_sum = 0;
    formula_ctx = ctx;
    for (uint64_t i = 0; i < FK_SCIENTIFIC_FORMULA_MAX; i++) {
        activation_sum += formulas[i].activation;
        safety_sum += formulas[i].safety;
    }
    formula_activation = activation_sum / FK_SCIENTIFIC_FORMULA_MAX;
    formula_safety = safety_sum / FK_SCIENTIFIC_FORMULA_MAX;
    if (ctx) {
        ctx->scientific_formula_ready = 1;
        sync_context();
    }
}

uint64_t fk_scientific_formula_count(void) {
    return FK_SCIENTIFIC_FORMULA_MAX;
}

uint64_t fk_scientific_formula_activation(void) {
    return formula_activation;
}

uint64_t fk_scientific_formula_safety(void) {
    return formula_safety;
}

uint64_t fk_scientific_formula_boost_storage(void) {
    if (formula_safety < 850) {
        return formula_activation;
    }
    formula_activation += 9;
    if (formula_activation > FK_FORMULA_SCALE) {
        formula_activation = FK_FORMULA_SCALE;
    }
    sync_context();
    return formula_activation;
}

void fk_scientific_formula_report(void) {
    fk_serial_write("ScientificFormula count=");
    fk_serial_write_hex64(fk_scientific_formula_count());
    fk_serial_write(" activation=");
    fk_serial_write_hex64(fk_scientific_formula_activation());
    fk_serial_write(" safety=");
    fk_serial_write_hex64(fk_scientific_formula_safety());
    fk_serial_write("\n");
}
