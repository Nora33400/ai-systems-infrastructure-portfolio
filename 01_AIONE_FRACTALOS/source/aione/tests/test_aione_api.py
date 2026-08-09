from __future__ import annotations

from pathlib import Path

from aione_forge.api import AioneLocalApi


def test_local_api_health_and_modules(tmp_path: Path) -> None:
    app = AioneLocalApi(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path))

    health = app.handle_request("GET", "/api/v1/health")
    modules = app.handle_request("GET", "/api/v1/modules")

    assert health.status == 200
    assert health.body["status"] == "ok"
    assert health.body["service"] == "aione-local-api"
    assert health.body["auth_required"] is False
    assert modules.status == 200
    assert {module["id"] for module in modules.body["modules"]} == {"memory", "routing", "truth"}


def test_local_api_routes_mission_through_module_registry(tmp_path: Path) -> None:
    app = AioneLocalApi(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path))

    response = app.handle_request(
        "POST",
        "/api/v1/modules/routing/route",
        body={
            "mission": {
                "intent_raw": "implement a code module",
                "objective": "build API bridge",
                "depth": "normal",
                "risk_level": "low",
                "autonomy_level": "bounded",
            }
        },
    )

    assert response.status == 200
    assert response.body["module"] == "routing"
    assert response.body["action"] == "route"
    assert response.body["result"]["selected_role"] == "code"
    assert response.body["result"]["requires_verification"] is True


def test_local_api_creates_memory_tile(tmp_path: Path) -> None:
    app = AioneLocalApi(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path))

    response = app.handle_request(
        "POST",
        "/api/v1/modules/memory/create-tile",
        body={
            "title": "Local API",
            "summary": "Bridge for local clients.",
            "source_refs": ["docs/LOCAL_API_ARCHITECTURE.md"],
            "tags": ["api", "local"],
            "claims": ["Clients use the same module contract."],
        },
    )

    assert response.status == 200
    assert response.body["result"]["id"].startswith("KT-")
    assert response.body["result"]["verification_status"] == "partial"


def test_local_api_rejects_bad_payloads(tmp_path: Path) -> None:
    app = AioneLocalApi(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path))

    response = app.handle_request("POST", "/api/v1/modules/routing/route", body={"mission": "bad"})

    assert response.status == 400
    assert response.body["status"] == "error"
    assert response.body["error"]["code"] == "bad_request"


def test_local_api_optional_token_guard(tmp_path: Path) -> None:
    app = AioneLocalApi(runtime_dir=str(tmp_path / "runtime"), target_workspace=str(tmp_path), api_token="secret")

    rejected = app.handle_request("GET", "/api/v1/health")
    accepted = app.handle_request("GET", "/api/v1/health", headers={"Authorization": "Bearer secret"})

    assert rejected.status == 401
    assert accepted.status == 200
    assert accepted.body["auth_required"] is True
