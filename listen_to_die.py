import asyncio
import logging.config

from pixels_bleak import scan_for_dice

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
        'pixels_bleak': {
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

    async with sr.connect() as die:
        @die.handler(...)
        def recv(msg):
            print(f"Received {msg}")
        print(f"{die=}")
        print(await die.who_are_you())
        print(await die.roll_state())
        await die.blink(
            count=3,
            duration=500,
            color=0xFFFFFF,
            face_mask=0xFF,
            fade=0,
            loop=0,
        )
        await asyncio.sleep(10)

asyncio.run(main())
