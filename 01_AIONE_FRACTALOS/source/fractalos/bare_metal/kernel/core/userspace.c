#include "../include/fractal_kernel.h"

#define FK_USERSPACE_MAX_PROGRAMS 8u
#define FK_USERSPACE_NAME_BYTES 24u

struct fk_userspace_program {
    uint64_t id;
    char name[FK_USERSPACE_NAME_BYTES];
    const char *purpose;
};

static struct fk_userspace_program program_table[FK_USERSPACE_MAX_PROGRAMS];
static struct fk_boot_context *userspace_ctx = 0;
static uint64_t program_count = 0;
static uint64_t launch_count = 0;
static uint64_t last_program_id = 0;

static void copy_name(char *dst, const char *src) {
    uint64_t i = 0;
    if (!dst) {
        return;
    }
    if (!src) {
        dst[0] = 0;
        return;
    }
    for (; i + 1 < FK_USERSPACE_NAME_BYTES && src[i] != 0; i++) {
        dst[i] = src[i];
    }
    dst[i] = 0;
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

static void register_program(const char *name, const char *purpose) {
    struct fk_userspace_program *slot;
    if (program_count >= FK_USERSPACE_MAX_PROGRAMS) {
        return;
    }
    slot = &program_table[program_count];
    slot->id = program_count + 1;
    copy_name(slot->name, name);
    slot->purpose = purpose;
    program_count += 1;
}

void fk_userspace_init(struct fk_boot_context *ctx) {
    for (uint64_t i = 0; i < FK_USERSPACE_MAX_PROGRAMS; i++) {
        program_table[i].id = 0;
        program_table[i].name[0] = 0;
        program_table[i].purpose = 0;
    }
    userspace_ctx = ctx;
    program_count = 0;
    launch_count = 0;
    last_program_id = 0;
    register_program("echo", "Retourne un programme user simple pour valider la lane.");
    register_program("inspect", "Expose l'etat du kernel aux futures vues user.");
    register_program("forge", "Prepare la future lane de build et d'auto-dev.");
    register_program("notes", "Base d'espace utilisateur pour traces et plans.");
    register_program("init", "Premier processus user cible pour session et bureau.");
    register_program("vfs", "Explorateur minimal de l'espace fichier natif.");
    register_program("packages", "Lecteur du manifeste de paquets FractalOS.");
    register_program("desktop", "Lanceur du bureau classique augmente.");
    if (ctx) {
        ctx->userspace_ready = 1;
        ctx->userspace_program_count = program_count;
        ctx->userspace_launch_count = 0;
        ctx->userspace_last_program_id = 0;
    }
}

uint64_t fk_userspace_program_count(void) {
    return program_count;
}

uint64_t fk_userspace_launch_count(void) {
    return launch_count;
}

uint64_t fk_userspace_last_program_id(void) {
    return last_program_id;
}

uint64_t fk_userspace_launch_by_name(const char *name) {
    for (uint64_t i = 0; i < program_count; i++) {
        if (streq(program_table[i].name, name)) {
            launch_count += 1;
            last_program_id = program_table[i].id;
            if (userspace_ctx) {
                userspace_ctx->userspace_launch_count = launch_count;
                userspace_ctx->userspace_last_program_id = last_program_id;
            }
            return program_table[i].id;
        }
    }
    return 0;
}

void fk_userspace_report(void) {
    fk_serial_write("Userspace programs=");
    fk_serial_write_hex64(program_count);
    fk_serial_write(" launches=");
    fk_serial_write_hex64(launch_count);
    fk_serial_write(" last_program=");
    fk_serial_write_hex64(last_program_id);
    fk_serial_write("\n");
}
