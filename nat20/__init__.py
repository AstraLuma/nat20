"""
Primary interface to Pixels dice.

::

    async for scan in scan_for_dice():
        break

    async with scan.connect() as die:
        die.blink_id(0x80)
"""
import asyncio
from collections.abc import AsyncIterable
import dataclasses
import datetime
import enum
import logging
import struct
from types import EllipsisType
from typing import Union

import bleak

from .constants import SERVICE_PIXELS, SERVICE_INFO
from .link import PixelLink, iter_msgs, Message
# Also, import messages so they get defined
from .messages import (
    WhoAreYou, IAmADie,
    RequestRollState, RollState, RollState_State,
    Blink, BlinkAck, BlinkId, BlinkIdAck,
    BatteryLevel, BatteryState,
)

LOG = logging.getLogger(__name__)

# Since these are protocol definitions, I would prefer to use explicit numbers
# in enums, but none of the first-party code does that.


class ScanBattState(enum.IntEnum):
    """
    The charge state of the battery.
    """
    #: The battery is discharging
    Ok = 0
    #: The battery is charging
    Charging = 1

    def as_batterystate(self) -> BatteryState:
        """
        Repackage as a :class:`BatteryState`.

        Note that due to data fidelity, the state can only be
        :attr:`.BatteryState.Ok` or :attr:`.BatteryState.Charging`.
        """
        match self:
            case ScanBattState.Ok:
                return BatteryState.Ok
            case ScanBattState.Charging:
                return BatteryState.Charging
            case _:
                # Can't happen, but covering bases
                return BatteryState.Error


@dataclasses.dataclass
class ScanResult:
    _device: bleak.backends.device.BLEDevice
    #: The name of the die
    name: str
    #: The number of LEDs and faces
    led_count: int
    #: The color and symbol set
    design: int  # TODO: Enum
    #: The motion of the die
    roll_state: RollState_State
    #: The current face (starting at 0)
    face: int
    #: The charge state of the battery
    batt_state: ScanBattState
    #: The level of the battery, as a percent
    batt_level: int
    #: The unique ID of the die
    id: int
    #: The build date of the firmware
    firmware_timestamp: datetime.datetime

    @classmethod
    def _construct(cls, device, name, mdata, sdata):
        led_count, design, roll_state, face, batt = struct.unpack(
            "<BBBBB", mdata)
        id, build = struct.unpack("<II", sdata)
        build = datetime.datetime.fromtimestamp(
            build, tz=datetime.timezone.utc)

        return cls(
            _device=device,
            name=name,
            led_count=led_count,
            design=design,
            roll_state=RollState_State(roll_state),
            face=face,
            batt_state=ScanBattState(batt >> 7),
            batt_level=batt & 0x7F,
            id=id,
            firmware_timestamp=build,
        )

    def to_rollstate(self) -> 'RollState':
        """
        Repackages the rolling information.
        """
        return RollState(
            state=self.roll_state,
            face=self.face,
        )

    def to_batterylevel(self) -> 'BatteryLevel':
        """
        Repackages the battery information.

        Note that due to data fidelity, the state can only be
        :attr:`.BatteryState.Ok` or :attr:`.BatteryState.Charging`.
        """
        return BatteryLevel(
            state=self.batt_state.as_batterystate(),
            percent=self.batt_level,
        )

    def connect(self) -> 'Pixel':
        """
        Constructs a full Pixel class for this die.
        """
        return Pixel(self)


async def scan_for_dice() -> AsyncIterable[ScanResult]:
    """
    Search for dice. Will scan forever as long as the iterator is live.

    For timeouts, :func:`asyncio.timeout` might be helpful.
    """
    q = asyncio.Queue()

    def detected(device, ad_data):
        if (
            0xFFFF in ad_data.manufacturer_data and
            SERVICE_INFO in ad_data.service_data
        ):
            sr = ScanResult._construct(
                device, ad_data.local_name,
                ad_data.manufacturer_data[0xFFFF],
                ad_data.service_data[SERVICE_INFO],
            )
            q.put_nowait(sr)

    scanner = bleak.BleakScanner(
        detection_callback=detected,
        service_uuids=[SERVICE_PIXELS],
    )

    async with scanner:
        while True:
            yield await q.get()


