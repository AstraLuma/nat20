import asyncio

import pytest

from nat20 import scan_for_dice
from pytest_pixels import DieFacade, dieresult


@pytest.mark.scanresults([
    dieresult(DieFacade.with_responses({
        b'\x01': b'\x02\x14\x0b\x00\x12\xa6\xbe\xb3Z\x8a\xf0\x060\x1e\x17\x87\x88d\x01\x05O\x00',
    })),
])
async def test_who():
    async with asyncio.timeout(1):
        async for sr in scan_for_dice():
            break
        else:
            assert False

        async with sr.hydrate() as device:
            iam = await device.who_are_you()

    assert iam
