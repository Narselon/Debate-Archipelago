"""Sanity-check that every file in your folder is the current version.
Run from the trap_overlay folder:  python tools/check_install.py"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FILES = ["main.py", "listener.py", "manager.py", "profiles.py", "target.py", "effects.py", "colorfx.py",
         "colormath.py", "overlay.py", "pip_effect.py", "pip_video.py", "video.py", "delaybuf.py",
         "remap.py", "inputs.py"]
OLD_FILES = {"pip.py": "rename-collision with the real pip; delete it", "grayscale.py": "replaced by colorfx.py; delete it"}
SYMBOLS = [
    ("manager", "Effect.done"), ("manager", "EffectManager.clear_all"), ("target", "Target.physical"),
    ("video", "place_rect"), ("video", "fit_aspect"), ("overlay", "exclude_from_capture"),
    ("colorfx", "InvertEffect"), ("pip_effect", "PipEffect"), ("pip_video", "PipVideoEffect"),
    ("profiles", "Profile"), ("remap", "PadRemap"), ("delaybuf", "DelayBuffer"), ("listener", "APListener"),
    ("inputs", "GamepadProxy"), ("effects", "REGISTRY"),
]
EFFECTS = {"blinds", "grayscale", "invert", "reverse_controls", "pip", "video", "pip_video"}

problems = 0


def report(ok: bool, msg: str):
    global problems
    problems += not ok
    print(("  ok     " if ok else "  PROBLEM ") + msg)


print("files")
for f in FILES:
    report((ROOT / f).exists(), f"{f} present")
for f, why in OLD_FILES.items():
    report(not (ROOT / f).exists(), f"{f} absent" + ("" if not (ROOT / f).exists() else f"  <- {why}"))

print("dependencies")
# (module, pip package, what needs it, windows only)
DEPS = [("PySide6", "PySide6", "everything", False), ("PySide6.QtMultimedia", "PySide6", "video effects", False),
        ("websockets", "websockets", "Archipelago connection", False), ("yaml", "pyyaml", "profiles", False),
        ("psutil", "psutil", "finding the emulator window", False),
        ("win32gui", "pywin32", "finding the emulator window", True),
        ("win32process", "pywin32", "finding the emulator window", True),
        ("mss", "mss", "PiP screen capture", False), ("pynput", "pynput", "panic hotkey, keyboard reversal", False),
        ("vgamepad", "vgamepad (needs the ViGEmBus driver)", "gamepad reversal", True)]
for mod, pkg, why, win_only in DEPS:
    if win_only and sys.platform != "win32":
        report(True, f"{mod} skipped (Windows only)")
        continue
    try:
        importlib.import_module(mod)
        report(True, f"{mod}")
    except BaseException as e:
        report(False, f"{mod} failed to import ({type(e).__name__}); needed for {why}.  py -m pip install {pkg.split()[0]}")

print("symbols (a missing one means that file is an older version)")
for mod, path in SYMBOLS:
    try:
        obj = importlib.import_module(mod)
        for part in path.split("."):
            obj = getattr(obj, part)
        report(True, f"{mod}.{path}")
    except Exception as e:
        report(False, f"{mod}.{path}  ({type(e).__name__}: {e})")

print("registry / main / profile")
try:
    reg = set(importlib.import_module("effects").REGISTRY)
    report(EFFECTS <= reg, f"effects registered: {sorted(reg)}")
except Exception as e:
    report(False, f"effects registry ({e})")
main_src = (ROOT / "main.py").read_text(encoding="utf-8") if (ROOT / "main.py").exists() else ""
report("--test-item" in main_src, "main.py has --test-item")
try:
    prof = importlib.import_module("profiles").load_profile("Pokemon Red and Blue", str(ROOT / "games"))
    report("Max Revive" in prof.effects, f"pokemon_rb.yaml loads ({len(prof.effects)} items)")
except BaseException as e:
    report(False, f"pokemon_rb.yaml ({e})")

print("\nAll good." if not problems else f"\n{problems} problem(s): re-save the files marked above from the latest attachments.")
sys.exit(1 if problems else 0)