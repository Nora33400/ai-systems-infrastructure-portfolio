#include "../include/fractal_kernel.h"

#define FK_CONSOLE_CELL_W 8ull
#define FK_CONSOLE_CELL_H 12ull
#define FK_CONSOLE_MAX_COLS 128ull
#define FK_CONSOLE_MAX_ROWS 64ull
#define FK_SHELL_INPUT_MAX 64u
#define FK_CONSOLE_BG 0x00101814u
#define FK_CONSOLE_FG 0x00d7fff1u
#define FK_CONSOLE_ACCENT 0x0034d1bfu

static uint32_t *console_fb = 0;
static struct fk_boot_context *console_ctx = 0;
static uint64_t console_width = 0;
static uint64_t console_height = 0;
static uint64_t console_pitch = 0;
static uint64_t console_cols = 0;
static uint64_t console_rows = 0;
static uint64_t cursor_col = 0;
static uint64_t cursor_row = 0;
static uint64_t console_chars_written = 0;
static char shell_input[FK_SHELL_INPUT_MAX];
static uint64_t shell_input_len = 0;
static uint64_t shell_command_count = 0;

static void console_put_char(char ch);
static void fill_rect(uint64_t x, uint64_t y, uint64_t w, uint64_t h, uint32_t color);
void fk_console_write(const char *text);

static void write_hex_line(const char *label, uint64_t value) {
    fk_console_write(label);
    fk_console_write("0x");
    for (int shift = 60; shift >= 0; shift -= 4) {
        char digit = "0123456789abcdef"[(value >> shift) & 0xf];
        console_put_char(digit);
    }
    fk_console_write("\n");
}

static uint8_t streq(const char *left, const char *right) {
    uint64_t i = 0;
    if (!left || !right) {
        return 0;
    }
    while (left[i] && right[i]) {
        if (left[i] != right[i]) {
            return 0;
        }
        i += 1;
    }
    return left[i] == right[i];
}

static void shell_prompt(void) {
    fk_console_write("> ");
}

static void shell_help(void) {
    fk_console_write("help tasks syscalls score clear ping apps launch-echo regimes regime-latency memory-map promote-page universe universe-chaos universe-evolution shadow shadow-shift contradict foundry foundry-batch proofs prove-state desktop overlay overlay-cycle formulas formula-storage vfs vfs-open packages package-policy storage storage-snapshot\n");
}

static void shell_tasks(void) {
    write_hex_line("tasks.count=", fk_task_count());
    write_hex_line("tasks.current=", fk_task_current_id());
    write_hex_line("tasks.capacity=", fk_task_capacity());
}

static void shell_syscalls(void) {
    write_hex_line("syscalls.count=", fk_syscall_count());
    write_hex_line("syscalls.last=", fk_syscall_last_id());
}

static void shell_score(void) {
    write_hex_line("score.scheduler=", fk_scheduler_score(console_ctx));
    write_hex_line("score.triple=", fk_triple_kernel_score());
}

static void shell_apps(void) {
    write_hex_line("userspace.programs=", fk_userspace_program_count());
    write_hex_line("userspace.launches=", fk_userspace_launch_count());
}

static void shell_launch_echo(void) {
    write_hex_line("launch.echo=", fk_userspace_launch_by_name("echo"));
}

static void shell_regimes(void) {
    write_hex_line("regimes.count=", fk_regime_count());
    write_hex_line("regimes.current=", fk_regime_current_id());
}

static void shell_regime_latency(void) {
    write_hex_line("regimes.select=", fk_regime_select(1));
}

static void shell_memory_map(void) {
    write_hex_line("semantic.classes=", fk_semantic_memory_class_count());
    write_hex_line("semantic.promoted=", fk_semantic_memory_promoted_pages());
}

static void shell_promote_page(void) {
    write_hex_line("semantic.promoted=", fk_semantic_memory_promote_pages(1));
}

static void shell_universe(void) {
    write_hex_line("universe.laws=", fk_universe_law_count());
    write_hex_line("universe.current=", fk_universe_current_law_id());
    write_hex_line("universe.force=", fk_universe_field_force_level());
}

static void shell_universe_chaos(void) {
    write_hex_line("universe.select=", fk_universe_select_law(3));
}

