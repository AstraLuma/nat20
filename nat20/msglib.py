"""
Library to define packed messages and going between blobs and structures.
"""
import abc
import dataclasses
import logging
import struct
import sys
from typing import Self, Iterable
import typing_extensions


LOG = logging.getLogger(__name__)
_messages = {}


class UnrecognizedMessageError(ValueError):
    """
    The message ID in the given blob isn't recognized.
    """


class UnpackError(ValueError):
    """
    Unable to unpack the given blob.
    """


class AbstractMessageGivenError(TypeError):
    """
    Got an abstract message when a concrete one was required.
    """


def iter_msgs() -> Iterable[type['Message']]:
    """
    List all known messages.
    """
    yield from _messages.values()


def msgid(msg: 'Message') -> int:
    """
    Gets the ID of the given message.

    Raises an :error:`AbstractMessageGivenError` if the message doesn't have an ID.
    """
    try:
        return msg._Message__id
    except AttributeError:
        raise AbstractMessageGivenError(f"{msg!r} does not have an ID") from None


def pack(msg: 'Message') -> typing_extensions.Buffer:
    """
    Produce a blob from a message.
    """
    blob = bytes([msgid(msg)]) + msg.__struct_pack__()
    return blob


def unpack(blob: typing_extensions.Buffer) -> 'Message':
    """
    Turn a Message into a blob.
    """
    msgid, body = blob[0], blob[1:]
    try:
        msgcls = _messages[msgid]
    except KeyError as exc:
        raise UnrecognizedMessageError(f"Unknown message ID={msgid:X} ({blob!r})") from exc
    else:
        try:
            msg = msgcls.__struct_unpack__(body)
        except Exception as exc:
            raise UnpackError(f"Problem unpacking blob ({blob!r})") from exc
        else:
            return msg


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

    def __init_subclass__(cls, /, id: int | None, **kwargs):
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

    @ classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        fields = struct.unpack(cls.__struct_format, blob)
        return cls(*fields)

    def __struct_pack__(self) -> bytes:
        fields = dataclasses.astuple(self)
        return struct.pack(self.__struct_format, *fields)


class EmptyMessage(Message, id=None):
    """
    Quick class for defining messages with no fields.
    """
    @ classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        return cls()

    def __struct_pack__(self) -> bytes:
        return b""
