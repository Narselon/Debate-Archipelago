"""Windows input glue: gamepad proxy (XInput in -> ViGEm virtual pad out) and keyboard remap."""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import byref, c_byte, c_short, c_ubyte, c_ulong, c_ushort

from remap import PadRemap, PadState

log = logging.getLogger("overlay.inputs")


class _Gamepad(ctypes.Structure):
    _fields_ = [("wButtons", c_ushort), ("bLeftTrigger", c_ubyte), ("bRightTrigger", c_ubyte),
                ("sThumbLX", c_short), ("sThumbLY", c_short), ("sThumbRX", c_short), ("sThumbRY", c_short)]


class _State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", c_ulong), ("Gamepad", _Gamepad)]


class GamepadProxy:
    """Always-on passthrough: reads the physical pad, writes a virtual Xbox 360 pad.
    Bind the emulator to the VIRTUAL pad (usually X2 if your real pad is X1).
    Plug in the real pad BEFORE starting so it keeps slot 0 and the virtual one gets the next slot."""

    def __init__(self, pad_index: int = 0, poll_hz: int = 250):
        import vgamepad as vg  # needs the ViGEmBus driver installed
        try:
            self._xi = ctypes.windll.xinput1_4
        except OSError:
            self._xi = ctypes.windll.xinput9_1_0
        self.pad = vg.VX360Gamepad()
        self.index, self.period = pad_index, 1.0 / poll_hz
        self.remap: PadRemap | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last = None

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def set_remap(self, remap: PadRemap | None):
        self.remap = remap  # single reference swap; safe across threads

    def _loop(self):
        st = _State()
        while not self._stop.is_set():
            if self._xi.XInputGetState(self.index, byref(st)) == 0:
                g = st.Gamepad
                s = PadState(g.wButtons, g.bLeftTrigger, g.bRightTrigger,
                             g.sThumbLX, g.sThumbLY, g.sThumbRX, g.sThumbRY)
                r = self.remap
                if r is not None:
                    s = r.apply(s)
                if s != self._last:
                    rep = self.pad.report
                    rep.wButtons, rep.bLeftTrigger, rep.bRightTrigger = s.buttons, s.lt, s.rt
                    rep.sThumbLX, rep.sThumbLY, rep.sThumbRX, rep.sThumbRY = s.lx, s.ly, s.rx, s.ry
                    self.pad.update()
                    self._last = s
                time.sleep(self.period)
            else:
                time.sleep(0.25)  # physical pad not connected


class KeyboardRemap:
    """Swallows physical keys and injects the mapped ones. Names: single characters or
    pynput Key names (left, right, up, down, space, shift, ctrl, ...)."""

    def __init__(self, keymap: dict):
        self.keymap = keymap
        self.listener = None
        self.held = set()

    def start(self):
        from pynput import keyboard
        ctl = keyboard.Controller()

        def vk(name):
            if len(name) == 1:
                return ctypes.windll.user32.VkKeyScanW(ord(name)) & 0xFF
            return getattr(keyboard.Key, name).value.vk

        def key(name):
            return name if len(name) == 1 else getattr(keyboard.Key, name)

        table = {vk(k): key(v) for k, v in self.keymap.items()}

        def filt(msg, data):
            if data.flags & 0x10:          # injected by us (or another tool): leave alone, avoids loops
                return True
            target = table.get(data.vkCode)
            if target is None:
                return True
            if msg in (0x100, 0x104):      # WM_KEYDOWN / WM_SYSKEYDOWN
                ctl.press(target)
                self.held.add(target)
            else:
                ctl.release(target)
                self.held.discard(target)
            self.listener.suppress_event()  # swallow the physical key
            return True

        self.listener = keyboard.Listener(win32_event_filter=filt)
        self.listener.start()
        self._ctl = ctl

    def stop(self):
        if self.listener:
            self.listener.stop()
        for k in list(self.held):          # don't leave remapped keys stuck down
            try:
                self._ctl.release(k)
            except Exception:
                pass
        self.held.clear()
