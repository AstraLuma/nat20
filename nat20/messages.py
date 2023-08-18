from dataclasses import dataclass
import datetime
from enum import Enum, IntEnum, auto
from typing import Self

from .msglib import BasicMessage, EmptyMessage, StrMessage


class BatteryState(IntEnum):
    #: Discharging
    Ok = 0
    #: Battery level is low, user should recharge
    Low = 1
    #: Battery is charging
    Charging = 2
    #: Battery is full and on craddle
    Done = 3
    #: Attempted to charge, but something went wrong (eg, coil voltage is wrong
    #: from sitting crooked)
    BadCharging = 4
    #: WEIRDNESS (eg charging but no coil voltage)
    Error = 5


class RollState_State(IntEnum):
    """
    The current motion of the die.
    """
    #:
    Unknown = 0
    #: The die is sitting flat and is not moving
    OnFace = 1
    #: The die is in hand (Note: I'm not sure how reliable the detection of
    #: this state is.)
    Handling = 2
    #: The die is actively rolling
    Rolling = 3
    #: The die is still but not flat and level
    Crooked = 4


class RequestMode(IntEnum):
    """
    How much should a thing be reported.

    (Called TelemetryRequestMode in other places.)
    """
    #: Turn repeating off
    Off = 0
    #: Do a one-shot request
    Once = 1
    #: Repeatedly send the data until turned off.
    Repeat = 2


@dataclass
class NoneMessage(EmptyMessage, id=0):
    """
    Filler for message type 0.
    """


@dataclass
class WhoAreYou(EmptyMessage, id=1):
    """
    Request some basic information.

    Die replies with :class:`IAmADie`.
    """


class DieFlavor(Enum):
    D4 = auto()
    D6 = auto()
    D6Pipped = auto()
    D6Fudge = auto()
    D8 = auto()
    D10 = auto()
    D12 = auto()
    D20 = auto()

    @staticmethod
    def _from_led_count(leds: int) -> 'DieFlavor':
        try:
            return {
                4: DieFlavor.D4,
                6: DieFlavor.D6,
                8: DieFlavor.D8,
                10: DieFlavor.D10,
                12: DieFlavor.D12,
                20: DieFlavor.D20,
                21: DieFlavor.D6Pipped,
                # ???: DieFlavor.D6Fudge
            }[leds]
        except KeyError as exc:
            raise ValueError("Unknown LED count: %i", leds) from exc

    @property
    def face_count(self) -> int:
        """
        Return the number of faces this flavor has.
        """
        return {
            DieFlavor.D4: 4,
            DieFlavor.D6: 6,
            DieFlavor.D8: 8,
            DieFlavor.D10: 10,
            DieFlavor.D12: 12,
            DieFlavor.D20: 20,
            DieFlavor.D6Pipped: 6,
            DieFlavor.D6Fudge: 6,
        }[self]


class DesignAndColor(IntEnum):
    Unknown = 0
    Generic = 1
    V3Orange = 2
    V4BlackClear = 3
    V4WhiteClear = 4
    V5Grey = 5
    V5White = 6
    V5Black = 7
    V5Gold = 8
    OnyxBlack = 9
    HematiteGrey = 10
    MidnightGalaxy = 11
    AuroraSky = 12


@dataclass
class IAmADie(BasicMessage, id=2, format="BB1xLLHL BB BB"):
    """
    A bunch of general info.

    Reply to :class:`WhoAreYou`
    """
    #: Number of LEDs
    led_count: int
    #: The aesthetic design of the die
    design_and_color: DesignAndColor
    data_set_hash: int
    #: The factory-assigned die ID
    pixel_id: int
    available_flash: int
    #: Timestamp of when the firmware was built.
    build_timestamp: datetime.datetime

    #: Current roll state
    roll_state: RollState_State
    #: Current face that's up, starting at 0. Validity depends on :attr:`roll_state`.
    roll_face: int

    #: Current battery level as a percent
    batt_level: int
    #: Current battery percent
    batt_state: BatteryState

    @property
    def flavor(self) -> DieFlavor:
        """
        The kind of die this is, like D20 or Pipped D6
        """
        return DieFlavor._from_led_count(self.led_count)

    @property
    def face_count(self) -> int:
        """
        The total number of faces
        """
        return self.flavor.face_count

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.roll_state = RollState_State(self.roll_state)
        self.batt_state = BatteryState(self.batt_state)
        self.design_and_color = DesignAndColor(self.design_and_color)
        self.build_timestamp = datetime.datetime.fromtimestamp(
            self.build_timestamp, tz=datetime.timezone.utc)

        return self

    def to_rollstate(self) -> 'RollState':
        """
        Repackages the rolling information.
        """
        return RollState(
            state=self.roll_state,
            face=self.roll_face,
        )

    def to_batterylevel(self) -> 'BatteryLevel':
        """
        Repackages the battery information.
        """
        return BatteryLevel(
            state=self.batt_state,
            level=self.batt_level,
        )


