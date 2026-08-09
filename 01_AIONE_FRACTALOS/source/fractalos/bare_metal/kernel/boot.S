.section .text
.global _start
.extern fractal_kernel_main

_start:
    cli
    lea stack_top(%rip), %rsp
    call fractal_kernel_main

.halt:
    hlt
    jmp .halt

.section .bss
.align 16
stack_bottom:
    .skip 65536
stack_top:
