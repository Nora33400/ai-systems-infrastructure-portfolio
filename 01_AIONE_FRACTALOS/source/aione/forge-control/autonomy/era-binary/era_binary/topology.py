"""Local hardware and model topology discovery without network access."""

from __future__ import annotations

import csv
import ctypes
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import shutil
import string
import subprocess
from typing import Any


def _run(command: list[str], timeout: float = 5.0) -> str:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _memory_total_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _discover_gpus() -> list[dict[str, Any]]:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,memory.used,temperature.gpu,utilization.gpu,pstate,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    gpus = []
    for row in csv.reader(output.splitlines(), skipinitialspace=True):
        if len(row) != 9:
            continue
        try:
            gpus.append(
                {
                    "index": int(row[0]),
                    "name": row[1].strip(),
                    "uuid": row[2].strip(),
                    "memoryTotalMb": int(row[3]),
                    "memoryUsedMb": int(row[4]),
                    "temperatureCelsius": int(row[5]),
                    "utilizationPercent": int(row[6]),
                    "performanceState": row[7].strip(),
                    "driverVersion": row[8].strip(),
                }
            )
        except ValueError:
            continue
    return gpus


def _discover_storage() -> list[dict[str, Any]]:
    roots = [Path(f"{letter}:\\") for letter in string.ascii_uppercase] if os.name == "nt" else [Path("/")]
    volumes = []
    for root in roots:
        if not root.exists():
            continue
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            continue
        volumes.append(
            {"mount": str(root), "totalBytes": usage.total, "usedBytes": usage.used, "freeBytes": usage.free}
        )
    return volumes


def _discover_models() -> list[dict[str, Any]]:
    output = _run(["ollama", "list"])
    models = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        models.append({"name": parts[0], "digestPrefix": parts[1], "runtime": "ollama", "observed": True})
    return models


def discover_hardware_topology() -> dict[str, Any]:
    return {
        "schema": "aione.hardware-topology.v1",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "host": {"node": platform.node(), "system": platform.system(), "release": platform.release()},
        "cpu": {
            "architecture": platform.machine(),
            "name": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
            "logicalProcessors": os.cpu_count() or 1,
        },
        "memory": {"totalPhysicalBytes": _memory_total_bytes()},
        "storage": _discover_storage(),
        "gpus": _discover_gpus(),
        "models": _discover_models(),
        "networkInspection": "NOT_PERFORMED",
    }

