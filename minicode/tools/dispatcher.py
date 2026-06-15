from minicode.permissions.policy import PolicyAction, ToolPolicy
from minicode.runtime.models import ToolCall
from minicode.tools.base import ToolContext, ToolResult
from minicode.tools.registry import ToolRegistry


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry, policy=None, approval_provider=None):
        self.registry = registry
        self.policy = policy or ToolPolicy()
        self.approval_provider = approval_provider

    def dispatch(self, call: ToolCall, context: ToolContext) -> ToolResult:
        try:
            tool = self.registry.get(call.name)
            decision = self.policy.before_tool(tool.name, tool.risk_level, call.arguments)
            policy_metadata = {
                "policy_action": decision.action.value,
                "policy_reason": decision.reason,
            }
            if decision.action == PolicyAction.DENY:
                return ToolResult(False, error=decision.reason, output_summary=decision.reason, metadata=policy_metadata)
            if decision.action == PolicyAction.REQUIRE_APPROVAL:
                approved = bool(self.approval_provider and self.approval_provider(decision, call))
                policy_metadata["approved"] = approved
                if not approved:
                    reason = "High-risk operation was rejected by user; it was not executed"
                    return ToolResult(False, error=reason, output_summary=reason, metadata=policy_metadata)
            result = tool.execute(call.arguments, context)
            result.metadata = {**result.metadata, **policy_metadata}
            return result
        except Exception as exc:
            return ToolResult(False, error=str(exc), output_summary=str(exc))