static void shell_universe_evolution(void) {
    write_hex_line("universe.select=", fk_universe_select_law(4));
}

static void shell_shadow(void) {
    write_hex_line("illusion.mode=", fk_illusion_mode_id());
    write_hex_line("illusion.depth=", fk_illusion_shadow_depth());
    write_hex_line("illusion.contradictions=", fk_illusion_contradiction_count());
}

static void shell_shadow_shift(void) {
    write_hex_line("illusion.select=", fk_illusion_shift_mode(3));
}

static void shell_contradict(void) {
    write_hex_line("illusion.contradictions=", fk_illusion_raise_contradiction());
}

static void shell_foundry(void) {
    write_hex_line("foundry.lines=", fk_foundry_line_count());
    write_hex_line("foundry.batches=", fk_foundry_batch_count());
}

static void shell_foundry_batch(void) {
    write_hex_line("foundry.batches=", fk_foundry_run_batch(2));
}

static void shell_proofs(void) {
    write_hex_line("proof.level=", fk_proofstate_attestation_level());
    write_hex_line("proof.promotions=", fk_proofstate_promotion_count());
}

static void shell_prove_state(void) {
    write_hex_line("proof.level=", fk_proofstate_promote(4));
}

static void shell_desktop(void) {
    write_hex_line("desktop.layers=", fk_desktop_plane_layer_count());
    write_hex_line("desktop.overlay=", fk_desktop_plane_overlay_mode());
    write_hex_line("desktop.panels=", fk_desktop_plane_persistent_panels());
}

static void shell_overlay(void) {
    write_hex_line("overlay.mode=", fk_desktop_plane_overlay_mode());
}

static void shell_overlay_cycle(void) {
    write_hex_line("overlay.mode=", fk_desktop_plane_cycle_overlay());
}

static void shell_formulas(void) {
    write_hex_line("formulas.count=", fk_scientific_formula_count());
    write_hex_line("formulas.activation=", fk_scientific_formula_activation());
    write_hex_line("formulas.safety=", fk_scientific_formula_safety());
}

static void shell_formula_storage(void) {
    write_hex_line("formulas.activation=", fk_scientific_formula_boost_storage());
}

static void shell_vfs(void) {
    write_hex_line("vfs.mounts=", fk_vfs_mount_count());
    write_hex_line("vfs.nodes=", fk_vfs_node_count());
    write_hex_line("vfs.opens=", fk_vfs_open_file_count());
}

static void shell_vfs_open(void) {
    write_hex_line("vfs.open.home=", fk_vfs_open_home_readme());
}

static void shell_packages(void) {
    write_hex_line("packages.manifests=", fk_package_manifest_count());
    write_hex_line("packages.available=", fk_package_available_count());
}

static void shell_package_policy(void) {
    write_hex_line("packages.policy=", fk_package_policy_score());
}

static void shell_storage(void) {
    write_hex_line("storage.slots=", fk_storage_plane_slot_count());
    write_hex_line("storage.journal=", fk_storage_plane_journal_count());
    write_hex_line("storage.snapshots=", fk_storage_plane_snapshot_count());
    write_hex_line("storage.score=", fk_storage_plane_persistence_score());
}

static void shell_storage_snapshot(void) {
    write_hex_line("storage.snapshots=", fk_storage_plane_snapshot());
}

static void shell_clear(void) {
    fill_rect(0, 0, console_cols * FK_CONSOLE_CELL_W, console_rows * FK_CONSOLE_CELL_H, FK_CONSOLE_BG);
    cursor_col = 0;
    cursor_row = 0;
}

