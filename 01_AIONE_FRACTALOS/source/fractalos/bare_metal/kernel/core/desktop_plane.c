#include "../include/fractal_kernel.h"

#define FK_DESKTOP_LAYER_MAX 10ull
#define FK_DESKTOP_OVERLAY_MAX 6ull

struct fk_desktop_layer {
    uint64_t id;
    const char *name;
    uint8_t persistent;
};

static struct fk_boot_context *desktop_ctx = 0;
static struct fk_desktop_layer desktop_layers[FK_DESKTOP_LAYER_MAX] = {
    {1, "login-greeter", 1},
    {2, "start-menu", 1},
    {3, "global-search", 1},
    {4, "tile-explorer", 1},
    {5, "fractal-terminal", 1},
    {6, "web-gateway", 0},
    {7, "package-center", 1},
    {8, "agent-overlay", 1},
    {9, "proof-ribbon", 1},
    {10, "command-veil", 1},
};
static uint64_t desktop_overlay_mode = 1;
static uint64_t desktop_persistent_panels = 0;

static void sync_context(void) {
    if (!desktop_ctx) {
        return;
    }
    desktop_ctx->desktop_layer_count = FK_DESKTOP_LAYER_MAX;
    desktop_ctx->desktop_overlay_mode_id = desktop_overlay_mode;
    desktop_ctx->desktop_persistent_panels = desktop_persistent_panels;
}

void fk_desktop_plane_init(struct fk_boot_context *ctx) {
    desktop_ctx = ctx;
    desktop_overlay_mode = 1;
    desktop_persistent_panels = 0;
    for (uint64_t i = 0; i < FK_DESKTOP_LAYER_MAX; i++) {
        desktop_persistent_panels += desktop_layers[i].persistent ? 1 : 0;
    }
    if (ctx) {
        ctx->desktop_ready = 1;
        sync_context();
    }
}

uint64_t fk_desktop_plane_layer_count(void) {
    return FK_DESKTOP_LAYER_MAX;
}

uint64_t fk_desktop_plane_overlay_mode(void) {
    return desktop_overlay_mode;
}

uint64_t fk_desktop_plane_persistent_panels(void) {
    return desktop_persistent_panels;
}

uint64_t fk_desktop_plane_cycle_overlay(void) {
    desktop_overlay_mode += 1;
    if (desktop_overlay_mode > FK_DESKTOP_OVERLAY_MAX) {
        desktop_overlay_mode = 1;
    }
    sync_context();
    return desktop_overlay_mode;
}

void fk_desktop_plane_report(void) {
    fk_serial_write("DesktopPlane layers=");
    fk_serial_write_hex64(fk_desktop_plane_layer_count());
    fk_serial_write(" overlay=");
    fk_serial_write_hex64(fk_desktop_plane_overlay_mode());
    fk_serial_write(" persistent=");
    fk_serial_write_hex64(fk_desktop_plane_persistent_panels());
    fk_serial_write("\n");
}
