"""Command line interface for the ERA Binary reference runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from .benchmark import benchmark_contract_gate
from .hci import compile_hci
from .interpreter import interpret_cir
from .polybinary import build_polybinary, select_morphology
from .scheduler import ComplexityVector
from .topology import discover_hardware_topology


def _emit(value: object, output: str | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output:
        target = Path(output).resolve()
        output_root = Path(os.environ.get("AIONE_HCI_OUTPUT_ROOT", str(Path.cwd() / "runtime" / "era-binary"))).resolve()
        if target != output_root and output_root not in target.parents:
            raise ValueError(f"output must remain under {output_root}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.{os.getpid()}.{uuid4().hex}.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(target)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aione-hci", description="AIONE HCI/CIR reference runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    topology_parser = sub.add_parser("topology")
    topology_parser.add_argument("--output")
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("source")
    compile_parser.add_argument("--output")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("source")
    run_parser.add_argument("--objective", default="")
    run_parser.add_argument("--output")
    poly_parser = sub.add_parser("polybin")
    poly_parser.add_argument("source")
    poly_parser.add_argument("--output")
    benchmark_parser = sub.add_parser("benchmark-report")
    benchmark_parser.add_argument("report")
    benchmark_parser.add_argument("--output")
    args = parser.parse_args(argv)

    if args.command == "topology":
        _emit(discover_hardware_topology(), args.output)
    elif args.command == "compile":
        _emit(compile_hci(Path(args.source).read_text(encoding="utf-8")), args.output)
    elif args.command == "run":
        cir = compile_hci(Path(args.source).read_text(encoding="utf-8"))
        topology = discover_hardware_topology()
        manifest = build_polybinary(cir)
        selection = select_morphology(manifest, topology, ComplexityVector())
        result = interpret_cir(cir, inputs={"user_request": args.objective})
        _emit({"cir": cir, "topology": topology, "polybinary": manifest, "selection": selection, "result": result}, args.output)
    elif args.command == "polybin":
        cir = compile_hci(Path(args.source).read_text(encoding="utf-8"))
        _emit(build_polybinary(cir), args.output)
    elif args.command == "benchmark-report":
        _emit(benchmark_contract_gate(Path(args.report)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
