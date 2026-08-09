from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .events import append_event
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


NATIVE_DESKTOP_COMPONENTS: list[dict[str, Any]] = [
    {
        "id": "login-greeter",
        "title": "Fractal Login Greeter",
        "status": "specified",
        "classic_role": "connexion qui donne sur le bureau",
        "native_gate": "users, homes, credential store, session manager",
        "extended_fractal_role": "guest/user/admin/doctor sessions with proof ribbon and rollback prompts.",
    },
    {
        "id": "home-menu",
        "title": "Living Home Menu",
        "status": "hosted-runtime",
        "classic_role": "menu d accueil interactif",
        "native_gate": "compositor, input focus, app launcher model",
        "extended_fractal_role": "intent-first menu that can spawn plans, agents, tests and formula programs.",
    },
    {
        "id": "global-search",
        "title": "Fractal Search Bar",
        "status": "hosted-runtime",
        "classic_role": "barre de recherche",
        "native_gate": "index service, VFS metadata, process/app registry",
        "extended_fractal_role": "search across files, tiles, agents, formulas, docs, packages and future branches.",
    },
    {
        "id": "tile-explorer",
        "title": "TileMind Explorer",
        "status": "hosted-runtime",
        "classic_role": "explorateur de fichiers",
        "native_gate": "storage driver, writable VFS, MIME registry",
        "extended_fractal_role": "view files as tiles, dedupe blocks, semantic memory and reconstructable manifests.",
    },
    {
        "id": "fractal-terminal",
        "title": "Fractal Terminal",
        "status": "kernel-console-and-hosted-runtime",
        "classic_role": "cmd/shell",
        "native_gate": "syscall ABI, ring3 programs, init, pty-like streams",
        "extended_fractal_role": "command veil with proof level, risk score and agent handoff.",
    },
    {
        "id": "web-gateway",
        "title": "Web Gateway",
        "status": "specified",
        "classic_role": "internet/navigation",
        "native_gate": "PCIe/NIC, TCP/IP, DNS, TLS, browser sandbox",
        "extended_fractal_role": "browser domain isolated from kernel and scored by trust/energy policies.",
    },
    {
        "id": "package-center",
        "title": "Package Center",
        "status": "specified",
        "classic_role": "installateur de paquets",
        "native_gate": "signed packages, dependency solver, rollback slots",
        "extended_fractal_role": "packages are promoted only after doctor, tests, attestations and safe restart.",
    },
    {
        "id": "office-desk",
        "title": "Office Desk",
        "status": "specified",
        "classic_role": "bureautique",
        "native_gate": "document handlers, fonts, print/export, clipboard",
        "extended_fractal_role": "documents become living objects with versioned intent, proof and agent summaries.",
    },
    {
        "id": "media-center",
        "title": "Media Center",
        "status": "specified",
        "classic_role": "images, audio, video",
        "native_gate": "GPU mode setting, audio, codecs, timers",
        "extended_fractal_role": "media pipelines expose energy, latency, cache and provenance overlays.",
    },
    {
        "id": "settings-and-doctor",
        "title": "Settings + Doctor",
        "status": "hosted-runtime",
        "classic_role": "parametres, maintenance, recovery",
        "native_gate": "policy store, boot slots, driver profiles",
        "extended_fractal_role": "every risky setting has a simulated future, rollback and doctor reinforcement.",
    },
]


NATIVE_PACKAGE_CATALOG: list[dict[str, Any]] = [
    {"id": "runtime.python", "name": "Python Runtime Domain", "kind": "runtime", "phase": "compat-alpha"},
    {"id": "runtime.rust", "name": "Rust Toolchain Domain", "kind": "runtime", "phase": "compat-alpha"},
    {"id": "runtime.java", "name": "Java Runtime Domain", "kind": "runtime", "phase": "compat-alpha"},
    {"id": "browser.firefox-domain", "name": "Firefox/Web Domain", "kind": "internet", "phase": "network-alpha"},
    {"id": "office.libreoffice-domain", "name": "LibreOffice Domain", "kind": "office", "phase": "desktop-alpha"},
    {"id": "media.codec-pack", "name": "Image/Audio/Video Codec Pack", "kind": "media", "phase": "desktop-alpha"},
    {"id": "dev.code-studio", "name": "Code Studio", "kind": "dev", "phase": "userspace-alpha"},
    {"id": "ai.ollama-local", "name": "Ollama Local Model Bridge", "kind": "ai", "phase": "hosted-ready"},
    {"id": "fs.tilemindfs", "name": "TileMindFS Storage Layer", "kind": "storage", "phase": "hosted-ready"},
    {"id": "doctor.safe-update", "name": "Doctor Safe Update Orchestrator", "kind": "recovery", "phase": "hosted-ready"},
    {"id": "compat.exe-domain", "name": "Windows EXE Compatibility Domain", "kind": "compat", "phase": "compat-alpha"},
    {"id": "net.mesh-agent", "name": "Mesh Agent Network", "kind": "network", "phase": "hosted-ready"},
]


