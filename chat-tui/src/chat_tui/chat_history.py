from textual.containers import ScrollableContainer

from .chat_message import ChatMessage


class ChatHistory(ScrollableContainer):
    """Scrollable container that accumulates chat messages."""

    _current_index: int = -1
    _autoscroll: bool = True

    def add_message(self, text: str, role: str) -> ChatMessage:
        """
        Append a new chat message to the history.

        Parameters
        ----------
        text
            The message content.
        role
            The role of the message sender, e.g. "user" or "assistant".

        Returns
        -------
        The ChatMessage widget that was mounted.
        """
        message = ChatMessage(text, role)
        self.mount(message)
        self.scroll_end_if_autoscroll()
        return message

    def scroll_end_if_autoscroll(self) -> None:
        """
        Scroll to the bottom of the history if autoscroll is enabled.
        """
        if self._autoscroll:
            self.scroll_end(animate=False)
