import asyncio

import pytest
from pytest_bleak import result
from pytest_bleak.client import DeviceFacade

from nat20 import scan_for_dice
from pytest_pixels import DieFacade, dieresult


class EmptyDev(DeviceFacade):
    pass


@pytest.mark.scanresults([
    result(EmptyDev),
])
async def test_scan_nodice():
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.25):
            async for _ in scan_for_dice():
                assert False


@pytest.mark.scanresults([
    result(EmptyDev),
    dieresult(DieFacade),
])
async def test_scan_yesdice():
    got_dice = False
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):
            async for sr in scan_for_dice():
                got_dice = True
    assert got_dice
