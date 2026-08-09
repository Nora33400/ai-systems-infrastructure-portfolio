#include <stddef.h>
#include <stdint.h>

typedef uint64_t EFI_STATUS;
typedef void* EFI_HANDLE;
typedef uint16_t CHAR16;
typedef unsigned long long UINTN;

#define EFI_SUCCESS 0

typedef struct {
    char _pad1[44];
    EFI_STATUS (*OutputString)(void* self, CHAR16* text);
} SIMPLE_TEXT_OUTPUT_INTERFACE;

typedef struct {
    char _pad2[64];
    SIMPLE_TEXT_OUTPUT_INTERFACE* ConOut;
} EFI_SYSTEM_TABLE;

static CHAR16* to_utf16(const char* ascii, CHAR16* buffer) {
    UINTN i = 0;
    while (ascii[i] != '\0') {
        buffer[i] = (CHAR16)ascii[i];
        i++;
    }
    buffer[i] = 0;
    return buffer;
}

EFI_STATUS efi_main(EFI_HANDLE image_handle, EFI_SYSTEM_TABLE* system_table) {
    (void)image_handle;

    if (!system_table || !system_table->ConOut || !system_table->ConOut->OutputString) {
        return EFI_SUCCESS;
    }

    CHAR16 line1[96];
    CHAR16 line2[96];
    CHAR16 line3[128];

    system_table->ConOut->OutputString(system_table->ConOut, to_utf16("FractalOS UEFI Bootloader\r\n", line1));
    system_table->ConOut->OutputString(system_table->ConOut, to_utf16("Target: ASUS B550 class / UEFI x64\r\n", line2));
    system_table->ConOut->OutputString(system_table->ConOut, to_utf16("Next stage: runtime handoff and kernel payload.\r\n", line3));

    return EFI_SUCCESS;
}
