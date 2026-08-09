ENTRY(_start)

SECTIONS
{
    . = 0xffffffff80000000;

    .text : ALIGN(4K) {
        *(.text .text.*)
    }

    .rodata : ALIGN(4K) {
        *(.rodata .rodata.*)
        *(.limine_requests_start)
        *(.limine_requests)
        *(.limine_requests_end)
    }

    .data : ALIGN(4K) {
        *(.data .data.*)
    }

    .bss : ALIGN(4K) {
        *(COMMON)
        *(.bss .bss.*)
    }
}
