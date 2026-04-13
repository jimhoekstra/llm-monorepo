from local_llm.response.models import Message


def build_system_prompt(prompt: str = "You are a helpful AI assistant.") -> Message:
    """
    Get the system prompt to send to the LLM.

    Parameters
    ----------
    prompt
        The system prompt string.

    Returns
    -------
    The system prompt as a Message object.
    """
    return _build_message(role="system", content=prompt)


def build_user_prompt(user_input: str) -> Message:
    """
    Build the user prompt to send to the LLM.

    Parameters
    ----------
    user_input
        The raw user input string.

    Returns
    -------
    The user prompt as a Message object.
    """
    return _build_message(role="user", content=user_input)


def _build_message(role: str, content: str) -> Message:
    """
    Build a Message with the given role and content.

    Parameters
    ----------
    role
        The role of the message sender (e.g. "system", "user").
    content
        The text content of the message.

    Returns
    -------
    The constructed Message object.
    """
    return Message(role=role, content=content)
