# FractalOS Storage VFS Stage22

Date: 2026-04-26

## What Stage22 Adds

Stage22 turns the hosted `/home` model into a persistent, journaled Storage VFS layer while exposing the same idea to the bare-metal kernel as a storage plane.

This is not yet a native SATA/NVMe block driver. It is a safe bridge step: FractalOS now has a persistent hosted home, snapshots, rollback, Doctor verification, UI actions, CLI commands and kernel-visible storage telemetry.

## Core Idea

Storage is treated as living state, not only bytes on a disk.

- Files under `/home/...` are persisted in `workspace/storage_vfs/root`.
- Every write is journaled before promotion.
- Snapshots capture the persistent home tree and can be restored.
- Rollback can undo the last write or restore a named snapshot.
- Doctor verifies that persistent state can be mounted, checked and reported.
- The bare-metal kernel exposes a Stage22 storage plane with slots, journal count, snapshot count and persistence score.

## Formula

Stage22 uses a conservative persistence score:

```text
PersistenceScore = 0.34*has_files + 0.26*verify_ok + 0.20*journal_density + 0.20*snapshot_density
```

The score favors safety over spectacle: a storage layer is considered useful only if it has files, can verify itself, and records enough history to recover.

## Commands

```powershell
python -m omega_tile_os storage-vfs-status --workspace .\workspace
python -m omega_tile_os storage-vfs-write --workspace .\workspace --path /home/user/notes.txt --text "FractalOS persists"
python -m omega_tile_os storage-vfs-read --workspace .\workspace --path /home/user/notes.txt
python -m omega_tile_os storage-vfs-snapshot --workspace .\workspace --label stage22-checkpoint
python -m omega_tile_os storage-vfs-rollback --workspace .\workspace --target latest-snapshot
python -m omega_tile_os storage-vfs-verify --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
python -m omega_tile_os doctor --workspace .\workspace
```

## Desktop And Dashboard Actions

The UI runtime now exposes the `storage-vfs-stage22` view with quick actions for report, status, demo write, snapshot and verify. The dashboard routes the same actions through the local hosted runtime.

## Bare-Metal Integration

The kernel includes:

- `kernel/core/storage_plane.c`
- `fk_storage_plane_init`
- `fk_storage_plane_report`
- storage syscalls `26` to `29`
- console commands `storage` and `storage-snapshot`
- serial boot trace containing `StorageVFS`

This makes storage state visible in the booted ISO even before a real disk driver is implemented.

## Truth Gate

What is real now:

- bootable ISO with Stage22 kernel plane;
- hosted persistent `/home` writes;
- journaling, verification, snapshots and rollback;
- Doctor and tests covering Stage22;
- ISO packaging of the Stage22 documentation and source.

What remains for a daily native OS:

- real native block driver;
- kernel-backed persistent VFS;
- ring3 init/session handoff;
- file associations and native viewers;
- native package install and rollback into A/B slots.

## Next Milestone

Stage23 should connect this storage truth to native execution:

- add a block-device abstraction and fake-disk test harness;
- map `/home` and `/state` to a storage-backed kernel VFS;
- create file associations for text, images, PDF, office and media;
- prepare the ELF/ring3 init handoff;
- promote package/runtime domains only after rollback verification.
