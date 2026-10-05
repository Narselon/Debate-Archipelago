"""Video interruption: plays a clip in a click-through, always-on-top window over the game."""
from __future__ import annotations

import logging
import random
from pathlib import Path

from PySide6.QtCore import QUrl

from manager import Effect
from overlay import exclude_when_ready, prepare

log = logging.getLogger("overlay.video")
EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4v"}


def fit_aspect(bw: int, bh: int, cw: int, ch: int) -> tuple:
    """Largest (w, h) with the clip's aspect ratio that fits inside a bw x bh box."""
    k = min(bw / cw, bh / ch)
    return max(1, int(cw * k)), max(1, int(ch * k))


def place_rect(l: int, t: int, W: int, H: int, w: int, h: int, corner: str = "c", m: int = 16) -> tuple:
    """Position a w x h box inside the (l, t, W, H) window. corner: c | tl | tr | bl | br."""
    if corner == "c":
        return l + (W - w) // 2, t + (H - h) // 2, w, h
    x = l + m if "l" in corner else l + W - w - m
    y = t + m if "t" in corner else t + H - h - m
    return x, y, w, h


def pick_clip(params: dict) -> str | None:
    if params.get("clips"):
        return random.choice(list(params["clips"]))
    if params.get("clip"):
        return params["clip"]
    d = params.get("clip_dir")
    if d:
        files = [p for p in Path(d).glob("*") if p.suffix.lower() in EXTS]
        if files:
            return str(random.choice(files))
    return None


class VideoEffect(Effect):
    """params: clip | clips: [..] | clip_dir, volume (0-1, default 0.5), size (0.2-1.0 of game window, default 1.0),
    corner (c | tl | tr | bl | br, default c). Small videos shrink their box to the clip's aspect ratio once loaded.
    Ends when the clip ends (or when `duration` runs out, whichever is first)."""
    name = "video"

    def start(self, params):
        self._done, self.w, self.player = False, None, None
        clip = pick_clip(params)
        if not clip or not Path(clip).exists():
            log.warning("no playable clip (%r)", clip)
            self._done = True
            return
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            log.warning("QtMultimedia not available")
            self._done = True
            return
        self.size = max(0.2, min(1.0, float(params.get("size", 1.0))))
        self.corner = params.get("corner", "c")
        self._fitted = False
        self.w = QVideoWidget()
        prepare(self.w, translucent=False)
        self.audio = QAudioOutput()
        self.audio.setVolume(max(0.0, min(1.0, float(params.get("volume", 0.5)))))
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.w)
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(self._error)
        self.player.setSource(QUrl.fromLocalFile(str(Path(clip).resolve())))
        self._place()
        self.w.show()
        exclude_when_ready(self.w, lambda ok: None)
        self.player.play()

    def done(self):
        return self._done

    def stop(self):
        if self.player:
            self.player.stop()
        if self.w:
            self.w.close()

    def _place(self, w=None, h=None):
        r = self.ctx.target.rect()
        self._box = (int(r.width() * self.size), int(r.height() * self.size))
        w, h = (w, h) if w else self._box
        self.w.setGeometry(*place_rect(r.left(), r.top(), r.width(), r.height(), w, h, self.corner))

    def _fit_to_clip(self):
        """Once the clip's resolution is known, drop the black bars on small videos."""
        if self._fitted or self.size >= 1.0:
            return
        try:
            from PySide6.QtMultimedia import QMediaMetaData
            res = self.player.metaData().value(QMediaMetaData.Key.Resolution)
            if res is not None and res.width() > 0 and res.height() > 0:
                self._place(*fit_aspect(*self._box, res.width(), res.height()))
                self._fitted = True
        except Exception:
            log.debug("could not fit video box to clip", exc_info=True)

    def _status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._done = True
        elif status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._fit_to_clip()

    def _error(self, *args):
        log.warning("video error: %s", args)
        self._done = True