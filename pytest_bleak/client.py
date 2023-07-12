import itertools
import sys
from typing import Self, Union, ClassVar, Optional, Any
import uuid
from uuid import UUID

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
            if base is not object:
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
            for c, p in chrs.items()
        }

    def __init__(self):
        self._notification_callbacks = {}

    _notification_callbacks: dict

    def notify(self, prop: str):
        """
        Pushes a notification of a characteristic change into the BLE stack.
        """
        if prop in self._notification_callbacks:
            self._notification_callbacks[prop]()

    def set_notify(self, prop: str, callback):
        """
        Sets the notification callback for the given characteristic.
        """
        self._notification_callbacks[prop] = callback


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
        raise NotImplementedError
    elif isinstance(char_specifier, uuid.UUID):
        uid = str(char_specifier)
    elif isinstance(char_specifier, str):
        uid = char_specifier
    else:
        raise TypeError(f"Cannot convert {char_specifier!r} into a UUID")

    return sys.intern(bleak.uuids.normalize_uuid_str(uid))


class Handled:
    _handle: int | None = None
    _generator = itertools.count(1)

    @property
    def handle(self):
        if self._handle is None:
            self._handle = next(self._generator)
        return self._handle


class BleakGATTServiceDummy(Handled, bleak.backends.service.BleakGATTService):
    def __init__(self, obj):
        super().__init__(obj)
        self._uuid = obj
        self._characteristics = []

    @property
    def uuid(self):
        return self._uuid

    @property
    def characteristics(self):
        return self._characteristics

    def add_characteristic(self,
                           characteristic: bleak.backends.characteristic.BleakGATTCharacteristic):
        self._characteristics.append(characteristic)


class BleakGATTCharacteristicDummy(Handled, bleak.backends.characteristic.BleakGATTCharacteristic):
    def __init__(self, obj: Any, max_write_without_response_size: int):
        super().__init__(obj, max_write_without_response_size)
        self._service, self._uuid = obj

    @property
    def service_uuid(self):
        return self._service.uuid

    @property
    def service_handle(self):
        return self._service.handle

    @property
    def uuid(self):
        return self._uuid

    @property
    def properties(self):
        raise NotImplementedError()

    @property
    def descriptors(self):
        raise NotImplementedError()

    def get_descriptor(
        self, specifier: Union[int, str, UUID]
    ) -> Union[bleak.backends.descriptor.BleakGATTDescriptor, None]:
        raise NotImplementedError()

    def add_descriptor(self, descriptor: bleak.backends.descriptor.BleakGATTDescriptor):
        raise NotImplementedError()


class BleakClientDummy(bleak.backends.client.BaseBleakClient):
    _connected: bool = False
    _paired: bool = False

    _impl: DeviceFacade

    def __init__(
        self,
        address_or_ble_device: Union[bleak.backends.device.BLEDevice, str],
        services: Optional[set[str]] = None,
        **kwargs,
    ):
        super().__init__(address_or_ble_device, **kwargs)
        if not isinstance(address_or_ble_device, bleak.backends.device.BLEDevice):
            raise TypeError("BleakClientDummy can't connect directly to an address.")

        devcls, = address_or_ble_device.details
        self._impl = devcls()

        self.services = bleak.backends.service.BleakGATTServiceCollection()
        for sid, chars in self._impl.services.items():
            svc = BleakGATTServiceDummy(sid)
            self.services.add_service(svc)
            for cid in chars:
                chr = BleakGATTCharacteristicDummy((svc, cid), self.mtu_size)
                svc.add_characteristic(chr)
                self.services.add_characteristic(chr)

    @property
    def mtu_size(self):
        return 517

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def pair(self):
        self._paired = True

    async def unpair(self):
        self._paired = False

    @property
    def is_connected(self):
        return self._connected

    async def get_services(self):
        return self.services

    async def read_gatt_char(self, char_specifier):
        cid = resolve_characteristic(char_specifier)
        prop = self._impl.characteristics[cid]
        return getattr(self._impl, prop)

    async def read_gatt_descriptor(self, handle):
        ...
        raise NotImplementedError()

    async def write_gatt_char(self, char_specifier, data, response):
        cid = resolve_characteristic(char_specifier)
        prop = self._impl.characteristics[cid]
        setattr(self._impl, prop, data)

    async def write_gatt_descriptor(self, handle, data):
        ...
        raise NotImplementedError()

    async def start_notify(self, characteristic, callback):
        cid = resolve_characteristic(characteristic)
        prop = self._impl.characteristics[cid]
        self._impl.set_notify(prop, lambda: callback(getattr(self._impl, prop)))

    async def stop_notify(self, char_specifier):
        cid = resolve_characteristic(char_specifier)
        prop = self._impl.characteristics[cid]
        self._impl.set_notify(prop, None)
