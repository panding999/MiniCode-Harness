import json
from collections import Counter
from pathlib import Path

from minicode.runtime.models import AgentResult, RuntimeEvent
from minicode.tools.base import ToolContext


class AgentRuntime:
    def __init__(self, llm, repositories, context_builder, dispatcher, registry, compactor, max_steps=8, repeat_limit=3):
        self.llm = llm
        self.repositories = repositories
        self.context_builder = context_builder
        self.dispatcher = dispatcher
        self.registry = registry
        self.compactor = compactor
        self.max_steps = max_steps
        self.repeat_limit = repeat_limit

    def run(self, session_id: str, workspace: Path, user_input: str, event_sink=None) -> AgentResult:
        emit = event_sink or (lambda event: None)
        workspace = workspace.resolve()
        session = self.repositories.sessions.get_or_create(session_id, str(workspace))
        self.repositories.messages.add(session_id, "user", user_input)
        task = self.repositories.tasks.get_or_create(session_id, user_input)
        run_id = self.repositories.traces.start_run(session_id)
        tool_context = ToolContext(workspace, set(task.files_read or []))
        repeated = Counter()

        for step in range(1, self.max_steps + 1):
            session = self.repositories.sessions.get(session_id)
            recent = [_message_dict(row) for row in self.repositories.messages.list_recent(session_id)]
            context = self.context_builder.build(workspace, task, session.summary, recent)
            emit(RuntimeEvent("thinking_started", step=step))
            streamed = False

            def on_delta(text):
                nonlocal streamed
                streamed = True
                emit(RuntimeEvent("text_delta", step=step, text=text))

            response = self.llm.complete(context, self.registry.schemas(), on_text_delta=on_delta)
            self.repositories.traces.add(run_id, session_id, step, "llm_response", success=True, output_summary=response.text[:500])

            if response.is_final:
                if response.text and not streamed:
                    emit(RuntimeEvent("text_delta", step=step, text=response.text))
                status = response.task_status or ("paused" if _requests_pause(user_input) else "completed")
                next_action = response.next_action or (response.text[:500] if status == "paused" else "")
                self.repositories.messages.add(session_id, "assistant", response.text)
                self.repositories.tasks.update(task.id, status=status, summary=response.text[:1000], next_action=next_action)
                self.repositories.traces.finish(run_id, status)
                self.compactor.compact_if_needed(session_id)
                emit(RuntimeEvent("run_finished", step=step, text=response.text))
                return AgentResult(response.text, status, run_id)

            self.repositories.messages.add(
                session_id,
                "assistant",
                response.text,
                extra_data={"tool_calls": [_tool_call_dict(call) for call in response.tool_calls]},
            )
            for call in response.tool_calls:
                emit(RuntimeEvent("tool_started", step=step, tool_name=call.name, arguments=call.arguments))
                signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
                repeated[signature] += 1
                if repeated[signature] >= self.repeat_limit:
                    return self._pause(task.id, run_id, session_id, step, "Detected repeated tool call")
                result = self.dispatcher.dispatch(call, tool_context)
                emit(RuntimeEvent("tool_finished", step=step, tool_name=call.name, text=result.output_summary, success=result.success))
                self.repositories.messages.add(session_id, "tool", result.output or result.error, call.id)
                self.repositories.traces.add(
                    run_id, session_id, step, "tool_result", tool_name=call.name,
                    arguments=call.arguments, success=result.success, output_summary=result.output_summary,
                    error=result.error, duration_ms=result.duration_ms,
                )
                task = self._record_task_result(task.id, task, call.name, result, tool_context)

        return self._pause(task.id, run_id, session_id, self.max_steps, "Maximum steps reached")

    def _pause(self, task_id, run_id, session_id, step, reason):
        self.repositories.tasks.update(task_id, status="paused", next_action=reason, last_error=reason)
        self.repositories.traces.add(run_id, session_id, step, "paused", success=False, output_summary=reason, error=reason)
        self.repositories.traces.finish(run_id, "paused")
        return AgentResult(reason, "paused", run_id)

    def _record_task_result(self, task_id, task, name, result, context):
        values = {"files_read": sorted(context.files_read)}
        if name == "write_file" and result.success:
            values["files_changed"] = _append_unique(task.files_changed, result.metadata.get("path"))
        if name == "run_command":
            values["commands_run"] = [*(task.commands_run or []), result.metadata.get("argv", [])]
            if result.metadata.get("argv", [None])[0] == "pytest":
                values["test_result"] = result.output_summary
        if not result.success:
            values["last_error"] = result.error
        return self.repositories.tasks.update(task_id, **values)


def _append_unique(items, value):
    return list(dict.fromkeys([*(items or []), value])) if value else list(items or [])


def _requests_pause(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ["只定位", "不要修改", "do not modify", "only investigate"])


def _tool_call_dict(call):
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
    }


def _message_dict(row):
    message = {"role": row.role, "content": row.content}
    if row.tool_call_id:
        message["tool_call_id"] = row.tool_call_id
    message.update(row.extra_data or {})
    return message
