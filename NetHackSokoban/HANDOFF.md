# Handoff: NetHack Sokoban iPhone app

Context for a Claude Code session on the Mac that picks this project up.
Written by the cloud session that created the code; updated 2026-09-18 by
the Mac session that first built and installed it.

## What the user wants

A personal, sideloaded iPhone app (Xcode + free Apple ID over USB, so
7-day installs) that plays the eight NetHack Sokoban levels with NetHack's
rules. Design decisions the user made explicitly:

- Movement is "press on a dungeon square" like iNethack2: a tap moves
  (or pushes) one step in the 8-way direction of the tapped square from
  the hero; pressing and holding a square (0.4 s, light haptic) travels
  there. No d-pad, no swipe. (Changed 2026-09-18 from tap-to-travel: the
  user found a light tap triggering a long travel too fluid compared to
  iNethack2.)
- No undo. Instead a **level reset** button and a **pick-axe with penalty**
  button (break an adjacent boulder, costs 1 Luck, tracked in the score).
- Native SwiftUI, iOS 17 minimum.

## What exists

```
NetHackSokoban.xcodeproj/project.pbxproj   hand-written, Xcode 16 format, untested
NetHackSokoban/
  NetHackSokobanApp.swift   @main, NavigationStack, injects Progress
  Levels.swift              GENERATED from tools/sokoban.des, do not hand-edit
  GameModel.swift           Point, LevelDef, Board (rules + travel BFS), Game (taps, travel animation), SokobanRun
  GameView.swift            Canvas renderer, tap/pan/pinch gestures, HUD, solved alert
  LevelSelectView.swift     level list with best scores
  Progress.swift            UserDefaults-backed best scores and run records
  Assets.xcassets/          AppIcon (1024x1024 PNG) + AccentColor
tools/sokoban.des           NetHack 3.6 dat/sokoban.des, verbatim
tools/gen_levels.py         parses the .des, validates positions, writes Levels.swift
tools/icon/make_icon.py     redraws Assets.xcassets/.../AppIcon.png (PIL, SF Mono Bold)
tools/roundtrip/main.swift  save/restore check for Board.Snapshot and SavedRun
tools/solve_check.py        Python port of Board.evaluate() + BFS solver (times out, see below)
tools/solve_greedy.py       best-first variant of the solver (never run)
README.md, NOTICE.md
```

Level naming: NetHack calls the entry level `soko4-*` and the prize level
`soko1-*`. The app presents them as Level 1 (entry) to Level 4 (prize),
variants A and B. `LevelDef.stage` is the app's number; `LevelDef.id` is
NetHack's name. All coordinates are (x, y) = (column, row), 0-based from
the top-left of the map, exactly as in the .des file.

## Run mode (added 2026-09-18 at the user's request)

