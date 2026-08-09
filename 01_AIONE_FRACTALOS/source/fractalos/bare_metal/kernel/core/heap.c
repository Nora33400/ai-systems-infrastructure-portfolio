#include "../include/fractal_kernel.h"

#define FK_HEAP_ARENA_SIZE (64ull * 1024ull)
#define FK_HEAP_BLOCK_CAPACITY 128
#define FK_HEAP_BOOTSTRAP_RESERVE_FRAMES 8

struct fk_heap_block {
    uint64_t offset;
    uint64_t size;
    uint8_t used;
};

static uint8_t heap_arena[FK_HEAP_ARENA_SIZE];
static struct fk_heap_block heap_blocks[FK_HEAP_BLOCK_CAPACITY];
static uint64_t heap_capacity = 0;
static uint64_t heap_used = 0;
static uint64_t heap_reserved = 0;

static uint64_t align_heap(uint64_t value) {
    return (value + 15ull) & ~15ull;
}

static void reset_heap_blocks(void) {
    for (uint64_t i = 0; i < FK_HEAP_BLOCK_CAPACITY; i++) {
        heap_blocks[i].offset = 0;
        heap_blocks[i].size = 0;
        heap_blocks[i].used = 0;
    }
}

void fk_heap_init(struct fk_boot_context *ctx) {
    heap_capacity = FK_HEAP_ARENA_SIZE;
    heap_used = 0;
    heap_reserved = 0;
    reset_heap_blocks();

    for (uint64_t i = 0; i < FK_HEAP_BOOTSTRAP_RESERVE_FRAMES; i++) {
        uint64_t frame = fk_pmm_alloc_frame();
        if (frame == 0) {
            break;
        }
        heap_reserved += 1;
    }

    heap_blocks[0].offset = 0;
    heap_blocks[0].size = heap_capacity;
    heap_blocks[0].used = 0;

    if (ctx) {
        ctx->heap_reserved_frames = heap_reserved;
        ctx->heap_capacity_bytes = heap_capacity;
        ctx->free_frame_count = fk_pmm_free_frames();
    }
}

void *fk_heap_alloc(uint64_t size) {
    uint64_t needed = align_heap(size == 0 ? 16ull : size);
    for (uint64_t i = 0; i < FK_HEAP_BLOCK_CAPACITY; i++) {
        if (heap_blocks[i].size >= needed && heap_blocks[i].used == 0) {
            if (heap_blocks[i].size > needed) {
                for (uint64_t j = 0; j < FK_HEAP_BLOCK_CAPACITY; j++) {
                    if (heap_blocks[j].size == 0 && heap_blocks[j].used == 0) {
                        heap_blocks[j].offset = heap_blocks[i].offset + needed;
                        heap_blocks[j].size = heap_blocks[i].size - needed;
                        heap_blocks[j].used = 0;
                        break;
                    }
                }
            }
            heap_blocks[i].size = needed;
            heap_blocks[i].used = 1;
            heap_used += needed;
            return &heap_arena[heap_blocks[i].offset];
        }
    }
    return 0;
}

void fk_heap_free(void *ptr) {
    if (!ptr) {
        return;
    }
    uint64_t base = (uint64_t)(uintptr_t)&heap_arena[0];
    uint64_t address = (uint64_t)(uintptr_t)ptr;
    if (address < base || address >= base + heap_capacity) {
        return;
    }
    uint64_t offset = address - base;
    for (uint64_t i = 0; i < FK_HEAP_BLOCK_CAPACITY; i++) {
        if (heap_blocks[i].offset == offset && heap_blocks[i].used) {
            heap_blocks[i].used = 0;
            heap_used -= heap_blocks[i].size;
            return;
        }
    }
}

uint64_t fk_heap_capacity_bytes(void) {
    return heap_capacity;
}

uint64_t fk_heap_used_bytes(void) {
    return heap_used;
}

uint64_t fk_heap_reserved_frames(void) {
    return heap_reserved;
}

void fk_heap_report(void) {
    fk_serial_write("Heap capacity=");
    fk_serial_write_hex64(heap_capacity);
    fk_serial_write(" used=");
    fk_serial_write_hex64(heap_used);
    fk_serial_write(" reserved_frames=");
    fk_serial_write_hex64(heap_reserved);
    fk_serial_write("\n");
}
