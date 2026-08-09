#include "../../include/fractal_kernel.h"

struct gdt_descriptor {
    uint16_t limit;
    uint64_t base;
} __attribute__((packed));

static uint64_t gdt[3];

static uint64_t gdt_entry(uint32_t base, uint32_t limit, uint8_t access, uint8_t flags) {
    return ((uint64_t)(limit & 0xffff))
        | (((uint64_t)(base & 0xffffff)) << 16)
        | (((uint64_t)access) << 40)
        | (((uint64_t)((limit >> 16) & 0x0f)) << 48)
        | (((uint64_t)(flags & 0x0f)) << 52)
        | (((uint64_t)((base >> 24) & 0xff)) << 56);
}

void fk_gdt_init(void) {
    gdt[0] = 0;
    gdt[1] = gdt_entry(0, 0xfffff, 0x9a, 0x0a);
    gdt[2] = gdt_entry(0, 0xfffff, 0x92, 0x0c);

    struct gdt_descriptor gdtr = {
        .limit = sizeof(gdt) - 1,
        .base = (uint64_t)&gdt,
    };

    __asm__ volatile ("lgdt %0" : : "m"(gdtr) : "memory");
    __asm__ volatile (
        "pushq $0x08\n"
        "leaq 1f(%%rip), %%rax\n"
        "pushq %%rax\n"
        "lretq\n"
        "1:\n"
        "movw $0x10, %%ax\n"
        "movw %%ax, %%ds\n"
        "movw %%ax, %%es\n"
        "movw %%ax, %%ss\n"
        "movw %%ax, %%fs\n"
        "movw %%ax, %%gs\n"
        :
        :
        : "rax", "memory"
    );
}
