from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .desktop_runtime import DESKTOP_OVERLAYS
from .events import append_event
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


CLASSIC_CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "bootable-iso",
        "question": "L OS boote-t-il depuis une ISO ?",
        "bare_metal": "yes",
        "hosted": "not_applicable",
        "truth": "QEMU BIOS and QEMU UEFI reach the FractalOS kernel.",
        "next_kernel_gate": "Automate BIOS and UEFI boot checks and test physical USB boot.",
    },
    {
        "id": "desktop-office",
        "question": "Interface de bureau exploitable pour bureautique classique ?",
        "bare_metal": "no",
        "hosted": "partial_plus_native_blueprint",
        "truth": "Bare-metal has framebuffer console and desktop-plane primitives; hosted mode now models login, start menu, search, TileMind explorer, package center, office/media surfaces and dashboard.",
        "next_kernel_gate": "Add compositor, windows, clipboard, settings and file manager.",
    },
    {
        "id": "persistent-install",
        "question": "Installation persistante sur VM ou machine ?",
        "bare_metal": "planned_not_self_hosted",
        "hosted": "vm_profile_ready",
        "truth": "FractalOS can generate a persistent QEMU disk profile and install plan; the ISO does not yet self-install because native storage/VFS/session/package gates remain.",
        "next_kernel_gate": "Add writable storage driver, VFS, init, boot slots and installer transaction engine.",
    },
    {
        "id": "internet-browser",
        "question": "Acces internet et navigation Google/Firefox ?",
        "bare_metal": "no",
        "hosted": "yes_if_host_online",
        "truth": "Hosted FractalOS can use host internet; bare-metal has no NIC driver, TCP/IP or browser yet.",
        "next_kernel_gate": "Add PCIe/NIC discovery, network driver, TCP/IP, DNS, TLS and browser container.",
    },
    {
        "id": "common-file-extensions",
        "question": "Extensions classiques png, jpeg, txt, pdf ?",
        "bare_metal": "no",
        "hosted": "partial",
        "truth": "Hosted tools can inspect/manipulate files; bare-metal has no native VFS/viewers yet.",
        "next_kernel_gate": "Add VFS, MIME registry, file associations and viewers.",
    },
    {
        "id": "video-playback",
        "question": "Lecture video ?",
        "bare_metal": "no",
        "hosted": "host_dependent",
        "truth": "Bare-metal has no audio/video stack or codecs yet.",
        "next_kernel_gate": "Add GPU mode setting, audio, timing, decoders and media player.",
    },
    {
        "id": "file-editing",
        "question": "Lire/ecrire/modifier txt, Word, LibreOffice ?",
        "bare_metal": "no",
        "hosted": "yes_via_host_tools",
        "truth": "Hosted mode can manipulate host files; bare-metal still needs persistent storage and editors.",
        "next_kernel_gate": "Add storage driver, writable filesystem, text editor and document app containers.",
    },
    {
        "id": "exe-compatibility",
        "question": "Executer des .exe ou autres formats ?",
        "bare_metal": "no",
        "hosted": "yes_via_windows_host",
        "truth": "Bare-metal cannot run Windows EXE yet; host Windows can.",
        "next_kernel_gate": "Add ELF first, then PE/Win32 via VM/domain isolation or Wine-like compatibility.",
    },
    {
        "id": "runtime-install",
        "question": "Installer Python, Rust, Java et modules existants ?",
        "bare_metal": "no",
        "hosted": "yes_if_host_toolchain_installed",
        "truth": "Hosted FractalOS can orchestrate host toolchains; bare-metal has no package manager or runtimes yet.",
        "next_kernel_gate": "Add package manager, signed packages, runtime domains and rollback.",
    },
    {
        "id": "onboarding",
        "question": "Prise en main intuitive, docs, tips, overlay, notifications ?",
        "bare_metal": "partial",
        "hosted": "yes",
        "truth": "Docs, desktop overlay concepts and guide exist; bare-metal tips are not yet interactive.",
        "next_kernel_gate": "Add first-run overlay, help center, notifications and guided missions.",
    },
    {
        "id": "user-sessions",
        "question": "Sessions guest/user/admin ?",
        "bare_metal": "no",
        "hosted": "modeled",
        "truth": "Hosted FractalOS can model roles; bare-metal has no native auth/session isolation yet.",
        "next_kernel_gate": "Add user database, homes, permissions, session manager and audit.",
    },
]


CLASSIC_SESSION_ROLES: list[dict[str, Any]] = [
    {
        "id": "guest",
        "risk": "low",
        "allowed": ["browse_docs", "open_demo_apps", "run_read_only_reports"],
        "blocked": ["write_system", "install_packages", "auto_upgrade"],
    },
    {
        "id": "user",
        "risk": "medium",
        "allowed": ["edit_home_files", "run_user_apps", "queue_agents", "use_browser_when_available"],
        "blocked": ["kernel_patch", "driver_install", "global_policy_change"],
    },
    {
        "id": "admin",
        "risk": "high",
        "allowed": ["install_packages", "approve_updates", "manage_users", "recover_modules"],
        "blocked": ["unsafe_hardware_overclock", "unverified_kernel_promotion"],
    },
    {
        "id": "doctor",
        "risk": "protective",
        "allowed": ["scan", "rollback", "quarantine", "reinforce_patch", "write_audit"],
        "blocked": ["silent_user_data_deletion", "unattested_promotion"],
    },
]


