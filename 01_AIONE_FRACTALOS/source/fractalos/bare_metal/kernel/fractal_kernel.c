#include <stdint.h>
#include <stddef.h>

#include "include/fractal_kernel.h"

struct limine_framebuffer {
    void *address;
    uint64_t width;
    uint64_t height;
    uint64_t pitch;
    uint16_t bpp;
    uint8_t memory_model;
    uint8_t red_mask_size;
    uint8_t red_mask_shift;
    uint8_t green_mask_size;
    uint8_t green_mask_shift;
    uint8_t blue_mask_size;
    uint8_t blue_mask_shift;
    uint8_t unused[7];
    uint64_t edid_size;
    void *edid;
    uint64_t mode_count;
    void **modes;
};

struct limine_framebuffer_response {
    uint64_t revision;
    uint64_t framebuffer_count;
    struct limine_framebuffer **framebuffers;
};

struct limine_framebuffer_request {
    uint64_t id[4];
    uint64_t revision;
    struct limine_framebuffer_response *response;
};

struct limine_memmap_entry {
    uint64_t base;
    uint64_t length;
    uint64_t type;
};

struct limine_memmap_response {
    uint64_t revision;
    uint64_t entry_count;
    struct limine_memmap_entry **entries;
};

struct limine_memmap_request {
    uint64_t id[4];
    uint64_t revision;
    struct limine_memmap_response *response;
};

struct limine_kernel_address_response {
    uint64_t revision;
    uint64_t physical_base;
    uint64_t virtual_base;
};

struct limine_kernel_address_request {
    uint64_t id[4];
    uint64_t revision;
    struct limine_kernel_address_response *response;
};

#define LIMINE_COMMON_MAGIC_0 0xc7b1dd30df4c8b88ull
#define LIMINE_COMMON_MAGIC_1 0x0a82e883a194f07bull
#define LIMINE_REQUEST_ID(req0, req1) {LIMINE_COMMON_MAGIC_0, LIMINE_COMMON_MAGIC_1, (req0), (req1)}

__attribute__((used, section(".limine_requests")))
static volatile struct limine_framebuffer_request framebuffer_request = {
    .id = LIMINE_REQUEST_ID(0x9d5827dcd881dd75ull, 0xa3148604f6fab11bull),
    .revision = 0,
    .response = 0
};

__attribute__((used, section(".limine_requests")))
static volatile struct limine_memmap_request memmap_request = {
    .id = LIMINE_REQUEST_ID(0x67cf3d9d378a806full, 0xe304acdfc50c3c62ull),
    .revision = 0,
    .response = 0
};

__attribute__((used, section(".limine_requests")))
static volatile struct limine_kernel_address_request kernel_address_request = {
    .id = LIMINE_REQUEST_ID(0x71ba76863cc55f63ull, 0xb2644a48c516a487ull),
    .revision = 0,
    .response = 0
};

__attribute__((used, section(".limine_requests_start")))
static volatile uint64_t limine_requests_start_marker[4] = {
    0xf6b8f4b39de7d1aeull,
    0xfab91a6940fcb9cfull,
    0x785c6ed015d3e316ull,
    0x181e920a7852b9d9ull
};

__attribute__((used, section(".limine_requests_end")))
static volatile uint64_t limine_requests_end_marker[2] = {0xadc0e0531bb10d03, 0x9572709f31764c62};

static const uint32_t COLOR_BG = 0x00101814;
static const uint32_t COLOR_FG = 0x00a7ffcf;
static const uint32_t COLOR_WARN = 0x00ffd166;
static const uint32_t COLOR_MESH = 0x008ab4ff;
static struct fk_boot_context boot_context;

static void idle_forever(void) {
    for (;;) {
        fk_console_tick(&boot_context);
        __asm__ volatile ("hlt");
    }
}

static void put_pixel(struct limine_framebuffer *fb, uint64_t x, uint64_t y, uint32_t color) {
    if (!fb || !fb->address || x >= fb->width || y >= fb->height) {
        return;
    }
    uint32_t *row = (uint32_t *)((uint8_t *)fb->address + y * fb->pitch);
    row[x] = color;
}

