import asyncio
import json
import uuid
from typing import AsyncIterator, Iterator

import requests
import aiohttp

from local_llm.tools.models import ToolCallResult
from local_llm.response.models import Chunk, Message, Response, UpdateSummary


def call_llm(
    messages: list[Message | ToolCallResult], tools: list[dict] = []
) -> Iterator[Response | UpdateSummary]:
    """
    Call the LLM API and stream back incremental updates followed by the final response.

    Parameters
    ----------
    messages
        The conversation history, including any prior tool call results.
    tools
        A list of tool definition dicts available to the LLM.

    Yields
    ------
    An UpdateSummary for each streamed delta, then the final Response once complete.
    """
    response = requests.post(
        "http://localhost:8080/v1/chat/completions",
        json=_build_request_body(messages, tools),
        stream=True,
    )
    response.raise_for_status()

    collected_response: Response | None = None

    for chunk in _chunks(response):
        if collected_response is None:
            collected_response = Response.from_chunk(chunk)
        else:
            update_summary = collected_response.update_from_chunk(chunk)
            yield update_summary

    assert collected_response is not None
    yield collected_response


async def call_llm_async(
    messages: list[Message | ToolCallResult] | list[Message],
    tools: list[dict] = [],
    session: aiohttp.ClientSession | None = None,
) -> AsyncIterator[UpdateSummary | Response]:
    """
    Call the LLM API asynchronously and stream back incremental updates followed by the final response.

    Parameters
    ----------
    messages
        The conversation history, including any prior tool call results.
    tools
        A list of tool definition dicts available to the LLM.
    session
        An optional aiohttp.ClientSession to use for the request. If None, a
        new session is created and closed after the request completes.

    Yields
    ------
    An UpdateSummary for each streamed delta, then the final Response once complete.
    """
    if session is not None:
        async for item in _call_llm_async_with_session(messages, tools, session):
            yield item
    else:
        async with aiohttp.ClientSession() as new_session:
            async for item in _call_llm_async_with_session(messages, tools, new_session):
                yield item


async def _call_llm_async_with_session(
    messages: list[Message | ToolCallResult] | list[Message],
    tools: list[dict],
    session: aiohttp.ClientSession,
) -> AsyncIterator[UpdateSummary | Response]:
    """
    Perform the LLM API request using the provided session.

    Parameters
    ----------
    messages
        The conversation history, including any prior tool call results.
    tools
        A list of tool definition dicts available to the LLM.
    session
        The aiohttp.ClientSession to use for the request.

    Yields
    ------
    An UpdateSummary for each streamed delta, then the final Response once complete.
    """
    async with session.post(
        "http://localhost:8080/v1/chat/completions",
        json=_build_request_body(messages, tools),
    ) as response:
        response.raise_for_status()

        collected_response: Response | None = None

        async for chunk in _chunks_async(response):
            if collected_response is None:
                collected_response = Response.from_chunk(chunk)
            else:
                update_summary = collected_response.update_from_chunk(chunk)
                yield update_summary

        assert collected_response is not None
        yield collected_response


def _build_request_body(
    messages: list[Message | ToolCallResult] | list[Message], tools: list[dict]
) -> dict:
    """
    Build the request body to send to the LLM API.

    Parameters
    ----------
    messages
        A list of Message objects representing the conversation history.
    tools
        A list of tool definition dicts.

    Returns
    -------
    dict
        The request body as a dict.
    """
    return {
        "messages": [message.format() for message in messages],
        "tools": tools,
        "stream": True,
        "stream_options": {
            "include_usage": True,
        },
        "n": 1,
    }


def _chunks(response: requests.Response) -> Iterator[Chunk]:
    """
    Parse a streaming HTTP response into Chunk objects.

    Parameters
    ----------
    response
        The streaming response from the LLM API.

    Yields
    ------
    Each parsed chunk from the server-sent events stream.
    """
    for line in response.iter_lines():
        if not line:
            continue

        decoded_line = line.decode("utf-8")
        if not decoded_line.startswith("data: "):
            continue

        data_str = decoded_line[len("data: ") :]
        if data_str == "[DONE]":
            break

        data_json = json.loads(data_str)
        chunk = Chunk.model_validate(data_json)
        yield chunk


