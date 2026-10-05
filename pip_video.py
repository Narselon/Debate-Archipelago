"""Combined layouts of the PiP and video effects.

layout: game_in_video  - full-size background video, small live copy of the game on top
        video_in_game  - game stays full size, small video in a corner
params: everything video accepts (clip | clips | clip_dir, volume), plus
        scale (0.1-0.6, size of the small picture), corner (tl | tr | bl | br),
        and for game_in_video the PiP options mode (normal | mirror | flip), delay, fps."""
from __future__ import annotations

import logging

from manager import Effect
from pip_effect import PipEffect
from video import VideoEffect

log = logging.getLogger("overlay.pip_video")


class PipVideoEffect(Effect):
    name = "pip_video"

    def start(self, params):
        self._parts, self._video = [], None
        layout = params.get("layout", "game_in_video")
        scale = float(params.get("scale", 0.3))
        corner = params.get("corner", "br")

        if layout == "game_in_video":
            video = VideoEffect(self.ctx)
            video.start({**params, "size": 1.0, "corner": "c"})
            self._video = video
            self._parts.append(video)
            if video.done():                    # no clip / no QtMultimedia: don't show a lone PiP
                return
            pip = PipEffect(self.ctx)           # started second so it sits above the video
            pip.start({"scale": scale, "corner": corner, "mode": params.get("mode", "normal"),
                       "delay": params.get("delay", 0), "fps": params.get("fps", 20)})
            self._parts.append(pip)
            w = getattr(pip, "w", None)
            if w is not None:
                w.raise_()
        elif layout == "video_in_game":
            video = VideoEffect(self.ctx)
            video.start({**params, "size": scale, "corner": corner})
            self._video = video
            self._parts.append(video)
        else:
            log.warning("unknown layout %r (use game_in_video or video_in_game)", layout)

    def tick(self, now):
        for part in self._parts:
            part.tick(now)

    def done(self):
        return self._video is None or self._video.done()   # the clip drives the lifetime

    def stop(self):
        for part in reversed(self._parts):
            try:
                part.stop()
            except Exception:
                log.exception("failed to stop %s", part.name)