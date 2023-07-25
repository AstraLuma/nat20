from textual import on, work
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Header, Footer, Label, Button
import nat20

from nat20.messages import (
    BatteryLevel, BatteryState, DieFlavor, RollState, RollState_State,
)

from .junk_drawer import Jumbo, WorkingModal


class DoubleLabel(Static):
    left = reactive("")
    right = reactive("")

    def __init__(self, left, right, **kwargs):
        super().__init__(**kwargs)
        self.left = left
        self.right = right

    def render(self):
        return self.left + self.right


class BatteryLabel(Label):
    state = reactive(BatteryState.Ok)
    percent = reactive(0)

    DEFAULT_CSS = """
    BatteryLabel {
        width: 6;
    }
    """

    def __init__(self, /, state: BatteryState = BatteryState.Ok, percent: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.percent = percent

    def render(self):
        match self.state:
            case BatteryState.Ok:
                prefix = "\U0001F50B"
            case BatteryState.Low:
                prefix = "\U0001FAAB"
            case BatteryState.Charging | BatteryState.Done:
                prefix = "\U000026A1"
            case BatteryState.BadCharging | BatteryState.Error:
                prefix = "\U000026A0"

        return f"{prefix}{self.percent}%"


class FaceLabel(Label):
    state = reactive(RollState_State.Unknown)
    face = reactive(0)

    DEFAULT_CSS = """
    FaceLabel {
        width: 10;
    }
    """

    def __init__(
        self, /,
            state: RollState_State = RollState_State.Unknown,
            face: int = 0,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.state = state
        self.face = face

    def render(self):
        if self.state == RollState_State.OnFace:
            return str(self.face + 1)
        else:
            return self.state.name


class IdLabel(Label):
    die_id = reactive(0)

    DEFAULT_CSS = """
    IdLabel {
        width: 12;
    }
    """

    def __init__(self, /, die_id: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.die_id = die_id

    def render(self):
        return f"ID: {self.die_id:06X}"


class FlavorLabel(Label):
    flavor = reactive(DieFlavor.D20)

    DEFAULT_CSS = """
    FlavorLabel {
        width: 12;
    }
    """

    def __init__(self, /, flavor: DieFlavor = DieFlavor.D20, **kwargs):
        super().__init__(**kwargs)
        self.flavor = flavor

    def render(self):
        match self.flavor:
            case DieFlavor.D4:
                return "Flavor: D4"
            case DieFlavor.D6:
                return "Flavor: D6"
            case DieFlavor.D6Pipped:
                return "Flavor: D6 (Pipped)"
            case DieFlavor.D6Fudge:
                return "Flavor: Fudge"
            case DieFlavor.D8:
                return "Flavor: D8"
            case DieFlavor.D10:
                return "Flavor: D10"
            case DieFlavor.D12:
                return "Flavor: D12"
            case DieFlavor.D20:
                return "Flavor: D20"
            case flavor:
                return f"Flavor: {flavor}"


class DieDetailsScreen(Screen):
    die: nat20.Pixel
    ad: nat20.ScanResult

    BINDINGS = [
        ("d", "disconnect", "Disconnect"),
    ]

    def __init__(self, die: nat20.Pixel, ad: nat20.ScanResult):
        super().__init__()
        self.die = die
        self.ad = ad

        self.die.got_roll_state.handler(self.update_state, weak=True)
        self.die.got_battery_state.handler(self.update_batt, weak=True)
        self.die.disconnected.handler(self.on_disconnected, weak=True)
        self.inquire_die()

    @work(exclusive=True)
    async def inquire_die(self):
        info = await self.die.who_are_you()
        self.get_child_by_id('id').die_id = info.pixel_id
        self.get_child_by_id('face').state = info.roll_state
        self.get_child_by_id('face').face = info.roll_face
        self.get_child_by_id('batt').state = info.battery_state
        self.get_child_by_id('batt').percent = info.battery_percent
        self.get_child_by_id('flavor').flavor = info.flavor

    def on_disconnected(self, _):
        self.app.push_screen(
            WorkingModal("Reconnecting", self.die.connect()),
        )

    def update_state(self, _, msg: RollState):
        print(f"{msg=}")
        lbl: FaceLabel = self.get_child_by_id('face')
        lbl.state = msg.state
        lbl.face = msg.face

    def update_batt(self, _, msg: BatteryLevel):
        print(f"{msg=}")
        lbl: BatteryLabel = self.get_child_by_id('batt')
        lbl.state = msg.state
        lbl.percent = msg.percent

    def compose(self):
        yield Header()
        yield Footer()
        yield Jumbo(text=self.die.name)
        yield IdLabel(die_id=self.ad.id, id='id')
        yield FlavorLabel(flavor=self.ad.flavor, id='flavor')
        yield BatteryLabel(percent=self.ad.batt_level, id='batt')
        yield FaceLabel(state=self.ad.roll_state, face=self.ad.face, id='face')
        yield Button("Identify", id="ident")

    @on(Button.Pressed, '#ident')
    async def do_ident(self, _):
        await self.die.blink_id(0xFF)

    async def action_disconnect(self):
        self.dismiss()
