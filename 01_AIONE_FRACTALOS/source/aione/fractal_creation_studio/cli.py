from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .studio import FractalCreationStudio, StudioConfig


def print_payload(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if isinstance(payload, dict):
            for key, value in payload.items():
                print(f"{key}: {value}")
        else:
            print(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fractal-creation-studio", description="Fractal Creation Studio and Tool Customization Runtime.")
    parser.add_argument("--root", default=None, help="Runtime root. Defaults to LOCALAPPDATA/AIONE/CreationStudio.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize runtime folders and default tool runtime.")
    sub.add_parser("status", help="Show runtime status.")
    sub.add_parser("scenario", help="Run the complete acceptance scenario.")
    sub.add_parser("tool-status", help="Show tool runtime counts.")
    sub.add_parser("reset-tools", help="Reset tool runtime to defaults.").add_argument("--recovery", action="store_true")

    create = sub.add_parser("create-project", help="Create an empty interface project.")
    create.add_argument("name")
    create.add_argument("--description", default="")
    create.add_argument("--author", default="the owner")

    preview = sub.add_parser("preview", help="Preview an existing project.")
    preview.add_argument("project", help="Project id or .fractalinterface path.")

    publish = sub.add_parser("publish", help="Publish a project for HUD or spatial runtime.")
    publish.add_argument("project", help="Project id or .fractalinterface path.")
    publish.add_argument("--target", choices=["hud", "spatial"], default="hud")

    export_profile = sub.add_parser("export-profile", help="Export a .fractaltoolprofile archive.")
    export_profile.add_argument("profile_id")
    export_profile.add_argument("--target", default=None)

    import_profile = sub.add_parser("import-profile", help="Import a .fractaltoolprofile archive.")
    import_profile.add_argument("archive")
    import_profile.add_argument("--strategy", choices=["copy", "overwrite"], default="copy")

    return parser


def handle(args: argparse.Namespace) -> Any:
    studio = FractalCreationStudio(StudioConfig.build(args.root))
    if args.command == "init":
        return studio.initialize()
    if args.command == "status":
        return studio.status()
    if args.command == "scenario":
        return studio.run_acceptance_scenario()
    if args.command == "create-project":
        project = studio.create_project(args.name, author=args.author, description=args.description)
        return {"id": project["id"], "path": str(studio.project_path(project)), "validation": studio.validate_project(project)}
    if args.command == "preview":
        return studio.preview_project(studio.load_project(args.project))
    if args.command == "publish":
        project = studio.load_project(args.project)
        result = studio.publish_project(project, args.target)
        studio.save_project(project, reason=f"publish-{args.target}")
        return result
    if args.command == "tool-status":
        state = studio.load_tool_runtime()
        return {
            "tools": len(state.get("tools", {})),
            "presets": len(state.get("presets", {})),
            "profiles": len(state.get("profiles", {})),
            "toolbars": len(state.get("toolbars", {})),
            "usageSamples": len(state.get("usage", [])),
        }
    if args.command == "reset-tools":
        state = studio.reset_tool_runtime(recovery=args.recovery)
        return {"tools": len(state["tools"]), "profiles": len(state["profiles"]), "recovery": bool(args.recovery)}
    if args.command == "export-profile":
        return studio.export_tool_profile(args.profile_id, target=args.target)
    if args.command == "import-profile":
        return studio.import_tool_profile(Path(args.archive), strategy=args.strategy)
    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        print_payload(handle(args), as_json=args.json)
        return 0
    except Exception as exc:
        print(f"component=fractal_creation_studio.cli operation={args.command} cause={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