@dataclass
class RollState(BasicMessage, id=3, format="BB"):
    """
    The current motion.

    Broadcast on changes (see :meth:`.Pixel.handler()`) and is a reply to
    :class:`RequestRollState`.
    """
    #: The current motion
    state: RollState_State
    #: The upright face (starting at 0). Validity depends on :attr:`roll_state`.
    face: int

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.state = RollState_State(self.state)
        return self


@dataclass
class Telemetry(BasicMessage, id=4, format="50x BBBB bB hh BB"):
    # accelFrame: ...  # TODO

    battery_percent: int
    battery_state: BatteryState
    #: times 50
    voltage: int
    #: times 50
    v_coil: int

    rssi: int
    #: 0-based
    bt_channel: int
    #: times 100
    mcu_temp: int
    #: times 100
    battery_temp: int

    internal_charge_state: int
    force_disable_charging_state: int


@dataclass
class BulkSetup(BasicMessage, id=5, format=""):
    ...


@dataclass
class BulkSetupAck(BasicMessage, id=6, format=""):
    ...


@dataclass
class BulkData(BasicMessage, id=7, format=""):
    ...


@dataclass
class BulkDataAck(BasicMessage, id=8, format=""):
    ...


@dataclass
class TransferAnimationSet(BasicMessage, id=9, format=""):
    ...


@dataclass
class TransferAnimationSetAck(BasicMessage, id=10, format=""):
    ...


@dataclass
class TransferAnimationSetFinished(BasicMessage, id=11, format=""):
    ...


@dataclass
class TransferSettings(BasicMessage, id=12, format=""):
    ...


@dataclass
class TransferSettingsAck(BasicMessage, id=13, format=""):
    ...


@dataclass
class TransferSettingsFinished(BasicMessage, id=14, format=""):
    ...


@dataclass
class TransferTestAnimationSet(BasicMessage, id=15, format=""):
    ...


@dataclass
class TransferTestAnimationSetAck(BasicMessage, id=16, format=""):
    ...


@dataclass
class TransferTestAnimationSetFinished(BasicMessage, id=17, format=""):
    ...


@dataclass
class DebugLog(StrMessage, id=18):
    text: str

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        return cls(
            text=blob.decode('utf-8')
        )

    def __struct_pack__(self) -> bytes:
        return self.text.encode('utf-8')


@dataclass
class PlayAnimation(BasicMessage, id=19, format="BBB"):
    animation: int
    remap_face: int
    loop: int


@dataclass
class PlayAnimationEvent(BasicMessage, id=20, format="BBB"):
    evt: int
    remap_face: int
    loop: int


@dataclass
class StopAnimation(BasicMessage, id=21, format="BB"):
    animation: int
    remap_face: int


@dataclass
class RemoteAction(BasicMessage, id=22, format="H"):
    action_id: int


@dataclass
class RequestRollState(EmptyMessage, id=23):
    """
    Request the current roll state.

    Replied with :class:`RollState`.
    """


@dataclass
class RequestAnimationSet(BasicMessage, id=24, format=""):
    ...


@dataclass
class RequestSettings(BasicMessage, id=25, format=""):
    ...


@dataclass
class RequestTelemetry(BasicMessage, id=26, format=""):
    ...


@dataclass
class ProgramDefaultAnimationSet(BasicMessage, id=27, format=""):
    ...


@dataclass
class ProgramDefaultAnimationSetFinished(BasicMessage, id=28, format=""):
    ...


@dataclass
class Blink(BasicMessage, id=29, format="BHLLBB"):
    """
    Do a custom blink.

    Replied with :class:`BlinkAck`
    """
    count: int
    duration: int
    color: int  # TODO: RGB
    face_mask: int  # TODO: Enum?
    fade: int
    loop: int  # TODO: bool/enum


@dataclass
class BlinkAck(EmptyMessage, id=30):
    """
    Reply to :class:`Blink`.
    """


@dataclass
class RequestDefaultAnimationSetColor(BasicMessage, id=31, format=""):
    ...


@dataclass
class DefaultAnimationSetColor(BasicMessage, id=32, format=""):
    ...


@dataclass
class RequestBatteryLevel(EmptyMessage, id=33):
    """
    Request the current battery.

    Replies with :class:`BatteryLevel`.
    """


@dataclass
class BatteryLevel(BasicMessage, id=34, format="BB"):
    """
    Current state of the battery.

    Broadcast on changes (see :meth:`.Pixel.handler`) and reply to
    :class:`RequestBatteryLevel`.
    """
    #: The current level of the battery, as a percent
    level: int
    #: The current charge state
    state: BatteryState

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.state = BatteryState(self.state)
        return self


@dataclass
class RequestRssi(BasicMessage, id=35, format="BH"):
    """
    Request RSSI.

    Replied with :class:`Rssi`.
    """
    #: Set the reporting mode
    request_mode: RequestMode
    #: Interval of repeated reports, in milliseconds
    min_interval: int

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.request_mode = RequestMode(self.request_mode)
        return self


@dataclass
class Rssi(BasicMessage, id=36, format="b"):
    """
    Report the current RSSI as seen by the die.

    See :class:`RequestRssi`.
    """
    rssi: int


