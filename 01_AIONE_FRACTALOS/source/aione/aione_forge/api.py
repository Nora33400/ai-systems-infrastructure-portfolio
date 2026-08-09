from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .forge import AioneForge
from .io import resolve_runtime_dir, write_json, write_text
from .mmr import (
    render_answer_quality_verification_status,
    render_external_workload_adapter_status,
    render_real_user_task_benchmark_status,
    run_answer_quality_verification,
    run_external_workload_adapter,
    run_real_user_task_benchmark,
)
from .operators import MemoryOperator, RoutingOperator, TruthGateOperator


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: Any
    headers: dict[str, str] | None = None


class AioneLocalApi:
    """Small localhost JSON API for browser extensions, web clients and local tools."""

    def __init__(
        self,
        *,
        runtime_dir: str | None = None,
        target_workspace: str = ".",
        api_token: str | None = None,
    ) -> None:
        resolved_runtime_dir, used_fallback = resolve_runtime_dir(runtime_dir)
        self.runtime_dir = resolved_runtime_dir
        self.used_fallback = used_fallback
        self.target_workspace = Path(target_workspace).expanduser().resolve()
        self.api_token = api_token if api_token is not None else os.environ.get("AIONE_API_TOKEN")
        self._module_actions: dict[tuple[str, str], Callable[[JsonObject], JsonObject]] = {
            ("routing", "route"): self._route_mission,
            ("memory", "create-tile"): self._create_memory_tile,
            ("truth", "create-proof-capsule"): self._create_proof_capsule,
        }

    def handle_request(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        method = method.upper()
        route_path = self._route_path(path)
        request_headers = {key.lower(): value for key, value in (headers or {}).items()}

        if method == "OPTIONS":
            return ApiResponse(HTTPStatus.NO_CONTENT, None)

        if not self._authorized(request_headers):
            return self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "A valid API token is required.")

        try:
            if method == "GET" and route_path == "/api/v1/health":
                return self._ok(self._health())
            if method == "GET" and route_path == "/api/v1/modules":
                return self._ok({"modules": self.module_specs()})
            if method == "GET" and route_path == "/api/v1/forge/status":
                return self._ok(self._forge_status())
            if method == "POST" and route_path == "/api/v1/forge/run":
                return self._ok(self._forge_run(self._require_object(body)))
            if method == "POST" and route_path == "/api/v1/workload/evaluate":
                return self._ok(self._evaluate_workload(self._require_object(body)))
            if method == "POST" and route_path.startswith("/api/v1/modules/"):
                return self._ok(self._dispatch_module_action(route_path, self._require_object(body)))
        except ValueError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))
        except FileNotFoundError as exc:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", str(exc))

        return self._error(HTTPStatus.NOT_FOUND, "not_found", f"Unknown endpoint: {method} {route_path}")

    def module_specs(self) -> list[JsonObject]:
        return [
            {
                "id": "routing",
                "name": "RoutingOperator",
                "description": "Selects an AIONE model role from a mission and optional message.",
                "actions": [
                    {
                        "id": "route",
                        "method": "POST",
                        "path": "/api/v1/modules/routing/route",
                        "input": {"mission": "object", "message": "object|null"},
                    }
                ],
            },
            {
                "id": "memory",
                "name": "MemoryOperator",
                "description": "Creates local knowledge tiles that can be stored or inspected by clients.",
                "actions": [
                    {
                        "id": "create-tile",
                        "method": "POST",
                        "path": "/api/v1/modules/memory/create-tile",
                        "input": {
                            "title": "string",
                            "summary": "string",
                            "source_refs": "string[]",
                            "tags": "string[]",
                            "claims": "string[]",
                        },
                    }
                ],
            },
            {
                "id": "truth",
                "name": "TruthGateOperator",
                "description": "Builds proof capsules and checks claims against local memory records.",
                "actions": [
                    {
                        "id": "create-proof-capsule",
                        "method": "POST",
                        "path": "/api/v1/modules/truth/create-proof-capsule",
                        "input": {
                            "target_artifact": "string",
                            "claims": "string[]",
                            "sources": "string[]",
                            "tests": "string[]",
                            "risks": "string[]|null",
                            "memory_records": "object[]|null",
                        },
                    }
                ],
            },
        ]

    def cors_headers(self, origin: str | None) -> dict[str, str]:
        headers = {
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Aione-Api-Token",
            "Vary": "Origin",
        }
        if origin and self._allowed_origin(origin):
            headers["Access-Control-Allow-Origin"] = origin
        return headers

    def serve_forever(self, *, host: str = "127.0.0.1", port: int = 8765) -> None:
        handler_cls = self._make_handler()
        server = ThreadingHTTPServer((host, port), handler_cls)
        try:
            server.serve_forever()
        finally:
            server.server_close()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "AioneLocalApi/0.1"

            def do_OPTIONS(self) -> None:
                self._send(app.handle_request("OPTIONS", self.path, headers=dict(self.headers)))

            def do_GET(self) -> None:
                self._send(app.handle_request("GET", self.path, headers=dict(self.headers)))

            def do_POST(self) -> None:
                try:
                    body = self._read_json_body()
                except ValueError as exc:
                    response = app._error(HTTPStatus.BAD_REQUEST, "bad_json", str(exc))
                else:
                    response = app.handle_request("POST", self.path, body=body, headers=dict(self.headers))
                self._send(response)

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _read_json_body(self) -> Any:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON body: {exc.msg}") from exc

            def _send(self, response: ApiResponse) -> None:
                origin = self.headers.get("Origin")
                body_bytes = b""
                if response.body is not None:
                    body_bytes = json.dumps(response.body, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(int(response.status))
                headers = {"Content-Type": "application/json; charset=utf-8", **app.cors_headers(origin)}
                if response.headers:
                    headers.update(response.headers)
                headers["Content-Length"] = str(len(body_bytes))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                if body_bytes:
                    self.wfile.write(body_bytes)

        return Handler

    def _health(self) -> JsonObject:
        return {
            "status": "ok",
            "service": "aione-local-api",
            "version": "v1",
            "runtime_dir": str(self.runtime_dir),
            "target_workspace": str(self.target_workspace),
            "used_fallback_runtime_dir": self.used_fallback,
            "auth_required": bool(self.api_token),
            "module_count": len(self.module_specs()),
        }

    def _forge_status(self) -> JsonObject:
        forge = AioneForge(runtime_dir=str(self.runtime_dir), target_workspace=str(self.target_workspace))
        return forge.load_state()

    def _forge_run(self, payload: JsonObject) -> JsonObject:
        cycles = int(payload.get("cycles", 1))
        if cycles < 1 or cycles > 10:
            raise ValueError("cycles must be between 1 and 10 for API-triggered runs")
        if payload.get("continuous") is True:
            raise ValueError("continuous Forge runs must be started from the CLI, not the HTTP API")

        forge = AioneForge(runtime_dir=str(self.runtime_dir), target_workspace=str(self.target_workspace))
        result = forge.run(cycles=cycles)
        return {
            "runtime_dir": str(result.runtime_dir),
            "used_fallback": result.used_fallback,
            "cycle": result.cycle,
            "status": result.status,
            "artifact_count": len(result.artifacts),
            "artifacts": result.artifacts,
        }

    def _evaluate_workload(self, payload: JsonObject) -> JsonObject:
        source_path = self._resolve_source_path(str(payload.get("path", "")).strip())
        queries = payload.get("queries")
        if queries is not None and not isinstance(queries, list):
            raise ValueError("queries must be a list of strings or null")
        benchmark = run_external_workload_adapter(
            self.runtime_dir / "stores" / "mmr_index.sqlite",
            source_path=source_path,
            queries=queries,
        )
        report_path = self.runtime_dir / "reports" / "MMR_EXTERNAL_WORKLOAD_ADAPTER.md"
        artifact_path = self.runtime_dir / "kernel" / "mmr_external_workload_adapter.json"
        write_text(report_path, render_external_workload_adapter_status(benchmark))
        write_json(artifact_path, benchmark)

        answer_quality = None
        if bool(payload.get("verify_answer", False)):
            answer_quality = run_answer_quality_verification(
                self.runtime_dir / "stores" / "mmr_index.sqlite",
                source_path=source_path,
                queries=queries,
            )
            write_text(
                self.runtime_dir / "reports" / "MMR_ANSWER_QUALITY_VERIFICATION.md",
                render_answer_quality_verification_status(answer_quality),
            )
            write_json(self.runtime_dir / "kernel" / "mmr_answer_quality_verification.json", answer_quality)

        real_tasks = None
        if bool(payload.get("real_tasks", False)):
            real_tasks = run_real_user_task_benchmark(
                self.runtime_dir / "stores" / "mmr_index.sqlite",
                source_path=source_path,
            )
            write_text(
                self.runtime_dir / "reports" / "MMR_REAL_USER_TASK_BENCHMARK.md",
                render_real_user_task_benchmark_status(real_tasks),
            )
            write_json(self.runtime_dir / "kernel" / "mmr_real_user_task_benchmark.json", real_tasks)

        return {
            "runtime_dir": str(self.runtime_dir),
            "status": benchmark["result"],
            "source_path": str(source_path),
            "report": str(report_path),
            "artifact": str(artifact_path),
            "metrics": benchmark["metrics"],
            "answer_quality_metrics": answer_quality["metrics"] if answer_quality else None,
            "real_tasks_metrics": real_tasks["metrics"] if real_tasks else None,
        }

    def _dispatch_module_action(self, route_path: str, payload: JsonObject) -> JsonObject:
        parts = route_path.strip("/").split("/")
        if len(parts) != 5:
            raise ValueError("module endpoints must match /api/v1/modules/{module}/{action}")
        module_id, action_id = parts[3], parts[4]
        action = self._module_actions.get((module_id, action_id))
        if action is None:
            raise FileNotFoundError(f"Unknown module action: {module_id}/{action_id}")
        return {
            "module": module_id,
            "action": action_id,
            "result": action(payload),
        }

    def _route_mission(self, payload: JsonObject) -> JsonObject:
        mission = payload.get("mission")
        if not isinstance(mission, dict):
            raise ValueError("mission must be an object")
        message = payload.get("message")
        if message is not None and not isinstance(message, dict):
            raise ValueError("message must be an object or null")
        return RoutingOperator().route(mission, message)

    def _create_memory_tile(self, payload: JsonObject) -> JsonObject:
        return MemoryOperator().create_tile(
            title=self._required_string(payload, "title"),
            summary=self._required_string(payload, "summary"),
            source_refs=self._string_list(payload, "source_refs"),
            tags=self._string_list(payload, "tags"),
            claims=self._string_list(payload, "claims"),
            relations=self._optional_string_list(payload, "relations"),
            compression_level=str(payload.get("compression_level", "summary")),
        )

    def _create_proof_capsule(self, payload: JsonObject) -> JsonObject:
        memory_records = payload.get("memory_records")
        if memory_records is not None and not isinstance(memory_records, list):
            raise ValueError("memory_records must be a list or null")
        return TruthGateOperator().create_proof_capsule(
            target_artifact=self._required_string(payload, "target_artifact"),
            claims=self._string_list(payload, "claims"),
            sources=self._string_list(payload, "sources"),
            tests=self._string_list(payload, "tests"),
            risks=self._optional_string_list(payload, "risks"),
            memory_records=memory_records,
        )

    def _resolve_source_path(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("path is required")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.target_workspace / path
        path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"Source path does not exist: {path}")
        return path

    def _authorized(self, headers: dict[str, str]) -> bool:
        if not self.api_token:
            return True
        auth = headers.get("authorization", "")
        token = headers.get("x-aione-api-token", "")
        return auth == f"Bearer {self.api_token}" or token == self.api_token

    def _allowed_origin(self, origin: str) -> bool:
        if origin.startswith(("chrome-extension://", "moz-extension://", "opera-extension://")):
            return True
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}

    def _route_path(self, path: str) -> str:
        route_path = urlparse(path).path.rstrip("/")
        return route_path or "/"

    def _require_object(self, body: Any) -> JsonObject:
        if body is None:
            return {}
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        return body

    def _required_string(self, payload: JsonObject, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value

    def _string_list(self, payload: JsonObject, key: str) -> list[str]:
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings")
        return value

    def _optional_string_list(self, payload: JsonObject, key: str) -> list[str] | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings or null")
        return value

    def _ok(self, body: Any) -> ApiResponse:
        return ApiResponse(HTTPStatus.OK, body)

    def _error(self, status: HTTPStatus, code: str, message: str) -> ApiResponse:
        return ApiResponse(
            int(status),
            {
                "status": "error",
                "error": {
                    "code": code,
                    "message": message,
                },
            },
        )
