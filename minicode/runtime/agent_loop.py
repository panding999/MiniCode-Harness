import json
from collections import Counter
from pathlib import Path

from minicode.runtime.models import AgentResult, RuntimeEvent
from minicode.tools.base import ToolContext


# 核心 Agent Loop：构建上下文、调用 LLM、执行工具、持久化 Observation，
# 直到最终回答或安全停止条件触发。
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
        # 每次请求 LLM 前先尝试压缩，避免 prompt 超过配置的字符预算。
        self.compactor.compact_if_needed(session_id)
        run_id = self.repositories.traces.start_run(session_id)
        tool_context = ToolContext(workspace, set(task.files_read or []))
        repeated = Counter()
        step = 0

        try:
            for step in range(1, self.max_steps + 1):
                session = self.repositories.sessions.get(session_id)
                recent = self.compactor.context_messages(session_id)
                summary = self.compactor.summary_for_context(session_id)
                # 每次调用 LLM 前重新召回 Memory/Task 状态，确保上一轮工具 Observation 可见。
                context = self.context_builder.build(workspace, task, summary, recent)
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
                    if result.metadata.get("policy_action"):
                        self.repositories.traces.add(
                            run_id, session_id, step, "policy_decision", tool_name=call.name,
                            arguments={
                                "action": result.metadata["policy_action"],
                                "reason": result.metadata.get("policy_reason", ""),
                                "approved": result.metadata.get("approved"),
                            },
                            success=result.metadata["policy_action"] != "deny" and result.metadata.get("approved", True),
                            output_summary=result.metadata.get("policy_reason", ""),
                        )
                    self.repositories.traces.add(
                        run_id, session_id, step, "tool_result", tool_name=call.name,
                        arguments=call.arguments, success=result.success, output_summary=result.output_summary,
                        error=result.error, duration_ms=result.duration_ms,
                    )
                    # Task Ledger 根据客观工具结果更新，而不是根据模型自然语言自述更新。
                    task = self._record_task_result(task.id, task, call.name, result, tool_context)
                    if (
                        result.metadata.get("policy_action") == "require_approval"
                        and result.metadata.get("approved") is False
                    ):
                        return self._pause(
                            task.id,
                            run_id,
                            session_id,
                            step,
                            "High-risk operation was rejected by user; this run was stopped",
                        )
                    if result.metadata.get("policy_action") == "deny":
                        return self._pause(
                            task.id,
                            run_id,
                            session_id,
                            step,
                            "High-risk operation was denied by policy; this run was stopped",
                        )

            return self._pause(task.id, run_id, session_id, self.max_steps, "Maximum steps reached")
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
            self.repositories.tasks.update(task.id, status="failed", last_error=reason, next_action="Resolve runtime failure")
            self.repositories.traces.add(
                run_id, session_id, step, "run_failed",
                success=False, output_summary=reason[:500], error=reason,
            )
            self.repositories.traces.finish(run_id, "failed")
            raise

    def _pause(self, task_id, run_id, session_id, step, reason):
        self.repositories.tasks.update(task_id, status="paused", next_action=reason, last_error=reason)
        self.repositories.traces.add(run_id, session_id, step, "paused", success=False, output_summary=reason, error=reason)
        self.repositories.traces.finish(run_id, "paused")
        return AgentResult(reason, "paused", run_id)

    def _record_task_result(self, task_id, task, name, result, context):
        # 文件、命令、测试结果和 last_error 的 Task Ledger 更新入口。
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
