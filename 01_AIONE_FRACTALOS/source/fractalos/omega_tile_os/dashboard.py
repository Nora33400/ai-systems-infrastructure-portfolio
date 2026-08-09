from __future__ import annotations

import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .core.action_router import execute_next_route, execute_route_loop
from .core.autonomy_runtime import autonomy_report, evolve_ecosystem, run_workloads, submit_workload
from .core.chrono_mesh import mission_journal_report
from .core.codex_worker import run_worker_sessions, submit_worker_session, worker_report, worker_to_mission
from .core.desktop_runtime import desktop_cycle_overlay, desktop_overlay_status, desktop_package_center, desktop_snapshot, desktop_tile_explorer
from .core.gpu_runtime import detect_gpu_runtime
from .core.mesh_federation import mesh_compact, mesh_consensus, mesh_daemon_snapshot, mesh_status
from .core.events import append_event, read_events
from .core.native_desktop_stack import native_desktop_blueprint, native_installation_plan, native_package_catalog, write_native_desktop_report
from .core.native_userspace import package_manifest, userspace_alpha_report, vfs_list, vfs_mount_report, write_userspace_alpha_report
from .core.perf_governor import PerformanceGovernor
from .core.ram_memory import OmegaRAM
from .core.state import load_state, load_ui_state, save_ui_state, utc_now
from .core.storage_vfs import storage_mount_report, storage_snapshot, storage_verify, storage_write, write_storage_vfs_report
from .core.ui_runtime import available_views, build_ui_model
from .tilemindfs.store import TileMindFS


