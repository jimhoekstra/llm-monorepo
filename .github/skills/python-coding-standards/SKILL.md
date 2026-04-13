---
name: python-coding-standards
description: "Python coding standards for this project. Use when writing, reviewing, or refactoring Python code. Covers type hints, docstrings, string quoting, and explicitness conventions."
---

# Python Coding Standards

## When to Use
- Writing new Python functions, methods, or classes
- Reviewing or refactoring existing Python code
- Unsure which style convention to follow in Python files

## Standards

### Type Hints

Always annotate function signatures with type hints. Be as specific as possible — prefer concrete types over abstract ones.

**Do:**
```python
def get_note(name: str) -> str | None: ...
def process_items(items: list[str]) -> dict[str, int]: ...
def call_llm_async(messages: list[Message], tools: list[Tool]) -> AsyncIterator[Response | UpdateSummary]: ...
```

**Don't:**
```python
def get_note(name): ...
def process_items(items: list) -> dict: ...
def call_llm_async(messages, tools): ...
```

Prefer:
- `list[str]` over `List[str]` (no need to import from `typing` in Python 3.9+)
- `str | None` over `Optional[str]`
- `X | Y` union syntax over `Union[X, Y]`
- `Literal["a", "b"]` when only specific values are valid
- `TypeAlias`, `TypeVar`, `Protocol` for complex structural types

### Docstrings

Add a numpy-style docstring to every function and method. Omit type information from the docstring — it belongs in the signature only.

**Template:**
```python
def example(param1: str, param2: int = 0) -> list[str]:
    """
    Short one-line summary.

    Extended description if needed (optional). Can span
    multiple lines.

    Parameters
    ----------
    param1
        Description of param1.
    param2
        Description of param2. Defaults to 0.

    Returns
    -------
    Description of return value.

    Raises
    ------
    ValueError
        When this condition is violated.
    """
```

Omit sections that don't apply (e.g. no `Raises` if the function doesn't raise).

### String Quoting

Always use double quotes `"` for strings. Never use single quotes `'`.

```python
# Correct
name = "Alice"
message = f"Hello, {name}"

# Wrong
name = 'Alice'
```

If a string contains a double quote literal, use a backslash escape rather than switching to single quotes:
```python
label = "She said \"hello\""
```

### Explicitness

Prefer explicit over implicit:
- Name variables and parameters clearly — avoid single-letter names except in trivial loops (`i`, `j`) or well-known math contexts
- Avoid `*args` / `**kwargs` unless the function genuinely accepts arbitrary arguments
- Use named arguments at call sites when the meaning isn't obvious from position
- Avoid implicit truthiness checks on non-boolean types; prefer explicit comparisons:

```python
# Explicit
if items is not None and len(items) > 0:
if response.has_tool_request() is not None:

# Avoid
if items:
if response.has_tool_request():
```

- Prefer explicit return types, even for `None`-returning functions: `-> None`
- Import specific names rather than wildcard imports

## Checklist

Before finishing any Python code, verify:
- [ ] All function/method signatures have complete type hints
- [ ] Type hints are as specific as possible (no bare `list`, `dict`, `Any` without reason)
- [ ] Every function/method has a numpy-style docstring
- [ ] Docstrings do NOT include type information
- [ ] All strings use double quotes
- [ ] No implicit behaviours — logic is clear from reading the code
