import sys
from typing import Self, Union, ClassVar
import uuid

import bleak.backends.client
import bleak.backends.characteristic
import bleak.uuids


class DeviceFacade:
    """
    Class for test suites to implement mock devices.

    Individual characteristics should be implemented as properties. Register
    their UUIDs in the characteristics class-level dictionary.
    """
    #: A dictionary mapping services to their characteristics
    services: ClassVar[dict[str, list[str]]] = {}

    #: Maps characteristic UUIDs to property name
    characteristics: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls: type[Self]) -> None:
        srvs = {}
        chrs = {}
        for base in cls.mro():
            if base is object:
                if hasattr(base, 'services'):
                    # TODO: merge values
                    srvs = base.services | srvs
                if hasattr(base, 'characteristics'):
                    chrs = base.characteristics | chrs

        cls.services = {
            sys.intern(bleak.uuids.normalize_uuid_str(s)):
            [sys.intern(bleak.uuids.normalize_uuid_str(c)) for c in clist]
            for s, clist in srvs.items()
        }
        cls.characteristics = {
            sys.intern(bleak.uuids.normalize_uuid_str(c)): p
            for c, p in srvs.items()
        }

    def __init__(self):
        self._notification_callbacks = {}

    _notification_callbacks: dict

    def notify(self, characteristic, value):
        """
        Pushes a notification of a characteristic change into the BLE stack.
        """

    def set_notify(self, characteristic, callback):
        """
        Sets the notification callback for the given characteristic.
        """


def resolve_characteristic(
    char_specifier: Union[bleak.backends.characteristic.BleakGATTCharacteristic,
                          int,
                          str,
                          uuid.UUID
                          ],
) -> str:
    """
    Normalizes all form of characteristic to a full UUID string.
    """
    if isinstance(char_specifier, bleak.backends.characteristic.BleakGATTCharacteristic):
        uid = char_specifier.uuid
    elif isinstance(char_specifier, int):
        # TODO: Look up handle
        uid = ...
    elif isinstance(char_specifier, uuid.UUID):
        uid = str(char_specifier)
    elif isinstance(char_specifier, str):
        uid = char_specifier
    else:
        raise TypeError(f"Cannot convert {char_specifier!r} into a UUID")

    return sys.intern(bleak.uuids.normalize_uuid_str(uid))


class BleakClientDummy(bleak.backends.client.BaseBleakClient):
    _connected: bool = False

    @property
    def mtu_size(self):
        ...

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def pair(self):
        ...

    async def unpair(self):
        ...

    @property
    def is_connected(self):
        return self._connected

    async def get_services(self):
        ...

    async def read_gatt_char(self, char_specifier):
        ...

    async def read_gatt_descriptor(self, handle):
        ...

    async def write_gatt_char(self, char_specifier, data, response):
        ...

    async def write_gatt_descriptor(self, handle, data):
        ...

    async def start_notify(self, characteristic, callback):
        ...

    async def stop_notify(self, char_specifier):
        ...
