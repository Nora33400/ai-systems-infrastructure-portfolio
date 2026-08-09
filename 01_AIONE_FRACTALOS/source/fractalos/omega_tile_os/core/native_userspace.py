from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import append_event
from .native_desktop_stack import NATIVE_PACKAGE_CATALOG
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from .storage_vfs import storage_mount_report, storage_read, storage_write
from ..tilemindfs.store import TileMindFS


DEFAULT_VFS_NODES: list[dict[str, Any]] = [
    {"path": "/", "kind": "dir", "owner": "root", "text": ""},
    {"path": "/etc", "kind": "dir", "owner": "root", "text": ""},
    {"path": "/etc/fractalos-release", "kind": "file", "owner": "root", "text": "FractalOS Userspace Alpha\n"},
    {"path": "/home", "kind": "dir", "owner": "root", "text": ""},
    {"path": "/home/guest", "kind": "dir", "owner": "guest", "text": ""},
    {"path": "/home/user", "kind": "dir", "owner": "user", "text": ""},
    {"path": "/home/user/README.txt", "kind": "file", "owner": "user", "text": "Bienvenue dans FractalOS Userspace Alpha.\n"},
    {"path": "/apps", "kind": "dir", "owner": "root", "text": ""},
    {"path": "/apps/packages.json", "kind": "file", "owner": "root", "text": ""},
    {"path": "/tiles", "kind": "dir", "owner": "root", "text": ""},
    {"path": "/tmp", "kind": "dir", "owner": "user", "text": ""},
]


SESSION_ROLES = {
    "guest": {"home": "/home/guest", "can_write_home": True, "can_install": False, "can_admin": False},
    "user": {"home": "/home/user", "can_write_home": True, "can_install": False, "can_admin": False},
    "admin": {"home": "/home/user", "can_write_home": True, "can_install": True, "can_admin": True},
    "doctor": {"home": "/home/user", "can_write_home": False, "can_install": False, "can_admin": True},
}


def _state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    root = workspace / "state"
    root.mkdir(parents=True, exist_ok=True)
    return root / "native_userspace.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    try:
        tmp_path.replace(path)
    except PermissionError:
        path.write_text(tmp_path.read_text(encoding="utf-8"), encoding="utf-8")
        tmp_path.unlink(missing_ok=True)


def _normalize_path(path: str) -> str:
    clean = (path or "/").replace("\\", "/").strip()
    if not clean.startswith("/"):
        clean = "/" + clean
    while "//" in clean:
        clean = clean.replace("//", "/")
    if len(clean) > 1 and clean.endswith("/"):
        clean = clean[:-1]
    return clean


def _parent(path: str) -> str:
    if path == "/":
        return ""
    parent = path.rsplit("/", 1)[0]
    return parent or "/"


def _default_state() -> dict[str, Any]:
    packages_text = json.dumps(NATIVE_PACKAGE_CATALOG, indent=2, ensure_ascii=True)
    nodes = []
    for item in DEFAULT_VFS_NODES:
        node = dict(item)
        if node["path"] == "/apps/packages.json":
            node["text"] = packages_text + "\n"
        nodes.append(node)
    return {
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "sessions": [],
        "active_session": None,
        "mounts": [
            {"path": "/", "source": "ram-vfs", "mode": "rw", "status": "mounted"},
            {"path": "/home", "source": "storage-vfs", "mode": "rw-journaled", "status": "mounted"},
            {"path": "/tiles", "source": "TileMindFS", "mode": "ro-bridge", "status": "mounted"},
        ],
        "nodes": nodes,
        "packages": [{"id": item["id"], "status": "available", "phase": item["phase"]} for item in NATIVE_PACKAGE_CATALOG],
        "metrics": {
            "sessions_started": 0,
            "reads": 0,
            "writes": 0,
            "package_reads": 0,
            "reports": 0,
        },
    }


