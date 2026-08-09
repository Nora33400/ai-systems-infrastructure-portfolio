#include "../include/fractal_kernel.h"

static struct fk_boot_context *storage_ctx = 0;
static uint64_t storage_slots = 0;
static uint64_t storage_journal = 0;
static uint64_t storage_snapshots = 0;
static uint64_t storage_score = 0;

static uint64_t compute_storage_score(void) {
    uint64_t vfs_weight = fk_vfs_node_count() * 5;
    uint64_t package_weight = fk_package_available_count() * 3;
    uint64_t journal_weight = storage_journal * 17;
    uint64_t snapshot_weight = storage_snapshots * 23;
    return storage_slots * 31 + vfs_weight + package_weight + journal_weight + snapshot_weight;
}

static void sync_context(void) {
    storage_score = compute_storage_score();
    if (!storage_ctx) {
        return;
    }
    storage_ctx->storage_slot_count = storage_slots;
    storage_ctx->storage_journal_count = storage_journal;
    storage_ctx->storage_snapshot_count = storage_snapshots;
    storage_ctx->storage_persistence_score = storage_score;
}

void fk_storage_plane_init(struct fk_boot_context *ctx) {
    storage_ctx = ctx;
    storage_slots = 7;      /* EFI, boot_a, boot_b, system, state, home, recovery */
    storage_journal = 1;    /* bootstrap journal seed */
    storage_snapshots = 1;  /* known-good boot snapshot seed */
    if (ctx) {
        ctx->storage_ready = 1;
    }
    sync_context();
}

uint64_t fk_storage_plane_slot_count(void) {
    return storage_slots;
}

uint64_t fk_storage_plane_journal_count(void) {
    return storage_journal;
}

uint64_t fk_storage_plane_snapshot_count(void) {
    return storage_snapshots;
}

uint64_t fk_storage_plane_persistence_score(void) {
    sync_context();
    return storage_score;
}

uint64_t fk_storage_plane_commit_journal(void) {
    storage_journal += 1;
    sync_context();
    return storage_journal;
}

uint64_t fk_storage_plane_snapshot(void) {
    storage_snapshots += 1;
    storage_journal += 1;
    sync_context();
    return storage_snapshots;
}

void fk_storage_plane_report(void) {
    sync_context();
    fk_serial_write("StorageVFS slots=");
    fk_serial_write_hex64(storage_slots);
    fk_serial_write(" journal=");
    fk_serial_write_hex64(storage_journal);
    fk_serial_write(" snapshots=");
    fk_serial_write_hex64(storage_snapshots);
    fk_serial_write(" score=");
    fk_serial_write_hex64(storage_score);
    fk_serial_write("\n");
}
