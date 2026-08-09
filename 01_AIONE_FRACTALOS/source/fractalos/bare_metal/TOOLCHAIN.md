# FractalOS Bare-Metal Toolchain

This machine now has a working build and VM validation path with:

- `C:\Program Files\LLVM\bin\clang.exe`;
- `C:\Program Files\LLVM\bin\ld.lld.exe`;
- `C:\Program Files\LLVM\bin\lld-link.exe`;
- `C:\Program Files\qemu\qemu-system-x86_64.exe`;
- `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe`;
- `pycdlib` for ISO creation.

Not visible in PATH and not required for the current ISO path:

- `xorriso`;
- `oscdimg`.

Required tools:

- LLVM `clang` and `ld.lld`, or `x86_64-elf-gcc` and `x86_64-elf-ld`
- `pycdlib` for ISO generation
- Limine binary payload staged under `bare_metal/tooling/limine`
- optionally `qemu-system-x86_64` for safe VM boot tests

## Fast Windows Path

Build:

```powershell
cd 01_AIONE_FRACTALOS\source\fractalos\bare_metal
.\build.ps1
```

Build the ISO:

```powershell
cd 01_AIONE_FRACTALOS\source\fractalos
$env:PYTHONPATH=(Get-Location).Path
python -m fractal_os build-iso --output-iso .\build\FractalOS.iso
```

## Current Validation

The current validated target is:

1. compile `bare_metal\build\fractal_kernel.elf`;
2. stage Limine BIOS/UEFI files into the ISO root;
3. generate `build\FractalOS.iso`;
4. boot with QEMU BIOS and QEMU UEFI;
5. verify serial output reaches `TripleKernel score=0x000000000000031b`.
