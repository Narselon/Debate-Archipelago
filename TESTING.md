# Testing guide

All commands run from the `trap_overlay` folder. `G` below means `--game "Pokemon Red and Blue"`.
`--test-item` fires **profile item names exactly as written in `games/pokemon_rb.yaml`**, using that entry's
full settings. `--test-gap N` sets seconds between firings (default 0.2). Panic key: **Ctrl+Alt+F12**.

## 0. Setup
- Select your interpreter (Ctrl+Shift+P > Python: Select Interpreter), then `py -m pip install -r requirements.txt`.
- For gamepad tests, install the **ViGEmBus** driver and plug in your real pad *before* starting anything.
- Put any short .mp4/.webm in `clips/` (a 3s `test_pattern.mp4` works).

## 1. Automated (no Windows needed)
`pytest` (Linux/CI: `QT_QPA_PLATFORM=offscreen pytest`). Covers remap math, color math, delay buffer, manager rules
(stack / cap / queue / cooldown / cleanse / self-ending effects), PiP+video layouts, and the AP listener against a
fake server (live items, restart without replay, items-before-datapackage, `--skip-backlog`).

## 2. Each effect on its own (Windows, no server, no game)
| Feature | Command | Pass if |
|---|---|---|
| Blinds | `python main.py G --test-item "Poke Doll"` | slow slats close/open over the emulator window (or whole screen if no emulator); never flickers faster than ~1 cycle / 3s |
| Grayscale | `... --test-item "Fresh Water"` | whole desktop goes gray, returns to color on expiry |
| Invert | `... --test-item "Repel"` | colors invert, restore on expiry |
| Stacked color | `... --test-item "Fresh Water,Repel" --test-gap 3` | gray, then inverted gray; when the first expires the other stays; screen normal after both |
| PiP | `... --test-item "Super Potion"` | mirrored live copy in bottom-right, **not** a tunnel of itself; follows the emulator window if dragged |
| PiP variants | edit the YAML entry: `mode: flip`, `corner: tl`, `scale: 0.5`, `delay: 3` | flipped / moved / bigger / copy lags ~3s behind the game |
| Video | `... --test-item "Escape Rope"` | clip covers the game, plays with sound, ends when the clip ends, emulator keeps keyboard focus |
| Small video | set `size: 0.3`, `corner: tr` on the video entry | small clip in the corner, no black bars around it |
| Gameplay over video | `... --test-item "Max Revive"` | full-size clip with a small live game copy on top (PiP stays above the video) |
| Video over gameplay | `... --test-item "Max Ether"` | game stays full size, small clip in the top-right |
| Panic key | start any effect above, press Ctrl+Alt+F12 | everything clears immediately, including the video and the color filter |

## 3. Manager rules
| Rule | Command | Pass if |
|---|---|---|
| Stacking extends | `--test-item "Poke Doll,Poke Doll" --test-gap 5` | one blinds window, lasts ~30s past the second firing (capped by `max_duration`), log shows one `started blinds` |
| Concurrency cap + queue | `--test-item "Poke Doll,Fresh Water,Repel" --test-gap 1` (`max_concurrent: 2`) | third effect starts only when one of the first two ends |
| Cooldown | `--test-item "Nugget,Nugget" --test-gap 25` with `duration: 20, cooldown: 60` | second firing waits until ~60s after the first ended |
| Cleanse all | `--test-item "Poke Doll,Fresh Water,Full Heal" --test-gap 3` | log shows `cleansed all`, blinds and gray vanish, queued effects dropped |
| Targeted cleanse | uncomment `"Antidote"` in the YAML, then `--test-item "Poke Doll,Nugget,Antidote" --test-gap 3` | only `reverse_controls` is cleared, blinds continue |
| Unknown item | `--test-item "Nope"` | clear error listing the valid item names |

## 4. Reverse controls
**Gamepad** (needs ViGEmBus + `vgamepad`; log must say `virtual gamepad proxy running`):
1. Open a gamepad tester website or Windows "Set up USB game controllers" and look at the **virtual** pad (usually the 2nd one).
2. Idle: press buttons on your real pad. The virtual pad should mirror them with no noticeable delay.
3. `python main.py G --test-item "Nugget"` (20s). Now Up reads as Down, Left as Right, A as B, and so on.
4. Hold a button as the effect expires. It must not stay stuck; mapping returns to normal.
5. Fire `"Nugget"` then `"Full Heal"` (`--test-gap 3`): mapping restores at the cleanse.
6. OoT profile: sticks should read inverted (both axes), C-stick too; A/B swapped.

**Keyboard**: set `input: keyboard` (or `both`) in the YAML, run `--test-item "Nugget"`, focus Notepad.
Pressing Left arrow should move the caret right, Up down. Hold a key through expiry: no stuck key afterward.
This path is the least tested. If an emulator ignores injected keys, tell me which one and how it reads input.

**In the emulator**: BizHawk > Config > Controllers, bind to the virtual pad (X2), load the ROM, fire the effect,
confirm menus and movement are reversed. Super Metroid's profile only swaps A/B by default (gentle).

## 5. Archipelago connection
**Fake server** (no Archipelago install):
```
python tools/fake_server.py --game "Pokemon Red and Blue"        # terminal 1
python main.py --server ws://127.0.0.1:38281 --slot Jon G        # terminal 2
```
At the `send>` prompt type `Poke Doll`, `Nugget`, `Full Heal`... Each should fire its effect.
- **Replay protection:** stop and restart terminal 2. Nothing should re-fire.
- **Reconnect:** stop terminal 1, wait, start it again; terminal 2 logs a connection problem and reconnects.
  *Delete the `state/` folder first*: a restarted fake server forgets its history, so old saved indexes would skip new items.
- **Mid-game start:** delete `state/`, send two items, start terminal 2 with `--skip-backlog`: those two must not fire; the next one does.

**Real server, no emulator:** generate a throwaway multiworld with your game, host it with `MultiServer.py`, run
`python main.py --server localhost:38281 --slot <your slot> G`, and in the server console type `/send <slot> "<item name>"`.
Real item names must match the YAML. List them with `--test-item "Nope"` (shows the YAML's names) and check the apworld's item table.

**Real game:** run your normal AP client for the emulator plus this overlay on the same slot, collect a mapped item.

## 6. Per-game checklist
| Game | Check |
|---|---|
| Pokemon R/B | blinds and PiP over BizHawk; full D-pad + A/B reversal; menus reverse too; cooldown keeps it humane |
| Super Metroid | `snes9x*.exe` window match; A/B swap only; no traps in the pool, so test with `--test-item` or map real items |
| OoT | stick inversion on both sticks; Z-target still works; C buttons follow the right stick if that's how you bound them |

## 7. If something's off
| Symptom | Likely cause |
|---|---|
| `Import "overlay" could not be resolved` | `overlay.py` missing from the folder |
| `PySide6... could not be resolved` | wrong interpreter selected, or PySide6 not installed in it |
| `python -m pip` errors in this folder | an old `pip.py` is still here; delete it (now `pip_effect.py`) |
| Overlay on the wrong monitor / offset | window match failed (check process name) or mixed-DPI monitors |
| `effect 'x' is not implemented yet` | the name isn't in `REGISTRY` in `effects.py` |
| `gamepad proxy unavailable` | ViGEmBus driver or `vgamepad` missing |
| Effects work but nothing from the server | slot/game name mismatch, or the item name isn't in the YAML |