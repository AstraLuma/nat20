import asyncio
import dataclasses
import datetime
import enum
import struct
from typing import Union
from collections.abc import AsyncIterable

import bleak

from .constants import SERVICE_PIXELS, SERVICE_INFO
from .link import PixelLink, iter_msgs
# Also, import messages so they get defined
from .messages import (
    WhoAreYou, IAmADie,
    RequestRollState, RollState, RollState_State,
    Blink, BlinkAck
)

# Since these are protocol definitions, I would prefer to use explicit numbers
# in enums, but none of the first-party code does that.


class ScanBattState(enum.IntEnum):
    """
    The charge state of the battery.
    """
    Ok = 0
    Charging = 1


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

    def connect(self) -> 'Pixel':
        """
        Constructs a full Pixel class for this die.

        (Note: Might not actually make a connection.)
        """
        return Pixel(self._device)


async def scan_for_dice() -> AsyncIterable[ScanResult]:
    """
    Search for dice.

    Will scan forever as long as the iterator is live.
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

    def __init__(self, device: bleak.backends.device.BLEDevice):
        self._device = device
        self._client = bleak.BleakClient(
            device,
            services=[SERVICE_INFO, SERVICE_PIXELS],
        )
        super().__init__()

    async def __aenter__(self):
        await self._client.connect()
        await super().__aenter__()
        return self

    async def __aexit__(self, *exc):
        await super().__aexit__(*exc)
        print("Disconnecting")
        await self._client.disconnect()

    def __repr__(self):
        return f"<{type(self).__name__} {self.address} is_connected={self.is_connected}>"

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

    def handler(self, msgcls: Union[type(...), type]):
        """
        Register to receive notifcations of events.

        @Pixel.register(RollState)
        def foobar
        """
        # FIXME: Correctly handle methods?
        def _(func):
            if msgcls is ...:
                for cls in iter_msgs():
                    self._message_handlers[cls].append(func)
            else:
                self._message_handlers[msgcls].append(func)

        return _

    async def who_are_you(self) -> IAmADie:
        """
        Perform a basic info query
        """
        return await self._send_and_wait(WhoAreYou(), IAmADie)

    async def what_do_you_want(self):
        return (
            "I'd like to live just long enough to be there when they cut off "
            "your head and stick it on a pike as a warning to the next ten "
            "generations that some favors come with too high a price. I would "
            "look up at your lifeless eyes and wave like this."
        )

    async def roll_state(self) -> RollState:
        return await self._send_and_wait(RequestRollState(), RollState)

    async def blink(self, **params) -> None:
        await self._send_and_wait(Blink(**params), BlinkAck)