CLASSIC_IMPORT_PLAN: list[dict[str, Any]] = [
    {
        "phase": "Userspace Alpha",
        "items": ["ring3", "ELF loader", "init process", "syscall ABI", "RAM disk VFS"],
        "why": "This turns the kernel from a bootable core into an OS that can run programs.",
    },
    {
        "phase": "Desktop Alpha",
        "items": ["compositor", "window manager", "input stack", "file manager", "tips overlay"],
        "why": "This makes the screen usable like a classic desktop while preserving FractalOS overlays.",
    },
    {
        "phase": "Storage Alpha",
        "items": ["writable VFS", "file associations", "snapshots", "TileMindFS bridge", "document editors"],
        "why": "This enables real work on txt, images, PDFs and office documents.",
    },
    {
        "phase": "Network Alpha",
        "items": ["PCIe scan", "NIC driver", "TCP/IP", "DNS", "TLS", "browser domain"],
        "why": "This brings internet without merging unsafe browser code into the kernel.",
    },
    {
        "phase": "Compatibility Alpha",
        "items": ["package manager", "Python/Rust/Java domains", "ELF packages", "Windows EXE VM domain"],
        "why": "This imports useful software ecosystems without sacrificing proof-gated updates.",
    },
]


ONBOARDING_TIPS: list[dict[str, str]] = [
    {
        "id": "start-with-doctor",
        "surface": "proof-ribbon",
        "tip": "Run Doctor before large work. If it reports critical risk, stabilize before expanding.",
    },
    {
        "id": "use-intent-lens",
        "surface": "intent-lens",
        "tip": "Describe the result you want; FractalOS turns it into plans, workers and verification gates.",
    },
    {
        "id": "respect-energy-strip",
        "surface": "energy-strip",
        "tip": "When thermal or stability pressure rises, let the scheduler reduce concurrency.",
    },
    {
        "id": "agent-orbit-is-a-fleet",
        "surface": "agent-orbit",
        "tip": "Treat agents as local workers: planner, builder, patcher, reviewer and documenter.",
    },
    {
        "id": "command-veil",
        "surface": "command-veil",
        "tip": "Use the overlay shell to run safe services without leaving the current context.",
    },
]


def classic_capability_report(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    report = {
        "generated_at": utc_now(),
        "mode": "classic_os_gap_bridge",
        "summary": {
            "bare_metal_daily_driver": False,
            "hosted_control_plane_usable": True,
            "bootable_iso": True,
            "primary_gap": "Bare-metal needs userspace, VFS, network, desktop compositor and sessions.",
        },
        "capabilities": CLASSIC_CAPABILITIES,
        "session_roles": CLASSIC_SESSION_ROLES,
        "classic_import_plan": CLASSIC_IMPORT_PLAN,
        "missing_from_conversation_integrated": [
            "office desktop gap tracking",
            "internet/browser gap tracking",
            "common file extension roadmap",
            "video/media roadmap",
            "read/write/edit filesystem roadmap",
            "EXE/runtime compatibility roadmap",
            "Python/Rust/Java package roadmap",
            "onboarding overlay tips",
            "guest/user/admin/doctor session model",
            "persistent VM install profile",
            "desktop search, package center and TileMind explorer",
        ],
    }
    append_event(workspace, "classic_os_capability_report", {"capabilities": len(CLASSIC_CAPABILITIES)})
    return report


def onboarding_pack(workspace: Path) -> dict[str, Any]:
    ensure_workspace(workspace)
    overlays = [item["id"] for item in DESKTOP_OVERLAYS]
    pack = {
        "generated_at": utc_now(),
        "title": "FractalOS first-run guidance pack",
        "overlays": overlays,
        "tips": ONBOARDING_TIPS,
        "first_commands": [
            "python -m omega_tile_os doctor --workspace .\\workspace",
            "python -m omega_tile_os desktop --workspace .\\workspace",
            "python -m omega_tile_os classic-os-report --workspace .\\workspace",
            "python -m omega_tile_os ai-model-plan --workspace .\\workspace",
            "python -m fractal_os build-report",
        ],
        "safe_rule": "Never promote a patch unless doctor, tests, build and recovery gates agree.",
    }
    append_event(workspace, "classic_os_onboarding_pack", {"tips": len(ONBOARDING_TIPS)})
    return pack


def write_classic_os_report(workspace: Path) -> dict[str, Any]:
    report = classic_capability_report(workspace)
    pack = onboarding_pack(workspace)
    root = workspace / "classic_os"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"CLASSIC_OS_REPORT_{len(list(root.glob('CLASSIC_OS_REPORT_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Classic OS Bridge Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Bare-metal daily driver: {report['summary']['bare_metal_daily_driver']}",
        f"- Hosted control plane usable: {report['summary']['hosted_control_plane_usable']}",
        f"- Primary gap: {report['summary']['primary_gap']}",
        "",
        "## Capability Answers",
    ]
    for item in report["capabilities"]:
        lines.extend(
            [
                f"### {item['id']}",
                f"- Question: {item['question']}",
                f"- Bare-metal: {item['bare_metal']}",
                f"- Hosted: {item['hosted']}",
                f"- Truth: {item['truth']}",
                f"- Next kernel gate: {item['next_kernel_gate']}",
                "",
            ]
        )
    lines.extend(["## Session Roles"])
    for role in report["session_roles"]:
        lines.append(f"- {role['id']} :: risk={role['risk']} :: allowed={', '.join(role['allowed'])}")
    lines.extend(["", "## Classic Import Plan"])
    for phase in report["classic_import_plan"]:
        lines.append(f"- {phase['phase']} :: {', '.join(phase['items'])} :: {phase['why']}")
    lines.extend(["", "## Onboarding Tips"])
    for tip in pack["tips"]:
        lines.append(f"- {tip['surface']} :: {tip['tip']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"classic_os::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="classic_os_bridge",
    )
    return {
        "report": report,
        "onboarding": pack,
        "report_path": str(path),
        "tile_manifest": tile.get("manifest_id", ""),
    }
