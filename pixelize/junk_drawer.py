import asyncio

from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import ProgressBar


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
        self.dismiss(future.result())

    def compose(self):
        yield Grid(
            ProgressBar(id='modal-content'),
            id='modal'
        )
