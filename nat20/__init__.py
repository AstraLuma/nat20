"""
Primary interface to Pixels dice.

::

    async for scan in scan_for_dice():
        break

    async with scan.connect() as die:
        die.blink_id(0x80)
"""
import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
import contextlib
import dataclasses
import datetime
import enum
import logging
import struct
from typing import Self

import aioevents
import bleak

from .constants import SERVICE_PIXELS, SERVICE_INFO
from .link import PixelLink
from .messages import (
    WhoAreYou, IAmADie, DieFlavor,
    RequestRollState, RollState, RollState_State,
    Blink, BlinkAck, BlinkId, BlinkIdAck,
    BatteryLevel, BatteryState,
)  # Also, import messages so they get defined

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

    def hydrate(self) -> 'Pixel':
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


class Pixel:
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

    _link: PixelLink

    got_roll_state = aioevents.Event("A new RollState has been sent.")
    got_battery_state = aioevents.Event("A new BatteryState has been sent.")
    disconnected = aioevents.Event("We've been unexpectedly disconnected from the die.")

    def __init__(self, sr: ScanResult):
        """
        Use :meth:`ScanResult.connect` instead.

        :meta private:
        """
        self._device = sr._device
        self.name = sr.name
        self._link = PixelLink(bleak.BleakClient(
            sr._device,
            services=[SERVICE_INFO, SERVICE_PIXELS],
            disconnected_callback=lambda c: asyncio.create_task(
                self._on_disconnect(c)),
        ))

        self._link._message_handlers[RollState].append(self._on_roll_state)
        self._link._message_handlers[BatteryState].append(self._on_battery_state)

    async def connect(self):
        """
        Connect to die
        """
        self._expected_disconnect = False
        await self._link.connect()

    async def disconnect(self):
        """
        Disconnect from die
        """
        self._expected_disconnect = True
        await self._link.disconnect()

    @contextlib.asynccontextmanager
    async def connect_with_reconnect(self) -> AsyncGenerator[Self, None]:
        """
        Connect to the die and make an effort to automatically reconnect.
        """
        @self.disconnected.handler
        async def reconnect(_):
            await self.connect()  # TODO: Forward error?

        await self.connect()
        try:
            yield self
        finally:
            self.disconnected.remove(reconnect)
            await self.disconnect()

    async def _on_disconnect(self, client):
        if not self._expected_disconnect:
            LOG.info("Disconnected from %r", client)
            self.disconnected.trigger()

    def _on_roll_state(self, msg: RollState):
        self.got_roll_state.trigger(msg)

    def _on_battery_state(self, msg: BatteryState):
        self.got_battery_state.trigger(msg)

    def __repr__(self):
        return (
            f"<{type(self).__name__} "
            f"{self.address} {self.name!r} is_connected={self.is_connected}"
            f">"
        )

    @property
    def address(self) -> str:
        """
        The MAC address (UUID on macOS) of the die.
        """
        return self._link.address

    @property
    def is_connected(self) -> bool:
        """
        Are we currently connected to the die?
        """
        return self._link.is_connected

    async def who_are_you(self) -> IAmADie:
        """
        Perform a basic info query
        """
        return await self._link.send_and_wait(WhoAreYou(), IAmADie)

    async def what_do_you_want(self):
        """
        Companion to :meth:`.who_are_you`

        :meta private:
        """
        # Babylon 5, Vir Cotto to Mr Morden
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
        return await self._link.send_and_wait(RequestRollState(), RollState)

    async def blink(self, **params) -> None:
        await self._link.send_and_wait(Blink(**params), BlinkAck)

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
        await self._link.send_and_wait(BlinkId(brightness, int(loop)), BlinkIdAck)
