#include "../../include/fractal_kernel.h"
#include "port_io.h"

#define COM1 0x3f8

static int serial_transmit_empty(void) {
    return inb(COM1 + 5) & 0x20;
}

void fk_serial_init(void) {
    outb(COM1 + 1, 0x00);
    outb(COM1 + 3, 0x80);
    outb(COM1 + 0, 0x03);
    outb(COM1 + 1, 0x00);
    outb(COM1 + 3, 0x03);
    outb(COM1 + 2, 0xc7);
    outb(COM1 + 4, 0x0b);
}

static void serial_write_char(char c) {
    for (uint32_t spin = 0; spin < 100000 && !serial_transmit_empty(); spin++) {
        __asm__ volatile ("pause");
    }
    outb(COM1, (uint8_t)c);
}

void fk_serial_write(const char *text) {
    if (!text) {
        return;
    }
    while (*text) {
        if (*text == '\n') {
            serial_write_char('\r');
        }
        serial_write_char(*text++);
    }
}

void fk_serial_write_hex64(uint64_t value) {
    static const char *hex = "0123456789abcdef";
    fk_serial_write("0x");
    for (int shift = 60; shift >= 0; shift -= 4) {
        serial_write_char(hex[(value >> shift) & 0xf]);
    }
}
