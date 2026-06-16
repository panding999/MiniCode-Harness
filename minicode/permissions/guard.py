from dataclasses import dataclass
from pathlib import Path


# 底层硬边界：路径限制和命令白名单都在这里。
# 如果要找命令白名单，看下面的 allowed_commands。
@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""


class PermissionGuard:
    # run_command 启动子进程前使用的命令白名单。
    allowed_commands = {"python", "python3", "pytest", "git"}

    def resolve_path(self, workspace: Path, requested: str) -> Path:
        # 先解析真实路径，再检查是否仍在 Workspace 内，阻止 ../ 路径穿越。
        root = workspace.resolve()
        candidate = (root / requested).resolve()
        if candidate != root and root not in candidate.parents:
            raise PermissionError("Path is outside the workspace")
        return candidate

    def check_path(self, workspace: Path, requested: str) -> PermissionDecision:
        try:
            self.resolve_path(workspace, requested)
            return PermissionDecision(True)
        except (OSError, PermissionError) as exc:
            return PermissionDecision(False, str(exc))

    def check_command(self, argv: list[str]) -> PermissionDecision:
        # 这里不会打开 shell，只校验 argv 数组本身。
        if not argv or argv[0] not in self.allowed_commands:
            return PermissionDecision(False, "Command is not allowlisted")
        if any(token in {"|", ">", ">>", "<", "&&", ";"} for token in argv):
            return PermissionDecision(False, "Shell operators are forbidden")
        if argv[0] == "git" and (len(argv) < 2 or argv[1] not in {"status", "diff"}):
            return PermissionDecision(False, "Only git status and git diff are allowed")
        if argv[0] in {"python", "python3"}:
            if argv[1:] == ["--version"]:
                return PermissionDecision(True)
            if len(argv) >= 3 and argv[1:3] == ["-m", "pytest"] and _is_safe_pytest_args(argv[3:]):
                return PermissionDecision(True)
            return PermissionDecision(False, "Python is limited to version checks and pytest")
        if argv[0] == "pytest" and not _is_safe_pytest_args(argv[1:]):
            return PermissionDecision(False, "pytest arguments are not allowlisted")
        return PermissionDecision(True)


def _is_safe_pytest_args(args: list[str]) -> bool:
    # 允许常见 pytest flag 和 Workspace 内相对测试路径；仍拒绝 shell、绝对路径和父目录穿越。
    allowed_flags = {
        "-q", "-v", "-x", "-s",
        "--maxfail=1", "--tb=short", "--tb=long", "--tb=auto", "--disable-warnings",
    }
    for arg in args:
        normalized = arg.replace("\\", "/")
        if arg in allowed_flags:
            continue
        if normalized.startswith("-k") or normalized.startswith("-m"):
            return False
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            return False
        if any(part in {"", "."} for part in normalized.split("/") if normalized != "."):
            return False
    return True
