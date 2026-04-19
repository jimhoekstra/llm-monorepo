import asyncio
import time

from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Markdown, Button, Collapsible
from textual.containers import Container, Horizontal
from textual import on

from local_llm.response.models import (
    # TokenUsage,
    # Timings,
    ToolCall,
)
from local_llm.tools import ToolCallResult


_ROLE_TITLE_STYLE: dict[str, str] = {
    "assistant": "#0088ff",
    "reasoning": "#d7875f",
    "user": "#8787ff",
    "tool-call": "#5faf5f",
}


class ChatMessage(Container):
    """A single chat message bubble."""

    DEFAULT_CSS = """
    .chat-message-collapsible {
        height: auto;
        margin: 0;
        padding: 0;
        background: transparent;
        border-top: none;
    }

    .chat-message-collapsible CollapsibleTitle:focus {
        color: $text;
        background: $surface;
    }

    ChatMessage {
        margin: 0;
        height: auto;
    }

    ChatMessage .chat-message-label {
        padding: 1 1 0 1;
        margin: 0;
        background: transparent;
    }

    .chat-message-collapsible > Contents {
        padding: 0;
        height: auto;
    }

    .chat-message-label-reasoning {
        color: $text-muted;
    }

    .chat-message-label-tool-call {
        color: $success-darken-3;
    }

    #loading-indicator {
        border: round $panel;
        height: 5;
    }
    """

    def __init__(self, text: str, role: str) -> None:
        super().__init__(classes=f"chat-message chat-message-{role}")
        self._text = text
        self._role = role
        self._is_complete = False

        self._start_time: float = 0.0
        self._elapsed_time: float = 0.0
        self._loading_timer: Timer | None = None

        self._is_default_collapsed = role in ("reasoning", "tool-call")
        self._title_text = " ".join(
            [word.capitalize() for word in self._role.split("-")]
        )
        self._title_suffix = ""

    def compose(self) -> ComposeResult:
        """
        Compose the chat message widget.

        Returns
        -------
        The composed widgets for this chat message.
        """
        label = Markdown(
            self._text,
            classes=f"chat-message-label chat-message-label-{self._role}",
            id="chat-message-content",
        )

        yield Collapsible(
            label,
            title=self._styled_title(),
            classes=f"chat-message-collapsible chat-message-collapsible-{self._role}",
            collapsed=self._is_default_collapsed,
            collapsed_symbol=">",
            expanded_symbol="v",
        )

    def _styled_title(self) -> str:
        """
        Compute the title with color and underline based on collapsed state.

        Returns
        -------
        The Rich-markup-styled title string.
        """
        style = _ROLE_TITLE_STYLE.get(self._role, "")
        title = f"[{style}]{self._title_text}[/{style}]" if style else self._title_text

        return f"{title}{self._title_suffix}"

    def mark_loading(self) -> None:
        """
        Start the loading animation and elapsed time display or proceed if already started.
        """
        if self._loading_timer is None or self._is_complete:
            self._is_complete = False
            self._start_time = time.monotonic()
            self._loading_timer = self.set_interval(0.1, self._animate_loading)

    def _animate_loading(self) -> None:
        """
        Update the title with the elapsed time in seconds.
        """
        self._elapsed_time = time.monotonic() - self._start_time
        collapsible = self.query_one(".chat-message-collapsible", Collapsible)
        collapsible.title = (
            f"{self._styled_title()} [dim]{self._elapsed_time:.1f}s[/dim]"
        )

    def mark_complete(self) -> None:
        """
        Stop the loading animation and restore the plain title.
        """
        self._is_complete = True
        if self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer = None
            self._animate_loading()

    def has_text(self) -> bool:
        """
        Check whether this message contains non-whitespace text.

        Returns
        -------
        True if the message has non-whitespace content, False otherwise.
        """
        return len(self._text.strip()) > 0

    # def update_title(self, title: str) -> None:
    #     """
    #     Update the border title of the message.

    #     Parameters
    #     ----------
    #     title
    #         The new title text to display in the border.
    #     """
    #     self.query_one(".chat-message-collapsible", Collapsible).border_title = title

    def append_title(self, title: str) -> None:
        """
        Append text to the existing base title.

        Parameters
        ----------
        title
            The text to append to the existing title.
        """
        self._title_suffix = f"{self._title_suffix}[dim]{title}[/dim]"
        self.query_one(
            ".chat-message-collapsible", Collapsible
        ).title = self._styled_title()
        self.display = True

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

    # def update_border_subtitle(self, subtitle: str) -> None:
    #     """
    #     Update the border subtitle of the message label.

    #     Parameters
    #     ----------
    #     subtitle
    #         The subtitle text to display in the border.
    #     """
    #     self.query_one(".chat-message-collapsible", Collapsible).border_subtitle = subtitle

    # def update_usage(self, usage: TokenUsage, timings: Timings) -> None:
    #     """
    #     Update the border subtitle with token usage and timing statistics.

    #     Parameters
    #     ----------
    #     usage
    #         Token usage counts for this message.
    #     timings
    #         Timing statistics for prompt and prediction.
    #     """
    #     self.update_border_subtitle(
    #         f"In: {usage.prompt_tokens} ({timings.prompt_per_second:.1f}/s - {timings.cache_n} cached) "
    #         f"- Out: {usage.completion_tokens} ({timings.predicted_per_second:.1f}/s) "
    #         f"- Total: {usage.total_tokens}"
    #     )


class ToolCallChatMessage(ChatMessage):
    tool_call: ToolCall | None = None
    tool_call_result: ToolCallResult | None = None

    def __init__(self, text: str, role: str) -> None:
        super().__init__(text, role)
        self._resolved = asyncio.Event()

    async def set_tool_call(self, tool_call: ToolCall) -> None:
        """
        Set the tool call associated with this message.

        If the tool call requires approval, approve and reject buttons will be
        displayed.

        Parameters
        ----------
        tool_call
            The tool call to associate with this message.
        """
        self.tool_call = tool_call

        if self.tool_call.requires_approval():
            await self.mount(
                Horizontal(
                    Button("Approve", classes="tool-call-approve"),
                    Button("Reject", classes="tool-call-reject"),
                    classes="tool-call-actions",
                )
            )

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
                f"\n\nResult:\n\n```json\n{tool_call_result.content}\n```"
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
