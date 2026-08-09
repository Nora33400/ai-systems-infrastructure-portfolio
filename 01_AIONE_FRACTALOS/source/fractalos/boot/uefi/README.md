# FractalOS UEFI Bootloader

This folder contains a custom UEFI x64 bootloader source intended for a modern board such as:

- `ASUS TUF GAMING B550-PLUS WIFI II`

## Why UEFI x64

That board is a modern AM4 motherboard designed around UEFI firmware.  
So the safest compatibility target is:

- PE/COFF `BOOTX64.EFI`
- FAT32 EFI System Partition layout
- standard fallback path `EFI/BOOT/BOOTX64.EFI`

## What is provided

- `FractalBootX64.c` - custom bootloader source
- `build_uefi.ps1` - build script for a clang/lld toolchain

## Limits

This workspace does not currently have a native EFI compiler toolchain installed, so the source is ready but not compiled here.

The source is designed as:

- a custom FractalOS-branded UEFI application
- a boot handoff entrypoint for future kernel/runtime payloads
- a firmware-compatible fallback for this board class

## Real hardware note

Source compatibility target is meaningful.  
Full boot compatibility can only be claimed after:

1. compiling the EFI binary,
2. placing it in the ISO or FAT image,
3. boot-testing on the actual motherboard firmware settings.
