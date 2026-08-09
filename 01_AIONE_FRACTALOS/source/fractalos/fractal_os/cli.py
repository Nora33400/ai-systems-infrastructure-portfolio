from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import stage_iso_tree, try_build_iso
from .fusion_registry import FUSION_REGISTRY
from .fusion_runtime import stage_fusion_runtime
from .report import full_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="fractal_os", description="FractalOS fusion tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fusion-report")
    sub.add_parser("build-report")

    runtime_parser = sub.add_parser("stage-runtime")
    runtime_parser.add_argument("--output-dir", default=None)

    stage_parser = sub.add_parser("stage-iso")
    stage_parser.add_argument("--output-dir", default=None)

    build_parser = sub.add_parser("build-iso")
    build_parser.add_argument("--output-dir", default=None)
    build_parser.add_argument("--output-iso", default=None)

    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.command == "fusion-report":
        print(json.dumps(FUSION_REGISTRY, indent=2, ensure_ascii=True))
        return

    if args.command == "build-report":
        print(json.dumps(full_report(root), indent=2, ensure_ascii=True))
        return

    if args.command == "stage-runtime":
        out = stage_fusion_runtime(Path(args.output_dir).resolve() if args.output_dir else None)
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return

    if args.command == "stage-iso":
        out = stage_iso_tree(Path(args.output_dir).resolve() if args.output_dir else None)
        print(json.dumps({"staged": True, "iso_root": str(out)}, indent=2, ensure_ascii=True))
        return

    if args.command == "build-iso":
        iso_root = stage_iso_tree(Path(args.output_dir).resolve() if args.output_dir else None)
        output_iso = Path(args.output_iso).resolve() if args.output_iso else (root / "build" / "FractalOS.iso")
        print(json.dumps(try_build_iso(iso_root, output_iso), indent=2, ensure_ascii=True))
        return
