from textual import on, work
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Header, Footer, Label, Button
import pixels_bleak

from pixels_bleak.messages import (
    BatteryLevel, BatteryState, RollState, RollState_State,
)


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
    state: BatteryState = reactive(BatteryState.Ok)
    percent: int = reactive(0)

    def render(self):
        match self.state:
            case BatteryState.Ok:
                prefix = "\U0001F50B"
            case BatteryState.Low:
                prefix = "\U0001FAAB"
            case BatteryState.Charging | BatteryState.Done:
                prefix = "\U0001F5F2"
            case BatteryState.BadCharging | BatteryState.Error:
                prefix = "\U000026A0"

        return f"{prefix}{self.percent}%"


class FaceLabel(Label):
    state: RollState_State = reactive(RollState_State.Unknown)
    face: int = reactive(0)

    DEFAULT_CSS = """
    FaceLabel {
        width: 10;
    }
    """

    def render(self):
        if self.state == RollState_State.OnFace:
            return str(self.face + 1)
        else:
            return self.state.name


class DieDetailsScreen(Screen):
    die: pixels_bleak.Pixel

    BINDINGS = [
        ("d", "disconnect", "Disconnect"),
    ]

    def __init__(self, die):
        super().__init__()
        self.die = die

        self.die.handler(RollState)(self.update_state)
        self.die.handler(BatteryState)(self.update_batt)
        self.inquire_die()

    @work(exclusive=True)
    async def inquire_die(self):
        info = await self.die.who_are_you()
        self.get_child_by_id('face').state = info.roll_state
        self.get_child_by_id('face').face = info.roll_face
        self.get_child_by_id('batt').state = info.battery_state
        self.get_child_by_id('batt').percent = info.battery_percent

    def update_state(self, msg: RollState):
        print(f"{msg=}")
        lbl: FaceLabel = self.get_child_by_id('face')
        lbl.state = msg.state
        lbl.face = msg.face

    def update_batt(self, msg: BatteryLevel):
        print(f"{msg=}")
        lbl: BatteryLabel = self.get_child_by_id('batt')
        lbl.state = msg.state
        lbl.percent = msg.percent

    def compose(self):
        yield Header()
        yield Footer()
        yield Label(repr(self.die))
        yield BatteryLabel(id='batt')
        yield FaceLabel(id='face')
        yield Button("Identify", id="ident")

    @on(Button.Pressed, '#ident')
    async def do_ident(self, _):
        await self.die.blink_id(0xFF)

    async def action_disconnect(self):
        self.dismiss()
