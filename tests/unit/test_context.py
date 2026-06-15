from pathlib import Path

from minicode.runtime.context_builder import ContextBuilder
from minicode.service import load_core_prompt


def test_context_contains_project_task_summary_and_messages(tmp_path: Path):
    (tmp_path / "AGENT.md").write_text("PROJECT RULE", encoding="utf-8")
    builder = ContextBuilder("CORE RULE")
    messages = builder.build(
        workspace=tmp_path,
        task={"goal": "fix bug", "next_action": "read file"},
        summary="OLD SUMMARY",
        recent_messages=[{"role": "user", "content": "hi"}],
    )
    joined = "\n".join(item["content"] for item in messages)
    assert joined.index("CORE RULE") < joined.index("PROJECT RULE") < joined.index("fix bug")
    assert "OLD SUMMARY" in joined and "hi" in joined


def test_core_prompt_uses_chinese_rules_and_preserves_tool_names():
    prompt = load_core_prompt()

    assert "你是 MiniCode" in prompt
    assert "默认使用与用户相同的语言回答" in prompt
    assert "read_file" in prompt
    assert "run_command" in prompt
