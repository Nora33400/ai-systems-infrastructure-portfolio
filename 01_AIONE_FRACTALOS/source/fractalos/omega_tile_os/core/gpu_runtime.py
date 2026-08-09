from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .autonomy_runtime import autonomy_report
from .hetero_scheduler import available_devices
from .chrono_mesh import mission_journal_report
from .codex_worker import worker_report
from .mesh_federation import mesh_daemon_snapshot, mesh_status
from .state import load_state


def _detect_torch_cuda() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except Exception:
        return {"available": False, "backend": "torch", "reason": "torch_not_installed"}

    try:
        available = bool(torch.cuda.is_available())
        count = int(torch.cuda.device_count()) if available else 0
        names = [str(torch.cuda.get_device_name(index)) for index in range(count)] if available else []
        return {
            "available": available,
            "backend": "torch",
            "device_count": count,
            "device_names": names,
            "version": getattr(torch, "__version__", "unknown"),
        }
    except Exception as exc:
        return {"available": False, "backend": "torch", "reason": str(exc)}


def _detect_cupy() -> dict[str, Any]:
    try:
        import cupy  # type: ignore
    except Exception:
        return {"available": False, "backend": "cupy", "reason": "cupy_not_installed"}

    try:
        count = int(cupy.cuda.runtime.getDeviceCount())
        names = []
        for index in range(count):
            props = cupy.cuda.runtime.getDeviceProperties(index)
            names.append(props["name"].decode("utf-8"))
        return {
            "available": count > 0,
            "backend": "cupy",
            "device_count": count,
            "device_names": names,
            "version": getattr(cupy, "__version__", "unknown"),
        }
    except Exception as exc:
        return {"available": False, "backend": "cupy", "reason": str(exc)}


def detect_gpu_runtime(workspace: Path) -> dict[str, Any]:
    devices = available_devices(workspace)
    nvidia_smi = shutil.which("nvidia-smi")
    runtimes = [_detect_torch_cuda(), _detect_cupy()]
    native = next((item for item in runtimes if item.get("available")), None)
    return {
        "devices": devices["devices"],
        "mode": devices["mode"],
        "nvidia_smi_present": bool(nvidia_smi),
        "native_runtime_available": bool(native),
        "selected_runtime": native,
        "probes": runtimes,
    }


def _matrix_stub(size: int) -> float:
    total = 0.0
    for row in range(size):
        for col in range(size):
            total += ((row + 1) * (col + 3)) % 17
    return total


def gpu_execute_stub(workspace: Path, device_id: str, size: int = 96) -> dict[str, Any]:
    runtime = detect_gpu_runtime(workspace)
    selected = runtime.get("selected_runtime")
    backend = "simulated"
    duration_hint_ms = round(6.0 + size * 0.22, 3)

    if selected and selected.get("backend") == "torch":
        try:
            import time
            import torch  # type: ignore

            device_index = max(int(device_id.split(".")[-1]) - 1, 0)
            started = time.perf_counter()
            x = torch.rand((size, size), device=f"cuda:{device_index}")
            y = torch.rand((size, size), device=f"cuda:{device_index}")
            z = x @ y
            checksum = float(z.sum().item())
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
            backend = "torch-cuda"
            return {
                "ok": True,
                "device_id": device_id,
                "backend": backend,
                "elapsed_ms": elapsed_ms,
                "checksum": round(checksum, 4),
            }
        except Exception as exc:
            return {
                "ok": False,
                "device_id": device_id,
                "backend": "torch-cuda",
                "error": str(exc),
            }

    checksum = round(_matrix_stub(size), 4)
    return {
        "ok": True,
        "device_id": device_id,
        "backend": backend,
        "elapsed_ms": duration_hint_ms,
        "checksum": checksum,
    }


def mission_control_snapshot(workspace: Path) -> dict[str, Any]:
    state = load_state(workspace)
    runtime = detect_gpu_runtime(workspace)
    mesh = mesh_status(workspace)
    daemon = mesh_daemon_snapshot(workspace)
    journal = mission_journal_report(workspace)
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    return {
        "node": state["node"],
        "metrics": state["metrics"],
        "gpu_runtime": runtime,
        "mesh": mesh,
        "mesh_daemon": daemon,
        "mission_journal": journal,
        "autonomy": autonomy,
        "worker": worker,
    }
