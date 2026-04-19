from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message as TextualMessage
from textual.widgets import TextArea
from textual.widget import Widget

from .chat_history import ChatHistory
from .chat_message import ChatMessage


class UserInput(TextArea):
    class Submitted(TextualMessage):
        def __init__(self, text: str) -> None:
            """
            Create a Submitted message.

            Parameters
            ----------
            text
                The submitted text content.
            """
            super().__init__()
            self.text = text

    BINDINGS = [Binding("ctrl+enter", "submit", "Submit", show=False)]

    def __init__(self) -> None:
        """
        Initialise the UserInput TextArea with cursor line highlighting disabled.
        """
        super().__init__(highlight_cursor_line=False)

    def action_submit(self) -> None:
        """
        Post a Submitted message with the current text and clear the input.
        """
        self.post_message(self.Submitted(self.text))
        self.clear()


class InputGroup(Widget):
    _last_user_message: ChatMessage | None = None

    def on_user_input_submitted(self, message: UserInput.Submitted) -> None:
        """
        Handle a submitted user input by appending it to the chat history.

        Parameters
        ----------
        message
            The submitted message containing the user's text.
        """
        self._last_user_message = self.app.query_one(ChatHistory).add_message(message.text, "user")
        self._last_user_message.mark_loading()

    def compose(self) -> ComposeResult:
        """
        Compose the input group widget.

        Returns
        -------
        The composed widgets for this input group.
        """
        yield UserInput()

    def mark_last_user_message_complete(self) -> None:
        """
        Mark the last user message as complete, stopping any loading animation.
        If there is no last user message, this method does nothing.
        """
        if self._last_user_message is not None:
            self._last_user_message.mark_complete()
