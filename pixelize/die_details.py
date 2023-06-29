from textual import on
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Header, Footer, Label, Button

from pixels_bleak.messages import RollState


class DoubleLabel(Static):
    left = reactive("")
    right = reactive("")

    def __init__(self, left, right, **kwargs):
        super().__init__(**kwargs)
        self.left = left
        self.right = right

    def render(self):
        return self.left + self.right


class DieDetailsScreen(Screen):
    def __init__(self, die):
        super().__init__()
        self.die = die

        @self.die.handler(RollState)
        def update_state(msg):
            print(f"{msg=}")
            self.get_child_by_id('face').right = str(msg.face + 1)

        # TODO: Request initial state

    def compose(self):
        yield Header()
        yield Footer()
        yield Label(repr(self.die))
        yield Button("Identify", id="ident")
        yield DoubleLabel("Face: ", "", id='face')

    @on(Button.Pressed, '#ident')
    async def do_ident(self, _):
        await self.die.blink_id(0xFF)
