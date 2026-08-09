from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .chrono_mesh import checkpoint_mission, compile_mission_graph
from .future_fabric import execute_future_plan, execute_wave_jobs, orchestrate_jobs
from .perf_governor import PerformanceGovernor
from .ram_memory import OmegaRAM
from .state import load_mission_journal, save_mission_journal
from .state import load_state, utc_now
from ..tilemindfs.store import TileMindFS


def _mesh_root(workspace: Path) -> Path:
    root = workspace / "mesh"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _registry_path(workspace: Path) -> Path:
    return _mesh_root(workspace) / "registry.json"


def _exports_root(workspace: Path) -> Path:
    root = _mesh_root(workspace) / "exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _imports_root(workspace: Path) -> Path:
    root = _mesh_root(workspace) / "imports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_root(workspace: Path) -> Path:
    root = _mesh_root(workspace) / "cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_objects_root(workspace: Path, category: str) -> Path:
    root = _cache_root(workspace) / category
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_registry(workspace: Path) -> dict[str, Any]:
    path = _registry_path(workspace)
    if not path.exists():
        return {"nodes": {}, "relays": [], "inbox": [], "outbox": [], "daemon": {}, "cache": {"entries": {}, "nodes": {}}}
    import json

    registry = json.loads(path.read_text(encoding="utf-8"))
    registry.setdefault("inbox", [])
    registry.setdefault("outbox", [])
    registry.setdefault("daemon", {})
    cache = registry.setdefault("cache", {})
    cache.setdefault("entries", {})
    cache.setdefault("nodes", {})
    return registry


def _save_registry(workspace: Path, registry: dict[str, Any]) -> None:
    import json

    path = _registry_path(workspace)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=True), encoding="utf-8")


def _node_cache_map(registry: dict[str, Any]) -> dict[str, list[str]]:
    cache = registry.setdefault("cache", {})
    cache.setdefault("entries", {})
    return cache.setdefault("nodes", {})


