from pathlib import Path

from minicode.llm.fake import FakeLLMClient
from minicode.runtime.models import LLMResponse, ToolCall
from minicode.service import AgentService


def test_agent_tool_loop_and_persistence(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello\n", encoding="utf-8")
    db_url = f"sqlite:///{tmp_path / 'state.db'}"
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[ToolCall(id="1", name="read_file", arguments={"path": "note.txt"})]),
        LLMResponse(text="Found hello", task_status="paused", next_action="continue later"),
    ])
    service = AgentService.create(db_url=db_url, llm=llm, max_steps=4)

    result = service.run("demo", workspace, "inspect note")

    assert result.text == "Found hello"
    assert result.status == "paused"
    assert service.repositories.tasks.get_current("demo").files_read == ["note.txt"]
    assert len(service.repositories.traces.list_for_session("demo")) >= 2
    second_request = llm.requests[1]
    assert any(message.get("tool_calls") for message in second_request)
    assert any(message.get("role") == "tool" and message.get("tool_call_id") == "1" for message in second_request)

    reopened = AgentService.create(db_url=db_url, llm=FakeLLMClient([LLMResponse(text="resumed")]))
    assert reopened.repositories.sessions.get("demo").workspace == str(workspace.resolve())
    assert reopened.repositories.tasks.get_current("demo").next_action == "continue later"


def test_max_steps_pauses_task(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repeated = LLMResponse(tool_calls=[ToolCall(id="1", name="list_files", arguments={"path": "."})])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=FakeLLMClient([repeated, repeated, repeated]),
        max_steps=2,
    )
    result = service.run("demo", workspace, "loop")
    assert result.status == "paused"
    assert "maximum" in result.text.lower()


def test_follow_up_after_completed_task_recalls_previous_ledger(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_url = f"sqlite:///{tmp_path / 'state.db'}"
    first = AgentService.create(db_url=db_url, llm=FakeLLMClient([LLMResponse(text="done")]))
    first.run("demo", workspace, "fix the original bug")

    llm = FakeLLMClient([LLMResponse(text="summary")])
    second = AgentService.create(db_url=db_url, llm=llm)
    second.run("demo", workspace, "what changed?")

    system_prompt = llm.requests[0][0]["content"]
    assert "fix the original bug" in system_prompt


def test_runtime_emits_thinking_tool_and_final_events(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    events = []
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[ToolCall(id="1", name="list_files", arguments={"path": "."})]),
        LLMResponse(text="done"),
    ])
    service = AgentService.create(db_url=f"sqlite:///{tmp_path / 'state.db'}", llm=llm)

    service.run("demo", workspace, "inspect", event_sink=events.append)

    assert [event.type for event in events] == [
        "thinking_started", "tool_started", "tool_finished",
        "thinking_started", "text_delta", "run_finished",
    ]
    assert events[1].tool_name == "list_files"
    assert events[4].text == "done"


def test_runtime_uses_summary_and_recent_messages_after_compaction(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    llm = FakeLLMClient([LLMResponse(text="done")])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=llm,
        context_char_limit=100,
        context_keep_messages=2,
    )
    service.repositories.sessions.get_or_create("demo", str(workspace.resolve()))
    service.repositories.messages.add("demo", "user", "旧目标：" + "A" * 80)
    service.repositories.messages.add("demo", "assistant", "旧回答：" + "B" * 80)

    service.run("demo", workspace, "当前问题")

    request = llm.requests[0]
    system = request[0]["content"]
    assert "旧目标" in system
    assert "compacted-through" not in system
    assert all("旧目标" not in message.get("content", "") for message in request[1:])
    assert request[-1]["content"] == "当前问题"
