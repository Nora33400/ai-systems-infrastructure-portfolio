#include "../include/fractal_kernel.h"

static struct fk_boot_context *proof_ctx = 0;
static uint64_t proof_attestation_level = 0;
static uint64_t proof_promotion_count = 0;

static void sync_context(void) {
    if (!proof_ctx) {
        return;
    }
    proof_ctx->proof_attestation_level = proof_attestation_level;
    proof_ctx->proof_promotion_count = proof_promotion_count;
}

void fk_proofstate_init(struct fk_boot_context *ctx) {
    proof_ctx = ctx;
    proof_attestation_level = 2;
    proof_promotion_count = 0;
    if (ctx) {
        ctx->proof_ready = 1;
        sync_context();
    }
}

uint64_t fk_proofstate_attestation_level(void) {
    return proof_attestation_level;
}

uint64_t fk_proofstate_promotion_count(void) {
    return proof_promotion_count;
}

uint64_t fk_proofstate_promote(uint64_t grade) {
    if (grade > proof_attestation_level) {
        proof_attestation_level = grade;
    }
    proof_promotion_count += 1;
    sync_context();
    return proof_attestation_level;
}

void fk_proofstate_report(void) {
    fk_serial_write("ProofState level=");
    fk_serial_write_hex64(fk_proofstate_attestation_level());
    fk_serial_write(" promotions=");
    fk_serial_write_hex64(fk_proofstate_promotion_count());
    fk_serial_write("\n");
}