`SokobanRun` (GameModel.swift) is a full Sokoban run as NetHack deals it:
`SokobanRun.random()` picks one variant per stage up front (e.g. "1B 2A 3A
4B"), and `GameView(run:)` plays them in order, summing moves and luck
penalties across levels and counting level resets (only when the level had
moves). Finishing the prize level stores a `RunRecord` via
`Progress.recordRun`, ranked by (penalties, resets, moves); the level list
shows "Start a run" plus the top five. Per-level bests still record during
a run.

**Run persistence (added 2026-09-18).** A run in progress is written to
UserDefaults (`sokoban.savedrun.v1`) after every move, so killing the app
or backing out to the level list only pauses it. The pieces:

- `Board.Snapshot` is the mutable half of a `Board` (boulders, traps, rocks,
  player, prize, moves, penalties, lastPushMove) keyed by level id;
  `Board.init?(snapshot:)` rebuilds the board on top of its `LevelDef`, so
  the terrain grid is never stored. The message line is deliberately not
  saved: a resumed level starts with a clear one.
- `SavedRun` (GameModel.swift) is that snapshot plus the run's level ids,
  index and totals. `SokobanRun.init?(_ SavedRun)` rebuilds it and refuses
  a run whose level ids no longer resolve, or drops a snapshot whose level
  does not match the run's current one (an old incompatible build).
- `Board.revision` counts every state change; `GameView` saves on
  `.onChange(of: game.board.revision)`, on `.task`, and after a reset (an
  untouched board bumps no revision but does re-roll the prize).
- A solved board is never saved. When a level is solved mid-run the save is
  written as the run will stand *after* the stairs are climbed, because the
  alert's only other choice is "Abandon run", which clears the save.
  Finishing the prize level clears it too.
- The level list shows "Resume run" (variants, level N of 4, total moves)
  with "Start a new run" below it, behind a confirmation that says the run
  in progress will be lost.

"Abandon run" in the solved alert, "New run" on completion, and "Start a
new run" on the level list are the only ways to drop a run.

## Rules implemented (Board.evaluate / Board.step in GameModel.swift)

Mirrors NetHack's `test_move()` and `moverock()` with Sokoban restrictions:

- Walls and solid rock block, silently.
- No diagonal move into or out of a doorway.
- No diagonal move when both orthogonal neighbours are "bad rock"
  (wall, rock, or boulder). This is the Sokoban "cannot pass that way" rule.
- Boulders push only orthogonally; blocked if the square beyond is rock or
  another boulder. Pushing into a pit or hole removes both boulder and trap.
- The hero is refused entry to an unfilled pit or hole (app-level guard;
  in NetHack you would fall in).
- Doors are treated as already open. Monsters and items are omitted.
- Win: step on the up stairs (levels 1 to 3) or on the prize square
  (level 4). The prize is placed at random in one of the three closets and
  drawn only once the hero is adjacent to it.
- Pick-axe: `Board.breakBoulder(at:)` requires an adjacent boulder,
  leaves a `*` rock glyph (cosmetic, non-blocking), increments `penalties`.

Travel (`Board.travelPath(to:)`): 8-direction BFS using the same legality
check with pushing disabled. If the target is unreachable it heads for the
reachable square with the smallest squared distance to the target,
mimicking NetHack's travel "guess". `Game.travel(to:)` animates it at
45 ms/step in a Task; any new touch cancels the travel. `Game.tap` is the
single step via `Point.direction(from:toward:)`.

## Verification status (2026-09-18)

- Builds clean with Xcode 26.6 (zero errors, zero warnings) for both the
  simulator and the device. The hand-written `project.pbxproj` was accepted
  as-is; only `DEVELOPMENT_TEAM` (774G4WJ84P, same as YearTree) and
  `PRODUCT_BUNDLE_IDENTIFIER` (`Hammon.NetHackSokoban`) were filled in.
- Positive rules check DONE: `tools/replay_wiki/main.swift` replays the NetHack
  wiki's full solutions for both entry levels through `Board` and passes
  (1A: 133 pushes, 9 pits filled; 1B: 139 pushes, 10 pits filled; stairs
  reached, `solved == true`). Every push and travel leg the wiki assumes is
  accepted, so `Board.evaluate` matches NetHack on those levels.
- `tools/gen_levels.py` position assertions still pass for all eight levels.
- Installed on the user's iPhone 17 (iOS 26.6.1). Not yet played by hand;
  the on-device feel items (tap vs. pan, solved alert, best-score save) are
  still to be confirmed by the user.
- `tools/solve_check.py` / `solve_greedy.py` remain unrun; superseded by the
  wiki replay for the purpose of validating the rules.
- Save/restore check DONE: `tools/roundtrip/main.swift` wanders every level
  at random, saves, restores, and plays the original and the restored board
  in lockstep for another 200 moves; all eight levels match on every field
  but the message line, and the `SavedRun` guards (mismatched snapshot,
  unknown level id) hold. A saved run is 400-800 bytes of JSON.
  Both harnesses now need `Progress.swift` on the swiftc line (`RunRecord`).

## Deploying to the phone

The user prefers the real phone over the simulator. Recipe that worked:

```
xcodebuild -project NetHackSokoban.xcodeproj -scheme NetHackSokoban \
  -destination 'generic/platform=iOS' -derivedDataPath <dir> \
  -allowProvisioningUpdates build
xcrun devicectl device install app --device <device-id> \
  <dir>/Build/Products/Debug-iphoneos/NetHackSokoban.app
```

Build against `generic/platform=iOS`, not the device id: a device
destination needs the developer disk image mounted, which fails while the
phone is locked (`kAMDMobileImageMounterDeviceLocked`). Install works
locked; launching (`devicectl device process launch`) does not, so the
user taps the icon. The phone was paired over Wi-Fi (`localNetwork`).

## State as of 2026-09-18 evening

Everything is committed on `main`. The project now lives in
`NetHackSokoban/` of the public BdwyJoe27Public repo
(https://github.com/BroadwayJoe27/BdwyJoe27Public), imported 2026-10-07
without its history. Its earlier history (the initial app, the
tap-steps/hold-travels controls, run mode, run persistence and the app
icon) stays in the private repo where it was first developed. The build on
the phone includes run persistence, the 0.23 s hold and the app icon.

Confirmed by the user on the phone: Level 1A end to end, tap/pan, solved
alert, best-score save. The user liked the tap-steps/hold-travels change.
NOT yet tried by the user: run mode, resuming a run, the shorter hold, and
the icon (it lands on the home screen at the next install).

## Suggested next steps, in order

1. User plays a run on the phone. Things to watch: the "Run 2/4" header,
   "Abandon run" in the solved alert, the "Sokoban complete!" alert on
   the prize level, and the ranked list on the level screen.
2. DONE (2026-09-18): runs persist. See "Run persistence" above.
3. Tune feel: `GameView.holdDuration` (now 0.23 s, was 0.4 s; the user asked
   for a shorter dwell before travel fires), `Game.travelStepDelay`
   (45 ms), cell fit padding, `Palette` colours.
4. Nice-to-haves the user has not asked for, so ask first: haptics on push,
   landscape layout. Undo was rejected as a design choice.

## App icon (added 2026-09-18)

The hero, a boulder and a pit in a row (`@ 0 ^`) on a three-cell dungeon
floor, drawn in the app's own `Palette` colours with SF Mono Bold, the same
monospaced face the board renders. The user picked this from five
candidates; the runners-up were the same two glyphs on a diagonal and a
large `@` alone. Regenerate with:

```
python3 tools/icon/make_icon.py NetHackSokoban/Assets.xcassets/AppIcon.appiconset/AppIcon.png
```

The asset catalog uses the single-size (1024x1024, `universal`/`ios`) form,
which Xcode 26 resizes for every slot. Keep the PNG opaque RGB: an alpha
channel is rejected by App Store tooling. No iOS 18 dark or tinted variants
are supplied; the icon is already dark and iOS derives the tinted one.

To rebuild and reinstall after any change, use the two commands under
"Deploying to the phone" above; the phone must be on the same Wi-Fi
(or USB) and unlocked only if you want to launch it from the Mac.

## Licensing

Level layouts are Copyright (c) 1998-1999 Kevin Hugo, NetHack General
Public License (see NOTICE.md). Keep the notice if the code goes anywhere.
