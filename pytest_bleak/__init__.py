import random

import bleak.backends.scanner
import pytest

from .scanner import BleakScannerDummy
from .client import BleakClientDummy, DeviceFacade


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "scanresults(items): Register items to be returned in scanning")


def result(devclass: type[DeviceFacade], *, addr=None, name=None, **ad_params):
    """
    Helper to produce an appropriate scan result, autogenerating missing fields.
    """
    if addr is None:
        addr = ':'.join(f'{random.randint(0, 255):02X}' for _ in range(6))
    if name is None:
        name = 'Fred'  # What my girlfriend always suggests for a name
    ad = bleak.backends.scanner.AdvertisementData(**{
        'local_name': name,
        'manufacturer_data': {},
        'service_data': {},
        'service_uuids': list(devclass.services.keys()),
        'tx_power': 42,
        'rssi': -42,
        'platform_data': (),
    } | ad_params)
    # TODO: Normalize UUIDs
    return (addr, name, ad, devclass)


@pytest.fixture(autouse=True)
def bleak_dummy(request, mocker):
    """
    Sets the testing backend to be used automatically.
    """
    marker = request.node.get_closest_marker("scanresults")
    if marker is None:
        sr = []
    else:
        sr = marker.args[0]

    def get_platform_scanner_backend_type():
        return BleakScannerDummy.with_results(sr)

    def get_platform_client_backend_type():
        return BleakClientDummy

    mocker.patch('bleak.backends.scanner.get_platform_scanner_backend_type',
                 get_platform_scanner_backend_type)
    mocker.patch('bleak.get_platform_scanner_backend_type',
                 get_platform_scanner_backend_type)
    mocker.patch('bleak.backends.client.get_platform_client_backend_type',
                 get_platform_client_backend_type)
    mocker.patch('bleak.get_platform_client_backend_type',
                 get_platform_client_backend_type)
    yield
