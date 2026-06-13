from pathlib import Path

from rich.console import Console

from minicode.terminal_ui import TerminalUI


def test_welcome_panel_contains_model_workspace_and_commands(tmp_path: Path):
    console = Console(record=True, width=100, force_terminal=False)
    ui = TerminalUI(console)

    ui.show_welcome("deepseek-v4-pro", tmp_path, "demo-session")

    output = console.export_text()
    assert "MiniCode Harness" in output
    assert "deepseek-v4-pro" in output
    assert "Workspace" in output
    assert "/help" in output
