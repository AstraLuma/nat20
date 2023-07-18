"""
Contains the messy details of communicating with a pixels die.
"""
import asyncio
import collections
import inspect
import logging
from typing import Callable

import bleak

from .constants import CHARI_NOTIFY, CHARI_WRITE
from .msglib import Message, pack, unpack

LOG = logging.getLogger(__name__)


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

    async def connect(self):
        """
        Does the bits necessary to start receiving stuff.
        """
        # https://github.com/hbldh/bleak/discussions/1350#discussioncomment-6308104
        # mtu = await _get_real_mtu(self._client)
        # print("MTU:", mtu)
        # assert mtu >= 517, f"Insufficient MTU ({mtu} < 517)"
        await self._client.start_notify(CHARI_NOTIFY, self._recv_notify)

    async def disconnect(self, *exc):
        """
        Does the bits necessary to stop receiving stuff.
        """
        await self._client.stop_notify(CHARI_NOTIFY)

    async def _recv_notify(self, _, packet: bytearray):
        """
        Callback for bleak.

        :meta private:
        """
        try:
            msg = unpack(packet)
        except Exception:
            LOG.exception("Unable to unpack packet %r", packet)
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
        blob = pack(message)
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
