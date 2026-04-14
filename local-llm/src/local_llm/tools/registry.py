from typing import Annotated, Callable, get_args, get_origin
from functools import wraps
from inspect import getdoc, signature, Parameter


from .models import Tool, ToolArgument, Description


PYTHON_TO_JSON_TYPE_MAP: dict[type, str] = {
    str: "string",
}


TOOL_REGISTRY: dict[str, Tool] = {}


def register_tool(description: str, requires_approval: bool = True) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """
    Decorator to register a function as a tool.

    Parameters
    ----------
    description
        A description of the tool's functionality, which will be included in the
        tool definition passed to the LLM.

    Returns
    -------
    A decorator that registers the decorated function as a tool.
    """

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        tool_name = fn.__name__

        if tool_name in TOOL_REGISTRY:
            raise ValueError(f"A tool named '{tool_name}' is already registered.")

        tool = Tool(
            name=tool_name,
            description=description,
            return_description=_get_function_return_description(fn),
            arguments=_get_function_signature(fn),
            fn=fn,
            requires_approval=requires_approval,
        )

        TOOL_REGISTRY[tool_name] = tool

        @wraps(fn)
        def wrapper(*args, **kwargs) -> str:
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def load_tools() -> list[dict]:
    """
    Return all registered tools serialised as JSON-compatible dicts.

    Returns
    -------
    A list of tool definition dicts, one per registered tool.
    """
    return [tool.to_json() for tool in TOOL_REGISTRY.values()]


def _get_function_signature(fn: Callable[..., str]) -> list[ToolArgument]:
    """
    Extract the tool arguments from a function's parameter annotations.

    Parameters
    ----------
    fn
        The function whose signature is to be inspected. Each parameter must be
        annotated with ``Annotated[<type>, Description(...)]``.

    Returns
    -------
    A list of ToolArgument objects derived from the function's parameters.

    Raises
    ------
    ValueError
        If any parameter lacks an ``Annotated`` annotation, has an unsupported
        type, or does not include a ``Description`` instance as its metadata.
    """
    sig = signature(fn)
    tool_arguments: list[ToolArgument] = []

    for parameter_name, parameter in sig.parameters.items():
        annotation = parameter.annotation

        if get_origin(annotation) is not Annotated:
            raise ValueError(
                f"Tool function parameters must be annotated with 'Annotated', "
                f"got {annotation} for parameter '{parameter_name}'."
            )

        args = get_args(annotation)
        if len(args) != 2:
            raise ValueError(
                f"Annotated type must have exactly two arguments, got {len(args)} for parameter '{parameter_name}'."
            )

        try:
            arg_type = PYTHON_TO_JSON_TYPE_MAP[args[0]]
        except KeyError:
            raise ValueError(
                f"Unsupported argument type '{args[0]}' for parameter '{parameter_name}'. "
                f"Supported types are: {list(PYTHON_TO_JSON_TYPE_MAP.keys())}."
            )

        description = args[1]
        if not isinstance(description, Description):
            raise ValueError(
                f"Annotated type's second argument must be a Description instance, got {type(description)} for parameter '{parameter_name}'."
            )

        tool_arguments.append(
            ToolArgument(
                name=parameter_name,
                description=str(description),
                type=arg_type,
                required=parameter.default is Parameter.empty,
            )
        )

    return tool_arguments


def _get_function_return_description(fn: Callable[..., str]) -> str:
    """
    Extract the return description from a function's signature.

    Parameters
    ----------
    fn
        The function whose return description is to be extracted.

    Returns
    -------
    The return description string.

    Raises
    ------
    ValueError
        If the function's return type annotation is not in the expected format.
    """
    return_annotation = signature(fn).return_annotation

    if get_origin(return_annotation) is not Annotated:
        raise ValueError(
            f"Tool function return type must be annotated with 'Annotated', got {return_annotation}."
        )

    args = get_args(return_annotation)
    if len(args) != 2:
        raise ValueError(
            f"Annotated return type must have exactly two arguments, got {len(args)}."
        )

    if not isinstance(args[1], Description):
        raise ValueError(
            f"Annotated return type's second argument must be a Description instance, got {type(args[1])}."
        )

    return str(args[1])