async def _chunks_async(response: aiohttp.ClientResponse) -> AsyncIterator[Chunk]:
    """
    Parse an async streaming HTTP response into Chunk objects.

    Parameters
    ----------
    response
        The streaming aiohttp response from the LLM API.

    Yields
    ------
    Each parsed chunk from the server-sent events stream.
    """
    async for raw_line in response.content:
        line = raw_line.strip()
        if not line:
            continue

        decoded_line = line.decode("utf-8")
        if not decoded_line.startswith("data: "):
            continue

        data_str = decoded_line[len("data: "):]
        if data_str == "[DONE]":
            break

        data_json = json.loads(data_str)
        chunk = Chunk.model_validate(data_json)
        yield chunk


class AsyncLLMRequest:

    messages: list[Message | ToolCallResult] | list[Message]
    tools: list[dict]
    is_finished: bool
    response: Response | None
    _session: aiohttp.ClientSession | None
    _task: asyncio.Task[None] | None
    _queue: asyncio.Queue[UpdateSummary | None]

    def __init__(
        self,
        messages: list[Message | ToolCallResult] | list[Message],
        tools: list[dict],
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """
        Parameters
        ----------
        messages
            The conversation history, including any prior tool call results.
        tools
            A list of tool definition dicts available to the LLM.
        session
            An optional shared aiohttp.ClientSession. If None, a new session
            is created per request.
        """
        self.messages = messages
        self.tools = tools
        self.is_finished = False
        self.response = None
        self._session = session
        self._task = None
        self._queue = asyncio.Queue()

    def start(self) -> None:
        """
        Dispatch the LLM request as a background asyncio task.

        Call this once to begin streaming. Use pop_updates() to retrieve
        incremental updates, and check is_finished / response when done.
        """
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """
        Run the async LLM request, collecting updates and the final response.
        """
        async for item in call_llm_async(self.messages, self.tools, session=self._session):
            if isinstance(item, UpdateSummary):
                await self._queue.put(item)
            elif isinstance(item, Response):
                self.response = item
        
        self.is_finished = True
        await self._queue.put(None)

    def __aiter__(self) -> "AsyncLLMRequest":
        """
        Return self as an async iterator over streamed updates.
        """
        return self

    async def __anext__(self) -> UpdateSummary:
        """
        Yield the next UpdateSummary as soon as it is available.

        Raises
        ------
        StopAsyncIteration
            When the request has finished and all updates have been consumed.
        """
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


class LLMRequestQueue:

    _requests: dict[uuid.UUID, AsyncLLMRequest]
    _session: aiohttp.ClientSession | None

    def __init__(self) -> None:
        self._requests = {}
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        """
        Close the shared aiohttp.ClientSession.
        """
        if self._session is not None:
            await self._session.close()
            self._session = None

    def add_request(self, request: AsyncLLMRequest) -> uuid.UUID:
        """
        Add a new AsyncLLMRequest to the queue and return its key.

        Parameters
        ----------
        request
            The AsyncLLMRequest to add to the queue.

        Returns
        -------
        A UUID key that can be used to retrieve the request later.
        """
        key = uuid.uuid4()
        self._requests[key] = request
        request.start()
        return key

    def create_request(
        self,
        messages: list[Message | ToolCallResult] | list[Message],
        tools: list[dict] = [],
    ) -> uuid.UUID:
        """
        Create an AsyncLLMRequest using the shared session, add it to the queue,
        and return its key.

        Parameters
        ----------
        messages
            The conversation history, including any prior tool call results.
        tools
            A list of tool definition dicts available to the LLM.

        Returns
        -------
        A UUID key that can be used to retrieve the request later.
        """
        request = AsyncLLMRequest(messages, tools, session=self._session)
        return self.add_request(request)

    def get_request(self, key: uuid.UUID) -> AsyncLLMRequest:
        """
        Return the AsyncLLMRequest associated with the given key.

        Parameters
        ----------
        key
            The UUID key returned by add_request or create_request.

        Returns
        -------
        The AsyncLLMRequest for the given key.

        Raises
        ------
        KeyError
            If no request exists for the given key.
        """
        return self._requests[key]
