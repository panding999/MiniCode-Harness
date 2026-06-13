from minicode.runtime.models import ToolCall
from minicode.tools.base import ToolContext, ToolResult
from minicode.tools.registry import ToolRegistry


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def dispatch(self, call: ToolCall, context: ToolContext) -> ToolResult:
        try:
            return self.registry.get(call.name).execute(call.arguments, context)
        except Exception as exc:
            return ToolResult(False, error=str(exc), output_summary=str(exc))