class Pixel(PixelLink):
    """
    Class for a pixel die.

    Do not construct directly, use :func:`scan_for_dice` to find the die you
    want and then use :meth:`ScanResult.connect` to get an instance.

    Actually perform the network connection using ``async with``. Use
    :class:`contextlib.AsyncExitStack` to avoid this.
    """
    # The requirement to use scan_for_dice() is because while bleak does
    # support connecting by address, it internally just does a scan anyway,
    # so might as well make that part of the data model. And then users can
    # scan by name or ID or whatever.

    #: The textual name of the die.
    name: str

    _expected_disconnect: bool = False

    def __init__(self, sr: ScanResult):
        """
        Use :meth:`ScanResult.connect` instead.

        :meta private:
        """
        self._device = sr._device
        self.name = sr.name
        self._client = bleak.BleakClient(
            sr._device,
            services=[SERVICE_INFO, SERVICE_PIXELS],
            disconnected_callback=lambda c: asyncio.create_task(
                self._on_disconnect(c)),
        )
        super().__init__()

    async def __aenter__(self):
        """
        Connect to die
        """
        self._expected_disconnect = False
        await self._client.connect()
        await super().__aenter__()
        return self

    async def __aexit__(self, *exc):
        """
        Disconnect from die
        """
        await super().__aexit__(*exc)
        print("Disconnecting")
        self._expected_disconnect = True
        await self._client.disconnect()

    async def _on_disconnect(self, client):
        if not self._expected_disconnect:  # Don't reconnect if we're exiting
            LOG.info("Disconnected from %r, reconnecting", client)
            await client.connect()
            # XXX: What if reconnect fails?
            # XXX: Block requests until reconnect happens?

    def __repr__(self):
        return f"<{type(self).__name__} {self.address} {self.name!r} is_connected={self.is_connected}>"

    @property
    def address(self) -> str:
        """
        The MAC address (macOS: UUID) of the die.
        """
        return self._client.address

    @property
    def is_connected(self) -> bool:
        """
        Are we currently connected to the die?
        """
        return self._client.is_connected

    def handler(self, msgcls: Union[EllipsisType, type[Message]]):
        """
        Register to receive notifcations of events.

        ::

            @die.handler(RollState)
            def foobar(msg):
                ...
        """
        # FIXME: Correctly handle methods?
        def _(func):
            if msgcls is ...:
                for cls in iter_msgs():
                    self._message_handlers[cls].append(func)
            else:
                self._message_handlers[msgcls].append(func)

            return func

        return _

    async def who_are_you(self) -> IAmADie:
        """
        Perform a basic info query
        """
        return await self._send_and_wait(WhoAreYou(), IAmADie)

    async def what_do_you_want(self):
        """
        Companion to :meth:`.who_are_you`

        :meta private:
        """
        return (
            "I'd like to live just long enough to be there when they cut off "
            "your head and stick it on a pike as a warning to the next ten "
            "generations that some favors come with too high a price. I would "
            "look up at your lifeless eyes and wave like this."
        )

    async def roll_state(self) -> RollState:
        """
        Request the current roll state.
        """
        return await self._send_and_wait(RequestRollState(), RollState)

    async def blink(self, **params) -> None:
        await self._send_and_wait(Blink(**params), BlinkAck)

    async def blink_id(self, brightness: int, loop: bool = False) -> None:
        """
        Blinks rainbow, suitable for die identification.

        Args:
            brightness: 0-255, 0 is off, 255 is max brightness
            loop: Whether to loop or just run once

        Note:
            This only blocks until the die acknowledges the command, not until
            the animation is finished.
        """
        await self._send_and_wait(BlinkId(brightness, int(loop)), BlinkIdAck)
