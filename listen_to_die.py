#!/usr/bin/env python3
import asyncio
import logging.config

from nat20 import scan_for_dice

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # Default is stderr
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': False
        },
        'nat20': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
})


async def main():
    async for sr in scan_for_dice():
        break
    else:
        raise RuntimeError("nope")
    print(f"{sr=}")
    assert sr is not None

    async with sr.hydrate().connect_with_reconnect() as die:
        @die.got_roll_state.handler
        @die.got_battery_level.handler
        def recv(_, msg):
            print(f"Received {msg}")
        print(f"{die=}")
        print(await die.who_are_you())
        print(await die.get_roll_state())
        print(await die.get_battery_level())
        print("RSSI:", await die.get_rssi())
        print("Temps:", await die.get_temperature())
        # await die.blink(
        #     count=3,
        #     duration=500,
        #     color=0xFFFFFF,
        #     face_mask=0xFF,
        #     fade=0,
        #     loop=0,
        # )
        print(1)
        await die.blink(color=0x000000FF, duration=3, fade=0)
        await asyncio.sleep(3)
        print(2)
        await die.blink(color=0x0000FF00, duration=3, fade=0x7F)
        await asyncio.sleep(3)
        print(3)
        await die.blink(color=0x00FF0000, duration=3, fade=0xFF)
        await asyncio.sleep(3)
        await die.blink(color=0xFFFFFF, duration=5, fade=0xEE, count=...)

        await asyncio.sleep(10)
        await die.stop_all_animations()
        await asyncio.sleep(3)

asyncio.run(main())
