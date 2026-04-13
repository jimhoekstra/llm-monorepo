import asyncio

from textual.app import ComposeResult
from textual.widgets import Markdown, Button
from textual.containers import Container, Horizontal
from textual import on

from local_llm.response.models import (
    TokenUsage,
    Timings,
    ToolCall,
)
from local_llm.tools import ToolCallResult


class ChatMessage(Container):
    """A single chat message bubble."""

    def __init__(self, text: str, role: str) -> None:
        super().__init__(classes=f"chat-message-{role}")
        self._text = text
        self._role = role

    def compose(self) -> ComposeResult:
        label = Markdown(
            self._text,
            classes=f"chat-message-label chat-message-label-{self._role}",
        )
        label.border_title = " ".join([w.capitalize() for w in self._role.split("-")])
        yield label

    def has_text(self) -> bool:
        return bool(self._text.strip())

    def append_token(self, token: str) -> None:
        if not self.has_text() and (
            self._role == "reasoning" or self._role == "tool-call"
        ):
            self.display = True

        self._text += token
        self.query_one(".chat-message-label", Markdown).update(self._text)

    def update_border_subtitle(self, subtitle: str) -> None:
        self.query_one(".chat-message-label", Markdown).border_subtitle = subtitle

    def update_usage(self, usage: TokenUsage, timings: Timings) -> None:
        self.update_border_subtitle(
            f"In: {usage.prompt_tokens} tokens ({timings.prompt_per_second:.1f}/s) "
            f"- Out: {usage.completion_tokens} tokens ({timings.predicted_per_second:.1f}/s) "
            f"- Total: {usage.total_tokens} tokens"
        )


class ToolCallChatMessage(ChatMessage):
    tool_call: ToolCall | None = None
    tool_call_result: ToolCallResult | None = None

    def __init__(self, text: str, role: str) -> None:
        super().__init__(text, role)
        self._resolved = asyncio.Event()

    def compose(self) -> ComposeResult:
        for w in super().compose():
            yield w

        with Horizontal(classes="tool-call-actions"):
            yield Button("Approve", classes="tool-call-approve")
            yield Button("Reject", classes="tool-call-reject")

    def set_tool_call(self, tool_call: ToolCall) -> None:
        self.tool_call = tool_call

    def _hide_buttons(self) -> None:
        for button in self.query(".tool-call-actions Button"):
            button.display = False

    @on(Button.Pressed, ".tool-call-approve")
    def tool_call_approved(self, event: Button.Pressed) -> None:
        if self.tool_call is None:
            raise ValueError("No tool call to approve.")

        try:
            tool_call_result = self.tool_call.call()
            self.tool_call_result = tool_call_result
            self.append_token(
                f"\n## Tool call approved. Result:\n\n{tool_call_result.content}"
            )
        except ValueError:
            self.append_token(
                "\n\nTool call failed due to invalid arguments or other error."
            )
        finally:
            self._resolved.set()
            self._hide_buttons()

    @on(Button.Pressed, ".tool-call-reject")
    def tool_call_rejected(self, event: Button.Pressed) -> None:
        if self.tool_call is None:
            raise ValueError("No tool call to reject.")

        self.append_token("\n## Tool call rejected.")
        self.tool_call_result = self.tool_call.reject()

        self._resolved.set()
        self._hide_buttons()

    async def wait_for_result(self) -> ToolCallResult:
        await self._resolved.wait()
        if self.tool_call_result is None:
            raise ValueError("Tool call was not resolved properly.")

        return self.tool_call_result
