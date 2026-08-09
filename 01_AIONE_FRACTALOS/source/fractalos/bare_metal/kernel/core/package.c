#include "../include/fractal_kernel.h"

#define FK_PACKAGE_MANIFEST_MAX 1ull
#define FK_PACKAGE_AVAILABLE_MAX 12ull

struct fk_package_entry {
    uint64_t id;
    const char *name;
    const char *phase;
};

static struct fk_boot_context *package_ctx = 0;
static struct fk_package_entry package_entries[FK_PACKAGE_AVAILABLE_MAX] = {
    {1, "runtime.python", "compat-alpha"},
    {2, "runtime.rust", "compat-alpha"},
    {3, "runtime.java", "compat-alpha"},
    {4, "browser.firefox-domain", "network-alpha"},
    {5, "office.libreoffice-domain", "desktop-alpha"},
    {6, "media.codec-pack", "desktop-alpha"},
    {7, "dev.code-studio", "userspace-alpha"},
    {8, "ai.ollama-local", "hosted-ready"},
    {9, "fs.tilemindfs", "hosted-ready"},
    {10, "doctor.safe-update", "hosted-ready"},
    {11, "compat.exe-domain", "compat-alpha"},
    {12, "net.mesh-agent", "hosted-ready"},
};

static void sync_context(void) {
    if (!package_ctx) {
        return;
    }
    package_ctx->package_manifest_count = FK_PACKAGE_MANIFEST_MAX;
    package_ctx->package_available_count = FK_PACKAGE_AVAILABLE_MAX;
    package_ctx->package_policy_score = fk_package_policy_score();
}

void fk_package_init(struct fk_boot_context *ctx) {
    package_ctx = ctx;
    if (ctx) {
        ctx->package_ready = 1;
        sync_context();
    }
}

uint64_t fk_package_manifest_count(void) {
    return FK_PACKAGE_MANIFEST_MAX;
}

uint64_t fk_package_available_count(void) {
    return FK_PACKAGE_AVAILABLE_MAX;
}

uint64_t fk_package_policy_score(void) {
    return fk_proofstate_attestation_level() * 64ull + fk_package_available_count() * 8ull + fk_vfs_node_count();
}

void fk_package_report(void) {
    (void)package_entries;
    fk_serial_write("Packages manifests=");
    fk_serial_write_hex64(fk_package_manifest_count());
    fk_serial_write(" available=");
    fk_serial_write_hex64(fk_package_available_count());
    fk_serial_write(" policy=");
    fk_serial_write_hex64(fk_package_policy_score());
    fk_serial_write("\n");
}
