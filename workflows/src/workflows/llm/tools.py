import json

from .models import Tool, Message, ToolCall
from workflows.utils.user_input import confirm


def tool_to_json(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": f"{tool.description} This tool returns: {tool.return_description}",
            "parameters": {
                "type": "object",
                "properties": {
                    arg.name: {
                        "type": arg.type,
                        "description": arg.description,
                        **(({"items": {"type": arg.items}}) if arg.items is not None else {}),
                    }
                    for arg in tool.arguments
                },
                "required": [arg.name for arg in tool.arguments if arg.required],
            },
        },
    }


def _find_tool(tools: list[Tool], tool_name: str) -> Tool | None:
    for tool in tools:
        if tool.name == tool_name:
            return tool
    return None


def call_tool(tool_call: ToolCall, tools: list[Tool]) -> Message:
    tool = _find_tool(tools, tool_call.function.name)
    if tool is None:
        raise ValueError(f"Tool '{tool_call.function.name}' not found.")
    
    arguments = json.loads(tool_call.function.arguments)
    
    # Assert that all required arguments are present
    for arg in tool.arguments:
        if arg.required and arg.name not in arguments:
            raise ValueError(f"Missing required argument '{arg.name}' for tool '{tool.name}'.")
        
    # Assert that only expected arguments are present
    for arg_name in arguments.keys():
        if arg_name not in [arg.name for arg in tool.arguments]:
            raise ValueError(f"Unexpected argument '{arg_name}' for tool '{tool.name}'.")

    if tool.requires_approval:
        approved = confirm(f"Approve tool call '[underline]{tool.name}[/underline]' with arguments: [dim]{arguments}[/dim] ?")
        if not approved:
            raise ValueError(f"Tool call '{tool.name}' was not approved.")

    tool_result = tool.resolver(**arguments)
    return Message(
        role="tool",
        tool_call_id=tool_call.id,
        content=tool_result,
    )
