from textual import work
from textual.app import App
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.containers import (
    VerticalScroll,
)
from textual.widgets import (
    Header, Footer, Static,
)

from pixels_bleak import Pixel, RollState


class Die(Static):
    """
    Displays stuff about a die
    """

    die_name = reactive("")
    led_count = reactive(0)
    face = reactive(0)
    roll_state = reactive(None)
    batt_level = reactive(0)

    def update_from_result(self, sr):
        for attr in dir(sr):
            if attr == 'name':
                self.die_name = sr.name
            elif attr in ('id',):
                # Skip
                pass
            elif hasattr(self, attr) and not attr.startswith('_'):
                setattr(self, attr, getattr(sr, attr))

        if self.roll_state in (RollState.OnFace, RollState.Crooked):
            self.remove_class("rolling")
        else:
            self.add_class("rolling")

    def render(self):
        if self.roll_state == RollState.OnFace:
            return f"{self.die_name} (d{self.led_count}): {self.face + 1} @ {self.batt_level}%"
        elif self.roll_state == RollState.Crooked:
            return f"{self.die_name} (d{self.led_count}): Crooked @ {self.batt_level}%"
        else:
            return f"{self.die_name} (d{self.led_count}): Rolling @ {self.batt_level}%"


class PixelsApp(App):
    TITLE = "Pixelize"
    SUB_TITLE = "A Pixels Dice TUI"

    CSS_PATH = 'pixels.css'

    BINDINGS = [
        ("q", "quit()", "Quit"),
    ]

    def compose(self):
        yield Header()
        yield Footer()
        yield VerticalScroll(id="dice")

    def on_mount(self, event):
        self.search_for_devices()

    @work(name='ble-scanner', exclusive=True)
    async def search_for_devices(self):
        """
        Run the BLE Scanner and update the app data
        """
        async for dev in Pixel.scan():
            cid = f"die_{dev.id:08X}"
            bag = self.get_child_by_id('dice')
            try:
                die = bag.get_child_by_id(cid)
            except NoMatches:
                # Create a new die
                die = Die(id=cid)
                die.update_from_result(dev)
                bag.mount(die, before=0)
            else:
                # Update the existing one
                die.update_from_result(dev)
                # FIXME: This fails if the child is already at the top
                # if dev.roll_state == RollState.OnFace:
                #     bag.move_child(die, before=0)

    def action_quit(self):
        self.exit()
