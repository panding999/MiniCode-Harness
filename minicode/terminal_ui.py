from pathlib import Path

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


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
        self.console.print(Panel(
            Group(
                Text("/help       查看命令"),
                Text("/task       查看当前 Task Ledger"),
                Text("/trace      查看当前 Session Trace"),
                Text("/sessions   查看所有 Session"),
                Text("/exit       退出"),
            ),
            title="MiniCode 命令",
            border_style="bright_magenta",
        ))

    def show_error(self, error: Exception):
        self._stop_status()
        self.streaming = False
        self.console.print(Panel(str(error), title="请求失败", border_style="red"))

    def _stop_status(self):
        if self.status:
            self.status.stop()
            self.status = None


def _compact_args(arguments: dict) -> str:
    return " ".join(f"{key}={value!r}" for key, value in arguments.items())[:200]
