#include "../include/fractal_kernel.h"

#define FK_SLAB_CLASS_COUNT 4
#define FK_SLAB_SLOT_COUNT 32

struct fk_slab_class {
    uint64_t object_size;
    uint8_t *arena;
    uint8_t used[FK_SLAB_SLOT_COUNT];
};

static struct fk_slab_class slab_classes[FK_SLAB_CLASS_COUNT];
static uint64_t slab_sizes[FK_SLAB_CLASS_COUNT] = {32ull, 64ull, 128ull, 256ull};
static uint64_t slab_live = 0;

void fk_slab_init(struct fk_boot_context *ctx) {
    slab_live = 0;
    for (uint64_t i = 0; i < FK_SLAB_CLASS_COUNT; i++) {
        slab_classes[i].object_size = slab_sizes[i];
        slab_classes[i].arena = (uint8_t *)fk_heap_alloc(slab_sizes[i] * FK_SLAB_SLOT_COUNT);
        for (uint64_t j = 0; j < FK_SLAB_SLOT_COUNT; j++) {
            slab_classes[i].used[j] = 0;
        }
    }
    if (ctx) {
        ctx->slab_classes_ready = FK_SLAB_CLASS_COUNT;
        ctx->slab_live_objects = slab_live;
    }
}

static struct fk_slab_class *select_class(uint64_t size) {
    uint64_t needed = size == 0 ? 16ull : size;
    for (uint64_t i = 0; i < FK_SLAB_CLASS_COUNT; i++) {
        if (needed <= slab_classes[i].object_size && slab_classes[i].arena) {
            return &slab_classes[i];
        }
    }
    return 0;
}

void *fk_slab_alloc(uint64_t size) {
    struct fk_slab_class *klass = select_class(size);
    if (!klass) {
        return fk_heap_alloc(size);
    }
    for (uint64_t i = 0; i < FK_SLAB_SLOT_COUNT; i++) {
        if (!klass->used[i]) {
            klass->used[i] = 1;
            slab_live += 1;
            return klass->arena + (i * klass->object_size);
        }
    }
    return fk_heap_alloc(size);
}

void fk_slab_free(void *ptr, uint64_t size_hint) {
    if (!ptr) {
        return;
    }
    struct fk_slab_class *klass = select_class(size_hint);
    if (!klass || !klass->arena) {
        fk_heap_free(ptr);
        return;
    }
    uint64_t base = (uint64_t)(uintptr_t)klass->arena;
    uint64_t address = (uint64_t)(uintptr_t)ptr;
    uint64_t span = klass->object_size * FK_SLAB_SLOT_COUNT;
    if (address < base || address >= base + span) {
        fk_heap_free(ptr);
        return;
    }
    uint64_t index = (address - base) / klass->object_size;
    if (index < FK_SLAB_SLOT_COUNT && klass->used[index]) {
        klass->used[index] = 0;
        if (slab_live > 0) {
            slab_live -= 1;
        }
    }
}

uint64_t fk_slab_class_count(void) {
    return FK_SLAB_CLASS_COUNT;
}

uint64_t fk_slab_live_objects(void) {
    return slab_live;
}

void fk_slab_report(void) {
    fk_serial_write("Slab classes=");
    fk_serial_write_hex64(FK_SLAB_CLASS_COUNT);
    fk_serial_write(" live_objects=");
    fk_serial_write_hex64(slab_live);
    fk_serial_write("\n");
}
