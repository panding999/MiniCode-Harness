from pathlib import Path

import pytest

from minicode.llm.fake import FakeLLMClient
from minicode.runtime.models import LLMResponse, ToolCall
from minicode.service import AgentService


def test_unhandled_runtime_exception_closes_run_task_and_trace(tmp_path: Path):
    class FailingLLM:
        def complete(self, messages, tools, on_text_delta=None):
            raise RuntimeError("LLM service unavailable")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=FailingLLM(),
    )

    with pytest.raises(RuntimeError, match="LLM service unavailable"):
        service.run("failure-demo", workspace, "inspect failure")

    task = service.repositories.tasks.get_current("failure-demo")
    run = service.repositories.traces.latest_run("failure-demo")
    traces = service.repositories.traces.list_for_session("failure-demo")

    assert task.status == "failed"
    assert task.last_error == "LLM service unavailable"
    assert run.status == "failed"
    assert run.finished_at is not None
    assert traces[-1].event_type == "run_failed"
    assert traces[-1].error == "LLM service unavailable"


def test_high_risk_tool_rejection_is_persisted_in_policy_trace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[
            ToolCall(id="1", name="write_file", arguments={"path": ".env", "content": "SECRET=value"}),
        ]),
        LLMResponse(text="Sensitive write was rejected"),
    ])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=llm,
    )

    service.run("policy-demo", workspace, "write sensitive config")

    traces = service.repositories.traces.list_for_session("policy-demo")
    policy_trace = next(trace for trace in traces if trace.event_type == "policy_decision")
    assert not (workspace / ".env").exists()
    assert policy_trace.arguments["action"] == "require_approval"
    assert policy_trace.arguments["approved"] is False
    assert policy_trace.success is False


def test_rejected_approval_stops_run_before_model_can_try_a_bypass(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[
            ToolCall(id="1", name="write_file", arguments={"path": ".env", "content": "SECRET=value"}),
        ]),
        LLMResponse(tool_calls=[
            ToolCall(id="2", name="run_command", arguments={"argv": ["python", "-c", "bypass"]}),
        ]),
    ])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=llm,
    )

    result = service.run("rejection-stops-run", workspace, "write sensitive config")

    assert result.status == "paused"
    assert "rejected by user" in result.text.lower()
    assert len(llm.requests) == 1
    assert not (workspace / ".env").exists()
    traces = service.repositories.traces.list_for_session("rejection-stops-run")
    assert [trace.event_type for trace in traces][-1] == "paused"


def test_policy_denied_sensitive_delete_stops_run_before_model_can_try_a_bypass(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / ".env"
    target.write_text("SECRET=value", encoding="utf-8")
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[
            ToolCall(id="1", name="delete_file", arguments={"path": ".env"}),
        ]),
        LLMResponse(tool_calls=[
            ToolCall(id="2", name="run_command", arguments={"argv": ["python", "-c", "bypass"]}),
        ]),
    ])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=llm,
    )

    result = service.run("denied-delete-stops-run", workspace, "delete sensitive config")

    assert result.status == "paused"
    assert "denied by policy" in result.text.lower()
    assert len(llm.requests) == 1
    assert target.exists()


def test_normal_file_delete_only_happens_after_user_approval(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "temporary.txt"
    target.write_text("temporary", encoding="utf-8")
    llm = FakeLLMClient([
        LLMResponse(tool_calls=[
            ToolCall(id="1", name="delete_file", arguments={"path": "temporary.txt"}),
        ]),
        LLMResponse(text="File deleted"),
    ])
    service = AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=llm,
        approval_provider=lambda decision, call: True,
    )

    result = service.run("approved-delete", workspace, "delete temporary file")

    assert result.status == "completed"
    assert not target.exists()
    policy_trace = next(
        trace for trace in service.repositories.traces.list_for_session("approved-delete")
        if trace.event_type == "policy_decision"
    )
    assert policy_trace.arguments["action"] == "require_approval"
    assert policy_trace.arguments["approved"] is True
