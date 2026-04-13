from .registry import TOOL_REGISTRY
from .models import ToolCallResult


def call_tool(name: str, args: dict, tool_call_id: str) -> ToolCallResult:
    """
    Call a registered tool by name with the given arguments.

    Parameters
    ----------
    name
        The name of the tool to call.
    args
        A dict of arguments to pass to the tool function.
    tool_call_id
        The unique identifier for this tool call, used for tracking in the conversation history.

    Returns
    -------
    The result of the tool function call as a ToolCallResult.

    Raises
    ------
    ValueError
        If the tool name is not registered or if the arguments are invalid.
    """
    if name not in TOOL_REGISTRY:
        raise ValueError(f"No tool registered with name '{name}'.")

    tool = TOOL_REGISTRY[name]
    required_args = {arg.name for arg in tool.arguments if arg.required}
    all_required_args_present = (
        required_args.intersection(set(args.keys())) == required_args
    )

    if not all_required_args_present:
        raise ValueError(
            f"Missing required arguments for tool '{name}'. Required arguments are: {required_args}."
        )

    allowed_args = {arg.name for arg in tool.arguments}
    no_extra_args_present = set(args.keys()).issubset(allowed_args)

    if not no_extra_args_present:
        raise ValueError(
            f"Received unexpected arguments for tool '{name}'. Allowed arguments are: {allowed_args}."
        )

    result = tool.fn(**args)
    return ToolCallResult(
        role="tool",
        tool_call_id=tool_call_id,
        content=result,
    )
