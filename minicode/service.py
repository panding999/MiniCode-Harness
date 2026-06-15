from pathlib import Path

from minicode.config import Settings
from minicode.persistence.database import Base, create_database
from minicode.persistence.repositories import Repositories
from minicode.permissions.policy import ToolPolicy
from minicode.runtime.agent_loop import AgentRuntime
from minicode.runtime.compactor import Compactor
from minicode.runtime.context_builder import ContextBuilder
from minicode.tools.coding import DeleteFileTool, ListFilesTool, ReadFileTool, RunCommandTool, SearchCodeTool, WriteFileTool
from minicode.tools.dispatcher import ToolDispatcher
from minicode.tools.executors import LocalRestrictedExecutor
from minicode.tools.registry import ToolRegistry


DEFAULT_PROMPT = """你是 MiniCode，一个最小 Coding Agent。请使用工具获取 Workspace 事实。
不得编造工具结果。修改已有文件前必须先读取。遵守用户明确约束。
目标完成后简洁回答。用户要求只调查时，不得修改文件。"""


def load_core_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "system.md"
    return path.read_text(encoding="utf-8") if path.exists() else DEFAULT_PROMPT


class AgentService:
    def __init__(self, runtime, repositories):
        self.runtime, self.repositories = runtime, repositories

    @classmethod
    def create(
        cls,
        db_url: str,
        llm,
        max_steps=8,
        core_prompt=None,
        context_char_limit=12_000,
        context_keep_messages=12,
        context_full_tool_results=5,
        approval_provider=None,
        command_executor=None,
    ):
        engine, factory = create_database(db_url)
        Base.metadata.create_all(engine)
        repositories = Repositories.create(factory)
        registry = ToolRegistry([
            ListFilesTool(), ReadFileTool(), SearchCodeTool(), WriteFileTool(), DeleteFileTool(),
            RunCommandTool(command_executor or LocalRestrictedExecutor()),
        ])
        runtime = AgentRuntime(
            llm, repositories, ContextBuilder(core_prompt or load_core_prompt()),
            ToolDispatcher(registry, policy=ToolPolicy(), approval_provider=approval_provider), registry,
            Compactor(
                repositories,
                char_limit=context_char_limit,
                keep_recent=context_keep_messages,
                keep_full_tool_results=context_full_tool_results,
            ),
            max_steps=max_steps,
        )
        return cls(runtime, repositories)

    def run(self, session_id: str, workspace: Path, user_input: str, event_sink=None):
        return self.runtime.run(session_id, workspace, user_input, event_sink=event_sink)