MISSING_CONVERSATION_ELEMENTS: list[dict[str, str]] = [
    {
        "id": "persistent-install",
        "integrated_as": "VM disk profile, install slots, machine install gates and generated run scripts.",
    },
    {
        "id": "classic-desktop",
        "integrated_as": "login, home menu, search, tile explorer, terminal, web gateway, package center and office/media apps.",
    },
    {
        "id": "fractalos-extensions",
        "integrated_as": "intent overlay, proof ribbon, energy strip, agent orbit, formula lab and TileMindFS explorer.",
    },
    {
        "id": "native-package-ecosystem",
        "integrated_as": "signed package catalog with runtime, browser, office, media, AI, storage and compatibility domains.",
    },
    {
        "id": "truth-gated-roadmap",
        "integrated_as": "explicit gates separating bootable kernel, hosted runtime and not-yet-native subsystems.",
    },
]


INSTALL_SLOTS: list[dict[str, str]] = [
    {"name": "EFI", "purpose": "UEFI boot files and Limine", "format": "FAT32", "size": "512MiB"},
    {"name": "boot_a", "purpose": "current verified FractalOS kernel slot", "format": "read-only image", "size": "1GiB"},
    {"name": "boot_b", "purpose": "rollback kernel slot", "format": "read-only image", "size": "1GiB"},
    {"name": "system", "purpose": "native services and package base", "format": "Fractal package image", "size": "8GiB"},
    {"name": "state", "purpose": "doctor logs, proofs, policies, sessions", "format": "journaled VFS target", "size": "4GiB"},
    {"name": "home", "purpose": "user files, tiles, documents and app data", "format": "TileMindFS-backed VFS target", "size": "grow"},
    {"name": "recovery", "purpose": "known-good modules and repair bundles", "format": "append-only archive", "size": "2GiB"},
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _qemu_img() -> str | None:
    found = shutil.which("qemu-img")
    if found:
        return found
    for candidate in [
        r"C:\Program Files\qemu\qemu-img.exe",
        r"C:\Program Files (x86)\qemu\qemu-img.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def _qemu_system() -> str | None:
    found = shutil.which("qemu-system-x86_64")
    if found:
        return found
    for candidate in [
        r"C:\Program Files\qemu\qemu-system-x86_64.exe",
        r"C:\Program Files (x86)\qemu\qemu-system-x86_64.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def native_package_catalog(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    by_kind: dict[str, int] = {}
    for item in NATIVE_PACKAGE_CATALOG:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    append_event(workspace, "native_package_catalog", {"packages": len(NATIVE_PACKAGE_CATALOG)})
    return {
        "generated_at": utc_now(),
        "packages": NATIVE_PACKAGE_CATALOG,
        "by_kind": by_kind,
        "install_policy": {
            "default": "plan-only-until-native-vfs",
            "promotion_gate": "doctor_ok && tests_ok && rollback_slot_ready && package_signature_ok",
            "unsafe_rule": "No package may write kernel or boot slots without admin + doctor approval.",
        },
    }


def native_desktop_blueprint(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    ready_hosted = [item for item in NATIVE_DESKTOP_COMPONENTS if "hosted" in item["status"] or "kernel-console" in item["status"]]
    specified = [item for item in NATIVE_DESKTOP_COMPONENTS if item["status"] == "specified"]
    append_event(workspace, "native_desktop_blueprint", {"components": len(NATIVE_DESKTOP_COMPONENTS)})
    return {
        "generated_at": utc_now(),
        "mode": "native_desktop_alpha",
        "truth": {
            "boots_now": (_project_root() / "build" / "FractalOS.iso").exists(),
            "classic_daily_driver_now": False,
            "persistent_self_install_now": False,
            "reason": "The kernel boots, but native storage, VFS, network, compositor, package manager and ring3 runtime are still gates.",
            "what_is_real_now": "Bootable bare-metal kernel plus hosted FractalOS control plane and generated persistent VM profile.",
        },
        "components": NATIVE_DESKTOP_COMPONENTS,
        "hosted_or_kernel_console_components": ready_hosted,
        "specified_native_gates": specified,
        "missing_conversation_elements_integrated": MISSING_CONVERSATION_ELEMENTS,
        "desktop_contract": {
            "first_screen": "login-greeter -> fractal-desktop",
            "core_surfaces": ["home-menu", "global-search", "tile-explorer", "fractal-terminal", "package-center"],
            "network_surface": "web-gateway",
            "safety_surfaces": ["proof-ribbon", "settings-and-doctor", "recovery slot"],
            "fractal_surfaces": ["intent overlay", "agent orbit", "formula lab", "future branches"],
        },
    }


def native_installation_plan(
    workspace: Path,
    target: str = "vm",
    disk_size_gb: int = 32,
    create_vm_disk: bool = False,
) -> dict[str, Any]:
    ensure_workspace(workspace)
    root = _project_root()
    iso = root / "build" / "FractalOS.iso"
    vm_dir = root / "build" / "vm"
    vm_dir.mkdir(parents=True, exist_ok=True)
    disk = vm_dir / "FractalOS-persistent.qcow2"
    qemu_img = _qemu_img()
    qemu_system = _qemu_system()
    disk_result: dict[str, Any] = {
        "requested": create_vm_disk,
        "created": False,
        "path": str(disk),
        "reason": "not_requested",
    }
    if create_vm_disk:
        if disk.exists():
            disk_result.update({"created": True, "reason": "already_exists", "size": disk.stat().st_size})
        elif qemu_img:
            completed = subprocess.run(
                [qemu_img, "create", "-f", "qcow2", str(disk), f"{disk_size_gb}G"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            disk_result.update(
                {
                    "created": completed.returncode == 0,
                    "reason": "qemu_img",
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-1200:],
                    "stderr": completed.stderr[-1200:],
                    "size": disk.stat().st_size if disk.exists() else 0,
                }
            )
        else:
            disk_result.update({"created": False, "reason": "qemu_img_missing"})

    start_script = _write_vm_start_script(root, workspace, iso, disk, qemu_system)
    report_path = _write_install_report(
        workspace=workspace,
        target=target,
        disk_size_gb=disk_size_gb,
        iso=iso,
        disk=disk,
        start_script=start_script,
        disk_result=disk_result,
        qemu_system=qemu_system,
    )
    tile = TileMindFS(workspace).store_file(report_path)
    OmegaRAM(workspace).put_text(
        key=f"native_install::{report_path.stem}",
        text=report_path.read_text(encoding="utf-8"),
        source="native_desktop_stack",
    )
    append_event(
        workspace,
        "native_installation_plan",
        {"target": target, "disk_created": disk_result["created"], "self_install_ready": False},
    )
    return {
        "generated_at": utc_now(),
        "target": target,
        "iso": str(iso),
        "iso_exists": iso.exists(),
        "disk": disk_result,
        "start_script": str(start_script),
        "report_path": str(report_path),
        "tile_manifest": tile.get("manifest_id", ""),
        "slots": INSTALL_SLOTS,
        "persistent_install_truth": {
            "vm_disk_profile_ready": disk.exists() or disk_result["created"],
            "machine_install_blueprint_ready": True,
            "self_hosted_installer_ready": False,
            "blocking_native_gates": [
                "writable storage driver",
                "native VFS",
                "init/user session manager",
                "package manager",
                "network stack",
                "desktop compositor",
            ],
        },
    }


def write_native_desktop_report(workspace: Path) -> dict[str, Any]:
    blueprint = native_desktop_blueprint(workspace)
    packages = native_package_catalog(workspace)
    plan = native_installation_plan(workspace, target="vm", create_vm_disk=False)
    root = workspace / "native_desktop"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"NATIVE_DESKTOP_REPORT_{len(list(root.glob('NATIVE_DESKTOP_REPORT_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Native Desktop And Install Report",
        "",
        f"- Generated at: {utc_now()}",
        f"- Boots now: {blueprint['truth']['boots_now']}",
        f"- Classic daily driver now: {blueprint['truth']['classic_daily_driver_now']}",
        f"- Persistent self install now: {blueprint['truth']['persistent_self_install_now']}",
        f"- Truth: {blueprint['truth']['reason']}",
        "",
        "## Desktop Surfaces",
    ]
    for item in blueprint["components"]:
        lines.append(f"- {item['id']} :: {item['status']} :: {item['classic_role']} :: gate={item['native_gate']}")
    lines.extend(["", "## Package Catalog"])
    for item in packages["packages"]:
        lines.append(f"- {item['id']} :: {item['kind']} :: {item['phase']}")
    lines.extend(["", "## Install Slots"])
    for slot in INSTALL_SLOTS:
        lines.append(f"- {slot['name']} :: {slot['format']} :: {slot['size']} :: {slot['purpose']}")
    lines.extend(["", "## Missing Conversation Elements Integrated"])
    for item in MISSING_CONVERSATION_ELEMENTS:
        lines.append(f"- {item['id']} :: {item['integrated_as']}")
    lines.extend(["", "## Generated Install Plan", f"- {plan['report_path']}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"native_desktop::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="native_desktop_stack",
    )
    return {
        "blueprint": blueprint,
        "packages": packages,
        "install_plan": plan,
        "report_path": str(path),
        "tile_manifest": tile.get("manifest_id", ""),
    }


def _write_vm_start_script(root: Path, workspace: Path, iso: Path, disk: Path, qemu_system: str | None) -> Path:
    script = root / "build" / "vm" / "Start-FractalOS-LivePersistent.ps1"
    qemu = qemu_system or "qemu-system-x86_64"
    serial = workspace / "vm_validation" / "native_persistent_serial.log"
    serial.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$Qemu = '{qemu}'",
        f"$Iso = '{iso}'",
        f"$Disk = '{disk}'",
        f"$Serial = '{serial}'",
        "if (-not (Test-Path $Iso)) { throw \"Missing ISO: $Iso\" }",
        "if (-not (Test-Path $Disk)) { throw \"Missing persistent disk: $Disk. Run native-os-install-plan --create-vm-disk first.\" }",
        "& $Qemu -m 4096 -smp 4 -cdrom $Iso -drive \"file=$Disk,format=qcow2,if=virtio\" -boot d -serial \"file:$Serial\"",
    ]
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return script


def _write_install_report(
    workspace: Path,
    target: str,
    disk_size_gb: int,
    iso: Path,
    disk: Path,
    start_script: Path,
    disk_result: dict[str, Any],
    qemu_system: str | None,
) -> Path:
    root = workspace / "native_install"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"NATIVE_INSTALL_PLAN_{len(list(root.glob('NATIVE_INSTALL_PLAN_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Native Installation Plan",
        "",
        f"- Generated at: {utc_now()}",
        f"- Target: {target}",
        f"- ISO: {iso}",
        f"- ISO exists: {iso.exists()}",
        f"- Persistent disk: {disk}",
        f"- Requested disk size: {disk_size_gb}G",
        f"- Disk created/ready: {disk_result.get('created')}",
        f"- QEMU: {qemu_system or 'not found'}",
        f"- Start script: {start_script}",
        "",
        "## Truth Gate",
        "FractalOS boots today, and this plan prepares a persistent VM profile.",
        "A self-hosted installer inside the bare-metal ISO is not yet complete because native storage, VFS, sessions, packages, network and compositor are still kernel/userspace gates.",
        "",
        "## Disk Slots",
    ]
    for slot in INSTALL_SLOTS:
        lines.append(f"- {slot['name']} :: {slot['format']} :: {slot['size']} :: {slot['purpose']}")
    lines.extend(
        [
            "",
            "## Install Flow",
            "- Boot ISO with persistent disk attached.",
            "- Doctor verifies kernel, bootloader, package signatures and rollback slot.",
            "- Installer writes EFI + boot_a, keeps boot_b known-good, creates system/state/home/recovery slots.",
            "- First restart enters safe mode and validates desktop, sessions, package catalog and TileMindFS.",
            "- If validation passes, FractalOS promotes boot_a as current; otherwise it falls back to boot_b.",
            "",
            "## Next Native Gates",
            "- Implement writable storage driver and native VFS.",
            "- Promote hosted package catalog into signed native packages.",
            "- Add init, login greeter and user homes.",
            "- Add compositor/window manager and file explorer.",
            "- Add NIC/TCP/IP/DNS/TLS and browser domain.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
