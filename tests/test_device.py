import pytest
from pytest_bleak.client import DeviceFacade

from nat20 import scan_for_dice
from pytest_pixels import DieFacade, dieresult


@pytest.mark.scanresults([
    dieresult(DieFacade),
])
async def test_who():
    async for sr in scan_for_dice():
        break
    else:
        assert False

    async with sr.connect() as device:
        iam = await device.who_are_you()

    assert iam
