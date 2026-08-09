#include "../../include/fractal_kernel.h"

struct idt_entry {
    uint16_t offset_low;
    uint16_t selector;
    uint8_t ist;
    uint8_t type_attr;
    uint16_t offset_mid;
    uint32_t offset_high;
    uint32_t zero;
} __attribute__((packed));

struct idt_descriptor {
    uint16_t limit;
    uint64_t base;
} __attribute__((packed));

static struct idt_entry idt[256];
struct fk_interrupt_frame;
__attribute__((interrupt)) extern void fk_timer_irq(struct fk_interrupt_frame *frame);
__attribute__((interrupt)) extern void fk_keyboard_irq(struct fk_interrupt_frame *frame);
__attribute__((interrupt)) extern void fk_syscall_irq(struct fk_interrupt_frame *frame);

static void default_interrupt_stub(void) {
    fk_serial_write("FractalOS: unexpected interrupt\n");
    for (;;) {
        __asm__ volatile ("hlt");
    }
}

static void set_gate(uint8_t vector, void (*handler)(void)) {
    uint8_t type_attr = 0x8e;
    uint64_t address = (uint64_t)handler;
    idt[vector].offset_low = address & 0xffff;
    idt[vector].selector = 0x08;
    idt[vector].ist = 0;
    idt[vector].type_attr = type_attr;
    idt[vector].offset_mid = (address >> 16) & 0xffff;
    idt[vector].offset_high = (address >> 32) & 0xffffffff;
    idt[vector].zero = 0;
}

static void set_gate_with_attr(uint8_t vector, void (*handler)(void), uint8_t type_attr) {
    uint64_t address = (uint64_t)handler;
    idt[vector].offset_low = address & 0xffff;
    idt[vector].selector = 0x08;
    idt[vector].ist = 0;
    idt[vector].type_attr = type_attr;
    idt[vector].offset_mid = (address >> 16) & 0xffff;
    idt[vector].offset_high = (address >> 32) & 0xffffffff;
    idt[vector].zero = 0;
}

void fk_idt_init(void) {
    for (uint16_t i = 0; i < 256; i++) {
        set_gate((uint8_t)i, default_interrupt_stub);
    }
    set_gate(32, (void (*)(void))fk_timer_irq);
    set_gate(33, (void (*)(void))fk_keyboard_irq);
    set_gate_with_attr(128, (void (*)(void))fk_syscall_irq, 0xee);

    struct idt_descriptor idtr = {
        .limit = sizeof(idt) - 1,
        .base = (uint64_t)&idt,
    };
    __asm__ volatile ("lidt %0" : : "m"(idtr) : "memory");
}