def _cache_entries(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cache = registry.setdefault("cache", {})
    cache.setdefault("nodes", {})
    return cache.setdefault("entries", {})


def _fingerprint_text(parts: list[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def _ram_payload_fingerprint(payload: dict[str, Any]) -> str:
    return _fingerprint_text(
        [
            str(payload.get("key", "")),
            str(payload.get("tableau_id", "")),
            str(payload.get("content", "")),
        ]
    )


def _manifest_fingerprint(manifest: dict[str, Any]) -> str:
    return _fingerprint_text(
        [
            str(manifest.get("manifest_id", "")),
            str(manifest.get("file_sha256", "")),
            str(manifest.get("tile_count", "")),
        ]
    )


def _cache_object_path(workspace: Path, category: str, fingerprint: str) -> Path:
    return _cache_objects_root(workspace, category) / f"{fingerprint}.json"


def _persist_cache_object(workspace: Path, category: str, fingerprint: str, payload: dict[str, Any]) -> None:
    import json

    path = _cache_object_path(workspace, category, fingerprint)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _load_cache_object(workspace: Path, category: str, fingerprint: str) -> dict[str, Any] | None:
    import json

    path = _cache_object_path(workspace, category, fingerprint)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _memory_capsule_fingerprints(capsule: dict[str, Any]) -> dict[str, list[str]]:
    ram = []
    for payload in capsule.get("ram_payloads", []):
        fingerprint = str(payload.get("fingerprint", "")).strip()
        if fingerprint:
            ram.append(fingerprint)
    manifests = []
    for manifest in capsule.get("tile_manifest_snapshots", []):
        fingerprint = str(manifest.get("fingerprint", "")).strip()
        if fingerprint:
            manifests.append(fingerprint)
    return {
        "ram": sorted(set(ram)),
        "manifests": sorted(set(manifests)),
    }


def _register_capsule_cache(
    workspace: Path,
    registry: dict[str, Any],
    capsule: dict[str, Any],
    node_name: str,
) -> dict[str, Any]:
    node_cache = _node_cache_map(registry)
    entries = _cache_entries(registry)
    known = set(node_cache.get(node_name, []))
    persisted_ram = 0
    persisted_manifests = 0

    for payload in capsule.get("ram_payloads", []):
        fingerprint = str(payload.get("fingerprint", "")).strip()
        if not fingerprint:
            continue
        content = str(payload.get("content", ""))
        if content:
            _persist_cache_object(workspace, "ram", fingerprint, payload)
            persisted_ram += 1
        entries[fingerprint] = {
            "category": "ram",
            "key": str(payload.get("key", "")),
            "size_bytes": len(content.encode("utf-8")) if content else int(entries.get(fingerprint, {}).get("size_bytes", 0)),
            "last_seen_at": utc_now(),
        }
        known.add(fingerprint)

    for manifest in capsule.get("tile_manifest_snapshots", []):
        fingerprint = str(manifest.get("fingerprint", "")).strip()
        if not fingerprint:
            continue
        _persist_cache_object(workspace, "manifests", fingerprint, manifest)
        persisted_manifests += 1
        entries[fingerprint] = {
            "category": "manifest",
            "manifest_id": str(manifest.get("manifest_id", "")),
            "size_bytes": len(str(manifest).encode("utf-8")),
            "last_seen_at": utc_now(),
        }
        known.add(fingerprint)

    node_cache[node_name] = sorted(known)
    return {
        "node_name": node_name,
        "known_entries": len(node_cache[node_name]),
        "persisted_ram": persisted_ram,
        "persisted_manifests": persisted_manifests,
    }


def _minimize_memory_capsule_for_target(
    registry: dict[str, Any],
    target_node: str,
    capsule: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    known = set(_node_cache_map(registry).get(target_node, []))
    minimized = dict(capsule)
    minimized_ram = []
    transferred_payloads = 0
    reused_payloads = 0
    transferred_bytes = 0
    reused_bytes = 0

    for payload in capsule.get("ram_payloads", []):
        item = dict(payload)
        fingerprint = str(item.get("fingerprint", "")).strip()
        content = str(item.get("content", ""))
        payload_bytes = len(content.encode("utf-8"))
        if fingerprint and fingerprint in known:
            item.pop("content", None)
            item["cached"] = True
            reused_payloads += 1
            reused_bytes += payload_bytes
        else:
            item["cached"] = False
            transferred_payloads += 1
            transferred_bytes += payload_bytes
        minimized_ram.append(item)
    minimized["ram_payloads"] = minimized_ram

    minimized_manifests = []
    reused_manifests = 0
    for manifest in capsule.get("tile_manifest_snapshots", []):
        item = dict(manifest)
        fingerprint = str(item.get("fingerprint", "")).strip()
        item["cached"] = bool(fingerprint and fingerprint in known)
        if item["cached"]:
            reused_manifests += 1
        minimized_manifests.append(item)
    minimized["tile_manifest_snapshots"] = minimized_manifests

    fingerprints = _memory_capsule_fingerprints(capsule)
    stats = {
        "transferred_payloads": transferred_payloads,
        "reused_payloads": reused_payloads,
        "transferred_payload_bytes": transferred_bytes,
        "reused_payload_bytes": reused_bytes,
        "reused_manifests": reused_manifests,
        "ram_fingerprints": len(fingerprints["ram"]),
        "manifest_fingerprints": len(fingerprints["manifests"]),
    }
    return minimized, stats, fingerprints


def _status_rank(status: str) -> int:
    return {
        "pending": 0,
        "accepted": 1,
        "adopted": 2,
    }.get(str(status), -1)


def _mission_priority_from_payload(payload: dict[str, Any]) -> float:
    mission = payload.get("mission", {})
    graph = mission.get("graph", {})
    nodes = list(graph.get("nodes", []))
    if not nodes:
        return 0.1

    criticalities = [float(node.get("criticality", 0.0)) for node in nodes]
    max_criticality = max(criticalities, default=0.0)
    mean_criticality = sum(criticalities) / max(len(criticalities), 1)
    wave_count = max(1, int(mission.get("causal_projection", {}).get("wave_count", 1)))
    envelope = mission.get("mission_envelope", {})
    risk_level = str(envelope.get("risk_level", "steady"))
    risk_bonus = {"steady": 0.08, "elevated": 0.16, "critical": 0.25}.get(risk_level, 0.05)
    wave_pressure = min(0.2, wave_count / 20.0)
    return round(max_criticality * 0.55 + mean_criticality * 0.25 + risk_bonus + wave_pressure, 4)


def _derive_jobs_from_mission(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if jobs:
        return list(jobs)

    mission = payload.get("mission", {})
    placements = {
        str(item.get("job_id")): item
        for item in mission.get("orchestration", {}).get("placements", [])
        if item.get("job_id") is not None
    }
    nodes = list(mission.get("graph", {}).get("nodes", []))
    if not nodes:
        return []

    def _wave_sort_key(node: dict[str, Any]) -> tuple[int, str]:
        wave_id = str(node.get("wave_id", "wave-999"))
        try:
            wave_index = int(wave_id.split("-")[-1])
        except ValueError:
            wave_index = 999
        return (wave_index, str(node.get("job_id", "")))

    derived_jobs: list[dict[str, Any]] = []
    for node in sorted(nodes, key=_wave_sort_key):
        placement = placements.get(str(node.get("job_id")), {})
        job: dict[str, Any] = {"job_id": str(node.get("job_id", "job"))}
        for key in [
            "title",
            "depends_on",
            "resource_estimate",
            "complexity",
            "risk",
            "vectorizable",
            "matrix_heavy",
            "latency_sensitive",
            "serial",
        ]:
            if key in placement:
                job[key] = placement[key]
            elif key in node:
                job[key] = node[key]
        derived_jobs.append(job)
    return derived_jobs


def _remaining_jobs(jobs: list[dict[str, Any]], completed_jobs: list[str] | set[str]) -> list[dict[str, Any]]:
    completed = {str(item) for item in completed_jobs}
    return [dict(job) for job in jobs if str(job.get("job_id", "")) not in completed]


def _normalize_transferred_dependencies(jobs: list[dict[str, Any]], completed_jobs: list[str] | set[str]) -> list[dict[str, Any]]:
    completed = {str(item) for item in completed_jobs}
    normalized = []
    for job in jobs:
        item = dict(job)
        deps = [str(dep) for dep in item.get("depends_on", []) if str(dep) not in completed]
        if deps:
            item["depends_on"] = deps
        elif "depends_on" in item:
            item["depends_on"] = []
        normalized.append(item)
    return normalized


def _build_memory_capsule(workspace: Path, jobs: list[dict[str, Any]], completed_jobs: list[str] | set[str]) -> dict[str, Any]:
    state = load_state(workspace)
    ram = OmegaRAM(workspace)
    ram_report = ram.report()
    tilemind = TileMindFS(workspace)
    job_ids = {str(job.get("job_id", "")) for job in jobs}
    completed = {str(item) for item in completed_jobs}
    matched_entries = []
    for entry in ram_report.get("top_entries", []):
        key = str(entry.get("key", ""))
        if any(token and token in key for token in job_ids.union(completed)):
            matched_entries.append(entry)
    if not matched_entries:
        matched_entries = ram_report.get("top_entries", [])[:3]
    ram_payloads = []
    for entry in matched_entries[:3]:
        resolved = ram.get(str(entry.get("key", "")))
        if resolved.get("found"):
            payload = {
                "key": resolved["entry"]["key"],
                "source": resolved["entry"]["source"],
                "tier": resolved["entry"]["tier"],
                "tableau_id": resolved["entry"]["tableau_id"],
                "content": resolved["content"],
            }
            payload["fingerprint"] = _ram_payload_fingerprint(payload)
            ram_payloads.append(payload)

    manifest_snapshots = []
    recent_artifacts = state.get("artifacts", [])[-3:]
    for artifact in recent_artifacts:
        for manifest_id in artifact.get("tile_archives", [])[:2]:
            manifest_path = tilemind.manifests_dir / f"{manifest_id}.json"
            if manifest_path.exists():
                import json

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                snapshot = {
                    "manifest_id": manifest["manifest_id"],
                    "source_name": manifest.get("source_name", ""),
                    "tile_count": manifest.get("tile_count", 0),
                    "raw_size": manifest.get("raw_size", 0),
                    "file_sha256": manifest.get("file_sha256", ""),
                }
                snapshot["fingerprint"] = _manifest_fingerprint(snapshot)
                manifest_snapshots.append(snapshot)
    return {
        "captured_at": utc_now(),
        "recent_focus": state.get("memory", {}).get("recent_focus", ""),
        "last_intent_title": state.get("memory", {}).get("last_intent_title", ""),
        "completed_jobs": sorted(completed),
        "tracked_job_ids": sorted(job_ids),
        "ram_context": matched_entries[:5],
        "ram_payloads": ram_payloads,
        "recent_artifacts": recent_artifacts,
        "tile_manifest_snapshots": manifest_snapshots[:4],
    }


def _hydrate_memory_capsule(workspace: Path, mission_record: dict[str, Any]) -> dict[str, Any]:
    capsule = dict(mission_record.get("memory_capsule", {}))
    ram = OmegaRAM(workspace)
    hydrated_ram = []
    for payload in capsule.get("ram_payloads", [])[:5]:
        key = str(payload.get("key", "")).strip()
        fingerprint = str(payload.get("fingerprint", "")).strip()
        content = str(payload.get("content", ""))
        cache_source = "inline"
        if not content and fingerprint:
            cached_payload = _load_cache_object(workspace, "ram", fingerprint)
            if cached_payload:
                content = str(cached_payload.get("content", ""))
                cache_source = "shared-cache"
        if not key:
            continue
        if not content:
            continue
        entry = ram.put_text(key=key, text=content, source=f"mesh-capsule:{mission_record.get('imported_from', 'remote')}:{cache_source}")
        hydrated_ram.append({"key": entry["key"], "tier": entry["tier"], "tableau_id": entry["tableau_id"]})

    replica_root = _mesh_root(workspace) / "replicas" / "manifests"
    replica_root.mkdir(parents=True, exist_ok=True)
    replicated_manifests = []
    for manifest in capsule.get("tile_manifest_snapshots", [])[:6]:
        manifest_id = str(manifest.get("manifest_id", "")).strip()
        if not manifest_id:
            continue
        replica_path = replica_root / f"{manifest_id}.json"
        import json

        replica_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
        replicated_manifests.append(manifest_id)

    return {
        "hydrated_ram": hydrated_ram,
        "replicated_manifests": replicated_manifests,
    }


def mesh_register(workspace: Path, node_name: str, endpoint: str, role: str = "worker") -> dict[str, Any]:
    registry = _load_registry(workspace)
    registry["nodes"][node_name] = {
        "name": node_name,
        "endpoint": endpoint,
        "role": role,
        "availability": "unknown",
        "registered_at": utc_now(),
    }
    _save_registry(workspace, registry)
    return registry["nodes"][node_name]


def _upsert_node(
    workspace: Path,
    node_name: str,
    endpoint: str,
    role: str = "peer",
    capabilities: dict[str, Any] | None = None,
    heartbeat_at: str | None = None,
) -> dict[str, Any]:
    registry = _load_registry(workspace)
    current = dict(registry.get("nodes", {}).get(node_name, {}))
    current.update(
        {
            "name": node_name,
            "endpoint": endpoint,
            "role": role,
            "availability": "online",
            "registered_at": current.get("registered_at") or utc_now(),
            "last_seen_at": utc_now(),
        }
    )
    if capabilities is not None:
        current["capabilities"] = capabilities
    if heartbeat_at is not None:
        current["heartbeat_at"] = heartbeat_at
    registry["nodes"][node_name] = current
    _save_registry(workspace, registry)
    return current


def mesh_descriptor(workspace: Path, endpoint: str | None = None) -> dict[str, Any]:
    state = load_state(workspace)
    status = mesh_status(workspace)
    cache = mesh_cache_report(workspace)
    daemon = mesh_daemon_snapshot(workspace)
    perf = PerformanceGovernor(workspace).report()
    return {
        "name": state["node"]["name"],
        "endpoint": endpoint or "",
        "role": "peer",
        "heartbeat_at": daemon.get("heartbeat_at"),
        "capabilities": {
            "mission_control": True,
            "mesh_push": True,
            "mesh_cycle": True,
            "mesh_cache_consensus": True,
            "gpu_native": False,
            "known_nodes": status["node_count"],
            "cache_entries": cache["entry_count"],
            "cache_nodes": cache["node_count"],
            "risk_level": perf["recommendations"]["risk_level"],
            "recommended_concurrency": perf["recommendations"]["recommended_concurrency"],
            "recommended_resource_limit": perf["recommendations"]["recommended_resource_limit"],
            "stability_index": perf["formulas"]["stability_index"],
        },
    }


def _local_candidate(workspace: Path) -> dict[str, Any]:
    descriptor = mesh_descriptor(workspace)
    return {
        "name": str(descriptor["name"]),
        "endpoint": str(descriptor.get("endpoint", "")),
        "role": "local",
        "availability": "online",
        "heartbeat_at": descriptor.get("heartbeat_at"),
        "capabilities": descriptor.get("capabilities", {}),
        "is_local": True,
    }


def _candidate_score(candidate: dict[str, Any], mission: dict[str, Any]) -> float:
    availability = str(candidate.get("availability", "unknown"))
    availability_score = {"online": 1.0, "unknown": 0.55, "offline": 0.05}.get(availability, 0.2)
    capabilities = candidate.get("capabilities", {}) or {}
    stability = float(capabilities.get("stability_index", 0.35))
    concurrency = float(capabilities.get("recommended_concurrency", 1.0))
    resource_limit = float(capabilities.get("recommended_resource_limit", 4.0))
    risk_level = str(capabilities.get("risk_level", "elevated"))
    risk_penalty = {"low": 0.0, "elevated": 0.08, "critical": 0.2}.get(risk_level, 0.12)
    envelope = mission.get("mission_envelope", {})
    mission_limit = float(envelope.get("recommended_resource_limit", 4.0))
    fit = min(1.0, resource_limit / max(mission_limit, 0.1))
    local_bonus = 0.08 if candidate.get("is_local") else 0.0
    return round(availability_score * 0.4 + stability * 0.25 + min(1.0, concurrency / 8.0) * 0.15 + fit * 0.12 + local_bonus - risk_penalty, 4)


def mesh_rank_targets(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    mission = compile_mission_graph(workspace, jobs)
    registry = _load_registry(workspace)
    candidates = [_local_candidate(workspace)]
    for node in registry.get("nodes", {}).values():
        candidate = dict(node)
        candidate["is_local"] = False
        candidates.append(candidate)

    ranked = []
    for candidate in candidates:
        ranked.append(
            {
                "name": candidate.get("name"),
                "endpoint": candidate.get("endpoint", ""),
                "role": candidate.get("role", "peer"),
                "availability": candidate.get("availability", "unknown"),
                "is_local": bool(candidate.get("is_local")),
                "score": _candidate_score(candidate, mission),
                "capabilities": candidate.get("capabilities", {}),
            }
        )
    ranked.sort(key=lambda item: (-float(item["score"]), not bool(item["is_local"]), str(item["name"])))
    return {"mission": mission, "ranked_targets": ranked}


def mesh_route_mission(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    ranking = mesh_rank_targets(workspace, jobs)
    best = ranking["ranked_targets"][0] if ranking["ranked_targets"] else None
    if not best:
        return {"routed": False, "reason": "no_targets"}

    if best["is_local"]:
        execution = execute_future_plan(workspace, jobs)
        return {
            "routed": True,
            "route": "local",
            "target": best,
            "execution": execution,
            "ranking": ranking["ranked_targets"],
        }

    exported = mesh_export_mission(workspace, jobs, str(best["name"]))
    flushed = mesh_flush_outbox(workspace)
    return {
        "routed": True,
        "route": "remote",
        "target": best,
        "exported": exported,
        "flush": flushed,
        "ranking": ranking["ranked_targets"],
    }


def _rank_targets_for_remaining(workspace: Path, remaining_jobs: list[dict[str, Any]], local_penalty: float = 0.0) -> list[dict[str, Any]]:
    ranking = mesh_rank_targets(workspace, remaining_jobs)
    ranked = []
    for item in ranking["ranked_targets"]:
        candidate = dict(item)
        if candidate.get("is_local"):
            candidate["score"] = round(float(candidate["score"]) - local_penalty, 4)
        ranked.append(candidate)
    ranked.sort(key=lambda item: (-float(item["score"]), not bool(item.get("is_local")), str(item.get("name"))))
    return ranked


def mesh_route_mission_dynamic(workspace: Path, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    orchestration = orchestrate_jobs(workspace, jobs)
    completed: set[str] = set()
    local_executed_waves: list[dict[str, Any]] = []
    migration = None
    stop_reason = "completed"

    for wave in orchestration.get("waves", []):
        remaining_jobs = _remaining_jobs(jobs, completed)
        if not remaining_jobs:
            break

        local_penalty = 0.0
        predicted = wave.get("predicted_state", {})
        if float(predicted.get("stability_index", 1.0)) < 0.24:
            local_penalty += 0.18
        if float(predicted.get("cpu_pressure", 0.0)) > 0.72:
            local_penalty += 0.08
        if float(predicted.get("gpu_pressure", 0.0)) > 0.68:
            local_penalty += 0.08

        ranked = _rank_targets_for_remaining(workspace, remaining_jobs, local_penalty=local_penalty)
        best = ranked[0] if ranked else None
        if not best:
            stop_reason = "stopped because no targets were available"
            break

        if not best.get("is_local"):
            exported = mesh_export_mission(
                workspace,
                remaining_jobs,
                str(best["name"]),
                transfer_context={
                    "origin_node": load_state(workspace)["node"]["name"],
                    "cutover_wave_id": wave["wave_id"],
                    "completed_jobs": sorted(completed),
                    "remaining_jobs": [str(job.get("job_id")) for job in remaining_jobs],
                    "local_executed_waves": [item["wave_id"] for item in local_executed_waves],
                },
            )
            flushed = mesh_flush_outbox(workspace)
            migration = {
                "wave_id": wave["wave_id"],
                "target": best,
                "exported": exported,
                "flush": flushed,
                "remaining_jobs": [str(job.get("job_id")) for job in remaining_jobs],
            }
            stop_reason = f"migrated at {wave['wave_id']} to {best['name']}"
            break

        wave_execution = execute_wave_jobs(wave["jobs"], completed)
        completed = wave_execution["completed_jobs"]
        local_executed_waves.append(
            {
                "wave_id": wave["wave_id"],
                "predicted_state": predicted,
                "results": wave_execution["results"],
                "ranking": ranked,
            }
        )
        if wave_execution["stop_reason"] != "completed":
            stop_reason = f"stopped in {wave['wave_id']}: {wave_execution['stop_reason']}"
            break

    mission_snapshots = []
    completed_projection: set[str] = set()
    for wave in local_executed_waves:
        for result in wave["results"]:
            completed_projection.add(str(result.get("job_id", "")))
        mission_snapshots.append(
            {
                "wave_id": wave["wave_id"],
                "completed_jobs": sorted(completed_projection),
                "predicted_state": wave["predicted_state"],
            }
        )

    return {
        "mode": "dynamic-cluster-routing",
        "executed_waves": local_executed_waves,
        "mission_snapshots": mission_snapshots,
        "migration": migration,
        "stop_reason": stop_reason,
        "orchestration": orchestration,
    }


def mesh_fetch_descriptor(endpoint: str) -> dict[str, Any]:
    target_url = endpoint.rstrip("/") + "/mesh/descriptor"
    with urllib.request.urlopen(target_url, timeout=5) as response:
        raw = response.read().decode("utf-8")
    import json

    return json.loads(raw)


def mesh_announce_to_peer(workspace: Path, endpoint: str, local_endpoint: str) -> dict[str, Any]:
    import json

    payload = json.dumps(mesh_descriptor(workspace, endpoint=local_endpoint), indent=2, ensure_ascii=True).encode("utf-8")
    target_url = endpoint.rstrip("/") + "/mesh/announce"
    request = urllib.request.Request(
        target_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def mesh_discover_peer(workspace: Path, endpoint: str, local_endpoint: str) -> dict[str, Any]:
    remote = mesh_fetch_descriptor(endpoint)
    node = _upsert_node(
        workspace,
        node_name=str(remote.get("name", "peer")),
        endpoint=str(remote.get("endpoint") or endpoint),
        role=str(remote.get("role", "peer")),
        capabilities=remote.get("capabilities"),
        heartbeat_at=remote.get("heartbeat_at"),
    )
    cache_sync = {"node_name": node["name"], "known_entries": 0, "entry_count": 0, "categories": {}}
    try:
        cache_manifest = mesh_fetch_cache_manifest(endpoint)
        cache_sync = _apply_remote_cache_manifest(workspace, str(cache_manifest.get("node_name") or node["name"]), cache_manifest)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    announced = mesh_announce_to_peer(workspace, endpoint, local_endpoint)
    registry = _load_registry(workspace)
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mesh_peer_discovered", "mission_id": "", "peer": node["name"], "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "peer": node,
        "cache_sync": cache_sync,
        "announce": announced,
    }


def mesh_sync_peers(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    synced: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for node_name, node in list(registry.get("nodes", {}).items()):
        endpoint = str(node.get("endpoint", ""))
        if not endpoint:
            continue
        try:
            descriptor = mesh_fetch_descriptor(endpoint)
            updated = _upsert_node(
                workspace,
                node_name=str(descriptor.get("name", node_name)),
                endpoint=str(descriptor.get("endpoint") or endpoint),
                role=str(descriptor.get("role", node.get("role", "peer"))),
                capabilities=descriptor.get("capabilities"),
                heartbeat_at=descriptor.get("heartbeat_at"),
            )
            try:
                cache_manifest = mesh_fetch_cache_manifest(endpoint)
                _apply_remote_cache_manifest(workspace, str(cache_manifest.get("node_name") or updated["name"]), cache_manifest)
            except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
                pass
            synced.append(updated)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            node["availability"] = "offline"
            node["last_error"] = str(exc)
            node["last_checked_at"] = utc_now()
            registry["nodes"][node_name] = node
            failed.append({"name": node_name, "endpoint": endpoint, "reason": str(exc)})
    registry = _load_registry(workspace)
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mesh_peers_synced", "mission_id": "", "peer_count": len(synced), "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {"synced": synced, "failed": failed}


def mesh_status(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    state = load_state(workspace)
    cache_nodes = _node_cache_map(registry)
    cache_entries = _cache_entries(registry)
    return {
        "local_node": state["node"],
        "node_count": len(registry.get("nodes", {})),
        "nodes": list(registry.get("nodes", {}).values()),
        "relays": registry.get("relays", [])[-10:],
        "inbox": registry.get("inbox", [])[-10:],
        "outbox": registry.get("outbox", [])[-10:],
        "cache": {
            "entry_count": len(cache_entries),
            "node_count": len(cache_nodes),
            "per_node": {name: len(items) for name, items in cache_nodes.items()},
        },
    }


def mesh_cache_report(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    cache_nodes = _node_cache_map(registry)
    cache_entries = _cache_entries(registry)
    ram_objects = list(_cache_objects_root(workspace, "ram").glob("*.json"))
    manifest_objects = list(_cache_objects_root(workspace, "manifests").glob("*.json"))
    return {
        "entry_count": len(cache_entries),
        "node_count": len(cache_nodes),
        "per_node": {name: len(items) for name, items in cache_nodes.items()},
        "object_counts": {
            "ram": len(ram_objects),
            "manifests": len(manifest_objects),
        },
        "recent_entries": [
            {
                "fingerprint": fingerprint,
                **entry,
            }
            for fingerprint, entry in list(cache_entries.items())[-10:]
        ],
    }


def mesh_cache_manifest(workspace: Path, limit: int = 256) -> dict[str, Any]:
    registry = _load_registry(workspace)
    state = load_state(workspace)
    entries = _cache_entries(registry)
    fingerprints = sorted(entries.keys())[: max(1, limit)]
    return {
        "node_name": state["node"]["name"],
        "generated_at": utc_now(),
        "entry_count": len(entries),
        "fingerprints": fingerprints,
        "categories": {
            "ram": len([1 for entry in entries.values() if str(entry.get("category")) == "ram"]),
            "manifests": len([1 for entry in entries.values() if str(entry.get("category")) == "manifest"]),
        },
    }


def _apply_remote_cache_manifest(workspace: Path, node_name: str, manifest: dict[str, Any]) -> dict[str, Any]:
    registry = _load_registry(workspace)
    node_cache = _node_cache_map(registry)
    entries = _cache_entries(registry)
    known = sorted(set(str(item) for item in manifest.get("fingerprints", []) if str(item).strip()))
    node_cache[node_name] = known
    for fingerprint in known:
        current = dict(entries.get(fingerprint, {}))
        current["category"] = current.get("category", "remote")
        current["last_seen_at"] = utc_now()
        current["announced_by"] = node_name
        entries[fingerprint] = current
    _save_registry(workspace, registry)
    return {
        "node_name": node_name,
        "known_entries": len(known),
        "entry_count": int(manifest.get("entry_count", len(known))),
        "categories": dict(manifest.get("categories", {})),
    }


def mesh_fetch_cache_manifest(endpoint: str) -> dict[str, Any]:
    target_url = endpoint.rstrip("/") + "/mesh/cache-manifest"
    with urllib.request.urlopen(target_url, timeout=5) as response:
        raw = response.read().decode("utf-8")
    import json

    return json.loads(raw)


def mesh_consensus(workspace: Path, node_name: str | None = None) -> dict[str, Any]:
    registry = _load_registry(workspace)
    nodes = registry.get("nodes", {})
    selected = []
    if node_name:
        node = nodes.get(node_name)
        if node:
            selected.append((node_name, node))
    else:
        selected = list(nodes.items())

    synced: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for current_name, node in selected:
        endpoint = str(node.get("endpoint", "")).strip()
        if not endpoint:
            continue
        try:
            manifest = mesh_fetch_cache_manifest(endpoint)
            applied = _apply_remote_cache_manifest(
                workspace,
                str(manifest.get("node_name") or current_name),
                manifest,
            )
            synced.append(applied)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            failed.append({"name": current_name, "endpoint": endpoint, "reason": str(exc)})

    registry = _load_registry(workspace)
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mesh_cache_consensus", "mission_id": "", "synced": len(synced), "failed": len(failed), "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {"synced": synced, "failed": failed}


def mesh_export_mission(
    workspace: Path,
    jobs: list[dict[str, Any]],
    target_node: str,
    transfer_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = checkpoint_mission(workspace, jobs)
    mission = compile_mission_graph(workspace, jobs)
    export_path = _exports_root(workspace) / f"{checkpoint['mission_id']}_{target_node}.json"
    import json
    registry = _load_registry(workspace)
    local_node_name = load_state(workspace)["node"]["name"]
    base_capsule = _build_memory_capsule(
        workspace,
        jobs,
        (transfer_context or {}).get("completed_jobs", []),
    )
    _register_capsule_cache(workspace, registry, base_capsule, local_node_name)
    memory_capsule, cache_stats, cache_fingerprints = _minimize_memory_capsule_for_target(registry, target_node, base_capsule)

    payload = {
        "mission_id": checkpoint["mission_id"],
        "target_node": target_node,
        "exported_at": utc_now(),
        "jobs": jobs,
        "checkpoint": checkpoint,
        "mission": mission,
        "transfer_context": transfer_context or {},
        "memory_capsule": memory_capsule,
        "cache_stats": cache_stats,
    }
    export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mission_exported", "mission_id": checkpoint["mission_id"], "target_node": target_node, "ts": utc_now()}]
    )[-100:]
    registry["outbox"] = (
        registry.get("outbox", [])
        + [
            {
                "mission_id": checkpoint["mission_id"],
                "target_node": target_node,
                "export_path": str(export_path),
                "status": "queued",
                "queued_at": utc_now(),
                "cache_fingerprints": cache_fingerprints,
                "cache_stats": cache_stats,
            }
        ]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "mission_id": checkpoint["mission_id"],
        "export_path": str(export_path),
        "target_node": target_node,
        "cache_stats": cache_stats,
    }


def _accept_import_payload(workspace: Path, payload: dict[str, Any], import_path: Path) -> dict[str, Any]:
    mission_id = payload["mission_id"]
    mission = payload["mission"]
    jobs = _derive_jobs_from_mission(payload)
    transfer_context = dict(payload.get("transfer_context", {}))
    memory_capsule = dict(payload.get("memory_capsule", {}))
    journal = load_mission_journal(workspace)
    journal["missions"][mission_id] = {
        "last_snapshot": payload["checkpoint"]["snapshot"],
        "mission": mission,
        "execution": payload["checkpoint"],
        "jobs": jobs,
        "transfer_context": transfer_context,
        "memory_capsule": memory_capsule,
        "imported_from": str(import_path),
        "accepted_at": utc_now(),
    }
    journal["events"] = (
        journal.get("events", [])
        + [
            {
                "kind": "mission_accepted_from_mesh",
                "mission_id": mission_id,
                "import_path": str(import_path),
                "ts": utc_now(),
            }
        ]
    )[-100:]
    save_mission_journal(workspace, journal)
    return {"mission_id": mission_id, "accepted": True, "job_count": len(jobs)}


def mesh_import_bundle(workspace: Path, bundle_path: Path, auto_accept: bool = True) -> dict[str, Any]:
    import json

    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    target = _imports_root(workspace) / bundle_path.name
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    registry = _load_registry(workspace)
    cache_registered = _register_capsule_cache(
        workspace,
        registry,
        dict(payload.get("memory_capsule", {})),
        load_state(workspace)["node"]["name"],
    )
    accepted = None
    inbox_entry = {
        "mission_id": payload["mission_id"],
        "source_bundle": str(bundle_path),
        "import_path": str(target),
        "status": "accepted" if auto_accept else "pending",
        "priority": _mission_priority_from_payload(payload),
        "imported_at": utc_now(),
    }
    if auto_accept:
        accepted = _accept_import_payload(workspace, payload, target)
    inbox = [item for item in registry.get("inbox", []) if item.get("mission_id") != payload["mission_id"]]
    registry["inbox"] = (inbox + [inbox_entry])[-100:]
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mission_imported", "mission_id": payload["mission_id"], "from_bundle": str(bundle_path), "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "mission_id": payload["mission_id"],
        "import_path": str(target),
        "auto_accept": auto_accept,
        "accepted": accepted,
        "cache_registered": cache_registered,
    }


def mesh_relay_local(workspace: Path, export_path: Path, target_workspace: Path) -> dict[str, Any]:
    imported = mesh_import_bundle(target_workspace, export_path, auto_accept=True)
    registry = _load_registry(workspace)
    registry["relays"] = (
        registry.get("relays", [])
        + [
            {
                "kind": "mission_relayed_local",
                "mission_id": imported["mission_id"],
                "target_workspace": str(target_workspace),
                "ts": utc_now(),
            }
        ]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "mission_id": imported["mission_id"],
        "export_path": str(export_path),
        "target_workspace": str(target_workspace),
        "import_path": imported["import_path"],
    }


def mesh_push_bundle(endpoint: str, bundle_path: Path) -> dict[str, Any]:
    payload = bundle_path.read_text(encoding="utf-8").encode("utf-8")
    target_url = endpoint.rstrip("/") + "/mesh/push"
    request = urllib.request.Request(
        target_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read().decode("utf-8")
    import json

    return json.loads(raw)


def mesh_flush_outbox(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    delivered: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for item in registry.get("outbox", []):
        if item.get("status") == "delivered":
            continue
        target_node = str(item.get("target_node", ""))
        node = registry.get("nodes", {}).get(target_node)
        if not node or not node.get("endpoint"):
            failed.append({"mission_id": item.get("mission_id"), "target_node": target_node, "reason": "node_unreachable"})
            item["status"] = "waiting-node"
            continue
        try:
            result = mesh_push_bundle(str(node["endpoint"]), Path(str(item["export_path"])))
            item["status"] = "delivered"
            item["delivered_at"] = utc_now()
            item["remote_result"] = result
            cache_nodes = _node_cache_map(registry)
            known = set(cache_nodes.get(target_node, []))
            fingerprints = dict(item.get("cache_fingerprints", {}))
            known.update(str(value) for value in fingerprints.get("ram", []))
            known.update(str(value) for value in fingerprints.get("manifests", []))
            cache_nodes[target_node] = sorted(value for value in known if value)
            delivered.append({"mission_id": item.get("mission_id"), "target_node": target_node, "result": result})
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            item["status"] = "retry"
            item["last_error"] = str(exc)
            item["last_attempt_at"] = utc_now()
            failed.append({"mission_id": item.get("mission_id"), "target_node": target_node, "reason": str(exc)})

    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mesh_outbox_flushed", "delivered": len(delivered), "failed": len(failed), "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "delivered": delivered,
        "failed": failed,
        "outbox": registry.get("outbox", [])[-10:],
    }


def mesh_accept_import(workspace: Path, mission_id: str) -> dict[str, Any]:
    import json

    registry = _load_registry(workspace)
    entry = next((item for item in registry.get("inbox", []) if item["mission_id"] == mission_id), None)
    if not entry:
        return {"mission_id": mission_id, "accepted": False, "reason": "not_found"}
    payload = json.loads(Path(entry["import_path"]).read_text(encoding="utf-8"))
    accepted = _accept_import_payload(workspace, payload, Path(entry["import_path"]))
    entry["status"] = "accepted"
    entry["accepted_at"] = utc_now()
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mission_accepted", "mission_id": mission_id, "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return accepted


def mesh_adopt_import(workspace: Path, mission_id: str) -> dict[str, Any]:
    journal = load_mission_journal(workspace)
    mission_record = journal.get("missions", {}).get(mission_id)
    if not mission_record:
        return {"mission_id": mission_id, "adopted": False, "reason": "mission_not_found"}

    jobs = list(mission_record.get("jobs", []))
    transfer_context = dict(mission_record.get("transfer_context", {}))
    memory_capsule = dict(mission_record.get("memory_capsule", {}))
    if not jobs:
        payload = {
            "mission_id": mission_id,
            "mission": mission_record.get("mission", {}),
            "jobs": mission_record.get("jobs", []),
        }
        jobs = _derive_jobs_from_mission(payload)
        if jobs:
            mission_record["jobs"] = jobs
    if not jobs:
        return {"mission_id": mission_id, "adopted": False, "reason": "jobs_missing"}

    hydrated = _hydrate_memory_capsule(workspace, mission_record)
    registry = _load_registry(workspace)
    _register_capsule_cache(workspace, registry, memory_capsule, load_state(workspace)["node"]["name"])
    _save_registry(workspace, registry)
    inherited_completed = [str(item) for item in transfer_context.get("completed_jobs", [])]
    replayable_jobs = _normalize_transferred_dependencies(_remaining_jobs(jobs, inherited_completed), inherited_completed)
    execution = execute_future_plan(workspace, replayable_jobs)
    completed_jobs = list(inherited_completed)
    if execution.get("mission_snapshots"):
        merged = set(completed_jobs)
        merged.update(execution["mission_snapshots"][-1]["completed_jobs"])
        completed_jobs = sorted(merged)
    mission_record["execution"] = execution
    mission_record["adopted_at"] = utc_now()
    mission_record["last_snapshot"] = {
        "mission_id": mission_id,
        "ts": utc_now(),
        "completed_jobs": completed_jobs,
        "stop_reason": execution["stop_reason"],
        "wave_count": len(execution.get("executed_waves", [])),
        "job_ids": [str(job.get("job_id")) for job in jobs],
    }
    mission_record["transfer_context"] = {
        **transfer_context,
        "completed_jobs": completed_jobs,
        "adopted_by": load_state(workspace)["node"]["name"],
        "adopted_at": utc_now(),
    }
    mission_record["memory_capsule"] = {
        **memory_capsule,
        "completed_jobs": completed_jobs,
        "adopted_by": load_state(workspace)["node"]["name"],
        "adopted_at": utc_now(),
        "hydration": hydrated,
    }
    journal["missions"][mission_id] = mission_record
    journal["events"] = (
        journal.get("events", [])
        + [
            {
                "kind": "mission_adopted_from_mesh",
                "mission_id": mission_id,
                "inherited_completed_jobs": inherited_completed,
                "completed_jobs": completed_jobs,
                "hydrated_ram_keys": [item["key"] for item in hydrated.get("hydrated_ram", [])],
                "ts": utc_now(),
            }
        ]
    )[-100:]
    save_mission_journal(workspace, journal)

    registry = _load_registry(workspace)
    entry = next((item for item in registry.get("inbox", []) if item["mission_id"] == mission_id), None)
    if entry:
        if entry.get("status") == "adopted":
            return {
                "mission_id": mission_id,
                "adopted": True,
                "stop_reason": execution["stop_reason"],
                "completed_jobs": completed_jobs,
            }
        entry["status"] = "adopted"
        entry["adopted_at"] = utc_now()
    registry["relays"] = (
        registry.get("relays", [])
        + [{"kind": "mission_adopted", "mission_id": mission_id, "ts": utc_now()}]
    )[-100:]
    _save_registry(workspace, registry)
    return {
        "mission_id": mission_id,
        "adopted": True,
        "stop_reason": execution["stop_reason"],
        "completed_jobs": completed_jobs,
    }


def mesh_pulse(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    accepted: list[dict[str, Any]] = []
    adopted: list[dict[str, Any]] = []
    seen_missions: set[str] = set()

    inbox = sorted(
        registry.get("inbox", []),
        key=lambda item: (-float(item.get("priority", 0.0)), str(item.get("imported_at", ""))),
    )

    for entry in inbox:
        mission_id = str(entry["mission_id"])
        if mission_id in seen_missions:
            continue
        seen_missions.add(mission_id)
        if entry.get("status") == "pending":
            accepted_result = mesh_accept_import(workspace, mission_id)
            accepted.append(accepted_result)

    registry = _load_registry(workspace)
    seen_missions.clear()
    inbox = sorted(
        registry.get("inbox", []),
        key=lambda item: (-float(item.get("priority", 0.0)), str(item.get("imported_at", ""))),
    )
    for entry in inbox:
        mission_id = str(entry["mission_id"])
        if mission_id in seen_missions:
            continue
        seen_missions.add(mission_id)
        if entry.get("status") == "accepted":
            adopted_result = mesh_adopt_import(workspace, mission_id)
            adopted.append(adopted_result)

    registry = _load_registry(workspace)
    return {
        "local_node": load_state(workspace)["node"]["name"],
        "accepted": accepted,
        "adopted": adopted,
        "inbox": registry.get("inbox", [])[-10:],
    }


def mesh_compact(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    before_inbox = len(registry.get("inbox", []))
    before_relays = len(registry.get("relays", []))

    compacted_inbox: dict[str, dict[str, Any]] = {}
    for entry in registry.get("inbox", []):
        mission_id = str(entry.get("mission_id", ""))
        if not mission_id:
            continue
        current = compacted_inbox.get(mission_id)
        if current is None or _status_rank(entry.get("status", "")) >= _status_rank(current.get("status", "")):
            compacted_inbox[mission_id] = dict(entry)
            if current:
                compacted_inbox[mission_id]["imported_at"] = max(
                    str(current.get("imported_at", "")),
                    str(entry.get("imported_at", "")),
                )
                compacted_inbox[mission_id]["priority"] = max(
                    float(current.get("priority", 0.0)),
                    float(entry.get("priority", 0.0)),
                )
                if current.get("adopted_at") or entry.get("adopted_at"):
                    compacted_inbox[mission_id]["adopted_at"] = max(
                        str(current.get("adopted_at", "")),
                        str(entry.get("adopted_at", "")),
                    )

    compacted_relays: dict[tuple[str, str], dict[str, Any]] = {}
    for relay in registry.get("relays", []):
        kind = str(relay.get("kind", ""))
        mission_id = str(relay.get("mission_id", ""))
        if not kind:
            continue
        key = (kind, mission_id)
        current = compacted_relays.get(key)
        if current is None or str(relay.get("ts", "")) >= str(current.get("ts", "")):
            compacted_relays[key] = dict(relay)

    registry["inbox"] = list(compacted_inbox.values())[-100:]
    registry["relays"] = sorted(compacted_relays.values(), key=lambda item: str(item.get("ts", "")))[-100:]
    _save_registry(workspace, registry)

    journal = load_mission_journal(workspace)
    before_events = len(journal.get("events", []))
    compacted_events: dict[tuple[str, str], dict[str, Any]] = {}
    for event in journal.get("events", []):
        kind = str(event.get("kind", ""))
        mission_id = str(event.get("mission_id", ""))
        if not kind:
            continue
        key = (kind, mission_id)
        current = compacted_events.get(key)
        if current is None or str(event.get("ts", "")) >= str(current.get("ts", "")):
            compacted_events[key] = dict(event)
    journal["events"] = sorted(compacted_events.values(), key=lambda item: str(item.get("ts", "")))[-100:]
    save_mission_journal(workspace, journal)

    return {
        "local_node": load_state(workspace)["node"]["name"],
        "before": {
            "inbox": before_inbox,
            "relays": before_relays,
            "journal_events": before_events,
        },
        "after": {
            "inbox": len(registry.get("inbox", [])),
            "relays": len(registry.get("relays", [])),
            "journal_events": len(journal.get("events", [])),
        },
        "missions": sorted(compacted_inbox.keys()),
    }


def mesh_daemon_snapshot(workspace: Path) -> dict[str, Any]:
    registry = _load_registry(workspace)
    daemon = dict(registry.get("daemon", {}))
    daemon.setdefault("status", "idle")
    daemon.setdefault("cycle_count", 0)
    daemon.setdefault("last_run_at", None)
    daemon.setdefault("heartbeat_at", None)
    daemon.setdefault("last_result", None)
    return daemon


def mesh_daemon_cycle(workspace: Path, compact: bool = True) -> dict[str, Any]:
    outbound = mesh_flush_outbox(workspace)
    pulse = mesh_pulse(workspace)
    compact_result = mesh_compact(workspace) if compact else None
    registry = _load_registry(workspace)
    daemon = dict(registry.get("daemon", {}))
    daemon["status"] = "active"
    daemon["cycle_count"] = int(daemon.get("cycle_count", 0)) + 1
    daemon["last_run_at"] = utc_now()
    daemon["heartbeat_at"] = daemon["last_run_at"]
    daemon["last_result"] = {
        "delivered_count": len(outbound.get("delivered", [])),
        "failed_delivery_count": len(outbound.get("failed", [])),
        "accepted_count": len(pulse.get("accepted", [])),
        "adopted_count": len(pulse.get("adopted", [])),
        "compacted": compact_result,
    }
    registry["daemon"] = daemon
    _save_registry(workspace, registry)
    return {
        "local_node": load_state(workspace)["node"]["name"],
        "daemon": daemon,
        "outbound": outbound,
        "pulse": pulse,
        "compact": compact_result,
    }


def run_mesh_daemon(workspace: Path, interval_s: float = 5.0, max_cycles: int | None = None, compact: bool = True) -> dict[str, Any]:
    cycles = 0
    last_result: dict[str, Any] | None = None
    while True:
        last_result = mesh_daemon_cycle(workspace, compact=compact)
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            break
        time.sleep(max(interval_s, 0.1))
    return last_result or {"local_node": load_state(workspace)["node"]["name"], "daemon": mesh_daemon_snapshot(workspace)}
