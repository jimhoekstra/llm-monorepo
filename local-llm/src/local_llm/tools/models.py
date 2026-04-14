from typing import Callable

from pydantic import BaseModel


class ToolArgument(BaseModel):
    name: str
    description: str
    type: str
    required: bool = True


class Tool(BaseModel):
    name: str
    description: str
    return_description: str
    arguments: list[ToolArgument]
    fn: Callable[..., str]
    requires_approval: bool = False

    def to_json(self) -> dict:
        """
        Serialise the tool into a dict suitable for the API request body.

        Returns
        -------
        A dict containing the tool's name, description, return description, and argument specifications.
        """

        tool_description = (
            f"{self.description} This tool returns: {self.return_description}"
        )
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": tool_description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        arg.name: {
                            "type": arg.type,
                            "description": arg.description,
                        }
                        for arg in self.arguments
                    },
                    "required": [arg.name for arg in self.arguments if arg.required],
                },
            },
        }


class Description(str):
    """
    A description of a tool argument.
    """

    pass


class ToolCallResult(BaseModel):
    role: str = "tool"
    tool_call_id: str
    content: str

    def format(self) -> dict[str, str | list | None]:
        """
        Serialise the tool call result into a dict suitable for the API request body.

        Returns
        -------
        A dict with role, tool_call_id, and content fields.
        """
        assert self.role is not None

        return {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }
