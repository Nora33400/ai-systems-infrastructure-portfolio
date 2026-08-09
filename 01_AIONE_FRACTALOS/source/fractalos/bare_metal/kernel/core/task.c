#include "../include/fractal_kernel.h"

#define FK_TASK_MAX 16u
#define FK_TASK_NAME_BYTES 24u

enum fk_task_state {
    FK_TASK_READY = 1,
    FK_TASK_RUNNING = 2,
    FK_TASK_WAITING = 3,
};

struct fk_task {
    uint64_t id;
    uint8_t ring;
    uint8_t state;
    char name[FK_TASK_NAME_BYTES];
};

static struct fk_task task_table[FK_TASK_MAX];
static struct fk_boot_context *task_ctx = 0;
static uint64_t task_total = 0;
static uint64_t current_task = 0;

static void copy_name(char *dst, const char *src) {
    uint64_t i = 0;
    if (!dst) {
        return;
    }
    if (!src) {
        dst[0] = 0;
        return;
    }
    for (; i + 1 < FK_TASK_NAME_BYTES && src[i] != 0; i++) {
        dst[i] = src[i];
    }
    dst[i] = 0;
}

static struct fk_task *task_slot(uint64_t id) {
    if (id == 0 || id > task_total) {
        return 0;
    }
    return &task_table[id - 1];
}

void fk_task_init(struct fk_boot_context *ctx) {
    for (uint64_t i = 0; i < FK_TASK_MAX; i++) {
        task_table[i].id = 0;
        task_table[i].ring = 0;
        task_table[i].state = 0;
        task_table[i].name[0] = 0;
    }
    task_ctx = ctx;
    task_total = 0;
    current_task = 0;
    if (ctx) {
        ctx->task_ready = 1;
        ctx->task_capacity = FK_TASK_MAX;
        ctx->task_count = 0;
        ctx->current_task_id = 0;
    }
}

uint64_t fk_task_spawn_kernel(const char *name, uint8_t ring, uint8_t state) {
    struct fk_task *slot;
    if (task_total >= FK_TASK_MAX) {
        return 0;
    }
    task_total += 1;
    slot = &task_table[task_total - 1];
    slot->id = task_total;
    slot->ring = ring;
    slot->state = state == 0 ? FK_TASK_READY : state;
    copy_name(slot->name, name);
    if (current_task == 0) {
        current_task = slot->id;
        slot->state = FK_TASK_RUNNING;
    }
    if (task_ctx) {
        task_ctx->task_count = task_total;
        task_ctx->current_task_id = current_task;
    }
    return slot->id;
}

uint64_t fk_task_count(void) {
    return task_total;
}

uint64_t fk_task_capacity(void) {
    return FK_TASK_MAX;
}

uint64_t fk_task_current_id(void) {
    return current_task;
}

void fk_task_set_current(uint64_t task_id) {
    struct fk_task *previous = task_slot(current_task);
    struct fk_task *next = task_slot(task_id);
    if (!next) {
        return;
    }
    if (previous && previous->state == FK_TASK_RUNNING) {
        previous->state = FK_TASK_READY;
    }
    current_task = task_id;
    next->state = FK_TASK_RUNNING;
    if (task_ctx) {
        task_ctx->current_task_id = current_task;
    }
}

void fk_task_report(void) {
    fk_serial_write("Task model current=");
    fk_serial_write_hex64(fk_task_current_id());
    fk_serial_write(" count=");
    fk_serial_write_hex64(fk_task_count());
    fk_serial_write(" capacity=");
    fk_serial_write_hex64(fk_task_capacity());
    fk_serial_write("\n");
}
