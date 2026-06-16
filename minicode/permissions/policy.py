from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

from minicode.permissions.guard import PermissionGuard
from minicode.tools.base import RiskLevel


# 风险策略层：工具执行前决定允许、拒绝或需要人工审批。
class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class PolicyDecision:
    action: PolicyAction
    reason: str


class ToolPolicy:
    # 敏感路径规则在这里；路径是否越界的硬检查在 guard.py。
    sensitive_names = {".env", ".env.local", ".env.production", "credentials.json"}
    sensitive_suffixes = {".pem", ".key"}

    def before_tool(self, tool_name: str, risk_level: RiskLevel, arguments: dict) -> PolicyDecision:
        # 只读工具可自动执行；写入、删除和命令会结合工具风险和具体参数分类。
        if risk_level == RiskLevel.READ_ONLY:
            return PolicyDecision(PolicyAction.ALLOW, "Read-only tool")

        if tool_name == "write_file":
            path = PurePosixPath(str(arguments.get("path", "")).replace("\\", "/"))
            if self._is_sensitive(path):
                return PolicyDecision(PolicyAction.REQUIRE_APPROVAL, f"Writing sensitive path: {path}")
            return PolicyDecision(PolicyAction.ALLOW, "Normal workspace write")

        if tool_name == "delete_file":
            path = PurePosixPath(str(arguments.get("path", "")).replace("\\", "/"))
            if self._is_sensitive(path):
                return PolicyDecision(PolicyAction.DENY, f"Deleting sensitive path is forbidden: {path}")
            return PolicyDecision(PolicyAction.REQUIRE_APPROVAL, f"Deleting file requires approval: {path}")

        if tool_name == "run_command":
            command = PermissionGuard().check_command(arguments.get("argv", []))
            action = PolicyAction.ALLOW if command.allowed else PolicyAction.DENY
            return PolicyDecision(action, command.reason or "Safe allowlisted command")

        return PolicyDecision(PolicyAction.REQUIRE_APPROVAL, f"{risk_level.value} tool requires approval")

    def _is_sensitive(self, path: PurePosixPath) -> bool:
        lowered_parts = {part.lower() for part in path.parts}
        return (
            ".git" in lowered_parts
            or path.name.lower() in self.sensitive_names
            or path.suffix.lower() in self.sensitive_suffixes
        )