static void fill_rect(struct limine_framebuffer *fb, uint64_t x, uint64_t y, uint64_t w, uint64_t h, uint32_t color) {
    for (uint64_t yy = y; yy < y + h && yy < fb->height; yy++) {
        for (uint64_t xx = x; xx < x + w && xx < fb->width; xx++) {
            put_pixel(fb, xx, yy, color);
        }
    }
}

static void draw_bar(struct limine_framebuffer *fb, uint64_t y, uint32_t color) {
    uint64_t margin = fb->width / 16;
    uint64_t width = fb->width - 2 * margin;
    fill_rect(fb, margin, y, width, 6, color);
}

static void draw_boot_sigils(struct limine_framebuffer *fb) {
    uint64_t cx = fb->width / 2;
    uint64_t cy = fb->height / 2;
    for (uint64_t i = 0; i < 96; i += 8) {
        fill_rect(fb, cx - i, cy - i / 2, i * 2 + 1, 3, COLOR_FG);
        fill_rect(fb, cx - i / 2, cy - i, 3, i * 2 + 1, COLOR_WARN);
    }
}

static void draw_triple_kernel_triangle(struct limine_framebuffer *fb) {
    uint64_t cx = fb->width / 2;
    uint64_t cy = fb->height / 2;
    uint64_t top_x = cx;
    uint64_t top_y = cy - 140;
    uint64_t left_x = cx - 170;
    uint64_t left_y = cy + 120;
    uint64_t right_x = cx + 170;
    uint64_t right_y = cy + 120;

    for (uint64_t i = 0; i < 170; i++) {
        put_pixel(fb, top_x - i, top_y + (i * 260) / 170, COLOR_FG);
        put_pixel(fb, top_x + i, top_y + (i * 260) / 170, COLOR_WARN);
        put_pixel(fb, left_x + i * 2, left_y, COLOR_MESH);
    }
    fill_rect(fb, top_x - 8, top_y - 8, 16, 16, COLOR_FG);
    fill_rect(fb, left_x - 8, left_y - 8, 16, 16, COLOR_WARN);
    fill_rect(fb, right_x - 8, right_y - 8, 16, 16, COLOR_MESH);
    fill_rect(fb, cx - 12, cy - 12, 24, 24, 0x00f4f1de);
    fill_rect(fb, cx - 3, top_y + 64, 6, 148, 0x0034d1bf);
    fill_rect(fb, left_x + 76, cy + 52, 180, 6, 0x0034d1bf);
}

void fk_panic(const char *message) {
    fk_serial_write("FractalOS PANIC: ");
    fk_serial_write(message ? message : "unknown");
    fk_serial_write("\n");
    idle_forever();
}

static void clear_screen(struct limine_framebuffer *fb) {
    fill_rect(fb, 0, 0, fb->width, fb->height, COLOR_BG);
}

static void initialize_physical_memory(struct fk_boot_context *ctx) {
    if (!ctx || !memmap_request.response || !memmap_request.response->entries) {
        return;
    }

    uint64_t count = memmap_request.response->entry_count;
    static uint64_t base_list[256];
    static uint64_t length_list[256];
    static uint64_t type_list[256];
    if (count > 256) {
        count = 256;
    }
    for (uint64_t i = 0; i < count; i++) {
        struct limine_memmap_entry *entry = memmap_request.response->entries[i];
        if (!entry) {
            base_list[i] = 0;
            length_list[i] = 0;
            type_list[i] = 255;
            continue;
        }
        base_list[i] = entry->base;
        length_list[i] = entry->length;
        type_list[i] = entry->type;
    }
    fk_pmm_init(ctx, count, base_list, length_list, type_list);
}

