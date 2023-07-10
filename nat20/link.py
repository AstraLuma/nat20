"""
Contains the messy details of communicating with a pixels die.
"""
import abc
import asyncio
import collections
import dataclasses
import inspect
import logging
import struct
import sys
from typing import Callable, Optional, Self, Iterable

import bleak

from .constants import CHARI_NOTIFY, CHARI_WRITE


LOG = logging.getLogger(__name__)


_messages = {}


def iter_msgs() -> Iterable[type['Message']]:
    """
    List all known messages.
    """
    yield from _messages.values()


def msgid(msg) -> Optional[int]:
    """
    Gets the ID of the given message.

    Returns :const:`None` if the message doesn't have one.
    """
    return msg._Message__id


class Message(abc.ABC):
    """
    Base class for messages that get communicated with the die.

    Messages must be defined as::

        class Spam(Message, id=42):

    Pass :const:`None` as the ID if this should not be registered
    as a message (eg, is abstract).

    Args:
        id (int|None): The message ID or None.
    """
    @classmethod
    @abc.abstractmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        """
        Construct an instance from a message blob.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def __struct_pack__(self) -> bytes:
        """
        Turn this message back into a blob.
        """
        raise NotImplementedError

    def __init_subclass__(cls, /, id: int, **kwargs):
        super().__init_subclass__(**kwargs)
        if id is not None:
            cls.__id = id
            _messages[id] = cls


class BasicMessage(Message, id=None):
    """
    Provides a helpful basic version of :class:`Message`
    for standard use cases.

    ::

        @dataclass
        class Spam(BasicMessage, id=42, format='i'):
           eggs: int

    Subclasses must also be a :mod:`dataclass <dataclasses>`.

    Args:
        id (int|None): The message ID, or None
        format (str): The format in :mod:`struct` form.
    """
    def __init_subclass__(cls, /, format: str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__struct_format = sys.intern(f"<{format}")

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        fields = struct.unpack(cls.__struct_format, blob)
        return cls(*fields)

    def __struct_pack__(self) -> bytes:
        fields = dataclasses.astuple(self)
        return struct.pack(self.__struct_format, *fields)


def _call_or_task(func, *pargs, **kwargs):
    """
    Calls the given function. Async functions are wrapped in a Task.
    """
    rv = func(*pargs, **kwargs)
    if inspect.isawaitable(rv):
        asyncio.ensure_future(rv)


async def _get_real_mtu(client):
    # https://github.com/hbldh/bleak/blob/master/examples/mtu_size.py
    if client._backend.__class__.__name__ == "BleakClientBlueZDBus":
        await client._backend._acquire_mtu()

    return client.mtu_size


class PixelLink:
    """
    All the messy details of communicating with a Pixels die.

    Not really meant to be user-accessible.
    """
    _client: bleak.BleakClient

    # Ok, so the way message dispatch is handled:
    # 1. A message is received and parsed
    # 2. If there's any Futures in the in _wait_queue, give it to the first one
    # 3. Otherwise, create tasks with each of _message_handlers
    # This kinda assumes that if a message is used for both broadcast and
    # response, the message immediately following the send is the reply. Which
    # sounds untrue with network latency and asynchronous weirdness.

    #: Handlers waiting for a one-time response
    #:
    #: :meta public:
    _wait_queue: dict[type, list[asyncio.Future]]

    #: Event receivers
    #:
    #: :meta public:
    _message_handlers: dict[type, list[Callable[[Message], None]]]

    def __init__(self):
        self._wait_queue = collections.defaultdict(list)
        self._message_handlers = collections.defaultdict(list)

    async def __aenter__(self):
        """
        Does the bits necessary to start receiving stuff.
        """
        # https://github.com/hbldh/bleak/discussions/1350#discussioncomment-6308104
        # mtu = await _get_real_mtu(self._client)
        # print("MTU:", mtu)
        # assert mtu >= 517, f"Insufficient MTU ({mtu} < 517)"
        await self._client.start_notify(CHARI_NOTIFY, self._recv_notify)

    async def __aexit__(self, *exc):
        """
        Does the bits necessary to stop receiving stuff.
        """
        print("Unsubbing")
        await self._client.stop_notify(CHARI_NOTIFY)

    async def _recv_notify(self, _, packet: bytearray):
        """
        Callback for bleak.

        :meta private:
        """
        msgid, blob = packet[0], packet[1:]
        try:
            msgcls = _messages[msgid]
        except KeyError:
            LOG.error("Unknown message ID=%i", msgid)
        else:
            try:
                msg = msgcls.__struct_unpack__(blob)
            except Exception:
                LOG.exception("Problem unpacking packet")
            else:
                self._dispatch(msg)

    def _dispatch(self, message: Message):
        """
        Calls the handlers of a message & performs maintenance.

        :meta private:
        """
        LOG.debug("Dispatching %r", message)
        msgcls = type(message)
        if len(self._wait_queue[msgcls]):
            fut = self._wait_queue[msgcls].pop(0)
            fut.set_result(message)
        else:
            for handler in self._message_handlers[msgcls]:
                _call_or_task(handler, message)

    async def _send(self, message: Message):
        """
        Send a message to the connected device

        :meta public:
        """
        blob = bytes([msgid(message)]) + message.__struct_pack__()
        await self._client.write_gatt_char(CHARI_WRITE, blob)

    async def _wait(self, msgcls: type[Message]) -> Message:
        """
        Waits for a given message.

        Note that if you want to send and receive a response, you should use
        :meth:`_send_and_wait`, it has better async properties.

        :meta public:
        """
        fut = asyncio.get_event_loop().create_future()
        self._wait_queue[msgcls].append(fut)
        return await fut

    async def _send_and_wait(self, msg: Message, respcls: type[Message]) -> Message:
        """
        Sends a message and waits for the response.

        Returns the response.

        :meta public
        """
        fut = asyncio.get_event_loop().create_future()
        self._wait_queue[respcls].append(fut)
        await self._send(msg)
        return await fut
