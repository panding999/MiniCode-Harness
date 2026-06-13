from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    task_status: str | None = None
    next_action: str | None = None

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


@dataclass
class AgentResult:
    text: str
    status: str
    run_id: str


@dataclass
class RuntimeEvent:
    type: str
    step: int = 0
    text: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool | None = None