def _load_state(workspace: Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        state = _default_state()
        _atomic_write_json(path, state)
        return state
    raw = path.read_text(encoding="utf-8")
    try:
        state = json.loads(raw) if raw.strip() else _default_state()
    except json.JSONDecodeError:
        corrupt_path = path.with_suffix(path.suffix + f".corrupt.{os.getpid()}")
        corrupt_path.write_text(raw, encoding="utf-8")
        state = _default_state()
        _atomic_write_json(path, state)
    state.setdefault("sessions", [])
    mounts = state.setdefault("mounts", _default_state()["mounts"])
    if not any(item.get("path") == "/home" and item.get("source") == "storage-vfs" for item in mounts):
        mounts.insert(1, {"path": "/home", "source": "storage-vfs", "mode": "rw-journaled", "status": "mounted"})
    state.setdefault("nodes", _default_state()["nodes"])
    state.setdefault("packages", [{"id": item["id"], "status": "available", "phase": item["phase"]} for item in NATIVE_PACKAGE_CATALOG])
    metrics = state.setdefault("metrics", {})
    for key in ["sessions_started", "reads", "writes", "package_reads", "reports"]:
        metrics.setdefault(key, 0)
    return state


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _atomic_write_json(_state_path(workspace), state)


def _find_node(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    wanted = _normalize_path(path)
    return next((item for item in state["nodes"] if item["path"] == wanted), None)


def userspace_session_start(workspace: Path, role: str = "user") -> dict[str, Any]:
    normalized = role.strip().lower()
    if normalized not in SESSION_ROLES:
        return {"started": False, "reason": "unknown_role", "roles": sorted(SESSION_ROLES)}
    state = _load_state(workspace)
    session = {
        "id": uuid4().hex[:12],
        "role": normalized,
        "home": SESSION_ROLES[normalized]["home"],
        "started_at": utc_now(),
        "policy": SESSION_ROLES[normalized],
    }
    state["sessions"].append(session)
    state["sessions"] = state["sessions"][-80:]
    state["active_session"] = session
    state["metrics"]["sessions_started"] = int(state["metrics"].get("sessions_started", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "native_userspace_session_started", {"role": normalized, "session_id": session["id"]})
    return {"started": True, "session": session}


def vfs_mount_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    tile = TileMindFS(workspace).report()
    storage = storage_mount_report(workspace)
    return {
        "mounts": state["mounts"],
        "node_count": len(state["nodes"]),
        "file_count": len([item for item in state["nodes"] if item["kind"] == "file"]),
        "dir_count": len([item for item in state["nodes"] if item["kind"] == "dir"]),
        "tile_bridge": tile,
        "storage_bridge": storage,
    }


def vfs_list(workspace: Path, path: str = "/") -> dict[str, Any]:
    state = _load_state(workspace)
    base = _normalize_path(path)
    node = _find_node(state, base)
    if not node:
        return {"listed": False, "reason": "not_found", "path": base}
    if node["kind"] != "dir":
        return {"listed": False, "reason": "not_a_directory", "path": base}
    children = []
    for item in state["nodes"]:
        if item["path"] == base:
            continue
        if _parent(item["path"]) == base:
            children.append({"path": item["path"], "kind": item["kind"], "owner": item["owner"], "size": len(item.get("text", ""))})
    append_event(workspace, "native_vfs_list", {"path": base, "count": len(children)})
    return {"listed": True, "path": base, "children": sorted(children, key=lambda item: item["path"])}


def vfs_read(workspace: Path, path: str) -> dict[str, Any]:
    state = _load_state(workspace)
    normalized = _normalize_path(path)
    node = _find_node(state, normalized)
    if not node:
        stored = storage_read(workspace, normalized)
        if not stored.get("read"):
            return {"read": False, "reason": "not_found", "path": normalized}
        node = {"path": normalized, "kind": "file", "owner": "user", "text": stored.get("text", "")}
        state["nodes"].append(node)
    if node["kind"] != "file":
        return {"read": False, "reason": "not_a_file", "path": normalized}
    state["metrics"]["reads"] = int(state["metrics"].get("reads", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "native_vfs_read", {"path": normalized, "size": len(node.get("text", ""))})
    return {"read": True, "path": normalized, "owner": node["owner"], "text": node.get("text", "")}


def vfs_write(workspace: Path, path: str, text: str, owner: str = "user") -> dict[str, Any]:
    state = _load_state(workspace)
    normalized = _normalize_path(path)
    parent = _parent(normalized)
    if not _find_node(state, parent):
        return {"written": False, "reason": "missing_parent", "path": normalized, "parent": parent}
    node = _find_node(state, normalized)
    if node and node["kind"] != "file":
        return {"written": False, "reason": "not_a_file", "path": normalized}
    if not node:
        node = {"path": normalized, "kind": "file", "owner": owner, "text": ""}
        state["nodes"].append(node)
    node["text"] = text
    node["owner"] = owner
    state["metrics"]["writes"] = int(state["metrics"].get("writes", 0)) + 1
    _save_state(workspace, state)
    temp = workspace / "native_userspace" / "last_write.txt"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text(text, encoding="utf-8")
    tile = TileMindFS(workspace).store_file(temp)
    storage_result = storage_write(workspace, normalized, text, owner=owner) if normalized.startswith("/home/") else {"written": False, "reason": "not_persistent_mount"}
    append_event(
        workspace,
        "native_vfs_write",
        {
            "path": normalized,
            "size": len(text),
            "tile": tile.get("manifest_id", ""),
            "storage_journal": storage_result.get("journal_id", ""),
        },
    )
    return {
        "written": True,
        "path": normalized,
        "owner": owner,
        "size": len(text),
        "tile_manifest": tile.get("manifest_id", ""),
        "storage": storage_result,
    }


def package_manifest(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    state["metrics"]["package_reads"] = int(state["metrics"].get("package_reads", 0)) + 1
    _save_state(workspace, state)
    by_phase: dict[str, int] = {}
    for package in NATIVE_PACKAGE_CATALOG:
        by_phase[package["phase"]] = by_phase.get(package["phase"], 0) + 1
    append_event(workspace, "native_package_manifest_read", {"packages": len(NATIVE_PACKAGE_CATALOG)})
    return {
        "path": "/apps/packages.json",
        "packages": NATIVE_PACKAGE_CATALOG,
        "by_phase": by_phase,
        "policy": "plan-only until native VFS, signatures and rollback slots are enforced in-kernel",
    }


def userspace_alpha_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    state["metrics"]["reports"] = int(state["metrics"].get("reports", 0)) + 1
    _save_state(workspace, state)
    report = {
        "generated_at": utc_now(),
        "mode": "userspace_vfs_alpha",
        "active_session": state.get("active_session"),
        "mounts": state["mounts"],
        "node_count": len(state["nodes"]),
        "package_count": len(NATIVE_PACKAGE_CATALOG),
        "storage_vfs": storage_mount_report(workspace),
        "metrics": state["metrics"],
        "truth": {
            "runtime_vfs_usable": True,
            "native_kernel_vfs_probe": True,
            "hosted_persistent_storage_vfs": True,
            "persistent_native_disk_write": False,
            "reason": "Runtime has RAM VFS plus hosted Storage VFS journal; kernel has VFS/package probes; real native block-device writes still need a storage driver.",
        },
    }
    append_event(workspace, "native_userspace_report", {"nodes": report["node_count"], "packages": report["package_count"]})
    return report


def write_userspace_alpha_report(workspace: Path) -> dict[str, Any]:
    report = userspace_alpha_report(workspace)
    root = workspace / "native_userspace"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"USERSPACE_ALPHA_{len(list(root.glob('USERSPACE_ALPHA_*.md'))) + 1:04d}.md"
    lines = [
        "# FractalOS Userspace + VFS Alpha",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Runtime VFS usable: {report['truth']['runtime_vfs_usable']}",
        f"- Kernel VFS probe: {report['truth']['native_kernel_vfs_probe']}",
        f"- Hosted Storage VFS: {report['truth']['hosted_persistent_storage_vfs']}",
        f"- Persistent native disk write: {report['truth']['persistent_native_disk_write']}",
        f"- Nodes: {report['node_count']}",
        f"- Packages: {report['package_count']}",
        f"- Storage files: {report['storage_vfs']['file_count']}",
        f"- Storage journal: {report['storage_vfs']['journal_count']}",
        "",
        "## Mounts",
    ]
    for mount in report["mounts"]:
        lines.append(f"- {mount['path']} :: {mount['source']} :: {mount['mode']} :: {mount['status']}")
    lines.extend(["", "## Truth", report["truth"]["reason"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"native_userspace::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="native_userspace",
    )
    return {"report": report, "report_path": str(path), "tile_manifest": tile.get("manifest_id", "")}
