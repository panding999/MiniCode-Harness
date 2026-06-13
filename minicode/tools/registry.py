from minicode.tools.base import BaseTool


class ToolRegistry:
    def __init__(self, tools: list[BaseTool]):
        self._tools = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool: {tool.name}")
            self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]
