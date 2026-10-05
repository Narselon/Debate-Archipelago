import asyncio

import websockets

from fake_server import FakeAP
from listener import APListener
from profiles import load_profile

GAME = "Pokemon Red and Blue"
NAMES = ["Poke Doll", "Nugget", "Full Heal", "Other"]


async def until(cond, timeout=5):
    end = asyncio.get_event_loop().time() + timeout
    while not cond():
        assert asyncio.get_event_loop().time() < end, "timed out"
        await asyncio.sleep(0.02)


def make_listener(port, fired, state_dir, **kw):
    prof = load_profile(GAME, "games")
    return APListener(f"ws://127.0.0.1:{port}", "Jon", GAME, None, prof,
                      lambda n, p: fired.append((n, p["item"])), state_dir=str(state_dir), **kw)


def port_of(server):
    return server.sockets[0].getsockname()[1]


def test_end_to_end_and_no_replay_on_restart(tmp_path):
    async def run():
        fake = FakeAP(GAME, NAMES)
        async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
            fired = []
            await fake.push("Poke Doll"); await fake.push("Other")      # already waiting at connect time
            t = asyncio.create_task(make_listener(port_of(server), fired, tmp_path).run())
            await until(lambda: len(fired) == 1)
            await fake.push("Nugget")                                   # arrives live
            await until(lambda: len(fired) == 2)
            t.cancel()
            assert fired == [("blinds", "Poke Doll"), ("reverse_controls", "Nugget")]

            fired2 = []                                                 # 'restart': same state dir
            t2 = asyncio.create_task(make_listener(port_of(server), fired2, tmp_path).run())
            await asyncio.sleep(0.5)
            assert fired2 == []                                         # backlog not replayed
            await fake.push("Full Heal")
            await until(lambda: len(fired2) == 1)
            t2.cancel()
            assert fired2 == [("cleanse", "Full Heal")]
    asyncio.run(run())


def test_items_before_datapackage(tmp_path):
    async def run():
        fake = FakeAP(GAME, NAMES, dp_last=True)
        async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
            fired = []
            await fake.push("Nugget")
            t = asyncio.create_task(make_listener(port_of(server), fired, tmp_path).run())
            await until(lambda: len(fired) == 1)
            t.cancel()
    asyncio.run(run())


def test_skip_backlog(tmp_path):
    async def run():
        fake = FakeAP(GAME, NAMES)
        async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
            fired = []
            await fake.push("Poke Doll")
            t = asyncio.create_task(make_listener(port_of(server), fired, tmp_path, skip_backlog=True).run())
            await asyncio.sleep(0.5)
            assert fired == []
            await fake.push("Nugget")
            await until(lambda: len(fired) == 1)
            t.cancel()
    asyncio.run(run())
