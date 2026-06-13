from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""


class PermissionGuard:
    allowed_commands = {"python", "python3", "pytest", "git"}

    def resolve_path(self, workspace: Path, requested: str) -> Path:
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
        if not argv or argv[0] not in self.allowed_commands:
            return PermissionDecision(False, "Command is not allowlisted")
        if any(token in {"|", ">", ">>", "<", "&&", ";"} for token in argv):
            return PermissionDecision(False, "Shell operators are forbidden")
        if argv[0] == "git" and (len(argv) < 2 or argv[1] not in {"status", "diff"}):
            return PermissionDecision(False, "Only git status and git diff are allowed")
        if argv[0] in {"python", "python3"} and argv[1:] not in [["--version"], ["-m", "pytest"], ["-m", "pytest", "-q"]]:
            return PermissionDecision(False, "Python is limited to version checks and pytest")
        return PermissionDecision(True)
