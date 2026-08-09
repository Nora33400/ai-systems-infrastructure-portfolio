from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import append_event
from .ram_memory import OmegaRAM
from .state import ensure_workspace, utc_now
from ..tilemindfs.store import TileMindFS


STORAGE_STAGE = "stage22-storage-vfs-journal-alpha"
SEED_TEXT = "FractalOS Stage22 Storage VFS: persistent hosted home is online.\n"


def _state_path(workspace: Path) -> Path:
    ensure_workspace(workspace)
    root = workspace / "state"
    root.mkdir(parents=True, exist_ok=True)
    return root / "storage_vfs.json"


def _storage_root(workspace: Path) -> Path:
    root = workspace / "storage_vfs" / "root"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _snapshot_root(workspace: Path) -> Path:
    root = workspace / "storage_vfs" / "snapshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _report_root(workspace: Path) -> Path:
    root = workspace / "storage_vfs" / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    try:
        tmp_path.replace(path)
    except PermissionError:
        path.write_text(tmp_path.read_text(encoding="utf-8"), encoding="utf-8")
        tmp_path.unlink(missing_ok=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_path(path: str) -> str:
    clean = (path or "/").replace("\\", "/").strip()
    if not clean.startswith("/"):
        clean = "/" + clean
    while "//" in clean:
        clean = clean.replace("//", "/")
    if len(clean) > 1 and clean.endswith("/"):
        clean = clean[:-1]
    parts = []
    for part in clean.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            continue
        parts.append(part)
    return "/" + "/".join(parts) if parts else "/"


def _physical_path(workspace: Path, virtual_path: str) -> Path:
    normalized = _normalize_path(virtual_path)
    root = _storage_root(workspace)
    if normalized == "/":
        return root
    return root.joinpath(*normalized.strip("/").split("/"))


def _default_state() -> dict[str, Any]:
    now = utc_now()
    return {
        "stage": STORAGE_STAGE,
        "created_at": now,
        "updated_at": now,
        "mount": {
            "path": "/home",
            "source": "storage-vfs",
            "mode": "rw-journaled",
            "status": "mounted",
        },
        "journal": [],
        "snapshots": [],
        "metrics": {
            "bootstraps": 0,
            "reads": 0,
            "writes": 0,
            "snapshots": 0,
            "rollbacks": 0,
            "reports": 0,
            "verifications": 0,
        },
    }


def _ensure_bootstrap_file(workspace: Path, state: dict[str, Any]) -> None:
    seed = _physical_path(workspace, "/home/user/STORAGE_VFS.txt")
    if seed.exists():
        return
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(SEED_TEXT, encoding="utf-8")
    state.setdefault("metrics", {}).setdefault("bootstraps", 0)
    state["metrics"]["bootstraps"] = int(state["metrics"].get("bootstraps", 0)) + 1


def _load_state(workspace: Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        state = _default_state()
        _ensure_bootstrap_file(workspace, state)
        _atomic_write_json(path, state)
        return state
    raw = path.read_text(encoding="utf-8")
    try:
        state = json.loads(raw) if raw.strip() else _default_state()
    except json.JSONDecodeError:
        corrupt_path = path.with_suffix(path.suffix + f".corrupt.{os.getpid()}")
        corrupt_path.write_text(raw, encoding="utf-8")
        state = _default_state()
    state.setdefault("stage", STORAGE_STAGE)
    state.setdefault("mount", _default_state()["mount"])
    state.setdefault("journal", [])
    state.setdefault("snapshots", [])
    metrics = state.setdefault("metrics", {})
    for key in ["bootstraps", "reads", "writes", "snapshots", "rollbacks", "reports", "verifications"]:
        metrics.setdefault(key, 0)
    _ensure_bootstrap_file(workspace, state)
    _atomic_write_json(path, state)
    return state


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _atomic_write_json(_state_path(workspace), state)


def _scan_files(workspace: Path, include_text: bool = False) -> list[dict[str, Any]]:
    root = _storage_root(workspace)
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8")
        item: dict[str, Any] = {
            "path": "/" + rel,
            "size": len(text.encode("utf-8")),
            "sha256": _hash_text(text),
        }
        if include_text:
            item["text"] = text
        files.append(item)
    return files


def storage_mount_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    files = _scan_files(workspace)
    return {
        "stage": state.get("stage", STORAGE_STAGE),
        "mount": state["mount"],
        "file_count": len(files),
        "byte_count": sum(int(item["size"]) for item in files),
        "journal_count": len(state.get("journal", [])),
        "snapshot_count": len(state.get("snapshots", [])),
        "latest_snapshot": state.get("snapshots", [])[-1] if state.get("snapshots") else None,
        "metrics": state.get("metrics", {}),
        "files": files[-12:],
        "truth": {
            "hosted_persistent_vfs": True,
            "native_disk_driver": False,
            "reason": "Stage22 persists files in the hosted workspace and proves the journal path; native block storage driver remains the next gate.",
        },
    }


def storage_write(workspace: Path, path: str, text: str, owner: str = "user") -> dict[str, Any]:
    state = _load_state(workspace)
    normalized = _normalize_path(path)
    if not (normalized.startswith("/home/") or normalized == "/home"):
        return {"written": False, "reason": "outside_persistent_home", "path": normalized}
    physical = _physical_path(workspace, normalized)
    physical.parent.mkdir(parents=True, exist_ok=True)
    before_text = physical.read_text(encoding="utf-8") if physical.exists() else None
    physical.write_text(text, encoding="utf-8")
    tile = TileMindFS(workspace).store_file(physical)
    entry = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "action": "write",
        "path": normalized,
        "owner": owner,
        "before_sha256": _hash_text(before_text) if before_text is not None else None,
        "after_sha256": _hash_text(text),
        "before_text": before_text,
        "after_size": len(text.encode("utf-8")),
        "tile_manifest": tile.get("manifest_id", ""),
    }
    state["journal"].append(entry)
    state["journal"] = state["journal"][-200:]
    state["metrics"]["writes"] = int(state["metrics"].get("writes", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "storage_vfs_write", {"path": normalized, "journal_id": entry["id"], "tile": entry["tile_manifest"]})
    return {
        "written": True,
        "path": normalized,
        "physical_path": str(physical),
        "journal_id": entry["id"],
        "sha256": entry["after_sha256"],
        "tile_manifest": entry["tile_manifest"],
    }


def storage_read(workspace: Path, path: str) -> dict[str, Any]:
    state = _load_state(workspace)
    normalized = _normalize_path(path)
    physical = _physical_path(workspace, normalized)
    if not physical.exists() or not physical.is_file():
        return {"read": False, "reason": "not_found", "path": normalized}
    text = physical.read_text(encoding="utf-8")
    state["metrics"]["reads"] = int(state["metrics"].get("reads", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "storage_vfs_read", {"path": normalized, "size": len(text)})
    return {"read": True, "path": normalized, "text": text, "sha256": _hash_text(text)}


def storage_snapshot(workspace: Path, label: str = "manual") -> dict[str, Any]:
    state = _load_state(workspace)
    files = _scan_files(workspace, include_text=True)
    snapshot_id = f"svfs-{len(state.get('snapshots', [])) + 1:04d}"
    payload = {
        "id": snapshot_id,
        "label": label,
        "created_at": utc_now(),
        "stage": STORAGE_STAGE,
        "files": files,
    }
    path = _snapshot_root(workspace) / f"{snapshot_id}.json"
    _atomic_write_json(path, payload)
    tile = TileMindFS(workspace).store_file(path)
    record = {
        "id": snapshot_id,
        "label": label,
        "created_at": payload["created_at"],
        "file_count": len(files),
        "byte_count": sum(int(item["size"]) for item in files),
        "path": str(path),
        "tile_manifest": tile.get("manifest_id", ""),
    }
    state["snapshots"].append(record)
    state["snapshots"] = state["snapshots"][-80:]
    state["metrics"]["snapshots"] = int(state["metrics"].get("snapshots", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "storage_vfs_snapshot", {"snapshot_id": snapshot_id, "files": len(files)})
    return {"snapshotted": True, "snapshot": record}


def _load_snapshot(workspace: Path, target: str) -> dict[str, Any] | None:
    state = _load_state(workspace)
    if target == "latest-snapshot":
        if not state.get("snapshots"):
            return None
        target = str(state["snapshots"][-1]["id"])
    path = _snapshot_root(workspace) / f"{target}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def storage_rollback(workspace: Path, target: str = "last-write") -> dict[str, Any]:
    state = _load_state(workspace)
    if target == "last-write":
        entry = next((item for item in reversed(state.get("journal", [])) if item.get("action") == "write"), None)
        if not entry:
            return {"rolled_back": False, "reason": "no_write_journal"}
        physical = _physical_path(workspace, str(entry["path"]))
        before_text = entry.get("before_text")
        if before_text is None:
            physical.unlink(missing_ok=True)
        else:
            physical.parent.mkdir(parents=True, exist_ok=True)
            physical.write_text(str(before_text), encoding="utf-8")
        state["metrics"]["rollbacks"] = int(state["metrics"].get("rollbacks", 0)) + 1
        rollback_entry = {
            "id": uuid4().hex[:12],
            "ts": utc_now(),
            "action": "rollback-last-write",
            "path": entry["path"],
            "target_journal_id": entry["id"],
        }
        state["journal"].append(rollback_entry)
        _save_state(workspace, state)
        append_event(workspace, "storage_vfs_rollback", {"target": target, "path": entry["path"]})
        return {"rolled_back": True, "target": target, "path": entry["path"], "journal_id": rollback_entry["id"]}

    snapshot = _load_snapshot(workspace, target)
    if not snapshot:
        return {"rolled_back": False, "reason": "snapshot_not_found", "target": target}
    root = _storage_root(workspace)
    wanted = {str(item["path"]): str(item.get("text", "")) for item in snapshot.get("files", [])}
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            rel = "/" + path.relative_to(root).as_posix()
            if rel not in wanted:
                path.unlink(missing_ok=True)
    for virtual_path, text in wanted.items():
        physical = _physical_path(workspace, virtual_path)
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_text(text, encoding="utf-8")
    state["metrics"]["rollbacks"] = int(state["metrics"].get("rollbacks", 0)) + 1
    rollback_entry = {
        "id": uuid4().hex[:12],
        "ts": utc_now(),
        "action": "rollback-snapshot",
        "snapshot_id": snapshot["id"],
        "restored_files": len(wanted),
    }
    state["journal"].append(rollback_entry)
    _save_state(workspace, state)
    append_event(workspace, "storage_vfs_rollback", {"target": target, "files": len(wanted)})
    return {"rolled_back": True, "target": target, "snapshot_id": snapshot["id"], "restored_files": len(wanted)}


def storage_verify(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    files = _scan_files(workspace)
    errors = []
    for item in files:
        physical = _physical_path(workspace, str(item["path"]))
        if not physical.exists():
            errors.append({"path": item["path"], "error": "missing"})
            continue
        text = physical.read_text(encoding="utf-8")
        if _hash_text(text) != item["sha256"]:
            errors.append({"path": item["path"], "error": "hash_mismatch"})
    state["metrics"]["verifications"] = int(state["metrics"].get("verifications", 0)) + 1
    _save_state(workspace, state)
    append_event(workspace, "storage_vfs_verify", {"ok": not errors, "files": len(files), "errors": len(errors)})
    return {"ok": not errors, "file_count": len(files), "errors": errors, "stage": STORAGE_STAGE}


def storage_vfs_report(workspace: Path) -> dict[str, Any]:
    state = _load_state(workspace)
    state["metrics"]["reports"] = int(state["metrics"].get("reports", 0)) + 1
    _save_state(workspace, state)
    mount = storage_mount_report(workspace)
    verify = storage_verify(workspace)
    score = min(
        1.0,
        0.34 * (1.0 if mount["file_count"] > 0 else 0.0)
        + 0.26 * (1.0 if verify["ok"] else 0.0)
        + 0.20 * min(1.0, mount["journal_count"] / 4.0)
        + 0.20 * min(1.0, mount["snapshot_count"] / 2.0),
    )
    return {
        "generated_at": utc_now(),
        "stage": STORAGE_STAGE,
        "mount": mount,
        "verify": verify,
        "formulas": {
            "PersistenceScore": "0.34*has_files + 0.26*verify_ok + 0.20*journal_density + 0.20*snapshot_density",
            "persistence_score": round(score, 4),
        },
    }


def write_storage_vfs_report(workspace: Path) -> dict[str, Any]:
    report = storage_vfs_report(workspace)
    root = _report_root(workspace)
    path = root / f"STORAGE_VFS_{len(list(root.glob('STORAGE_VFS_*.md'))) + 1:04d}.md"
    mount = report["mount"]
    lines = [
        "# FractalOS Stage22 Storage VFS",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Stage: {report['stage']}",
        f"- Files: {mount['file_count']}",
        f"- Bytes: {mount['byte_count']}",
        f"- Journal entries: {mount['journal_count']}",
        f"- Snapshots: {mount['snapshot_count']}",
        f"- Verify OK: {report['verify']['ok']}",
        f"- Persistence score: {report['formulas']['persistence_score']}",
        "",
        "## Mount",
        f"- {mount['mount']['path']} :: {mount['mount']['source']} :: {mount['mount']['mode']} :: {mount['mount']['status']}",
        "",
        "## Formula",
        f"- PersistenceScore = {report['formulas']['PersistenceScore']}",
        "",
        "## Truth Gate",
        f"- Hosted persistent VFS: {mount['truth']['hosted_persistent_vfs']}",
        f"- Native disk driver: {mount['truth']['native_disk_driver']}",
        f"- Reason: {mount['truth']['reason']}",
        "",
        "## Files",
    ]
    for item in mount["files"]:
        lines.append(f"- {item['path']} :: {item['size']} bytes :: {item['sha256'][:12]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tile = TileMindFS(workspace).store_file(path)
    OmegaRAM(workspace).put_text(
        key=f"storage_vfs::{path.stem}",
        text=path.read_text(encoding="utf-8"),
        source="storage_vfs",
    )
    append_event(workspace, "storage_vfs_report", {"path": str(path), "tile": tile.get("manifest_id", "")})
    return {"report": report, "report_path": str(path), "tile_manifest": tile.get("manifest_id", "")}
