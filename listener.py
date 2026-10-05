"""Minimal Archipelago client: second connection on the same slot, receives items,
turns profile-mapped items into effect requests. Runs in its own thread/event loop."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path

import websockets

log = logging.getLogger("overlay.ap")
AP_VERSION = {"major": 0, "minor": 6, "build": 0, "class": "Version"}  # bump to match your server if refused


class APListener:
    def __init__(self, server, slot, game, password, profile, emit,
                 state_dir="state", skip_backlog=False):
        self.server, self.slot, self.game, self.password = server, slot, game, password
        self.profile, self.emit = profile, emit
        self.state_dir, self.skip_backlog = Path(state_dir), skip_backlog
        self.uuid = str(uuid.uuid4())
        self.seed = ""
        self.item_names: dict[int, str] = {}
        self._pending: list[tuple[int, list]] = []
        self._last: int | None = None

    async def run(self):
        delay = 2
        while True:
            try:
                await self._connect()
                delay = 2
            except Exception as e:
                log.warning("connection problem: %s", e)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    async def _connect(self):
        urls = [self.server] if "://" in self.server else [f"wss://{self.server}", f"ws://{self.server}"]
        err = None
        for url in urls:
            try:
                async with websockets.connect(url, max_size=None, ping_timeout=None) as ws:
                    await self._session(ws)
                    return
            except (OSError, websockets.InvalidHandshake, websockets.InvalidMessage) as e:
                err = e
        raise err

    async def _session(self, ws):
        self._pending.clear()
        async for raw in ws:
            for msg in json.loads(raw):
                cmd = msg.get("cmd")
                if cmd == "RoomInfo":
                    self.seed = msg.get("seed_name", "")
                    await ws.send(json.dumps([
                        {"cmd": "GetDataPackage", "games": [self.game]},
                        {"cmd": "Connect", "password": self.password, "game": self.game,
                         "name": self.slot, "uuid": self.uuid, "version": AP_VERSION,
                         "items_handling": 0b111, "tags": ["TrapOverlay"], "slot_data": False},
                    ]))
                elif cmd == "ConnectionRefused":
                    raise RuntimeError(f"server refused connection: {msg.get('errors')}")
                elif cmd == "Connected":
                    log.info("connected to slot %s", self.slot)
                elif cmd == "DataPackage":
                    table = msg["data"]["games"].get(self.game, {}).get("item_name_to_id", {})
                    self.item_names = {v: k for k, v in table.items()}
                    self._flush()
                elif cmd == "ReceivedItems":
                    self._pending.append((msg["index"], msg["items"]))
                    if self.item_names:  # items can arrive before the data package
                        self._flush()

    # ---- item handling with replay protection ----
    def _state_path(self) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{self.seed}_{self.slot}")
        return self.state_dir / f"{safe}.json"

    def _last_index(self, index: int, n: int) -> int:
        if self._last is None:
            p = self._state_path()
            if p.exists():
                self._last = json.loads(p.read_text())["index"]
            elif self.skip_backlog and index == 0:
                self._last = index + n   # first run mid-game: don't re-fire old traps
            else:
                self._last = 0
        return self._last

    def _flush(self):
        while self._pending:
            index, items = self._pending.pop(0)
            last = self._last_index(index, len(items))
            for i, it in enumerate(items, start=index):
                if i < last:
                    continue
                name = self.item_names.get(it["item"])
                entry = self.profile.effects.get(name)
                if entry:
                    params = {k: v for k, v in entry.items() if k != "effect"} | {"item": name}
                    log.info("item %r -> %s", name, entry["effect"])
                    self.emit(entry["effect"], params)
            self._last = max(self._last, index + len(items))
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(json.dumps({"index": self._last}))