void fractal_kernel_main(void) {
    uint64_t sample_frame = 0;
    uint64_t syscall_probe = 0;
    uint64_t task_probe = 0;
    uint64_t userspace_probe = 0;
    uint64_t regime_probe = 0;
    uint64_t semantic_probe = 0;
    uint64_t universe_probe = 0;
    uint64_t illusion_probe = 0;
    uint64_t foundry_probe = 0;
    uint64_t proof_probe = 0;
    uint64_t desktop_probe = 0;
    uint64_t formula_probe = 0;
    uint64_t vfs_probe = 0;
    uint64_t package_probe = 0;
    uint64_t storage_probe = 0;
    void *heap_probe = 0;
    void *slab_probe = 0;
    fk_serial_init();
    boot_context.serial_ready = 1;
    fk_serial_write("FractalOS bare-metal kernel ");
    fk_serial_write(FRACTAL_KERNEL_VERSION);
    fk_serial_write(" booting\n");

    fk_gdt_init();
    boot_context.gdt_ready = 1;
    fk_idt_init();
    boot_context.idt_ready = 1;
    fk_pic_init();
    boot_context.pic_ready = 1;

    if (!framebuffer_request.response || framebuffer_request.response->framebuffer_count < 1) {
        fk_panic("no framebuffer from bootloader");
    }

    struct limine_framebuffer *fb = framebuffer_request.response->framebuffers[0];
    boot_context.framebuffer_width = fb->width;
    boot_context.framebuffer_height = fb->height;
    boot_context.framebuffer_pitch = fb->pitch;
    boot_context.framebuffer_address = (uint64_t)(uintptr_t)fb->address;
    boot_context.framebuffer_bpp = fb->bpp;
    if (!kernel_address_request.response) {
        fk_panic("no kernel address response from bootloader");
    }
    initialize_physical_memory(&boot_context);
    fk_vmm_init(
        &boot_context,
        kernel_address_request.response->physical_base,
        kernel_address_request.response->virtual_base
    );
    fk_keyboard_init(&boot_context);
    fk_syscall_init(&boot_context);
    fk_heap_init(&boot_context);
    fk_slab_init(&boot_context);
    fk_task_init(&boot_context);
    fk_userspace_init(&boot_context);
    fk_regime_init(&boot_context);
    fk_semantic_memory_init(&boot_context);
    fk_universe_init(&boot_context);
    fk_illusion_init(&boot_context);
    fk_foundry_init(&boot_context);
    fk_proofstate_init(&boot_context);
    fk_desktop_plane_init(&boot_context);
    fk_scientific_formula_init(&boot_context);
    fk_vfs_init(&boot_context);
    fk_package_init(&boot_context);
    fk_storage_plane_init(&boot_context);
    fk_task_spawn_kernel("boot", 0, 2);
    fk_task_spawn_kernel("console", 0, 1);
    fk_task_set_current(1);
    fk_scheduler_init(&boot_context);
    fk_timer_init(&boot_context, 100);
    __asm__ volatile ("sti");
    boot_context.interrupts_enabled = 1;
    fk_triple_kernel_init(&boot_context);

    clear_screen(fb);
    draw_bar(fb, fb->height / 8, COLOR_FG);
    draw_boot_sigils(fb);
    draw_triple_kernel_triangle(fb);
    draw_bar(fb, fb->height - fb->height / 8, COLOR_WARN);
    fk_console_init(&boot_context, (uint64_t)(uintptr_t)fb->address, fb->width, fb->height, fb->pitch);
    fk_console_write("FractalOS console online\n");
    fk_console_write("Matter Mind Mesh ready\n");
    fk_console_write("Task core stable\n");
    fk_console_write("Userspace lane primed\n");
    fk_console_write("Physical regimes online\n");
    fk_console_write("Semantic memory online\n");
    fk_console_write("Programmable universe online\n");
    fk_console_write("Shadow reality online\n");
    fk_console_write("Digital foundry online\n");
    fk_console_write("Proof state online\n");
    fk_console_write("Desktop plane online\n");
    fk_console_write("Scientific formulas online\n");
    fk_console_write("Userspace VFS online\n");
    fk_console_write("Package manifest online\n");
    fk_console_write("Storage VFS plane online\n");
    fk_console_write("Type: help\n");
    fk_console_write("> ");

    fk_serial_write("FractalOS kernel online score=");
    fk_serial_write_hex64(fk_scheduler_score(&boot_context));
    fk_serial_write("\n");
    fk_timer_report();
    fk_pmm_report();
    fk_vmm_report();
    fk_keyboard_report();
    syscall_probe = fk_syscall_invoke(3, 0, 0, 0);
    fk_syscall_report();
    fk_serial_write("Syscall probe score=");
    fk_serial_write_hex64(syscall_probe);
    fk_serial_write("\n");
    task_probe = fk_syscall_invoke(6, 0, 0, 0);
    fk_task_report();
    fk_serial_write("Task probe count=");
    fk_serial_write_hex64(task_probe);
    fk_serial_write("\n");
    userspace_probe = fk_syscall_invoke(8, 0, 0, 0);
    fk_userspace_report();
    fk_serial_write("Userspace probe count=");
    fk_serial_write_hex64(userspace_probe);
    fk_serial_write("\n");
    regime_probe = fk_syscall_invoke(10, 0, 0, 0);
    fk_regime_report();
    fk_serial_write("Regime probe current=");
    fk_serial_write_hex64(regime_probe);
    fk_serial_write("\n");
    semantic_probe = fk_syscall_invoke(11, 0, 0, 0);
    fk_semantic_memory_report();
    fk_serial_write("Semantic probe promoted=");
    fk_serial_write_hex64(semantic_probe);
    fk_serial_write("\n");
    universe_probe = fk_syscall_invoke(12, 0, 0, 0);
    fk_universe_report();
    fk_serial_write("Universe probe current=");
    fk_serial_write_hex64(universe_probe);
    fk_serial_write("\n");
    illusion_probe = fk_syscall_invoke(14, 0, 0, 0);
    fk_illusion_report();
    fk_serial_write("Illusion probe mode=");
    fk_serial_write_hex64(illusion_probe);
    fk_serial_write("\n");
    foundry_probe = fk_syscall_invoke(16, 0, 0, 0);
    fk_foundry_report();
    fk_serial_write("Foundry probe batches=");
    fk_serial_write_hex64(foundry_probe);
    fk_serial_write("\n");
    proof_probe = fk_syscall_invoke(17, 0, 0, 0);
    fk_proofstate_report();
    fk_serial_write("Proof probe level=");
    fk_serial_write_hex64(proof_probe);
    fk_serial_write("\n");
    desktop_probe = fk_syscall_invoke(18, 0, 0, 0);
    fk_desktop_plane_report();
    fk_serial_write("Desktop probe layers=");
    fk_serial_write_hex64(desktop_probe);
    fk_serial_write("\n");
    formula_probe = fk_syscall_invoke(20, 0, 0, 0);
    fk_scientific_formula_report();
    fk_serial_write("Formula probe count=");
    fk_serial_write_hex64(formula_probe);
    fk_serial_write("\n");
    vfs_probe = fk_syscall_invoke(22, 0, 0, 0);
    fk_vfs_report();
    fk_serial_write("VFS probe nodes=");
    fk_serial_write_hex64(vfs_probe);
    fk_serial_write("\n");
    package_probe = fk_syscall_invoke(24, 0, 0, 0);
    fk_package_report();
    fk_serial_write("Package probe available=");
    fk_serial_write_hex64(package_probe);
    fk_serial_write("\n");
    storage_probe = fk_syscall_invoke(26, 0, 0, 0);
    fk_storage_plane_report();
    fk_serial_write("Storage probe slots=");
    fk_serial_write_hex64(storage_probe);
    fk_serial_write("\n");
    fk_console_report();
    sample_frame = fk_pmm_alloc_frame();
    fk_serial_write("PMM sample frame=");
    fk_serial_write_hex64(sample_frame);
    fk_serial_write("\n");
    fk_pmm_free_frame(sample_frame);
    heap_probe = fk_heap_alloc(96);
    fk_heap_report();
    fk_serial_write("Heap probe=");
    fk_serial_write_hex64((uint64_t)(uintptr_t)heap_probe);
    fk_serial_write("\n");
    fk_heap_free(heap_probe);
    slab_probe = fk_slab_alloc(48);
    fk_slab_report();
    fk_serial_write("Slab probe=");
    fk_serial_write_hex64((uint64_t)(uintptr_t)slab_probe);
    fk_serial_write("\n");
    fk_slab_free(slab_probe, 48);
    fk_triple_kernel_report();

    idle_forever();
}
