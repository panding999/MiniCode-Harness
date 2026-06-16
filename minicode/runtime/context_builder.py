import json
from pathlib import Path


# 上下文布局在这里。项目 Memory、任务 Memory、Workspace 路径和 Session Summary
# 会先放进一个 system message，再拼接最近消息。
class ContextBuilder:
    def __init__(self, core_prompt: str):
        self.core_prompt = core_prompt

    def build(self, workspace: Path, task, summary: str, recent_messages: list[dict]) -> list[dict]:
        # Project Memory 来源：workspace/AGENT.md。
        agent_file = workspace / "AGENT.md"
        project = agent_file.read_text(encoding="utf-8") if agent_file.exists() else "(No AGENT.md)"
        task_data = task if isinstance(task, dict) else {
            "goal": task.goal, "status": task.status, "summary": task.summary,
            "next_action": task.next_action, "files_read": task.files_read,
            "files_changed": task.files_changed, "commands_run": task.commands_run,
            "test_result": task.test_result, "last_error": task.last_error,
        }
        system = "\n\n".join([
            self.core_prompt,
            f"PROJECT MEMORY:\n{project}",
            f"WORKSPACE:\n{workspace.resolve()}",
            f"ACTIVE TASK LEDGER:\n{json.dumps(task_data, ensure_ascii=False)}",
            f"SESSION SUMMARY:\n{summary or '(empty)'}",
        ])
        return [{"role": "system", "content": system}, *recent_messages]
