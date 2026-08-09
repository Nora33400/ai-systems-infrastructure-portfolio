from __future__ import annotations

from pathlib import Path

from fractal_creation_studio import FractalCreationStudio, StudioConfig
from fractal_creation_studio.cli import build_parser, handle
from fractal_dev_runtime.api import ContinuousDevApi
from fractal_dev_runtime.runtime import ContinuousDevRuntime, RuntimeConfig


def make_studio(tmp_path: Path) -> FractalCreationStudio:
    return FractalCreationStudio(StudioConfig.build(tmp_path / "studio"))


def test_acceptance_scenario_builds_publishable_project(tmp_path: Path) -> None:
    studio = make_studio(tmp_path)
    result = studio.run_acceptance_scenario()

    project_path = Path(result["project"]["path"])
    hud_path = Path(result["runtime"]["publish"]["hud"]["path"])
    spatial_path = Path(result["runtime"]["publish"]["spatial"]["path"])
    export_path = Path(result["tools"]["export"]["path"])

    assert result["project"]["validation"]["valid"] is True
    assert result["runtime"]["script"]["trace"] == ["event", "validate", "focus"]
    assert result["runtime"]["preview"]["windows"] == 1
    assert result["runtime"]["preview"]["widgets"] >= 2
    assert result["runtime"]["preview"]["objects3D"] >= 2
    assert result["runtime"]["preview"]["zones"] >= 2
    assert result["tools"]["resolved"]["conflicts"]
    assert project_path.exists()
    assert hud_path.exists()
    assert spatial_path.exists()
    assert export_path.exists()

    loaded = studio.load_project(project_path)
    assert loaded["windows"]
    assert loaded["models3D"]
    assert loaded["interactionZones"]
    assert loaded["eventBindings"]


def test_project_model_supports_windows_widgets_3d_zones_and_snapshots(tmp_path: Path) -> None:
    studio = make_studio(tmp_path)
    project = studio.create_project("Manual Studio Project")
    window = studio.create_window(project, "Inspector", size={"width": 500, "height": 320})
    widget = studio.create_widget(project, "Apply", "Button", parent_window_id=window["id"])
    source = studio.create_data_source(project, "Selection", "runtime-state", {"path": "selection.current"})
    binding = studio.bind_widget_data(project, widget["id"], source["id"], {"text": "name"})
    function = studio.register_function(project, "hud.window.open_custom", description="Open a custom HUD window.", permissions=["hud.window.open"])
    event = studio.bind_event_to_function(project, widget["id"], "OnClick", function["address"], {"windowId": window["id"]})
    script = studio.create_visual_script(
        project,
        "Click Flow",
        blocks=[{"id": "start", "type": "EventBlock", "event": "OnClick"}, {"id": "open", "type": "CallFunction"}],
        connections=[{"from": "start", "to": "open", "kind": "flow"}],
    )
    obj = studio.create_object3d(project, "Panel Cube", "cube")
    moved = studio.transform_object3d(project, obj["id"], move={"x": 0.26, "y": 0.24, "z": 0}, snap=True)
    zone = studio.create_zone_around_object(project, obj["id"], margin=0.4)
    mesh_path = tmp_path / "sample.obj"
    mesh_path.write_text("o sample\nv 0 0 0\nv 0 1 0\nv 1 0 0\nf 1 2 3\n", encoding="utf-8")
    imported = studio.import_object3d(project, mesh_path, scale=2, create_collision=True, create_interaction=True)
    saved = studio.save_project(project, reason="unit-test")
    snapshots = list((studio.snapshots_dir / project["id"]).glob("*.json"))
    preview = studio.preview_project(project)

    assert binding["id"] == widget["id"]
    assert binding["dataSource"] == source["id"]
    assert binding["customProperties"]["dataBinding"]["text"] == "name"
    assert event["functionAddress"] == function["address"]
    assert script["validation"]["valid"] is True
    assert moved["properties"]["transform"]["position"]["x"] == 0.25
    assert zone["properties"]["targetObjectId"] == obj["id"]
    assert imported["asset"]["format"] == "obj"
    assert saved.exists()
    assert snapshots
    assert preview["valid"] is True


def test_tool_customization_profiles_shortcuts_conflicts_and_recovery(tmp_path: Path) -> None:
    studio = make_studio(tmp_path)
    studio.initialize()
    clone = studio.clone_tool("tool-move", "Move Custom Test")
    precise = studio.create_tool_preset("Precise Test", "move", clone["id"], {"snap": {"moveStep": 0.01, "angleStep": 1}})
    coarse = studio.create_tool_preset("Coarse Test", "move", clone["id"], {"snap": {"moveStep": 1.0}})
    profile = studio.create_tool_profile("Tool Profile Test", tools=["tool-selection", clone["id"]], presets=[precise["id"]])
    first_shortcut = studio.set_shortcut(profile["id"], "tool.select", "S", context="studio")
    conflict_shortcut = studio.set_shortcut(profile["id"], "tool.move", "S", context="studio")
    resolved = studio.resolve_tool_parameters(clone["id"], profile["id"], active_presets=[precise["id"], coarse["id"]])
    toolbar = studio.create_toolbar("Tool Test Bar", [{"kind": "tool", "id": clone["id"]}])
    perf = studio.measure_tool_performance(clone["id"], targets=20, render_ms=6, response_ms=12)
    exported = studio.export_tool_profile(profile["id"])
    imported = studio.import_tool_profile(exported["path"], strategy="copy")
    recovery = studio.reset_tool_runtime(recovery=True)

    assert first_shortcut["success"] is True
    assert conflict_shortcut["success"] is False
    assert resolved["values"]["snap.moveStep"] == 1.0
    assert resolved["conflicts"]
    assert toolbar["id"].startswith("toolbar-")
    assert perf["sample"]["cost"] == "low"
    assert Path(exported["path"]).exists()
    assert imported["profiles"]
    assert list(recovery["profiles"].keys()) == ["profile-minimal"]


def test_cli_scenario_and_tool_status(tmp_path: Path) -> None:
    root = tmp_path / "cli"
    parser = build_parser()
    scenario_args = parser.parse_args(["--root", str(root), "--json", "scenario"])
    scenario = handle(scenario_args)
    status_args = parser.parse_args(["--root", str(root), "--json", "tool-status"])
    status = handle(status_args)

    assert scenario["project"]["validation"]["valid"] is True
    assert status["tools"] >= 26
    assert status["profiles"] >= 15


def test_continuous_runtime_api_exposes_creation_studio(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime = ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=tmp_path / "runtime", workspace_root=workspace))
    runtime.initialize()
    api = ContinuousDevApi(runtime, api_token="secret")

    status = api.handle("GET", "/api/v1/creation/status", headers={"X-Fractal-Dev-Token": "secret"})
    tools = api.handle("GET", "/api/v1/tools/status", headers={"X-Fractal-Dev-Token": "secret"})
    scenario = api.handle("POST", "/api/v1/creation/scenario", body={}, headers={"X-Fractal-Dev-Token": "secret"})
    message = api.handle("POST", "/api/v1/message", body={"message": "/studio status"}, headers={"X-Fractal-Dev-Token": "secret"})

    assert status.status == 200
    assert status.body["name"] == "Fractal Creation Studio"
    assert tools.status == 200
    assert tools.body["tools"] >= 26
    assert scenario.status == 200
    assert scenario.body["project"]["validation"]["valid"] is True
    assert message.body["intent"] == "creation_studio_status"
