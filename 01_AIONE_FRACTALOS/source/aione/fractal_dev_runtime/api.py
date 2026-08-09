from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .runtime import ContinuousDevRuntime, RuntimeConfig


@dataclass(frozen=True)
class ApiResult:
    status: int
    body: Any
    content_type: str = "application/json; charset=utf-8"


class ContinuousDevApi:
    def __init__(self, runtime: ContinuousDevRuntime, *, api_token: str | None = None) -> None:
        self.runtime = runtime
        self.api_token = api_token or self._load_or_create_token()

    def serve_forever(self, *, host: str = "127.0.0.1", port: int = 8795) -> None:
        if host in {"0.0.0.0", "::"} and os.environ.get("FRACTAL_CDR_ALLOW_ALL_INTERFACES") != "1":
            raise ValueError("Binding to all interfaces is disabled. Set FRACTAL_CDR_ALLOW_ALL_INTERFACES=1 explicitly.")
        server = ThreadingHTTPServer((host, port), self._handler())
        try:
            server.serve_forever()
        finally:
            server.server_close()

    def handle(self, method: str, raw_path: str, *, body: Any = None, headers: dict[str, str] | None = None) -> ApiResult:
        parsed = urlparse(raw_path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        method = method.upper()
        headers = {key.lower(): value for key, value in (headers or {}).items()}

        if method == "OPTIONS":
            return ApiResult(HTTPStatus.NO_CONTENT, None)
        if method == "GET" and path == "/":
            return ApiResult(HTTPStatus.OK, self._mobile_html(), "text/html; charset=utf-8")
        if method == "GET" and path == "/openapi.json":
            return ApiResult(HTTPStatus.OK, self.runtime.openapi_spec())
        if method == "GET" and path == "/api/v1/health":
            return ApiResult(HTTPStatus.OK, self.runtime.health())

        if not self._authorized(headers):
            return self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "A valid local runtime token is required.")

        try:
            if method == "GET" and path == "/api/v1/runtime/status":
                return ApiResult(HTTPStatus.OK, self.runtime.status())
            if method == "GET" and path == "/api/v1/runtime/mobile":
                return ApiResult(HTTPStatus.OK, {"summary": self.runtime.mobile_summary(), "queue": self.runtime.mobile_queue(limit=10)})
            if method == "GET" and path == "/api/v1/creation/status":
                return ApiResult(HTTPStatus.OK, self.runtime.creation_studio_status())
            if method == "POST" and path == "/api/v1/creation/scenario":
                return ApiResult(HTTPStatus.OK, self.runtime.run_creation_studio_scenario())
            if method == "GET" and path == "/api/v1/tools/status":
                return ApiResult(HTTPStatus.OK, self.runtime.tool_customization_status())
            if method == "POST" and path == "/api/v1/runtime/pause":
                return ApiResult(HTTPStatus.OK, self.runtime.pause_runtime(reason="api"))
            if method == "POST" and path == "/api/v1/runtime/resume":
                return ApiResult(HTTPStatus.OK, self.runtime.resume_runtime())
            if method == "POST" and path == "/api/v1/runtime/stop-after-current":
                return ApiResult(HTTPStatus.OK, self.runtime.stop_after_current())
            if method == "POST" and path == "/api/v1/runtime/emergency-stop":
                return ApiResult(HTTPStatus.OK, self.runtime.emergency_stop())
            if method == "POST" and path == "/api/v1/runtime/run-cycle":
                payload = self._object(body)
                return ApiResult(HTTPStatus.OK, self.runtime.run_cycle(max_steps=int(payload.get("max_steps", 1) or 1)))
            if method == "POST" and path == "/api/v1/message":
                payload = self._object(body)
                return ApiResult(HTTPStatus.OK, self.runtime.interpret_message(str(payload.get("message", "")), author=str(payload.get("author", "the owner"))))
            if method == "GET" and path == "/api/v1/ideas":
                limit = int(query.get("limit", ["50"])[0])
                status = query.get("status", [None])[0]
                return ApiResult(HTTPStatus.OK, {"ideas": self.runtime.list_ideas(status=status, limit=limit)})
            if method == "POST" and path == "/api/v1/ideas":
                payload = self._object(body)
                return ApiResult(HTTPStatus.CREATED, self.runtime.add_idea(str(payload.get("text", "")), author=str(payload.get("author", "the owner")), source=str(payload.get("source", "api"))))
            if method == "POST" and path.endswith("/plan") and path.startswith("/api/v1/ideas/"):
                idea_id = path.split("/")[-2]
                return ApiResult(HTTPStatus.OK, self.runtime.plan_idea(idea_id))
            if method == "POST" and path.endswith("/approve") and path.startswith("/api/v1/ideas/"):
                idea_id = path.split("/")[-2]
                return ApiResult(HTTPStatus.OK, self.runtime.approve_idea(idea_id))
            if method == "GET" and path == "/api/v1/queue":
                return ApiResult(HTTPStatus.OK, {"queue": self.runtime.list_queue(limit=int(query.get("limit", ["20"])[0]))})
            if method == "POST" and path == "/api/v1/idea-worker/run":
                return ApiResult(HTTPStatus.OK, self.runtime.run_idea_worker())
            if method == "POST" and path == "/api/v1/ideas/import-ready":
                return ApiResult(HTTPStatus.OK, self.runtime.import_ready_ideas())
            if method == "GET" and path == "/api/v1/memory/status":
                return ApiResult(HTTPStatus.OK, self.runtime.memory_status())
            if method == "POST" and path == "/api/v1/memory/restore":
                payload = self._object(body)
                return ApiResult(HTTPStatus.OK, self.runtime.restore_memory(str(payload.get("id", ""))))
            if method == "POST" and path == "/api/v1/backup":
                payload = self._object(body)
                return ApiResult(HTTPStatus.OK, self.runtime.backup(payload.get("target")))
            if method == "GET" and path == "/api/v1/diagnostics":
                return ApiResult(HTTPStatus.OK, {"markdown": self.runtime.diagnostics_report()})
        except KeyError as exc:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", str(exc))
        except ValueError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))
        except Exception as exc:
            return self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "runtime_error",
                f"component=ContinuousDevApi operation={method} {path} cause={type(exc).__name__}: {exc}",
            )

        return self._error(HTTPStatus.NOT_FOUND, "not_found", f"Unknown endpoint: {method} {path}")

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "FractalContinuousDevRuntime/0.1"

            def do_OPTIONS(self) -> None:
                self._send(app.handle("OPTIONS", self.path, headers=dict(self.headers)))

            def do_GET(self) -> None:
                self._send(app.handle("GET", self.path, headers=dict(self.headers)))

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    self._send(app._error(HTTPStatus.BAD_REQUEST, "bad_json", "Invalid JSON body."))
                    return
                self._send(app.handle("POST", self.path, body=payload, headers=dict(self.headers)))

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send(self, result: ApiResult) -> None:
                self.send_response(result.status)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Fractal-Dev-Token")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if result.body is None:
                    return
                if result.content_type.startswith("application/json"):
                    payload = json.dumps(result.body, ensure_ascii=False, indent=2).encode("utf-8")
                elif isinstance(result.body, str):
                    payload = result.body.encode("utf-8")
                else:
                    payload = str(result.body).encode("utf-8")
                self.wfile.write(payload)

        return Handler

    def _authorized(self, headers: dict[str, str]) -> bool:
        provided = headers.get("x-fractal-dev-token", "")
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        return bool(provided and secrets.compare_digest(provided, self.api_token))

    def _load_or_create_token(self) -> str:
        env_token = os.environ.get("FRACTAL_CDR_TOKEN")
        if env_token:
            return env_token
        token_path = self.runtime.runtime_dir / "runtime-token.txt"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        if token_path.exists():
            return token_path.read_text(encoding="utf-8").strip()
        token = secrets.token_urlsafe(32)
        token_path.write_text(token, encoding="utf-8")
        return token

    def _mobile_html(self) -> str:
        return """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fractal Continuous Dev</title>
  <style>
    body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#0c1117;color:#e9eef4}
    main{max-width:780px;margin:auto;padding:16px}
    h1{font-size:22px;margin:8px 0 12px}
    textarea,input{width:100%;box-sizing:border-box;border:1px solid #334155;background:#111827;color:#f8fafc;border-radius:6px;padding:10px}
    button{border:0;border-radius:6px;padding:10px 12px;margin:4px;background:#38bdf8;color:#031018;font-weight:700}
    button.secondary{background:#263244;color:#d7e3f0}
    pre{white-space:pre-wrap;background:#111827;border:1px solid #243244;border-radius:6px;padding:12px;overflow:auto}
    .row{display:flex;flex-wrap:wrap;gap:6px}
  </style>
</head>
<body>
<main>
  <h1>Fractal Continuous Dev Commander</h1>
  <input id="token" placeholder="Token local X-Fractal-Dev-Token">
  <textarea id="msg" rows="4" placeholder="Ajoute cette idée à la liste : ..."></textarea>
  <div class="row">
    <button onclick="sendMsg()">Envoyer</button>
    <button class="secondary" onclick="getStatus()">Status</button>
    <button class="secondary" onclick="runCycle()">Run cycle</button>
    <button class="secondary" onclick="ideaWorker()">Idea worker</button>
    <button class="secondary" onclick="pause()">Pause</button>
    <button class="secondary" onclick="resume()">Resume</button>
  </div>
  <pre id="out">Charge le token local depuis runtime-token.txt.</pre>
</main>
<script>
const out=document.getElementById('out');
function headers(){return {'Content-Type':'application/json','X-Fractal-Dev-Token':document.getElementById('token').value.trim()};}
async function call(path,opts={}){const r=await fetch(path,{...opts,headers:headers()}); out.textContent=await r.text();}
function sendMsg(){call('/api/v1/message',{method:'POST',body:JSON.stringify({message:document.getElementById('msg').value})});}
function getStatus(){call('/api/v1/runtime/mobile');}
function runCycle(){call('/api/v1/runtime/run-cycle',{method:'POST',body:JSON.stringify({max_steps:1})});}
function ideaWorker(){call('/api/v1/idea-worker/run',{method:'POST',body:'{}'});}
function pause(){call('/api/v1/runtime/pause',{method:'POST',body:'{}'});}
function resume(){call('/api/v1/runtime/resume',{method:'POST',body:'{}'});}
</script>
</body>
</html>
"""

    def _object(self, body: Any) -> dict[str, Any]:
        if isinstance(body, dict):
            return body
        raise ValueError("JSON object body required.")

    def _error(self, status: int, code: str, message: str) -> ApiResult:
        return ApiResult(status, {"error": {"code": code, "message": message}})


def build_api(runtime_dir: str | Path | None = None, workspace_root: str | Path = ".", token: str | None = None) -> ContinuousDevApi:
    runtime = ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=runtime_dir, workspace_root=workspace_root))
    runtime.initialize()
    return ContinuousDevApi(runtime, api_token=token)
