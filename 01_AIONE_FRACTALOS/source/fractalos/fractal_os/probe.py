from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


COMMON_TOOL_PATHS = {
    "qemu-system-x86_64": [
        r"C:\Program Files\qemu\qemu-system-x86_64.exe",
        r"C:\Program Files (x86)\qemu\qemu-system-x86_64.exe",
    ],
    "VBoxManage": [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    ],
    "clang": [
        r"C:\Program Files\LLVM\bin\clang.exe",
    ],
    "lld-link": [
        r"C:\Program Files\LLVM\bin\lld-link.exe",
    ],
    "ld.lld": [
        r"C:\Program Files\LLVM\bin\ld.lld.exe",
    ],
    "xorriso": [
        r"C:\msys64\usr\bin\xorriso.exe",
        r"C:\tools\msys64\usr\bin\xorriso.exe",
    ],
    "oscdimg": [
        r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\x64\oscdimg.exe",
    ],
}


def _which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in COMMON_TOOL_PATHS.get(name, []):
        if Path(candidate).exists():
            return candidate
    return None


def _python_module_present(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def toolchain_report() -> dict:
    names = ["python", "py", "dotnet", "clang", "lld-link", "ld.lld", "xorriso", "oscdimg", "qemu-system-x86_64", "VBoxManage"]
    return {
        "tools": {name: {"present": bool(_which(name)), "path": _which(name)} for name in names},
        "pycdlib_present": _python_module_present("pycdlib"),
    }


def motherboard_report() -> dict:
    script = (
        "Get-CimInstance Win32_BaseBoard | "
        "Select-Object Manufacturer,Product,SerialNumber | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        data = json.loads(result.stdout.strip())
        return {
            "detected": True,
            "manufacturer": data.get("Manufacturer"),
            "product": data.get("Product"),
            "serial_number": data.get("SerialNumber"),
        }
    except Exception as exc:
        return {"detected": False, "error": str(exc)}


def build_status(root: Path) -> dict:
    iso_path = root / "build" / "FractalOS.iso"
    efi_src = root / "boot" / "uefi" / "FractalBootX64.c"
    efi_bin = root / "boot" / "uefi" / "build" / "BOOTX64.EFI"
    kernel = root / "bare_metal" / "build" / "fractal_kernel.elf"
    limine_boot = root / "bare_metal" / "tooling" / "limine" / "BOOTX64.EFI"
    staged_kernel = root / "build" / "iso_root" / "boot" / "fractal_kernel.elf"
    iso_root = root / "build" / "iso_root"
    return {
        "iso_exists": iso_path.exists(),
        "iso_path": str(iso_path),
        "iso_size": iso_path.stat().st_size if iso_path.exists() else 0,
        "iso_root_exists": iso_root.exists(),
        "efi_source_exists": efi_src.exists(),
        "efi_binary_exists": efi_bin.exists(),
        "efi_binary_path": str(efi_bin),
        "bare_metal_kernel_exists": kernel.exists(),
        "bare_metal_kernel_path": str(kernel),
        "limine_uefi_loader_exists": limine_boot.exists(),
        "limine_uefi_loader_path": str(limine_boot),
        "staged_kernel_exists": staged_kernel.exists(),
    }
