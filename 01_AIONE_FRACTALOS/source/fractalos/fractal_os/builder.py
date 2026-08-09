from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .fusion_registry import FUSION_REGISTRY
from .fusion_runtime import stage_fusion_runtime


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _iso_component(name: str) -> str:
    # Limine searches for canonical filenames such as "limine-bios.sys".
    # ISO9660 level 4 lets us keep those names instead of mangling them to 8.3.
    return name


def _iso_path_from_rel(rel_parts: tuple[str, ...], is_file: bool) -> str:
    mapped = [_iso_component(part) for part in rel_parts]
    path = "/" + "/".join(mapped)
    return path + ";1" if is_file else path


def _limine_root(root: Path) -> Path:
    return root / "bare_metal" / "tooling" / "limine"


def _copy_limine_file(root: Path, iso_root: Path, name: str, rel_dir: str = "boot/limine") -> bool:
    src = _limine_root(root) / name
    if not src.exists():
        return False
    dst = (iso_root / rel_dir / name) if rel_dir else (iso_root / name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def stage_iso_tree(output_dir: Path | None = None) -> Path:
    root = project_root()
    iso_root = output_dir or (root / "build" / "iso_root")
    if iso_root.exists():
        shutil.rmtree(iso_root)
    (iso_root / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
    (iso_root / "fractal" / "boot").mkdir(parents=True, exist_ok=True)
    (iso_root / "fractal" / "fusion").mkdir(parents=True, exist_ok=True)
    (iso_root / "fractal" / "docs").mkdir(parents=True, exist_ok=True)
    (iso_root / "fractal" / "runtime").mkdir(parents=True, exist_ok=True)
    (iso_root / "boot" / "limine").mkdir(parents=True, exist_ok=True)

    # Prefer the real Limine boot path for the bare-metal kernel. The custom
    # UEFI app remains source-ready, but Limine is the actual bootloader track.
    kernel = root / "bare_metal" / "build" / "fractal_kernel.elf"
    if kernel.exists():
        shutil.copy2(kernel, iso_root / "boot" / "fractal_kernel.elf")
    else:
        (iso_root / "boot" / "fractal_kernel.elf.MISSING.txt").write_text(
            "Run bare_metal/build.ps1 before building a bootable ISO.\n",
            encoding="utf-8",
        )

    limine_conf = root / "bare_metal" / "limine" / "limine.conf"
    if limine_conf.exists():
        shutil.copy2(limine_conf, iso_root / "boot" / "limine" / "limine.conf")

    for name in ["limine-bios.sys", "limine-bios-cd.bin", "limine-uefi-cd.bin", "BOOTIA32.EFI", "BOOTX64.EFI"]:
        _copy_limine_file(root, iso_root, name)

    # The BIOS stage is deliberately replicated at every path Limine documents
    # in its panic message. This keeps QEMU BIOS and stricter firmware readers
    # from depending on Joliet/Rock-Ridge name resolution.
    _copy_limine_file(root, iso_root, "limine-bios.sys", rel_dir="")
    _copy_limine_file(root, iso_root, "limine-bios.sys", rel_dir="boot")
    _copy_limine_file(root, iso_root, "limine-bios.sys", rel_dir="limine")

    limine_uefi = iso_root / "boot" / "limine" / "BOOTX64.EFI"
    if limine_uefi.exists():
        shutil.copy2(limine_uefi, iso_root / "EFI" / "BOOT" / "BOOTX64.EFI")
    else:
        built_boot = root / "boot" / "uefi" / "build" / "BOOTX64.EFI"
        if built_boot.exists():
            shutil.copy2(built_boot, iso_root / "EFI" / "BOOT" / "BOOTX64.EFI")
        else:
            (iso_root / "EFI" / "BOOT" / "BOOTX64.EFI.MISSING.txt").write_text(
                "Limine BOOTX64.EFI or compiled boot/uefi/build/BOOTX64.EFI is required.\n",
                encoding="utf-8",
            )

    (iso_root / "fractal" / "boot" / "fractal.cfg").write_text(
        "\n".join(
            [
                "title=FractalOS",
                "boot_mode=uefi_x64",
                "runtime=python_control_plane",
                "kernel_profile=fractal_fusion",
                "overlay_hud=enabled",
                "tilemindfs=enabled",
                "omega_ram=enabled",
                "agent_board=enabled",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (iso_root / "startup.nsh").write_text(
        "echo Starting FractalOS UEFI fallback\n"
        "if exist fs0:\\EFI\\BOOT\\BOOTX64.EFI then fs0:\\EFI\\BOOT\\BOOTX64.EFI\n",
        encoding="utf-8",
    )
    (iso_root / "fractal" / "fusion" / "fusion_registry.json").write_text(
        json.dumps(FUSION_REGISTRY, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    doc_sources = [root / "README.md", root / "boot" / "uefi" / "README.md"]
    docs_dir = root / "docs"
    if docs_dir.exists():
        doc_sources.extend(sorted(docs_dir.glob("*.md")))
    for src in doc_sources:
        if src.exists():
            rel_name = src.relative_to(root).as_posix().replace("/", "__")
            shutil.copy2(src, iso_root / "fractal" / "docs" / rel_name)

    workspace_hint = {
        "workspace_default": "workspace",
        "features": [
            "tilemindfs",
            "omega_ram",
            "planner",
            "daemon",
            "dashboard",
            "agent_board_bridge",
            "hud_bridge",
        ],
    }
    (iso_root / "fractal" / "runtime" / "workspace_template.json").write_text(
        json.dumps(workspace_hint, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    fusion_runtime = stage_fusion_runtime(root / "build" / "fusion_runtime")
    (iso_root / "fractal" / "runtime" / "fusion_runtime_hint.json").write_text(
        json.dumps(fusion_runtime, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return iso_root


def try_build_iso(iso_root: Path, output_iso: Path) -> dict:
    boot_ready = (iso_root / "EFI" / "BOOT" / "BOOTX64.EFI").exists()
    kernel_ready = (iso_root / "boot" / "fractal_kernel.elf").exists()
    bios_boot = iso_root / "boot" / "limine" / "limine-bios-cd.bin"
    uefi_boot = iso_root / "boot" / "limine" / "limine-uefi-cd.bin"
    try:
        import pycdlib  # type: ignore
    except Exception:
        return {
            "built": False,
            "reason": "pycdlib_not_installed",
            "iso_root": str(iso_root),
            "output_iso": str(output_iso),
            "boot_payload_present": boot_ready,
            "kernel_present": kernel_ready,
        }

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=4, vol_ident="FRACTALOS", joliet=3)

    for path in sorted(iso_root.rglob("*")):
        rel = path.relative_to(iso_root)
        iso_path = _iso_path_from_rel(rel.parts, path.is_file())
        if path.is_dir():
            if rel.parts:
                iso.add_directory(iso_path=iso_path, joliet_path="/" + "/".join(rel.parts))
        else:
            kwargs = {"iso_path": iso_path, "joliet_path": "/" + "/".join(rel.parts)}
            iso.add_file(str(path), **kwargs)

    boot_entries: list[str] = []
    if bios_boot.exists():
        iso.add_eltorito(
            _iso_path_from_rel(bios_boot.relative_to(iso_root).parts, True),
            bootcatfile="/boot/limine/bios.cat;1",
            joliet_bootcatfile="/boot/limine/bios.cat",
            boot_load_size=4,
            boot_info_table=True,
        )
        boot_entries.append("bios")
    if uefi_boot.exists():
        iso.add_eltorito(
            _iso_path_from_rel(uefi_boot.relative_to(iso_root).parts, True),
            bootcatfile="/boot/limine/uefi.cat;1",
            joliet_bootcatfile="/boot/limine/uefi.cat",
            platform_id=0xEF,
            efi=True,
        )
        boot_entries.append("uefi")

    output_iso.parent.mkdir(parents=True, exist_ok=True)
    iso.write(str(output_iso))
    iso.close()
    limine_install = {"attempted": False, "ok": False, "stdout": "", "stderr": ""}
    limine_exe = _limine_root(project_root()) / "limine.exe"
    if limine_exe.exists() and "bios" in boot_entries:
        completed = subprocess.run(
            [str(limine_exe), "bios-install", str(output_iso)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        limine_install = {
            "attempted": True,
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-1200:],
            "stderr": completed.stderr[-1200:],
        }
    return {
        "built": True,
        "reason": "ok",
        "iso_root": str(iso_root),
        "output_iso": str(output_iso),
        "boot_payload_present": boot_ready,
        "kernel_present": kernel_ready,
        "boot_entries": boot_entries,
        "limine_bios_install": limine_install,
    }
