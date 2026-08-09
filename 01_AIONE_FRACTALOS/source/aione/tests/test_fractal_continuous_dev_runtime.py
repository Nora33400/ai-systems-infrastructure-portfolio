from __future__ import annotations

from pathlib import Path

from fractal_dev_runtime.api import ContinuousDevApi
from fractal_dev_runtime.runtime import ContinuousDevRuntime, RuntimeConfig


def make_runtime(tmp_path: Path) -> ContinuousDevRuntime:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n\nTODO: console HUD ecriture.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("# Rules\n\nNo push.\n", encoding="utf-8")
    return ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=tmp_path / "runtime", workspace_root=workspace))


def test_idea_priority_persistence_and_approval(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    runtime.initialize()

    idea = runtime.add_idea("Ajoute cette idée à la liste : inspecteur graphique de mémoire cyclique.", urgency=6, impact=8)
    planned = runtime.plan_idea(idea["id"])
    approved = runtime.approve_idea(idea["id"])

    restarted = ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=tmp_path / "runtime", workspace_root=tmp_path / "workspace"))
    loaded = restarted.get_idea(idea["id"])
    queue = restarted.list_queue(limit=5)

    assert loaded["original_text"] == idea["original_text"]
    assert loaded["status"] == "Ready"
    assert loaded["priority_calculated"] > 0
    assert planned["approval"]["status"] == "Pending"
    assert approved["task"]["status"] == "Ready"
    assert queue[0]["id"] == approved["task"]["id"]


def test_scheduler_runs_urgent_first_and_compacts_memory(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    normal = runtime.add_idea("Documenter un panneau secondaire.", urgency=4, impact=4)
    urgent = runtime.add_idea("Cette idée est urgente : corriger la console HUD inutilisable.", urgency=9, impact=9, tags=["urgent"])
    runtime.approve_idea(normal["id"])
    runtime.approve_idea(urgent["id"])

    before = runtime.list_queue(limit=2)
    result = runtime.run_cycle(max_steps=2)
    memory = runtime.memory_status()

    assert before[0]["idea_id"] == urgent["id"]
    assert len(result["executions"]) == 2
    assert all(execution["status"] == "Completed" for execution in result["executions"])
    assert memory["levels"]["ProjectCompacted"]["summaries"] >= 2
    assert (tmp_path / "runtime" / "agent-workspace" / "sandboxes" / "demo_repo" / "implemented_features.md").exists()


def test_idea_worker_generates_markdown_and_imports_backlog(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    generated = runtime.run_idea_worker(max_documents=10)
    imported = runtime.import_ready_ideas()
    ideas = runtime.list_ideas(limit=10)

    assert generated["generated"]
    assert imported["imported"]
    assert any(idea["source"] == "agent-workspace" for idea in ideas)
    assert not list((tmp_path / "runtime" / "agent-workspace" / "ideas" / "ready").glob("*.md"))


def test_memory_restore_and_runtime_controls(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    idea = runtime.add_idea("Ajouter un test de restauration mémoire.", urgency=7, impact=7)
    runtime.approve_idea(idea["id"])
    result = runtime.run_cycle(max_steps=1)
    memory_id = result["executions"][0]["memory_summary"]["id"]

    restored = runtime.restore_memory(memory_id)
    paused = runtime.pause_runtime(reason="test")
    resumed = runtime.resume_runtime()
    stopped = runtime.stop_after_current()
    emergency = runtime.emergency_stop()

    assert restored["id"] == memory_id
    assert "Task:" in restored["summary"]
    assert paused["state"]["paused"] is True
    assert resumed["state"]["paused"] is False
    assert stopped["state"]["stop_after_current"] is True
    assert emergency["state"]["emergency_stop"] is True


def test_api_auth_message_queue_and_openapi(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    runtime.initialize()
    api = ContinuousDevApi(runtime, api_token="secret")

    unauthorized = api.handle("GET", "/api/v1/runtime/status", headers={})
    openapi = api.handle("GET", "/openapi.json", headers={})
    message = api.handle(
        "POST",
        "/api/v1/message",
        body={"message": "Ajoute cette idée à la liste : connexion entre fenêtres."},
        headers={"X-Fractal-Dev-Token": "secret"},
    )
    queue = api.handle("GET", "/api/v1/queue", headers={"Authorization": "Bearer secret"})

    assert unauthorized.status == 401
    assert openapi.status == 200
    assert message.status == 200
    assert message.body["intent"] == "add_idea"
    assert queue.status == 200


def test_full_vertical_scenario_does_not_modify_user_repo(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    first = runtime.interpret_message("Ajoute cette idée à la liste : créer un inspecteur graphique de la mémoire cyclique.")
    second = runtime.interpret_message("Cette idée est urgente : la console du HUD ne permet toujours pas d'écrire.")
    first_id = first["response"]["idea"]["id"]
    second_id = second["response"]["idea"]["id"]
    runtime.approve_idea(first_id)
    runtime.approve_idea(second_id)

    queue = runtime.list_queue(limit=2)
    cycle = runtime.run_cycle(max_steps=2)
    generated = runtime.run_idea_worker(max_documents=10)
    imported = runtime.import_ready_ideas()
    restarted = ContinuousDevRuntime(RuntimeConfig.build(runtime_dir=tmp_path / "runtime", workspace_root=tmp_path / "workspace"))

    assert queue[0]["idea_id"] == second_id
    assert len(cycle["executions"]) == 2
    assert generated["generated"]
    assert imported["imported"]
    assert restarted.status()["counts"]["ideas"] >= 3
    assert not (tmp_path / "workspace" / "implemented_features.md").exists()
