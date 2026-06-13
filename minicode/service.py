from pathlib import Path

from minicode.config import Settings
from minicode.persistence.database import Base, create_database
from minicode.persistence.repositories import Repositories
from minicode.runtime.agent_loop import AgentRuntime
from minicode.runtime.compactor import Compactor
from minicode.runtime.context_builder import ContextBuilder
from minicode.tools.coding import ListFilesTool, ReadFileTool, RunCommandTool, SearchCodeTool, WriteFileTool
from minicode.tools.dispatcher import ToolDispatcher
from minicode.tools.registry import ToolRegistry


DEFAULT_PROMPT = """You are MiniCode, a coding agent. Use tools for workspace facts.
Never invent tool results. Read a file before writing it. Respect user constraints.
When finished, answer concisely. When asked only to investigate, do not modify files."""


def load_core_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "system.md"
    return path.read_text(encoding="utf-8") if path.exists() else DEFAULT_PROMPT


class AgentService:
    def __init__(self, runtime, repositories):
        self.runtime, self.repositories = runtime, repositories

    @classmethod
    def create(cls, db_url: str, llm, max_steps=8, core_prompt=None):
        engine, factory = create_database(db_url)
        Base.metadata.create_all(engine)
        repositories = Repositories.create(factory)
        registry = ToolRegistry([ListFilesTool(), ReadFileTool(), SearchCodeTool(), WriteFileTool(), RunCommandTool()])
        runtime = AgentRuntime(
            llm, repositories, ContextBuilder(core_prompt or load_core_prompt()), ToolDispatcher(registry), registry,
            Compactor(repositories), max_steps=max_steps,
        )
        return cls(runtime, repositories)

    def run(self, session_id: str, workspace: Path, user_input: str, event_sink=None):
        return self.runtime.run(session_id, workspace, user_input, event_sink=event_sink)
