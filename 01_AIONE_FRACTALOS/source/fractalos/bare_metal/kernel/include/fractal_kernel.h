#ifndef FRACTAL_KERNEL_H
#define FRACTAL_KERNEL_H

#include <stddef.h>
#include <stdint.h>

#define FRACTAL_KERNEL_VERSION "0.5.0"
#define FK_PAGE_SIZE 4096ull

enum fk_kernel_vertex_id {
    FK_VERTEX_MATTER = 0,
    FK_VERTEX_MIND = 1,
    FK_VERTEX_MESH = 2
};

struct fk_kernel_vertex {
    enum fk_kernel_vertex_id id;
    const char *name;
    const char *purpose;
    uint64_t readiness;
};

struct fk_kernel_bridge {
    enum fk_kernel_vertex_id left;
    enum fk_kernel_vertex_id right;
    uint64_t strength;
};

struct fk_boot_context {
    uint64_t framebuffer_width;
    uint64_t framebuffer_height;
    uint64_t framebuffer_pitch;
    uint64_t framebuffer_address;
    uint64_t memory_map_entries;
    uint64_t usable_memory_bytes;
    uint64_t free_frame_count;
    uint64_t heap_reserved_frames;
    uint64_t heap_capacity_bytes;
    uint64_t slab_classes_ready;
    uint64_t slab_live_objects;
    uint64_t kernel_physical_base;
    uint64_t kernel_virtual_base;
    uint64_t vmm_mapped_bytes;
    uint64_t keyboard_buffered_keys;
    uint64_t syscall_count;
    uint64_t last_syscall_id;
    uint64_t console_columns;
    uint64_t console_rows;
    uint64_t console_written_chars;
    uint64_t task_capacity;
    uint64_t task_count;
    uint64_t current_task_id;
    uint64_t shell_command_count;
    uint64_t userspace_program_count;
    uint64_t userspace_launch_count;
    uint64_t userspace_last_program_id;
    uint64_t regime_count;
    uint64_t current_regime_id;
    uint64_t semantic_page_classes;
    uint64_t semantic_promoted_pages;
    uint64_t universe_law_count;
    uint64_t current_universe_law_id;
    uint64_t field_force_level;
    uint64_t illusion_mode_id;
    uint64_t shadow_dimension_depth;
    uint64_t contradiction_count;
    uint64_t foundry_line_count;
    uint64_t foundry_batch_count;
    uint64_t proof_attestation_level;
    uint64_t proof_promotion_count;
    uint64_t desktop_layer_count;
    uint64_t desktop_overlay_mode_id;
    uint64_t desktop_persistent_panels;
    uint64_t scientific_formula_count;
    uint64_t scientific_formula_activation;
    uint64_t scientific_formula_safety;
    uint64_t vfs_mount_count;
    uint64_t vfs_node_count;
    uint64_t vfs_open_file_count;
    uint64_t package_manifest_count;
    uint64_t package_available_count;
    uint64_t package_policy_score;
    uint64_t storage_slot_count;
    uint64_t storage_journal_count;
    uint64_t storage_snapshot_count;
    uint64_t storage_persistence_score;
    uint16_t framebuffer_bpp;
    uint8_t serial_ready;
    uint8_t gdt_ready;
    uint8_t idt_ready;
    uint8_t pic_ready;
    uint8_t timer_ready;
    uint8_t pmm_ready;
    uint8_t vmm_ready;
    uint8_t keyboard_ready;
    uint8_t syscall_ready;
    uint8_t console_ready;
    uint8_t task_ready;
    uint8_t shell_ready;
    uint8_t userspace_ready;
    uint8_t regime_ready;
    uint8_t semantic_memory_ready;
    uint8_t universe_ready;
    uint8_t illusion_ready;
    uint8_t foundry_ready;
    uint8_t proof_ready;
    uint8_t desktop_ready;
    uint8_t scientific_formula_ready;
    uint8_t vfs_ready;
    uint8_t package_ready;
    uint8_t storage_ready;
    uint8_t interrupts_enabled;
    uint8_t scheduler_ready;
    uint8_t triple_kernel_ready;
};

