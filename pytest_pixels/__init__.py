import asyncio
from typing import ClassVar, Self

import pytest_bleak
import nat20.constants


def dieresult(devcls, **_):
    # This is just the data from Francis.
    return pytest_bleak.result(
        devcls,
        local_name='Francis',
        manufacturer_data={
            0xFFFF: b'\x14\x0b\x01\nH'
        },
        service_data={
            nat20.constants.SERVICE_INFO: b'Z\x8a\xf0\x06\x17\x87\x88d',
        },
        service_uuids=[nat20.constants.SERVICE_INFO, nat20.constants.SERVICE_PIXELS],
        rssi=-76,
    )


class DieFacade(pytest_bleak.DeviceFacade):
    services = {
        nat20.constants.SERVICE_INFO: [],
        nat20.constants.SERVICE_PIXELS: [
            nat20.constants.CHARI_WRITE,
            nat20.constants.CHARI_NOTIFY,
        ]
    }

    characteristics = {
        nat20.constants.CHARI_WRITE: 'msg_inbox',
        nat20.constants.CHARI_NOTIFY: 'msg_outbox',
    }

    responses: ClassVar[dict[bytes, bytes]] = {}
    outbox: asyncio.Queue

    @classmethod
    def with_responses(cls, responses) -> type[Self]:
        """
        Returns a version of the class that'll produce these responses.
        """
        return type(cls.__name__, (cls,), {'responses': responses})

    def __init_subclass__(cls: type[Self]) -> None:
        super().__init_subclass__()
        for base in cls.mro():
            if base is not object:
                if hasattr(base, 'responses'):
                    cls.responses = base.responses | cls.responses

    def __init__(self):
        super().__init__()

        self.outbox = asyncio.Queue()

    @property
    def msg_inbox(self):
        """
        Messages from computer to die.
        """
        return b""

    @msg_inbox.setter
    def msg_inbox(self, data):
        msgid = data[0:1]
        if msgid in self.responses:
            self.outbox.put_nowait(self.responses[msgid])
            self.notify('msg_outbox')
        else:
            raise ValueError(f"No response known for {data!r}")

    @property
    def msg_outbox(self):
        """
        Messages from die to computer
        """
        return self.outbox.get_nowait()

    @msg_outbox.setter
    def msg_outbox(self, value):
        pass
