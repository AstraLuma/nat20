"""
Library to define packed messages and going between blobs and structures.
"""
import abc
import dataclasses
import logging
import struct
import sys
from typing import Optional, Self, Iterable
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


def _str_field_name(cls_or_object) -> Optional[str]:
    """
    Examines a dataclass's fields and returns the name of the final string field,
    if there is one.
    """
    flds = dataclasses.fields(cls_or_object)
    f = flds[-1]
    if f.type == str:
        return f.name


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

    If the last field is a `str`, then it consumes the entire rest of the message.
    """
    def __init_subclass__(cls, /, format: str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__struct_format = sys.intern(f"<{format}")

    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        sfld = _str_field_name(cls)
        if sfld is not None:
            l = struct.calcsize(cls.__struct_format)
            blob, bin = blob[:l], blob[l:]
        fields = struct.unpack(cls.__struct_format, blob)
        if sfld is None:
            return cls(*fields)
        else:
            return cls(*fields, bin.decode('utf-8'))

    def __struct_pack__(self) -> bytes:
        sfld = _str_field_name(self)
        fields = dataclasses.astuple(self)
        if sfld is None:
            return struct.pack(self.__struct_format, *fields)
        else:
            return struct.pack(self.__struct_format, *fields[:-1]) + fields[-1].encode('utf-8')


class StrMessage(Message, id=None):
    """
    Define a message with one string field.

    Must be a dataclass.
    """
    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        field = dataclasses.fields(cls)[-1].name
        return cls(**{field: blob.decode('utf-8')})

    def __struct_pack__(self) -> bytes:
        field = dataclasses.fields(self)[-1].name
        return getattr(self, field).encode('utf-8')


class EmptyMessage(Message, id=None):
    """
    Quick class for defining messages with no fields.
    """
    @classmethod
    def __struct_unpack__(cls, blob: bytes) -> Self:
        return cls()

    def __struct_pack__(self) -> bytes:
        return b""
