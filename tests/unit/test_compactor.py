from minicode.llm.fake import FakeLLMClient
from minicode.runtime.compactor import Compactor
from minicode.service import AgentService


def make_service(tmp_path):
    return AgentService.create(
        db_url=f"sqlite:///{tmp_path / 'state.db'}",
        llm=FakeLLMClient([]),
    )


def test_compaction_summarizes_old_messages_without_deleting_history(tmp_path):
    service = make_service(tmp_path)
    repositories = service.repositories
    repositories.sessions.get_or_create("demo", str(tmp_path))
    repositories.messages.add("demo", "user", "旧目标：" + "A" * 80)
    repositories.messages.add("demo", "assistant", "旧结论：" + "B" * 80)
    repositories.messages.add("demo", "user", "最近问题")
    repositories.messages.add("demo", "assistant", "最近回答")
    compactor = Compactor(repositories, char_limit=100, keep_recent=2)

    compactor.compact_if_needed("demo")

    session = repositories.sessions.get("demo")
    assert repositories.messages.count("demo") == 4
    assert "旧目标" in session.summary
    assert "旧结论" in session.summary
    assert "最近问题" not in session.summary
    assert [message["content"] for message in compactor.context_messages("demo")] == [
        "最近问题",
        "最近回答",
    ]


def test_micro_compaction_keeps_tool_protocol_but_shortens_old_tool_output(tmp_path):
    service = make_service(tmp_path)
    repositories = service.repositories
    repositories.sessions.get_or_create("demo", str(tmp_path))
    repositories.messages.add(
        "demo",
        "assistant",
        "",
        extra_data={
            "tool_calls": [
                {
                    "id": "old-call",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"old.py"}'},
                }
            ]
        },
    )
    repositories.messages.add("demo", "tool", "OLD TOOL OUTPUT " + "X" * 100, "old-call")
    repositories.messages.add(
        "demo",
        "assistant",
        "",
        extra_data={
            "tool_calls": [
                {
                    "id": "new-call",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"new.py"}'},
                }
            ]
        },
    )
    repositories.messages.add("demo", "tool", "NEW TOOL OUTPUT", "new-call")
    compactor = Compactor(repositories, char_limit=10_000, keep_full_tool_results=1)

    messages = compactor.context_messages("demo")

    assert messages[0]["tool_calls"][0]["id"] == "old-call"
    assert messages[1]["role"] == "tool"
    assert messages[1]["tool_call_id"] == "old-call"
    assert "旧工具输出已压缩" in messages[1]["content"]
    assert messages[2]["tool_calls"][0]["id"] == "new-call"
    assert messages[3]["content"] == "NEW TOOL OUTPUT"
