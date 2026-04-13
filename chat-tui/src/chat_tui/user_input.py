
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message as TextualMessage
from textual.widgets import TextArea
from textual.widget import Widget


from .chat_history import ChatHistory


class UserInput(TextArea):
    class Submitted(TextualMessage):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    BINDINGS = [Binding("ctrl+enter", "submit", "Submit", show=False)]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, highlight_cursor_line=False)

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self.text))
        self.clear()


class InputGroup(Widget):
    def on_user_input_submitted(self, message: UserInput.Submitted) -> None:
        self.app.query_one(ChatHistory).add_message(message.text, "user")

    def compose(self) -> ComposeResult:
        yield UserInput()
