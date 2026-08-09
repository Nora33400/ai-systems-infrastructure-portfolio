from __future__ import annotations

from pathlib import Path

from .fusion_registry import FUSION_REGISTRY
from .probe import build_status, motherboard_report, toolchain_report


def full_report(root: Path) -> dict:
    tools = toolchain_report()
    board = motherboard_report()
    build = build_status(root)
    efi_compiler_ready = tools["tools"]["clang"]["present"] and tools["tools"]["lld-link"]["present"]
    bootloader_ready = build.get("efi_binary_exists") or build.get("limine_uefi_loader_exists")
    bootable_payload_ready = build.get("bare_metal_kernel_exists") and bootloader_ready
    return {
        "identity": FUSION_REGISTRY["identity"],
        "motherboard_target": FUSION_REGISTRY["motherboard_target"],
        "motherboard_detected": board,
        "toolchain": tools,
        "build": build,
        "readiness": {
            "iso_pipeline_ready": bool(tools["pycdlib_present"] and tools["tools"]["python"]["present"]),
            "iso_built": bool(build["iso_exists"]),
            "efi_compiler_ready": bool(efi_compiler_ready),
            "boot_payload_ready": bool(bootable_payload_ready),
            "bootable_iso_ready": bool(build["iso_exists"] and bootable_payload_ready),
            "qemu_ready": bool(tools["tools"].get("qemu-system-x86_64", {}).get("present")),
            "virtualbox_ready": bool(tools["tools"].get("VBoxManage", {}).get("present")),
        },
    }
