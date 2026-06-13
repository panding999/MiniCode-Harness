from pathlib import Path

from minicode.runtime.context_builder import ContextBuilder


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
