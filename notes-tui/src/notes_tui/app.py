from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ContentSwitcher, Markdown, TextArea, DirectoryTree
from textual.containers import Horizontal, Vertical
from textual import work

from chat_tui.chat_message import ChatMessage
from local_llm.request.request import call_llm_async
from local_llm.request.message import build_system_prompt
from local_llm.response.models import UpdateSummary


class NotesApp(App):
    """
    A TUI application for writing and previewing markdown notes.
    """

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+d", "toggle_preview", "View Preview", priority=True),
        Binding("ctrl+f", "toggle_files", "Browse Files", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    async def on_mount(self) -> None:
        """
        Set the theme and widget border titles on startup.
        """
        self.theme = "catppuccin-mocha"
        self.query_one("#editor", TextArea).border_title = "Editor"
        self.query_one("#preview", Markdown).border_title = "Preview"
        self.query_one("#file-tree", DirectoryTree).border_title = "Files"

        self.add_welcome_message()

    @work
    async def add_welcome_message(self) -> None:
        sidebar = self.query_one("#sidebar", Vertical)
        chat_message = ChatMessage(
                text="",
                role="assistant",
            )
        sidebar.mount(chat_message)

        messages = [
            build_system_prompt(
                prompt="You are a helpful assistant that provides a motivating "
                "welcome message to users when they log in to their notes app for "
                "the first time each day. When providing the welcome message, do not "
                "show multiple options but provide a single, concise message. This "
                "conversation marks the user's first interaction with their notes "
                "app today."
            ),
        ]

        async for response in call_llm_async(
                messages=messages  # type: ignore
            ):
                if isinstance(response, UpdateSummary):
                    if response.content is not None:
                        chat_message.append_token(response.content)


    def compose(self) -> ComposeResult:
        """
        Compose the app layout.

        Returns
        -------
        The composed widgets for the application.
        """
        with Horizontal(id="columns"):
            with ContentSwitcher(initial="editor", id="main"):
                yield TextArea(language="markdown", id="editor")
                yield Markdown(id="preview")
                yield DirectoryTree("notes", id="file-tree")
            
            yield Vertical(id="sidebar")

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """
        Update the markdown preview whenever the editor content changes.

        Parameters
        ----------
        event
            The change event from the TextArea.
        """
        preview = self.query_one("#preview", Markdown)
        await preview.update(event.text_area.text)

    def action_toggle_preview(self) -> None:
        """
        Toggle between the editor and the markdown preview.
        """
        switcher = self.query_one("#main", ContentSwitcher)
        if switcher.current == "editor":
            switcher.current = "preview"
        else:
            switcher.current = "editor"
            self.query_one("#editor", TextArea).focus()

    def action_toggle_files(self) -> None:
        """
        Toggle the file browser, showing the notes directory tree.
        """
        switcher = self.query_one("#main", ContentSwitcher)
        if switcher.current == "file-tree":
            switcher.current = "editor"
            self.query_one("#editor", TextArea).focus()
        else:
            switcher.current = "file-tree"
            self.query_one("#file-tree", DirectoryTree).focus()

    def action_save(self) -> None:
        """
        Save the current note content to note.md in the working directory.
        """
        # TODO: Implement file saving logic
        # editor = self.query_one("#editor", TextArea)
        # Path("note.md").write_text(editor.text)
        self.notify("Saved note!")
