import re
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field

from minicode.permissions.guard import PermissionGuard
from minicode.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from minicode.tools.executors import LocalRestrictedExecutor


def _result(start: float, success: bool, output: str = "", error: str = "", metadata: dict | None = None):
    summary = (output or error)[:500]
    return ToolResult(success, output, summary, error, metadata or {}, int((time.monotonic() - start) * 1000))


def _validate(model, args):
    return model.model_validate(args) if hasattr(model, "model_validate") else model.parse_obj(args)


class ListFilesArgs(BaseModel):
    path: str = "."
    max_depth: int = Field(2, ge=0, le=10)


class ListFilesTool(BaseTool):
    name, description, risk_level, args_model = "list_files", "List workspace files", RiskLevel.READ_ONLY, ListFilesArgs

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            root = PermissionGuard().resolve_path(context.workspace, data.path)
            rows = []
            for path in sorted(root.rglob("*")):
                if len(path.relative_to(root).parts) <= data.max_depth:
                    rows.append(path.relative_to(context.workspace.resolve()).as_posix() + ("/" if path.is_dir() else ""))
            return _result(start, True, "\n".join(rows))
        except Exception as exc:
            return _result(start, False, error=str(exc))


class ReadFileArgs(BaseModel):
    path: str
    start_line: int = Field(1, ge=1)
    end_line: int | None = Field(None, ge=1)


class ReadFileTool(BaseTool):
    name, description, risk_level, args_model = "read_file", "Read a workspace file by line range", RiskLevel.READ_ONLY, ReadFileArgs

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            path = PermissionGuard().resolve_path(context.workspace, data.path)
            lines = path.read_text(encoding="utf-8").splitlines()
            end = data.end_line or min(len(lines), data.start_line + 299)
            output = "\n".join(f"{i}: {lines[i-1]}" for i in range(data.start_line, min(end, len(lines)) + 1))[:20000]
            context.files_read.add(Path(data.path).as_posix())
            return _result(start, True, output, metadata={"path": Path(data.path).as_posix()})
        except Exception as exc:
            return _result(start, False, error=str(exc))


class SearchCodeArgs(BaseModel):
    query: str
    path: str = "."
    regex: bool = False


class SearchCodeTool(BaseTool):
    name, description, risk_level, args_model = "search_code", "Search text in workspace files", RiskLevel.READ_ONLY, SearchCodeArgs

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            root = PermissionGuard().resolve_path(context.workspace, data.path)
            pattern = re.compile(data.query if data.regex else re.escape(data.query))
            rows = []
            files = [root] if root.is_file() else root.rglob("*")
            for path in files:
                if not path.is_file():
                    continue
                try:
                    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                        if pattern.search(line):
                            rows.append(f"{path.relative_to(context.workspace.resolve()).as_posix()}:{number}: {line[:300]}")
                            if len(rows) >= 100:
                                return _result(start, True, "\n".join(rows))
                except (UnicodeDecodeError, OSError):
                    continue
            return _result(start, True, "\n".join(rows))
        except Exception as exc:
            return _result(start, False, error=str(exc))


class WriteFileArgs(BaseModel):
    path: str
    content: str


class WriteFileTool(BaseTool):
    name, description, risk_level, args_model = "write_file", "Write a workspace file after it has been read", RiskLevel.WRITE, WriteFileArgs

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            relative = Path(data.path).as_posix()
            path = PermissionGuard().resolve_path(context.workspace, data.path)
            if path.exists() and relative not in context.files_read:
                return _result(start, False, error="File must be read before writing")
            before = path.read_text(encoding="utf-8") if path.exists() else ""
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data.content, encoding="utf-8")
            return _result(start, True, f"Wrote {relative}", metadata={"path": relative, "before_chars": len(before), "after_chars": len(data.content)})
        except Exception as exc:
            return _result(start, False, error=str(exc))


class DeleteFileArgs(BaseModel):
    path: str


class DeleteFileTool(BaseTool):
    name, description, risk_level, args_model = "delete_file", "Delete one workspace file", RiskLevel.WRITE, DeleteFileArgs

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            relative = Path(data.path).as_posix()
            path = PermissionGuard().resolve_path(context.workspace, data.path)
            if not path.exists():
                return _result(start, False, error="File does not exist")
            if not path.is_file():
                return _result(start, False, error="Only individual files can be deleted")
            path.unlink()
            return _result(start, True, f"Deleted {relative}", metadata={"path": relative})
        except Exception as exc:
            return _result(start, False, error=str(exc))


class RunCommandArgs(BaseModel):
    argv: list[str]
    timeout_seconds: int = Field(30, ge=1, le=120)


class RunCommandTool(BaseTool):
    name, description, risk_level, args_model = "run_command", "Run an allowlisted command without a shell", RiskLevel.EXECUTE, RunCommandArgs

    def __init__(self, executor=None):
        self.executor = executor or LocalRestrictedExecutor()

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            data = _validate(self.args_model, args)
            decision = PermissionGuard().check_command(data.argv)
            if not decision.allowed:
                return _result(start, False, error=decision.reason)
            completed = self.executor.execute(data.argv, context.workspace, data.timeout_seconds)
            return _result(
                start,
                completed.returncode == 0,
                completed.output,
                "" if completed.returncode == 0 else f"exit code {completed.returncode}",
                {"argv": data.argv, "exit_code": completed.returncode, "output_truncated": completed.truncated},
            )
        except subprocess.TimeoutExpired:
            return _result(start, False, error="Command timed out")
        except Exception as exc:
            return _result(start, False, error=str(exc))
