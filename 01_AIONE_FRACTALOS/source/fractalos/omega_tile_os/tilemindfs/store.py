from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path
from uuid import uuid4

from ..core.state import load_config


class TileMindFS:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.objects_dir = workspace / "tiles" / "objects"
        self.manifests_dir = workspace / "tiles" / "manifests"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.config = load_config(workspace)["tilemindfs"]

    def _iter_fixed(self, data: bytes, tile_size: int) -> list[bytes]:
        return [data[i : i + tile_size] for i in range(0, len(data), tile_size)] or [b""]

    def _iter_cdc(self, data: bytes) -> list[bytes]:
        min_chunk = int(self.config["min_chunk"])
        max_chunk = int(self.config["max_chunk"])
        boundary_mask = int(self.config["boundary_mask"])
        if not data:
            return [b""]

        chunks = []
        start = 0
        rolling = 0
        for index, byte in enumerate(data):
            rolling = ((rolling << 5) + rolling + byte) & 0xFFFFFFFF
            size = index - start + 1
            boundary_hit = size >= min_chunk and (rolling & boundary_mask) == 0
            max_hit = size >= max_chunk
            if boundary_hit or max_hit:
                chunks.append(data[start : index + 1])
                start = index + 1
                rolling = 0
        if start < len(data):
            chunks.append(data[start:])
        return chunks or [b""]

    def store_file(self, file_path: Path, mode: str = "cdc", tile_size: int | None = None) -> dict:
        data = file_path.read_bytes()
        chosen_tile_size = int(tile_size or self.config["tile_size"])
        chunks = self._iter_cdc(data) if mode == "cdc" else self._iter_fixed(data, chosen_tile_size)

        manifest_tiles = []
        reused = 0
        for chunk in chunks:
            digest = hashlib.sha256(chunk).hexdigest()
            object_path = self.objects_dir / f"{digest}.zlib"
            if object_path.exists():
                reused += 1
            else:
                object_path.write_bytes(zlib.compress(chunk, level=9))
            manifest_tiles.append(
                {
                    "sha256": digest,
                    "raw_size": len(chunk),
                    "compressed_size": object_path.stat().st_size,
                }
            )

        manifest = {
            "manifest_id": uuid4().hex[:12],
            "source_name": file_path.name,
            "source_path": str(file_path),
            "mode": mode,
            "tile_size": chosen_tile_size,
            "file_sha256": hashlib.sha256(data).hexdigest(),
            "raw_size": len(data),
            "tile_count": len(manifest_tiles),
            "reused_tiles": reused,
            "tiles": manifest_tiles,
        }
        manifest_path = self.manifests_dir / f"{manifest['manifest_id']}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
        return manifest

    def reconstruct(self, manifest_id: str, output_path: Path) -> dict:
        manifest_path = self.manifests_dir / f"{manifest_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as handle:
            for tile in manifest["tiles"]:
                raw = zlib.decompress((self.objects_dir / f"{tile['sha256']}.zlib").read_bytes())
                handle.write(raw)
        rebuilt_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return {
            "manifest_id": manifest_id,
            "output": str(output_path),
            "expected_sha256": manifest["file_sha256"],
            "rebuilt_sha256": rebuilt_hash,
            "verified": rebuilt_hash == manifest["file_sha256"],
        }

    def report(self) -> dict:
        manifests = list(self.manifests_dir.glob("*.json"))
        objects = list(self.objects_dir.glob("*.zlib"))
        total_raw = 0
        total_manifest_tiles = 0
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            total_raw += int(manifest.get("raw_size", 0))
            total_manifest_tiles += int(manifest.get("tile_count", 0))
        total_compressed = sum(path.stat().st_size for path in objects)
        ratio = (total_compressed / total_raw) if total_raw else 0.0
        return {
            "manifest_count": len(manifests),
            "unique_tile_objects": len(objects),
            "total_manifest_tiles": total_manifest_tiles,
            "total_raw_size": total_raw,
            "total_compressed_size": total_compressed,
            "compression_ratio": ratio,
        }
