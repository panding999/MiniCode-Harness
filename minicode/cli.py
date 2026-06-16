import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from minicode.config import Settings
from minicode.llm.openai_compatible import OpenAICompatibleClient
from minicode.service import AgentService
from minicode.terminal_ui import NewSessionRequest, TerminalUI
from minicode.tools.executors import create_command_executor


@dataclass
class ChatCommandResult:
    should_exit: bool = False
    selected_session: object | None = None


def _safe_print(value, stream=None):
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    text = str(value).encode(encoding, errors="replace").decode(encoding)
    print(text, file=stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minicode", description="Minimal coding agent runtime")
    sub = parser.add_subparsers(dest="command")
    chat = sub.add_parser("chat", help="Start or resume a chat session")
    chat.add_argument("--workspace")
    chat.add_argument("--session")
    chat.add_argument("--message")
    for name in ["trace", "task"]:
        command = sub.add_parser(name, help=f"Show session {name}")
        command.add_argument("--session")
    sub.add_parser("sessions", help="List sessions")
    return parser


def default_session_id(workspace: Path) -> str:
    resolved = str(workspace.resolve())
    digest = hashlib.sha256(resolved.lower().encode("utf-8")).hexdigest()[:10]
    return f"{workspace.resolve().name.lower().replace(' ', '-')}-{digest}"


def new_session_id(workspace: Path) -> str:
    prefix = workspace.resolve().name.lower().replace(" ", "-")
    return f"{prefix}-{uuid4().hex[:10]}"


def normalize_args(args, cwd: Path | None = None):
    workspace = (cwd or Path.cwd()).resolve()
    if args.command is None:
        args.command = "chat"
        args.workspace = str(workspace)
        args.session = new_session_id(workspace)
        args.message = None
    elif args.command == "chat":
        selected = Path(args.workspace).resolve() if args.workspace else workspace
        args.workspace = str(selected)
        args.session = args.session or new_session_id(selected)
    elif args.command in {"task", "trace"}:
        args.session = args.session or new_session_id(workspace)
    return args


def _service() -> AgentService:
    settings = Settings()
    key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not key or not model:
        raise SystemExit("Set LLM_API_KEY and LLM_MODEL before using chat.")
    llm = OpenAICompatibleClient(key, model, os.getenv("LLM_BASE_URL"))
    command_executor = create_command_executor(
        settings.command_executor,
        env_allowlist=settings.command_env_allowlist,
        output_limit=settings.command_output_limit,
        image=settings.docker_image,
        cpus=settings.docker_cpus,
        memory=settings.docker_memory,
        pids_limit=settings.docker_pids_limit,
    )
    return AgentService.create(
        settings.db_url,
        llm,
        settings.max_steps,
        context_char_limit=settings.context_char_limit,
        context_keep_messages=settings.context_keep_messages,
        context_full_tool_results=settings.context_full_tool_results,
        command_executor=command_executor,
    )


def main(argv=None):
    args = normalize_args(build_parser().parse_args(argv))
    settings = Settings()
    if args.command == "chat":
        ui = TerminalUI()
        service = _service()
        workspace = Path(args.workspace)
        approval_provider = getattr(ui, "approve_tool", None)
        if not args.message and approval_provider and hasattr(service, "runtime"):
            service.runtime.dispatcher.approval_provider = approval_provider
        if not args.message:
            ui.show_welcome(os.getenv("LLM_MODEL", "unknown"), workspace, args.session)
        messages = [args.message] if args.message else iter(lambda: ui.console.input("\n[bold]> [/]").strip(), "")
        session_id = args.session
        for message in messages:
            if not message:
                break
            if message.startswith("/"):
                result = _handle_chat_command(message, service, session_id, ui)
                if result.should_exit:
                    break
                if result.selected_session is not None:
                    if isinstance(result.selected_session, NewSessionRequest):
                        session_id = new_session_id(workspace)
                        selected = service.repositories.sessions.get_or_create(session_id, str(workspace.resolve()))
                        ui.show_active_session(os.getenv("LLM_MODEL", "unknown"), selected, [])
                    else:
                        session_id = result.selected_session.id
                        workspace = Path(result.selected_session.workspace)
                        history = service.repositories.messages.list_recent(session_id, 20)
                        ui.show_active_session(os.getenv("LLM_MODEL", "unknown"), result.selected_session, history)
                continue
            try:
                service.run(session_id, workspace, message, event_sink=ui.handle)
            except Exception as exc:
                ui.show_error(exc)
    else:
        from minicode.llm.fake import FakeLLMClient
        service = AgentService.create(settings.db_url, FakeLLMClient([]), settings.max_steps)
        if args.command == "sessions":
            for row in service.repositories.sessions.list():
                _safe_print(f"{row.id}\t{row.workspace}\t{row.updated_at}")
        elif args.command == "task":
            row = service.repositories.tasks.get_current(args.session)
            _safe_print("No task" if row is None else f"{row.status}: {row.goal}\nnext: {row.next_action}\nchanged: {row.files_changed}\ntests: {row.test_result}")
        elif args.command == "trace":
            for row in service.repositories.traces.list_for_session(args.session):
                _safe_print(f"{row.step_number:02d} {row.event_type:12} {row.tool_name or '-':14} {'ok' if row.success else 'fail'} {row.output_summary}")


def _handle_chat_command(message, service, session_id, ui):
    command = message.lower().split()[0]
    if command in {"/exit", "/quit"}:
        return ChatCommandResult(should_exit=True)
    if command == "/help":
        ui.show_help()
    elif command == "/task":
        row = service.repositories.tasks.get_current(session_id)
        ui.console.print("No task" if row is None else f"[bold]{row.status}[/]: {row.goal}\nnext: {row.next_action}\nchanged: {row.files_changed}\ntests: {row.test_result}")
    elif command == "/trace":
        for row in service.repositories.traces.list_for_session(session_id):
            ui.console.print(f"{row.step_number:02d} {row.event_type:12} {row.tool_name or '-':14} {'[green]ok[/]' if row.success else '[red]fail[/]'} {row.output_summary}")
    elif command == "/sessions":
        selected = ui.select_session(service.repositories.sessions.list(), session_id)
        return ChatCommandResult(selected_session=selected)
    else:
        ui.console.print(f"[yellow]未知命令：{message}。输入 /help 查看可用命令。[/]")
    return ChatCommandResult()


if __name__ == "__main__":
    main()
