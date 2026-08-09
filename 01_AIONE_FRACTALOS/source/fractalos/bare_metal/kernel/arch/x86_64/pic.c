#include "../../include/fractal_kernel.h"
#include "port_io.h"

#define PIC1 0x20
#define PIC2 0xa0
#define PIC1_COMMAND PIC1
#define PIC1_DATA (PIC1 + 1)
#define PIC2_COMMAND PIC2
#define PIC2_DATA (PIC2 + 1)

#define ICW1_ICW4 0x01
#define ICW1_INIT 0x10
#define ICW4_8086 0x01

static void io_wait(void) {
    outb(0x80, 0);
}

void fk_pic_init(void) {
    outb(PIC1_COMMAND, ICW1_INIT | ICW1_ICW4);
    io_wait();
    outb(PIC2_COMMAND, ICW1_INIT | ICW1_ICW4);
    io_wait();

    outb(PIC1_DATA, 0x20);
    io_wait();
    outb(PIC2_DATA, 0x28);
    io_wait();

    outb(PIC1_DATA, 4);
    io_wait();
    outb(PIC2_DATA, 2);
    io_wait();

    outb(PIC1_DATA, ICW4_8086);
    io_wait();
    outb(PIC2_DATA, ICW4_8086);
    io_wait();

    /*
     * Firmware/bootloader masks are not a safe contract for our early kernel.
     * Keep only PIT timer (IRQ0) and PS/2 keyboard (IRQ1) unmasked; everything
     * else stays quiet until FractalOS has a real device manager/APIC layer.
     */
    outb(PIC1_DATA, 0xfc);
    outb(PIC2_DATA, 0xff);
}

void fk_pic_eoi(uint8_t irq) {
    if (irq >= 8) {
        outb(PIC2_COMMAND, 0x20);
    }
    outb(PIC1_COMMAND, 0x20);
}
