from __future__ import annotations

import json
import shutil
from pathlib import Path

from .fusion_registry import FUSION_REGISTRY


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def source_root() -> Path:
    return project_root().parent


def stage_fusion_runtime(output_dir: Path | None = None) -> dict:
    root = project_root()
    src_root = source_root()
    out = output_dir or (root / "build" / "fusion_runtime")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    manifests = []
    source_specs = [
        {"name": "OmegaSystem", "copy": [src_root / "OmegaSystem" / "README.md", src_root / "OmegaSystem" / "fractal.config.yaml"]},
        {"name": "Omegafusion", "copy": [src_root / "Omegafusion" / "README.md", src_root / "Omegafusion" / "VERSION", src_root / "Omegafusion" / "runtime" / "dashboard" / "index.html"]},
        {"name": "omega_tilemind_os", "copy": [src_root / "omega_tilemind_os" / "README.md", src_root / "omega_tilemind_os" / "docs" / "ARCHITECTURE.md"]},
        {"name": "fractal_ecosystem_build_v6", "copy": [src_root / "fractal_ecosystem_build_v6" / "README.md", src_root / "fractal_ecosystem_build_v6" / "requirements.txt"]},
        {"name": "fractal_auto_evolution_realtime", "copy": [src_root / "fractal_auto_evolution_realtime" / "README.md"]},
        {"name": "local_ai_stack_pack", "copy": [src_root / "local_ai_stack_pack" / "README.md", src_root / "local_ai_stack_pack" / "services" / "agent_board" / "app.py"]},
        {"name": "LAYER_HUD", "copy": [src_root / "LAYER_HUD" / "README.md", src_root / "LAYER_HUD" / "src" / "LayerOSHUD.App" / "Program.cs"]},
        {"name": "hypi", "copy": [src_root / "hypi" / "package.json", src_root / "hypi" / "server.js", src_root / "hypi" / "public" / "index.html"]},
        {"name": "IA", "copy": [src_root / "IA" / "AGENTS.md", src_root / "IA" / "SOUL.md", src_root / "IA" / "USER.md"]},
        {"name": "OmegaSystem2.12", "copy": [src_root / "folder0001" / "OmegaSystem2.12" / "README.md", src_root / "folder0001" / "OmegaSystem2.12" / "docs" / "MODULES_OVERVIEW.md", src_root / "folder0001" / "OmegaSystem2.12" / "scripts" / "fractal_orchestrator.py"]},
    ]

    for spec in source_specs:
        target_dir = out / spec["name"]
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in spec["copy"]:
            if src.exists():
                dst = target_dir / src.name
                shutil.copy2(src, dst)
                copied.append(str(dst))
        manifests.append({"name": spec["name"], "files": copied})

    (out / "fusion_registry.json").write_text(json.dumps(FUSION_REGISTRY, indent=2, ensure_ascii=True), encoding="utf-8")
    (out / "fusion_manifest.json").write_text(json.dumps({"sources": manifests}, indent=2, ensure_ascii=True), encoding="utf-8")
    return {"staged": True, "output": str(out), "sources": manifests}
