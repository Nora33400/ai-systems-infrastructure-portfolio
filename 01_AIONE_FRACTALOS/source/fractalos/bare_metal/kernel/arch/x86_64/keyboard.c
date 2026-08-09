#include "../../include/fractal_kernel.h"
#include "port_io.h"

#define PS2_DATA_PORT 0x60
#define PS2_STATUS_PORT 0x64
#define FK_KEYBOARD_BUFFER_CAPACITY 64

struct fk_interrupt_frame {
    uint64_t rip;
    uint64_t cs;
    uint64_t rflags;
    uint64_t rsp;
    uint64_t ss;
};

static uint8_t keyboard_buffer[FK_KEYBOARD_BUFFER_CAPACITY];
static uint64_t keyboard_head = 0;
static uint64_t keyboard_tail = 0;
static uint8_t last_scancode = 0;

static uint8_t scancode_to_ascii(uint8_t scancode) {
    static const uint8_t map[128] = {
        0, 27, '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', '\b',
        '\t', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\n', 0,
        'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', '\'', '`', 0, '\\', 'z',
        'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 0, '*', 0, ' ', 0
    };
    if (scancode < 128) {
        return map[scancode];
    }
    return 0;
}

static void keyboard_push(uint8_t ch) {
    uint64_t next_head = (keyboard_head + 1) % FK_KEYBOARD_BUFFER_CAPACITY;
    if (next_head == keyboard_tail) {
        return;
    }
    keyboard_buffer[keyboard_head] = ch;
    keyboard_head = next_head;
}

__attribute__((interrupt))
void fk_keyboard_irq(struct fk_interrupt_frame *frame) {
    uint8_t scancode;
    uint8_t ascii;
    (void)frame;
    scancode = inb(PS2_DATA_PORT);
    last_scancode = scancode;
    if ((scancode & 0x80) == 0) {
        ascii = scancode_to_ascii(scancode);
        if (ascii) {
            keyboard_push(ascii);
        }
    }
    fk_pic_eoi(1);
}

void fk_keyboard_init(struct fk_boot_context *ctx) {
    while (inb(PS2_STATUS_PORT) & 0x01) {
        (void)inb(PS2_DATA_PORT);
    }
    keyboard_head = 0;
    keyboard_tail = 0;
    last_scancode = 0;
    if (ctx) {
        ctx->keyboard_ready = 1;
        ctx->keyboard_buffered_keys = 0;
    }
}

uint64_t fk_keyboard_buffered_keys(void) {
    if (keyboard_head >= keyboard_tail) {
        return keyboard_head - keyboard_tail;
    }
    return FK_KEYBOARD_BUFFER_CAPACITY - keyboard_tail + keyboard_head;
}

uint8_t fk_keyboard_pop_char(void) {
    uint8_t value;
    if (keyboard_head == keyboard_tail) {
        return 0;
    }
    value = keyboard_buffer[keyboard_tail];
    keyboard_tail = (keyboard_tail + 1) % FK_KEYBOARD_BUFFER_CAPACITY;
    return value;
}

void fk_keyboard_report(void) {
    fk_serial_write("Keyboard buffered=");
    fk_serial_write_hex64(fk_keyboard_buffered_keys());
    fk_serial_write(" last_scancode=");
    fk_serial_write_hex64(last_scancode);
    fk_serial_write("\n");
}
