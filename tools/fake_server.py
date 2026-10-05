"""Tiny fake Archipelago server: enough protocol to exercise listener.py without a real multiworld.
Manual use:  python tools/fake_server.py --game "Pokemon Red and Blue"
then run main.py with --server ws://127.0.0.1:38281 --slot Jon --game "Pokemon Red and Blue"
and type an item name (as written in the profile YAML) + Enter to 'send' it."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeAP:
    def __init__(self, game, item_names, seed="fakeseed", dp_last=False):
        self.game, self.seed, self.dp_last = game, seed, dp_last
        self.ids = {n: i + 1 for i, n in enumerate(item_names)}
        self.sent: list[int] = []
        self.clients = set()

    @staticmethod
    def _item(i):
        return {"item": i, "location": 0, "player": 1, "flags": 0}

    async def handler(self, ws):
        await ws.send(json.dumps([{"cmd": "RoomInfo", "seed_name": self.seed, "games": [self.game]}]))
        self.clients.add(ws)
        try:
            async for raw in ws:
                msgs = json.loads(raw)
                if self.dp_last:   # exercise the 'items arrive before the data package' path
                    msgs.sort(key=lambda m: m["cmd"] == "GetDataPackage")
                for m in msgs:
                    if m["cmd"] == "GetDataPackage":
                        await ws.send(json.dumps([{"cmd": "DataPackage", "data": {
                            "games": {self.game: {"item_name_to_id": self.ids}}}}]))
                    elif m["cmd"] == "Connect":
                        await ws.send(json.dumps([
                            {"cmd": "Connected", "slot": 1, "team": 0},
                            {"cmd": "ReceivedItems", "index": 0, "items": [self._item(i) for i in self.sent]},
                        ]))
        finally:
            self.clients.discard(ws)

    async def push(self, name):
        self.sent.append(self.ids[name])
        msg = json.dumps([{"cmd": "ReceivedItems", "index": len(self.sent) - 1,
                           "items": [self._item(self.ids[name])]}])
        for ws in list(self.clients):
            await ws.send(msg)


async def _main(args):
    from profiles import load_profile
    prof = load_profile(args.game, args.profiles)
    fake = FakeAP(args.game, list(prof.effects))
    async with websockets.serve(fake.handler, "127.0.0.1", args.port):
        print(f"fake AP on ws://127.0.0.1:{args.port}; items: {', '.join(fake.ids)}")
        while True:
            line = (await asyncio.to_thread(input, "send> ")).strip()
            if line in fake.ids:
                await fake.push(line)
            elif line:
                print("unknown item; choose from:", ", ".join(fake.ids))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--profiles", default="games")
    ap.add_argument("--port", type=int, default=38281)
    asyncio.run(_main(ap.parse_args()))
