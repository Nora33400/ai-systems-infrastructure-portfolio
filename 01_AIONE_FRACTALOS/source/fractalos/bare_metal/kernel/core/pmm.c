#include "../include/fractal_kernel.h"

#define FK_PMM_USABLE 0
#define FK_PMM_MAX_FRAMES 8192

static uint64_t pmm_total_regions = 0;
static uint64_t pmm_usable_regions = 0;
static uint64_t pmm_usable_bytes = 0;
static uint64_t pmm_frame_stack[FK_PMM_MAX_FRAMES];
static uint64_t pmm_frame_count = 0;

static uint64_t align_up(uint64_t value, uint64_t alignment) {
    uint64_t mask = alignment - 1;
    return (value + mask) & ~mask;
}

void fk_pmm_init(
    struct fk_boot_context *ctx,
    uint64_t entry_count,
    const uint64_t *base_list,
    const uint64_t *length_list,
    const uint64_t *type_list
) {
    pmm_total_regions = entry_count;
    pmm_usable_regions = 0;
    pmm_usable_bytes = 0;
    pmm_frame_count = 0;

    if (!base_list || !length_list || !type_list) {
        return;
    }

    for (uint64_t i = 0; i < entry_count; i++) {
        if (type_list[i] == FK_PMM_USABLE) {
            pmm_usable_regions += 1;
            pmm_usable_bytes += length_list[i];
            uint64_t start = align_up(base_list[i], FK_PAGE_SIZE);
            uint64_t end = (base_list[i] + length_list[i]) & ~(FK_PAGE_SIZE - 1);
            for (uint64_t frame = start; frame + FK_PAGE_SIZE <= end && pmm_frame_count < FK_PMM_MAX_FRAMES; frame += FK_PAGE_SIZE) {
                pmm_frame_stack[pmm_frame_count++] = frame;
            }
        }
    }

    if (ctx) {
        ctx->memory_map_entries = entry_count;
        ctx->usable_memory_bytes = pmm_usable_bytes;
        ctx->free_frame_count = pmm_frame_count;
        ctx->pmm_ready = pmm_usable_regions > 0 ? 1 : 0;
    }
}

uint64_t fk_pmm_usable_bytes(void) {
    return pmm_usable_bytes;
}

uint64_t fk_pmm_total_regions(void) {
    return pmm_total_regions;
}

uint64_t fk_pmm_usable_regions(void) {
    return pmm_usable_regions;
}

uint64_t fk_pmm_free_frames(void) {
    return pmm_frame_count;
}

uint64_t fk_pmm_alloc_frame(void) {
    if (pmm_frame_count == 0) {
        return 0;
    }
    pmm_frame_count -= 1;
    return pmm_frame_stack[pmm_frame_count];
}

void fk_pmm_free_frame(uint64_t address) {
    if (address == 0 || (address & (FK_PAGE_SIZE - 1)) != 0 || pmm_frame_count >= FK_PMM_MAX_FRAMES) {
        return;
    }
    pmm_frame_stack[pmm_frame_count++] = address;
}

void fk_pmm_report(void) {
    fk_serial_write("PMM total_regions=");
    fk_serial_write_hex64(pmm_total_regions);
    fk_serial_write(" usable_regions=");
    fk_serial_write_hex64(pmm_usable_regions);
    fk_serial_write(" usable_bytes=");
    fk_serial_write_hex64(pmm_usable_bytes);
    fk_serial_write(" free_frames=");
    fk_serial_write_hex64(pmm_frame_count);
    fk_serial_write("\n");
}
