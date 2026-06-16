from typing import Protocol

from minicode.runtime.models import LLMResponse


# Runtime 使用的最小 LLM 接口；真实客户端和 Fake 客户端都实现这个形状。
class LLMClient(Protocol):
    def complete(self, messages: list[dict], tools: list[dict], on_text_delta=None) -> LLMResponse: ...
