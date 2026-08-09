# FractalOS Classic OS Capability Matrix

Date: 2026-04-26

## Short answer

FractalOS can boot as a real x86_64 OS prototype from ISO in QEMU BIOS and QEMU UEFI. Stage22 adds native userspace/VFS/package/storage probes plus a hosted persistent Storage VFS model. It is not yet usable as a daily Windows/Linux replacement.

Runtime command:

```powershell
python -m omega_tile_os classic-os-report --workspace .\workspace
python -m omega_tile_os onboarding-pack --workspace .\workspace
python -m omega_tile_os native-os-report --workspace .\workspace
python -m omega_tile_os native-os-install-plan --workspace .\workspace --target vm --create-vm-disk
python -m omega_tile_os userspace-alpha-report --workspace .\workspace
python -m omega_tile_os storage-vfs-report --workspace .\workspace
```

## Capability matrix

| Capability | Bare-metal FractalOS today | Hosted control plane today | Target next |
|---|---:|---:|---|
| Bootable ISO | Yes | N/A | Physical USB validation |
| QEMU BIOS boot | Yes | N/A | Automated boot test |
| QEMU UEFI boot | Yes, after OVMF key prompt | N/A | Remove OVMF volume warning |
| Persistent VM install | Planned, not self-hosted yet | VM disk profile and install report | Native storage/VFS installer |
| Userspace/VFS | Kernel probes + RAM VFS + storage plane model | Sessions, `/home/user`, `/apps/packages.json`, TileMindFS bridge, hosted persistent Storage VFS | Native writable storage-backed VFS |
| Desktop for office work | No, kernel has desktop-plane primitives only | Login/start/search/explorer/package/office/media model and dashboard | Real compositor/window manager |
| Internet/browser | No native network stack/browser | Uses host internet if Windows has access | NIC driver + TCP/IP + browser container |
| PNG/JPEG/TXT/PDF handling | No native viewers yet | Host/Python can manipulate files | VFS + file associations + viewers |
| Video playback | No | Host can use external apps | Audio/video drivers + codecs |
| Read/write/modify files | No persistent native VFS yet; storage plane is telemetry only | Yes through host filesystem and Stage22 `/home` Storage VFS | Native VFS and storage driver |
| Word/LibreOffice docs | No native suite | Host apps can open them | Office app containers or compatibility layer |
| Execute `.exe` | No | Windows host can | VM/Wine-like compatibility domain |
| Install Python/Rust/Java modules | No native package manager | Host can install toolchains | Package manager + runtime domains |
| Intuitive onboarding | Partial docs + overlay model | Yes, guide/doctor/dashboard | First-run tips overlay |
| User sessions | No native auth/session isolation | Workspace roles can be modeled | guest/user/admin, permissions and homes |
| AI workers | Kernel has foundry primitives | Yes, local orchestrator + Ollama bridge | Agent domains tied to kernel policies |
| Auto-upgrade | No native patcher yet | Yes, guarded auto-upgrade loop | Boot-slot update integration |
| Error logging/recovery | Kernel serial only | Usage black-box + restart recovery | Unified kernel/user error journal |

## What can be imported from classic OS design

- Process model: ring 3 processes, syscall ABI, scheduling classes and clean termination.
- Filesystem: VFS, file permissions, file associations, mount table, journaling and snapshots.
- Desktop: compositor, window manager, input stack, clipboard, notifications and settings.
- Networking: NIC drivers, TCP/IP, DNS, TLS, browser/runtime sandbox.
- Users: guest/user/admin sessions, home directories, privilege escalation and audit logs.
- Package system: signed packages, rollback, dependency solver and runtime registries.
- Installation: EFI, boot A/B, system, state, home and recovery partitions with safe restart gates.
- Hardware: ACPI power, APIC, HPET, PCIe enumeration, USB, storage and GPU drivers.
- Compatibility: ELF first, then hosted `.exe` execution through VM/domain isolation.

## What makes FractalOS different

- Intent-first desktop: the top layer is an overlay of goals, proof, energy and agents.
- Triple kernel model: Matter for hardware, Mind for agents/formulas, Mesh for storage/network topology.
- Proof-gated auto-upgrade: candidates must pass doctor, tests, build and recovery gates.
- Corpus-native formulas: `<FORMULA_CORPUS>` is indexed and converted into safe program candidates.
- TileMindFS/OmegaRAM/Storage VFS: hosted memory/storage layers now expose compression, deduplication, hot/warm/cold tiers, persistent `/home`, journal, snapshots and rollback.