def render_dashboard(workspace: Path, active_view: str = "mission-control", detail_key: str | None = None) -> str:
    state = load_state(workspace)
    report = TileMindFS(workspace).report()
    ram_report = OmegaRAM(workspace).report()
    perf_report = PerformanceGovernor(workspace).report()
    gpu_runtime = detect_gpu_runtime(workspace)
    mesh = mesh_status(workspace)
    mesh_daemon = mesh_daemon_snapshot(workspace)
    journal = mission_journal_report(workspace)
    autonomy = autonomy_report(workspace)
    worker = worker_report(workspace)
    events = read_events(workspace, limit=20)
    ui_model = build_ui_model(workspace, active_view=active_view, detail_key=detail_key)
    accent_map = {
        "cluster": "#b55a1a",
        "worker": "#8a4fff",
        "autonomy": "#1d8f6a",
        "research": "#2d6cdf",
        "automation": "#c94b16",
        "observatory": "#3b506b",
    }
    accent = accent_map.get(ui_model["view"].get("accent", ""), "#b55a1a")
    nav_html = "".join(
        f"<a href='/?view={html.escape(view['id'])}' style='display:inline-block;padding:8px 12px;margin:0 8px 8px 0;border-radius:999px;border:1px solid var(--line);text-decoration:none;color:var(--ink);background:{accent if ui_model['active_view'] == view['id'] else '#fffaf2'};color:{'#fffaf2' if ui_model['active_view'] == view['id'] else 'var(--ink)'}'>{html.escape(view['title'])}</a>"
        for view in available_views()
    )
    recommended_html = "".join(
        f"<li><a href='/?view={html.escape(view['id'])}' style='color:var(--ink)'>{html.escape(view['title'])}</a> - {html.escape(view['description'])}</li>"
        for view in ui_model.get("recommended_views", [])
    ) or "<li>none</li>"
    quick_actions_html = "".join(f"<li><code>{html.escape(item)}</code></li>" for item in ui_model['view'].get('quick_actions', [])) or "<li>No quick actions.</li>"
    focus_html = "".join(
        f"<div class='focus-chip'>{html.escape(str(item))}</div>"
        for item in ui_model['view'].get('focus', [])
    )
    action_panels = []
    for action in ui_model.get("actions", []):
        if action.get("kind") == "button":
            action_panels.append(
                "<article class='card'>"
                f"<h2>{html.escape(str(action['label']))}</h2>"
                f"<form method='post' action='/action'>"
                f"<input type='hidden' name='view' value='{html.escape(active_view)}'>"
                f"<input type='hidden' name='action_id' value='{html.escape(str(action['id']))}'>"
                "<button class='primary' type='submit'>Run</button>"
                "</form></article>"
            )
            continue
        fields_html = []
        defaults = dict(action.get("defaults", {}))
        for field in action.get("fields", []):
            field_name = str(field["name"])
            field_type = str(field.get("type", "text"))
            default = str(defaults.get(field_name, ""))
            if field_type == "hidden":
                fields_html.append(f"<input type='hidden' name='{html.escape(field_name)}' value='{html.escape(default)}'>")
            elif field_type == "textarea":
                fields_html.append(
                    f"<label><strong>{html.escape(str(field['label']))}</strong><textarea name='{html.escape(field_name)}'>{html.escape(default)}</textarea></label>"
                )
            elif field_type == "select":
                options_html = "".join(
                    f"<option value='{html.escape(str(option))}'{' selected' if str(option) == default else ''}>{html.escape(str(option))}</option>"
                    for option in field.get("options", [])
                )
                fields_html.append(
                    f"<label><strong>{html.escape(str(field['label']))}</strong><select name='{html.escape(field_name)}'>{options_html}</select></label>"
                )
            else:
                fields_html.append(
                    f"<label><strong>{html.escape(str(field['label']))}</strong><input type='text' name='{html.escape(field_name)}' value='{html.escape(default)}'></label>"
                )
        action_panels.append(
            "<article class='card'>"
            f"<h2>{html.escape(str(action['label']))}</h2>"
            f"<form method='post' action='/action' class='action-form'>"
            f"<input type='hidden' name='view' value='{html.escape(active_view)}'>"
            f"<input type='hidden' name='action_id' value='{html.escape(str(action['id']))}'>"
            + "".join(fields_html)
            + "<button class='primary' type='submit'>Submit</button></form></article>"
        )
    if active_view == "worker-studio":
        recent_workers = worker["recent_done"][:3]
        if recent_workers:
            options_html = "".join(
                f"<option value='{html.escape(str(item['id']))}'>{html.escape(str(item['title']))}</option>"
                for item in recent_workers
            )
            action_panels.append(
                "<article class='card'>"
                "<h2>Bridge Worker To Mission</h2>"
                "<form method='post' action='/action' class='action-form'>"
                f"<input type='hidden' name='view' value='{html.escape(active_view)}'>"
                "<input type='hidden' name='action_id' value='worker-mission'>"
                f"<label><strong>Session</strong><select name='session_id'>{options_html}</select></label>"
                "<label><strong>Route</strong><select name='route'><option value='checkpoint'>checkpoint</option><option value='dynamic'>dynamic</option></select></label>"
                "<button class='primary' type='submit'>Bridge</button></form></article>"
            )
    action_html = "".join(action_panels) or "<article class='card'><h2>Actions</h2><p>No actions for this view.</p></article>"
    detail_panel_html = ""
    if ui_model.get("detail_panel"):
        detail_panel_html = (
            "<article class='card'>"
            f"<h2>{html.escape(str(ui_model['detail_panel']['title']))}</h2>"
            + "<ul>"
            + "".join(f"<li>{html.escape(str(item))}</li>" for item in ui_model["detail_panel"]["items"])
            + "</ul></article>"
        )
    detail_cards_html = "".join(
        "<article class='card'>"
        f"<h2>{html.escape(str(card['title']))}</h2>"
        + "<ul>"
        + "".join(f"<li>{html.escape(str(item))}</li>" for item in card["items"])
        + "</ul></article>"
        for card in ui_model.get("detail_cards", [])
    )
    timeline_items = []
    for item in ui_model.get("timeline", []):
        label = f"<code>{html.escape(str(item['ts']))}</code> - <strong>{html.escape(str(item['kind']))}</strong> - {html.escape(str(item['title']))}"
        detail_key = item.get("detail_key")
        if detail_key:
            href = f"/?view=timeline-center&detail={quote(str(detail_key))}"
            timeline_items.append(f"<li><a href='{href}' style='color:var(--ink)'>{label}</a></li>")
        else:
            timeline_items.append(f"<li>{label}</li>")
    timeline_html = "".join(timeline_items) or "<li>No timeline items.</li>"
    ui_sections_html = "".join(
        "<article class='card'>"
        f"<h2>{html.escape(section['title'])}</h2>"
        + "<ul>"
        + "".join(f"<li>{html.escape(str(item))}</li>" for item in section["items"])
        + "</ul></article>"
        for section in ui_model["view"]["sections"]
    )

    agent_html = "".join(
        f"<li><strong>{html.escape(agent['name'])}</strong> - {html.escape(agent['status'])} - {html.escape(agent['last_output'])}</li>"
        for agent in state["agents"]
    )
    intent_html = "".join(
        f"<li><strong>{html.escape(item['title'])}</strong> - {html.escape(item['status'])}</li>"
        for item in state["intents"][-10:]
    ) or "<li>No intents yet.</li>"
    artifact_html = "".join(
        f"<li><strong>{html.escape(item['title'])}</strong> - {len(item['files'])} files - {len(item.get('tile_archives', []))} archives</li>"
        for item in state["artifacts"][-10:]
    ) or "<li>No artifacts yet.</li>"
    event_html = "".join(
        f"<li><code>{html.escape(event['ts'])}</code> - <strong>{html.escape(event['kind'])}</strong></li>"
        for event in reversed(events)
    ) or "<li>No events yet.</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Omega TileMind OS</title>
  <style>
    :root {{
      --bg: #efe8dc;
      --panel: #fffaf2;
      --line: #d9c8af;
      --ink: #231b14;
      --accent: {accent};
      --soft: #f0dbc4;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #f8f0e5 0%, transparent 35%),
        linear-gradient(180deg, #f2ebdf, var(--bg));
    }}
    .shell {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      background: linear-gradient(135deg, #fff5e7, #edd1b2);
      margin-bottom: 18px;
    }}
    .metrics, .grid {{
      display: grid;
      gap: 16px;
    }}
    .metrics {{
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin-top: 14px;
    }}
    .grid {{
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    .shell-grid {{
      display: grid;
      grid-template-columns: minmax(240px, 0.85fr) minmax(0, 2.15fr);
      gap: 16px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 10px 30px rgba(60, 31, 7, 0.07);
    }}
    .action-form {{
      display: grid;
      gap: 12px;
    }}
    .action-form label {{
      display: grid;
      gap: 6px;
      font-size: 14px;
    }}
    .action-form input,
    .action-form textarea,
    .action-form select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      background: #fffef9;
      color: var(--ink);
      border-radius: 12px;
      padding: 10px 12px;
      font: inherit;
    }}
    .action-form textarea {{
      min-height: 88px;
      resize: vertical;
    }}
    .primary {{
      border: none;
      background: var(--accent);
      color: #fffaf2;
      border-radius: 12px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
    }}
    .metric {{
      background: var(--soft);
      border-radius: 14px;
      padding: 12px;
    }}
    .focus-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .focus-chip {{
      background: rgba(255, 250, 242, 0.78);
      border: 1px solid rgba(35, 27, 20, 0.08);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 14px;
    }}
    .split {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }}
    h1, h2 {{
      margin-top: 0;
    }}
    ul {{
      margin-bottom: 0;
      padding-left: 18px;
    }}
    code {{
      background: #f8e7d5;
      padding: 2px 6px;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Omega TileMind OS</h1>
      <p>OS-like orchestration platform with native TileMindFS, resource-aware planning and local control surfaces.</p>
      <p><strong>Active view:</strong> {html.escape(ui_model['view']['headline'])}</p>
      <div style="margin-top:14px;">{nav_html}</div>
      <div class="focus-row">{focus_html}</div>
      <div class="metrics">
        <div class="metric"><strong>Status</strong><br>{html.escape(state['node']['status'])}</div>
        <div class="metric"><strong>Ticks</strong><br>{state['metrics']['ticks']}</div>
        <div class="metric"><strong>Processed</strong><br>{state['metrics']['processed_intents']}</div>
        <div class="metric"><strong>Queued</strong><br>{state['metrics']['queued_intents']}</div>
        <div class="metric"><strong>Manifests</strong><br>{report['manifest_count']}</div>
        <div class="metric"><strong>Unique Tiles</strong><br>{report['unique_tile_objects']}</div>
        <div class="metric"><strong>Hot RAM</strong><br>{ram_report['metrics']['hot_entries']}</div>
        <div class="metric"><strong>Perf Stability</strong><br>{perf_report['formulas']['stability_index']:.3f}</div>
        <div class="metric"><strong>Recommended Concurrency</strong><br>{perf_report['recommendations']['recommended_concurrency']}</div>
        <div class="metric"><strong>Mesh Nodes</strong><br>{mesh['node_count']}</div>
        <div class="metric"><strong>GPU Native</strong><br>{'yes' if gpu_runtime['native_runtime_available'] else 'no'}</div>
        <div class="metric"><strong>Missions</strong><br>{journal['mission_count']}</div>
        <div class="metric"><strong>Mesh Inbox</strong><br>{len(mesh['inbox'])}</div>
        <div class="metric"><strong>Mesh Outbox</strong><br>{len(mesh['outbox'])}</div>
        <div class="metric"><strong>Mesh Cycles</strong><br>{mesh_daemon['cycle_count']}</div>
        <div class="metric"><strong>Autonomy Queued</strong><br>{autonomy['status_counts'].get('queued', 0)}</div>
        <div class="metric"><strong>Autonomy Done</strong><br>{autonomy['status_counts'].get('done', 0)}</div>
        <div class="metric"><strong>Worker Queued</strong><br>{worker['status_counts'].get('queued', 0)}</div>
        <div class="metric"><strong>Worker Done</strong><br>{worker['status_counts'].get('done', 0)}</div>
      </div>
    </section>
    <section class="shell-grid">
      <div class="stack">
        <article class="card">
          <h2>Quick Actions</h2>
          <ul>{quick_actions_html}</ul>
        </article>
        {action_html}
        <article class="card">
          <h2>Suggested Views</h2>
          <ul>{recommended_html}</ul>
        </article>
        <article class="card">
          <h2>Timeline</h2>
          <ul>{timeline_html}</ul>
        </article>
        {detail_panel_html}
        <article class="card">
          <h2>Recent Events</h2>
          <ul>{event_html}</ul>
        </article>
      </div>
      <div class="stack">
        <section class="split">
          {ui_sections_html}
          {detail_cards_html}
        </section>
        <section class="grid">
      <article class="card">
        <h2>Agents</h2>
        <ul>{agent_html}</ul>
      </article>
      <article class="card">
        <h2>Intents</h2>
        <ul>{intent_html}</ul>
      </article>
      <article class="card">
        <h2>Artifacts</h2>
        <ul>{artifact_html}</ul>
      </article>
      <article class="card">
        <h2>Autonomy</h2>
        <ul>
          <li><strong>Submitted</strong> - {autonomy['metrics'].get('submitted', 0)}</li>
          <li><strong>Processed</strong> - {autonomy['metrics'].get('processed', 0)}</li>
          <li><strong>Evolution cycles</strong> - {autonomy['metrics'].get('evolution_cycles', 0)}</li>
          <li><strong>Domains</strong> - {html.escape(json.dumps(autonomy['domain_counts'], ensure_ascii=True))}</li>
        </ul>
      </article>
      <article class="card">
        <h2>Worker IA</h2>
        <ul>
          <li><strong>Submitted</strong> - {worker['metrics'].get('submitted', 0)}</li>
          <li><strong>Processed</strong> - {worker['metrics'].get('processed', 0)}</li>
          <li><strong>Reflections</strong> - {worker['metrics'].get('reflections', 0)}</li>
          <li><strong>Modes</strong> - {html.escape(json.dumps(worker['mode_counts'], ensure_ascii=True))}</li>
        </ul>
      </article>
      <article class="card">
        <h2>TileMindFS</h2>
        <ul>
          <li><strong>Total raw size</strong> - {report['total_raw_size']}</li>
          <li><strong>Total compressed size</strong> - {report['total_compressed_size']}</li>
          <li><strong>Compression ratio</strong> - {report['compression_ratio']:.4f}</li>
          <li><strong>Total manifest tiles</strong> - {report['total_manifest_tiles']}</li>
        </ul>
      </article>
      <article class="card">
        <h2>OmegaRAM</h2>
        <ul>
          <li><strong>Hot/Warm/Cold</strong> - {ram_report['metrics']['hot_entries']}/{ram_report['metrics']['warm_entries']}/{ram_report['metrics']['cold_entries']}</li>
          <li><strong>Cache hits</strong> - {ram_report['metrics']['cache_hits']}</li>
          <li><strong>Cache misses</strong> - {ram_report['metrics']['cache_misses']}</li>
          <li><strong>Promotions</strong> - {ram_report['metrics']['promotions']}</li>
          <li><strong>Demotions</strong> - {ram_report['metrics']['demotions']}</li>
        </ul>
      </article>
      <article class="card">
        <h2>Performance Governor</h2>
        <ul>
          <li><strong>Risk level</strong> - {html.escape(perf_report['recommendations']['risk_level'])}</li>
          <li><strong>CPU headroom</strong> - {perf_report['formulas']['cpu_headroom']:.3f}</li>
          <li><strong>GPU headroom</strong> - {perf_report['formulas']['gpu_headroom']:.3f}</li>
          <li><strong>Memory guard</strong> - {perf_report['formulas']['memory_guard']:.3f}</li>
          <li><strong>Planner limit</strong> - {perf_report['recommendations']['recommended_resource_limit']}</li>
        </ul>
      </article>
      <article class="card">
        <h2>GPU Runtime</h2>
        <ul>
          <li><strong>Native runtime</strong> - {'yes' if gpu_runtime['native_runtime_available'] else 'no'}</li>
          <li><strong>nvidia-smi</strong> - {'yes' if gpu_runtime['nvidia_smi_present'] else 'no'}</li>
          <li><strong>Detected devices</strong> - {len(gpu_runtime['devices']) - 1 if gpu_runtime['devices'] else 0}</li>
          <li><strong>Selected backend</strong> - {html.escape(str((gpu_runtime.get('selected_runtime') or {}).get('backend', 'simulated')))}</li>
        </ul>
      </article>
      <article class="card">
        <h2>Mission Control</h2>
        <ul>
          <li><strong>Profile</strong> - {html.escape(state['node'].get('performance_profile', 'unknown'))}</li>
          <li><strong>Mesh relays</strong> - {len(mesh['relays'])}</li>
          <li><strong>Outbox states</strong> - {", ".join(html.escape(item['status']) for item in mesh['outbox'][:3]) or 'none'}</li>
          <li><strong>Recent nodes</strong> - {", ".join(html.escape(item['name']) for item in mesh['nodes'][:3]) or 'none'}</li>
          <li><strong>Peer heartbeats</strong> - {", ".join(html.escape(str(item.get('heartbeat_at'))) for item in mesh['nodes'][:2]) or 'none'}</li>
          <li><strong>Mission journal</strong> - {journal['mission_count']} tracked</li>
          <li><strong>Inbox states</strong> - {", ".join(html.escape(item['status']) for item in mesh['inbox'][:3]) or 'none'}</li>
        </ul>
      </article>
      <article class="card">
        <h2>Mesh Daemon</h2>
        <ul>
          <li><strong>Status</strong> - {html.escape(str(mesh_daemon['status']))}</li>
          <li><strong>Cycle count</strong> - {mesh_daemon['cycle_count']}</li>
          <li><strong>Heartbeat</strong> - {html.escape(str(mesh_daemon['heartbeat_at']))}</li>
          <li><strong>Last run</strong> - {html.escape(str(mesh_daemon['last_run_at']))}</li>
        </ul>
      </article>
        </section>
      </div>
    </section>
  </div>
  <script>
    (function() {{
      const refreshMs = 30000;
      window.setTimeout(function() {{
        if (document.visibilityState === "visible") {{
          window.location.reload();
        }}
      }}, refreshMs);
    }})();
  </script>
</body>
</html>"""


def serve_dashboard(workspace: Path, host: str, port: int) -> None:
    def _summarize_action_result(result: dict) -> str:
        if "error" in result:
            return str(result["error"])
        for key in ("status", "mode", "mission_id", "checkpoint_mission_id", "id"):
            if result.get(key):
                return f"{key}={result[key]}"
        for key in ("processed", "queued", "actions"):
            if isinstance(result.get(key), list):
                return f"{key}={len(result[key])}"
        return "ok"

    def _compact_action_result(result: dict) -> dict:
        raw = json.dumps(result, ensure_ascii=True, default=str)
        if len(raw) <= 4096:
            return result
        return {
            "truncated": True,
            "keys": sorted(result.keys()),
            "preview": raw[:4096],
        }

    def _remember_action(action_id: str, view: str, result: dict, duration_ms: int) -> None:
        ui_state = load_ui_state(workspace)
        status = "error" if result.get("error") else "ok"
        record = {
            "ts": utc_now(),
            "action_id": action_id,
            "view": view,
            "status": status,
            "duration_ms": duration_ms,
            "summary": _summarize_action_result(result),
            "result": _compact_action_result(result),
        }
        ui_state.setdefault("actions", []).append(record)
        ui_state["actions"] = ui_state["actions"][-50:]
        metrics = ui_state.setdefault("metrics", {"executed": 0, "failed": 0})
        metrics["executed"] = int(metrics.get("executed", 0)) + 1
        if status == "error":
            metrics["failed"] = int(metrics.get("failed", 0)) + 1
        ui_state["last_result"] = record
        save_ui_state(workspace, ui_state)
        append_event(
            workspace,
            "ui_action_executed",
            {"action_id": action_id, "view": view, "status": status, "summary": record["summary"]},
        )

    def _execute_action(form: dict[str, list[str]]) -> dict:
        action_id = form.get("action_id", [""])[0]
        if action_id == "router-next":
            return execute_next_route(workspace)
        if action_id == "router-loop":
            return execute_route_loop(workspace, max_cycles=3, stop_on_elevated=True)
        if action_id == "perf-tune":
            return PerformanceGovernor(workspace).apply()
        if action_id == "mesh-consensus":
            return mesh_consensus(workspace)
        if action_id == "mesh-compact":
            return mesh_compact(workspace)
        if action_id == "worker-run":
            return run_worker_sessions(workspace, max_items=1)
        if action_id == "worker-submit":
            return submit_worker_session(
                workspace,
                form.get("mode", ["builder"])[0],
                form.get("title", ["Worker session"])[0],
                form.get("objective", [""])[0],
                scope=form.get("scope", [""])[0],
            )
        if action_id == "worker-mission":
            return worker_to_mission(
                workspace,
                form.get("session_id", [""])[0],
                route=form.get("route", ["checkpoint"])[0],
            )
        if action_id == "autonomy-run":
            return run_workloads(workspace, max_items=2)
        if action_id == "autonomy-evolve":
            return evolve_ecosystem(workspace, queue_followups=True)
        if action_id == "autonomy-submit":
            return submit_workload(
                workspace,
                form.get("domain", ["code"])[0],
                form.get("title", ["Autonomy workload"])[0],
                form.get("goal", [""])[0],
                context=form.get("context", [""])[0],
            )
        if action_id == "desktop-overlay":
            return desktop_overlay_status(workspace)
        if action_id == "desktop-overlay-cycle":
            return desktop_cycle_overlay(workspace)
        if action_id == "desktop":
            return desktop_snapshot(workspace)
        if action_id == "desktop-files":
            return desktop_tile_explorer(workspace)
        if action_id == "desktop-packages":
            return desktop_package_center(workspace)
        if action_id == "native-os-report":
            return write_native_desktop_report(workspace)
        if action_id == "native-os-blueprint":
            return native_desktop_blueprint(workspace)
        if action_id == "native-os-install-plan":
            return native_installation_plan(workspace, target="vm")
        if action_id == "native-os-app-catalog":
            return native_package_catalog(workspace)
        if action_id == "userspace-alpha-report":
            return write_userspace_alpha_report(workspace)
        if action_id == "userspace-alpha-status":
            return userspace_alpha_report(workspace)
        if action_id == "vfs-mounts":
            return vfs_mount_report(workspace)
        if action_id == "vfs-ls-root":
            return vfs_list(workspace, "/")
        if action_id == "package-manifest":
            return package_manifest(workspace)
        if action_id == "storage-vfs-report":
            return write_storage_vfs_report(workspace)
        if action_id == "storage-vfs-status":
            return storage_mount_report(workspace)
        if action_id == "storage-vfs-snapshot":
            return storage_snapshot(workspace, label="dashboard")
        if action_id == "storage-vfs-verify":
            return storage_verify(workspace)
        if action_id == "storage-vfs-write-demo":
            return storage_write(workspace, "/home/user/dashboard-stage22.txt", "FractalOS Stage22 dashboard persistent write\n")
        return {"error": "unknown_action", "action_id": action_id}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/state":
                body = json.dumps(load_state(workspace), indent=2, ensure_ascii=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/ui-model":
                qs = parse_qs(parsed.query)
                active_view = qs.get("view", ["mission-control"])[0]
                detail_key = qs.get("detail", [None])[0]
                body = json.dumps(build_ui_model(workspace, active_view=active_view, detail_key=detail_key), indent=2, ensure_ascii=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            active_view = "mission-control"
            detail_key = None
            qs = parse_qs(parsed.query)
            if parsed.path.startswith("/view/"):
                active_view = parsed.path.rsplit("/", 1)[-1]
            elif qs.get("view"):
                active_view = qs.get("view", ["mission-control"])[0]
            if qs.get("detail"):
                detail_key = qs.get("detail", [None])[0]
            body = render_dashboard(workspace, active_view=active_view, detail_key=detail_key).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/action":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = parse_qs(raw, keep_blank_values=True)
            view = form.get("view", ["mission-control"])[0]
            action_id = form.get("action_id", [""])[0]
            started = time.perf_counter()
            try:
                result = _execute_action(form)
            except Exception as exc:  # noqa: BLE001
                result = {"error": exc.__class__.__name__, "message": str(exc)}
            duration_ms = int((time.perf_counter() - started) * 1000)
            _remember_action(action_id, view, result, duration_ms)
            self.send_response(303)
            self.send_header("Location", f"/?view={quote(view)}")
            self.end_headers()

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Omega TileMind dashboard running on http://{host}:{port}")
    server.serve_forever()
