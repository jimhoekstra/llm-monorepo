from pathlib import Path
from datetime import datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json

from textual.app import App, ComposeResult
from textual import work

from local_llm.request import call_llm_async, build_system_prompt, build_user_prompt
from local_llm.response.models import (
    Response,
    UpdateSummary,
    Message,
)
from local_llm.tools import ToolCallResult, load_tools, register_tool, Description

from .chat_history import ChatHistory
from .chat_message import ChatMessage, ToolCallChatMessage, LoadingIndicatorChatMessage
from .user_input import UserInput, InputGroup


@register_tool(
    description=(
        "Get the current time using UTC timezone in ISO format, and the day of the week. "
        "Use this tool when the assistant needs to know the current time, keep in mind that "
        "the resulting timestamp might need to be converted to a different timezone using the "
        "`convert_timezone` tool if the user is asking for the current time in a specific region "
        "or city."
    ),
    requires_approval=False,
)
def get_current_time() -> Annotated[
    str, Description("Information about the current timestamp using UTC timezone and the day of the week in JSON format")
]:
    """
    Get the current UTC time as a JSON string.

    Returns
    -------
    A JSON object containing the ISO timestamp and weekday name.
    """
    now = datetime.now(timezone.utc)

    date = {"iso_timestamp": now.isoformat(), "weekday": now.strftime("%A")}

    return json.dumps(date)


@register_tool(
    description=(
        "Convert a datetime from one time zone to another. Use this tool when the assistant "
        "needs to convert a datetime between time zones, or use this tool after getting the "
        "current time in UTC if the user asks for the current time in a specific region or city."
    ),
    requires_approval=False,
)
def convert_timezone(
    iso_timestamp: Annotated[str, Description("The datetime to convert, in ISO 8601 format")],
    from_tz: Annotated[str, Description("The IANA time zone name of the input datetime, e.g. 'America/New_York'")],
    to_tz: Annotated[str, Description("The IANA time zone name to convert to, e.g. 'Europe/London'")],
) -> Annotated[str, Description("The converted datetime in ISO 8601 format, returned in JSON format")]:
    """
    Convert a datetime from one time zone to another.

    Parameters
    ----------
    iso_timestamp
        The datetime to convert, in ISO 8601 format.
    from_tz
        The IANA time zone name of the input datetime, e.g. "America/New_York".
    to_tz
        The IANA time zone name to convert to, e.g. "Europe/London".

    Returns
    -------
    A JSON object containing the converted ISO timestamp and the target time zone name.

    Raises
    ------
    ValueError
        When either time zone name is invalid or the timestamp cannot be parsed.
    """
    try:
        source_zone = ZoneInfo(from_tz)
        target_zone = ZoneInfo(to_tz)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Unknown time zone: {e}") from e

    try:
        dt = datetime.fromisoformat(iso_timestamp).replace(tzinfo=source_zone)
    except ValueError as e:
        raise ValueError(f"Invalid ISO timestamp: {e}") from e

    converted = dt.astimezone(target_zone)
    return json.dumps({"iso_timestamp": converted.isoformat(), "timezone": to_tz})


class ChatApp(App):
    """
    Textual TUI application for chatting with an LLM.
    """

    CSS_PATH = "styles.tcss"
    messages: list[Message | ToolCallResult]

    def on_mount(self) -> None:
        """
        Initialize the application after mounting.

        Sets the theme, focuses the user input widget, and seeds the
        message history with the system prompt.
        """
        self.theme = "catppuccin-mocha"
        self.query_one(UserInput).focus()
        self.messages = [
            build_system_prompt(
                prompt=(
                    Path(__file__).resolve().parent / "prompts" / "system.md"
                ).read_text()
            )
        ]

    def on_user_input_submitted(self, message: UserInput.Submitted) -> None:
        """
        Handle a user input submission event.

        Parameters
        ----------
        message
            The submission event containing the user's text.
        """
        self.stream_reply(message.text)

    @work
    async def stream_reply(self, user_text: str) -> None:
        """
        Stream a reply from the LLM in response to user input.

        Appends the user message to history, then iterates through LLM
        responses until a stop signal is received. Handles streaming text,
        reasoning tokens, and tool calls, updating the chat history UI
        as tokens arrive.

        Parameters
        ----------
        user_text
            The message text submitted by the user.
        """
        chat_history = self.query_one(ChatHistory)

        self.messages.append(build_user_prompt(user_text))
        finish_reason = None

        while finish_reason not in {"stop"}:
            loading_message = LoadingIndicatorChatMessage()
            await chat_history.mount(loading_message)

            reasoning_message = ChatMessage("", "reasoning")
            reasoning_message.display = False
            await chat_history.mount(reasoning_message)

            assistant_message = ChatMessage("", "assistant")
            assistant_message.display = False
            await chat_history.mount(assistant_message)

            tool_calls_message = ToolCallChatMessage("", "tool-call")
            tool_calls_message.display = False
            await chat_history.mount(tool_calls_message)

            last_updated_message = None

            chat_history.scroll_end(animate=False)

            async for response in call_llm_async(
                messages=self.messages, tools=load_tools()
            ):
                if isinstance(response, UpdateSummary):
                    if response.content is not None:
                        assistant_message.append_token(response.content)
                        last_updated_message = assistant_message
                        loading_message.dismiss()

                    if response.reasoning_content is not None:
                        reasoning_message.append_token(response.reasoning_content)
                        last_updated_message = reasoning_message
                        loading_message.dismiss()

                    if response.tool_calls is not None:
                        last_updated_message = tool_calls_message
                        if not tool_calls_message.has_text():
                            tool_calls_message.append_token(
                                f"Calling tool: `{response.tool_calls.name}`, with arguments:\n\n"
                            )
                            loading_message.dismiss()

                        if response.tool_calls.arguments is not None:
                            tool_calls_message.append_token(
                                response.tool_calls.arguments
                            )

                elif isinstance(response, Response):
                    if response.usage is not None and response.timings is not None and last_updated_message is not None:
                        last_updated_message.update_usage(response.usage, response.timings)

                    self.messages.append(response.get_message())
                    finish_reason = response.get_finish_reason()

                    if (tool_call := response.has_tool_request()) is not None:
                        tool_calls_message.set_tool_call(tool_call)

                        if (
                            tool_call_result
                            := await tool_calls_message.wait_for_result()
                        ) is not None:
                            self.messages.append(tool_call_result)

                chat_history.scroll_end_if_autoscroll()

    def compose(self) -> ComposeResult:
        """
        Build the widget tree for the application.

        Returns
        -------
        The composed widgets: a ChatHistory and an InputGroup.
        """
        yield ChatHistory()
        yield InputGroup()
