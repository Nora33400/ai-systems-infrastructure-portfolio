#include "../include/fractal_kernel.h"

#define FK_PAGE_PRESENT 0x001ull
#define FK_PAGE_WRITABLE 0x002ull
#define FK_PAGE_LARGE 0x080ull
#define FK_VMM_WINDOW_2M (2ull * 1024ull * 1024ull)
#define FK_VMM_WINDOW_1G (512ull * FK_VMM_WINDOW_2M)

static uint64_t pml4[512] __attribute__((aligned(4096)));
static uint64_t low_pdpt[512] __attribute__((aligned(4096)));
static uint64_t low_pd[512] __attribute__((aligned(4096)));
static uint64_t high_pdpt[512] __attribute__((aligned(4096)));
static uint64_t high_pd[512] __attribute__((aligned(4096)));
static uint64_t vmm_bytes = 0;

static uint64_t page_align_down(uint64_t value, uint64_t alignment) {
    return value & ~(alignment - 1);
}

static uint64_t pml4_index(uint64_t address) {
    return (address >> 39) & 0x1ffull;
}

static uint64_t pdpt_index(uint64_t address) {
    return (address >> 30) & 0x1ffull;
}

static void clear_tables(void) {
    for (uint64_t i = 0; i < 512; i++) {
        pml4[i] = 0;
        low_pdpt[i] = 0;
        low_pd[i] = 0;
        high_pdpt[i] = 0;
        high_pd[i] = 0;
    }
}

static uint64_t kernel_virtual_to_physical(
    uint64_t address,
    uint64_t kernel_physical_base,
    uint64_t kernel_virtual_base
) {
    return address - kernel_virtual_base + kernel_physical_base;
}

void fk_vmm_init(struct fk_boot_context *ctx, uint64_t kernel_physical_base, uint64_t kernel_virtual_base) {
    uint64_t kernel_window_base = page_align_down(kernel_virtual_base, FK_VMM_WINDOW_1G);
    uint64_t kernel_phys_window_base = page_align_down(kernel_physical_base, FK_VMM_WINDOW_1G);
    uint64_t pml4_phys = 0;
    uint64_t low_pdpt_phys = 0;
    uint64_t low_pd_phys = 0;
    uint64_t high_pdpt_phys = 0;
    uint64_t high_pd_phys = 0;

    clear_tables();

    pml4_phys = kernel_virtual_to_physical((uint64_t)(uintptr_t)&pml4[0], kernel_physical_base, kernel_virtual_base);
    low_pdpt_phys = kernel_virtual_to_physical((uint64_t)(uintptr_t)&low_pdpt[0], kernel_physical_base, kernel_virtual_base);
    low_pd_phys = kernel_virtual_to_physical((uint64_t)(uintptr_t)&low_pd[0], kernel_physical_base, kernel_virtual_base);
    high_pdpt_phys = kernel_virtual_to_physical((uint64_t)(uintptr_t)&high_pdpt[0], kernel_physical_base, kernel_virtual_base);
    high_pd_phys = kernel_virtual_to_physical((uint64_t)(uintptr_t)&high_pd[0], kernel_physical_base, kernel_virtual_base);

    pml4[0] = low_pdpt_phys | FK_PAGE_PRESENT | FK_PAGE_WRITABLE;
    low_pdpt[0] = low_pd_phys | FK_PAGE_PRESENT | FK_PAGE_WRITABLE;
    for (uint64_t i = 0; i < 512; i++) {
        low_pd[i] = (i * FK_VMM_WINDOW_2M) | FK_PAGE_PRESENT | FK_PAGE_WRITABLE | FK_PAGE_LARGE;
    }

    pml4[pml4_index(kernel_window_base)] = high_pdpt_phys | FK_PAGE_PRESENT | FK_PAGE_WRITABLE;
    high_pdpt[pdpt_index(kernel_window_base)] = high_pd_phys | FK_PAGE_PRESENT | FK_PAGE_WRITABLE;
    for (uint64_t i = 0; i < 512; i++) {
        high_pd[i] = (kernel_phys_window_base + i * FK_VMM_WINDOW_2M) | FK_PAGE_PRESENT | FK_PAGE_WRITABLE | FK_PAGE_LARGE;
    }

    /*
     * Keep Limine's page tables for the first real boot. The prototype tables
     * above are a preview map, but replacing CR3 with 2 MiB pages is unsafe when
     * the bootloader places the kernel at a non-2MiB-aligned physical base or
     * when framebuffer mappings live outside our early identity window.
     */
    (void)pml4_phys;
    vmm_bytes = 2ull * FK_VMM_WINDOW_1G;
    fk_serial_write("VMM preview ready; preserving Limine CR3\n");

    if (ctx) {
        ctx->kernel_physical_base = kernel_physical_base;
        ctx->kernel_virtual_base = kernel_virtual_base;
        ctx->vmm_mapped_bytes = vmm_bytes;
        ctx->vmm_ready = 1;
    }
}

uint64_t fk_vmm_mapped_bytes(void) {
    return vmm_bytes;
}

void fk_vmm_report(void) {
    fk_serial_write("VMM mapped_bytes=");
    fk_serial_write_hex64(vmm_bytes);
    fk_serial_write("\n");
}
