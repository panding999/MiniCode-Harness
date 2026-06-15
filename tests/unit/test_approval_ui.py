from io import StringIO

from rich.console import Console

from minicode.permissions.policy import PolicyAction, PolicyDecision
from minicode.runtime.models import ToolCall
from minicode.terminal_ui import TerminalUI


def test_terminal_approval_accepts_yes_and_rejects_no_with_clear_prompt():
    output = StringIO()
    ui = TerminalUI(Console(file=output, force_terminal=False))
    decision = PolicyDecision(PolicyAction.REQUIRE_APPROVAL, "Writing sensitive path: .env")
    call = ToolCall(id="1", name="write_file", arguments={"path": ".env", "content": "secret"})

    prompts = []
    approved = ui.approve_tool(decision, call, input_func=lambda prompt: prompts.append(prompt) or "y")
    rejected = ui.approve_tool(decision, call, input_func=lambda prompt: prompts.append(prompt) or "n")

    assert approved is True
    assert rejected is False
    assert all("[y/n]" in prompt for prompt in prompts)
    assert "write_file" in output.getvalue()
    assert ".env" in output.getvalue()
    assert "secret" not in output.getvalue()


def test_terminal_approval_reprompts_invalid_answer():
    ui = TerminalUI(Console(file=StringIO(), force_terminal=False))
    decision = PolicyDecision(PolicyAction.REQUIRE_APPROVAL, "Writing sensitive path: .env")
    call = ToolCall(id="1", name="write_file", arguments={"path": ".env"})
    answers = iter(["maybe", "n"])

    result = ui.approve_tool(decision, call, input_func=lambda prompt: next(answers))

    assert result is False
