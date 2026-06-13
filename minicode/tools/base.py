from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass
class ToolContext:
    workspace: Path
    files_read: set[str] = field(default_factory=set)


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    output_summary: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


class BaseTool:
    name: str
    description: str
    risk_level: RiskLevel
    args_model: type[BaseModel]

    def schema(self) -> dict:
        parameters = self.args_model.model_json_schema() if hasattr(self.args_model, "model_json_schema") else self.args_model.schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }

    def execute(self, args: dict, context: ToolContext) -> ToolResult:
        raise NotImplementedError
