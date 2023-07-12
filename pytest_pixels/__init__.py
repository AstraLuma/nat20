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

    # TODO: Make actual properties
