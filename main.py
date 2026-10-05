"""Archipelago trap overlay.
Run:        python main.py --server archipelago.gg:38281 --slot Jon --game "Pokemon Red and Blue"
Local test: python main.py --test blinds,grayscale --test-duration 15 --game "Pokemon Red and Blue"
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import threading
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from effects import REGISTRY
from listener import APListener
from manager import EffectManager
from profiles import load_profile
from target import Target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server")
    ap.add_argument("--slot")
    ap.add_argument("--game", required=True, help="exact AP game name; selects the profile")
    ap.add_argument("--password")
    ap.add_argument("--profiles", default="games")
    ap.add_argument("--skip-backlog", action="store_true",
                    help="on first run for a seed, ignore items already received")
    ap.add_argument("--hotkey", default="<ctrl>+<alt>+<f12>", help="panic key: clears all effects")
    ap.add_argument("--test", help="comma-separated effects to fire locally instead of connecting")
    ap.add_argument("--test-item", help="comma-separated PROFILE ITEM NAMES to fire locally, exactly as in the YAML "
                    '(e.g. "Poke Doll,Full Heal"); uses that entry\'s full settings')
    ap.add_argument("--test-gap", type=float, default=0.2, help="seconds between --test-item firings")
    ap.add_argument("--test-duration", type=float, default=20)
    ap.add_argument("--no-pad", action="store_true", help="don't start the virtual gamepad proxy")
    args = ap.parse_args()
    local = bool(args.test or args.test_item)
    if not local and not (args.server and args.slot):
        ap.error("--server and --slot are required unless --test or --test-item is used")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    profile = load_profile(args.game, args.profiles)
    ctx = SimpleNamespace(target=Target(profile.process), profile=profile, pad=None)

    if profile.input in ("gamepad", "both") and not args.no_pad:
        try:
            from inputs import GamepadProxy
            ctx.pad = GamepadProxy(profile.pad_index)
            ctx.pad.start()
            logging.info("virtual gamepad proxy running - bind your emulator to the virtual pad")
        except Exception as e:
            logging.warning("gamepad proxy unavailable: %s", e)

    mgr = EffectManager(REGISTRY, ctx, profile.limits)

    if local:
        def params_for(name):
            # reuse the profile's own settings for this effect (clip_dir, scale, mode, ...)
            base = next((dict(e) for e in profile.effects.values() if e.get("effect") == name), {})
            base.pop("effect", None)
            base["duration"] = args.test_duration
            return base

        for i, name in enumerate(n.strip() for n in (args.test or "").split(",") if n.strip()):
            QTimer.singleShot(500 + 200 * i, lambda n=name: mgr.request.emit(n, params_for(n)))

        for i, item in enumerate(n.strip() for n in (args.test_item or "").split(",") if n.strip()):
            entry = profile.effects.get(item)
            if entry is None:
                logging.error("--test-item %r is not in the profile (items: %s)", item, ", ".join(profile.effects))
                continue
            params = {k: v for k, v in entry.items() if k != "effect"} | {"item": item}
            QTimer.singleShot(int(500 + 1000 * args.test_gap * i),
                              lambda e=entry["effect"], q=params: mgr.request.emit(e, q))
    else:
        listener = APListener(args.server, args.slot, args.game, args.password, profile,
                              emit=mgr.request.emit, skip_backlog=args.skip_backlog)
        threading.Thread(target=lambda: asyncio.run(listener.run()), daemon=True).start()

    try:
        from pynput import keyboard
        keyboard.GlobalHotKeys({args.hotkey: mgr.kill.emit}).start()
    except ImportError:
        logging.warning("pynput not installed; no panic hotkey")

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer()           # lets Python see Ctrl+C while Qt's loop runs
    keepalive.timeout.connect(lambda: None)
    keepalive.start(500)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()