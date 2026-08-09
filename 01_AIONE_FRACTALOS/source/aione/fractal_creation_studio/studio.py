from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERFACE_SCHEMA_VERSION = "fractal-interface-project-v1"
TOOL_PROFILE_SCHEMA_VERSION = "fractal-tool-profile-v1"
SUPPORTED_3D_EXTENSIONS = {".obj", ".stl", ".ply", ".gltf", ".glb", ".dae"}
ELEMENT_TYPES = {
    "Workspace",
    "Window",
    "Panel",
    "Widget",
    "Module",
    "Container",
    "Layout",
    "Menu",
    "Toolbar",
    "Button",
    "Input",
    "Label",
    "List",
    "Tree",
    "Table",
    "Graph",
    "Chart",
    "Console",
    "Inspector",
    "Timeline",
    "Canvas",
    "SpatialPanel",
    "Object3D",
    "InteractionZone",
    "ScriptGraph",
    "DataSource",
    "FunctionBinding",
    "EventBinding",
}
VISUAL_STATES = [
    "Normal",
    "Hover",
    "Pressed",
    "Focused",
    "Selected",
    "Disabled",
    "Loading",
    "Error",
    "Warning",
    "Success",
    "Active",
    "Inactive",
    "Dragging",
    "DropTarget",
    "Highlighted",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):013d}-{os.urandom(3).hex()}"


def stable_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:80] or "item"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class StudioConfig:
    root: Path
    max_snapshots: int = 40

    @staticmethod
    def build(root: str | Path | None = None) -> "StudioConfig":
        if root:
            base = Path(root).expanduser().resolve()
        else:
            local_app = os.environ.get("LOCALAPPDATA")
            base = Path(local_app) / "AIONE" / "CreationStudio" if local_app else Path.home() / ".aione" / "CreationStudio"
        return StudioConfig(root=base)


