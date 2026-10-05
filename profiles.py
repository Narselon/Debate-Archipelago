from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from remap import PadRemap


@dataclass
class Profile:
    game: str
    process: str
    effects: dict          # item name -> {effect: ..., duration: ..., ...}
    limits: dict
    input: str = "gamepad"             # gamepad | keyboard | both | none
    pad_index: int = 0
    reverse_pad: PadRemap | None = None
    reverse_keys: dict = field(default_factory=dict)


def load_profile(game: str, directory: str) -> Profile:
    for p in sorted(Path(directory).glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if data.get("game") != game:
            continue
        rev = data.get("reverse_controls") or {}
        pad = PadRemap(rev.get("buttons"), rev.get("axes")) if (rev.get("buttons") or rev.get("axes")) else None
        return Profile(
            game=game,
            process=(data.get("window_match") or {}).get("process", ""),
            effects=data.get("effects") or {},
            limits=data.get("limits") or {},
            input=data.get("input", "gamepad"),
            pad_index=int(data.get("pad_index", 0)),
            reverse_pad=pad,
            reverse_keys=rev.get("keys") or {},
        )
    raise SystemExit(f"No profile for game {game!r} in {directory!r}")
