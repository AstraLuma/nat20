import asyncio
import importlib.resources
import json
import time
from typing import Optional, Self

import art
import rich.repr
from rich.text import Text, TextType
from textual import on
from textual.app import RenderResult
from textual.containers import Grid
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Label, Button, Static


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
            LoadingIndicator(id='modal-content'),
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


class OkCancelModal(ModalScreen):
    """Screen with a dialog to quit."""

    def __init__(self,
                 msg: str,
                 show_ok: bool = True,
                 show_cancel: bool = True,
                 timeout: Optional[float] = None,
                 ):
        super().__init__()
        self.msg = msg
        self.show_ok = show_ok
        self.show_cancel = show_cancel
        if timeout is not None:
            self.timer = self.set_timer(timeout, self.on_timeout, pause=True)
        else:
            self.timer = None

    def on_mount(self, _):
        if self.timer is not None:
            self.timer.resume()

    def compose(self):
        yield Grid(
            Label(str(self.msg), id="modal-content"),
            Button("Ok", variant="primary", id="ok"),
            Button("Cancel", variant="default", id="cancel"),
            id="modal",
        )

    @on(Button.Pressed, '#ok')
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)

    @on(Button.Pressed, '#cancel')
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    def on_timeout(self):
        self.dismiss(TimeoutError)


class Jumbo(Static):
    text = reactive("")
    font = reactive(art.DEFAULT_FONT)

    def __init__(self, /, text: str = "", font: str = art.DEFAULT_FONT, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font = font

    def render(self):
        return art.text2art(self.text, font=self.font)


SPINNERS = json.loads(importlib.resources.read_text(__package__, 'spinners.json'))


class SpinningMixin(Widget):
    """
    Provides some infra around throbbing.

    Takes command of :attr:`auto_refresh`.
    """
    #: See https://jsfiddle.net/sindresorhus/2eLtsbey/embedded/result/
    spinner = reactive[Optional[str]](None)

    _frames: list[str]

    def watch_spinner(self, spinner: str | None):
        if spinner is None:
            self.auto_refresh = None
            self._frames = []
        else:
            spininfo = SPINNERS[spinner]
            self.auto_refresh = spininfo['interval'] / 1000
            self._frames = spininfo['frames']

    def get_spin_frame(self) -> str | None:
        """
        Gets the current frame of the spinner, or returns None if spinning is
        disabled.
        """
        if self.auto_refresh is None or not self._frames:
            return None
        else:
            cur_frame = int((time.monotonic() / self.auto_refresh) % len(self._frames))
            return self._frames[cur_frame]


class Spinner(SpinningMixin, Static):
    """
    Sits and spins.
    """

    def __init__(self, /, spinner: str = 'dots', **kwargs):
        super().__init__(**kwargs)
        self.spinner = spinner

    def __rich_repr__(self) -> rich.repr.Result:
        yield from super().__rich_repr__()
        yield "spinner", self.spinner

    def render(self) -> RenderResult:
        return self.get_spin_frame() or ""


class SpinButton(SpinningMixin, Button):
    """
    A button, but if you set the spinner, it'll override the label and disable pressing.
    """
    DEFAULT_CSS = """
    SpinButton {
        width: auto;
        min-width: 16;
        height: 3;
        background: $panel;
        color: $text;
        border: none;
        border-top: tall $panel-lighten-2;
        border-bottom: tall $panel-darken-3;
        content-align: center middle;
        text-style: bold;
    }

    SpinButton:focus {
        text-style: bold reverse;
    }

    SpinButton:hover {
        border-top: tall $panel;
        background: $panel-darken-2;
        color: $text;
    }
    """

    def press(self) -> Self:
        if self.get_spin_frame() is not None:
            return self
        return super().press()

    def render(self) -> TextType:
        if (frame := self.get_spin_frame()) is None:
            return super().render()
        else:
            label = Text.assemble(" ", frame, " ")
            label.stylize(self.text_style)
            return label


class ActionButton(SpinButton):
    """
    A button that can show a spinner based on a future
    """

    def track_future(self, spinner: str, future):
        """
        Set the spinner to track the given task/future/etc.

        This is not re-entrant; do not call multiple times. Instead use
        :func:`asyncio.gather`.
        """
        future = asyncio.ensure_future(future)
        self.spinner = spinner

        @future.add_done_callback
        def done(_):
            self.spinner = None

        return future
