from pathlib import Path

from minicode.permissions.policy import PolicyAction, ToolPolicy
from minicode.runtime.models import ToolCall
from minicode.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from minicode.tools.dispatcher import ToolDispatcher
from minicode.tools.registry import ToolRegistry


class RecordingTool(BaseTool):
    name = "recording"
    description = "record execution"
    risk_level = RiskLevel.WRITE
    args_model = object

    def __init__(self):
        self.executed = False

    def execute(self, args, context):
        self.executed = True
        return ToolResult(True, output="executed", output_summary="executed")


def test_policy_allows_normal_tools_and_safe_commands():
    policy = ToolPolicy()

    assert policy.before_tool("read_file", RiskLevel.READ_ONLY, {"path": "a.py"}).action == PolicyAction.ALLOW
    assert policy.before_tool("write_file", RiskLevel.WRITE, {"path": "a.py"}).action == PolicyAction.ALLOW
    assert policy.before_tool("run_command", RiskLevel.EXECUTE, {"argv": ["pytest", "-q"]}).action == PolicyAction.ALLOW


def test_policy_requires_approval_for_sensitive_file_write():
    decision = ToolPolicy().before_tool("write_file", RiskLevel.WRITE, {"path": ".env"})

    assert decision.action == PolicyAction.REQUIRE_APPROVAL
    assert "sensitive" in decision.reason.lower()


def test_policy_requires_approval_for_normal_delete_and_denies_sensitive_delete():
    policy = ToolPolicy()

    normal = policy.before_tool("delete_file", RiskLevel.WRITE, {"path": "notes.txt"})
    sensitive = policy.before_tool("delete_file", RiskLevel.WRITE, {"path": ".env"})

    assert normal.action == PolicyAction.REQUIRE_APPROVAL
    assert sensitive.action == PolicyAction.DENY
    assert "sensitive" in sensitive.reason.lower()


def test_policy_denies_forbidden_command_without_prompting():
    decision = ToolPolicy().before_tool("run_command", RiskLevel.EXECUTE, {"argv": ["rm", "-rf", "."]})

    assert decision.action == PolicyAction.DENY
    assert "allowlisted" in decision.reason.lower()


def test_dispatcher_only_executes_high_risk_tool_after_approval(tmp_path: Path):
    tool = RecordingTool()
    approvals = []
    dispatcher = ToolDispatcher(
        ToolRegistry([tool]),
        policy=ToolPolicy(),
        approval_provider=lambda decision, call: approvals.append((decision, call)) or True,
    )

    result = dispatcher.dispatch(
        ToolCall(id="1", name="recording", arguments={}),
        ToolContext(tmp_path),
    )

    assert result.success
    assert tool.executed
    assert approvals
    assert result.metadata["policy_action"] == "require_approval"
    assert result.metadata["approved"] is True


def test_dispatcher_does_not_execute_rejected_high_risk_tool(tmp_path: Path):
    tool = RecordingTool()
    dispatcher = ToolDispatcher(
        ToolRegistry([tool]),
        policy=ToolPolicy(),
        approval_provider=lambda decision, call: False,
    )

    result = dispatcher.dispatch(
        ToolCall(id="1", name="recording", arguments={}),
        ToolContext(tmp_path),
    )

    assert not result.success
    assert not tool.executed
    assert result.metadata["approved"] is False
