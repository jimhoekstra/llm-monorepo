---
description: "Align the active Python file with the project coding standards. Use when reviewing or fixing type hints, docstrings, string quoting, and explicitness in a Python file."
agent: "agent"
---

Update the currently active Python file to comply with the project's Python coding standards defined in [python-coding-standards](./../skills/python-coding-standards/SKILL.md).

Read the skill file first, then apply all required changes to the active Python file based on the checklist:

- All function and method signatures have complete, specific type hints
- Every function and method has a numpy-style docstring (no type info in docstrings)
- All strings use double quotes
- No implicit truthiness checks on non-boolean types
- Variables and parameters use clear, descriptive names
