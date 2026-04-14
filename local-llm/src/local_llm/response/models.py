import json

from pydantic import BaseModel

from local_llm.tools.call import call_tool, ToolCallResult, tool_requires_approval


class ToolCallUpdate(BaseModel):
    name: str
    arguments: str | None = None


class UpdateSummary(BaseModel):
    finish_reason: str | None = None
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: ToolCallUpdate | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Timings(BaseModel):
    cache_n: int
    prompt_n: int
    prompt_ms: float
    prompt_per_token_ms: float
    prompt_per_second: float
    predicted_n: int
    predicted_ms: float
    predicted_per_token_ms: float
    predicted_per_second: float


class ToolCallFunctionChunk(BaseModel):
    name: str | None = None
    arguments: str


class ToolCallFunction(BaseModel):
    name: str
    arguments: str

    @classmethod
    def from_chunk(
        cls, tool_call_function_chunk: ToolCallFunctionChunk
    ) -> "ToolCallFunction":
        assert tool_call_function_chunk.name is not None
        return cls(
            name=tool_call_function_chunk.name,
            arguments=tool_call_function_chunk.arguments,
        )

    def append_to_arguments(self, arguments: str) -> None:
        self.arguments += arguments


class ToolCallChunk(BaseModel):
    id: str | None = None
    index: int
    type: str | None = None
    function: ToolCallFunctionChunk


class ToolCall(BaseModel):
    id: str
    index: int
    type: str
    function: ToolCallFunction | None = None

    @classmethod
    def from_chunk(cls, tool_call_chunk: ToolCallChunk) -> "ToolCall":
        assert tool_call_chunk.id is not None
        assert tool_call_chunk.type is not None
        return cls(
            id=tool_call_chunk.id,
            index=tool_call_chunk.index,
            type=tool_call_chunk.type,
            function=ToolCallFunction.from_chunk(tool_call_chunk.function),
        )

    def update_from_chunk(self, tool_call: ToolCallChunk) -> ToolCallUpdate | None:
        if tool_call.function is None:
            return None

        if self.function is None:
            self.function = ToolCallFunction.from_chunk(tool_call.function)
            return ToolCallUpdate(
                name=self.function.name,
                arguments=self.function.arguments,
            )

        self.function.append_to_arguments(tool_call.function.arguments)
        return ToolCallUpdate(
            name=self.function.name,
            arguments=tool_call.function.arguments,
        )
    
    def requires_approval(self) -> bool:
        if self.function is None:
            return True
        
        return tool_requires_approval(self.function.name)
    
    def call(self) -> ToolCallResult:
        if self.function is None:
            return ToolCallResult(
                tool_call_id=self.id,
                content="Error: Tool call function is not fully specified.",
            )
    
        try:
            tool_call_args = json.loads(self.function.arguments)
        except json.JSONDecodeError:
            return ToolCallResult(
                tool_call_id=self.id,
                content="Error: Tool call arguments are not valid JSON.",
            )

        try:
            call_tool_result = call_tool(
                name=self.function.name,
                args=tool_call_args,
                tool_call_id=self.id,
            )

            return call_tool_result
        
        except ValueError as e:
            return ToolCallResult(
                tool_call_id=self.id,
                content=f"Error calling tool.",
            )
        
    def reject(self) -> ToolCallResult:
        return ToolCallResult(
            tool_call_id=self.id,
            content=f"Tool call rejected by user.",
        )


class ChunkChoiceDelta(BaseModel):
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCallChunk] | None = None


class ChoiceChunk(BaseModel):
    finish_reason: str | None = None
    index: int
    delta: ChunkChoiceDelta | None = None

    def get_updated_content(self) -> str | None:
        if self.delta is None:
            return None
        return self.delta.content

    def get_updated_reasoning_content(self) -> str | None:
        if self.delta is None:
            return None
        return self.delta.reasoning_content

    def get_updated_tool_calls(self) -> list[ToolCallChunk] | None:
        if self.delta is None:
            return None
        return self.delta.tool_calls


