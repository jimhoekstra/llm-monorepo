import json
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
    messages: list[Message | ToolCallResult] | list[Message], tools: list[dict] = []
) -> AsyncIterator[UpdateSummary | Response]:
    """
    Call the LLM API asynchronously and stream back incremental updates followed by the final response.

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
    async with aiohttp.ClientSession() as session:
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