static void shell_execute(const char *command) {
    shell_command_count += 1;
    if (console_ctx) {
        console_ctx->shell_command_count = shell_command_count;
    }
    if (streq(command, "help")) {
        shell_help();
    } else if (streq(command, "tasks")) {
        shell_tasks();
    } else if (streq(command, "syscalls")) {
        shell_syscalls();
    } else if (streq(command, "score")) {
        shell_score();
    } else if (streq(command, "apps")) {
        shell_apps();
    } else if (streq(command, "launch-echo")) {
        shell_launch_echo();
    } else if (streq(command, "regimes")) {
        shell_regimes();
    } else if (streq(command, "regime-latency")) {
        shell_regime_latency();
    } else if (streq(command, "memory-map")) {
        shell_memory_map();
    } else if (streq(command, "promote-page")) {
        shell_promote_page();
    } else if (streq(command, "universe")) {
        shell_universe();
    } else if (streq(command, "universe-chaos")) {
        shell_universe_chaos();
    } else if (streq(command, "universe-evolution")) {
        shell_universe_evolution();
    } else if (streq(command, "shadow")) {
        shell_shadow();
    } else if (streq(command, "shadow-shift")) {
        shell_shadow_shift();
    } else if (streq(command, "contradict")) {
        shell_contradict();
    } else if (streq(command, "foundry")) {
        shell_foundry();
    } else if (streq(command, "foundry-batch")) {
        shell_foundry_batch();
    } else if (streq(command, "proofs")) {
        shell_proofs();
    } else if (streq(command, "prove-state")) {
        shell_prove_state();
    } else if (streq(command, "desktop")) {
        shell_desktop();
    } else if (streq(command, "overlay")) {
        shell_overlay();
    } else if (streq(command, "overlay-cycle")) {
        shell_overlay_cycle();
    } else if (streq(command, "formulas")) {
        shell_formulas();
    } else if (streq(command, "formula-storage")) {
        shell_formula_storage();
    } else if (streq(command, "vfs")) {
        shell_vfs();
    } else if (streq(command, "vfs-open")) {
        shell_vfs_open();
    } else if (streq(command, "packages")) {
        shell_packages();
    } else if (streq(command, "package-policy")) {
        shell_package_policy();
    } else if (streq(command, "storage")) {
        shell_storage();
    } else if (streq(command, "storage-snapshot")) {
        shell_storage_snapshot();
    } else if (streq(command, "clear")) {
        shell_clear();
    } else if (streq(command, "ping")) {
        write_hex_line("ping=", fk_syscall_invoke(1, 0, 0, 0));
    } else if (command[0] == 0) {
        return;
    } else {
        fk_console_write("unknown command\n");
    }
}

static void put_pixel(uint64_t x, uint64_t y, uint32_t color) {
    if (!console_fb || x >= console_width || y >= console_height) {
        return;
    }
    console_fb[(y * (console_pitch / 4ull)) + x] = color;
}

static void fill_rect(uint64_t x, uint64_t y, uint64_t w, uint64_t h, uint32_t color) {
    for (uint64_t yy = y; yy < y + h && yy < console_height; yy++) {
        for (uint64_t xx = x; xx < x + w && xx < console_width; xx++) {
            put_pixel(xx, yy, color);
        }
    }
}

static void scroll_if_needed(void) {
    uint64_t stride;
    uint64_t visible_height;
    if (!console_fb || cursor_row < console_rows) {
        return;
    }
    stride = console_pitch / 4ull;
    visible_height = console_rows * FK_CONSOLE_CELL_H;
    for (uint64_t y = 0; y + FK_CONSOLE_CELL_H < visible_height; y++) {
        uint64_t from = (y + FK_CONSOLE_CELL_H) * stride;
        uint64_t to = y * stride;
        for (uint64_t x = 0; x < stride; x++) {
            console_fb[to + x] = console_fb[from + x];
        }
    }
    fill_rect(0, visible_height - FK_CONSOLE_CELL_H, console_cols * FK_CONSOLE_CELL_W, FK_CONSOLE_CELL_H, FK_CONSOLE_BG);
    cursor_row = console_rows - 1;
}

static void draw_cell(uint64_t col, uint64_t row, char ch) {
    uint64_t x0 = col * FK_CONSOLE_CELL_W;
    uint64_t y0 = row * FK_CONSOLE_CELL_H;
    uint8_t seed = (uint8_t)ch;
    fill_rect(x0, y0, FK_CONSOLE_CELL_W, FK_CONSOLE_CELL_H, FK_CONSOLE_BG);
    if (ch == ' ') {
        return;
    }
    for (uint64_t y = 1; y < FK_CONSOLE_CELL_H - 1; y++) {
        for (uint64_t x = 1; x < FK_CONSOLE_CELL_W - 1; x++) {
            uint8_t mask = (uint8_t)(1u << ((x + y) & 7u));
            if ((seed & mask) != 0 || y == 1 || y == FK_CONSOLE_CELL_H - 2) {
                put_pixel(x0 + x, y0 + y, FK_CONSOLE_FG);
            }
        }
    }
    put_pixel(x0, y0, FK_CONSOLE_ACCENT);
    put_pixel(x0 + FK_CONSOLE_CELL_W - 1, y0 + FK_CONSOLE_CELL_H - 1, FK_CONSOLE_ACCENT);
}