void fk_serial_init(void);
void fk_serial_write(const char *text);
void fk_serial_write_hex64(uint64_t value);

void fk_gdt_init(void);
void fk_idt_init(void);
void fk_panic(const char *message);
void fk_pic_init(void);
void fk_pic_eoi(uint8_t irq);
void fk_timer_init(struct fk_boot_context *ctx, uint32_t frequency_hz);
uint64_t fk_timer_ticks(void);
uint32_t fk_timer_frequency_hz(void);
void fk_timer_report(void);
void fk_pmm_init(struct fk_boot_context *ctx, uint64_t entry_count, const uint64_t *base_list, const uint64_t *length_list, const uint64_t *type_list);
uint64_t fk_pmm_usable_bytes(void);
uint64_t fk_pmm_total_regions(void);
uint64_t fk_pmm_usable_regions(void);
uint64_t fk_pmm_free_frames(void);
uint64_t fk_pmm_alloc_frame(void);
void fk_pmm_free_frame(uint64_t address);
void fk_pmm_report(void);
void fk_heap_init(struct fk_boot_context *ctx);
void *fk_heap_alloc(uint64_t size);
void fk_heap_free(void *ptr);
uint64_t fk_heap_capacity_bytes(void);
uint64_t fk_heap_used_bytes(void);
uint64_t fk_heap_reserved_frames(void);
void fk_heap_report(void);
void fk_slab_init(struct fk_boot_context *ctx);
void *fk_slab_alloc(uint64_t size);
void fk_slab_free(void *ptr, uint64_t size_hint);
uint64_t fk_slab_class_count(void);
uint64_t fk_slab_live_objects(void);
void fk_slab_report(void);
void fk_vmm_init(struct fk_boot_context *ctx, uint64_t kernel_physical_base, uint64_t kernel_virtual_base);
uint64_t fk_vmm_mapped_bytes(void);
void fk_vmm_report(void);
void fk_keyboard_init(struct fk_boot_context *ctx);
uint64_t fk_keyboard_buffered_keys(void);
uint8_t fk_keyboard_pop_char(void);
void fk_keyboard_report(void);
void fk_syscall_init(struct fk_boot_context *ctx);
uint64_t fk_syscall_count(void);
uint64_t fk_syscall_last_id(void);
uint64_t fk_syscall_dispatch(uint64_t id, uint64_t arg0, uint64_t arg1, uint64_t arg2);
uint64_t fk_syscall_invoke(uint64_t id, uint64_t arg0, uint64_t arg1, uint64_t arg2);
void fk_syscall_report(void);
void fk_console_init(struct fk_boot_context *ctx, uint64_t framebuffer_address, uint64_t width, uint64_t height, uint64_t pitch);
void fk_console_write(const char *text);
void fk_console_tick(struct fk_boot_context *ctx);
void fk_console_report(void);
void fk_task_init(struct fk_boot_context *ctx);
uint64_t fk_task_spawn_kernel(const char *name, uint8_t ring, uint8_t state);
uint64_t fk_task_count(void);
uint64_t fk_task_capacity(void);
uint64_t fk_task_current_id(void);
void fk_task_set_current(uint64_t task_id);
void fk_task_report(void);
void fk_userspace_init(struct fk_boot_context *ctx);
uint64_t fk_userspace_program_count(void);
uint64_t fk_userspace_launch_count(void);
uint64_t fk_userspace_last_program_id(void);
uint64_t fk_userspace_launch_by_name(const char *name);
void fk_userspace_report(void);
void fk_regime_init(struct fk_boot_context *ctx);
uint64_t fk_regime_count(void);
uint64_t fk_regime_current_id(void);
uint64_t fk_regime_select(uint64_t regime_id);
void fk_regime_report(void);
void fk_semantic_memory_init(struct fk_boot_context *ctx);
uint64_t fk_semantic_memory_class_count(void);
uint64_t fk_semantic_memory_promoted_pages(void);
uint64_t fk_semantic_memory_promote_pages(uint64_t pages);
void fk_semantic_memory_report(void);
void fk_universe_init(struct fk_boot_context *ctx);
uint64_t fk_universe_law_count(void);
uint64_t fk_universe_current_law_id(void);
uint64_t fk_universe_field_force_level(void);
uint64_t fk_universe_select_law(uint64_t law_id);
void fk_universe_report(void);
void fk_illusion_init(struct fk_boot_context *ctx);
uint64_t fk_illusion_mode_id(void);
uint64_t fk_illusion_shadow_depth(void);
uint64_t fk_illusion_contradiction_count(void);
uint64_t fk_illusion_shift_mode(uint64_t mode_id);
uint64_t fk_illusion_raise_contradiction(void);
void fk_illusion_report(void);
void fk_foundry_init(struct fk_boot_context *ctx);
uint64_t fk_foundry_line_count(void);
uint64_t fk_foundry_batch_count(void);
uint64_t fk_foundry_run_batch(uint64_t line_id);
void fk_foundry_report(void);
void fk_proofstate_init(struct fk_boot_context *ctx);
uint64_t fk_proofstate_attestation_level(void);
uint64_t fk_proofstate_promotion_count(void);
uint64_t fk_proofstate_promote(uint64_t grade);
void fk_proofstate_report(void);
void fk_desktop_plane_init(struct fk_boot_context *ctx);
uint64_t fk_desktop_plane_layer_count(void);
uint64_t fk_desktop_plane_overlay_mode(void);
uint64_t fk_desktop_plane_persistent_panels(void);
uint64_t fk_desktop_plane_cycle_overlay(void);
void fk_desktop_plane_report(void);
void fk_scientific_formula_init(struct fk_boot_context *ctx);
uint64_t fk_scientific_formula_count(void);
uint64_t fk_scientific_formula_activation(void);
uint64_t fk_scientific_formula_safety(void);
uint64_t fk_scientific_formula_boost_storage(void);
void fk_scientific_formula_report(void);
void fk_vfs_init(struct fk_boot_context *ctx);
uint64_t fk_vfs_mount_count(void);
uint64_t fk_vfs_node_count(void);
uint64_t fk_vfs_open_file_count(void);
uint64_t fk_vfs_open_home_readme(void);
void fk_vfs_report(void);
void fk_package_init(struct fk_boot_context *ctx);
uint64_t fk_package_manifest_count(void);
uint64_t fk_package_available_count(void);
uint64_t fk_package_policy_score(void);
void fk_package_report(void);
void fk_storage_plane_init(struct fk_boot_context *ctx);
uint64_t fk_storage_plane_slot_count(void);
uint64_t fk_storage_plane_journal_count(void);
uint64_t fk_storage_plane_snapshot_count(void);
uint64_t fk_storage_plane_persistence_score(void);
uint64_t fk_storage_plane_commit_journal(void);
uint64_t fk_storage_plane_snapshot(void);
void fk_storage_plane_report(void);

void fk_scheduler_init(struct fk_boot_context *ctx);
uint64_t fk_scheduler_score(const struct fk_boot_context *ctx);

void fk_triple_kernel_init(struct fk_boot_context *ctx);
uint64_t fk_triple_kernel_score(void);
const struct fk_kernel_vertex *fk_triple_kernel_vertices(void);
uint64_t fk_triple_kernel_vertex_count(void);
const struct fk_kernel_bridge *fk_triple_kernel_bridges(void);
uint64_t fk_triple_kernel_bridge_count(void);
void fk_triple_kernel_report(void);

#endif
