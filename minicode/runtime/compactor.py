import re


SUMMARY_MARKER = "<!-- compacted-through:{message_id} -->"
SUMMARY_MARKER_PATTERN = re.compile(r"<!-- compacted-through:(\d+) -->")


class Compactor:
    def __init__(
        self,
        repositories,
        char_limit=12_000,
        keep_recent=12,
        keep_full_tool_results=5,
        max_summary_chars=8_000,
    ):
        self.repositories = repositories
        self.char_limit = char_limit
        self.keep_recent = keep_recent
        self.keep_full_tool_results = keep_full_tool_results
        self.max_summary_chars = max_summary_chars

    def compact_if_needed(self, session_id: str):
        session = self.repositories.sessions.get(session_id)
        compacted_through = _compacted_through(session.summary)
        pending = self.repositories.messages.list_after(session_id, compacted_through)
        if sum(len(message.content or "") for message in pending) <= self.char_limit:
            return

        cutoff = _safe_cutoff(pending, self.keep_recent)
        older = pending[:cutoff]
        if not older:
            return

        previous = _summary_body(session.summary)
        addition = _structured_summary(older)
        body = "\n".join(part for part in [previous, addition] if part).strip()
        if len(body) > self.max_summary_chars:
            body = "（较早摘要已省略）\n" + body[-self.max_summary_chars:]
        summary = f"{body}\n{SUMMARY_MARKER.format(message_id=older[-1].id)}"
        self.repositories.sessions.update_summary(session_id, summary)

    def context_messages(self, session_id: str) -> list[dict]:
        session = self.repositories.sessions.get(session_id)
        compacted_through = _compacted_through(session.summary)
        rows = self.repositories.messages.list_after(session_id, compacted_through)
        tool_rows = [message for message in rows if message.role == "tool"]
        full_tool_rows = tool_rows[-self.keep_full_tool_results:] if self.keep_full_tool_results else []
        full_tool_ids = {
            row.id
            for row in full_tool_rows
        }
        return [_message_dict(row, keep_tool_output=row.id in full_tool_ids) for row in rows]

    def summary_for_context(self, session_id: str) -> str:
        return _summary_body(self.repositories.sessions.get(session_id).summary)


def _safe_cutoff(messages, keep_recent):
    cutoff = max(0, len(messages) - keep_recent)
    if cutoff >= len(messages):
        return len(messages)
    while cutoff > 0 and messages[cutoff].role == "tool":
        cutoff -= 1
    return cutoff


def _structured_summary(messages):
    sections = {
        "用户目标与约束": [],
        "助手结论": [],
        "工具执行": [],
    }
    for message in messages:
        content = " ".join((message.content or "").split())
        if message.role == "user" and content:
            sections["用户目标与约束"].append(content[:400])
        elif message.role == "assistant":
            tool_calls = (message.extra_data or {}).get("tool_calls", [])
            if tool_calls:
                names = ", ".join(call["function"]["name"] for call in tool_calls)
                sections["工具执行"].append(f"请求工具：{names}")
            elif content:
                sections["助手结论"].append(content[:400])
        elif message.role == "tool":
            sections["工具执行"].append(f"工具结果（{message.tool_call_id or 'unknown'}）：{content[:200]}")

    rows = ["## 累计会话摘要"]
    for title, items in sections.items():
        if items:
            rows.append(f"### {title}")
            rows.extend(f"- {item}" for item in items)
    return "\n".join(rows)


def _compacted_through(summary):
    match = SUMMARY_MARKER_PATTERN.search(summary or "")
    return int(match.group(1)) if match else 0


def _summary_body(summary):
    return SUMMARY_MARKER_PATTERN.sub("", summary or "").strip()


def _message_dict(row, keep_tool_output=True):
    content = row.content
    if row.role == "tool" and not keep_tool_output:
        content = f"[旧工具输出已压缩：tool_call_id={row.tool_call_id or 'unknown'}]"
    message = {"role": row.role, "content": content}
    if row.tool_call_id:
        message["tool_call_id"] = row.tool_call_id
    message.update(row.extra_data or {})
    return message
