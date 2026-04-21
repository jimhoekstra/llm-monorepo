from typing import Callable
from enum import StrEnum

from pydantic import BaseModel


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    NULL = "null"


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str
    function: ToolCallFunction


class Message(BaseModel):
    role: str
    tool_call_id: str | None = None
    content: str
    tool_calls: list[ToolCall] | None = None


class ToolArgument(BaseModel):
    name: str
    description: str
    type: str
    items: str | None = None
    required: bool = True


class Tool(BaseModel):
    name: str
    description: str
    return_description: str
    arguments: list[ToolArgument]
    resolver: Callable[..., str]
    requires_approval: bool = False
