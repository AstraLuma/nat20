"""
Contains the messy details of communicating with a pixels die.
"""
import abc
import asyncio
import collections
import dataclasses
import struct
import sys
from typing import Optional, Self

import bleak


_messages = {}


def msgid(msg) -> Optional[int]:
    """
    Gets the ID of the given message.
    """
    return msg._Message__id


class Message(abc.ABC):
    """
    Base class for messages that get communicated with the die.

    Messages must be defined as::

        class Spam(Message, id=42):

    Pass :const:`None` as the ID if this should not be registered
    as a message (eg, is abstract).
    """
    @classmethod
    @abc.abstractmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        raise NotImplementedError

    @abc.abstractmethod
    def __struct_pack__(self) -> bytes:
        raise NotImplementedError

    def __init_subclass__(cls, /, id: int, **kwargs):
        print(kwargs)
        super().__init_subclass__(**kwargs)
        if id is not None:
            cls.__id = id
            _messages[id] = cls


class BasicMessage(Message, id=None):
    """
    Provides a helpful basic version of :class:`Message`
    for standard use cases.

        @dataclass
        class Spam(BasicMessage, id=42, format='i'):
           eggs: int

    Subclasses must also be a :module:`dataclass <dataclasses>`.
    """
    def __init_subclass__(cls, /, format: str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__struct_format = sys.intern(f"<{format}")

    def __struct_unpack__(cls, blob: bytes) -> Self:
        fields = struct.unpack(cls.__struct_format, blob)
        return cls(fields)

    def __struct_pack__(self) -> bytes:
        fields = dataclasses.astuple(self)
        return struct.pack(self.__struct_format, fields)


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
    _wait_queue: dict[type, list[asyncio.Future]]

    #: Event receivers
    _message_handlers: dict[type, list]

    def __init__(self):
        self._wait_queue = collections.defaultdict(list)
        self._message_handlers = collections.defaultdict(list)

    async def _message_pump_task(self):
        """
        Background task to receive & dispatch messages from the device.
        """

    async def _send(self, message: Message):
        """
        Send a message to the connected device
        """

    async def _wait(self, msgcls: type) -> Message:
        """
        Waits for a given message.

        Note that if you want to send and receive a response, you should use
        :meth:`_send_and_wait`, it has better async properties.
        """
        fut = asyncio.get_event_loop().create_future()
        self._wait_queue[msgid(msgcls)].append(fut)
        return await fut

    async def _send_and_wait(self, msg: Message, respcls: type) -> Message:
        """
        Sends a message and waits for the response.

        Returns the response.
        """
        fut = asyncio.get_event_loop().create_future()
        self._wait_queue[msgid(respcls)].append(fut)
        await self._send(msg)
        return await fut
