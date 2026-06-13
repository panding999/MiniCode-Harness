from types import SimpleNamespace

from minicode.llm.openai_compatible import OpenAICompatibleClient


def chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def tool_delta(index, call_id=None, name=None, arguments=None):
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=call_id, function=function)


def test_streaming_client_emits_text_and_assembles_tool_calls():
    client = OpenAICompatibleClient("key", "model")
    client.client.chat.completions.create = lambda **kwargs: iter([
        chunk(content="hel"),
        chunk(content="lo"),
        chunk(tool_calls=[tool_delta(0, "call-1", "read_file", '{"path":')]),
        chunk(tool_calls=[tool_delta(0, arguments='"a.py"}')]),
    ])
    deltas = []

    response = client.complete([], [], on_text_delta=deltas.append)

    assert deltas == ["hel", "lo"]
    assert response.text == "hello"
    assert response.tool_calls[0].arguments == {"path": "a.py"}
