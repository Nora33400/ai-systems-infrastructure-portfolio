# OmegaFusion TimeWarp (4W-equivalent bundle)

Feature-scale bundle (pure Python stdlib):
- Multi-agent runtime (planner/coder/debugger/tester/applier/doc/forge)
- Ω-time orchestrator + CoherenceGuard + PolicyEngine
- ToolRouter sandbox (workspace-only)
- Append-only JSONL ledger
- CmdForge: create new CLI commands on the fly (`omega forge ...`)
- Dynamic command router (loads `workspace/commands/*.json`)
- Realtime dashboard with Forge panel + pause/resume/step/approve controls

## Quickstart
1) Init:
   python runtime/cli/omega.py init --workspace ./omega_ws
2) Run daemon:
   python runtime/daemon/omega_daemon.py --workspace ./omega_ws --port 8787
3) Open:
   http://127.0.0.1:8787/

## TimeWarp v2: .exe launcher
This bundle includes a Windows-friendly launcher entrypoint:

- Source: `launcher/omega_launcher.py`
- Build script: `build/build_exe.ps1`

### Build on Windows
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip pyinstaller
.\build\build_exe.ps1
```

### Use
```powershell
.\dist\omega-launcher.exe init --workspace .\omega_ws
.\dist\omega-launcher.exe daemon --workspace .\omega_ws --port 8787
```

## Hybrid Dev Mode (Mode 1 + Mode 2)
Default seed enables `dev_mode: hybrid`:
- Pulse-Weave L/S/M pattern
- Usefulness scoring via `payload.contract`
- Coherence-adaptive fallback using C/P/N metrics

See `docs/DEV_MODES_HYBRID.md`.
