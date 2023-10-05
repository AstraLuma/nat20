#!/usr/bin/env python

import asyncio
import nat20
from nat20.messages import RollState_State, RollState


async def main():
    print("Looking for die...")
    async for sr in nat20.scan_for_dice():
        if sr.roll_state in (RollState_State.Handling, RollState_State.Rolling):
            die = sr.hydrate()
            break

    print(f"{die.name} ({die.flavor}) found, waiting for roll...")
    async with die.connect_with_reconnect():
        rolled = asyncio.Event()

        @die.got_roll_state.handler
        def got_roll(_, rs: RollState):
            if rs.state == RollState_State.OnFace:
                rolled.set()
                print(f"Got a {rs.face + 1}")

        await rolled.wait()  # Block until an appropriate event has been received.

asyncio.run(main())
