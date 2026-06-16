import json

from openai import OpenAI

from minicode.runtime.models import LLMResponse, ToolCall


# OpenAI-compatible 流式适配器。它把文本增量和 tool_call 片段合并成 Runtime 使用的 LLMResponse。
class OpenAICompatibleClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, messages: list[dict], tools: list[dict], on_text_delta=None) -> LLMResponse:
        # stream=True 用于终端实时输出，同时仍会收集完整工具调用供 Runtime 执行。
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            stream=True,
        )
        text_parts = []
        calls: dict[int, dict] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_parts.append(delta.content)
                if on_text_delta:
                    on_text_delta(delta.content)
            for call in delta.tool_calls or []:
                current = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                if call.id:
                    current["id"] = call.id
                if call.function:
                    current["name"] += call.function.name or ""
                    current["arguments"] += call.function.arguments or ""
        tool_calls = [
            ToolCall(id=data["id"], name=data["name"], arguments=json.loads(data["arguments"] or "{}"))
            for _, data in sorted(calls.items())
        ]
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)
