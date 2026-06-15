from pathlib import Path

from minicode.permissions.guard import PermissionGuard
from minicode.tools.coding import DeleteFileTool, ListFilesTool, ReadFileTool, RunCommandTool, SearchCodeTool, WriteFileTool
from minicode.tools.base import ToolContext


def context(workspace: Path) -> ToolContext:
    return ToolContext(workspace=workspace)


def test_file_tools_work_inside_workspace(tmp_path: Path):
    (tmp_path / "a.py").write_text("answer = 42\n", encoding="utf-8")
    ctx = context(tmp_path)

    assert "a.py" in ListFilesTool().execute({"path": ".", "max_depth": 2}, ctx).output
    assert "answer = 42" in ReadFileTool().execute({"path": "a.py"}, ctx).output
    assert "a.py:1" in SearchCodeTool().execute({"query": "answer"}, ctx).output


def test_guard_rejects_workspace_escape(tmp_path: Path):
    guard = PermissionGuard()
    decision = guard.check_path(tmp_path, "../outside.txt")
    assert not decision.allowed


def test_write_requires_prior_read(tmp_path: Path):
    (tmp_path / "existing.py").write_text("old\n", encoding="utf-8")
    ctx = context(tmp_path)
    result = WriteFileTool().execute({"path": "existing.py", "content": "x = 1\n"}, ctx)
    assert not result.success
    ReadFileTool().execute({"path": "existing.py"}, ctx)
    result = WriteFileTool().execute({"path": "existing.py", "content": "x = 1\n"}, ctx)
    assert result.success


def test_write_can_create_new_file(tmp_path: Path):
    result = WriteFileTool().execute({"path": "new.py", "content": "x = 1\n"}, context(tmp_path))
    assert result.success


def test_run_command_allows_pytest_and_rejects_shell(tmp_path: Path):
    ctx = context(tmp_path)
    ok = RunCommandTool().execute({"argv": ["python", "--version"], "timeout_seconds": 5}, ctx)
    denied = RunCommandTool().execute({"argv": ["rm", "-rf", "."], "timeout_seconds": 5}, ctx)
    assert ok.success and "Python" in ok.output
    assert not denied.success


def test_delete_file_only_deletes_single_workspace_file(tmp_path: Path):
    target = tmp_path / "remove-me.txt"
    target.write_text("temporary", encoding="utf-8")
    directory = tmp_path / "keep-directory"
    directory.mkdir()

    deleted = DeleteFileTool().execute({"path": "remove-me.txt"}, context(tmp_path))
    directory_result = DeleteFileTool().execute({"path": "keep-directory"}, context(tmp_path))
    missing_result = DeleteFileTool().execute({"path": "missing.txt"}, context(tmp_path))

    assert deleted.success
    assert not target.exists()
    assert not directory_result.success
    assert directory.exists()
    assert not missing_result.success
