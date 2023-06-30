import asyncio

import art
from textual import on
from textual.containers import Grid
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import ProgressBar, Label, Button, Static


class WorkingModal(ModalScreen):
    """
    Waits for a async task to complete.
    """

    def __init__(self, title: str, task):
        super().__init__()
        self.title = title
        self._future = asyncio.ensure_future(task)
        self._future.add_done_callback(self._complete)

    def _complete(self, future):
        try:
            result = future.result()
        except Exception as exc:
            self.app.switch_screen(ErrorModal(exc))
        else:
            self.dismiss(result)

    def compose(self):
        yield Grid(
            ProgressBar(id='modal-content'),
            id='modal'
        )


class ErrorModal(ModalScreen):
    """Screen with a dialog to quit."""

    def __init__(self, error: Exception):
        super().__init__()
        self.error = error

    def compose(self):
        print(repr(self.error), str(self.error))
        yield Grid(
            Label(str(self.error), id="modal-content"),
            Button("Ok", variant="error", id="continue"),
            id="modal",
        )

    @on(Button.Pressed, '#continue')
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(self.error)


class Jumbo(Static):
    text = reactive("")
    font = reactive(art.DEFAULT_FONT)

    def __init__(self, /, text: str = "", font: str = art.DEFAULT_FONT, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font = font

    def render(self):
        return art.text2art(self.text, font=self.font)
