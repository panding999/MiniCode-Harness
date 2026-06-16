from minicode.tools.base import BaseTool


# 按名称管理工具的注册表。Runtime 不直接导入具体工具，而是通过这里获取 schema 和工具实例。
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
