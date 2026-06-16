import io
import os
from pathlib import Path
from types import SimpleNamespace

from minicode import cli
from minicode.cli import (
    _handle_chat_command,
    _safe_print,
    build_parser,
    default_session_id,
    new_session_id,
    normalize_args,
)
from minicode.terminal_ui import NewSessionRequest


def test_cli_help_lists_core_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert all(command in help_text for command in ["chat", "trace", "task", "sessions"])


def test_no_arguments_defaults_to_chat_in_current_workspace(tmp_path: Path):
    args = normalize_args(build_parser().parse_args([]), tmp_path)
    assert args.command == "chat"
    assert args.workspace == str(tmp_path.resolve())
    assert args.session.startswith(f"{tmp_path.name.lower()}-")
    assert args.session != default_session_id(tmp_path)


def test_task_and_trace_default_to_current_workspace_session(tmp_path: Path):
    for command in ["task", "trace"]:
        args = normalize_args(build_parser().parse_args([command]), tmp_path)
        assert args.session.startswith(f"{tmp_path.name.lower()}-")
        assert args.session != default_session_id(tmp_path)


def test_explicit_session_still_resumes_named_session(tmp_path: Path):
    args = normalize_args(
        build_parser().parse_args(["chat", "--workspace", str(tmp_path), "--session", "existing"]),
        Path("D:/elsewhere"),
    )

    assert args.workspace == str(tmp_path.resolve())
    assert args.session == "existing"


def test_sessions_command_returns_selected_session():
    selected = SimpleNamespace(id="other", workspace="D:/other")
    service = SimpleNamespace(
        repositories=SimpleNamespace(
            sessions=SimpleNamespace(list=lambda: [selected]),
        )
    )
    ui = SimpleNamespace(select_session=lambda sessions, current: selected)

    result = _handle_chat_command("/sessions", service, "current", ui)

    assert result.selected_session is selected
    assert result.should_exit is False


def test_sessions_command_preserves_session_when_selector_is_cancelled():
    service = SimpleNamespace(
        repositories=SimpleNamespace(
            sessions=SimpleNamespace(list=lambda: []),
        )
    )
    ui = SimpleNamespace(select_session=lambda sessions, current: None)

    result = _handle_chat_command("/sessions", service, "current", ui)

    assert result.selected_session is None
    assert result.should_exit is False


def test_rename_command_returns_renamed_session():
    renamed = SimpleNamespace(id="new-name", workspace="D:/workspace")
    calls = []
    service = SimpleNamespace(
        repositories=SimpleNamespace(
            sessions=SimpleNamespace(rename=lambda old, new: calls.append((old, new)) or renamed),
            messages=SimpleNamespace(list_recent=lambda session_id, limit: []),
        )
    )
    ui = SimpleNamespace(console=SimpleNamespace(print=lambda *args, **kwargs: None))

    result = _handle_chat_command("/rename new-name", service, "old-name", ui)

    assert calls == [("old-name", "new-name")]
    assert result.selected_session is renamed


def test_rename_command_requires_new_name():
    printed = []
    service = SimpleNamespace(repositories=SimpleNamespace())
    ui = SimpleNamespace(console=SimpleNamespace(print=lambda value, *args, **kwargs: printed.append(value)))

    result = _handle_chat_command("/rename", service, "old-name", ui)

    assert result.selected_session is None
    assert any("用法" in str(value) for value in printed)


def test_chat_uses_selected_session_and_workspace_for_next_message(monkeypatch, tmp_path: Path):
    selected = SimpleNamespace(id="other", workspace=str(tmp_path / "other"))
    history = [SimpleNamespace(role="user", content="old message")]
    calls = []
    active_session_calls = []
    messages = iter(["/sessions", "hello", ""])

    class FakeConsole:
        def input(self, prompt):
            return next(messages)

        def print(self, *args, **kwargs):
            pass

    fake_ui = SimpleNamespace(
        console=FakeConsole(),
        show_welcome=lambda *args: None,
        select_session=lambda sessions, current: selected,
        show_active_session=lambda model, session, rows: active_session_calls.append((model, session, rows)),
        handle=lambda event: None,
        show_error=lambda error: None,
    )
    fake_service = SimpleNamespace(
        repositories=SimpleNamespace(
            sessions=SimpleNamespace(list=lambda: [selected]),
            messages=SimpleNamespace(list_recent=lambda session_id, limit: history),
        ),
        run=lambda session_id, workspace, message, event_sink: calls.append(
            (session_id, workspace, message)
        ),
    )
    monkeypatch.setattr(cli, "TerminalUI", lambda: fake_ui)
    monkeypatch.setattr(cli, "_service", lambda: fake_service)

    cli.main(["chat", "--workspace", str(tmp_path), "--session", "current"])

    assert calls == [("other", Path(selected.workspace), "hello")]
    assert active_session_calls == [(os.getenv("LLM_MODEL", "unknown"), selected, history)]


def test_chat_creates_empty_session_in_current_workspace(monkeypatch, tmp_path: Path):
    messages = iter(["/sessions", "hello", ""])
    created = []
    active_session_calls = []
    calls = []

    class FakeConsole:
        def input(self, prompt):
            return next(messages)

        def print(self, *args, **kwargs):
            pass

    sessions = SimpleNamespace(
        list=lambda: [],
        get_or_create=lambda session_id, workspace: created.append((session_id, workspace))
        or SimpleNamespace(id=session_id, workspace=workspace),
    )
    fake_ui = SimpleNamespace(
        console=FakeConsole(),
        show_welcome=lambda *args: None,
        select_session=lambda rows, current: NewSessionRequest(),
        show_active_session=lambda model, session, rows: active_session_calls.append((model, session, rows)),
        handle=lambda event: None,
        show_error=lambda error: None,
    )
    fake_service = SimpleNamespace(
        repositories=SimpleNamespace(sessions=sessions),
        run=lambda session_id, workspace, message, event_sink: calls.append(
            (session_id, workspace, message)
        ),
    )
    monkeypatch.setattr(cli, "TerminalUI", lambda: fake_ui)
    monkeypatch.setattr(cli, "_service", lambda: fake_service)

    cli.main(["chat", "--workspace", str(tmp_path), "--session", "current"])

    assert len(created) == 1
    assert created[0][1] == str(tmp_path.resolve())
    assert created[0][0] != "current"
    assert active_session_calls[0][1].id == created[0][0]
    assert active_session_calls[0][2] == []
    assert calls == [(created[0][0], tmp_path.resolve(), "hello")]


def test_new_session_id_is_unique_and_keeps_workspace_prefix(tmp_path: Path):
    first = new_session_id(tmp_path)
    second = new_session_id(tmp_path)

    assert first.startswith(f"{tmp_path.name.lower()}-")
    assert first != second


def test_safe_print_does_not_crash_on_gbk_terminal_with_unicode():
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="gbk", errors="strict")

    _safe_print("trace contains ✅", stream=stream)
    stream.flush()

    assert buffer.getvalue().decode("gbk") == "trace contains ?\r\n"
