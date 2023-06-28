import asyncio

from pixels_bleak import Pixel


async def main():
    async for dev in Pixel.scan():
        print(dev)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
