from pathlib import Path

from minicode.cli import build_parser, default_session_id, normalize_args


def test_cli_help_lists_core_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert all(command in help_text for command in ["chat", "trace", "task", "sessions"])


def test_no_arguments_defaults_to_chat_in_current_workspace(tmp_path: Path):
    args = normalize_args(build_parser().parse_args([]), tmp_path)
    assert args.command == "chat"
    assert args.workspace == str(tmp_path.resolve())
    assert args.session == default_session_id(tmp_path)


def test_task_and_trace_default_to_current_workspace_session(tmp_path: Path):
    for command in ["task", "trace"]:
        args = normalize_args(build_parser().parse_args([command]), tmp_path)
        assert args.session == default_session_id(tmp_path)
