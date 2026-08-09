from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core.autonomy_runtime import autonomy_report, evolve_ecosystem, run_workloads, submit_workload
from .core.codex_worker import run_worker_sessions, submit_worker_session, worker_report, worker_to_mission
from .core.engine import submit_intent, tick
from .core.gpu_runtime import detect_gpu_runtime, mission_control_snapshot
from .core.mesh_federation import mesh_cache_manifest, mesh_cache_report, mesh_daemon_cycle, mesh_daemon_snapshot, mesh_descriptor, mesh_flush_outbox, mesh_import_bundle, mesh_status, _upsert_node
from .core.perf_governor import PerformanceGovernor
from .core.ram_memory import OmegaRAM
from .core.state import load_state
from .core.ui_runtime import available_views, build_ui_model
from .tilemindfs.planner import plan_jobs
from .tilemindfs.store import TileMindFS


def serve_daemon(workspace: Path, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"ok": True})
                return
            if self.path == "/state":
                self._send_json(200, load_state(workspace))
                return
            if self.path == "/autonomy/report":
                self._send_json(200, autonomy_report(workspace))
                return
            if self.path == "/worker/report":
                self._send_json(200, worker_report(workspace))
                return
            if self.path == "/ui/views":
                self._send_json(200, {"views": available_views()})
                return
            if self.path.startswith("/ui/view"):
                active = self.path.split("?view=", 1)[1] if "?view=" in self.path else "mission-control"
                self._send_json(200, build_ui_model(workspace, active_view=active))
                return
            if self.path == "/tile/report":
                self._send_json(200, TileMindFS(workspace).report())
                return
            if self.path == "/memory/report":
                self._send_json(200, OmegaRAM(workspace).report())
                return
            if self.path == "/performance/report":
                self._send_json(200, PerformanceGovernor(workspace).report())
                return
            if self.path == "/gpu/runtime":
                self._send_json(200, detect_gpu_runtime(workspace))
                return
            if self.path == "/mesh/status":
                self._send_json(200, mesh_status(workspace))
                return
            if self.path == "/mesh/cache":
                self._send_json(200, mesh_cache_report(workspace))
                return
            if self.path == "/mesh/cache-manifest":
                self._send_json(200, mesh_cache_manifest(workspace))
                return
            if self.path == "/mesh/descriptor":
                endpoint = f"http://{host}:{port}"
                self._send_json(200, mesh_descriptor(workspace, endpoint=endpoint))
                return
            if self.path == "/mesh/heartbeat":
                self._send_json(200, mesh_daemon_snapshot(workspace))
                return
            if self.path == "/mesh/outbox":
                self._send_json(200, mesh_status(workspace).get("outbox", []))
                return
            if self.path == "/mission-control":
                self._send_json(200, mission_control_snapshot(workspace))
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid_json"})
                return

            if self.path == "/tick":
                self._send_json(200, tick(workspace))
                return

            if self.path == "/intent":
                title = str(payload.get("title", "")).strip() or "Untitled intent"
                intent_text = str(payload.get("intent", "")).strip()
                if not intent_text:
                    self._send_json(400, {"error": "intent_required"})
                    return
                self._send_json(201, submit_intent(workspace, title, intent_text))
                return

            if self.path == "/autonomy/submit":
                domain = str(payload.get("domain", "")).strip().lower()
                title = str(payload.get("title", "")).strip() or f"{domain.title()} workload"
                goal = str(payload.get("goal", "")).strip()
                if not goal:
                    self._send_json(400, {"error": "goal_required"})
                    return
                try:
                    result = submit_workload(workspace, domain, title, goal, context=str(payload.get("context", "")))
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(201, result)
                return

            if self.path == "/autonomy/run":
                max_items = int(payload.get("max_items", 1))
                self._send_json(200, run_workloads(workspace, max_items=max_items))
                return

            if self.path == "/autonomy/evolve":
                queue_followups = bool(payload.get("queue_followups", True))
                self._send_json(200, evolve_ecosystem(workspace, queue_followups=queue_followups))
                return

            if self.path == "/worker/submit":
                mode = str(payload.get("mode", "")).strip().lower()
                title = str(payload.get("title", "")).strip() or f"{mode.title()} worker session"
                objective = str(payload.get("objective", "")).strip()
                if not objective:
                    self._send_json(400, {"error": "objective_required"})
                    return
                try:
                    result = submit_worker_session(workspace, mode, title, objective, scope=str(payload.get("scope", "")))
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(201, result)
                return

            if self.path == "/worker/run":
                max_items = int(payload.get("max_items", 1))
                auto_queue = bool(payload.get("auto_queue_autonomy", True))
                self._send_json(200, run_worker_sessions(workspace, max_items=max_items, auto_queue_autonomy=auto_queue))
                return

            if self.path == "/worker/mission":
                session_id = str(payload.get("session_id", "")).strip()
                if not session_id:
                    self._send_json(400, {"error": "session_id_required"})
                    return
                route = str(payload.get("route", "dynamic"))
                self._send_json(200, worker_to_mission(workspace, session_id, route=route))
                return

            if self.path == "/tile/store":
                file_path = payload.get("file")
                if not file_path:
                    self._send_json(400, {"error": "file_required"})
                    return
                mode = str(payload.get("mode", "cdc"))
                result = TileMindFS(workspace).store_file(Path(str(file_path)), mode=mode)
                self._send_json(201, result)
                return

            if self.path == "/plan":
                jobs = list(payload.get("jobs", []))
                if not jobs:
                    self._send_json(400, {"error": "jobs_required"})
                    return
                limit = payload.get("resource_limit")
                top_k = payload.get("top_k")
                result = plan_jobs(workspace, jobs, resource_limit=limit, top_k=top_k)
                self._send_json(200, result)
                return

            if self.path == "/memory/put":
                key = str(payload.get("key", "")).strip()
                text = str(payload.get("text", ""))
                if not key:
                    self._send_json(400, {"error": "key_required"})
                    return
                self._send_json(201, OmegaRAM(workspace).put_text(key=key, text=text, source="daemon"))
                return

            if self.path == "/memory/get":
                key = str(payload.get("key", "")).strip()
                if not key:
                    self._send_json(400, {"error": "key_required"})
                    return
                self._send_json(200, OmegaRAM(workspace).get(key))
                return

            if self.path == "/performance/tune":
                self._send_json(200, PerformanceGovernor(workspace).apply())
                return

            if self.path == "/mesh/cycle":
                compact = bool(payload.get("compact", True))
                self._send_json(200, mesh_daemon_cycle(workspace, compact=compact))
                return

            if self.path == "/mesh/flush":
                self._send_json(200, mesh_flush_outbox(workspace))
                return

            if self.path == "/mesh/push":
                tmp_bundle = workspace / "mesh" / "incoming_push.json"
                tmp_bundle.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
                result = mesh_import_bundle(workspace, tmp_bundle, auto_accept=True)
                cycle = mesh_daemon_cycle(workspace, compact=True)
                self._send_json(201, {"imported": result, "cycle": cycle})
                return

            if self.path == "/mesh/announce":
                node = _upsert_node(
                    workspace,
                    node_name=str(payload.get("name", "peer")),
                    endpoint=str(payload.get("endpoint", "")),
                    role=str(payload.get("role", "peer")),
                    capabilities=payload.get("capabilities"),
                    heartbeat_at=payload.get("heartbeat_at"),
                )
                endpoint = f"http://{host}:{port}"
                self._send_json(201, {"accepted": True, "peer": node, "local": mesh_descriptor(workspace, endpoint=endpoint)})
                return

            self._send_json(404, {"error": "not_found"})

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Omega TileMind daemon running on http://{host}:{port}")
    server.serve_forever()
