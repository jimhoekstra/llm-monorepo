import asyncio
from datetime import datetime, timezone

from rich import print as rprint
from rich.progress import Progress

from workflows.llm import LLMRequestQueue, Message, Tool, FinishReason, ToolArgument
from workflows.utils.user_input import ask_choices, confirm_str


def get_current_time() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


TOOLS = [
    Tool(
        name="get_current_time",
        description="Get the current time in ISO 8601 format.",
        return_description="The current time in ISO 8601 format.",
        arguments=[],
        resolver=get_current_time,
    ),
    Tool(
        name="ask_user_confirmation",
        description="Ask the user to confirm something with a yes or no question.",
        return_description="Whether the user confirmed or not.",
        arguments=[
            ToolArgument(
                name="prompt",
                description="The yes or no question to ask the user.",
                type="string",
            ),
        ],
        resolver=confirm_str,
    ),
    Tool(
        name="ask_user_to_choose",
        description="Ask the user to choose from a list of options.",
        return_description="The option chosen by the user.",
        arguments=[
            ToolArgument(
                name="prompt",
                description="The question to ask the user.",
                type="string",
            ),
            ToolArgument(
                name="choices",
                description="The list of choices to present to the user.",
                type="array",
                items="string",
            ),
        ],
        resolver=ask_choices,
    )
]


async def main():
    async with LLMRequestQueue() as queue:
        messages: list[Message] = [
            Message(
                role="system",
                content="You are a helpful assistant.",
            ),
            Message(
                role="user",
                content="Hello! What time is it? Please reply in HH:MM format using 24h time.",
            )
        ]

        finish_reason = FinishReason.NULL
        llm_response = None

        while finish_reason != FinishReason.STOP:
            request_id = queue.create_request(
                messages=messages,
                tools=TOOLS,
            )

            with Progress() as progress:
                task = progress.add_task("[dim]Waiting for AI...[/dim]", total=None)
                while not queue.get_request(request_id).is_finished():
                    await asyncio.sleep(0.1)
                    progress.advance(task)

                progress.remove_task(task)

            request = queue.get_request(request_id)
            if request._task is not None and (exception := request._task.exception()) is not None:
                raise exception

            llm_response = request.extract_message()
            finish_reason = request.get_finish_reason()

            messages.append(llm_response)
            if finish_reason == FinishReason.TOOL_CALLS:
                messages.extend(request.call_tools_from_response())
        
        rprint(llm_response)


if __name__ == "__main__":
    asyncio.run(main())
