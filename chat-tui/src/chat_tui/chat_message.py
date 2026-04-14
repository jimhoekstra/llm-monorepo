import asyncio

from textual.app import ComposeResult
from textual.widgets import Markdown, Button, LoadingIndicator
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

    DEFAULT_CSS = """
    ChatMessage {
        height: auto;
        margin: 1 0 0 0;
    }

    ChatMessage ContentSwitcher {
        height: auto;
    }

    ChatMessage .chat-message-label {
        padding: 1 1 0 1;
        background: transparent;
    }

    .chat-message-label-assistant {
        border: round $secondary;
        border-title-background: $secondary-muted;
        
        border-subtitle-color: $text-muted;
        border-subtitle-background: $surface;
    }

    .chat-message-label-reasoning {
        border: round $warning;
        color: $text-muted;
    }

    .chat-message-label-tool-call {
        border: round $success-darken-2;
        border-title-background: $success-muted;
        
        border-subtitle-color: $text-muted;
        border-subtitle-background: $surface;
    }

    .chat-message-label-user {
        border: round $panel;
        border-title-color: $text-muted;
        border-title-background: $surface;
        
    }

    #loading-indicator {
        border: round $panel;
        height: 5;
    }
    """

    def __init__(self, text: str, role: str) -> None:
        super().__init__(classes=f"chat-message-{role}")
        self._text = text
        self._role = role

    def compose(self) -> ComposeResult:
        """
        Compose the chat message widget.

        Returns
        -------
        The composed widgets for this chat message.
        """
        border_title = " ".join([word.capitalize() for word in self._role.split("-")])

        label = Markdown(
            self._text,
            classes=f"chat-message-label chat-message-label-{self._role}",
            id="chat-message-content",
        )
        label.border_title = border_title
        yield label

    def has_text(self) -> bool:
        """
        Check whether this message contains non-whitespace text.

        Returns
        -------
        True if the message has non-whitespace content, False otherwise.
        """
        return len(self._text.strip()) > 0

    def append_token(self, token: str) -> None:
        """
        Append a token to the message text and update the rendered markdown.

        Parameters
        ----------
        token
            The text token to append.
        """
        is_first_token = not self.has_text()

        if is_first_token:
            self.display = True

        self._text += token
        self.query_one(".chat-message-label", Markdown).update(self._text)

    def update_border_subtitle(self, subtitle: str) -> None:
        """
        Update the border subtitle of the message label.

        Parameters
        ----------
        subtitle
            The subtitle text to display in the border.
        """
        self.query_one(".chat-message-label", Markdown).border_subtitle = subtitle

    def update_usage(self, usage: TokenUsage, timings: Timings) -> None:
        """
        Update the border subtitle with token usage and timing statistics.

        Parameters
        ----------
        usage
            Token usage counts for this message.
        timings
            Timing statistics for prompt and prediction.
        """
        self.update_border_subtitle(
            f"In: {usage.prompt_tokens} ({int(timings.prompt_per_second)}/s - {timings.cache_n} cached) "
            f"- Out: {usage.completion_tokens} ({int(timings.predicted_per_second)}/s) "
            f"- Total: {usage.total_tokens}"
        )


class LoadingIndicatorChatMessage(ChatMessage):
    def __init__(self) -> None:
        """
        Create a loading indicator chat message.
        """
        super().__init__("", "loading")

    def compose(self) -> ComposeResult:
        """
        Compose the loading indicator widget.

        Returns
        -------
        The composed widgets for this loading indicator message.
        """
        border_title = " ".join([word.capitalize() for word in self._role.split("-")])
        loading = LoadingIndicator(id="loading-indicator")
        loading.border_title = border_title
        yield loading

    def dismiss(self) -> None:
        """
        Remove this message from the chat history.
        """
        self.remove()


class ToolCallChatMessage(ChatMessage):
    tool_call: ToolCall | None = None
    tool_call_result: ToolCallResult | None = None

    def __init__(self, text: str, role: str) -> None:
        super().__init__(text, role)
        self._resolved = asyncio.Event()

    def compose(self) -> ComposeResult:
        """
        Compose the tool call message with approve and reject buttons.

        Returns
        -------
        The composed widgets for this tool call message.
        """
        for widget in super().compose():
            yield widget

        with Horizontal(classes="tool-call-actions"):
            yield Button("Approve", classes="tool-call-approve")
            yield Button("Reject", classes="tool-call-reject")

    def set_tool_call(self, tool_call: ToolCall) -> None:
        """
        Set the tool call associated with this message.

        Parameters
        ----------
        tool_call
            The tool call to associate with this message.
        """
        self.tool_call = tool_call

    def _hide_buttons(self) -> None:
        """
        Hide the approve and reject buttons.
        """
        for button in self.query(".tool-call-actions Button"):
            button.display = False

    def call_tool_and_set_result(self) -> None:
        if self.tool_call is None:
            raise ValueError("No tool call to run.")

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

    @on(Button.Pressed, ".tool-call-approve")
    def tool_call_approved(self, event: Button.Pressed) -> None:
        """
        Handle approval of the tool call.

        Parameters
        ----------
        event
            The button press event.

        Raises
        ------
        ValueError
            When no tool call has been set on this message.
        """
        if self.tool_call is None:
            raise ValueError("No tool call to approve.")

        return self.call_tool_and_set_result()

    @on(Button.Pressed, ".tool-call-reject")
    def tool_call_rejected(self, event: Button.Pressed) -> None:
        """
        Handle rejection of the tool call.

        Parameters
        ----------
        event
            The button press event.

        Raises
        ------
        ValueError
            When no tool call has been set on this message.
        """
        if self.tool_call is None:
            raise ValueError("No tool call to reject.")

        self.append_token("\n## Tool call rejected.")
        self.tool_call_result = self.tool_call.reject()

        self._resolved.set()
        self._hide_buttons()

    async def wait_for_result(self) -> ToolCallResult:
        """
        Wait until the tool call has been approved or rejected.

        Returns
        -------
        The result of the tool call once resolved.

        Raises
        ------
        ValueError
            When the tool call was not resolved properly.
        """
        if self.tool_call is None:
            raise ValueError("No tool call to wait for.")

        if self.tool_call.requires_approval():
            await self._resolved.wait()
        else:
            self.call_tool_and_set_result()

        if self.tool_call_result is None:
            raise ValueError("Tool call was not resolved properly.")

        return self.tool_call_result
