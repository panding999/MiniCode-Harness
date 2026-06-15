from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from minicode.terminal_ui import NewSessionRequest, TerminalUI


def test_welcome_panel_contains_model_workspace_and_commands(tmp_path: Path):
    console = Console(record=True, width=100, force_terminal=False)
    ui = TerminalUI(console)

    ui.show_welcome("deepseek-v4-pro", tmp_path, "demo-session")

    output = console.export_text()
    assert "MiniCode Harness" in output
    assert "deepseek-v4-pro" in output
    assert "Workspace" in output
    assert "/help" in output


def test_session_selector_selects_highlighted_session():
    sessions = [
        SimpleNamespace(id="newest", workspace="D:/newest", updated_at="now"),
        SimpleNamespace(id="older", workspace="D:/older", updated_at="before"),
    ]
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = TerminalUI().select_session(
            sessions,
            current_session_id="newest",
            input=pipe_input,
            output=DummyOutput(),
        )

    assert selected.id == "older"


def test_session_selector_returns_none_when_escape_is_pressed():
    sessions = [SimpleNamespace(id="current", workspace="D:/current", updated_at="now")]
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        selected = TerminalUI().select_session(
            sessions,
            current_session_id="current",
            input=pipe_input,
            output=DummyOutput(),
        )

    assert selected is None


def test_session_selector_can_create_new_session():
    sessions = [SimpleNamespace(id="current", workspace="D:/current", updated_at="now")]
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[A\r")
        selected = TerminalUI().select_session(
            sessions,
            current_session_id="current",
            input=pipe_input,
            output=DummyOutput(),
        )

    assert isinstance(selected, NewSessionRequest)


def test_empty_session_selector_still_offers_new_session():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = TerminalUI().select_session(
            [],
            current_session_id="current",
            input=pipe_input,
            output=DummyOutput(),
        )

    assert isinstance(selected, NewSessionRequest)


def test_show_session_history_replays_only_conversation_in_normal_chat_style(tmp_path: Path):
    console = Console(record=True, width=100, force_terminal=False)
    ui = TerminalUI(console)
    session = SimpleNamespace(id="restored", workspace=str(tmp_path))
    messages = [
        SimpleNamespace(role="user", content="original question"),
        SimpleNamespace(role="tool", content="secret tool output"),
        SimpleNamespace(role="assistant", content=""),
        SimpleNamespace(role="assistant", content="original answer"),
    ]

    ui.show_session_history(session, messages)

    output = console.export_text()
    assert "> original question" in output
    assert "MiniCode\noriginal answer" in output
    assert "original answer" in output
    assert "secret tool output" not in output
    assert "restored" not in output
    assert str(tmp_path) not in output
    assert "Restored Session" not in output


def test_show_active_session_redraws_normal_interface_with_new_label(tmp_path: Path):
    console = Console(record=True, width=100, force_terminal=False)
    ui = TerminalUI(console)
    session = SimpleNamespace(id="new-session", workspace=str(tmp_path))
    messages = [SimpleNamespace(role="assistant", content="previous answer")]

    ui.show_active_session("deepseek-v4-pro", session, messages)

    output = console.export_text()
    assert "MiniCode Harness" in output
    assert "new-session" in output
    assert "Workspace" in output
    assert "previous answer" in output
