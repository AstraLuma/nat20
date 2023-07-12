import asyncio
from typing import Self

import bleak.backends.scanner


class BleakScannerDummy(bleak.backends.scanner.BaseBleakScanner):
    scans = []

    _task = None

    def __init__(
        self,
        detection_callback,
        service_uuids,
        scanning_mode,
        **kwargs,
    ):
        super().__init__(detection_callback, service_uuids)

    @classmethod
    def with_results(cls, results) -> type[Self]:
        """
        Returns a version of the class that'll produce these results.
        """
        return type(cls.__name__, (cls,), {'scans': results})

    async def _production_task(self):
        while True:
            for addr, name, ad, devclass in self.scans:
                dev = self.create_or_update_device(
                    addr,
                    name,
                    (devclass,),
                    ad
                )
                if self._callback is not None:
                    self._callback(dev, ad)
                await asyncio.sleep(0.1)

    async def start(self):
        self._task = asyncio.create_task(self._production_task())

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            await self._task
            self._task = None

    async def set_scanning_filter(self, **_):
        # Unsupported, we don't have this feature at all.
        pass