class Choice(BaseModel):
    finish_reason: str | None = None
    index: int
    message: "Message | None" = None

    def update_from_chunk(self, choice_chunk: "ChoiceChunk") -> UpdateSummary:
        if self.message is None:
            self.message = Message.from_chunk(choice_chunk)
            # TODO
            return UpdateSummary()

        self.finish_reason = choice_chunk.finish_reason

        if (updated_content := choice_chunk.get_updated_content()) is not None:
            self.message.append_to_content(updated_content)
            return UpdateSummary(
                finish_reason=self.finish_reason, content=updated_content
            )

        if (
            updated_reasoning_content := choice_chunk.get_updated_reasoning_content()
        ) is not None:
            self.message.append_to_reasoning_content(updated_reasoning_content)
            return UpdateSummary(
                finish_reason=self.finish_reason,
                reasoning_content=updated_reasoning_content,
            )

        if (updated_tool_calls := choice_chunk.get_updated_tool_calls()) is not None:
            tool_call_update = self.message.update_tool_calls(updated_tool_calls)
            return UpdateSummary(
                finish_reason=self.finish_reason, tool_calls=tool_call_update
            )

        # TODO
        return UpdateSummary(finish_reason=self.finish_reason)

    def has_tool_request(self) -> ToolCall | None:
        if self.finish_reason != "tool_calls":
            return None

        assert (
            self.message is not None
            and self.message.tool_calls is not None
            and len(self.message.tool_calls) == 1
        )
        return self.message.tool_calls[0]


class Chunk(BaseModel):
    id: str
    object: str
    created: int
    choices: list[ChoiceChunk]
    model: str
    system_fingerprint: str
    timings: Timings | None = None
    usage: TokenUsage | None = None


class Message(BaseModel):
    role: str
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None

    @classmethod
    def from_chunk(cls, choice_chunk: ChoiceChunk) -> "Message":
        content = choice_chunk.get_updated_content()
        reasoning_content = choice_chunk.get_updated_reasoning_content()

        return cls(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
            # TODO: add tool calls here?
            # tool_calls=tool_calls,
        )

    def append_to_content(self, content: str) -> None:
        self.content = (self.content or "") + content

    def append_to_reasoning_content(self, reasoning_content: str) -> None:
        self.reasoning_content = (self.reasoning_content or "") + reasoning_content

    def update_tool_calls(
        self, tool_calls: list[ToolCallChunk]
    ) -> ToolCallUpdate | None:
        if len(tool_calls) != 1 and tool_calls[0].index != 0:
            return None

        if self.tool_calls is None:
            new_tool_call = ToolCall.from_chunk(tool_calls[0])
            self.tool_calls = [new_tool_call]

            assert new_tool_call.function is not None
            return ToolCallUpdate(
                name=new_tool_call.function.name,
                arguments=new_tool_call.function.arguments,
            )

        return self.tool_calls[0].update_from_chunk(tool_calls[0])

    def format(self) -> dict[str, str | list | None]:
        assert self.role is not None

        tool_calls = None
        if self.tool_calls is not None:
            tool_calls = [
                tool_call.model_dump(exclude={"index"}) for tool_call in self.tool_calls
            ]

        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": tool_calls,
        }


class Response(Chunk):
    id: str
    object: str
    created: int
    choices: list[Choice]
    model: str
    system_fingerprint: str
    timings: Timings | None = None
    usage: TokenUsage | None = None

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> "Response":
        chunk_content = chunk.model_dump()
        chunk_content["choices"] = [
            Choice(
                finish_reason=choice_chunk.finish_reason,
                index=choice_chunk.index,
                message=Message.from_chunk(choice_chunk),
            )
            for choice_chunk in chunk.choices
        ]

        return cls.model_validate(chunk_content)

    def update_from_chunk(self, chunk: Chunk) -> UpdateSummary:
        if chunk.timings is not None:
            self.timings = chunk.timings

        if chunk.usage is not None:
            self.usage = chunk.usage

        if len(chunk.choices) != 1 or len(self.choices) != 1:
            return UpdateSummary()

        return self.choices[0].update_from_chunk(chunk.choices[0])

    def get_finish_reason(self) -> str | None:
        assert len(self.choices) == 1
        return self.choices[0].finish_reason

    def get_message(self) -> "Message":
        assert len(self.choices) == 1
        choice = self.choices[0]
        message = choice.message
        assert message is not None
        return message

    def has_tool_request(self) -> None | ToolCall:
        assert len(self.choices) == 1
        return self.choices[0].has_tool_request()
