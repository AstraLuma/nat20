import asyncio
import dataclasses
import datetime
import enum
import struct
from collections.abc import (
    AsyncIterable,
)

import bleak

from .link import PixelLink

SERVICE_PIXELS = bleak.uuids.normalize_uuid_str(
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
)
SERVICE_INFO = bleak.uuids.normalize_uuid_str('180a')

# Since these are protocol definitions, I would prefer to use explicit numbers
# in enums, but none of the first-party code does that.


class RollState(enum.IntEnum):
    """
    The current motion of the die.
    """
    Unknown = 0
    #: The die is sitting flat and is not moving
    OnFace = enum.auto()
    #: The die is in hand (Note: I'm not sure how reliable the detection of
    #: this state is.)
    Handling = enum.auto()
    #: The die is actively rolling
    Rolling = enum.auto()
    #: The die is still but not flat and level
    Crooked = enum.auto()


class BattState(enum.IntEnum):
    """
    The charge state of the battery.
    """
    Discharging = 0
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
    roll_state: RollState
    #: The current face (starting at 0)
    face: int
    #: The charge state of the battery
    batt_state: BattState
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
            roll_state=RollState(roll_state),
            face=face,
            batt_state=BattState(batt >> 7),
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
        super().__init__()
        self._device = device
        self._client = bleak.BleakClient(
            device,
            services=[SERVICE_INFO, SERVICE_PIXELS],
        )
        self._task = None

    async def __aenter__(self):
        await self._client.connect()
        self._task = asyncio.create_task(
            self._message_pump_task,
            name=f"pump-{self.address}"
        )
        return self

    async def __aexit__(self, *exc):
        self._task.cancel()
        await self._task
        self._task = None

        await self._client.disconnect()

    def __del__(self):
        if self._task is not None:
            # This implies some kind of improper shutdown, but cleanup anyway.
            self._task.cancel()
            self._task = None

    def __repr__(self):
        return f"<{type(self).__name__} {self.address} is_connected={self.is_connnected}>"

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
