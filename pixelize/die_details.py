from typing import Callable

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.widgets import Input, Static, Header, Footer, Label, Button

import nat20
from nat20.messages import (
    BatteryState, DieFlavor, RollState_State,
)

from .junk_drawer import ActionButton, Jumbo, OkCancelModal, WorkingModal


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


class ChangeNameModal(ModalScreen):
    """
    Prompts the user to change the name of the given die.
    """
    die: nat20.Pixel

    def __init__(self, die: nat20.Pixel):
        super().__init__()
        self.die = die

    def compose(self) -> ComposeResult:
        yield Grid(
            Vertical(
                Input(placeholder="Name", value=self.die.name, id="name"),
                id="modal-content",
            ),
            ActionButton("Change", variant="error", id="change"),
            Button("Cancel", variant="primary", id="cancel"),
            id="modal",
        )

    @on(Input.Submitted, '#name')
    def on_submitted(self, _):
        self.get_widget_by_id('change').press()

    @on(Button.Pressed, '#change')
    async def on_changed(self, event: Button.Pressed):
        async def work():
            input: Input = self.get_widget_by_id('name')
            newname = input.value
            await self.die.set_name(newname)
            self.dismiss(True)

        await event.button.track_future('dots', work())

    @on(Button.Pressed, '#cancel')
    def on_cancelled(self, _):
        self.dismiss(False)


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

        self.die.data_changed.handler(self.update_data, weak=True)
        self.die.disconnected.handler(self.on_disconnected, weak=True)
        self.die.notify_user.handler(self.on_notify, weak=True)
        self.inquire_die()

    async def on_unmount(self, _):
        await self.die.disconnect()

    @work(exclusive=True)
    async def inquire_die(self):
        await self.die.who_are_you()  # Relies on firing the data_changed event

    async def update_data(self, _, props):
        print("Got updated data", props)
        self.get_child_by_id('title').text = self.die.name
        self.get_child_by_id('id').die_id = self.die.pixel_id
        self.get_child_by_id('face').state = self.die.roll_state
        self.get_child_by_id('face').face = self.die.roll_face
        self.get_child_by_id('batt').state = self.die.batt_state
        self.get_child_by_id('batt').percent = self.die.batt_level
        self.get_child_by_id('flavor').flavor = self.die.flavor

    def on_disconnected(self, _):
        self.app.push_screen(
            WorkingModal("Reconnecting", self.die.connect()),
        )

    def on_notify(self, _, text: str, ok: bool, cancel: bool, timeout: int, respond: Callable):
        def got_response(resp):
            if resp is TimeoutError:
                pass
            else:
                respond(resp)
        self.app.push_screen(OkCancelModal(
            text,
            show_ok=ok,
            show_cancel=cancel,
            timeout=timeout,
        ), got_response)

    def compose(self):
        yield Header()
        yield Footer()
        yield Jumbo(text=self.die.name, id='title')
        yield Button("Change Name", id='change-name')
        yield IdLabel(die_id=self.ad.pixel_id, id='id')
        yield FlavorLabel(flavor=self.ad.flavor, id='flavor')
        yield BatteryLabel(percent=self.ad.batt_level, id='batt')
        yield FaceLabel(state=self.ad.roll_state, face=self.ad.roll_face, id='face')
        yield ActionButton("Identify", id="ident")
        yield Button("Calibrate", id="calibrate")

    @on(Button.Pressed, '#ident')
    async def do_ident(self, event: Button.Pressed):
        await event.button.track_future('dots', self.die.blink_id(0xFF))

    @on(Button.Pressed, '#change-name')
    def do_name_change(self, _):
        self.app.push_screen(ChangeNameModal(self.die))

    @on(Button.Pressed, '#calibrate')
    async def do_calibrate(self, _):
        await self.die.start_calibration()

    async def action_disconnect(self):
        self.dismiss()
