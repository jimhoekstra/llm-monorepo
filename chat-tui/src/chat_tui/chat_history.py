
from textual.containers import ScrollableContainer


from .chat_message import ChatMessage


class ChatHistory(ScrollableContainer):
    """Scrollable container that accumulates chat messages."""

    _current_index: int = -1
    _autoscroll: bool = True

    def add_message(self, text: str, role: str) -> None:
        """Append a message. role should be 'user' or 'assistant'."""
        self.mount(ChatMessage(text, role))
        self.scroll_end_if_autoscroll()

    def scroll_end_if_autoscroll(self) -> None:
        if self._autoscroll:
            self.scroll_end(animate=False)
