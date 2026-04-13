from pathlib import Path

from textual.app import App, ComposeResult
from textual import work

from local_llm.request import call_llm_async, build_system_prompt, build_user_prompt
from local_llm.response.models import (
    Response,
    UpdateSummary,
    Message,
)
from local_llm.tools import ToolCallResult, load_tools

from .chat_history import ChatHistory
from .chat_message import ChatMessage, ToolCallChatMessage
from .user_input import UserInput, InputGroup


class ChatApp(App):
    CSS_PATH = "styles.tcss"
    messages: list[Message | ToolCallResult]

    def on_mount(self) -> None:
        self.theme = "catppuccin-mocha"
        self.messages = [
            build_system_prompt(prompt=(Path(__file__).resolve().parent / "prompts" / "system.md").read_text())
        ]

    def on_user_input_submitted(self, message: UserInput.Submitted) -> None:
        self.stream_reply(message.text)

    @work
    async def stream_reply(self, user_text: str) -> None:
        chat_history = self.query_one(ChatHistory)

        self.messages.append(build_user_prompt(user_text))
        finish_reason = None

        while finish_reason not in {"stop"}:
            reasoning_message = ChatMessage("", "reasoning")
            reasoning_message.display = False
            await chat_history.mount(reasoning_message)

            assistant_message = ChatMessage("", "assistant")
            await chat_history.mount(assistant_message)

            tool_calls_message = ToolCallChatMessage("", "tool-call")
            tool_calls_message.display = False
            await chat_history.mount(tool_calls_message)

            chat_history.scroll_end(animate=False)

            async for response in call_llm_async(
                messages=self.messages, tools=load_tools()
            ):  # type: ignore
                if isinstance(response, UpdateSummary):
                    if response.content is not None:
                        assistant_message.append_token(response.content)

                    if response.reasoning_content is not None:
                        reasoning_message.append_token(response.reasoning_content)

                    if response.tool_calls is not None:
                        if not tool_calls_message.has_text():
                            tool_calls_message.append_token(
                                f"Calling tool: `{response.tool_calls.name}`, with arguments:\n"
                            )

                        if response.tool_calls.arguments is not None:
                            tool_calls_message.append_token(
                                f"```json\n{response.tool_calls.arguments}\n```"
                            )

                elif isinstance(response, Response):
                    if response.usage is not None and response.timings is not None:
                        assistant_message.update_usage(response.usage, response.timings)

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
        yield ChatHistory()
        yield InputGroup()
