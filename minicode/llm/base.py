from typing import Protocol

from minicode.runtime.models import LLMResponse


class LLMClient(Protocol):
    def complete(self, messages: list[dict], tools: list[dict], on_text_delta=None) -> LLMResponse: ...