static void advance_cursor(void) {
    cursor_col += 1;
    if (cursor_col >= console_cols) {
        cursor_col = 0;
        cursor_row += 1;
        scroll_if_needed();
    }
}

static void console_put_char(char ch) {
    if (!console_fb || console_cols == 0 || console_rows == 0) {
        return;
    }
    if (ch == '\r') {
        return;
    }
    if (ch == '\n') {
        cursor_col = 0;
        cursor_row += 1;
        scroll_if_needed();
        return;
    }
    if (ch == '\b') {
        if (cursor_col > 0) {
            cursor_col -= 1;
        }
        draw_cell(cursor_col, cursor_row, ' ');
        return;
    }
    draw_cell(cursor_col, cursor_row, ch);
    console_chars_written += 1;
    advance_cursor();
}

void fk_console_init(struct fk_boot_context *ctx, uint64_t framebuffer_address, uint64_t width, uint64_t height, uint64_t pitch) {
    console_fb = (uint32_t *)(uintptr_t)framebuffer_address;
    console_ctx = ctx;
    console_width = width;
    console_height = height;
    console_pitch = pitch;
    console_cols = width / FK_CONSOLE_CELL_W;
    console_rows = height / FK_CONSOLE_CELL_H;
    if (console_cols > FK_CONSOLE_MAX_COLS) {
        console_cols = FK_CONSOLE_MAX_COLS;
    }
    if (console_rows > FK_CONSOLE_MAX_ROWS) {
        console_rows = FK_CONSOLE_MAX_ROWS;
    }
    cursor_col = 0;
    cursor_row = 0;
    console_chars_written = 0;
    shell_input_len = 0;
    shell_command_count = 0;
    fill_rect(0, 0, console_cols * FK_CONSOLE_CELL_W, console_rows * FK_CONSOLE_CELL_H, FK_CONSOLE_BG);
    if (ctx) {
        ctx->console_ready = 1;
        ctx->console_columns = console_cols;
        ctx->console_rows = console_rows;
        ctx->console_written_chars = 0;
        ctx->shell_ready = 1;
        ctx->shell_command_count = 0;
    }
}

void fk_console_write(const char *text) {
    if (!text) {
        return;
    }
    while (*text) {
        console_put_char(*text++);
    }
}

void fk_console_tick(struct fk_boot_context *ctx) {
    uint8_t ch = 0;
    while ((ch = fk_keyboard_pop_char()) != 0) {
        if (ch == '\n') {
            console_put_char('\n');
            shell_input[shell_input_len] = 0;
            shell_execute(shell_input);
            shell_input_len = 0;
            shell_prompt();
        } else if (ch == '\b') {
            if (shell_input_len > 0) {
                shell_input_len -= 1;
            }
            console_put_char('\b');
        } else if (shell_input_len + 1 < FK_SHELL_INPUT_MAX) {
            shell_input[shell_input_len++] = (char)ch;
            console_put_char((char)ch);
        }
        if (ctx) {
            ctx->keyboard_buffered_keys = fk_keyboard_buffered_keys();
        }
    }
    if (ctx) {
        ctx->console_columns = console_cols;
        ctx->console_rows = console_rows;
        ctx->console_written_chars = console_chars_written;
        ctx->shell_command_count = shell_command_count;
    }
}

void fk_console_report(void) {
    fk_serial_write("Console grid=");
    fk_serial_write_hex64(console_cols);
    fk_serial_write("x");
    fk_serial_write_hex64(console_rows);
    fk_serial_write(" chars=");
    fk_serial_write_hex64(console_chars_written);
    fk_serial_write(" shell_commands=");
    fk_serial_write_hex64(shell_command_count);
    fk_serial_write("\n");
}
