import uuid
import asyncio

import aiohttp
from .models import Message, Tool, FinishReason
from .tools import tool_to_json, call_tool


COMPLETIONS_URL = "http://localhost:8080/v1/chat/completions"


async def call_llm_async_with_session(
    messages: list[Message],
    tools: list[Tool],
    session: aiohttp.ClientSession,
) -> dict:
    async with session.post(
        COMPLETIONS_URL,
        json={
            "messages": [message.model_dump(exclude_none=True) for message in messages],
            "tools": [tool_to_json(tool) for tool in tools],
        },
        headers={"Connection": "close"},
    ) as response:
        response.raise_for_status()
        return await response.json()


class AsyncLLMRequest:
    messages: list[Message]
    tools: list[Tool]
    _response: dict | None
    _is_finished: bool
    _session: aiohttp.ClientSession
    _task: asyncio.Task[None] | None

    def __init__(
        self,
        messages: list[Message],
        tools: list[Tool],
        session: aiohttp.ClientSession,
    ) -> None:
        self.messages = messages
        self.tools = tools
        self._response = None
        self._is_finished = False
        self._session = session
        self._task = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        else:
            raise RuntimeError("Request has already been started.")

    async def _run(self) -> None:
        try:
            self._response = await call_llm_async_with_session(
                self.messages,
                self.tools,
                self._session,
            )
        
        finally:
            self._is_finished = True

    def is_finished(self) -> bool:
        return self._is_finished
    
    def get_response(self) -> dict:
        if not self._is_finished:
            raise RuntimeError("Request is not finished yet.")
        assert self._response is not None
        return self._response
    
    def _extract_first_choice(self) -> dict:
        response = self.get_response()
        assert "choices" in response and len(response["choices"]) == 1
        return response["choices"][0]
    
    def extract_message(self) -> Message:
        first_choice = self._extract_first_choice()
        assert "message" in first_choice
        return Message.model_validate(first_choice["message"])
    
    def get_finish_reason(self) -> FinishReason:
        first_choice = self._extract_first_choice()
        assert "finish_reason" in first_choice
        finish_reason = first_choice["finish_reason"]
        return FinishReason(finish_reason)
    
    def call_tools_from_response(self) -> list[Message]:
        message = self.extract_message()

        assert self.get_finish_reason() == FinishReason.TOOL_CALLS
        if message.tool_calls is None or len(message.tool_calls) == 0:
            raise RuntimeError("LLM indicated tool calls but no tool calls found in message.")
        
        tool_call_result_messages: list[Message] = []
        for tool_call in message.tool_calls:
            tool_response = call_tool(tool_call, self.tools)
            tool_call_result_messages.append(tool_response)

        return tool_call_result_messages
    
    def call_tools_and_build_next_request(self) -> "AsyncLLMRequest":
        return AsyncLLMRequest(
            messages=self.messages + [self.extract_message()] + self.call_tools_from_response(),
            tools=self.tools,
            session=self._session,
        )


class LLMRequestQueue:
    _requests: dict[uuid.UUID, AsyncLLMRequest]
    _session: aiohttp.ClientSession

    def __init__(self) -> None:
        self._requests = {}
        self._session = aiohttp.ClientSession()
    
    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def __aenter__(self) -> "LLMRequestQueue":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def add_request(self, request: AsyncLLMRequest) -> uuid.UUID:
        key = uuid.uuid4()
        self._requests[key] = request
        request.start()
        return key

    def create_request(
        self,
        messages: list[Message],
        tools: list[Tool] = [],
    ) -> uuid.UUID:
        request = AsyncLLMRequest(messages, tools, session=self._session)
        return self.add_request(request)

    def get_request(self, key: uuid.UUID) -> AsyncLLMRequest:
        return self._requests[key]
