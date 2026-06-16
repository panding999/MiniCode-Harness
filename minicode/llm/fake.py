from collections import deque

from minicode.runtime.models import LLMResponse


# 确定性的测试替身，让 Runtime 测试无需网络和 API 费用也能验证编排逻辑。
class FakeLLMClient:
    def __init__(self, responses: list[LLMResponse]):
        self.responses = deque(responses)
        self.requests: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict], on_text_delta=None) -> LLMResponse:
        self.requests.append(messages)
        if not self.responses:
            return LLMResponse(text="FakeLLM has no remaining scripted response.", task_status="failed")
        return self.responses.popleft()
