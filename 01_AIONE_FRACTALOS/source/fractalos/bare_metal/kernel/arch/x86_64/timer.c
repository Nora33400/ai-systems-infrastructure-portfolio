#include "../../include/fractal_kernel.h"
#include "port_io.h"

#define PIT_COMMAND 0x43
#define PIT_CHANNEL0 0x40
#define PIT_BASE_FREQUENCY 1193182u

struct fk_interrupt_frame {
    uint64_t rip;
    uint64_t cs;
    uint64_t rflags;
    uint64_t rsp;
    uint64_t ss;
};

static volatile uint64_t timer_ticks = 0;
static uint32_t timer_frequency = 0;

__attribute__((interrupt))
void fk_timer_irq(struct fk_interrupt_frame *frame) {
    (void)frame;
    timer_ticks += 1;
    fk_pic_eoi(0);
}

void fk_timer_init(struct fk_boot_context *ctx, uint32_t frequency_hz) {
    uint32_t frequency = frequency_hz == 0 ? 100 : frequency_hz;
    uint32_t divisor = PIT_BASE_FREQUENCY / frequency;
    if (divisor == 0) {
        divisor = 1;
    }

    timer_frequency = PIT_BASE_FREQUENCY / divisor;
    outb(PIT_COMMAND, 0x36);
    outb(PIT_CHANNEL0, (uint8_t)(divisor & 0xff));
    outb(PIT_CHANNEL0, (uint8_t)((divisor >> 8) & 0xff));

    if (ctx) {
        ctx->timer_ready = 1;
    }
}

uint64_t fk_timer_ticks(void) {
    return timer_ticks;
}

uint32_t fk_timer_frequency_hz(void) {
    return timer_frequency;
}

void fk_timer_report(void) {
    fk_serial_write("Timer frequency=");
    fk_serial_write_hex64(timer_frequency);
    fk_serial_write(" ticks=");
    fk_serial_write_hex64(timer_ticks);
    fk_serial_write("\n");
}
