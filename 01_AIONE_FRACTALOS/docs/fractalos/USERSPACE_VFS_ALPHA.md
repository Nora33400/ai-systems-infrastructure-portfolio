# FractalOS Userspace + VFS Alpha

Date: 2026-04-26

## Purpose

This layer turns the previous desktop/install blueprint into a first usable OS matter model: sessions, a RAM-backed VFS, home directories, package manifests and a TileMindFS bridge.

## What exists now

- Runtime sessions: `guest`, `user`, `admin`, `doctor`.
- RAM VFS mount at `/`.
- TileMindFS bridge at `/tiles`.
- System release file at `/etc/fractalos-release`.
- User home at `/home/user`.
- Package manifest at `/apps/packages.json`.
- Kernel probes for VFS node count, file open count, package availability and package policy score.

## Commands

```powershell
python -m omega_tile_os userspace-alpha-report --workspace .\workspace
python -m omega_tile_os userspace-alpha-status --workspace .\workspace
python -m omega_tile_os session-start --workspace .\workspace --role user
python -m omega_tile_os vfs-mounts --workspace .\workspace
python -m omega_tile_os vfs-ls --workspace .\workspace --path /
python -m omega_tile_os vfs-read --workspace .\workspace --path /etc/fractalos-release
python -m omega_tile_os vfs-write --workspace .\workspace --path /home/user/hello.txt --text "FractalOS alive"
python -m omega_tile_os package-manifest --workspace .\workspace
```

## Kernel bridge

The bare-metal kernel now exposes:

- `fk_vfs_init`
- `fk_vfs_node_count`
- `fk_vfs_open_home_readme`
- `fk_package_init`
- `fk_package_available_count`
- `fk_package_policy_score`

The boot log should include:

- `VFS mounts=... nodes=... opens=...`
- `Packages manifests=... available=... policy=...`

## Truth gate

This is not yet a real disk filesystem. It is a RAM VFS model plus kernel probes. The next native gate is a writable storage-backed VFS connected to the persistent VM disk.