@dataclass
class Calibrate(EmptyMessage, id=37):
    """
    Start the calibration process.
    """


@dataclass
class CalibrateFace(BasicMessage, id=38, format="B"):
    """
    Immediately calibrate the given face.
    """
    face: int


@dataclass
class NotifyUser(BasicMessage, id=39, format="BBB"):
    """
    Die asking the user a question
    """
    #: How long the die will wait for a response, in seconds
    timeout: int
    #: Whether "ok" is an accepted answer
    ok: bool
    #: Whether "cancel" is an accepted answer
    cancel: bool
    #: Prompt to show the user
    text: str

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.ok = bool(self.ok)
        self.cancel = bool(self.cancel)
        return self


class OkCancel(IntEnum):
    """
    Button enum for :class:`NotifyUserAck`
    """
    Cancel = 0
    Ok = 1


@dataclass
class NotifyUserAck(BasicMessage, id=40, format="B"):
    """
    Response to :class:`NotifyUser`
    """
    ok_cancel: OkCancel

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        self = super().__struct_unpack__(blob)
        self.ok_cancel = OkCancel(self.ok_cancel)
        return self


@dataclass
class TestHardware(BasicMessage, id=41, format=""):
    ...


@dataclass
class TestLEDLoopback(BasicMessage, id=42, format=""):
    ...


@dataclass
class LedLoopback(BasicMessage, id=43, format=""):
    ...


@dataclass
class SetTopLevelState(BasicMessage, id=44, format=""):
    ...


@dataclass
class ProgramDefaultParameters(BasicMessage, id=45, format=""):
    ...


@dataclass
class ProgramDefaultParametersFinished(BasicMessage, id=46, format=""):
    ...


@dataclass
class SetDesignAndColor(BasicMessage, id=47, format=""):
    ...


@dataclass
class SetDesignAndColorAck(BasicMessage, id=48, format=""):
    ...


@dataclass
class SetCurrentBehavior(BasicMessage, id=49, format=""):
    ...


@dataclass
class SetCurrentBehaviorAck(BasicMessage, id=50, format=""):
    ...


@dataclass
class SetName(StrMessage, id=51):
    """
    Change the name of the die.
    """
    name: str


@dataclass
class SetNameAck(EmptyMessage, id=52):
    """
    Acknowledges :class:`SetName`.
    """


@dataclass
class Sleep(BasicMessage, id=53, format=""):
    ...


@dataclass
class ExitValidation(BasicMessage, id=54, format=""):
    ...


@dataclass
class TransferInstantAnimationSet(BasicMessage, id=55, format=""):
    ...


@dataclass
class TransferInstantAnimationSetAck(BasicMessage, id=56, format=""):
    ...


@dataclass
class TransferInstantAnimationSetFinished(BasicMessage, id=57, format=""):
    ...


@dataclass
class PlayInstantAnimation(BasicMessage, id=58, format=""):
    ...


@dataclass
class StopAllAnimations(EmptyMessage, id=59):
    """
    Stop all animations.
    """


@dataclass
class RequestTemperature(EmptyMessage, id=60):
    """
    Get the current temperature

    Die replies with :class:`Temperature`.
    """


@dataclass
class Temperature(BasicMessage, id=61, format="hh"):
    #: CPU temp in centidegrees Celsius
    mcu_temp: int
    #: Battery temp in centidgrees Celsius
    batt_temp: int


@dataclass
class EnableCharging(BasicMessage, id=62, format=""):
    ...


@dataclass
class DisableCharging(BasicMessage, id=63, format=""):
    ...


@dataclass
class Discharge(BasicMessage, id=64, format=""):
    ...


@dataclass
class BlinkId(BasicMessage, id=65, format="BB"):
    brightness: int
    loop: int


@dataclass
class BlinkIdAck(EmptyMessage, id=66):
    pass


# FIXME: Do these TransferTest* messages exist?
# FIXME: Are messages beyond this point numbered correctly?
@dataclass
class TransferTest(BasicMessage, id=67, format=""):
    ...


@dataclass
class TransferTestAck(BasicMessage, id=68, format=""):
    ...


@dataclass
class TransferTestFinished(BasicMessage, id=69, format=""):
    ...


@dataclass
class TestBulkSend(BasicMessage, id=70, format=""):
    ...


@dataclass
class TestBulkReceive(BasicMessage, id=71, format=""):
    ...


@dataclass
class SetAllLEDsToColor(BasicMessage, id=72, format=""):
    ...


@dataclass
class AttractMode(BasicMessage, id=73, format=""):
    ...


@dataclass
class PrintNormals(BasicMessage, id=74, format=""):
    ...


@dataclass
class PrintA2DReadings(BasicMessage, id=75, format=""):
    ...


@dataclass
class LightUpFace(BasicMessage, id=76, format=""):
    ...


@dataclass
class SetLEDToColor(BasicMessage, id=77, format=""):
    ...


@dataclass
class DebugAnimationController(BasicMessage, id=78, format=""):
    ...
