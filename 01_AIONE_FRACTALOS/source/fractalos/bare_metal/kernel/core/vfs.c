#include "../include/fractal_kernel.h"

#define FK_VFS_MOUNT_MAX 2ull
#define FK_VFS_NODE_MAX 10ull

struct fk_vfs_node {
    uint64_t id;
    const char *path;
    uint8_t directory;
    uint8_t writable;
};

static struct fk_boot_context *vfs_ctx = 0;
static uint64_t vfs_open_count = 0;
static struct fk_vfs_node vfs_nodes[FK_VFS_NODE_MAX] = {
    {1, "/", 1, 0},
    {2, "/etc", 1, 0},
    {3, "/etc/fractalos-release", 0, 0},
    {4, "/home", 1, 0},
    {5, "/home/guest", 1, 1},
    {6, "/home/user", 1, 1},
    {7, "/home/user/README.txt", 0, 1},
    {8, "/apps", 1, 0},
    {9, "/apps/packages.json", 0, 0},
    {10, "/tiles", 1, 0},
};

static void sync_context(void) {
    if (!vfs_ctx) {
        return;
    }
    vfs_ctx->vfs_mount_count = FK_VFS_MOUNT_MAX;
    vfs_ctx->vfs_node_count = FK_VFS_NODE_MAX;
    vfs_ctx->vfs_open_file_count = vfs_open_count;
}

void fk_vfs_init(struct fk_boot_context *ctx) {
    vfs_ctx = ctx;
    vfs_open_count = 0;
    if (ctx) {
        ctx->vfs_ready = 1;
        sync_context();
    }
}

uint64_t fk_vfs_mount_count(void) {
    return FK_VFS_MOUNT_MAX;
}

uint64_t fk_vfs_node_count(void) {
    return FK_VFS_NODE_MAX;
}

uint64_t fk_vfs_open_file_count(void) {
    return vfs_open_count;
}

uint64_t fk_vfs_open_home_readme(void) {
    vfs_open_count += 1;
    sync_context();
    return vfs_nodes[6].id;
}

void fk_vfs_report(void) {
    fk_serial_write("VFS mounts=");
    fk_serial_write_hex64(fk_vfs_mount_count());
    fk_serial_write(" nodes=");
    fk_serial_write_hex64(fk_vfs_node_count());
    fk_serial_write(" opens=");
    fk_serial_write_hex64(fk_vfs_open_file_count());
    fk_serial_write("\n");
}
