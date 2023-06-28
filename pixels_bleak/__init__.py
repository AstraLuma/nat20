import asyncio
import dataclasses
import datetime
import enum
import struct

import bleak

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
    batt_state: bool  # TODO: Enum
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
        roll_state = RollState(roll_state)
        id, build = struct.unpack("<II", sdata)
        build = datetime.datetime.fromtimestamp(
            build, tz=datetime.timezone.utc)

        return cls(
            _device=device,
            name=name,
            led_count=led_count,
            design=design,
            roll_state=roll_state,
            face=face,
            batt_state=bool(batt & 0x80),
            batt_level=batt & 0x7F,
            id=id,
            firmware_timestamp=build,
        )


class Pixel:
    @staticmethod
    async def scan():
        """
        Search for dice.
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
