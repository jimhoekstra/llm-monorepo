from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ContentSwitcher, Markdown, TextArea, Label
from textual.containers import Horizontal


class NotesApp(App):
    """
    A TUI application for writing and previewing markdown notes.
    """

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+d", "toggle_preview", "View Preview", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        """
        Set the theme and widget border titles on startup.
        """
        self.theme = "catppuccin-mocha"
        self.query_one("#editor", TextArea).border_title = "Editor"
        self.query_one("#preview", Markdown).border_title = "Preview"

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
            
            yield Label("Test")

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
        switcher.current = "preview" if switcher.current == "editor" else "editor"

    def action_save(self) -> None:
        """
        Save the current note content to note.md in the working directory.
        """
        # TODO: Implement file saving logic
        # editor = self.query_one("#editor", TextArea)
        # Path("note.md").write_text(editor.text)
        self.notify("Saved note!")
