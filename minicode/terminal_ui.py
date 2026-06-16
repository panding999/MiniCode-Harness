from dataclasses import dataclass
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import Window
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# Rich/prompt-toolkit 终端适配层。Runtime 发事件，这个类决定如何在交互式 CLI 展示。
@dataclass(frozen=True)
class NewSessionRequest:
    pass


class TerminalUI:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.status = None
        self.streaming = False

    def show_welcome(self, model: str, workspace: Path, session: str):
        info = Table.grid(padding=(0, 2))
        info.add_column(style="bold bright_cyan")
        info.add_column()
        info.add_row("Model", model)
        info.add_row("Workspace", str(workspace.resolve()))
        info.add_row("Session", session)

        commands = Table.grid(padding=(0, 2))
        commands.add_column(style="bold bright_magenta")
        commands.add_column(style="dim")
        commands.add_row("/help", "查看可用命令")
        commands.add_row("/task", "查看当前任务")
        commands.add_row("/trace", "查看执行记录")
        commands.add_row("/rename", "重命名当前 Session")
        commands.add_row("/exit", "退出 MiniCode")

        body = Table.grid(expand=True)
        body.add_column(ratio=1)
        body.add_column(ratio=1)
        body.add_row(info, commands)
        title = Text(" MiniCode Harness ", style="bold bright_cyan")
        subtitle = Text("自研 Coding Agent Runtime", style="dim")
        self.console.print(Panel(body, title=title, subtitle=subtitle, border_style="bright_cyan", padding=(1, 2)))

    def handle(self, event):
        if event.type == "thinking_started":
            self._stop_status()
            self.status = self.console.status(f"[bright_cyan]Step {event.step}  正在思考...[/]", spinner="line")
            self.status.start()
        elif event.type == "tool_started":
            self._stop_status()
            args = _compact_args(event.arguments)
            self.console.print(f"[bold bright_magenta]● {event.tool_name}[/] [dim]{args}[/]")
        elif event.type == "tool_finished":
            marker = "[green]OK[/]" if event.success else "[red]FAIL[/]"
            self.console.print(f"  {marker} [dim]{event.text[:240]}[/]")
        elif event.type == "text_delta":
            self._stop_status()
            if not self.streaming:
                self.console.print("\n[bold bright_cyan]MiniCode[/]")
                self.streaming = True
            self.console.print(event.text, end="", markup=False, highlight=False)
        elif event.type == "run_finished":
            self._stop_status()
            if self.streaming:
                self.console.print()
            self.streaming = False

    def show_help(self):
        commands = Table.grid(padding=(0, 2))
        commands.add_column(style="bold bright_magenta", no_wrap=True)
        commands.add_column()
        commands.add_row("/help", "查看命令")
        commands.add_row("/task", "查看当前 Task Ledger")
        commands.add_row("/trace", "查看当前 Session Trace")
        commands.add_row("/sessions", "查看所有 Session")
        commands.add_row("/rename 名称", "重命名当前 Session")
        commands.add_row("/exit", "退出")
        self.console.print(Panel(
            commands,
            title="MiniCode 命令",
            border_style="bright_magenta",
        ))

    def show_error(self, error: Exception):
        self._stop_status()
        self.streaming = False
        self.console.print(Panel(str(error), title="请求失败", border_style="red"))

    def approve_tool(self, decision, call, input_func=None) -> bool:
        # 注入 ToolDispatcher 的人工审批钩子，仅交互式运行使用。
        visible_arguments = {key: value for key, value in call.arguments.items() if key != "content"}
        body = (
            f"工具: {call.name}\n"
            f"参数: {_compact_args(visible_arguments)}\n"
            f"风险原因: {decision.reason}\n\n"
            "输入 y：批准执行\n"
            "输入 n：拒绝操作并停止本轮"
        )
        self.console.print(Panel(body, title="高风险操作审批", border_style="yellow"))
        reader = input_func or self.console.input
        while True:
            answer = reader("是否允许执行？[y/n]: ").strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                self.console.print("[yellow]用户已拒绝该高风险操作，本轮将停止。[/]")
                return False
            self.console.print("[yellow]请输入 y 批准，或输入 n 拒绝。[/]")

    def show_session_history(self, session, messages):
        self._stop_status()
        self.streaming = False
        pending_tool_pause = False
        for message in messages:
            if message.role not in {"user", "assistant"}:
                continue
            if message.role == "user":
                self.console.print(f"\n[bold]> [/]{message.content}", markup=True, highlight=False)
                continue
            if (getattr(message, "extra_data", {}) or {}).get("tool_calls") and not message.content.strip():
                pending_tool_pause = True
                continue
            if message.content.strip():
                pending_tool_pause = False
                self.console.print("\n[bold bright_cyan]MiniCode[/]")
                self.console.print(message.content, markup=False, highlight=False)
        if pending_tool_pause:
            self.console.print("\n[bold bright_cyan]MiniCode[/]")
            self.console.print("本轮因工具调用失败或安全策略暂停。详情请查看 /trace。", markup=False, highlight=False)

    def show_active_session(self, model: str, session, messages):
        self._stop_status()
        self.streaming = False
        self.console.clear()
        self.show_welcome(model, Path(session.workspace), session.id)
        self.show_session_history(session, messages)

    def select_session(self, sessions, current_session_id: str, input=None, output=None):
        # 全屏 Session 选择器，用于显式恢复历史或创建空白会话。
        entries = [NewSessionRequest(), *sessions]
        selected_index = next(
            (index for index, session in enumerate(entries) if getattr(session, "id", None) == current_session_id),
            0,
        )
        bindings = KeyBindings()

        def content():
            lines = [
                ("bold fg:ansicyan", f" Sessions ({selected_index + 1} of {len(entries)})\n\n"),
            ]
            for index, session in enumerate(entries):
                marker = ">" if index == selected_index else " "
                style = "bold fg:ansiblue" if index == selected_index else ""
                if isinstance(session, NewSessionRequest):
                    lines.append((style, f"{marker} + New session\n"))
                    lines.append(("fg:ansibrightblack", "    在当前 Workspace 创建空白会话\n\n"))
                    continue
                current = "  current" if session.id == current_session_id else ""
                lines.append((style, f"{marker} {session.id}{current}\n"))
                lines.append(("fg:ansibrightblack", f"    {session.workspace}  {session.updated_at}\n\n"))
            lines.append(("fg:ansibrightblack", " Up/Down move  Enter select  Esc return"))
            return FormattedText(lines)

        @bindings.add("up")
        def move_up(event):
            nonlocal selected_index
            selected_index = (selected_index - 1) % len(entries)
            event.app.invalidate()

        @bindings.add("down")
        def move_down(event):
            nonlocal selected_index
            selected_index = (selected_index + 1) % len(entries)
            event.app.invalidate()

        @bindings.add("enter")
        def select(event):
            event.app.exit(result=entries[selected_index])

        @bindings.add("escape", eager=True)
        def cancel(event):
            event.app.exit(result=None)

        app = Application(
            layout=Layout(Window(FormattedTextControl(content), always_hide_cursor=True)),
            key_bindings=bindings,
            full_screen=True,
            input=input,
            output=output,
        )
        return app.run()

    def _stop_status(self):
        if self.status:
            self.status.stop()
            self.status = None


def _compact_args(arguments: dict) -> str:
    return " ".join(f"{key}={value!r}" for key, value in arguments.items())[:200]