class FractalCreationStudio:
    def __init__(self, config: StudioConfig | None = None) -> None:
        self.config = config or StudioConfig.build()
        self.root = self.config.root
        self.projects_dir = self.root / "projects"
        self.assets_dir = self.root / "assets"
        self.snapshots_dir = self.root / "snapshots"
        self.exports_dir = self.root / "exports"
        self.tools_path = self.root / "tool-runtime" / "tool-runtime.json"

    def initialize(self) -> dict[str, Any]:
        for path in [self.projects_dir, self.assets_dir, self.snapshots_dir, self.exports_dir, self.tools_path.parent]:
            path.mkdir(parents=True, exist_ok=True)
        if not self.tools_path.exists():
            self.save_tool_runtime(self.default_tool_runtime())
        return self.status()

    def status(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        return {
            "name": "Fractal Creation Studio",
            "root": str(self.root),
            "projects": len(list(self.projects_dir.glob("*.fractalinterface"))) if self.projects_dir.exists() else 0,
            "tool_runtime": self.tools_path.exists(),
            "schemas": {
                "interface": INTERFACE_SCHEMA_VERSION,
                "tool_profile": TOOL_PROFILE_SCHEMA_VERSION,
            },
        }

    def create_project(self, name: str, *, author: str = "the owner", description: str = "") -> dict[str, Any]:
        self.initialize()
        project_id = new_id("IFACE")
        now = utc_now()
        project = {
            "schemaVersion": INTERFACE_SCHEMA_VERSION,
            "id": project_id,
            "metadata": {
                "name": name.strip() or "Interface Project",
                "description": description,
                "author": author,
                "createdAt": now,
                "updatedAt": now,
                "version": "0.1.0",
                "provenance": "fractal-creation-studio",
            },
            "themes": {},
            "styles": {},
            "windows": {},
            "widgets": {},
            "modules": {},
            "components": {},
            "assets": {},
            "models3D": {},
            "interactionZones": {},
            "visualScripts": {},
            "textScripts": {},
            "dataSources": {},
            "functionBindings": {},
            "eventBindings": {},
            "templates": {},
            "presets": {},
            "tests": {},
            "documentation": {},
            "scene": {
                "id": new_id("SCENE"),
                "name": "Scene",
                "hierarchy": ["Environment", "Interfaces", "Objects", "Lights", "Cameras", "InteractionZones", "Effects", "RuntimeObjects"],
                "layers": self.default_layers(),
                "mode": "edit",
            },
            "clipboard": None,
            "undoStack": [],
            "redoStack": [],
            "versions": [],
            "published": {"hud": [], "spatial": []},
            "history": [{"at": now, "action": "create_project", "message": name}],
        }
        self.add_theme(project, "Fractal", self.default_theme("Fractal"))
        self.add_template_set(project)
        self.save_project(project, reason="create")
        return project

    def project_path(self, project: dict[str, Any] | str) -> Path:
        if isinstance(project, dict):
            project_id = project["id"]
            name = project["metadata"]["name"]
        else:
            project_id = project
            name = project
        return self.projects_dir / f"{slug(name)}-{project_id}.fractalinterface"

    def find_project_path(self, project_id: str) -> Path:
        matches = list(self.projects_dir.glob(f"*-{project_id}.fractalinterface"))
        if not matches:
            matches = list(self.projects_dir.glob(f"*{project_id}*.fractalinterface"))
        if not matches:
            raise FileNotFoundError(project_id)
        return matches[0]

    def load_project(self, project_id_or_path: str | Path) -> dict[str, Any]:
        path = Path(project_id_or_path)
        if not path.exists():
            path = self.find_project_path(str(project_id_or_path))
        project = read_json(path)
        migrated = self.migrate_project(project)
        migrated.setdefault("undoStack", [])
        migrated.setdefault("redoStack", [])
        validation = self.validate_project(migrated)
        if not validation["valid"]:
            raise ValueError("Invalid interface project: " + "; ".join(validation["errors"]))
        return migrated

    def save_project(self, project: dict[str, Any], *, reason: str = "manual") -> Path:
        self.validate_project_or_raise(project)
        project["metadata"]["updatedAt"] = utc_now()
        self.snapshot_project(project, reason=f"before-{reason}")
        path = self.project_path(project)
        write_json_atomic(path, self.project_storage_copy(project))
        self.trim_snapshots(project["id"])
        return path

    def snapshot_project(self, project: dict[str, Any], *, reason: str) -> Path:
        target = self.snapshots_dir / project["id"] / f"{int(time.time() * 1000)}-{slug(reason)}.json"
        project.setdefault("versions", []).append({"at": utc_now(), "reason": reason, "path": str(target)})
        write_json_atomic(target, self.project_storage_copy(project))
        return target

    def restore_snapshot(self, snapshot_path: str | Path) -> dict[str, Any]:
        snapshot = read_json(Path(snapshot_path))
        snapshot["undoStack"] = []
        snapshot["redoStack"] = []
        self.save_project(snapshot, reason="restore-snapshot")
        return snapshot

    def project_storage_copy(self, project: dict[str, Any]) -> dict[str, Any]:
        stored = copy.deepcopy(project)
        stored["undoStack"] = []
        stored["redoStack"] = []
        return stored

    def trim_snapshots(self, project_id: str) -> None:
        folder = self.snapshots_dir / project_id
        if not folder.exists():
            return
        snapshots = sorted(folder.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old in snapshots[self.config.max_snapshots :]:
            old.unlink(missing_ok=True)

    def migrate_project(self, project: dict[str, Any]) -> dict[str, Any]:
        if project.get("schemaVersion") == INTERFACE_SCHEMA_VERSION:
            return project
        backup = self.snapshots_dir / "migrations" / f"{int(time.time())}-{project.get('id', 'unknown')}.json"
        write_json_atomic(backup, project)
        project["schemaVersion"] = INTERFACE_SCHEMA_VERSION
        project.setdefault("history", []).append({"at": utc_now(), "action": "migration", "backup": str(backup)})
        return project

    def common_element(self, element_type: str, name: str, **overrides: Any) -> dict[str, Any]:
        if element_type not in ELEMENT_TYPES:
            raise ValueError(f"Unsupported element type: {element_type}")
        now = utc_now()
        element = {
            "id": overrides.pop("id", new_id(element_type.upper())),
            "name": name,
            "type": element_type,
            "description": overrides.pop("description", ""),
            "tags": overrides.pop("tags", []),
            "parent": overrides.pop("parent", ""),
            "children": overrides.pop("children", []),
            "displayOrder": overrides.pop("displayOrder", 0),
            "visible": overrides.pop("visible", True),
            "enabled": overrides.pop("enabled", True),
            "locked": overrides.pop("locked", False),
            "permissions": overrides.pop("permissions", []),
            "dataSource": overrides.pop("dataSource", ""),
            "events": overrides.pop("events", {}),
            "commands": overrides.pop("commands", []),
            "scripts": overrides.pop("scripts", []),
            "style": overrides.pop("style", self.default_style()),
            "theme": overrides.pop("theme", "Fractal"),
            "state": overrides.pop("state", "Ready"),
            "customProperties": overrides.pop("customProperties", {}),
            "metadata": overrides.pop("metadata", {}),
            "createdAt": now,
            "updatedAt": now,
            "author": overrides.pop("author", "the owner"),
            "schemaVersion": INTERFACE_SCHEMA_VERSION,
            "provenance": overrides.pop("provenance", "fractal-creation-studio"),
            "history": [{"at": now, "action": "created", "name": name}],
        }
        element.update(overrides)
        return element

    def create_window(self, project: dict[str, Any], name: str, **properties: Any) -> dict[str, Any]:
        self.push_undo(project, "create-window")
        window = self.common_element(
            "Window",
            name,
            properties={
                "x": properties.get("x", 120),
                "y": properties.get("y", 120),
                "width": properties.get("width", 520),
                "height": properties.get("height", 360),
                "minWidth": properties.get("minWidth", 220),
                "minHeight": properties.get("minHeight", 160),
                "maxWidth": properties.get("maxWidth", 2400),
                "maxHeight": properties.get("maxHeight", 1600),
                "ratio": properties.get("ratio", ""),
                "alignment": properties.get("alignment", "free"),
                "margins": properties.get("margins", [0, 0, 0, 0]),
                "padding": properties.get("padding", [12, 12, 12, 12]),
                "titleBar": properties.get("titleBar", True),
                "systemButtons": properties.get("systemButtons", ["close", "pin", "minimize"]),
                "icon": properties.get("icon", "window"),
                "title": name,
                "subtitle": properties.get("subtitle", ""),
                "initialState": properties.get("initialState", "normal"),
                "initialVisible": properties.get("initialVisible", True),
                "resizable": properties.get("resizable", True),
                "movable": properties.get("movable", True),
                "dockable": properties.get("dockable", True),
                "modal": properties.get("modal", False),
                "alwaysVisible": properties.get("alwaysVisible", False),
                "workspaceTarget": properties.get("workspaceTarget", "HUD"),
                "screenTarget": properties.get("screenTarget", "primary"),
                "layerTarget": properties.get("layerTarget", "HUD"),
                "hudDepth": properties.get("hudDepth", 0),
                "anchoring": properties.get("anchoring", self.default_anchor()),
                "responsiveVariants": properties.get("responsiveVariants", self.default_responsive_variants()),
            },
        )
        project["windows"][window["id"]] = window
        self.record_history(project, "create_window", window["id"])
        return window

    def create_widget(self, project: dict[str, Any], name: str, kind: str = "Label", *, parent_window_id: str = "", **properties: Any) -> dict[str, Any]:
        self.push_undo(project, "create-widget")
        widget = self.common_element(
            "Widget",
            name,
            parent=parent_window_id,
            properties={
                "kind": kind,
                "inputs": properties.get("inputs", []),
                "outputs": properties.get("outputs", []),
                "properties": properties.get("properties", {}),
                "events": properties.get("events", ["OnClick", "OnHover"]),
                "commands": properties.get("commands", []),
                "permissions": properties.get("permissions", []),
                "states": VISUAL_STATES,
                "errors": [],
                "dependencies": properties.get("dependencies", []),
                "renderCost": properties.get("renderCost", "low"),
                "compatibility": properties.get("compatibility", {"2d": True, "3d": True, "mobile": True}),
            },
        )
        project["widgets"][widget["id"]] = widget
        if parent_window_id and parent_window_id in project["windows"]:
            project["windows"][parent_window_id]["children"].append(widget["id"])
        self.record_history(project, "create_widget", widget["id"])
        return widget

    def create_module(self, project: dict[str, Any], name: str, **properties: Any) -> dict[str, Any]:
        self.push_undo(project, "create-module")
        module = self.common_element(
            "Module",
            name,
            manifest={
                "id": properties.get("moduleId", slug(name)),
                "name": name,
                "version": properties.get("version", "0.1.0"),
                "description": properties.get("description", ""),
                "dependencies": properties.get("dependencies", []),
                "permissions": properties.get("permissions", ["interface.read"]),
                "components": properties.get("components", []),
                "windows": properties.get("windows", []),
                "widgets": properties.get("widgets", []),
                "scripts": properties.get("scripts", []),
                "functions": properties.get("functions", []),
                "eventsIn": properties.get("eventsIn", []),
                "eventsOut": properties.get("eventsOut", []),
                "compatibility": properties.get("compatibility", ["HUD", "Spatial", "Mobile"]),
                "migration": properties.get("migration", []),
            },
        )
        project["modules"][module["id"]] = module
        self.record_history(project, "create_module", module["id"])
        return module

    def add_theme(self, project: dict[str, Any], name: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.push_undo(project, "theme")
        theme_id = slug(name)
        theme = {
            "id": theme_id,
            "name": name,
            "palette": variables.get("palette", {}),
            "typography": variables.get("typography", {}),
            "shapes": variables.get("shapes", {}),
            "radii": variables.get("radii", {}),
            "borders": variables.get("borders", {}),
            "shadows": variables.get("shadows", {}),
            "spacing": variables.get("spacing", {}),
            "sizes": variables.get("sizes", {}),
            "animations": variables.get("animations", {}),
            "componentStyles": variables.get("componentStyles", {}),
            "hudStyles": variables.get("hudStyles", {}),
            "spatialStyles": variables.get("spatialStyles", {}),
            "mobileStyles": variables.get("mobileStyles", {}),
            "accessibility": variables.get("accessibility", {}),
            "variables": variables.get("variables", self.default_theme_variables()),
            "createdAt": utc_now(),
        }
        project["themes"][theme_id] = theme
        return theme

    def apply_style(self, project: dict[str, Any], element_id: str, style_patch: dict[str, Any], *, state: str = "Normal") -> dict[str, Any]:
        self.push_undo(project, "apply-style")
        element = self.find_element(project, element_id)
        if state not in VISUAL_STATES:
            raise ValueError(f"Invalid visual state: {state}")
        element["style"].setdefault("states", {}).setdefault(state, {}).update(style_patch)
        element["updatedAt"] = utc_now()
        element["history"].append({"at": utc_now(), "action": "style", "state": state, "patch": style_patch})
        return element

    def create_data_source(self, project: dict[str, Any], name: str, source_type: str, config: dict[str, Any]) -> dict[str, Any]:
        self.push_undo(project, "data-source")
        source = self.common_element("DataSource", name, sourceType=source_type, config=config, permissions=config.get("permissions", []))
        project["dataSources"][source["id"]] = source
        return source

    def bind_widget_data(self, project: dict[str, Any], widget_id: str, data_source_id: str, mapping: dict[str, str]) -> dict[str, Any]:
        self.push_undo(project, "data-binding")
        widget = self.find_element(project, widget_id)
        if data_source_id not in project["dataSources"]:
            raise ValueError(f"Missing data source: {data_source_id}")
        widget["dataSource"] = data_source_id
        widget["customProperties"]["dataBinding"] = mapping
        return widget

    def register_function(self, project: dict[str, Any], address: str, *, description: str, parameters: dict[str, Any] | None = None, permissions: list[str] | None = None, side_effects: list[str] | None = None) -> dict[str, Any]:
        self.push_undo(project, "register-function")
        if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,4}$", address):
            raise ValueError(f"Invalid function address: {address}")
        binding = self.common_element(
            "FunctionBinding",
            address,
            address=address,
            description=description,
            parameters=parameters or {},
            result={},
            permissions=permissions or ["function.call"],
            sideEffects=side_effects or [],
            availability="available",
        )
        project["functionBindings"][binding["id"]] = binding
        return binding

    def bind_event_to_function(self, project: dict[str, Any], target_id: str, event_name: str, function_address: str, parameters: dict[str, Any]) -> dict[str, Any]:
        self.push_undo(project, "event-binding")
        target = self.find_element(project, target_id)
        function = self.find_function(project, function_address)
        binding = self.common_element(
            "EventBinding",
            f"{event_name} -> {function_address}",
            parent=target_id,
            eventName=event_name,
            functionAddress=function_address,
            functionId=function["id"],
            parameters=parameters,
            parameterSources={key: self.parameter_source(value) for key, value in parameters.items()},
        )
        project["eventBindings"][binding["id"]] = binding
        target.setdefault("events", {}).setdefault(event_name, []).append(binding["id"])
        return binding

    def create_visual_script(self, project: dict[str, Any], name: str, blocks: list[dict[str, Any]], connections: list[dict[str, Any]]) -> dict[str, Any]:
        self.push_undo(project, "visual-script")
        script = self.common_element(
            "ScriptGraph",
            name,
            blocks=blocks,
            connections=connections,
            variables=[],
            functions=[],
            debug={"breakpoints": [], "lastTrace": []},
        )
        validation = self.validate_visual_script(script)
        script["state"] = "Ready" if validation["valid"] else "Error"
        script["validation"] = validation
        project["visualScripts"][script["id"]] = script
        return script

    def execute_visual_script(self, project: dict[str, Any], script_id: str, event: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        script = project["visualScripts"][script_id]
        validation = self.validate_visual_script(script)
        if not validation["valid"]:
            return {"success": False, "error": "invalid-script", "details": validation}
        trace: list[str] = []
        blocks = {block["id"]: block for block in script["blocks"]}
        starters = [block for block in script["blocks"] if block.get("type") == "EventBlock" and block.get("event") == event]
        for block in starters:
            current = block["id"]
            visited: set[str] = set()
            while current and current not in visited:
                visited.add(current)
                trace.append(current)
                next_edges = [edge for edge in script["connections"] if edge.get("from") == current and edge.get("kind") == "flow"]
                current = next_edges[0]["to"] if next_edges else ""
                if current and blocks.get(current, {}).get("type") == "SecurityBlock" and "security.dangerous" in blocks[current].get("permissions", []):
                    return {"success": False, "error": "permission-required", "trace": trace}
        script["debug"]["lastTrace"] = trace
        return {"success": True, "event": event, "trace": trace, "context": context or {}}

    def create_text_script(self, project: dict[str, Any], name: str, language: str, source: str, permissions: list[str] | None = None) -> dict[str, Any]:
        self.push_undo(project, "text-script")
        script = self.common_element("ScriptGraph", name, language=language, source=source, permissions=permissions or ["script.read"], sandbox={"enabled": True, "network": False, "filesystem": "project-only"})
        project["textScripts"][script["id"]] = script
        return script

    def create_object3d(self, project: dict[str, Any], name: str, shape: str = "cube", **properties: Any) -> dict[str, Any]:
        self.push_undo(project, "object3d")
        obj = self.common_element(
            "Object3D",
            name,
            properties={
                "shape": shape,
                "transform": properties.get("transform", self.default_transform()),
                "pivot": properties.get("pivot", {"x": 0, "y": 0, "z": 0}),
                "material": properties.get("material", self.material_preset("hud-spatial")),
                "collision": properties.get("collision", {"type": "box", "trigger": False, "layer": "objects", "mask": ["interaction"]}),
                "interactive": properties.get("interactive", False),
                "interaction": properties.get("interaction", {}),
                "bounds": properties.get("bounds", {"size": {"x": 1, "y": 1, "z": 1}, "center": {"x": 0, "y": 0, "z": 0}}),
                "gizmo": self.default_gizmo(),
                "snap": {"enabled": False, "moveStep": 0.25, "angleStep": 15, "tolerance": 0.05},
            },
        )
        project["models3D"][obj["id"]] = obj
        project["scene"].setdefault("objects", []).append(obj["id"])
        return obj

    def import_object3d(self, project: dict[str, Any], file_path: str | Path, *, scale: float = 1.0, up_axis: str = "Y", create_collision: bool = True, create_interaction: bool = False) -> dict[str, Any]:
        source = Path(file_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(str(source))
        ext = source.suffix.lower()
        if ext not in SUPPORTED_3D_EXTENSIONS:
            raise ValueError(f"Unsupported 3D format: {ext}")
        content = source.read_bytes()
        digest = stable_hash(content)
        asset_folder = self.assets_dir / digest[:2] / digest
        asset_folder.mkdir(parents=True, exist_ok=True)
        copied = asset_folder / source.name
        if not copied.exists():
            copied.write_bytes(content)
        existing = [asset for asset in project["assets"].values() if asset.get("hash") == digest]
        asset = {
            "id": existing[0]["id"] if existing else new_id("ASSET"),
            "name": source.name,
            "type": "Model3D",
            "format": ext[1:],
            "sourcePath": str(source),
            "storedPath": str(copied),
            "sizeBytes": len(content),
            "hash": digest,
            "meshCount": 1,
            "materials": [],
            "textures": [],
            "animations": [],
            "bounds": {"size": {"x": scale, "y": scale, "z": scale}, "center": {"x": 0, "y": 0, "z": 0}},
            "options": {"scale": scale, "upAxis": up_axis, "collision": create_collision, "interaction": create_interaction},
            "provenance": {"importedAt": utc_now(), "wizard": ["file", "analysis", "configuration", "preview", "import"]},
        }
        project["assets"][asset["id"]] = asset
        obj = self.create_object3d(project, source.stem, "imported", properties={"assetId": asset["id"]})
        obj["properties"]["assetId"] = asset["id"]
        obj["properties"]["collision"] = {"type": "box", "trigger": False, "auto": True} if create_collision else {"type": "none"}
        if create_interaction:
            self.create_zone_around_object(project, obj["id"], margin=0.25)
        return {"asset": asset, "object": obj}

    def transform_object3d(self, project: dict[str, Any], object_id: str, *, move: dict[str, float] | None = None, rotate: dict[str, float] | None = None, scale: dict[str, float] | None = None, snap: bool = False) -> dict[str, Any]:
        self.push_undo(project, "transform-object3d")
        obj = project["models3D"][object_id]
        transform = obj["properties"]["transform"]
        if move:
            for axis in ["x", "y", "z"]:
                value = transform["position"].get(axis, 0) + float(move.get(axis, 0))
                step = obj["properties"]["snap"]["moveStep"] if snap else 0
                transform["position"][axis] = round(value / step) * step if step else value
        if rotate:
            for axis in ["pitch", "yaw", "roll"]:
                value = transform["rotation"].get(axis, 0) + float(rotate.get(axis, 0))
                step = obj["properties"]["snap"]["angleStep"] if snap else 0
                transform["rotation"][axis] = round(value / step) * step if step else value
        if scale:
            for axis in ["x", "y", "z"]:
                transform["scale"][axis] = max(0.001, transform["scale"].get(axis, 1) * float(scale.get(axis, 1)))
        return obj

    def create_interaction_zone(self, project: dict[str, Any], name: str, shape: str = "box", **properties: Any) -> dict[str, Any]:
        self.push_undo(project, "interaction-zone")
        zone = self.common_element(
            "InteractionZone",
            name,
            properties={
                "shape": shape,
                "position": properties.get("position", {"x": 0, "y": 0, "z": 0}),
                "rotation": properties.get("rotation", {"pitch": 0, "yaw": 0, "roll": 0}),
                "size": properties.get("size", {"x": 1, "y": 1, "z": 1}),
                "parent": properties.get("parent", ""),
                "targetObjectId": properties.get("targetObjectId", properties.get("parent", "")),
                "visibleInEditor": properties.get("visibleInEditor", True),
                "visibleInRuntime": properties.get("visibleInRuntime", False),
                "debugColor": properties.get("debugColor", "#FFD154"),
                "priority": properties.get("priority", 0),
                "distance": properties.get("distance", 2.5),
                "layer": properties.get("layer", "zones"),
                "filters": properties.get("filters", []),
                "permissions": properties.get("permissions", ["interaction.use"]),
                "activation": properties.get("activation", "enabled"),
                "cooldownMs": properties.get("cooldownMs", 0),
                "events": properties.get("events", ["OnEnter", "OnExit", "OnInteract", "OnClick"]),
                "function": properties.get("function", ""),
                "feedback": properties.get("feedback", {"text": "Interact", "color": "#7BDFF2"}),
            },
        )
        project["interactionZones"][zone["id"]] = zone
        project["scene"].setdefault("interactionZones", []).append(zone["id"])
        return zone

    def create_zone_around_object(self, project: dict[str, Any], object_id: str, *, margin: float = 0.2, shape: str = "box") -> dict[str, Any]:
        obj = project["models3D"][object_id]
        bounds = obj["properties"].get("bounds", {"size": {"x": 1, "y": 1, "z": 1}, "center": {"x": 0, "y": 0, "z": 0}})
        size = bounds["size"]
        zone = self.create_interaction_zone(
            project,
            f"{obj['name']} Interaction Zone",
            shape,
            parent=object_id,
            targetObjectId=object_id,
            size={axis: float(size.get(axis, 1)) + margin * 2 for axis in ["x", "y", "z"]},
            position=bounds.get("center", {"x": 0, "y": 0, "z": 0}),
        )
        obj["properties"]["interactive"] = True
        obj["properties"].setdefault("interaction", {}).setdefault("zones", []).append(zone["id"])
        return zone

    def preview_project(self, project: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate_project(project)
        render_cost = sum(1 for _ in project["windows"]) + sum(1 for _ in project["widgets"]) + len(project["models3D"]) * 2
        return {
            "valid": validation["valid"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "windows": len(project["windows"]),
            "widgets": len(project["widgets"]),
            "objects3D": len(project["models3D"]),
            "zones": len(project["interactionZones"]),
            "renderCost": "low" if render_cost < 12 else "medium" if render_cost < 40 else "high",
            "mode": project["scene"]["mode"],
        }

    def publish_project(self, project: dict[str, Any], target: str) -> dict[str, Any]:
        if target not in {"hud", "spatial"}:
            raise ValueError("target must be hud or spatial")
        validation = self.validate_project(project)
        if not validation["valid"]:
            return {"success": False, "target": target, "errors": validation["errors"]}
        target_dir = self.root / "published" / target
        payload = {
            "schemaVersion": INTERFACE_SCHEMA_VERSION,
            "projectId": project["id"],
            "target": target,
            "publishedAt": utc_now(),
            "windows": list(project["windows"].values()),
            "widgets": list(project["widgets"].values()),
            "modules": list(project["modules"].values()),
            "objects3D": list(project["models3D"].values()) if target == "spatial" else [],
            "interactionZones": list(project["interactionZones"].values()) if target == "spatial" else [],
            "functionBindings": list(project["functionBindings"].values()),
        }
        output = target_dir / f"{project['id']}.json"
        write_json_atomic(output, payload)
        project["published"][target].append({"at": utc_now(), "path": str(output)})
        return {"success": True, "target": target, "path": str(output)}

    def copy_element(self, project: dict[str, Any], element_id: str) -> dict[str, Any]:
        element = copy.deepcopy(self.find_element(project, element_id))
        project["clipboard"] = {"mode": "copy", "element": element, "copiedAt": utc_now()}
        return project["clipboard"]

    def paste_element(self, project: dict[str, Any], *, as_instance: bool = False) -> dict[str, Any]:
        self.push_undo(project, "paste-element")
        if not project.get("clipboard"):
            raise ValueError("Clipboard is empty")
        element = copy.deepcopy(project["clipboard"]["element"])
        original_id = element["id"]
        if not as_instance:
            element["id"] = new_id(element["type"].upper())
            element["name"] = element["name"] + " Copy"
            element["metadata"]["clonedFrom"] = original_id
        else:
            element["metadata"]["instanceOf"] = original_id
        section = self.section_for_type(element["type"])
        project[section][element["id"]] = element
        return element

    def undo(self, project: dict[str, Any]) -> dict[str, Any]:
        if not project["undoStack"]:
            return project
        project["redoStack"].append(copy.deepcopy(project))
        previous = project["undoStack"].pop()
        previous["redoStack"] = project["redoStack"]
        return previous

    def redo(self, project: dict[str, Any]) -> dict[str, Any]:
        if not project["redoStack"]:
            return project
        project["undoStack"].append(copy.deepcopy(project))
        return project["redoStack"].pop()

    def push_undo(self, project: dict[str, Any], label: str) -> None:
        snapshot = self.project_storage_copy(project)
        snapshot.setdefault("history", []).append({"at": utc_now(), "action": "undo-point", "label": label})
        project.setdefault("undoStack", []).append(snapshot)
        if len(project["undoStack"]) > 60:
            project["undoStack"] = project["undoStack"][-60:]
        project["redoStack"] = []

    def validate_project(self, project: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        if project.get("schemaVersion") != INTERFACE_SCHEMA_VERSION:
            errors.append("schemaVersion mismatch")
        seen: set[str] = set()
        for section in ["windows", "widgets", "modules", "models3D", "interactionZones", "functionBindings", "eventBindings"]:
            for element_id, element in project.get(section, {}).items():
                if element_id in seen:
                    errors.append(f"duplicate id {element_id}")
                seen.add(element_id)
                if not element.get("name"):
                    errors.append(f"{element_id} missing name")
                for permission in element.get("permissions", []):
                    if permission in {"process.control", "security.process.stop"} and element.get("state") != "AwaitingApproval":
                        warnings.append(f"{element_id} uses dangerous permission {permission}")
        for binding in project.get("eventBindings", {}).values():
            if not self.find_function(project, binding.get("functionAddress", ""), required=False):
                errors.append(f"missing function {binding.get('functionAddress')} for binding {binding['id']}")
        for script in project.get("visualScripts", {}).values():
            result = self.validate_visual_script(script)
            errors.extend(f"{script['id']}: {error}" for error in result["errors"])
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def validate_project_or_raise(self, project: dict[str, Any]) -> None:
        result = self.validate_project(project)
        if not result["valid"]:
            raise ValueError("; ".join(result["errors"]))

    def validate_visual_script(self, script: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        blocks = {block["id"]: block for block in script.get("blocks", [])}
        for connection in script.get("connections", []):
            source = blocks.get(connection.get("from"))
            target = blocks.get(connection.get("to"))
            if source is None or target is None:
                errors.append("connection references missing block")
                continue
            out_type = connection.get("outType", "flow")
            in_type = connection.get("inType", "flow")
            if out_type != in_type and not connection.get("conversion"):
                errors.append(f"incompatible connection {source['id']}->{target['id']}: {out_type} to {in_type}")
        graph = {block_id: [edge["to"] for edge in script.get("connections", []) if edge.get("from") == block_id and edge.get("kind") == "flow"] for block_id in blocks}
        if self.has_cycle(graph):
            warnings.append("flow contains a cycle; loop blocks must declare cancellation")
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def has_cycle(self, graph: dict[str, list[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for child in graph.get(node, []):
                if visit(child):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def find_element(self, project: dict[str, Any], element_id: str) -> dict[str, Any]:
        for section in ["windows", "widgets", "modules", "components", "models3D", "interactionZones", "visualScripts", "textScripts", "dataSources", "functionBindings", "eventBindings"]:
            if element_id in project.get(section, {}):
                return project[section][element_id]
        raise KeyError(element_id)

    def find_function(self, project: dict[str, Any], address: str, *, required: bool = True) -> dict[str, Any] | None:
        for binding in project.get("functionBindings", {}).values():
            if binding.get("address") == address:
                return binding
        defaults = self.default_function_registry()
        if address in defaults:
            return defaults[address]
        if required:
            raise KeyError(address)
        return None

    def section_for_type(self, element_type: str) -> str:
        return {
            "Window": "windows",
            "Widget": "widgets",
            "Module": "modules",
            "Object3D": "models3D",
            "InteractionZone": "interactionZones",
            "ScriptGraph": "visualScripts",
            "DataSource": "dataSources",
            "FunctionBinding": "functionBindings",
            "EventBinding": "eventBindings",
        }.get(element_type, "components")

    def record_history(self, project: dict[str, Any], action: str, target: str) -> None:
        project.setdefault("history", []).append({"at": utc_now(), "action": action, "target": target})

    def parameter_source(self, value: Any) -> str:
        if isinstance(value, str) and value.startswith("$"):
            return "dynamic"
        return "constant"

    def default_style(self) -> dict[str, Any]:
        return {
            "dimensions": {"width": "auto", "height": "auto", "min": None, "max": None, "ratio": None, "margin": 0, "padding": 8, "spacing": 8, "alignment": "start", "position": "relative"},
            "corners": {"radius": 8, "topLeft": 8, "topRight": 8, "bottomLeft": 8, "bottomRight": 8, "shape": "rectangle", "mask": None},
            "border": {"width": 1, "color": "var(--border-color)", "opacity": 1, "style": "solid", "position": "center"},
            "background": {"color": "var(--surface-color)", "opacity": 1, "gradient": None, "image": None, "blur": 0, "glass": False, "noise": 0},
            "shadow": {"enabled": True, "color": "#000000", "opacity": 0.25, "x": 0, "y": 8, "spread": 0, "blur": 18, "inner": False},
            "text": {"font": "Segoe UI", "size": 12, "weight": "normal", "style": "normal", "color": "var(--text-color)", "align": "left", "lineHeight": 1.2, "letterSpacing": 0, "decoration": "none"},
            "effects": {"blur": 0, "brightness": 1, "contrast": 1, "saturation": 1, "hue": 0, "opacity": 1, "transition": "120ms ease", "animation": None},
            "states": {state: {} for state in VISUAL_STATES},
        }

    def default_theme_variables(self) -> dict[str, Any]:
        return {
            "--primary-color": "#7BDFF2",
            "--secondary-color": "#B2F7EF",
            "--accent-color": "#FFD166",
            "--background-color": "#0C1117",
            "--surface-color": "#111827",
            "--text-color": "#E9EEF4",
            "--error-color": "#FF6B6B",
            "--warning-color": "#FFD166",
            "--success-color": "#7AE582",
            "--border-color": "#334155",
            "--border-radius-small": 4,
            "--border-radius-medium": 8,
            "--border-radius-large": 14,
            "--border-width": 1,
            "--shadow-small": "0 4px 10px rgba(0,0,0,.24)",
            "--shadow-medium": "0 10px 28px rgba(0,0,0,.28)",
            "--shadow-large": "0 20px 48px rgba(0,0,0,.32)",
            "--spacing-small": 4,
            "--spacing-medium": 8,
            "--spacing-large": 16,
        }

    def default_theme(self, name: str) -> dict[str, Any]:
        variables = self.default_theme_variables()
        if name.lower() == "light":
            variables.update({"--background-color": "#F7FAFC", "--surface-color": "#FFFFFF", "--text-color": "#111827"})
        if name.lower() == "high contrast":
            variables.update({"--background-color": "#000000", "--surface-color": "#101010", "--text-color": "#FFFFFF", "--accent-color": "#FFFF00"})
        return {"variables": variables, "palette": {}, "typography": {}, "shapes": {}, "shadows": {}, "spacing": {}, "componentStyles": {}}

    def default_anchor(self) -> dict[str, Any]:
        return {"mode": "free", "target": "", "edge": "center", "offset": {"x": 0, "y": 0, "z": 0}, "magnetic": True, "threshold": 12, "guides": True}

    def default_responsive_variants(self) -> dict[str, Any]:
        return {variant: {"enabled": True, "layout": "auto"} for variant in ["Desktop", "Mobile", "Tablet", "HUD", "SpatialNear", "SpatialFar", "VR", "Compact", "Expanded"]}

    def default_layers(self) -> dict[str, Any]:
        return {name: {"visible": True, "locked": False, "filtered": False} for name in ["HUD", "menus", "notifications", "debug", "world", "objects", "spatialInterfaces", "zones", "collisions", "agents", "security", "selection"]}

    def default_transform(self) -> dict[str, Any]:
        return {"position": {"x": 0, "y": 0, "z": -2}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}, "space": "global"}

    def default_gizmo(self) -> dict[str, Any]:
        return {
            "mode": "move",
            "coordinateSpace": "global",
            "handles": {
                "move": ["arrowX", "arrowY", "arrowZ", "planeXY", "planeXZ", "planeYZ", "free"],
                "rotate": ["ringX", "ringY", "ringZ", "free"],
                "scale": ["handleX", "handleY", "handleZ", "planeXY", "planeXZ", "planeYZ", "uniform"],
                "pivot": ["pivotMove", "pivotCenter", "pivotSurface"],
            },
            "visual": {"size": 1, "distanceScale": True, "thickness": 2, "opacity": 0.9, "colors": {"x": "#FF4D4D", "y": "#4DFF88", "z": "#4DA3FF"}},
        }

    def material_preset(self, name: str) -> dict[str, Any]:
        presets = {
            "plastic": {"color": "#8EA7B8", "roughness": 0.65, "metallic": 0, "opacity": 1},
            "metal": {"color": "#B8C0CC", "roughness": 0.32, "metallic": 1, "opacity": 1},
            "glass": {"color": "#CFFAFE", "roughness": 0.02, "metallic": 0, "opacity": 0.35},
            "wood": {"color": "#7A5230", "roughness": 0.8, "metallic": 0, "opacity": 1},
            "stone": {"color": "#777C85", "roughness": 0.9, "metallic": 0, "opacity": 1},
            "hologram": {"color": "#7BDFF2", "roughness": 0.1, "metallic": 0, "opacity": 0.52, "emission": "#7BDFF2"},
            "hud-spatial": {"color": "#7BDFF2", "roughness": 0.25, "metallic": 0, "opacity": 0.82, "emission": "#1FB6D6"},
            "emission": {"color": "#FFD166", "roughness": 0.15, "metallic": 0, "opacity": 1, "emission": "#FFD166"},
            "invisible-interactive": {"color": "#FFFFFF", "roughness": 0, "metallic": 0, "opacity": 0.05},
        }
        return presets.get(name, presets["plastic"])

    def default_function_registry(self) -> dict[str, dict[str, Any]]:
        def fn(address: str, description: str, permissions: list[str], side_effects: list[str] | None = None) -> dict[str, Any]:
            return {"id": "builtin:" + address, "address": address, "description": description, "permissions": permissions, "sideEffects": side_effects or [], "availability": "available"}

        return {
            "runtime.pause": fn("runtime.pause", "Pause runtime safely.", ["runtime.control"]),
            "runtime.resume": fn("runtime.resume", "Resume runtime.", ["runtime.control"]),
            "hud.window.open": fn("hud.window.open", "Open a HUD window.", ["interface.write"]),
            "hud.widget.show": fn("hud.widget.show", "Show a widget.", ["interface.write"]),
            "spatial.object.hide": fn("spatial.object.hide", "Hide a spatial object.", ["object.write"]),
            "spatial.object.move": fn("spatial.object.move", "Move a spatial object.", ["object.write"]),
            "agent.task.submit": fn("agent.task.submit", "Submit an agent task.", ["agent.task.submit"]),
            "security.process.stop": fn("security.process.stop", "Stop a process after confirmation.", ["process.control"], ["process-stop"]),
            "module.inventory.open": fn("module.inventory.open", "Open inventory module.", ["module.open"]),
            "door.open": fn("door.open", "Open an interactive door.", ["interaction.use"]),
            "door.toggle": fn("door.toggle", "Toggle an interactive door.", ["interaction.use"]),
        }

    def add_template_set(self, project: dict[str, Any]) -> None:
        for name in [
            "fenetre vide",
            "fenetre de parametres",
            "dashboard",
            "console",
            "inspecteur",
            "gestionnaire de fichiers",
            "liste de taches",
            "gestionnaire de plugins",
            "panneau de securite",
            "panneau GPU",
            "panneau spatial",
            "inspecteur objet 3D",
            "editeur zone interaction",
        ]:
            project["templates"][slug(name)] = {"id": slug(name), "name": name, "type": "template", "createdAt": utc_now()}
        for name in ["bouton", "carte", "panneau", "fenetre", "texte", "menu", "notification", "objet interactif", "zone declenchement", "panneau spatial"]:
            project["presets"][slug(name)] = {"id": slug(name), "name": name, "type": "preset", "patch": {}, "createdAt": utc_now()}

    def run_acceptance_scenario(self) -> dict[str, Any]:
        self.initialize()
        project = self.create_project(
            "Alpha Creation Studio Scenario",
            description="Scenario vertical couvrant interfaces, widgets, modules, 3D, scripts, zones et profils outils.",
        )
        theme = self.add_theme(
            project,
            "Alpha Studio",
            {
                **self.default_theme("Alpha Studio"),
                "color.accent": "#7BDFF2",
                "color.warning": "#FBBF24",
                "space.panel": 12,
                "radius.window": 8,
                "font.ui": "Segoe UI",
            },
        )
        window = self.create_window(
            project,
            "Command Deck",
            size={"width": 820, "height": 520},
            position={"x": 96, "y": 84},
            docking={"mode": "floating", "allowPin": True, "pinned": False},
            tabs=["Accueil", "Objets", "Scripts", "Tests"],
        )
        module = self.create_module(
            project,
            "Spatial Object Control",
            status="alpha",
            type="tool",
            entryWindowId=window["id"],
            actions=["open", "focus-object", "edit-zone", "run-preview"],
        )
        widget = self.create_widget(
            project,
            "Object Status",
            "StatusCard",
            parent_window_id=window["id"],
            layout={"row": 0, "column": 0, "width": 320, "height": 120},
            text="Objet actif",
        )
        data_source = self.create_data_source(
            project,
            "Scene State",
            "runtime-state",
            {"path": "scene.activeObject", "refresh": "event", "schema": {"name": "string", "status": "string"}},
        )
        data_binding = self.bind_widget_data(widget_id=widget["id"], project=project, data_source_id=data_source["id"], mapping={"title": "name", "subtitle": "status"})
        styled = self.apply_style(project, window["id"], {"background": "#101820", "border": "#7BDFF2", "radius": 8, "shadow": "soft"})
        function = self.register_function(
            project,
            "module.spatial_object_control.focus",
            description="Focalise l'inspecteur sur l'objet ou la zone selectionnee.",
            parameters={"targetId": "string", "mode": "string"},
            permissions=["object.read", "hud.window.open"],
        )
        event_binding = self.bind_event_to_function(
            project,
            widget["id"],
            "OnInteract",
            function["address"],
            {"targetId": {"source": "context.selectedObject"}, "mode": "inspect"},
        )
        visual_script = self.create_visual_script(
            project,
            "Open Object Inspector",
            blocks=[
                {"id": "event", "type": "EventBlock", "event": "OnInteract", "outputs": ["flow"]},
                {"id": "validate", "type": "Condition", "condition": "targetId != null", "inputs": ["flow"], "outputs": ["flow"]},
                {"id": "focus", "type": "CallFunction", "functionAddress": function["address"], "inputs": ["flow"]},
            ],
            connections=[
                {"from": "event", "to": "validate", "kind": "flow"},
                {"from": "validate", "to": "focus", "kind": "flow"},
            ],
        )
        script_result = self.execute_visual_script(project, visual_script["id"], "OnInteract", {"targetId": "demo-object"})
        text_script = self.create_text_script(
            project,
            "Allowed Patch Proposal",
            "fractalscript",
            "tool.proposePatch(target='selected', mode='preview')",
            permissions=["script.read", "patch.propose"],
        )
        obj = self.create_object3d(
            project,
            "Demo Console Cube",
            "cube",
            interactive=True,
            material=self.material_preset("glass-panel"),
            bounds={"size": {"x": 1.6, "y": 0.9, "z": 0.35}, "center": {"x": 0, "y": 1.2, "z": -2}},
        )
        transform = self.transform_object3d(project, obj["id"], move={"x": 0.23, "y": 1.11, "z": -1.87}, rotate={"y": 13}, scale={"x": 1.15, "y": 1.15, "z": 1.15}, snap=True)
        sample_obj = self.assets_dir / "samples" / "demo-console.obj"
        sample_obj.parent.mkdir(parents=True, exist_ok=True)
        if not sample_obj.exists():
            sample_obj.write_text("o demo_console\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
        imported = self.import_object3d(project, sample_obj, scale=1.25, create_collision=True, create_interaction=True)
        zone = self.create_zone_around_object(project, obj["id"], margin=0.35)
        zone_binding = self.bind_event_to_function(project, zone["id"], "OnEnter", function["address"], {"targetId": obj["id"], "mode": "zone-enter"})
        copied = self.copy_element(project, widget["id"])
        pasted = self.paste_element(project)
        preview = self.preview_project(project)
        hud_publish = self.publish_project(project, "hud")
        spatial_publish = self.publish_project(project, "spatial")
        saved_path = self.save_project(project, reason="acceptance-scenario")

        cloned_tool = self.clone_tool("tool-move", "Move Precision the owner")
        preset = self.create_tool_preset(
            "Millimetre Snap",
            "move",
            cloned_tool["id"],
            {"snap": {"enabled": True, "moveStep": 0.001, "angleStep": 1}, "gizmo": {"size": 0.75}, "performance": {"preview": "fast"}},
        )
        conflict_preset = self.create_tool_preset(
            "Large Snap",
            "move",
            cloned_tool["id"],
            {"snap": {"moveStep": 1.0}},
        )
        profile = self.create_tool_profile(
            "the owner Creation Studio",
            tools=["tool-selection", cloned_tool["id"], "tool-window-designer", "tool-widget-designer", "tool-interaction-zone", "tool-visual-scripting"],
            presets=[preset["id"]],
        )
        toolbar = self.create_toolbar(
            "Studio Core Toolbar",
            [
                {"kind": "tool", "id": "tool-selection"},
                {"kind": "tool", "id": cloned_tool["id"]},
                {"kind": "tool", "id": "tool-widget-designer"},
                {"kind": "command", "id": "preview.run"},
            ],
        )
        shortcut = self.set_shortcut(profile["id"], "preview.run", "Ctrl+Enter", context="creation-studio")
        resolved = self.resolve_tool_parameters(cloned_tool["id"], profile["id"], active_presets=[preset["id"], conflict_preset["id"]], session_values={"target": "selected-object"})
        performance = self.measure_tool_performance(cloned_tool["id"], targets=12, render_ms=5.2, response_ms=14.0)
        exported_profile = self.export_tool_profile(profile["id"])
        imported_profile = self.import_tool_profile(exported_profile["path"], strategy="copy")
        comparison = self.compare_profiles("profile-standard", profile["id"])

        return {
            "project": {"id": project["id"], "path": str(saved_path), "theme": theme["id"], "validation": self.validate_project(project)},
            "created": {
                "window": window["id"],
                "module": module["id"],
                "widget": widget["id"],
                "dataSource": data_source["id"],
                "dataBinding": data_binding["id"],
                "style": styled["id"],
                "function": function["address"],
                "eventBinding": event_binding["id"],
                "visualScript": visual_script["id"],
                "textScript": text_script["id"],
                "object3D": obj["id"],
                "importedObject3D": imported["object"]["id"],
                "interactionZone": zone["id"],
                "zoneBinding": zone_binding["id"],
                "clipboardCopy": copied["element"]["id"],
                "clipboardPaste": pasted["id"],
            },
            "runtime": {"script": script_result, "transform": transform, "preview": preview, "publish": {"hud": hud_publish, "spatial": spatial_publish}},
            "tools": {
                "clone": cloned_tool["id"],
                "preset": preset["id"],
                "conflictPreset": conflict_preset["id"],
                "profile": profile["id"],
                "toolbar": toolbar["id"],
                "shortcut": shortcut,
                "resolved": resolved,
                "performance": performance,
                "export": exported_profile,
                "import": imported_profile,
                "comparison": comparison,
            },
        }

    def default_tool_runtime(self) -> dict[str, Any]:
        return {
            "schemaVersion": TOOL_PROFILE_SCHEMA_VERSION,
            "tools": {tool["id"]: tool for tool in self.default_tools()},
            "presets": {preset["id"]: preset for preset in self.default_tool_presets()},
            "profiles": {profile["id"]: profile for profile in self.default_tool_profiles()},
            "toolbars": {},
            "shortcuts": {},
            "radialMenus": {},
            "favorites": [],
            "usage": [],
            "snapshots": [],
            "recoveryProfileId": "profile-minimal",
        }

    def load_tool_runtime(self) -> dict[str, Any]:
        self.initialize()
        return read_json(self.tools_path)

    def save_tool_runtime(self, state: dict[str, Any]) -> None:
        write_json_atomic(self.tools_path, state)

    def tool_definition(self, name: str, category: str, tool_type: str, **overrides: Any) -> dict[str, Any]:
        now = utc_now()
        tool_id = overrides.pop("id", "tool-" + slug(name))
        return {
            "id": tool_id,
            "name": name,
            "shortName": overrides.pop("shortName", name[:4].upper()),
            "description": overrides.pop("description", ""),
            "category": category,
            "type": tool_type,
            "icon": overrides.pop("icon", tool_type),
            "color": overrides.pop("color", "#7BDFF2"),
            "version": overrides.pop("version", "1.0.0"),
            "author": overrides.pop("author", "system"),
            "source": overrides.pop("source", "system"),
            "state": overrides.pop("state", "enabled"),
            "tags": overrides.pop("tags", [tool_type]),
            "platforms": overrides.pop("platforms", ["desktop", "mobile", "hud"]),
            "spaces": overrides.pop("spaces", ["2d", "3d", "hud", "spatial"]),
            "compatibleElementTypes": overrides.pop("compatibleElementTypes", ["Widget", "Window", "Object3D", "InteractionZone"]),
            "actions": overrides.pop("actions", ["activate", "configure", "preview"]),
            "properties": overrides.pop("properties", {}),
            "parameters": overrides.pop("parameters", self.default_tool_parameters(tool_type)),
            "defaults": overrides.pop("defaults", {}),
            "shortcuts": overrides.pop("shortcuts", []),
            "gestures": overrides.pop("gestures", []),
            "permissions": overrides.pop("permissions", ["interface.read"]),
            "limits": overrides.pop("limits", {"maxTargets": 200, "timeoutMs": 5000}),
            "modes": overrides.pop("modes", ["default"]),
            "events": overrides.pop("events", ["OnActivate", "OnChange", "OnComplete"]),
            "commands": overrides.pop("commands", []),
            "scripts": overrides.pop("scripts", []),
            "configurationInterface": overrides.pop("configurationInterface", {"display": "compact", "controls": []}),
            "optionsBar": overrides.pop("optionsBar", []),
            "preview": overrides.pop("preview", {"enabled": True}),
            "persistentData": overrides.pop("persistentData", {}),
            "history": [{"at": now, "action": "created"}],
            "performance": overrides.pop("performance", {"activationMs": 0, "renderMs": 0, "cost": "low"}),
            "compatibility": overrides.pop("compatibility", {"minRuntime": "0.1.0", "maxTested": "0.1.0"}),
            "dependencies": overrides.pop("dependencies", []),
            "migration": overrides.pop("migration", []),
            "documentation": overrides.pop("documentation", ""),
        }

    def create_tool(self, name: str, category: str, tool_type: str, **overrides: Any) -> dict[str, Any]:
        state = self.load_tool_runtime()
        tool = self.tool_definition(name, category, tool_type, source="user", **overrides)
        state["tools"][tool["id"]] = tool
        self.save_tool_runtime(state)
        return tool

    def clone_tool(self, tool_id: str, new_name: str) -> dict[str, Any]:
        state = self.load_tool_runtime()
        tool = copy.deepcopy(state["tools"][tool_id])
        tool["id"] = "tool-" + slug(new_name)
        tool["name"] = new_name
        tool["source"] = "user-clone"
        tool["history"].append({"at": utc_now(), "action": "cloned", "from": tool_id})
        state["tools"][tool["id"]] = tool
        self.save_tool_runtime(state)
        return tool

    def create_tool_preset(self, name: str, category: str, tool_id: str, patch: dict[str, Any], *, scope: str = "tool") -> dict[str, Any]:
        state = self.load_tool_runtime()
        preset = {
            "id": "preset-" + slug(name),
            "name": name,
            "description": "",
            "category": category,
            "toolId": tool_id,
            "patch": patch,
            "scope": scope,
            "compatibility": ["desktop", "hud", "spatial", "mobile"],
            "tags": [category],
            "version": "1.0.0",
            "createdAt": utc_now(),
        }
        state["presets"][preset["id"]] = preset
        self.save_tool_runtime(state)
        return preset

    def stack_presets(self, preset_ids: list[str]) -> dict[str, Any]:
        state = self.load_tool_runtime()
        merged: dict[str, Any] = {}
        conflicts: list[dict[str, Any]] = []
        provenance: dict[str, str] = {}
        for preset_id in preset_ids:
            preset = state["presets"][preset_id]
            for key, value in self.flatten(preset.get("patch", {})).items():
                if key in merged and merged[key] != value:
                    conflicts.append({"path": key, "previous": merged[key], "new": value, "winner": preset_id})
                merged[key] = value
                provenance[key] = preset_id
        return {"values": merged, "conflicts": conflicts, "provenance": provenance}

    def create_tool_profile(self, name: str, *, base_profile_id: str = "profile-standard", tools: list[str] | None = None, presets: list[str] | None = None) -> dict[str, Any]:
        state = self.load_tool_runtime()
        base = copy.deepcopy(state["profiles"].get(base_profile_id, {}))
        profile = {
            "id": "profile-" + slug(name),
            "name": name,
            "baseProfileId": base_profile_id,
            "metadata": {"createdAt": utc_now(), "author": "the owner", "version": "1.0.0"},
            "enabledTools": tools or base.get("enabledTools", list(state["tools"].keys())),
            "hiddenTools": [],
            "parameters": copy.deepcopy(base.get("parameters", {})),
            "presets": presets or base.get("presets", []),
            "shortcuts": copy.deepcopy(base.get("shortcuts", {})),
            "gestures": copy.deepcopy(base.get("gestures", {})),
            "toolbars": copy.deepcopy(base.get("toolbars", [])),
            "menus": copy.deepcopy(base.get("menus", [])),
            "themes": copy.deepcopy(base.get("themes", [])),
            "gizmos": copy.deepcopy(base.get("gizmos", {})),
            "assistants": copy.deepcopy(base.get("assistants", [])),
            "performanceProfiles": copy.deepcopy(base.get("performanceProfiles", ["Balanced"])),
            "contextRules": copy.deepcopy(base.get("contextRules", [])),
            "locked": False,
        }
        state["profiles"][profile["id"]] = profile
        self.save_tool_runtime(state)
        return profile

    def resolve_tool_parameters(self, tool_id: str, profile_id: str, *, active_presets: list[str] | None = None, session_values: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.load_tool_runtime()
        tool = state["tools"][tool_id]
        profile = state["profiles"][profile_id]
        values = copy.deepcopy(tool.get("defaults", {}))
        provenance = {key: "tool-default" for key in values}
        for key, value in profile.get("parameters", {}).get(tool_id, {}).items():
            values[key] = value
            provenance[key] = "profile"
        stacked = self.stack_presets(active_presets or profile.get("presets", []))
        for key, value in stacked["values"].items():
            values[key] = value
            provenance[key] = stacked["provenance"][key]
        for key, value in (session_values or {}).items():
            values[key] = value
            provenance[key] = "session"
        return {"values": values, "provenance": provenance, "conflicts": stacked["conflicts"]}

    def create_toolbar(self, name: str, items: list[dict[str, Any]], *, toolbar_type: str = "hud") -> dict[str, Any]:
        state = self.load_tool_runtime()
        toolbar = {"id": "toolbar-" + slug(name), "name": name, "type": toolbar_type, "orientation": "horizontal", "items": items, "createdAt": utc_now()}
        state["toolbars"][toolbar["id"]] = toolbar
        self.save_tool_runtime(state)
        return toolbar

    def set_shortcut(self, profile_id: str, action_id: str, shortcut: str, *, context: str = "global") -> dict[str, Any]:
        state = self.load_tool_runtime()
        profile = state["profiles"][profile_id]
        conflicts = []
        for action, spec in profile.setdefault("shortcuts", {}).items():
            if spec.get("shortcut") == shortcut and spec.get("context", "global") == context and action != action_id:
                conflicts.append({"action": action, "shortcut": shortcut, "context": context})
        if conflicts:
            return {"success": False, "conflicts": conflicts}
        profile["shortcuts"][action_id] = {"shortcut": shortcut, "context": context, "priority": 1}
        self.save_tool_runtime(state)
        return {"success": True, "action": action_id, "shortcut": shortcut}

    def measure_tool_performance(self, tool_id: str, *, targets: int = 1, render_ms: float = 0, response_ms: float = 0) -> dict[str, Any]:
        state = self.load_tool_runtime()
        tool = state["tools"][tool_id]
        cost = "low" if render_ms < 8 and response_ms < 20 and targets < 100 else "medium" if render_ms < 20 and targets < 1000 else "high"
        sample = {"at": utc_now(), "toolId": tool_id, "targets": targets, "renderMs": render_ms, "responseMs": response_ms, "cost": cost}
        state.setdefault("usage", []).append(sample)
        tool["performance"] = sample
        self.save_tool_runtime(state)
        recommendation = "ok" if cost == "low" else "reduce-preview-refresh" if cost == "medium" else "simplify-gizmo-and-collision"
        return {"sample": sample, "recommendation": recommendation}

    def export_tool_profile(self, profile_id: str, target: str | Path | None = None, *, selective: dict[str, list[str]] | None = None) -> dict[str, Any]:
        state = self.load_tool_runtime()
        if profile_id not in state["profiles"]:
            raise KeyError(profile_id)
        self.snapshot_tool_runtime("before-export")
        target_path = Path(target).expanduser().resolve() if target else self.exports_dir / f"{profile_id}.fractaltoolprofile"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        included_profiles = selective.get("profiles", [profile_id]) if selective else [profile_id]
        included_tools = selective.get("tools", state["profiles"][profile_id].get("enabledTools", [])) if selective else state["profiles"][profile_id].get("enabledTools", [])
        included_presets = selective.get("presets", state["profiles"][profile_id].get("presets", [])) if selective else state["profiles"][profile_id].get("presets", [])
        manifest = {
            "schemaVersion": TOOL_PROFILE_SCHEMA_VERSION,
            "profileId": profile_id,
            "createdAt": utc_now(),
            "included": {"profiles": included_profiles, "tools": included_tools, "presets": included_presets},
            "permissions": sorted({permission for tool_id in included_tools for permission in state["tools"].get(tool_id, {}).get("permissions", [])}),
        }
        with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for item_id in included_profiles:
                archive.writestr(f"profiles/{item_id}.json", json.dumps(state["profiles"][item_id], indent=2))
            for item_id in included_tools:
                if item_id in state["tools"]:
                    archive.writestr(f"tools/{item_id}.json", json.dumps(state["tools"][item_id], indent=2))
            for item_id in included_presets:
                if item_id in state["presets"]:
                    archive.writestr(f"presets/{item_id}.json", json.dumps(state["presets"][item_id], indent=2))
            archive.writestr("documentation/README.md", "# Fractal Tool Profile\n\nExported by Fractal Tool Customization Runtime.\n")
        return {"path": str(target_path), "manifest": manifest}

    def import_tool_profile(self, archive_path: str | Path, *, strategy: str = "copy") -> dict[str, Any]:
        path = Path(archive_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        self.snapshot_tool_runtime("before-import")
        state = self.load_tool_runtime()
        preview = {"tools": [], "profiles": [], "presets": [], "conflicts": [], "permissions": []}
        with zipfile.ZipFile(path, "r") as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("schemaVersion") != TOOL_PROFILE_SCHEMA_VERSION:
                raise ValueError("Unsupported tool profile schema")
            for name in archive.namelist():
                if name.startswith("tools/") and name.endswith(".json"):
                    item = json.loads(archive.read(name).decode("utf-8"))
                    target_id = item["id"]
                    if target_id in state["tools"]:
                        preview["conflicts"].append({"type": "tool", "id": target_id})
                        if strategy == "copy":
                            item["id"] = target_id + "-imported"
                    if "script.execute" in item.get("permissions", []):
                        item["state"] = "disabled"
                        item.setdefault("history", []).append({"at": utc_now(), "action": "disabled-import-script-permission"})
                    state["tools"][item["id"]] = item
                    preview["tools"].append(item["id"])
                    preview["permissions"].extend(item.get("permissions", []))
                if name.startswith("presets/") and name.endswith(".json"):
                    item = json.loads(archive.read(name).decode("utf-8"))
                    if item["id"] in state["presets"] and strategy == "copy":
                        item["id"] = item["id"] + "-imported"
                    state["presets"][item["id"]] = item
                    preview["presets"].append(item["id"])
                if name.startswith("profiles/") and name.endswith(".json"):
                    item = json.loads(archive.read(name).decode("utf-8"))
                    if item["id"] in state["profiles"] and strategy == "copy":
                        item["id"] = item["id"] + "-imported"
                    state["profiles"][item["id"]] = item
                    preview["profiles"].append(item["id"])
        preview["permissions"] = sorted(set(preview["permissions"]))
        self.save_tool_runtime(state)
        return preview

    def compare_profiles(self, left_id: str, right_id: str) -> dict[str, Any]:
        state = self.load_tool_runtime()
        left = state["profiles"][left_id]
        right = state["profiles"][right_id]
        return {
            "toolsAdded": sorted(set(right.get("enabledTools", [])) - set(left.get("enabledTools", []))),
            "toolsRemoved": sorted(set(left.get("enabledTools", [])) - set(right.get("enabledTools", []))),
            "presetsAdded": sorted(set(right.get("presets", [])) - set(left.get("presets", []))),
            "presetsRemoved": sorted(set(left.get("presets", [])) - set(right.get("presets", []))),
            "shortcutsChanged": left.get("shortcuts", {}) != right.get("shortcuts", {}),
            "parametersChanged": left.get("parameters", {}) != right.get("parameters", {}),
        }

    def reset_tool_runtime(self, *, recovery: bool = False) -> dict[str, Any]:
        self.snapshot_tool_runtime("before-reset")
        state = self.default_tool_runtime()
        if recovery:
            minimal = state["profiles"]["profile-minimal"]
            state["profiles"] = {"profile-minimal": minimal}
            state["tools"] = {tool_id: tool for tool_id, tool in state["tools"].items() if tool_id in minimal["enabledTools"]}
        self.save_tool_runtime(state)
        return state

    def snapshot_tool_runtime(self, reason: str) -> Path:
        state = self.load_tool_runtime() if self.tools_path.exists() else self.default_tool_runtime()
        target = self.root / "tool-runtime" / "snapshots" / f"{int(time.time() * 1000)}-{slug(reason)}.json"
        write_json_atomic(target, state)
        return target

    def default_tools(self) -> list[dict[str, Any]]:
        specs = [
            ("Selection", "selection", "selection"),
            ("Move", "transform", "move"),
            ("Rotate", "transform", "rotation"),
            ("Scale", "transform", "scale"),
            ("Pivot", "transform", "pivot"),
            ("Align", "layout", "alignment"),
            ("Measure", "diagnostic", "measurement"),
            ("Duplicate", "edit", "duplication"),
            ("Create Object", "3d", "creation"),
            ("Material Paint", "3d", "material"),
            ("Texture Tool", "3d", "texture"),
            ("Light Tool", "3d", "light"),
            ("Camera Tool", "3d", "camera"),
            ("Collision Tool", "3d", "collision"),
            ("Interaction Zone", "interaction", "zone"),
            ("Function Binding", "interaction", "function-binding"),
            ("Visual Scripting", "scripting", "scripting"),
            ("Data Binding", "data", "data"),
            ("Window Designer", "interface", "window"),
            ("Widget Designer", "interface", "widget"),
            ("Module Designer", "module", "module"),
            ("Graph Tool", "graph", "graph"),
            ("Debug Tool", "debug", "debug"),
            ("Optimization Tool", "optimization", "optimization"),
            ("Security Tool", "security", "security"),
            ("Agent Tool", "agent", "agent"),
        ]
        return [self.tool_definition(name, category, tool_type) for name, category, tool_type in specs]

    def default_tool_presets(self) -> list[dict[str, Any]]:
        groups = {
            "selection": ["Selection simple", "Selection multiple", "Selection precise", "Selection hierarchique", "Selection par surface", "Selection par type", "Selection par zone", "Selection spatiale proche", "Selection verrouillee aux objets interactifs"],
            "move": ["Libre", "Precision", "Grille fine", "Grille moyenne", "Grille large", "Surface", "Axe local", "Axe global", "Axe camera", "Deplacement spatial confortable", "Deplacement rapide", "Placement architectural"],
            "rotation": ["Libre", "Increment 1 degre", "Increment 5 degres", "Increment 15 degres", "Increment 45 degres", "Rotation locale", "Rotation globale", "Alignement surface", "Alignement camera", "Rotation architecturale"],
            "scale": ["Uniforme", "Libre", "Conservation du ratio", "Precision", "Depuis le centre", "Depuis le pivot", "Taille reelle", "Echelle metrique", "Echelle miniature", "Echelle interface spatiale"],
            "alignment": ["Alignement au sol", "Alignement au plafond", "Alignement a une face", "Alignement entre objets", "Centrage", "Distribution reguliere", "Empilement horizontal", "Empilement vertical", "Disposition circulaire", "Disposition radiale", "Disposition en grille", "Disposition spatiale automatique"],
            "interaction-zone": ["Zone ajustee", "Zone proche", "Zone moyenne", "Zone distante", "Boite", "Sphere", "Capsule", "Detection de regard", "Interaction tactile", "Interaction par proximite", "Interaction par clic", "Interaction avec maintien"],
            "interface-2d": ["Compact", "Confort", "Dense", "Mobile", "HUD transparent", "Contraste eleve", "Panneau inspecteur", "Console", "Dashboard", "Menu radial", "Palette flottante"],
            "interface-3d": ["Panneau proche", "Panneau moyen", "Panneau distant", "Etiquette spatiale", "Terminal spatial", "Inspecteur d'objet", "Menu autour de l'objet", "Tableau mural", "Interface attachee", "Interface suivant la camera", "Interface fixe dans le monde"],
            "performance": ["Economie", "Equilibre", "Haute qualite", "Grande scene", "Faible VRAM", "Faible RAM", "Priorite edition", "Priorite rendu", "Priorite interaction", "Mode diagnostic"],
        }
        presets: list[dict[str, Any]] = []
        for category, names in groups.items():
            for index, name in enumerate(names):
                patch = {"preset": name, "category": category, "order": index}
                if "Grille fine" in name:
                    patch.update({"snap.moveStep": 0.01, "snap.angleStep": 1})
                if "Faible VRAM" in name:
                    patch.update({"performance.preview": "reduced", "performance.cache": "limited"})
                presets.append({"id": "preset-" + slug(category + "-" + name), "name": name, "category": category, "toolId": "", "patch": patch, "version": "1.0.0", "createdAt": utc_now()})
        return presets

    def default_tool_profiles(self) -> list[dict[str, Any]]:
        names = ["Debutant", "Standard", "Creation 2D", "Creation 3D", "HUD", "Spatial", "Developpement", "Scripting visuel", "Precision", "Performance", "Grande scene", "Mobile", "Accessibilite", "Minimal", "Expert"]
        all_tools = [tool["id"] for tool in self.default_tools()]
        profiles = []
        for name in names:
            profile_id = "profile-" + slug(name)
            enabled = all_tools[:8] if name == "Minimal" else all_tools
            profiles.append(
                {
                    "id": profile_id,
                    "name": name,
                    "baseProfileId": "",
                    "metadata": {"system": True, "createdAt": utc_now(), "version": "1.0.0"},
                    "enabledTools": enabled,
                    "hiddenTools": [],
                    "parameters": {},
                    "presets": [],
                    "shortcuts": {},
                    "gestures": {},
                    "toolbars": [],
                    "menus": [],
                    "themes": [],
                    "gizmos": {},
                    "assistants": [],
                    "performanceProfiles": [name if name in {"Performance", "Grande scene", "Mobile"} else "Equilibre"],
                    "contextRules": [],
                    "locked": True,
                }
            )
        return profiles

    def default_tool_parameters(self, tool_type: str) -> dict[str, Any]:
        return {
            "enabled": {"type": "boolean", "default": True, "group": "general", "order": 0, "permission": "interface.read"},
            "snap": {"type": "boolean", "default": tool_type in {"move", "rotation", "scale"}, "group": "precision", "order": 1},
            "moveStep": {"type": "distance", "default": 0.25, "min": 0.001, "max": 10, "step": 0.001, "unit": "unit", "group": "precision"},
            "angleStep": {"type": "angle", "default": 15, "min": 0.1, "max": 90, "step": 0.1, "unit": "deg", "group": "precision"},
            "gizmoSize": {"type": "decimal", "default": 1, "min": 0.1, "max": 10, "group": "gizmo"},
            "preview": {"type": "boolean", "default": True, "group": "performance"},
        }

    def flatten(self, value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict):
                result.update(self.flatten(item, path))
            else:
                result[path] = item
        return result
