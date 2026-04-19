from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ContentSwitcher, Input, Markdown, TextArea, DirectoryTree
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual import work

from chat_tui.chat_message import ChatMessage
from local_llm.request.request import call_llm_async
from local_llm.request.message import build_system_prompt
from local_llm.response.models import UpdateSummary, Response


class NotesApp(App):
    """
    A TUI application for writing and previewing markdown notes.
    """

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+n", "new_note", "New Note"),
        Binding("ctrl+r", "focus_filename", "Rename"),
        Binding("ctrl+e", "show_editor", "Edit", priority=True),
        Binding("ctrl+d", "show_preview", "View Preview", priority=True),
        Binding("ctrl+f", "show_files", "Browse Files", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    _current_path: Path | None = None

    async def on_mount(self) -> None:
        """
        Set the theme and widget border titles on startup.
        """
        self.theme = "catppuccin-mocha"
        self.query_one("#filename", Input).border_title = "Filename"
        self.query_one("#editor", TextArea).border_title = "Editor"
        self.query_one("#preview", VerticalScroll).border_title = "Preview"
        self.query_one("#file-tree", DirectoryTree).border_title = "Files"

        self.add_welcome_message()

    @work
    async def add_welcome_message(self) -> None:
        sidebar = self.query_one("#sidebar", Vertical)
        chat_message = ChatMessage(
            text="",
            role="assistant",
        )
        chat_message.mark_loading()
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

        async for response in call_llm_async(messages=messages):
            if isinstance(response, UpdateSummary):
                if response.content is not None:
                    chat_message.append_token(response.content)
            if isinstance(response, Response):
                chat_message.mark_complete()

    def compose(self) -> ComposeResult:
        """
        Compose the app layout.

        Returns
        -------
        The composed widgets for the application.
        """
        with Horizontal(id="columns"):
            with Vertical(id="main-column"):
                yield Input(placeholder="untitled.md", id="filename")
                with ContentSwitcher(initial="editor", id="main"):
                    yield TextArea(
                        language="markdown", id="editor", highlight_cursor_line=False
                    )
                    with VerticalScroll(id="preview"):
                        yield Markdown(id="preview-md")
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
        preview = self.query_one("#preview-md", Markdown)
        await preview.update(event.text_area.text)

    def action_show_editor(self) -> None:
        """
        Show the editor and focus it.
        """
        self.query_one("#main", ContentSwitcher).current = "editor"
        self.query_one("#editor", TextArea).focus()

    def action_show_preview(self) -> None:
        """
        Show the markdown preview and focus it.
        """
        self.query_one("#main", ContentSwitcher).current = "preview"
        self.query_one("#preview", VerticalScroll).focus()

    def action_show_files(self) -> None:
        """
        Show the file browser and focus it.
        """
        self.query_one("#main", ContentSwitcher).current = "file-tree"
        self.query_one("#file-tree", DirectoryTree).focus()

    def action_new_note(self) -> None:
        """
        Clear the editor and filename input to start a new note.
        """
        self._current_path = None
        self.query_one("#filename", Input).value = ""
        self.query_one("#editor", TextArea).load_text("")

        switcher = self.query_one("#main", ContentSwitcher)
        switcher.current = "editor"

        self.query_one("#editor", TextArea).focus()

    def action_focus_filename(self) -> None:
        """
        Focus the filename input.
        """
        self.query_one("#filename", Input).focus()

    async def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """
        Load the selected file into the editor and switch to the preview.

        Parameters
        ----------
        event
            The file selection event from the DirectoryTree.
        """
        self._current_path = event.path
        self.query_one("#filename", Input).value = event.path.name

        content = event.path.read_text()
        self.query_one("#editor", TextArea).load_text(content)

        await self.query_one("#preview-md", Markdown).update(content)

        switcher = self.query_one("#main", ContentSwitcher)
        switcher.current = "preview"

        self.query_one("#preview", VerticalScroll).focus()

    def action_save(self) -> None:
        """
        Save the current editor content to the file named in the filename input.

        If the filename has changed from the currently open file, the file is
        renamed before writing. New notes with no existing path are saved into
        the notes/ directory.
        """
        filename = self.query_one("#filename", Input).value.strip()
        if not filename:
            self.notify("Please enter a filename.", severity="error")
            return

        content = self.query_one("#editor", TextArea).text

        if self._current_path is not None:
            if self._current_path.name != filename:
                new_path = self._current_path.parent / filename
                self._current_path.rename(new_path)
                self._current_path = new_path
            self._current_path.write_text(content)

        else:
            save_path = Path("notes") / filename
            save_path.write_text(content)
            self._current_path = save_path

        self.notify(f"Saved {self._current_path.name}!")
