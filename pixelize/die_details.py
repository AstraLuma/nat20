from textual import on
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button


class DieDetailsScreen(Screen):
    def __init__(self, die):
        super().__init__()
        self.die = die

    def compose(self):
        yield Header()
        yield Footer()
        yield Label("TODO: Die thingies here")
        yield Label(repr(self.die))
        yield Button("Identify", id="ident")

    @on(Button.Pressed, '#ident')
    async def do_ident(self, _):
        await self.die.blink_id(0xFF)
