from textual import work, on
from textual.app import App
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.containers import (
    VerticalScroll,
)
from textual.widgets import (
    Header, Footer, Static, Button,
)

from nat20 import scan_for_dice, ScanResult
from nat20.messages import DieFlavor, RollState_State

from .junk_drawer import WorkingModal
from .die_details import DieDetailsScreen


class DieSummary(Static):
    """
    Displays stuff about a die
    """

    die_name = reactive("")
    flavor = reactive(DieFlavor.D20)
    face = reactive(0)
    roll_state = reactive(None)
    batt_level = reactive(0)

    def update_from_result(self, sr: ScanResult):
        for attr in dir(sr):
            if attr == 'name':
                self.die_name = sr.name
            elif hasattr(self, attr) and not attr.startswith('_'):
                setattr(self, attr, getattr(sr, attr))

        if self.roll_state in (RollState_State.OnFace, RollState_State.Crooked):
            self.remove_class("rolling")
        else:
            self.add_class("rolling")

    def render(self):
        if self.roll_state == RollState_State.OnFace:
            return (
                f"{self.die_name} ({self.flavor}): {self.face + 1} "
                f"\U0001F50B{self.batt_level}%"
            )
        elif self.roll_state == RollState_State.Crooked:
            return f"{self.die_name} ({self.flavor}): Crooked \U0001F50B{self.batt_level}%"
        else:
            return f"{self.die_name} ({self.flavor}): Rolling \U0001F50B{self.batt_level}%"


class Die(Static):
    _scan_result: ScanResult

    def update_from_result(self, sr: ScanResult):
        self._scan_result = sr
        try:
            info = self.query_one(DieSummary)
        except NoMatches:
            pass
        else:
            info.update_from_result(sr)

    @on(Button.Pressed, '#connect')
    def on_connect(self):
        die = self._scan_result.hydrate()

        async def connect():
            print("connecting")
            await die.connect()
            return die

        def switch(die):
            print("Open the dice now hal")
            print(die)
            self.app.push_screen(
                DieDetailsScreen(die, self._scan_result)
            )

        self.app.push_screen(
            WorkingModal("Connecting", connect()),
            switch
        )

    def compose(self):
        yield Button("Connect", id="connect")
        yield (ds := DieSummary(id="info"))
        if self._scan_result is not None:
            ds.update_from_result(self._scan_result)


class DiceBagScreen(Screen):
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
        async for dev in scan_for_dice():
            cid = f"die_{dev.pixel_id:08X}"
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
                if dev.roll_state == RollState_State.OnFace and len(bag.children) > 1:
                    bag.move_child(die, before=0)


class PixelsApp(App):
    TITLE = "Pixelize"
    SUB_TITLE = "A Pixels Dice TUI"

    SCREENS = {
        'bag': DiceBagScreen(),
    }

    CSS_PATH = 'pixels.css'

    BINDINGS = [
        ("q", "quit()", "Quit"),
    ]

    def on_mount(self, event):
        self.push_screen('bag')

    def action_quit(self):
        self.exit()
