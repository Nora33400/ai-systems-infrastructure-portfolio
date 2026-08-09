CC ?= x86_64-elf-gcc
LD ?= x86_64-elf-ld
OBJCOPY ?= x86_64-elf-objcopy

BUILD_DIR := build
KERNEL := $(BUILD_DIR)/fractal_kernel.elf

CFLAGS := -std=c11 -ffreestanding -fno-stack-protector -fno-stack-check -fno-lto -fno-pic -m64 -march=x86-64 -mcmodel=kernel -mno-red-zone -Wall -Wextra -O2 -Ikernel/include
LDFLAGS := -nostdlib -static -z max-page-size=0x1000 -T kernel/linker.ld
OBJS := \
	$(BUILD_DIR)/boot.o \
	$(BUILD_DIR)/fractal_kernel.o \
	$(BUILD_DIR)/serial.o \
	$(BUILD_DIR)/gdt.o \
	$(BUILD_DIR)/idt.o \
	$(BUILD_DIR)/pic.o \
	$(BUILD_DIR)/keyboard.o \
	$(BUILD_DIR)/timer.o \
	$(BUILD_DIR)/syscall.o \
	$(BUILD_DIR)/console.o \
	$(BUILD_DIR)/task.o \
	$(BUILD_DIR)/userspace.o \
	$(BUILD_DIR)/regime.o \
	$(BUILD_DIR)/semantic_memory.o \
	$(BUILD_DIR)/universe.o \
	$(BUILD_DIR)/illusion.o \
	$(BUILD_DIR)/foundry.o \
	$(BUILD_DIR)/proofstate.o \
	$(BUILD_DIR)/desktop_plane.o \
	$(BUILD_DIR)/scientific_formula.o \
	$(BUILD_DIR)/vfs.o \
	$(BUILD_DIR)/package.o \
	$(BUILD_DIR)/storage_plane.o \
	$(BUILD_DIR)/pmm.o \
	$(BUILD_DIR)/heap.o \
	$(BUILD_DIR)/slab.o \
	$(BUILD_DIR)/vmm.o \
	$(BUILD_DIR)/scheduler.o \
	$(BUILD_DIR)/triple_kernel.o

.PHONY: all clean iso

all: $(KERNEL)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/boot.o: kernel/boot.S | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/fractal_kernel.o: kernel/fractal_kernel.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/serial.o: kernel/arch/x86_64/serial.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/gdt.o: kernel/arch/x86_64/gdt.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/idt.o: kernel/arch/x86_64/idt.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/pic.o: kernel/arch/x86_64/pic.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/keyboard.o: kernel/arch/x86_64/keyboard.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -mgeneral-regs-only -c $< -o $@

$(BUILD_DIR)/timer.o: kernel/arch/x86_64/timer.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -mgeneral-regs-only -c $< -o $@

$(BUILD_DIR)/syscall.o: kernel/core/syscall.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -mgeneral-regs-only -c $< -o $@

$(BUILD_DIR)/console.o: kernel/core/console.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/task.o: kernel/core/task.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/userspace.o: kernel/core/userspace.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/regime.o: kernel/core/regime.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/semantic_memory.o: kernel/core/semantic_memory.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/universe.o: kernel/core/universe.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/illusion.o: kernel/core/illusion.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/foundry.o: kernel/core/foundry.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/proofstate.o: kernel/core/proofstate.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/desktop_plane.o: kernel/core/desktop_plane.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/scientific_formula.o: kernel/core/scientific_formula.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/vfs.o: kernel/core/vfs.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/package.o: kernel/core/package.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/storage_plane.o: kernel/core/storage_plane.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/pmm.o: kernel/core/pmm.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/heap.o: kernel/core/heap.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/slab.o: kernel/core/slab.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/vmm.o: kernel/core/vmm.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/scheduler.o: kernel/core/scheduler.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/triple_kernel.o: kernel/core/triple_kernel.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(KERNEL): $(OBJS)
	$(LD) $(LDFLAGS) $^ -o $@

iso: $(KERNEL)
	@echo "Copy Limine binaries into build/iso_root and run xorriso in the next stage."

clean:
	rm -rf $(BUILD_DIR)
